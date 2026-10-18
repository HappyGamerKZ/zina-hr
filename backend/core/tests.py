from io import StringIO

from django.core.management import call_command
from rest_framework.test import APITestCase

from accounts.models import Role, User
from hr_requests.models import HrRequest, Status


class SeedTests(APITestCase):
    def test_seed_users_hierarchy_and_rerun(self):
        call_command("seed_users", stdout=StringIO())
        call_command("seed_users", stdout=StringIO())  # повторный запуск не падает

        expected = {
            "ceo": (Role.MANAGER, None),
            "manager_logistics": (Role.MANAGER, "ceo"),
            "employee": (Role.EMPLOYEE, "manager_logistics"),
            "manager_service": (Role.MANAGER, "ceo"),
            "employee_service": (Role.EMPLOYEE, "manager_service"),
            "head_hr": (Role.HR_ADMIN, "ceo"),
            "hr_spec_1": (Role.HR_ADMIN, "head_hr"),
            "hr_spec_2": (Role.HR_ADMIN, "head_hr"),
        }
        self.assertEqual(User.objects.count(), len(expected))
        for login, (role, manager) in expected.items():
            user = User.objects.get(username=login)
            self.assertEqual(user.role, role, login)
            actual_manager = user.employee.manager.user.username if user.employee.manager else None
            self.assertEqual(actual_manager, manager, login)
        self.assertTrue(User.objects.get(username="ceo").is_superuser)

    def test_seed_demo_routes(self):
        call_command("seed", reset=True, stdout=StringIO())

        def approvals(login):
            self.client.force_authenticate(User.objects.get(username=login))
            return {r["id"] for r in self.client.get("/api/v1/requests?scope=approvals").data}

        pool = set(HrRequest.objects.filter(status=Status.WAITING_HR_APPROVAL).values_list("id", flat=True))
        self.assertEqual(len(pool), 2)
        # общий пул одинаково виден обоим HR-специалистам
        self.assertEqual(approvals("hr_spec_1"), pool)
        self.assertEqual(approvals("hr_spec_2"), pool)

        # отпуск руководителя логистики ждёт CEO → после одобрения попадает в пул HR
        mgr_req = HrRequest.objects.get(employee__user__username="manager_logistics", status=Status.WAITING_MANAGER_APPROVAL)
        self.assertIn(mgr_req.id, approvals("ceo"))
        res = self.client.patch(f"/api/v1/requests/{mgr_req.id}/approve-manager", {}, format="json")
        self.assertEqual(res.data["status"], Status.WAITING_HR_APPROVAL)

        # аванс HR-специалиста: head_hr одобряет → сразу в 1С
        hr_req = HrRequest.objects.get(employee__user__username="hr_spec_1", status=Status.WAITING_MANAGER_APPROVAL)
        self.client.force_authenticate(User.objects.get(username="head_hr"))
        res = self.client.patch(f"/api/v1/requests/{hr_req.id}/approve-manager", {}, format="json")
        self.assertEqual(res.data["status"], Status.APPROVED_SENT_TO_1C)

    def test_seed_two_departments_are_isolated(self):
        """Демо-сценарий 3: руководитель видит только свою команду и её заявки, чужой отдел — 404."""
        call_command("seed", reset=True, stdout=StringIO())
        service_req = HrRequest.objects.get(employee__user__username="employee_service",
                                            status=Status.WAITING_MANAGER_APPROVAL)
        logistics_req = HrRequest.objects.filter(employee__user__username="employee").first()

        def as_user(login):
            self.client.force_authenticate(User.objects.get(username=login))

        as_user("manager_logistics")
        team = {m["full_name"] for m in self.client.get("/api/v1/team").data}
        self.assertIn("Сапарова Айгерим Нурлановна", team)
        self.assertNotIn("Исмаилов Данияр Ерланович", team)
        self.assertEqual(self.client.get(f"/api/v1/requests/{service_req.id}").status_code, 404)
        service_emp = User.objects.get(username="employee_service").employee_id
        self.assertEqual(self.client.get(f"/api/v1/team/{service_emp}").status_code, 404)
        self.assertNotIn(service_req.id, [r["id"] for r in self.client.get("/api/v1/requests?scope=team").data])

        as_user("manager_service")
        self.assertIn(service_req.id, [r["id"] for r in self.client.get("/api/v1/requests?scope=approvals").data])
        self.assertEqual(self.client.get(f"/api/v1/requests/{logistics_req.id}").status_code, 404)
        self.assertEqual(len(self.client.get("/api/v1/team").data), 3)

        as_user("employee_service")
        self.assertEqual(self.client.get(f"/api/v1/requests/{logistics_req.id}").status_code, 404)
        self.assertEqual(self.client.get("/api/v1/team").status_code, 403)

    def test_team_shows_vacation_and_deputy(self):
        call_command("seed", reset=True, stdout=StringIO())

        def team(login):
            self.client.force_authenticate(User.objects.get(username=login))
            return {m["full_name"]: m for m in self.client.get("/api/v1/team").data}

        logistics = team("manager_logistics")
        self.assertEqual(logistics["Ким Алина Викторовна"]["absence"]["state"], "vacation")  # сейчас в отпуске
        self.assertIsNone(logistics["Сапарова Айгерим Нурлановна"]["absence"])  # на месте
        board = team("ceo")
        service = board["Жумабаева Гульнара Ахметовна"]
        self.assertEqual(service["absence"]["state"], "planned")  # отпуск через 12 дней
        self.assertEqual(service["deputy"]["full_name"], "Исмаилов Данияр Ерланович")
        self.assertIsNone(board["Бекенов Ерлан Серикович"]["deputy"])
