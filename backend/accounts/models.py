from django.contrib.auth.models import AbstractUser
from django.db import models


class Role(models.TextChoices):
    EMPLOYEE = "employee", "Сотрудник"
    MANAGER = "manager", "Руководитель"
    HR_ADMIN = "hr_admin", "HR / администратор"


# Что пользователь видит в интерфейсе; сервер всё равно проверяет каждый запрос.
ROLE_PERMISSIONS = {
    Role.EMPLOYEE: ["requests.create", "academy.learn", "ai.ask"],
    Role.MANAGER: ["requests.create", "academy.learn", "ai.ask", "team.view", "requests.approve"],
    Role.HR_ADMIN: [
        "requests.create", "academy.learn", "ai.ask", "team.view", "requests.approve",
        "hr.all_requests", "hr.admin",
    ],
}


class User(AbstractUser):
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.EMPLOYEE)
    locale = models.CharField(max_length=2, choices=[("ru", "RU"), ("kk", "KZ")], default="ru")
    employee = models.OneToOneField(
        "org.Employee", null=True, blank=True, on_delete=models.SET_NULL, related_name="user"
    )

    class Meta:
        verbose_name = "пользователь"
        verbose_name_plural = "пользователи"

    @property
    def permissions_list(self):
        return ROLE_PERMISSIONS.get(self.role, [])
