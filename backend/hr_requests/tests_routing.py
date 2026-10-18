"""Руководитель в отпуске или уволен: И.О., эскалация к вышестоящему и динамическая смена согласующего.

docker compose exec backend python manage.py test hr_requests
"""
from datetime import date, timedelta

from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import Role, User
from hr_requests import routing
from hr_requests.models import HrRequest, RequestType, Status, VacationDetails
from notifications.models import Notification
from org.models import Company, Delegation, Department, Employee, LeaveBalance, Position


class RoutingTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        company = Company.objects.create(name_ru="Тест", external_id="C1")
        dep = Department.objects.create(company=company, name_ru="Логистика", external_id="D1")
        dep_other = Department.objects.create(company=company, name_ru="Продажи", external_id="D2")
        dep_hr = Department.objects.create(company=company, name_ru="HR", external_id="D3")
        pos = Position.objects.create(title_ru="Должность", external_id="P1")

        def person(code, role, manager=None, department=dep):
            emp = Employee.objects.create(
                full_name=f"Сотрудник {code}", company=company, department=department, position=pos,
                manager=manager, hire_date=date(2020, 1, 1), external_id=code,
            )
            LeaveBalance.objects.create(employee=emp, days_total=28, days_used=0, as_of=date(2026, 1, 1))
            return emp, User.objects.create_user(username=code, password="x", role=role, employee=emp)

        # CEO → руководитель логистики → два сотрудника; в продажах — свой руководитель и сотрудник
        cls.ceo_emp, cls.ceo = person("ceo", Role.MANAGER, department=dep_other)
        cls.mgr_emp, cls.mgr = person("manager", Role.MANAGER, manager=cls.ceo_emp)
        cls.emp_emp, cls.emp = person("employee", Role.EMPLOYEE, manager=cls.mgr_emp)
        cls.mate_emp, cls.mate = person("teammate", Role.EMPLOYEE, manager=cls.mgr_emp)
        cls.sales_mgr_emp, cls.sales_mgr = person("sales_manager", Role.MANAGER, manager=cls.ceo_emp,
                                                  department=dep_other)
        cls.outsider_emp, cls.outsider = person("outsider", Role.EMPLOYEE, manager=cls.sales_mgr_emp,
                                                department=dep_other)
        cls.hr_head_emp, cls.hr_head = person("hr_head", Role.HR_ADMIN, department=dep_hr)
        cls.hr_emp, cls.hr = person("hr", Role.HR_ADMIN, manager=cls.hr_head_emp, department=dep_hr)

    # --- helpers ---

    def today(self):
        return timezone.localdate()

    def advance(self, user):
        self.client.force_authenticate(user)
        with self.captureOnCommitCallbacks(execute=True):  # уведомления уходят после фиксации транзакции
            res = self.client.post("/api/v1/requests", {"type": "advance", "advance": {"amount": "50000"}}, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        return res.data

    def act(self, user, request_id, endpoint, comment=""):
        self.client.force_authenticate(user)
        return self.client.patch(f"/api/v1/requests/{request_id}/{endpoint}", {"comment": comment}, format="json")

    def detail(self, user, request_id):
        self.client.force_authenticate(user)
        return self.client.get(f"/api/v1/requests/{request_id}")

    def approvals(self, user):
        self.client.force_authenticate(user)
        return [r["id"] for r in self.client.get("/api/v1/requests?scope=approvals").data]

    def on_vacation(self, employee, start_offset=0, days=10):
        """Утверждённый отпуск сотрудника (как будто уже прошёл согласование)."""
        start = self.today() + timedelta(days=start_offset)
        req = HrRequest.objects.create(type=RequestType.VACATION, employee=employee, status=Status.APPROVED_SENT_TO_1C)
        VacationDetails.objects.create(request=req, date_from=start, date_to=start + timedelta(days=days - 1), days=days)
        return req

    def delegate(self, deputy, start_offset=0, days=10, manager=None):
        manager = manager or self.mgr_emp
        start = self.today() + timedelta(days=start_offset)
        return Delegation.objects.create(manager=manager, deputy=deputy, date_from=start,
                                         date_to=start + timedelta(days=days - 1))

    # --- маршрут ---

    def test_manager_present_approves_as_before(self):
        req = self.advance(self.emp)
        self.assertEqual(self.detail(self.emp, req["id"]).data["approver"]["kind"], "manager")
        self.assertEqual(HrRequest.objects.get(pk=req["id"]).current_approver, self.mgr_emp)
        self.assertEqual(self.act(self.ceo, req["id"], "approve-manager").status_code, 404)  # не его заявка
        self.assertEqual(self.act(self.mgr, req["id"], "approve-manager").data["status"], Status.WAITING_HR_APPROVAL)

    def test_manager_on_vacation_escalates_to_higher_manager(self):
        self.on_vacation(self.mgr_emp)
        req = self.advance(self.emp)
        data = self.detail(self.ceo, req["id"]).data  # CEO видит заявку не своего подчинённого
        self.assertEqual(data["approver"]["kind"], "escalated")
        self.assertEqual(data["approver"]["employee"]["id"], self.ceo_emp.id)
        self.assertIn("в отпуске", data["approver"]["note"])
        self.assertEqual(data["allowed_actions"], ["approve_manager", "reject"])
        self.assertIn(req["id"], self.approvals(self.ceo))
        self.assertNotIn(req["id"], self.approvals(self.mgr))
        self.assertEqual(self.act(self.mgr, req["id"], "approve-manager").status_code, 400)  # в отпуске — не решает
        self.assertTrue(Notification.objects.filter(user=self.ceo, link=f"/requests/{req['id']}").exists())
        self.assertEqual(self.act(self.ceo, req["id"], "approve-manager").data["status"], Status.WAITING_HR_APPROVAL)

    def test_deputy_approves_while_manager_away(self):
        self.on_vacation(self.mgr_emp)
        self.delegate(self.mate_emp)
        req = self.advance(self.emp)
        data = self.detail(self.mate, req["id"]).data  # сотрудник-И.О. видит заявку коллеги
        self.assertEqual((data["approver"]["kind"], data["approver"]["acting_for"]["id"]), ("deputy", self.mgr_emp.id))
        self.client.force_authenticate(self.mate)
        self.assertIn("requests.approve", self.client.get("/api/v1/me").data["permissions"])
        self.assertEqual(self.approvals(self.mate), [req["id"]])
        self.assertNotIn(req["id"], self.approvals(self.ceo))
        self.assertEqual(self.act(self.mate, req["id"], "approve-manager").data["status"], Status.WAITING_HR_APPROVAL)

    def test_deputy_has_no_power_while_manager_present(self):
        self.delegate(self.mate_emp)  # замещение назначено, но руководитель на месте
        req = self.advance(self.emp)
        self.assertEqual(self.act(self.mate, req["id"], "approve-manager").status_code, 404)  # даже не видит
        self.client.force_authenticate(self.mate)
        self.assertIn("requests.approve", self.client.get("/api/v1/me").data["permissions"])  # раздел открыт
        self.assertEqual(self.approvals(self.mate), [])

    def test_deputy_cannot_approve_own_request(self):
        self.on_vacation(self.mgr_emp)
        self.delegate(self.mate_emp)
        req = self.advance(self.mate)
        data = self.detail(self.mate, req["id"]).data
        self.assertEqual(data["approver"]["kind"], "escalated")  # своя заявка И.О. уходит к CEO
        self.assertEqual(data["allowed_actions"], ["cancel"])
        self.assertEqual(self.act(self.ceo, req["id"], "approve-manager").status_code, 200)

    def test_dismissed_manager_and_disabled_account(self):
        Employee.objects.filter(pk=self.mgr_emp.pk).update(dismissed_on=self.today())
        req = self.advance(self.emp)
        self.assertEqual(self.detail(self.ceo, req["id"]).data["approver"]["note"].count("уволен"), 1)
        Employee.objects.filter(pk=self.mgr_emp.pk).update(dismissed_on=None)
        User.objects.filter(pk=self.mgr.pk).update(is_active=False)
        self.assertEqual(routing.resolve_approver(Employee.objects.get(pk=self.emp_emp.pk)).approver, self.ceo_emp)
        Employee.objects.filter(pk=self.mgr_emp.pk).update(dismissed_on=self.today() + timedelta(days=5))
        User.objects.filter(pk=self.mgr.pk).update(is_active=True)
        self.assertEqual(routing.resolve_approver(Employee.objects.get(pk=self.emp_emp.pk)).approver, self.mgr_emp)  # уволят позже

    def test_whole_chain_absent_goes_to_hr_pool(self):
        self.on_vacation(self.mgr_emp)
        self.on_vacation(self.ceo_emp)
        req = self.advance(self.emp)
        data = self.detail(self.hr, req["id"]).data
        self.assertEqual((data["approver"]["kind"], data["approver"]["employee"]), ("hr_pool", None))
        self.assertIn(req["id"], self.approvals(self.hr))
        self.assertEqual(self.act(self.hr, req["id"], "approve-manager").data["status"], Status.WAITING_HR_APPROVAL)
        self.assertEqual(self.act(self.hr_head, req["id"], "approve-hr").data["status"], Status.APPROVED_SENT_TO_1C)

    # --- динамическая смена согласующего ---

    def test_reroute_when_manager_leaves_and_back_when_returns(self):
        req = self.advance(self.emp)
        r = HrRequest.objects.get(pk=req["id"])
        self.assertEqual((r.current_approver, r.approver_kind), (self.mgr_emp, "manager"))

        vacation = self.on_vacation(self.mgr_emp, start_offset=2, days=5)  # уходит послезавтра
        self.assertEqual(routing.sync_pending(), 0)  # пока на месте
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(routing.sync_pending(on=self.today() + timedelta(days=2)), 1)
        r.refresh_from_db()
        self.assertEqual((r.current_approver, r.approver_kind), (self.ceo_emp, "escalated"))
        event = r.events.last()
        self.assertEqual((event.from_status, event.to_status, event.actor), (r.status, r.status, None))
        self.assertIn("вышестоящий", event.comment)
        self.assertTrue(Notification.objects.filter(user=self.ceo, title__contains="передана вам").exists())
        self.assertTrue(Notification.objects.filter(user=self.emp, title__contains="сменился согласующий").exists())

        back = vacation.vacation.date_to + timedelta(days=1)
        self.assertEqual(routing.sync_pending(on=back), 1)  # вернулся — заявка снова у него
        r.refresh_from_db()
        self.assertEqual(r.current_approver, self.mgr_emp)
        self.assertEqual(routing.sync_pending(on=back), 0)  # повторный проход ничего не меняет

    def test_approving_managers_vacation_reroutes_team_requests(self):
        pending = self.advance(self.emp)
        self.client.force_authenticate(self.mgr)
        res = self.client.post("/api/v1/requests", {"type": "vacation", "vacation": {
            "date_from": self.today().isoformat(), "date_to": (self.today() + timedelta(days=4)).isoformat(),
        }}, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(self.act(self.ceo, res.data["id"], "approve-manager").status_code, 200)
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.act(self.hr, res.data["id"], "approve-hr").data["status"], Status.APPROVED_SENT_TO_1C)
        self.assertEqual(HrRequest.objects.get(pk=pending["id"]).current_approver, self.ceo_emp)

    def test_dismissal_with_pending_request_moves_it_to_deputy(self):
        req = self.advance(self.emp)
        self.delegate(self.mate_emp)
        Employee.objects.filter(pk=self.mgr_emp.pk).update(dismissed_on=self.today())
        self.assertEqual(routing.sync_pending(), 1)
        r = HrRequest.objects.get(pk=req["id"])
        self.assertEqual((r.current_approver, r.approver_kind), (self.mate_emp, "deputy"))
        self.assertEqual(self.act(self.mgr, req["id"], "approve-manager").status_code, 400)
        self.assertEqual(self.act(self.mate, req["id"], "approve-manager").status_code, 200)

    # --- API замещения ---

    def test_delegation_api_rules(self):
        url = "/api/v1/me/delegations"
        start, end = self.today() + timedelta(days=1), self.today() + timedelta(days=7)
        body = lambda deputy, a=start, b=end: {"deputy_id": deputy.id, "date_from": a.isoformat(),  # noqa: E731
                                               "date_to": b.isoformat()}
        self.client.force_authenticate(self.emp)  # без подчинённых
        self.assertFalse(self.client.get(url).data["can_delegate"])
        self.assertEqual(self.client.post(url, body(self.mate_emp), format="json").status_code, 403)

        self.client.force_authenticate(self.mgr)
        data = self.client.get(url).data
        self.assertTrue(data["can_delegate"])
        self.assertEqual({c["id"] for c in data["candidates"]}, {self.emp_emp.id, self.mate_emp.id})
        self.assertEqual(self.client.post(url, body(self.outsider_emp), format="json").status_code, 400)
        past = self.today() - timedelta(days=1)
        self.assertEqual(self.client.post(url, body(self.mate_emp, a=past), format="json").status_code, 400)
        self.assertEqual(self.client.post(url, body(self.mate_emp, a=end, b=start), format="json").status_code, 400)
        res = self.client.post(url, body(self.mate_emp), format="json")
        self.assertEqual((res.status_code, res.data["state"]), (201, "planned"))
        self.assertEqual(self.client.post(url, body(self.emp_emp, a=end, b=end), format="json").status_code, 400)
        self.assertTrue(Notification.objects.filter(user=self.mate, title__contains="И.О.").exists())

        self.client.force_authenticate(self.mate)
        self.assertEqual(self.client.get(url).data["acting_for"][0]["manager"]["id"], self.mgr_emp.id)
        self.assertEqual(self.client.post(f"{url}/{res.data['id']}/revoke").status_code, 404)  # отменяет только автор

        self.client.force_authenticate(self.mgr)
        revoked = self.client.post(f"{url}/{res.data['id']}/revoke").data
        self.assertEqual(revoked["state"], "revoked")
        self.assertEqual(self.client.post(url, body(self.emp_emp, a=end, b=end), format="json").status_code, 201)

    def test_revoking_active_delegation_reroutes_to_escalation(self):
        self.on_vacation(self.mgr_emp)
        d = self.delegate(self.mate_emp)
        req = self.advance(self.emp)
        self.assertEqual(HrRequest.objects.get(pk=req["id"]).current_approver, self.mate_emp)
        self.client.force_authenticate(self.mgr)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(f"/api/v1/me/delegations/{d.id}/revoke")
        self.assertEqual(HrRequest.objects.get(pk=req["id"]).current_approver, self.ceo_emp)
