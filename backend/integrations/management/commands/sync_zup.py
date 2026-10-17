"""Синхронизация кадровых данных из 1С:ЗУП.

python manage.py sync_zup                  — вручную
python manage.py sync_zup --trigger startup — при старте контейнера (ошибка не останавливает запуск)
"""
from django.core.management.base import BaseCommand, CommandError

from integrations.models import SyncRun
from integrations.zup_sync import sync_from_zup


class Command(BaseCommand):
    help = "Загрузить сотрудников, оргструктуру и остатки отпуска из 1С:ЗУП"

    def add_arguments(self, parser):
        parser.add_argument("--trigger", default="manual")

    def handle(self, *args, trigger="manual", **options):
        run = sync_from_zup(trigger=trigger)
        if run.status == SyncRun.RunStatus.OK:
            self.stdout.write(self.style.SUCCESS(f"1С:ЗУП: синхронизация выполнена {run.stats}"))
        elif trigger == "startup":
            self.stdout.write(self.style.WARNING(f"1С:ЗУП: синхронизация не выполнена — {run.error}"))
        else:
            raise CommandError(run.error)
