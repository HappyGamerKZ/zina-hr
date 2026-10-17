"""Jana Academy: проверка ответов, порядок уроков, попытки, назначения, права.

docker compose exec backend python manage.py test academy
"""
from datetime import date

from rest_framework.test import APITestCase

from academy import services
from academy.grading import correct_answer, grade_question
from academy.models import AssignmentStatus, CourseAssignment, LessonType, QuestionType
from accounts.models import Role, User
from core.demo_courses import create_demo_courses
from notifications.models import Notification
from org.models import Company, Department, Employee, Position


class AcademyTests(APITestCase):
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
            return emp, User.objects.create_user(username=code, password="x", role=role, employee=emp)

        cls.hr_emp, cls.hr = person("hr", Role.HR_ADMIN)
        cls.mgr_emp, cls.mgr = person("manager", Role.MANAGER)
        cls.emp_emp, cls.emp = person("employee", Role.EMPLOYEE, manager=cls.mgr_emp)
        cls.other_mgr_emp, cls.other_mgr = person("other_manager", Role.MANAGER)
        cls.stranger_emp, cls.stranger = person("stranger", Role.EMPLOYEE, manager=cls.other_mgr_emp)
        cls.courses = create_demo_courses()
        cls.course = cls.courses["onboarding"]  # 3 текстовых урока + тест со всеми типами вопросов

    # --- helpers ---

    def enroll(self, user=None):
        self.client.force_authenticate(user or self.emp)
        res = self.client.post(f"/api/v1/academy/courses/{self.course.id}/enroll")
        self.assertEqual(res.status_code, 201, res.data)
        return res.data["id"]

    def lessons(self):
        return services.ordered_lessons(self.course)

    def quiz(self):
        return next(l for l in self.lessons() if l.type == LessonType.QUIZ).quiz

    def complete_text_lessons(self, assignment_id):
        for lesson in self.lessons():
            if lesson.type != LessonType.QUIZ:
                res = self.client.post(f"/api/v1/academy/assignments/{assignment_id}/lessons/{lesson.id}/complete")
                self.assertEqual(res.status_code, 200, res.data)

    def correct_answers(self):
        return {str(q.id): correct_answer(q) for q in self.quiz().questions.all()}

    def submit(self, assignment_id, answers):
        return self.client.post(
            f"/api/v1/academy/assignments/{assignment_id}/quizzes/{self.quiz().id}/attempts",
            {"answers": answers}, format="json",
        )

    # --- проверка ответов всех типов ---

    def test_grading_all_question_types(self):
        questions = {q.type: q for q in self.quiz().questions.prefetch_related("options")}
        self.assertEqual(set(questions), {t.value for t in QuestionType})
        for q in questions.values():
            self.assertEqual(grade_question(q, correct_answer(q)), 1.0, q.type)

        single = questions[QuestionType.SINGLE]
        wrong = next(o.id for o in single.options.all() if not o.is_correct)
        self.assertEqual(grade_question(single, wrong), 0.0)

        multi = questions[QuestionType.MULTIPLE]
        right = [o.id for o in multi.options.all() if o.is_correct]
        bad = [o.id for o in multi.options.all() if not o.is_correct]
        self.assertAlmostEqual(grade_question(multi, right[:2]), 2 / 3)        # 2 из 3 верных
        self.assertAlmostEqual(grade_question(multi, right + bad[:1]), 2 / 3)  # лишний вариант штрафуется
        self.assertEqual(grade_question(multi, bad), 0.0)

        ordering = questions[QuestionType.ORDERING]
        order = correct_answer(ordering)
        swapped = [order[1], order[0]] + order[2:]
        self.assertEqual(grade_question(ordering, swapped), 0.5)
        self.assertEqual(grade_question(ordering, order[:2]), 0.0)  # неполный ответ

        blanks = questions[QuestionType.FILL_BLANKS]
        answer = correct_answer(blanks)
        partial = {**answer, "3": next(o.id for o in blanks.options.all() if o.correct_position is None)}
        self.assertAlmostEqual(grade_question(blanks, partial), 2 / 3)
        self.assertEqual(grade_question(blanks, {}), 0.0)

    def test_quiz_payload_does_not_leak_answers(self):
        a_id = self.enroll()
        self.complete_text_lessons(a_id)
        res = self.client.get(f"/api/v1/academy/assignments/{a_id}/lessons/{self.quiz().lesson_id}")
        self.assertEqual(res.status_code, 200)
        text = str(res.data)
        self.assertNotIn("is_correct", text)
        self.assertNotIn("correct_position", text)
        blanks_q = next(q for q in res.data["quiz"]["questions"] if q["type"] == "fill_blanks")
        self.assertEqual(blanks_q["blanks"], [1, 2, 3])

    # --- прохождение курса ---

    def test_lessons_unlock_in_order(self):
        a_id = self.enroll()
        last_text = [l for l in self.lessons() if l.type != LessonType.QUIZ][-1]
        res = self.client.post(f"/api/v1/academy/assignments/{a_id}/lessons/{last_text.id}/complete")
        self.assertEqual(res.status_code, 400)
        res = self.client.get(f"/api/v1/academy/assignments/{a_id}/lessons/{self.quiz().lesson_id}")
        self.assertEqual(res.status_code, 403)

    def test_full_course_flow_with_retry(self):
        CourseAssignment.objects.filter(employee=self.emp_emp).delete()
        self.client.force_authenticate(self.mgr)
        res = self.client.post(
            "/api/v1/academy/assignments",
            {"course_id": self.course.id, "employee_ids": [self.emp_emp.id]}, format="json",
        )
        self.assertEqual(res.status_code, 201, res.data)
        a_id = res.data[0]["id"]

        self.client.force_authenticate(self.emp)
        self.complete_text_lessons(a_id)
        self.assertEqual(CourseAssignment.objects.get(pk=a_id).progress_pct, 75)

        res = self.submit(a_id, {})  # пустые ответы
        self.assertEqual(res.status_code, 201)
        self.assertFalse(res.data["passed"])
        self.assertFalse(res.data["answers_revealed"])
        self.assertEqual(res.data["attempts_left"], 2)

        with self.captureOnCommitCallbacks(execute=True):
            res = self.submit(a_id, self.correct_answers())
        self.assertTrue(res.data["passed"])
        self.assertEqual(res.data["score"], 100)
        self.assertTrue(res.data["answers_revealed"])

        a = CourseAssignment.objects.get(pk=a_id)
        self.assertEqual((a.status, a.progress_pct, a.score), (AssignmentStatus.COMPLETED, 100, 100))
        self.assertTrue(Notification.objects.filter(user=self.emp, type="course_completed").exists())
        self.assertTrue(Notification.objects.filter(user=self.mgr, type="course_completed").exists())
        # профиль показывает результат
        self.assertEqual(self.client.get("/api/v1/me/profile").data["learning"][0]["score"], 100)
        # повторно сдавать сданный тест нельзя
        self.assertEqual(self.submit(a_id, self.correct_answers()).status_code, 400)

    def test_attempts_exhausted_marks_failed(self):
        a_id = self.enroll()
        self.complete_text_lessons(a_id)
        for _ in range(self.quiz().max_attempts):
            res = self.submit(a_id, {})
        self.assertTrue(res.data["answers_revealed"])
        self.assertEqual(CourseAssignment.objects.get(pk=a_id).status, AssignmentStatus.FAILED)
        self.assertEqual(self.submit(a_id, self.correct_answers()).status_code, 400)

    # --- назначения и права ---

    def test_assign_permissions_and_notification(self):
        self.client.force_authenticate(self.mgr)
        url = "/api/v1/academy/assignments"
        body = {"course_id": self.courses["security"].id, "employee_ids": [self.stranger_emp.id]}
        self.assertEqual(self.client.post(url, body, format="json").status_code, 400)  # чужой сотрудник

        with self.captureOnCommitCallbacks(execute=True):
            res = self.client.post(url, {**body, "employee_ids": [self.emp_emp.id]}, format="json")
        self.assertEqual(res.status_code, 201)
        self.assertTrue(Notification.objects.filter(user=self.emp, type="course_assigned").exists())

        self.client.force_authenticate(self.emp)
        self.assertEqual(self.client.post(url, body, format="json").status_code, 403)

        self.client.force_authenticate(self.hr)  # HR назначает любому
        body["employee_ids"] = [self.stranger_emp.id]
        self.assertEqual(self.client.post(url, body, format="json").status_code, 201)

    def test_visibility_of_assignments(self):
        a_id = self.enroll()
        self.client.force_authenticate(self.other_mgr)
        self.assertEqual(self.client.get(f"/api/v1/academy/assignments/{a_id}").status_code, 404)

        self.client.force_authenticate(self.mgr)  # руководитель видит прогресс подчинённого
        self.assertEqual(self.client.get(f"/api/v1/academy/assignments/{a_id}").status_code, 200)
        team = self.client.get("/api/v1/academy/assignments?scope=team").data
        self.assertIn(a_id, [x["id"] for x in team])
        # но не проходит курс за него
        first = self.lessons()[0]
        self.assertEqual(
            self.client.post(f"/api/v1/academy/assignments/{a_id}/lessons/{first.id}/complete").status_code, 403
        )
