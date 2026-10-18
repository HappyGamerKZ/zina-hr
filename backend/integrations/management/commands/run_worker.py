"""Фоновый обработчик outbox: повторяет отправки во внешние системы.

python manage.py run_worker            — работать постоянно (контейнер worker в docker compose)
python manage.py run_worker --once     — один проход (для проверки)
"""
import time

from django.core.management.base import BaseCommand
from django.db import DatabaseError, close_old_connections

from integrations.outbox import process_due
from hr_requests.routing import sync_pending

ROUTING_EVERY = 60  # с: начался отпуск руководителя, наступила дата увольнения, закончилось замещение


class Command(BaseCommand):
    help = "Отправлять задачи outbox в 1С и Documentolog с повторами"

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true")
        parser.add_argument("--interval", type=float, default=3.0)

    def handle(self, *args, once=False, interval=3.0, **options):
        self.stdout.write("Outbox worker запущен")
        last_routing = 0.0
        while True:
            close_old_connections()
            try:
                for task in process_due():
                    self.stdout.write(
                        f"{task.request.number} → {task.get_target_display()}: {task.get_status_display()}"
                        + (f" (попытка {task.attempts}: {task.last_error})" if task.last_error else "")
                    )
                if once or time.monotonic() - last_routing >= ROUTING_EVERY:
                    last_routing = time.monotonic()
                    if changed := sync_pending():
                        self.stdout.write(f"Маршрут согласования изменён у заявок: {changed}")
            except DatabaseError as exc:  # база ещё не готова (миграции идут) — подождать
                self.stdout.write(self.style.WARNING(f"База недоступна: {exc}"))
                time.sleep(5)
            if once:
                return
            time.sleep(interval)
