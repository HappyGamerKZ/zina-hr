"""Тестовые данные для демо. Все люди вымышленные, пароли тестовые.

python manage.py seed          — заполнить, если база пустая
python manage.py seed --reset  — удалить демо-данные и заполнить заново
"""
from datetime import date, datetime, time, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import Role, User
from hr_requests.models import (
    AdvanceDetails,
    HrRequest,
    RequestEvent,
    RequestType,
    Status,
    VacationDetails,
)
from integrations.models import AccountingExport
from integrations.services import build_accounting_payload
from notifications.models import Notification, NotificationType
from org.models import Company, Department, Employee, LeaveBalance, Position

DEMO_PASSWORD = "demo1234"


def at(d: date, hour: int = 10) -> datetime:
    return timezone.make_aware(datetime.combine(d, time(hour, 0)))


class Command(BaseCommand):
    help = "Заполнить базу тестовыми данными JanaМен"

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true")

    @transaction.atomic
    def handle(self, *args, reset=False, **options):
        if reset:
            Notification.objects.all().delete()
            HrRequest.objects.all().delete()
            User.objects.all().delete()
            LeaveBalance.objects.all().delete()
            Employee.objects.update(manager=None)
            Employee.objects.all().delete()
            Position.objects.all().delete()
            Department.objects.all().delete()
            Company.objects.all().delete()
        elif User.objects.filter(username="employee").exists():
            self.stdout.write("Демо-данные уже есть, пропускаю (используйте --reset).")
            return

        now = timezone.now()
        today = timezone.localdate()

        company = Company.objects.create(
            name_ru="ТОО «Jana Post» (демо)", name_kk="«Jana Post» ЖШС (демо)", external_id="ZUP-ORG-001"
        )
        dep_log = Department.objects.create(
            company=company, name_ru="Отдел логистики", name_kk="Логистика бөлімі", external_id="ZUP-DEP-010"
        )
        dep_sales = Department.objects.create(
            company=company, name_ru="Отдел продаж", name_kk="Сату бөлімі", external_id="ZUP-DEP-020"
        )
        dep_hr = Department.objects.create(
            company=company, name_ru="HR-департамент", name_kk="HR-департамент", external_id="ZUP-DEP-030"
        )

        def pos(code, ru, kk):
            return Position.objects.create(title_ru=ru, title_kk=kk, external_id=code)

        p_head_log = pos("ZUP-POS-01", "Руководитель отдела логистики", "Логистика бөлімінің басшысы")
        p_logist = pos("ZUP-POS-02", "Специалист по логистике", "Логистика маманы")
        p_coord = pos("ZUP-POS-03", "Координатор складских операций", "Қойма операцияларының үйлестірушісі")
        p_head_sales = pos("ZUP-POS-04", "Руководитель отдела продаж", "Сату бөлімінің басшысы")
        p_sales = pos("ZUP-POS-05", "Менеджер по продажам", "Сату менеджері")
        p_hr_head = pos("ZUP-POS-06", "Директор по персоналу", "Персонал жөніндегі директор")
        p_hr = pos("ZUP-POS-07", "HR-специалист", "HR-маман")

        def emp(code, name, dep, position, hired, manager=None, total=24, used=0):
            e = Employee.objects.create(
                full_name=name, company=company, department=dep, position=position, manager=manager,
                hire_date=hired, email=f"{code.lower()}@demo.janapost.test", external_id=code,
                synced_at=now,
            )
            LeaveBalance.objects.create(
                employee=e, days_total=total, days_used=used, as_of=today, synced_at=now
            )
            return e

        # Маршрут согласования зависит от manager_id и роли автора:
        #   hr_head  — manager_id = null → его заявки утверждаются сразу;
        #   hr       — HR-специалист, руководитель hr_head → после hr_head сразу в 1С (без шага HR);
        #   employee — сотрудник, руководитель manager → manager → HR → 1С.
        hr_head_e = emp("T-0001", "Касымова Динара Маратовна", dep_hr, p_hr_head, date(2016, 3, 11), used=17)
        hr_e = emp("T-0008", "Нурланова Асель Ериковна", dep_hr, p_hr, date(2021, 8, 2),
                   manager=hr_head_e, used=6)
        mgr_e = emp("T-0002", "Бекенов Ерлан Серикович", dep_log, p_head_log, date(2018, 9, 3), used=14)
        empl_e = emp("T-0003", "Сапарова Айгерим Нурлановна", dep_log, p_logist, date(2022, 2, 14),
                     manager=mgr_e, used=7)
        col1_e = emp("T-0004", "Омаров Тимур Асланович", dep_log, p_logist, date(2023, 6, 1),
                     manager=mgr_e, used=0)
        col2_e = emp("T-0005", "Ким Алина Викторовна", dep_log, p_coord, date(2021, 11, 22),
                     manager=mgr_e, used=12)
        sales_head_e = emp("T-0006", "Ахметова Сауле Кайратовна", dep_sales, p_head_sales,
                           date(2017, 4, 17), used=5)
        sales_e = emp("T-0007", "Жумабаев Арман Даулетович", dep_sales, p_sales, date(2024, 1, 15),
                      manager=sales_head_e, used=3)

        def user(username, role, employee, staff=False):
            u = User(username=username, role=role, employee=employee, is_staff=staff, is_superuser=staff)
            u.set_password(DEMO_PASSWORD)
            u.save()
            return u

        u_hr_head = user("hr_head", Role.HR_ADMIN, hr_head_e, staff=True)
        u_hr = user("hr", Role.HR_ADMIN, hr_e, staff=True)
        u_mgr = user("manager", Role.MANAGER, mgr_e)
        u_emp = user("employee", Role.EMPLOYEE, empl_e)
        user("employee2", Role.EMPLOYEE, sales_e)
        u_sales_head = user("sales_head", Role.MANAGER, sales_head_e)

        def make_request(employee, author, req_type, chain, created, vacation=None, advance=None):
            """chain: [(статус, кто, комментарий), ...] — первый элемент = создание."""
            req = HrRequest.objects.create(
                type=req_type, employee=employee, status=chain[-1][0], created_by=author
            )
            if vacation:
                d_from, d_to = vacation
                VacationDetails.objects.create(
                    request=req, date_from=d_from, date_to=d_to, days=(d_to - d_from).days + 1
                )
            if advance:
                AdvanceDetails.objects.create(request=req, amount=advance[0], reason=advance[1])
            prev = ""
            for i, (st, actor, comment) in enumerate(chain):
                ev = RequestEvent.objects.create(
                    request=req, from_status=prev, to_status=st, actor=actor, comment=comment
                )
                RequestEvent.objects.filter(pk=ev.pk).update(created_at=created + timedelta(hours=20 * i))
                prev = st
            HrRequest.objects.filter(pk=req.pk).update(
                created_at=created, updated_at=created + timedelta(hours=20 * (len(chain) - 1))
            )
            req.refresh_from_db()
            return req

        def sent_to_1c(req):
            """Утверждённая заявка в журнале передач в 1С / бухгалтерию (mock)."""
            seq = AccountingExport.objects.count() + 1
            external_id = f"BUH-{req.created_at:%Y}-{seq:05d}"
            AccountingExport.objects.create(
                request=req, provider="mock_accounting", payload=build_accounting_payload(req),
                status=AccountingExport.ExportStatus.SENT, external_id=external_id,
            )
            HrRequest.objects.filter(pk=req.pk).update(external_accounting_id=external_id)
            return f"Передано в 1С / бухгалтерию, документ № {external_id}"

        W_MGR, W_HR = Status.WAITING_MANAGER_APPROVAL, Status.WAITING_HR_APPROVAL
        DONE, REJ, CANC = Status.APPROVED_SENT_TO_1C, Status.REJECTED, Status.CANCELLED

        # employee (сотрудник): полный путь manager → HR → 1С, плюс отменённая заявка
        vac = make_request(
            empl_e, u_emp, RequestType.VACATION,
            [(W_MGR, u_emp, ""), (W_HR, u_mgr, ""), (DONE, u_hr, "")],
            at(date(2026, 4, 6)), vacation=(date(2026, 5, 4), date(2026, 5, 10)),
        )
        RequestEvent.objects.filter(request=vac, to_status=DONE).update(comment=sent_to_1c(vac))
        adv = make_request(
            empl_e, u_emp, RequestType.ADVANCE,
            [(W_MGR, u_emp, ""), (W_HR, u_mgr, ""), (DONE, u_hr, "")],
            at(today - timedelta(days=9)), advance=(80000, "Оплата обучения ребёнка"),
        )
        RequestEvent.objects.filter(request=adv, to_status=DONE).update(comment=sent_to_1c(adv))
        make_request(
            empl_e, u_emp, RequestType.VACATION,
            [(W_MGR, u_emp, ""), (CANC, u_emp, "Перенесу на зиму")],
            at(today - timedelta(days=30)), vacation=(today + timedelta(days=20), today + timedelta(days=24)),
        )

        # Команда manager: ждёт руководителя, ждёт HR, отклонённая
        make_request(
            col1_e, None, RequestType.VACATION, [(W_MGR, None, "")],
            at(today - timedelta(days=1)), vacation=(today + timedelta(days=46), today + timedelta(days=59)),
        )
        make_request(
            col2_e, None, RequestType.ADVANCE, [(W_MGR, None, ""), (W_HR, u_mgr, "")],
            at(today - timedelta(days=3)), advance=(120000, "Непредвиденные расходы"),
        )
        make_request(
            col2_e, None, RequestType.VACATION,
            [(W_MGR, None, ""), (REJ, u_mgr, "Пик сезона, предлагаю перенести на январь")],
            at(today - timedelta(days=12)), vacation=(today + timedelta(days=5), today + timedelta(days=18)),
        )

        # hr (HR-специалист): аванс ждёт hr_head; после её одобрения уйдёт сразу в 1С
        hr_adv = make_request(
            hr_e, u_hr, RequestType.ADVANCE, [(W_MGR, u_hr, "")],
            at(today - timedelta(days=1)), advance=(60000, "Ремонт автомобиля"),
        )

        # hr_head (без руководителя): заявка утверждена автоматически при создании
        head_vac = make_request(
            hr_head_e, u_hr_head, RequestType.VACATION, [(DONE, u_hr_head, "")],
            at(today - timedelta(days=20)), vacation=(today + timedelta(days=60), today + timedelta(days=66)),
        )
        RequestEvent.objects.filter(request=head_vac).update(
            comment="Руководитель не назначен — утверждено автоматически. " + sent_to_1c(head_vac)
        )

        # Другой отдел: manager эту заявку видеть не должен
        make_request(
            sales_e, None, RequestType.VACATION, [(W_MGR, None, "")],
            at(today - timedelta(days=2)), vacation=(today + timedelta(days=30), today + timedelta(days=36)),
        )

        def note(u, type_, title, body, link, read, days_ago):
            n = Notification.objects.create(user=u, type=type_, title=title, body=body, link=link, is_read=read)
            Notification.objects.filter(pk=n.pk).update(created_at=now - timedelta(days=days_ago))

        note(u_emp, NotificationType.REQUEST_STATUS_CHANGED, f"Заявка {adv.number}: утверждено / передано в 1С",
             "Аванс 80 000 ₸: приказ оформлен, передано в бухгалтерию", f"/requests/{adv.pk}", False, 7)
        note(u_emp, NotificationType.COURSE_ASSIGNED, "Назначен курс «Адаптация в Jana Post»",
             "Пройдите курс до конца месяца", "/academy", False, 2)
        note(u_mgr, NotificationType.REQUEST_SUBMITTED, "Новая заявка на отпуск",
             "Омаров Тимур Асланович отправил заявку на согласование", "/team/approvals", False, 1)
        note(u_hr, NotificationType.REQUEST_SUBMITTED, "Заявка на аванс ждёт оформления приказа",
             "Ким Алина Викторовна: аванс, одобрено руководителем", "/team/approvals", False, 2)
        note(u_hr_head, NotificationType.REQUEST_SUBMITTED, f"Новая заявка {hr_adv.number}: аванс",
             "Нурланова Асель Ериковна отправила заявку на согласование", f"/requests/{hr_adv.pk}", False, 1)
        note(u_sales_head, NotificationType.REQUEST_SUBMITTED, "Новая заявка на отпуск",
             "Жумабаев Арман Даулетович отправил заявку на согласование", "/team/approvals", False, 2)

        self.stdout.write(self.style.SUCCESS(
            "Готово: логины employee / manager / hr / hr_head / employee2 / sales_head, "
            f"пароль {DEMO_PASSWORD}"
        ))
