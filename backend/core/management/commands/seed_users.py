"""Демо-пользователи и оргструктура (без заявок).

python manage.py seed_users

Каждый запуск очищает пользователей (и заявки/уведомления, которые на них ссылаются)
и создаёт их заново. Полные демо-данные с заявками: python manage.py seed --reset
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from core.demo_users import DEMO_LOGINS, DEMO_PASSWORD, create_demo_users, ensure_migrated, wipe_demo_data


class Command(BaseCommand):
    help = "Пересоздать демо-пользователей JanaМен (CEO, руководитель, сотрудник, Head of HR, 2 HR-специалиста)"

    @transaction.atomic
    def handle(self, *args, **options):
        ensure_migrated()
        wipe_demo_data()
        people = create_demo_users()

        self.stdout.write(f"{'логин':<20}{'роль':<12}{'руководитель':<20}подразделение")
        for login in DEMO_LOGINS:
            p = people[login]
            manager = p.employee.manager.user.username if p.employee.manager else "—"
            self.stdout.write(
                f"{login:<20}{p.user.role:<12}{manager:<20}{p.employee.department.name_ru}"
            )
        self.stdout.write(self.style.SUCCESS(f"Готово, пароль у всех: {DEMO_PASSWORD}"))
