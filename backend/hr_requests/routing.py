"""Кто согласует заявку на шаге руководителя, если руководитель в отпуске или уволен.

Правило (считается заново при каждой проверке, поэтому маршрут меняется сам):
    1. Руководитель автора на месте → он.
    2. Руководителя нет (отпуск / увольнение), но он назначил И.О. на эти даты → И.О.
    3. Иначе → вышестоящий руководитель, и для него те же правила (до CEO).
    4. Никого нет на месте по всей цепочке → общий пул HR.

«Нет на месте» — уволен (дата увольнения из 1С:ЗУП наступила, учётная запись отключена)
или в утверждённом отпуске на эту дату. И.О. не согласует собственные заявки.

Сохранённое поле HrRequest.current_approver нужно для списка «Согласование», уведомлений
и истории; права проверяются по живому расчёту resolve_approver().
"""
from dataclasses import dataclass, field
from datetime import date

from django.db import transaction
from django.utils import timezone

from accounts.models import User
from hr_requests.models import HrRequest, RequestEvent, RequestType, Status
from org.models import Delegation, Employee

DIRECT, DEPUTY, ESCALATED, HR_POOL = "manager", "deputy", "escalated", "hr_pool"


@dataclass
class Route:
    kind: str  # manager | deputy | escalated | hr_pool
    approver: Employee | None  # None — общий пул HR
    acting_for: Employee | None = None  # за кого действует И.О.
    absent: list[Employee] = field(default_factory=list)  # кого пропустили по цепочке


def absence_reason(employee: Employee, on: date) -> str | None:
    """«уволен» / «в отпуске» / None — на месте."""
    if employee.dismissed_on and employee.dismissed_on <= on:
        return "уволен"
    if User.objects.filter(employee=employee, is_active=False).exists():  # учётная запись отключена
        return "уволен"
    on_vacation = HrRequest.objects.filter(
        employee=employee, type=RequestType.VACATION, status=Status.APPROVED_SENT_TO_1C,
        vacation__date_from__lte=on, vacation__date_to__gte=on,
    ).exists()
    return "в отпуске" if on_vacation else None


def active_deputy(manager: Employee, on: date) -> Employee | None:
    delegation = (
        Delegation.objects.filter(manager=manager, revoked_at__isnull=True, date_from__lte=on, date_to__gte=on)
        .select_related("deputy__user").order_by("-created_at").first()
    )
    return delegation.deputy if delegation else None


def resolve_approver(requester: Employee, on: date | None = None) -> Route | None:
    """Маршрут шага руководителя. None — у автора нет руководителя (заявка утверждается сразу)."""
    on = on or timezone.localdate()
    manager = requester.manager
    if manager is None:
        return None
    absent: list[Employee] = []
    seen = {requester.pk}
    while manager is not None and manager.pk not in seen:
        seen.add(manager.pk)
        if absence_reason(manager, on) is None:
            return Route(ESCALATED if absent else DIRECT, manager, absent=absent)
        deputy = active_deputy(manager, on)
        if deputy is not None and deputy.pk != requester.pk and absence_reason(deputy, on) is None:
            return Route(DEPUTY, deputy, acting_for=manager, absent=absent + [manager])
        absent.append(manager)
        manager = manager.manager
    return Route(HR_POOL, None, absent=absent)


def describe(route: Route, on: date | None = None) -> str:
    """Текст для истории заявки и уведомлений."""
    on = on or timezone.localdate()
    why = ", ".join(f"{e.full_name} — {absence_reason(e, on)}" for e in route.absent)
    if route.kind == DIRECT:
        return f"Согласует руководитель: {route.approver.full_name}"
    if route.kind == DEPUTY:
        return f"Согласует И.О. {route.approver.full_name} за {route.acting_for.full_name} ({why})"
    if route.kind == ESCALATED:
        return f"Согласует вышестоящий руководитель {route.approver.full_name} ({why})"
    return f"Руководителей нет на месте ({why}) — согласует HR"


def sync_request(req: HrRequest, on: date | None = None, notify: bool = True) -> bool:
    """Обновить согласующего у заявки на шаге руководителя. True — согласующий сменился."""
    if req.status != Status.WAITING_MANAGER_APPROVAL:
        return False
    route = resolve_approver(req.employee, on)
    if route is None:
        return False
    new_id = route.approver.pk if route.approver else None
    if req.current_approver_id == new_id and req.approver_kind == route.kind:
        return False
    first = req.approver_kind == ""
    req.current_approver = route.approver
    req.approver_kind = route.kind
    req.save(update_fields=["current_approver", "approver_kind", "updated_at"])
    if not first:
        text = describe(route, on)
        RequestEvent.objects.create(request=req, from_status=req.status, to_status=req.status, actor=None,
                                    comment=f"Согласующий изменён. {text}")
        if notify:
            from core import events

            transaction.on_commit(lambda: events.publish(events.REQUEST_REROUTED, request=req, text=text))
    return True


def sync_pending(on: date | None = None) -> int:
    """Пересчитать согласующих у всех заявок, ждущих руководителя (worker, замещения, увольнения)."""
    changed = 0
    qs = HrRequest.objects.filter(status=Status.WAITING_MANAGER_APPROVAL).select_related("employee__manager")
    for req in qs:
        with transaction.atomic():
            changed += sync_request(req, on)
    return changed
