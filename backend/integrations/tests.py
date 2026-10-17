"""Интеграции: синхронизация с 1С:ЗУП, outbox с повторами, обратный вызов Documentolog.

docker compose exec backend python manage.py test integrations
Внешние системы подменяются адаптерами inmemory (HRIS_PROVIDER / DOCFLOW_PROVIDER по умолчанию).
"""
import hashlib
import hmac
import json
from datetime import date, timedelta
from unittest import mock

from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import Role, User
from hr_requests.models import HrRequest, Status
from integrations import outbox
from integrations.adapters import InMemoryDocflowAdapter, InMemoryZupAdapter
from integrations.models import OutboxTask, SyncRun
from integrations.ports import IntegrationError, ZupDepartment, ZupEmployee, ZupLeaveBalance, ZupPosition, ZupSnapshot
from integrations.zup_sync import sync_from_zup
from notifications.models import Notification
from org.models import Company, Department, Employee, LeaveBalance, Position

WEBHOOK = "/api/v1/integrations/documentolog/webhook"


def snapshot(position_of_employee="POS-1", days_used=3) -> ZupSnapshot:
    return ZupSnapshot(
        company_code="ORG", company_name_ru="Тест",
        departments=[ZupDepartment("DEP-1", "Логистика"), ZupDepartment("DEP-2", "HR")],
        positions=[ZupPosition("POS-1", "Логист"), ZupPosition("POS-2", "Руководитель"), ZupPosition("POS-3", "Старший логист")],
        employees=[
            ZupEmployee("T-1", "Руководитель Р.", "DEP-1", "POS-2", date(2018, 1, 1)),
            ZupEmployee("T-2", "Сотрудник С.", "DEP-1", position_of_employee, date(2022, 1, 1), manager_tab_number="T-1"),
            ZupEmployee("T-3", "Кадровик К.", "DEP-2", "POS-1", date(2020, 1, 1)),
        ],
        balances=[ZupLeaveBalance("T-2", 24, days_used, date(2026, 10, 1))],
    )


class ZupSyncTests(APITestCase):
    def tearDown(self):
        InMemoryZupAdapter.snapshot = None

    def test_sync_creates_and_updates_from_zup(self):
        InMemoryZupAdapter.snapshot = snapshot()
        run = sync_from_zup()
        self.assertEqual(run.status, SyncRun.RunStatus.OK, run.error)
        emp = Employee.objects.get(external_id="T-2")
        self.assertEqual((emp.position.title_ru, emp.manager.external_id, emp.source), ("Логист", "T-1", "zup"))
        self.assertEqual(LeaveBalance.objects.get(employee=emp).days_used, 3)

        # «кадровик изменил данные в 1С» → после синхронизации профиль обновился
        InMemoryZupAdapter.snapshot = snapshot(position_of_employee="POS-3", days_used=10)
        run = sync_from_zup()
        emp.refresh_from_db()
        self.assertEqual(emp.position.title_ru, "Старший логист")
        self.assertEqual(LeaveBalance.objects.get(employee=emp).days_used, 10)
        self.assertEqual(run.stats["employees"], {"unchanged": 2, "updated": 1})

    def test_sync_failure_is_logged_not_raised(self):
        run = sync_from_zup()  # снимок не задан = 1С недоступна
        self.assertEqual(run.status, SyncRun.RunStatus.FAILED)
        self.assertIn("1С:ЗУП", run.error)


class OutboxAndWebhookTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        company = Company.objects.create(name_ru="Тест", external_id="C1")
        dep = Department.objects.create(company=company, name_ru="Отдел", external_id="D1")
        pos = Position.objects.create(title_ru="Должность", external_id="P1")

        def person(code, role, manager=None):
            emp = Employee.objects.create(
                full_name=f"Сотрудник {code}", company=company, department=dep, position=pos,
                manager=manager, hire_date=date(2020, 1, 1), external_id=code,
            )
            LeaveBalance.objects.create(employee=emp, days_total=24, days_used=0, as_of=date(2026, 1, 1))
            return User.objects.create_user(username=code, password="x", role=role, employee=emp)

        cls.hr = person("hr", Role.HR_ADMIN)
        cls.mgr = person("manager", Role.MANAGER)
        cls.emp = person("employee", Role.EMPLOYEE, manager=cls.mgr.employee)

    def setUp(self):
        InMemoryZupAdapter.pushed.clear()
        InMemoryDocflowAdapter.created.clear()

    def approved_vacation(self) -> HrRequest:
        """Заявка проходит руководителя и HR; отправки в 1С и Documentolog выполняются после коммита."""
        self.client.force_authenticate(self.emp)
        start = timezone.localdate() + timedelta(days=30)
        req_id = self.client.post("/api/v1/requests", {"type": "vacation", "vacation": {
            "date_from": start.isoformat(), "date_to": (start + timedelta(days=4)).isoformat(),
        }}, format="json").data["id"]
        self.client.force_authenticate(self.mgr)
        self.client.patch(f"/api/v1/requests/{req_id}/approve-manager", {}, format="json")
        self.client.force_authenticate(self.hr)
        with self.captureOnCommitCallbacks(execute=True):
            res = self.client.patch(f"/api/v1/requests/{req_id}/approve-hr", {}, format="json")
        self.assertEqual(res.data["status"], Status.APPROVED_SENT_TO_1C)
        return HrRequest.objects.get(pk=req_id)

    # --- outbox ---

    def test_approval_delivers_to_all_systems(self):
        req = self.approved_vacation()
        tasks = {t.target: t for t in req.outbox_tasks.all()}
        self.assertEqual(set(tasks), {"accounting", "zup", "documentolog"})
        self.assertTrue(all(t.status == OutboxTask.TaskStatus.SENT for t in tasks.values()))
        self.assertTrue(req.external_accounting_id.startswith("BUH-"))
        self.assertTrue(req.external_zup_id.startswith("ZUP-"))
        self.assertTrue(req.external_doc_id.startswith("DL-"))
        self.assertEqual(req.doc_status, "on_signing")
        # в ЗУП ушёл документ «Отпуск», в Documentolog — приказ с адресом обратного вызова
        self.assertEqual(InMemoryZupAdapter.pushed[0]["days"], 5)
        self.assertTrue(InMemoryDocflowAdapter.created[0]["callback_url"].endswith(WEBHOOK))
        notes = list(req.events.values_list("comment", flat=True))
        self.assertTrue(any("1С:ЗУП" in n for n in notes) and any("Documentolog" in n for n in notes))

    def test_external_failure_does_not_break_approval_and_is_retried(self):
        with mock.patch.object(InMemoryDocflowAdapter, "create_document", side_effect=IntegrationError("down")):
            req = self.approved_vacation()  # утверждение прошло, несмотря на сбой Documentolog
            task = req.outbox_tasks.get(target="documentolog")
            self.assertEqual((task.status, task.attempts, task.last_error), (OutboxTask.TaskStatus.PENDING, 1, "down"))
            self.assertGreater(task.next_attempt_at, timezone.now() + timedelta(seconds=20))  # повтор через ~30 с
            self.assertEqual(outbox.process_due(), [])  # время повтора ещё не наступило

        OutboxTask.objects.filter(pk=task.pk).update(next_attempt_at=timezone.now())
        delivered = outbox.process_due()  # Documentolog снова доступен
        self.assertEqual([t.status for t in delivered], [OutboxTask.TaskStatus.SENT])
        self.assertTrue(HrRequest.objects.get(pk=req.pk).external_doc_id.startswith("DL-"))

    @override_settings(OUTBOX_MAX_ATTEMPTS=2)
    def test_attempts_exhausted_then_manual_retry(self):
        with mock.patch.object(InMemoryDocflowAdapter, "create_document", side_effect=IntegrationError("down")):
            req = self.approved_vacation()
            OutboxTask.objects.filter(request=req).update(next_attempt_at=timezone.now())
            outbox.process_due()
            task = req.outbox_tasks.get(target="documentolog")
            self.assertEqual((task.status, task.attempts), (OutboxTask.TaskStatus.FAILED, 2))
        outbox.retry_now(OutboxTask.objects.filter(pk=task.pk))  # кнопка «Отправить повторно» в админке
        outbox.dispatch([task.pk])
        task.refresh_from_db()
        self.assertEqual(task.status, OutboxTask.TaskStatus.SENT)

    # --- обратный вызов Documentolog ---

    def post_webhook(self, body: dict, secret="dev-webhook-secret"):
        raw = json.dumps(body).encode()
        sig = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
        self.client.force_authenticate(None)
        return self.client.generic(
            "POST", WEBHOOK, raw, content_type="application/json", HTTP_X_DOCUMENTOLOG_SIGNATURE=sig
        )

    def test_webhook_signed(self):
        req = self.approved_vacation()
        body = {"event": "document.signed", "document_id": req.external_doc_id,
                "registration_number": "15-к/2026", "signer": "Директор"}

        self.assertEqual(self.post_webhook(body, secret="wrong").status_code, 403)
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.post_webhook(body).status_code, 200)
        req.refresh_from_db()
        self.assertEqual((req.doc_status, req.doc_registration_number, req.status),
                         ("signed", "15-к/2026", Status.APPROVED_SENT_TO_1C))  # статус заявки не меняется
        self.assertTrue(req.events.filter(comment__contains="приказ подписан").exists())
        self.assertTrue(Notification.objects.filter(user=self.emp, title__contains="приказ подписан").exists())
        # повторный вызов ничего не меняет
        self.assertEqual(self.post_webhook(body).data["status"], "already processed")
        self.assertEqual(req.events.filter(comment__contains="приказ подписан").count(), 1)

    def test_webhook_rejected_notifies_hr_and_unknown_document(self):
        req = self.approved_vacation()
        with self.captureOnCommitCallbacks(execute=True):
            self.post_webhook({"event": "document.rejected", "document_id": req.external_doc_id, "comment": "Нет подписи"})
        req.refresh_from_db()
        self.assertEqual(req.doc_status, "rejected")
        self.assertTrue(Notification.objects.filter(user=self.hr, title__contains="отклонён").exists())
        self.assertEqual(self.post_webhook({"event": "document.signed", "document_id": "DL-NOPE"}).status_code, 404)
