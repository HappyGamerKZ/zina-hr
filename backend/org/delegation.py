"""Замещение руководителя (И.О.): кого можно назначить, создание и отмена.

После каждого изменения заявки на шаге руководителя пересчитываются (hr_requests/routing.py):
пока руководитель на месте, И.О. ничего не согласует — замещение срабатывает, только когда
руководитель в отпуске или уволен.
"""
from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from org.models import Delegation, Employee

MAX_DAYS = 92


def can_delegate(employee: Employee | None) -> bool:
    """Назначать И.О. может тот, у кого есть подчинённые."""
    return employee is not None and employee.reports.exists()


def candidates(manager: Employee):
    """И.О. — из своей команды (прямые подчинённые) или своего подразделения, с учётной записью и не уволенный."""
    today = timezone.localdate()
    return (
        Employee.objects.filter(Q(manager=manager) | Q(department_id=manager.department_id))
        .exclude(pk=manager.pk)
        .filter(user__is_active=True)
        .filter(Q(dismissed_on__isnull=True) | Q(dismissed_on__gt=today))
        .select_related("position")
        .distinct()
        .order_by("full_name")
    )


def _resync():
    from hr_requests import routing

    transaction.on_commit(routing.sync_pending)


@transaction.atomic
def create(user, deputy_id: int, date_from, date_to) -> Delegation:
    manager = user.employee
    if not can_delegate(manager):
        raise PermissionDenied("Назначать исполняющего обязанности может руководитель")
    deputy = candidates(manager).filter(pk=deputy_id).first()
    if deputy is None:
        raise ValidationError({"deputy_id": "И.О. выбирается из вашей команды или подразделения"})
    today = timezone.localdate()
    if date_from < today:
        raise ValidationError({"date_from": "Дата начала не может быть в прошлом"})
    if date_to < date_from:
        raise ValidationError({"date_to": "Дата окончания раньше даты начала"})
    if date_to - date_from > timedelta(days=MAX_DAYS - 1):
        raise ValidationError({"date_to": f"Замещение — не больше {MAX_DAYS} дней"})
    Employee.objects.select_for_update().get(pk=manager.pk)  # две одновременные заявки не пересекутся
    clash = Delegation.objects.filter(
        manager=manager, revoked_at__isnull=True, date_from__lte=date_to, date_to__gte=date_from
    ).first()
    if clash:
        raise ValidationError({"date_from": (
            f"На эти даты уже назначен И.О.: {clash.deputy.full_name} "
            f"({clash.date_from:%d.%m.%Y}–{clash.date_to:%d.%m.%Y})"
        )})
    delegation = Delegation.objects.create(
        manager=manager, deputy=deputy, date_from=date_from, date_to=date_to, created_by=user
    )
    _notify(delegation, created=True)
    _resync()
    return delegation


@transaction.atomic
def revoke(user, delegation: Delegation) -> Delegation:
    if delegation.manager_id != user.employee_id:
        raise PermissionDenied("Отменить замещение может только руководитель, который его назначил")
    if delegation.revoked_at is None:
        delegation.revoked_at = timezone.now()
        delegation.save(update_fields=["revoked_at"])
        _notify(delegation, created=False)
        _resync()
    return delegation


def _notify(d: Delegation, created: bool) -> None:
    from notifications.models import Notification, NotificationType

    user = getattr(d.deputy, "user", None)
    if user is None:
        return
    period = f"{d.date_from:%d.%m.%Y}–{d.date_to:%d.%m.%Y}"
    if created:
        title = f"Вы назначены И.О. руководителя: {d.manager.full_name}"
        body = f"{period}. Пока руководителя нет на месте, заявки его команды будут приходить вам на согласование."
    else:
        title = f"Замещение отменено: {d.manager.full_name}"
        body = f"Замещение на {period} больше не действует."
    Notification.objects.create(user=user, type=NotificationType.REQUEST_STATUS_CHANGED, title=title, body=body,
                                link="/team/approvals")
