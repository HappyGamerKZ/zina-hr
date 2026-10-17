from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import F, Sum
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from core import events
from hr_requests import state_machine
from integrations import services as accounting
from hr_requests.models import (
    RESERVING_STATUSES,
    VACATION_BLOCKING_STATUSES,
    AdvanceDetails,
    HrRequest,
    RequestEvent,
    RequestType,
    Status,
    VacationDetails,
    VacationType,
)
from org.models import Employee, LeaveBalance


def vacation_balance(employee: Employee) -> dict:
    """Остаток ежегодного отпуска: данные 1С:ЗУП минус дни в ещё не оформленных заявках."""
    balance = LeaveBalance.objects.filter(employee=employee, leave_type="annual").first()
    total = balance.days_total if balance else 0
    used = balance.days_used if balance else 0
    reserved = (
        VacationDetails.objects.filter(
            request__employee=employee,
            request__status__in=RESERVING_STATUSES,
            vacation_type=VacationType.ANNUAL,
        ).aggregate(s=Sum("days"))["s"]
        or 0
    )
    return {
        "days_total": total,
        "days_used": used,
        "days_reserved": reserved,
        "days_available": max(total - used - reserved, 0),
        "as_of": balance.as_of if balance else None,
        "synced_at": balance.synced_at if balance else None,
    }


def busy_vacations(employee: Employee, exclude_request_id: int | None = None):
    """Отпуска сотрудника, дни которых уже заняты (на согласовании или утверждены)."""
    qs = VacationDetails.objects.filter(
        request__employee=employee, request__status__in=VACATION_BLOCKING_STATUSES
    ).select_related("request").order_by("date_from")
    if exclude_request_id is not None:
        qs = qs.exclude(request_id=exclude_request_id)
    return qs


def _check_overlap(employee: Employee, date_from, date_to, exclude_request_id: int | None = None) -> None:
    clash = busy_vacations(employee, exclude_request_id).filter(
        date_from__lte=date_to, date_to__gte=date_from
    ).first()
    if clash:
        r = clash.request
        raise ValidationError({"date_from": (
            f"Даты пересекаются с заявкой {r.number} "
            f"({clash.date_from:%d.%m.%Y}–{clash.date_to:%d.%m.%Y}, «{r.get_status_display()}»)"
        )})


def _validate_vacation(employee: Employee, data: dict, exclude_request_id: int | None = None) -> int:
    date_from, date_to = data["date_from"], data["date_to"]
    if date_from < timezone.localdate():
        raise ValidationError({"date_from": "Дата начала отпуска не может быть в прошлом"})
    if date_to < date_from:
        raise ValidationError({"date_to": "Дата окончания раньше даты начала"})
    _check_overlap(employee, date_from, date_to, exclude_request_id)
    days = (date_to - date_from).days + 1  # календарные дни
    if data.get("vacation_type", VacationType.ANNUAL) == VacationType.ANNUAL:
        available = vacation_balance(employee)["days_available"]
        if days > available:
            raise ValidationError(
                {"date_to": f"Запрошено {days} дн., доступно {available} дн. ежегодного отпуска"}
            )
    return days


def _validate_advance(data: dict) -> None:
    amount = Decimal(data["amount"])
    if amount <= 0:
        raise ValidationError({"amount": "Сумма должна быть больше нуля"})
    if amount > settings.ADVANCE_MAX_AMOUNT:
        raise ValidationError({"amount": f"Максимальная сумма аванса — {settings.ADVANCE_MAX_AMOUNT} ₸"})


