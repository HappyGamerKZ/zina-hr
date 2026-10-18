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


def _lower_first(text: str) -> str:
    """«Утверждено / Передано в 1С» → «утверждено / Передано в 1С»: аббревиатуры не портятся."""
    return text[:1].lower() + text[1:]


def _hr_users():
    return User.objects.filter(role=Role.HR_ADMIN, is_active=True)


def _approvers(request):
    """Кому сейчас решать на шаге руководителя: согласующий из маршрута или весь пул HR (routing.py)."""
    if request.current_approver_id:
        return [u for u in [_user_of(request.current_approver)] if u]
    return list(_hr_users().exclude(employee=request.employee))


def on_request_submitted(request, **_):
    """Заявка ждёт руководителя → уведомление тому, кто сейчас согласует (руководитель, И.О., вышестоящий)."""
    author = request.employee
    acting = " (вы исполняете обязанности руководителя)" if request.approver_kind == "deputy" else ""
    for user in _approvers(request):
        notify(
            user,
            NotificationType.REQUEST_SUBMITTED,
            f"Новая заявка {request.number}: {request.get_type_display().lower()}",
            f"{author.full_name} отправил(а) заявку на согласование{acting}",
            f"/requests/{request.pk}",
        )


def on_request_rerouted(request, text, **_):
    """Согласующий сменился (отпуск, увольнение, замещение) → новому согласующему и автору."""
    link = f"/requests/{request.pk}"
    for user in _approvers(request):
        notify(user, NotificationType.REQUEST_SUBMITTED, f"Заявка {request.number} передана вам на согласование",
               f"{request.employee.full_name}: {request.get_type_display().lower()}. {text}", link)
    notify(_user_of(request.employee), NotificationType.REQUEST_STATUS_CHANGED,
           f"Заявка {request.number}: сменился согласующий", text, link)


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
            f"Заявка {request.number}: {_lower_first(request.get_status_display())}",
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


def on_course_assigned(assignment, actor, repeat=False, **_):
    who = actor.employee.full_name if getattr(actor, "employee", None) else actor.username
    due = f" Срок: {assignment.due_date:%d.%m.%Y}." if assignment.due_date else ""
    title = "Курс назначен повторно" if repeat else "Назначен курс"
    notify(
        _user_of(assignment.employee),
        NotificationType.COURSE_ASSIGNED,
        f"{title} «{assignment.course.title_ru}»",
        f"Назначил(а): {who}.{due}",
        f"/academy/assignments/{assignment.pk}",
    )


def on_course_completed(assignment, **_):
    score = f", результат {assignment.score}%" if assignment.score is not None else ""
    link = f"/academy/assignments/{assignment.pk}"
    notify(
        _user_of(assignment.employee),
        NotificationType.COURSE_COMPLETED,
        f"Курс «{assignment.course.title_ru}» завершён",
        f"Поздравляем! Курс пройден{score}.",
        link,
    )
    notify(
        _user_of(assignment.employee.manager),
        NotificationType.COURSE_COMPLETED,
        f"{assignment.employee.full_name} завершил(а) курс «{assignment.course.title_ru}»",
        f"Курс пройден{score}.",
        link,
    )


def on_course_failed(assignment, **_):
    """Попытки закончились → руководителю (или HR, если руководителя нет), чтобы назначить курс повторно."""
    link = f"/academy/assignments/{assignment.pk}"
    title = f"{assignment.employee.full_name} не сдал(а) курс «{assignment.course.title_ru}»"
    body = "Попытки теста закончились. Курс можно назначить повторно."
    manager_user = _user_of(assignment.employee.manager)
    recipients = [manager_user] if manager_user else list(_hr_users())
    for user in recipients:
        notify(user, NotificationType.COURSE_FAILED, title, body, link)


def on_document_status_changed(request, **_):
    """Documentolog: приказ подписан → автору; отклонён → автору и HR."""
    link = f"/requests/{request.pk}"
    if request.doc_status == "signed":
        notify(
            _user_of(request.employee),
            NotificationType.REQUEST_STATUS_CHANGED,
            f"Заявка {request.number}: приказ подписан",
            f"Приказ зарегистрирован в Documentolog, № {request.doc_registration_number}",
            link,
        )
    elif request.doc_status == "rejected":
        title = f"Заявка {request.number}: приказ отклонён в Documentolog"
        notify(_user_of(request.employee), NotificationType.REQUEST_STATUS_CHANGED, title, "HR свяжется с вами", link)
        for hr in _hr_users().exclude(employee=request.employee):
            notify(hr, NotificationType.REQUEST_STATUS_CHANGED, title, "Проверьте приказ в Documentolog", link)


def register():
    events.subscribe(events.DOCUMENT_STATUS_CHANGED, on_document_status_changed)
    events.subscribe(events.REQUEST_SUBMITTED, on_request_submitted)
    events.subscribe(events.REQUEST_REROUTED, on_request_rerouted)
    events.subscribe(events.REQUEST_STATUS_CHANGED, on_request_status_changed)
    events.subscribe(events.COURSE_ASSIGNED, on_course_assigned)
    events.subscribe(events.COURSE_COMPLETED, on_course_completed)
    events.subscribe(events.COURSE_FAILED, on_course_failed)
