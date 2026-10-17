"""Маршрут согласования заявок и серверная проверка прав.

docker compose exec backend python manage.py test hr_requests
"""
from datetime import date, timedelta

from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import Role, User
from hr_requests.models import HrRequest, Status
from integrations.models import AccountingExport
from notifications.models import Notification
from org.models import Company, Department, Employee, LeaveBalance, Position


class ApprovalFlowTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        company = Company.objects.create(name_ru="Тест", external_id="C1")
        dep = Department.objects.create(company=company, name_ru="Отдел", external_id="D1")
        dep_hr = Department.objects.create(company=company, name_ru="HR", external_id="D2")
        pos = Position.objects.create(title_ru="Должность", external_id="P1")

        def person(code, role, manager=None, department=dep):
            emp = Employee.objects.create(
                full_name=f"Сотрудник {code}", company=company, department=department, position=pos,
                manager=manager, hire_date=date(2020, 1, 1), external_id=code,
            )
            LeaveBalance.objects.create(employee=emp, days_total=24, days_used=0, as_of=date(2026, 1, 1))
            user = User.objects.create_user(username=code, password="x", role=role, employee=emp)
            return emp, user

        # 3. Head of HR — manager_id = null
        cls.hr_head_emp, cls.hr_head = person("hr_head", Role.HR_ADMIN, department=dep_hr)
        # 2. HR-специалист — руководитель Head of HR
        cls.hr_emp, cls.hr = person("hr", Role.HR_ADMIN, manager=cls.hr_head_emp, department=dep_hr)
        cls.hr2_emp, cls.hr2 = person("hr2", Role.HR_ADMIN, manager=cls.hr_head_emp, department=dep_hr)
        # руководитель отдела и 1. обычный сотрудник
        cls.mgr_emp, cls.mgr = person("manager", Role.MANAGER)
        cls.emp_emp, cls.emp = person("employee", Role.EMPLOYEE, manager=cls.mgr_emp)
        # чужой руководитель — не должен видеть заявки отдела manager
        cls.other_mgr_emp, cls.other_mgr = person("other_manager", Role.MANAGER)

    # --- helpers ---

    def create_advance(self, user, amount="100000"):
        self.client.force_authenticate(user)
        res = self.client.post(
            "/api/v1/requests", {"type": "advance", "advance": {"amount": amount}}, format="json"
        )
        self.assertEqual(res.status_code, 201, res.data)
        return res.data

    def create_vacation(self, user, days=5):
        self.client.force_authenticate(user)
        start = timezone.localdate() + timedelta(days=30)
        res = self.client.post(
            "/api/v1/requests",
            {"type": "vacation", "vacation": {
                "date_from": start.isoformat(),
                "date_to": (start + timedelta(days=days - 1)).isoformat(),
            }},
            format="json",
        )
        self.assertEqual(res.status_code, 201, res.data)
        return res.data

    def act(self, user, request_id, endpoint, comment=""):
        self.client.force_authenticate(user)
        return self.client.patch(
            f"/api/v1/requests/{request_id}/{endpoint}", {"comment": comment}, format="json"
        )

    # --- три сценария маршрута ---

    def test_employee_goes_manager_then_hr_then_1c(self):
        req = self.create_vacation(self.emp, days=5)
        self.assertEqual(req["status"], Status.WAITING_MANAGER_APPROVAL)

        res = self.act(self.mgr, req["id"], "approve-manager")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["status"], Status.WAITING_HR_APPROVAL)

        res = self.act(self.hr, req["id"], "approve-hr")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["status"], Status.APPROVED_SENT_TO_1C)
        self.assertTrue(res.data["external_accounting_id"].startswith("BUH-"))
        self.assertEqual(AccountingExport.objects.filter(request_id=req["id"]).count(), 1)
        # дни отпуска списаны (mock проводки в 1С:ЗУП)
        self.assertEqual(LeaveBalance.objects.get(employee=self.emp_emp).days_used, 5)

    def test_hr_specialist_skips_hr_step_after_head_of_hr(self):
        req = self.create_advance(self.hr)
        self.assertEqual(req["status"], Status.WAITING_MANAGER_APPROVAL)

        # HR-специалист не может «оформить приказ» сам себе
        self.assertEqual(self.act(self.hr, req["id"], "approve-hr").status_code, 400)

        res = self.act(self.hr_head, req["id"], "approve-manager")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["status"], Status.APPROVED_SENT_TO_1C)

    def test_head_of_hr_without_manager_is_approved_immediately(self):
        req = self.create_advance(self.hr_head)
        self.assertEqual(req["status"], Status.APPROVED_SENT_TO_1C)
        self.assertTrue(req["external_accounting_id"].startswith("BUH-"))

    def test_shared_hr_queue(self):
        """«Единое окно»: заявку видят все HR, оформляет один, второй получает отказ."""
        req = self.create_advance(self.emp)
        self.act(self.mgr, req["id"], "approve-manager")

        for hr in (self.hr, self.hr2, self.hr_head):
            self.client.force_authenticate(hr)
            ids = [r["id"] for r in self.client.get("/api/v1/requests?scope=approvals").data]
            self.assertIn(req["id"], ids, hr.username)

        self.assertEqual(self.act(self.hr2, req["id"], "approve-hr").status_code, 200)
        self.assertEqual(self.act(self.hr, req["id"], "approve-hr").status_code, 400)
        self.client.force_authenticate(self.hr)
        ids = [r["id"] for r in self.client.get("/api/v1/requests?scope=approvals").data]
        self.assertNotIn(req["id"], ids)

    # --- права и конфликт интересов ---

    def test_only_assigned_manager_can_approve(self):
        req = self.create_advance(self.emp)
        # HR не может перескочить шаг руководителя
        self.assertEqual(self.act(self.hr, req["id"], "approve-manager").status_code, 400)
        self.assertEqual(self.act(self.hr, req["id"], "approve-hr").status_code, 400)
        # автор не согласует сам себе
        self.assertEqual(self.act(self.emp, req["id"], "approve-manager").status_code, 400)
        # чужой руководитель заявку вообще не видит
        self.assertEqual(self.act(self.other_mgr, req["id"], "approve-manager").status_code, 404)
        self.client.force_authenticate(self.other_mgr)
        self.assertEqual(self.client.get(f"/api/v1/requests/{req['id']}").status_code, 404)

    def test_allowed_actions_shown_only_to_current_approver(self):
        req = self.create_advance(self.emp)
        self.client.force_authenticate(self.mgr)
        self.assertEqual(
            self.client.get(f"/api/v1/requests/{req['id']}").data["allowed_actions"],
            ["approve_manager", "reject"],
        )
        self.client.force_authenticate(self.hr)
        self.assertEqual(self.client.get(f"/api/v1/requests/{req['id']}").data["allowed_actions"], [])
        self.client.force_authenticate(self.emp)
        self.assertEqual(self.client.get(f"/api/v1/requests/{req['id']}").data["allowed_actions"], ["cancel"])

    def test_reject_requires_comment(self):
        req = self.create_advance(self.emp)
        self.assertEqual(self.act(self.mgr, req["id"], "reject").status_code, 400)
        res = self.act(self.mgr, req["id"], "reject", comment="Нет бюджета")
        self.assertEqual(res.data["status"], Status.REJECTED)

    def test_round_advance_amount_accepted(self):
        req = self.create_advance(self.emp, amount="100000")
        self.assertEqual(HrRequest.objects.get(pk=req["id"]).advance.amount, 100000)

    def test_notifications_follow_the_route(self):
        with self.captureOnCommitCallbacks(execute=True):
            req = self.create_advance(self.emp)
        self.assertTrue(Notification.objects.filter(user=self.mgr, link=f"/requests/{req['id']}").exists())

        with self.captureOnCommitCallbacks(execute=True):
            self.act(self.mgr, req["id"], "approve-manager")
        self.assertTrue(Notification.objects.filter(user=self.hr, link=f"/requests/{req['id']}").exists())
        self.assertTrue(Notification.objects.filter(user=self.emp, link=f"/requests/{req['id']}").exists())
