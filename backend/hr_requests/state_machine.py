"""Адаптивный маршрут согласования заявок (отпуск, аванс).

Создание:
    у автора есть руководитель   → WAITING_MANAGER_APPROVAL
    руководителя нет (топ / Head of HR) → APPROVED_SENT_TO_1C
Руководитель «Одобрить» (approve-manager):
    автор — обычный сотрудник → WAITING_HR_APPROVAL
    автор — HR                → APPROVED_SENT_TO_1C (шаг HR пропускается: руководитель HR уже одобрил,
                                а HR-специалист не обрабатывает заявки коллег и свои — нет конфликта интересов)
HR «Оформить приказ» (approve-hr):
    только из WAITING_HR_APPROVAL, только чужие заявки → APPROVED_SENT_TO_1C

Отклонить может тот, чей сейчас шаг. Отменить — автор, пока заявку не начали согласовывать.
"""
from accounts.models import Role
from hr_requests.models import HrRequest, Status

SUBMIT = "submit"
APPROVE_MANAGER = "approve_manager"
APPROVE_HR = "approve_hr"
REJECT = "reject"
CANCEL = "cancel"
ALL_ACTIONS = (SUBMIT, APPROVE_MANAGER, APPROVE_HR, REJECT, CANCEL)


def requester_is_hr(req: HrRequest) -> bool:
    user = getattr(req.employee, "user", None)
    return user is not None and user.role == Role.HR_ADMIN


def initial_status(employee) -> str:
    return Status.WAITING_MANAGER_APPROVAL if employee.manager_id else Status.APPROVED_SENT_TO_1C


def status_after_manager_approval(req: HrRequest) -> str:
    return Status.APPROVED_SENT_TO_1C if requester_is_hr(req) else Status.WAITING_HR_APPROVAL


def is_author(user, req: HrRequest) -> bool:
    return user.employee_id is not None and req.employee_id == user.employee_id


def is_assigned_manager(user, req: HrRequest) -> bool:
    """Назначенный руководитель автора заявки (а не любой руководитель)."""
    return (
        user.role in (Role.MANAGER, Role.HR_ADMIN)
        and user.employee_id is not None
        and req.employee.manager_id == user.employee_id
    )


def is_hr_processor(user, req: HrRequest) -> bool:
    """HR, обрабатывающий заявку. Свою заявку HR не обрабатывает — нет конфликта интересов."""
    return user.role == Role.HR_ADMIN and not is_author(user, req)


def next_status(user, req: HrRequest, action: str) -> str | None:
    """Новый статус, если пользователь вправе выполнить действие; иначе None."""
    s = req.status
    if action == SUBMIT and s == Status.DRAFT and is_author(user, req):
        return initial_status(req.employee)
    if action == CANCEL and s in (Status.DRAFT, Status.WAITING_MANAGER_APPROVAL) and is_author(user, req):
        return Status.CANCELLED
    if action == APPROVE_MANAGER and s == Status.WAITING_MANAGER_APPROVAL and is_assigned_manager(user, req):
        return status_after_manager_approval(req)
    if action == APPROVE_HR and s == Status.WAITING_HR_APPROVAL and is_hr_processor(user, req):
        return Status.APPROVED_SENT_TO_1C
    if action == REJECT:
        if s == Status.WAITING_MANAGER_APPROVAL and is_assigned_manager(user, req):
            return Status.REJECTED
        if s == Status.WAITING_HR_APPROVAL and is_hr_processor(user, req):
            return Status.REJECTED
    return None


def allowed_actions(user, req: HrRequest) -> list[str]:
    return [a for a in ALL_ACTIONS if next_status(user, req, a)]
