"""Демо-оргструктура и пользователи. Все люди вымышленные, пароль у всех тестовый.

Иерархия (поле Employee.manager — кадровая копия из 1С:ЗУП; User ссылается на Employee):

    ceo  (Дирекция, руководителя нет)
    ├── manager_logistics  (Логистика)
    │   ├── employee
    │   └── 2 сотрудника без учётной записи — для списка «Моя команда»
    └── head_hr  (HR)
        ├── hr_spec_1
        └── hr_spec_2

HR работает по модели «Единое окно / Shared Queue»: все заявки в статусе
WAITING_HR_APPROVAL попадают в общий пул (hr_requests.views.approvals_queryset).
hr_spec_1 и hr_spec_2 имеют к этому пулу одинаковый доступ — заявку берёт любой
свободный специалист. Двойная обработка исключена: переход блокирует строку
(select_for_update) и проверяет статус, второй специалист получит отказ.
"""
from dataclasses import dataclass
from datetime import date

from django.utils import timezone

from accounts.models import Role, User
from hr_requests.models import HrRequest
from notifications.models import Notification
from org.models import Company, Department, Employee, LeaveBalance, Position

DEMO_PASSWORD = "demo1234"


@dataclass
class Person:
    employee: Employee
    user: User | None


def ensure_migrated() -> None:
    """Seed по базе без свежих миграций падает невнятной ошибкой SQL — сообщаем понятно."""
    from django.core.management.base import CommandError
    from django.db import connection
    from django.db.migrations.executor import MigrationExecutor

    executor = MigrationExecutor(connection)
    pending = executor.migration_plan(executor.loader.graph.leaf_nodes())
    if pending:
        names = ", ".join(f"{m.app_label}.{m.name}" for m, _ in pending)
        raise CommandError(
            f"Есть непримененные миграции: {names}.\n"
            "Выполните: docker compose exec backend python manage.py migrate"
        )


def wipe_demo_data() -> None:
    """Очистить пользователей и всё, что на них ссылается, — команду можно запускать повторно.

    Заявки и уведомления удаляются вместе с пользователями: они ссылаются на сотрудников.
    """
    Notification.objects.all().delete()
    HrRequest.objects.all().delete()  # каскадом: история, детали, передачи в бухгалтерию
    User.objects.all().delete()
    LeaveBalance.objects.all().delete()
    Employee.objects.update(manager=None)
    Employee.objects.all().delete()
    Position.objects.all().delete()
    Department.objects.all().delete()
    Company.objects.all().delete()


def create_demo_users() -> dict[str, Person]:
    """Создать оргструктуру и пользователей сверху вниз: сначала CEO, затем руководители, затем рядовые."""
    now = timezone.now()
    today = timezone.localdate()

    company = Company.objects.create(
        name_ru="ТОО «Jana Post» (демо)", name_kk="«Jana Post» ЖШС (демо)", external_id="ZUP-ORG-001"
    )

    def dept(code, ru, kk):
        return Department.objects.create(company=company, name_ru=ru, name_kk=kk, external_id=code)

    d_board = dept("ZUP-DEP-001", "Дирекция", "Дирекция")
    d_log = dept("ZUP-DEP-010", "Логистика", "Логистика")
    d_hr = dept("ZUP-DEP-030", "HR", "HR")

    def pos(code, ru, kk):
        return Position.objects.create(title_ru=ru, title_kk=kk, external_id=code)

    def person(username, role, full_name, department, position, hired, manager=None,
               used_days=0, staff=False, superuser=False) -> Person:
        tab_number = f"T-{Employee.objects.count() + 1:04d}"
        emp = Employee.objects.create(
            full_name=full_name, company=company, department=department, position=position,
            manager=manager.employee if manager else None, hire_date=hired,
            email=f"{tab_number.lower()}@demo.janapost.test", external_id=tab_number, synced_at=now,
        )
        LeaveBalance.objects.create(employee=emp, days_total=24, days_used=used_days, as_of=today, synced_at=now)
        user = None
        if username:
            user = User(username=username, role=role, employee=emp, is_staff=staff, is_superuser=superuser)
            user.set_password(DEMO_PASSWORD)
            user.save()
        return Person(emp, user)

    p = {}
    # 1. CEO — никому не подчиняется. Роль MANAGER + админские права (Django Admin).
    p["ceo"] = person(
        "ceo", Role.MANAGER, "Абенов Нурлан Касымович", d_board,
        pos("ZUP-POS-01", "Генеральный директор", "Бас директор"), date(2015, 1, 12),
        used_days=7, staff=True, superuser=True,
    )
    # 2. Руководитель логистики → CEO
    p["manager_logistics"] = person(
        "manager_logistics", Role.MANAGER, "Бекенов Ерлан Серикович", d_log,
        pos("ZUP-POS-02", "Руководитель отдела логистики", "Логистика бөлімінің басшысы"), date(2018, 9, 3),
        manager=p["ceo"], used_days=14,
    )
    # 4. Head of HR → CEO. Роль HR с полным доступом (в т.ч. Django Admin).
    p["head_hr"] = person(
        "head_hr", Role.HR_ADMIN, "Касымова Динара Маратовна", d_hr,
        pos("ZUP-POS-03", "Руководитель отдела кадров", "Кадр бөлімінің басшысы"), date(2016, 3, 11),
        manager=p["ceo"], used_days=10, staff=True, superuser=True,
    )
    # 3. Обычный сотрудник → руководитель логистики
    p_logist = pos("ZUP-POS-04", "Логист", "Логист")
    p["employee"] = person(
        "employee", Role.EMPLOYEE, "Сапарова Айгерим Нурлановна", d_log, p_logist, date(2022, 2, 14),
        manager=p["manager_logistics"], used_days=7,
    )
    # 5–6. Рядовые HR-специалисты → Head of HR.
    # Равнозначный доступ к общему пулу заявок WAITING_HR_APPROVAL (см. docstring модуля).
    p_hr_spec = pos("ZUP-POS-05", "HR-специалист", "HR-маман")
    p["hr_spec_1"] = person(
        "hr_spec_1", Role.HR_ADMIN, "Нурланова Асель Ериковна", d_hr, p_hr_spec, date(2021, 8, 2),
        manager=p["head_hr"], used_days=6,
    )
    p["hr_spec_2"] = person(
        "hr_spec_2", Role.HR_ADMIN, "Серикбаева Мадина Болатовна", d_hr, p_hr_spec, date(2023, 4, 17),
        manager=p["head_hr"], used_days=2,
    )

    # Коллеги employee без учётной записи: наполняют «Мою команду» и очередь согласования.
    p["colleague_1"] = person(
        None, None, "Омаров Тимур Асланович", d_log, p_logist, date(2023, 6, 1), manager=p["manager_logistics"],
    )
    p["colleague_2"] = person(
        None, None, "Ким Алина Викторовна", d_log,
        pos("ZUP-POS-06", "Координатор складских операций", "Қойма операцияларының үйлестірушісі"),
        date(2021, 11, 22), manager=p["manager_logistics"], used_days=12,
    )
    return p


DEMO_LOGINS = ["ceo", "manager_logistics", "employee", "head_hr", "hr_spec_1", "hr_spec_2"]