@transaction.atomic
def create_request(user, req_type: str, details: dict, as_draft: bool = False) -> HrRequest:
    if user.employee is None:
        raise PermissionDenied("Учётная запись не связана с сотрудником")
    # Блокировка строки сотрудника: две одновременные заявки не проскочат проверку пересечения.
    employee = Employee.objects.select_for_update().get(pk=user.employee_id)

    if req_type == RequestType.VACATION:
        days = _validate_vacation(employee, details)
    else:
        _validate_advance(details)

    status = Status.DRAFT if as_draft else state_machine.initial_status(employee)
    req = HrRequest.objects.create(type=req_type, employee=employee, status=status, created_by=user)
    if req_type == RequestType.VACATION:
        VacationDetails.objects.create(
            request=req,
            date_from=details["date_from"],
            date_to=details["date_to"],
            days=days,
            vacation_type=details.get("vacation_type", VacationType.ANNUAL),
            comment=details.get("comment", ""),
        )
    else:
        AdvanceDetails.objects.create(
            request=req, amount=details["amount"], reason=details.get("reason", "")
        )
    comment = ""
    if status == Status.APPROVED_SENT_TO_1C:
        comment = "Руководитель не назначен — утверждено автоматически. " + _finalize_approved(req)
    RequestEvent.objects.create(request=req, from_status="", to_status=status, actor=user, comment=comment)

    transaction.on_commit(lambda: _publish(req, old_status="", actor=user))
    return req


@transaction.atomic
def apply_transition(user, req: HrRequest, action: str, comment: str = "") -> HrRequest:
    req = HrRequest.objects.select_for_update(of=("self",)).select_related("employee").get(pk=req.pk)
    new_status = state_machine.next_status(user, req, action)
    if new_status is None:
        raise ValidationError(
            {"action": f"Действие «{action}» недоступно для заявки в статусе «{req.get_status_display()}»"}
        )
    if action == state_machine.REJECT and not comment.strip():
        raise ValidationError({"comment": "Укажите причину отклонения"})
    if action == state_machine.SUBMIT and req.type == RequestType.VACATION:
        _validate_vacation(req.employee, {
            "date_from": req.vacation.date_from,
            "date_to": req.vacation.date_to,
            "vacation_type": req.vacation.vacation_type,
        }, exclude_request_id=req.pk)
    if action in (state_machine.APPROVE_MANAGER, state_machine.APPROVE_HR) and req.type == RequestType.VACATION:
        # Повторная проверка при одобрении: даты не должны пересекаться с другими отпусками сотрудника.
        _check_overlap(req.employee, req.vacation.date_from, req.vacation.date_to, exclude_request_id=req.pk)

    old_status = req.status
    req.status = new_status
    req.save(update_fields=["status", "updated_at"])
    if new_status == Status.APPROVED_SENT_TO_1C:
        note = _finalize_approved(req)
        comment = f"{comment.strip()}\n{note}" if comment.strip() else note
    RequestEvent.objects.create(
        request=req, from_status=old_status, to_status=new_status, actor=user, comment=comment
    )

    transaction.on_commit(lambda: _publish(req, old_status=old_status, actor=user))
    return req


def _finalize_approved(req: HrRequest) -> str:
    """Утверждённая заявка уходит в 1С / бухгалтерию (mock); дни отпуска списываются из остатка."""
    if req.type == RequestType.VACATION and req.vacation.vacation_type == VacationType.ANNUAL:
        # Имитация проводки в 1С:ЗУП: в боевом режиме days_used придёт синхронизацией.
        LeaveBalance.objects.filter(employee=req.employee, leave_type="annual").update(
            days_used=F("days_used") + req.vacation.days
        )
    export = accounting.send_to_accounting(req)
    if export.status != export.ExportStatus.SENT:
        return "Ошибка передачи в 1С — см. журнал интеграций"
    req.external_accounting_id = export.external_id
    req.save(update_fields=["external_accounting_id", "updated_at"])
    return f"Передано в 1С / бухгалтерию, документ № {export.external_id}"


def _publish(req: HrRequest, old_status: str, actor) -> None:
    if req.status == Status.WAITING_MANAGER_APPROVAL:
        events.publish(events.REQUEST_SUBMITTED, request=req)
    elif req.status != Status.DRAFT:
        events.publish(events.REQUEST_STATUS_CHANGED, request=req, old_status=old_status, actor=actor)

