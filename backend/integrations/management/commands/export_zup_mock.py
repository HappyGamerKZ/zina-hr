"""Выгрузить текущие демо-данные в формате HTTP-сервиса 1С:ЗУП → mocks/zup/data.json.

Нужно, чтобы заглушка 1С:ЗУП отдавала тех же сотрудников, что и seed (совпадают табельные номера).
python manage.py export_zup_mock --out /mocks/zup/data.json
"""
import json

from django.core.management.base import BaseCommand
from django.utils import timezone

from org.models import Company, Department, Employee, LeaveBalance, Position


class Command(BaseCommand):
    help = "Сформировать data.json для заглушки 1С:ЗУП из текущих демо-данных"

    def add_arguments(self, parser):
        parser.add_argument("--out", required=True)

    def handle(self, *args, out, **options):
        company = Company.objects.first()
        data = {
            "company": {"code": company.external_id, "name_ru": company.name_ru, "name_kk": company.name_kk},
            "departments": [
                {"code": d.external_id, "name_ru": d.name_ru, "name_kk": d.name_kk,
                 "parent_code": d.parent.external_id if d.parent else None}
                for d in Department.objects.select_related("parent").order_by("external_id")
            ],
            "positions": [
                {"code": p.external_id, "title_ru": p.title_ru, "title_kk": p.title_kk}
                for p in Position.objects.order_by("external_id")
            ],
            "employees": [
                {"tab_number": e.external_id, "full_name": e.full_name, "department_code": e.department.external_id,
                 "position_code": e.position.external_id, "hire_date": e.hire_date.isoformat(),
                 "manager_tab_number": e.manager.external_id if e.manager else None, "email": e.email,
                 "dismissed_on": e.dismissed_on.isoformat() if e.dismissed_on else None}
                for e in Employee.objects.select_related("department", "position", "manager").order_by("external_id")
            ],
            "leave_balances": [
                {"tab_number": b.employee.external_id, "leave_type": b.leave_type, "days_total": b.days_total,
                 "days_used": b.days_used, "as_of": timezone.localdate().isoformat()}
                for b in LeaveBalance.objects.select_related("employee").order_by("employee__external_id")
            ],
        }
        with open(out, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        self.stdout.write(self.style.SUCCESS(f"Записано: {out} ({len(data['employees'])} сотрудников)"))
