"""Вход: по логину и по рабочей почте.

docker compose exec backend python manage.py test accounts
"""
from datetime import date

from rest_framework.test import APITestCase

from accounts.models import Role, User
from org.models import Company, Department, Employee, Position

LOGIN = "/api/v1/auth/login"


class LoginTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        company = Company.objects.create(name_ru="Тест", external_id="C1")
        dep = Department.objects.create(company=company, name_ru="Отдел", external_id="D1")
        pos = Position.objects.create(title_ru="Должность", external_id="P1")
        emp = Employee.objects.create(full_name="Сотрудник", company=company, department=dep, position=pos,
                                      hire_date=date(2020, 1, 1), external_id="E1", email="worker@demo.test")
        User.objects.create_user(username="worker", password="pass12345", role=Role.EMPLOYEE, employee=emp)

    def login(self, username, password="pass12345"):
        return self.client.post(LOGIN, {"username": username, "password": password}, format="json")

    def test_login_by_username_or_work_email(self):
        self.assertEqual(self.login("worker").status_code, 200)
        self.assertEqual(self.login("Worker@Demo.test").status_code, 200)
        self.assertEqual(self.login("worker@demo.test", "wrong").status_code, 400)
        self.assertEqual(self.login("nobody@demo.test").status_code, 400)
