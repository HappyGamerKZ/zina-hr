"""Подбор: публичная форма, доступ, этапы, интервью, закрытые резюме.

docker compose exec backend python manage.py test recruitment
"""
from datetime import date, timedelta

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import Role, User
from core.demo_recruitment import make_pdf
from notifications.models import Notification
from org.models import Company, Department, Employee, Position
from recruitment.models import Candidate, Interview, Stage, Vacancy, VacancyStatus

APPLY = "/api/v1/careers/applications"


class RecruitmentTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        company = Company.objects.create(name_ru="Тест", external_id="C1")
        dep = Department.objects.create(company=company, name_ru="Логистика", external_id="D1")
        pos = Position.objects.create(title_ru="Должность", external_id="P1")

        def person(code, role):
            emp = Employee.objects.create(full_name=f"Сотрудник {code}", company=company, department=dep,
                                          position=pos, hire_date=date(2020, 1, 1), external_id=code)
            return User.objects.create_user(username=code, password="x", role=role, employee=emp)

        cls.hr = person("hr", Role.HR_ADMIN)
        cls.mgr = person("manager", Role.MANAGER)
        cls.other_mgr = person("other_manager", Role.MANAGER)
        cls.emp = person("employee", Role.EMPLOYEE)
        cls.vacancy = Vacancy.objects.create(title_ru="Логист", department=dep, hiring_manager=cls.mgr.employee)
        cls.closed = Vacancy.objects.create(title_ru="Закрытая", status=VacancyStatus.CLOSED)

    def setUp(self):
        cache.clear()  # счётчик ограничения частоты отправок

    # --- публичная форма ---

    def apply(self, **overrides):
        data = {
            "vacancy_id": self.vacancy.id, "full_name": "Кандидат Тестовый", "email": "c@example.com",
            "phone": "+7 700 123 45 67", "social": "@cand", "expected_salary": 400000, "comment": "Привет",
            "consent": "true", "resume_pdf": SimpleUploadedFile("cv.pdf", make_pdf(["CV"]), "application/pdf"),
        }
        data.update(overrides)
        data = {k: v for k, v in data.items() if v is not None}
        self.client.force_authenticate(None)
        return self.client.post(APPLY, data, format="multipart")

    def test_public_application_creates_candidate_and_notifies_hr(self):
        res = self.apply()
        self.assertEqual(res.status_code, 201, res.data)
        c = Candidate.objects.get()
        self.assertEqual((c.stage, c.expected_salary, c.reviewed_at), (Stage.SCREENING, 400000, None))
        self.assertTrue(c.resume_pdf.name.startswith("resumes/"))
        self.assertTrue(Notification.objects.filter(user=self.hr, type="recruitment").exists())
        self.assertFalse(Notification.objects.filter(user=self.emp).exists())

    def test_public_application_validation(self):
        fake_pdf = SimpleUploadedFile("cv.pdf", b"not a pdf at all", "application/pdf")
        self.assertEqual(self.apply(resume_pdf=fake_pdf).status_code, 400)
        self.assertEqual(self.apply(consent="false").status_code, 400)
        self.assertEqual(self.apply(vacancy_id=self.closed.id).status_code, 400)
        self.assertEqual(self.apply(resume_pdf=None).status_code, 400)  # ни PDF, ни ссылки
        res = self.apply(resume_pdf=None, profile_url="https://hh.kz/resume/123")  # ссылка вместо PDF — можно
        self.assertEqual(res.status_code, 201, res.data)

    def test_honeypot_and_rate_limit(self):
        self.assertEqual(self.apply(website="http://spam").status_code, 201)
        self.assertEqual(Candidate.objects.count(), 0)  # бот получил «успех», но ничего не сохранено
        cache.clear()
        codes = [self.apply().status_code for _ in range(6)]
        self.assertEqual(codes[:5], [201] * 5)
        self.assertEqual(codes[5], 429)

    # --- доступ ---

    def make_candidate(self, stage=Stage.SCREENING) -> Candidate:
        self.apply()
        c = Candidate.objects.latest("id")
        Candidate.objects.filter(pk=c.pk).update(stage=stage)
        return Candidate.objects.get(pk=c.pk)

    def test_access_control(self):
        c = self.make_candidate()
        url = f"/api/v1/recruitment/candidates/{c.id}"
        self.client.force_authenticate(None)
        self.assertIn(self.client.get(url).status_code, (401, 403))
        self.client.force_authenticate(self.emp)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.get(url + "/resume").status_code, 403)
        self.client.force_authenticate(self.mgr)  # руководитель без интервью кандидата не видит
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_authenticate(self.hr)
        res = self.client.get(url + "/resume")
        self.assertEqual((res.status_code, res["Content-Type"]), (200, "application/pdf"))
        self.assertEqual(b"".join(res.streaming_content)[:5], b"%PDF-")

    # --- этапы ---

    def act(self, c, action, comment=""):
        return self.client.post(f"/api/v1/recruitment/candidates/{c.id}/actions",
                                {"action": action, "comment": comment}, format="json")

    def schedule(self, c, days=1, interviewer_id=None):
        when = (timezone.now() + timedelta(days=days)).isoformat()
        body = {"scheduled_at": when, "location": "Zoom"}
        if interviewer_id:
            body["interviewer_id"] = interviewer_id
        return self.client.post(f"/api/v1/recruitment/candidates/{c.id}/interviews", body, format="json")

    def step_states(self, data):
        return {s["key"]: s["state"] for s in data["steps"]}

    def test_full_pipeline_to_hire(self):
        c = self.make_candidate()
        self.client.force_authenticate(self.hr)
        data = self.client.get(f"/api/v1/recruitment/candidates/{c.id}").data
        self.assertEqual(self.step_states(data)["screening"], "current")  # серое до решения
        self.assertEqual(data["allowed_actions"], ["review", "next", "reject", "hire"])

        data = self.act(c, "review").data
        self.assertEqual(self.step_states(data)["screening"], "done")  # «Ознакомлен» → галочка
        self.assertEqual(data["stage"], Stage.SCREENING)

        data = self.act(c, "next").data
        self.assertEqual(data["stage"], Stage.HR_INTERVIEW)
        self.assertIn("schedule", data["allowed_actions"])
        self.assertEqual(self.schedule(c, days=-1).status_code, 400)  # дата в прошлом
        data = self.schedule(c).data
        self.assertEqual(data["interviews"][0]["kind"], "hr")
        self.assertEqual(data["interviews"][0]["interviewer"]["id"], self.hr.id)  # по умолчанию — сам HR

        data = self.act(c, "next").data
        self.assertEqual(data["stage"], Stage.TECH_INTERVIEW)
        self.assertNotIn("next", data["allowed_actions"])
        data = self.schedule(c, days=2).data  # интервьюер по умолчанию — руководитель вакансии
        tech = next(i for i in data["interviews"] if i["kind"] == "tech")
        self.assertEqual(tech["interviewer"]["id"], self.mgr.id)
        self.assertTrue(Notification.objects.filter(user=self.mgr, type="recruitment").exists())

        data = self.act(c, "hire").data
        self.assertEqual((data["stage"], data["decision_stage"]), (Stage.HIRED, Stage.TECH_INTERVIEW))
        self.assertEqual(self.step_states(data), {
            "screening": "done", "hr_interview": "done", "tech_interview": "done", "decision": "hired",
        })
        self.assertEqual(data["allowed_actions"], [])
        self.assertEqual(self.act(c, "reject").status_code, 400)  # финальный этап

    def test_reject_from_screening_marks_step(self):
        c = self.make_candidate()
        self.client.force_authenticate(self.hr)
        data = self.act(c, "reject", "Нет опыта").data
        self.assertEqual(self.step_states(data)["screening"], "rejected")
        self.assertEqual(self.step_states(data)["hr_interview"], "skipped")
        self.assertIsNotNone(Candidate.objects.get(pk=c.pk).reviewed_at)

    def test_manager_sees_only_own_interviews_and_leaves_feedback(self):
        c = self.make_candidate(Stage.TECH_INTERVIEW)
        self.client.force_authenticate(self.hr)
        self.schedule(c, days=2, interviewer_id=self.mgr.id)

        self.client.force_authenticate(self.mgr)
        listed = [x["id"] for x in self.client.get("/api/v1/recruitment/candidates").data]
        self.assertEqual(listed, [c.id])
        data = self.client.get(f"/api/v1/recruitment/candidates/{c.id}").data
        self.assertEqual(data["allowed_actions"], [])  # решения принимает HR
        self.assertEqual(self.act(c, "hire").status_code, 400)
        summary = self.client.get("/api/v1/recruitment/summary").data
        self.assertEqual(len(summary["upcoming_interviews"]), 1)
        self.assertNotIn("new_resumes", summary)
        interview = Interview.objects.get(candidate=c)
        res = self.client.post(f"/api/v1/recruitment/interviews/{interview.id}/feedback",
                               {"feedback": "Сильный кандидат"}, format="json")
        self.assertEqual(res.data["status"], "done")

        self.client.force_authenticate(self.other_mgr)
        self.assertEqual(self.client.get(f"/api/v1/recruitment/candidates/{c.id}").status_code, 404)
        self.assertEqual(self.client.get("/api/v1/recruitment/candidates").data, [])

    def test_hr_list_filters_and_summary(self):
        a = self.make_candidate()
        self.make_candidate(Stage.HR_INTERVIEW)
        self.client.force_authenticate(self.hr)
        by_stage = self.client.get("/api/v1/recruitment/candidates?stage=screening").data
        self.assertEqual([x["id"] for x in by_stage], [a.id])
        self.assertEqual(len(self.client.get(f"/api/v1/recruitment/candidates?vacancy={self.vacancy.id}").data), 2)
        self.assertEqual(self.client.get(f"/api/v1/recruitment/candidates?vacancy={self.closed.id}").data, [])
        summary = self.client.get("/api/v1/recruitment/summary").data
        self.assertEqual(summary["new_resumes"], 1)
        self.assertEqual(summary["by_stage"]["hr_interview"], 1)

    # --- вакансии, балл соответствия, статус для кандидата ---

    def test_vacancy_create_status_and_public_form(self):
        self.client.force_authenticate(self.emp)
        self.assertEqual(self.client.post("/api/v1/recruitment/vacancies", {"title_ru": "X"}, format="json").status_code, 403)
        self.client.force_authenticate(self.hr)
        res = self.client.post("/api/v1/recruitment/vacancies", {
            "title_ru": "Аналитик", "employment_type": "contract", "status": "draft",
            "salary_from": 500_000, "salary_to": 400_000,
        }, format="json")
        self.assertEqual(res.status_code, 400)  # «до» меньше «от»
        res = self.client.post("/api/v1/recruitment/vacancies", {
            "title_ru": "Аналитик", "employment_type": "contract", "status": "draft", "salary_to": 600_000,
        }, format="json")
        self.assertEqual((res.status_code, res.data["status"], res.data["is_open"]), (201, "draft", False))
        public = lambda: [v["title_ru"] for v in self.client.get("/api/v1/careers/vacancies").data]  # noqa: E731
        self.assertNotIn("Аналитик", public())  # черновик в форме не виден
        res = self.client.patch(f"/api/v1/recruitment/vacancies/{res.data['id']}", {"status": "active"}, format="json")
        self.assertEqual(res.data["status"], "active")
        self.assertIn("Аналитик", public())
        drafts = self.client.get("/api/v1/recruitment/vacancies?status=closed").data
        self.assertEqual([v["id"] for v in drafts], [self.closed.id])

    def test_match_score_and_hire_closes_vacancy(self):
        Vacancy.objects.filter(pk=self.vacancy.pk).update(salary_from=300_000, salary_to=450_000)
        c = self.make_candidate()
        self.client.force_authenticate(self.hr)
        data = self.client.get(f"/api/v1/recruitment/candidates/{c.id}").data
        # зарплата в вилке 35 + PDF 15 + короткий комментарий 5 + скрининг ещё не пройден 0
        self.assertEqual(data["match"]["score"], 55)
        self.assertEqual(sum(f["max"] for f in data["match"]["factors"]), 100)
        self.assertEqual(self.client.get("/api/v1/recruitment/candidates").data[0]["match_score"], 55)
        summary = self.client.get("/api/v1/recruitment/summary").data
        self.assertEqual([x["id"] for x in summary["top_candidates"]], [c.id])
        self.assertEqual(summary["open_vacancies"], 1)

        res = self.client.post(f"/api/v1/recruitment/candidates/{c.id}/actions",
                               {"action": "hire", "close_vacancy": True}, format="json")
        self.assertEqual((res.data["stage"], res.data["vacancy_status"]), (Stage.HIRED, "closed"))
        self.assertIsNotNone(res.data["steps"][-1]["date"])  # дата решения

    def test_candidate_tracks_application_by_number_and_email(self):
        res = self.apply()
        number = res.data["number"]
        self.assertRegex(number, r"^CV-\d{4}$")
        track = lambda n, e: self.client.post("/api/v1/careers/status", {"number": n, "email": e}, format="json")  # noqa: E731
        res = track(number.lower(), "C@Example.com")
        self.assertEqual((res.status_code, res.data["stage"]), (200, Stage.SCREENING))
        self.assertNotIn("email", res.data)
        self.assertNotIn("events", res.data)  # отзывы и комментарии HR кандидату не показываем
        self.assertEqual(track(number, "other@example.com").status_code, 404)
        self.assertEqual(track("CV-9999", "c@example.com").status_code, 404)
        self.assertEqual(track("abc", "c@example.com").status_code, 404)

    def test_interview_calendar_scoped(self):
        c = self.make_candidate(Stage.TECH_INTERVIEW)
        self.client.force_authenticate(self.hr)
        self.schedule(c, days=2, interviewer_id=self.mgr.id)
        self.assertEqual(len(self.client.get("/api/v1/recruitment/interviews").data), 1)
        self.assertEqual(self.client.get("/api/v1/recruitment/interviews?days=1").data, [])
        self.assertEqual(self.client.get("/api/v1/recruitment/interviews?from=bad").status_code, 400)
        self.client.force_authenticate(self.other_mgr)
        self.assertEqual(self.client.get("/api/v1/recruitment/interviews").data, [])
        self.client.force_authenticate(self.emp)
        self.assertEqual(self.client.get("/api/v1/recruitment/interviews").status_code, 403)
