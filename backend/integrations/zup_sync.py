"""Синхронизация кадровых данных из 1С:ЗУП (источник истины) в read-only копию org.*.

Сопоставление по кодам 1С: табельный номер (Employee.external_id), коды подразделений и должностей.
Учётные записи (accounts.User) синхронизация не создаёт — вход в платформу настраивается отдельно.
Сотрудники, которых нет в ЗУП, не удаляются (история заявок и обучения сохраняется).
"""
from django.db import transaction
from django.utils import timezone

from integrations.adapters import get_hris
from integrations.models import SyncRun
from integrations.ports import IntegrationError, ZupSnapshot
from org.models import Company, Department, Employee, LeaveBalance, Position


def _upsert(model, lookup: dict, values: dict) -> str:
    """created | updated | unchanged"""
    obj = model.objects.filter(**lookup).first()
    if obj is None:
        model.objects.create(**lookup, **values)
        return "created"
    changed = [k for k, v in values.items() if getattr(obj, k) != v]
    if not changed:
        return "unchanged"
    for k in changed:
        setattr(obj, k, values[k])
    obj.save(update_fields=changed)
    return "updated"


@transaction.atomic
def apply_snapshot(snap: ZupSnapshot) -> dict:
    now = timezone.now()
    stats = {"departments": {}, "positions": {}, "employees": {}, "balances": {}}

    def count(section, result):
        stats[section][result] = stats[section].get(result, 0) + 1

    _upsert(Company, {"external_id": snap.company_code}, {"name_ru": snap.company_name_ru, "name_kk": snap.company_name_kk})
    company = Company.objects.get(external_id=snap.company_code)

    for d in snap.departments:
        count("departments", _upsert(Department, {"external_id": d.code}, {
            "company": company, "name_ru": d.name_ru, "name_kk": d.name_kk,
        }))
    for d in snap.departments:  # родители — вторым проходом, когда все подразделения есть
        if d.parent_code:
            Department.objects.filter(external_id=d.code).update(
                parent=Department.objects.filter(external_id=d.parent_code).first()
            )
    for p in snap.positions:
        count("positions", _upsert(Position, {"external_id": p.code}, {"title_ru": p.title_ru, "title_kk": p.title_kk}))

    departments = {d.external_id: d for d in Department.objects.all()}
    positions = {p.external_id: p for p in Position.objects.all()}
    for e in snap.employees:
        if e.department_code not in departments or e.position_code not in positions:
            count("employees", "skipped")
            continue
        result = _upsert(Employee, {"external_id": e.tab_number}, {
            "full_name": e.full_name, "company": company,
            "department": departments[e.department_code], "position": positions[e.position_code],
            "hire_date": e.hire_date, "email": e.email, "source": "zup", "dismissed_on": e.dismissed_on,
        })
        count("employees", result)
    Employee.objects.filter(external_id__in=[e.tab_number for e in snap.employees]).update(synced_at=now)

    # руководители — вторым проходом
    employees = {e.external_id: e for e in Employee.objects.all()}
    for e in snap.employees:
        emp = employees.get(e.tab_number)
        manager = employees.get(e.manager_tab_number) if e.manager_tab_number else None
        if emp and emp.manager_id != (manager.id if manager else None):
            emp.manager = manager
            emp.save(update_fields=["manager"])
            count("employees", "manager_changed")

    for b in snap.balances:
        emp = employees.get(b.tab_number)
        if not emp:
            continue
        result = _upsert(LeaveBalance, {"employee": emp, "leave_type": b.leave_type}, {
            "days_total": b.days_total, "days_used": b.days_used, "as_of": b.as_of,
        })
        count("balances", result)
    LeaveBalance.objects.filter(employee__external_id__in=[b.tab_number for b in snap.balances]).update(synced_at=now)
    return stats


def sync_from_zup(trigger: str = "manual") -> SyncRun:
    """Загрузить снимок из 1С:ЗУП и применить. Ошибка внешней системы пишется в журнал, а не роняет вызов."""
    hris = get_hris()
    run = SyncRun.objects.create(
        provider=getattr(hris, "name", "none"), trigger=trigger, status=SyncRun.RunStatus.FAILED
    )
    try:
        if hris is None:
            raise IntegrationError("Интеграция с 1С:ЗУП отключена (HRIS_PROVIDER=none)")
        run.stats = apply_snapshot(hris.fetch_snapshot())
        run.status = SyncRun.RunStatus.OK
        # сменился руководитель или пришла дата увольнения — пересчитать согласующих
        from hr_requests.routing import sync_pending

        run.stats["rerouted_requests"] = sync_pending()
    except IntegrationError as exc:
        run.error = str(exc)
    run.finished_at = timezone.now()
    run.save()
    return run
