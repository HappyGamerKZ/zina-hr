"""Подписчики на доменные события → записи в центре уведомлений."""
from accounts.models import Role, User
from core import events
from hr_requests.models import Status
from notifications.models import Notification, NotificationType


def notify(user, type_, title, body="", link=""):
    if user is None:
        return None
    return Notification.objects.create(user=user, type=type_, title=title, body=body, link=link)


def _user_of(employee):
    return getattr(employee, "user", None) if employee else None


def _hr_users():
    return User.objects.filter(role=Role.HR_ADMIN, is_active=True)


def on_request_submitted(request, **_):
    """Заявка ждёт руководителя → уведомление назначенному руководителю."""
    author = request.employee
    notify(
        _user_of(author.manager),
        NotificationType.REQUEST_SUBMITTED,
        f"Новая заявка {request.number}: {request.get_type_display().lower()}",
        f"{author.full_name} отправил(а) заявку на согласование",
        f"/requests/{request.pk}",
    )


def on_request_status_changed(request, old_status, actor, **_):
    link = f"/requests/{request.pk}"
    author_user = _user_of(request.employee)

    # Автору — о любом изменении, которое сделал не он сам (и всегда — об итоговом утверждении).
    if author_user and (author_user != actor or request.status == Status.APPROVED_SENT_TO_1C):
        body = f"Новый статус: «{request.get_status_display()}»"
        if old_status:
            body = f"«{Status(old_status).label}» → «{request.get_status_display()}»"
        notify(
            author_user,
            NotificationType.REQUEST_STATUS_CHANGED,
            f"Заявка {request.number}: {request.get_status_display().lower()}",
            body,
            link,
        )

    # Руководитель одобрил заявку сотрудника → она ждёт HR.
    if request.status == Status.WAITING_HR_APPROVAL:
        for hr in _hr_users().exclude(pk=getattr(actor, "pk", None)).exclude(employee=request.employee):
            notify(
                hr,
                NotificationType.REQUEST_SUBMITTED,
                f"Заявка {request.number} ждёт оформления приказа",
                f"{request.employee.full_name}: {request.get_type_display().lower()}, одобрено руководителем",
                link,
            )


def register():
    events.subscribe(events.REQUEST_SUBMITTED, on_request_submitted)
    events.subscribe(events.REQUEST_STATUS_CHANGED, on_request_status_changed)
