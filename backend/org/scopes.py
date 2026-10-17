"""Серверная проверка доступа к данным сотрудников.

Каждый эндпоинт, который отдаёт данные сотрудников или их заявки,
берёт QuerySet отсюда. Чужая запись просто не попадает в выборку → 404.
"""
from django.db.models import Q

from accounts.models import Role
from org.models import Employee


def visible_employees(user):
    qs = Employee.objects.all()
    if user.role == Role.HR_ADMIN:
        return qs
    if user.employee_id is None:
        return qs.none()
    if user.role == Role.MANAGER:
        return qs.filter(Q(id=user.employee_id) | Q(manager_id=user.employee_id))
    return qs.filter(id=user.employee_id)


def team_members(user):
    """Команда без самого пользователя: для руководителя — прямые подчинённые, для HR — все."""
    qs = visible_employees(user)
    if user.employee_id is not None:
        qs = qs.exclude(id=user.employee_id)
    return qs
