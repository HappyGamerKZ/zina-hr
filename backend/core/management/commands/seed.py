"""Полные демо-данные: пользователи (core/demo_users.py) + заявки во всех статусах + уведомления.

python manage.py seed          — заполнить, если база пустая
python manage.py seed --reset  — удалить демо-данные и заполнить заново
"""
from datetime import date, datetime, time, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from core.demo_users import DEMO_LOGINS, DEMO_PASSWORD, create_demo_users, wipe_demo_data
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

W_MGR, W_HR = Status.WAITING_MANAGER_APPROVAL, Status.WAITING_HR_APPROVAL
DONE, REJ, CANC = Status.APPROVED_SENT_TO_1C, Status.REJECTED, Status.CANCELLED


def at(d: date, hour: int = 10) -> datetime:
    return timezone.make_aware(datetime.combine(d, time(hour, 0)))


def make_request(employee, author, req_type, chain, created, vacation=None, advance=None):
    """chain: [(статус, кто, комментарий), ...] — первый элемент = создание."""
    req = HrRequest.objects.create(type=req_type, employee=employee, status=chain[-1][0], created_by=author)
    if vacation:
        d_from, d_to = vacation
        VacationDetails.objects.create(request=req, date_from=d_from, date_to=d_to, days=(d_to - d_from).days + 1)
    if advance:
        AdvanceDetails.objects.create(request=req, amount=advance[0], reason=advance[1])
    prev = ""
    for i, (st, actor, comment) in enumerate(chain):
        ev = RequestEvent.objects.create(request=req, from_status=prev, to_status=st, actor=actor, comment=comment)
        RequestEvent.objects.filter(pk=ev.pk).update(created_at=created + timedelta(hours=20 * i))
        prev = st
    HrRequest.objects.filter(pk=req.pk).update(
        created_at=created, updated_at=created + timedelta(hours=20 * (len(chain) - 1))
    )
    req.refresh_from_db()
    if req.status == DONE:
        _sent_to_1c(req, auto=len(chain) == 1)
    return req


def _sent_to_1c(req, auto: bool) -> None:
    """Утверждённая заявка в журнале передач в 1С / бухгалтерию (mock)."""
    external_id = f"BUH-{req.created_at:%Y}-{AccountingExport.objects.count() + 1:05d}"
    AccountingExport.objects.create(
        request=req, provider="mock_accounting", payload=build_accounting_payload(req),
        status=AccountingExport.ExportStatus.SENT, external_id=external_id,
    )
    HrRequest.objects.filter(pk=req.pk).update(external_accounting_id=external_id)
    note = f"Передано в 1С / бухгалтерию, документ № {external_id}"
    if auto:
        note = "Руководитель не назначен — утверждено автоматически. " + note
    RequestEvent.objects.filter(request=req, to_status=DONE).update(comment=note)


class Command(BaseCommand):
    help = "Заполнить базу демо-данными JanaМен"

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true")

    @transaction.atomic
    def handle(self, *args, reset=False, **options):
        if not reset and User.objects.filter(username="employee").exists():
            self.stdout.write("Демо-данные уже есть, пропускаю (используйте --reset).")
            return
        wipe_demo_data()
        p = create_demo_users()
        u = {k: v.user for k, v in p.items()}
        e = {k: v.employee for k, v in p.items()}
        today = timezone.localdate()
        now = timezone.now()

        # employee: полный путь руководитель → HR (общий пул) → 1С; отменённая заявка
        make_request(
            e["employee"], u["employee"], RequestType.VACATION,
            [(W_MGR, u["employee"], ""), (W_HR, u["manager_logistics"], ""), (DONE, u["hr_spec_1"], "")],
            at(date(2026, 4, 6)), vacation=(date(2026, 5, 4), date(2026, 5, 10)),
        )
        adv = make_request(
            e["employee"], u["employee"], RequestType.ADVANCE,
            [(W_MGR, u["employee"], ""), (W_HR, u["manager_logistics"], ""), (DONE, u["hr_spec_2"], "")],
            at(today - timedelta(days=9)), advance=(80000, "Оплата обучения ребёнка"),
        )
        make_request(
            e["employee"], u["employee"], RequestType.VACATION,
            [(W_MGR, u["employee"], ""), (CANC, u["employee"], "Перенесу на зиму")],
            at(today - timedelta(days=30)), vacation=(today + timedelta(days=20), today + timedelta(days=24)),
        )

        # Команда логистики: ждёт руководителя; две заявки в общем пуле HR; отклонённая
        make_request(
            e["colleague_1"], None, RequestType.VACATION, [(W_MGR, None, "")],
            at(today - timedelta(days=1)), vacation=(today + timedelta(days=46), today + timedelta(days=59)),
        )
        make_request(
            e["colleague_1"], None, RequestType.ADVANCE, [(W_MGR, None, ""), (W_HR, u["manager_logistics"], "")],
            at(today - timedelta(days=2)), advance=(50000, "Медицинские расходы"),
        )
        make_request(
            e["colleague_2"], None, RequestType.ADVANCE, [(W_MGR, None, ""), (W_HR, u["manager_logistics"], "")],
            at(today - timedelta(days=3)), advance=(120000, "Непредвиденные расходы"),
        )
        make_request(
            e["colleague_2"], None, RequestType.VACATION,
            [(W_MGR, None, ""), (REJ, u["manager_logistics"], "Пик сезона, предлагаю перенести на январь")],
            at(today - timedelta(days=12)), vacation=(today + timedelta(days=5), today + timedelta(days=18)),
        )

        # manager_logistics: отпуск ждёт CEO; после одобрения уйдёт в общий пул HR
        mgr_vac = make_request(
            e["manager_logistics"], u["manager_logistics"], RequestType.VACATION,
            [(W_MGR, u["manager_logistics"], "")],
            at(today - timedelta(days=1)), vacation=(today + timedelta(days=40), today + timedelta(days=49)),
        )

        # hr_spec_1: аванс ждёт head_hr; после её одобрения — сразу в 1С (без шага HR)
        hr_adv = make_request(
            e["hr_spec_1"], u["hr_spec_1"], RequestType.ADVANCE, [(W_MGR, u["hr_spec_1"], "")],
            at(today - timedelta(days=1)), advance=(60000, "Ремонт автомобиля"),
        )

        # ceo: руководителя нет → утверждено автоматически при создании
        make_request(
            e["ceo"], u["ceo"], RequestType.VACATION, [(DONE, u["ceo"], "")],
            at(today - timedelta(days=20)), vacation=(today + timedelta(days=60), today + timedelta(days=66)),
        )

        def note(user, type_, title, body, link, days_ago, read=False):
            n = Notification.objects.create(user=user, type=type_, title=title, body=body, link=link, is_read=read)
            Notification.objects.filter(pk=n.pk).update(created_at=now - timedelta(days=days_ago))

        new = NotificationType.REQUEST_SUBMITTED
        note(u["employee"], NotificationType.REQUEST_STATUS_CHANGED,
             f"Заявка {adv.number}: утверждено / передано в 1С",
             "Аванс 80 000 ₸: приказ оформлен, передано в бухгалтерию", f"/requests/{adv.pk}", 7)
        note(u["employee"], NotificationType.COURSE_ASSIGNED, "Назначен курс «Адаптация в Jana Post»",
             "Пройдите курс до конца месяца", "/academy", 2)
        note(u["manager_logistics"], new, "Новая заявка на отпуск",
             "Омаров Тимур Асланович отправил заявку на согласование", "/team/approvals", 1)
        for hr in ("hr_spec_1", "hr_spec_2", "head_hr"):  # общий пул: уведомление получают все HR
            note(u[hr], new, "2 заявки ждут оформления приказа",
                 "Аванс: Омаров Тимур Асланович, Ким Алина Викторовна", "/team/approvals", 1)
        note(u["head_hr"], new, f"Новая заявка {hr_adv.number}: аванс",
             "Нурланова Асель Ериковна отправила заявку на согласование", f"/requests/{hr_adv.pk}", 1)
        note(u["ceo"], new, f"Новая заявка {mgr_vac.number}: отпуск",
             "Бекенов Ерлан Серикович отправил заявку на согласование", f"/requests/{mgr_vac.pk}", 1)

        self.stdout.write(self.style.SUCCESS(
            f"Готово: логины {', '.join(DEMO_LOGINS)}; пароль {DEMO_PASSWORD}"
        ))
