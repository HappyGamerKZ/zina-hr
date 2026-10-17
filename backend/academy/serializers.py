import random
import re

from rest_framework import serializers

from academy import services
from academy.grading import correct_answer
from academy.models import Course, CourseAssignment, Lesson, LessonType, QuestionType, QuizAttempt

BLANK_RE = re.compile(r"\{\{(\d+)\}\}")


# --- курсы и каталог ---

class CourseShortSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = ["id", "title_ru", "title_kk", "cover_emoji"]


class CourseListSerializer(serializers.ModelSerializer):
    lessons_count = serializers.SerializerMethodField()
    my_assignment = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            "id", "title_ru", "title_kk", "description_ru", "description_kk", "cover_emoji",
            "duration_min", "lessons_count", "my_assignment",
        ]

    def get_lessons_count(self, course) -> int:
        return Lesson.objects.filter(module__course=course).count()

    def get_my_assignment(self, course) -> dict | None:
        a = self.context.get("my_assignments", {}).get(course.id)
        return {"id": a.id, "status": a.status, "progress_pct": a.progress_pct} if a else None


class CourseDetailSerializer(CourseListSerializer):
    modules = serializers.SerializerMethodField()

    class Meta(CourseListSerializer.Meta):
        fields = CourseListSerializer.Meta.fields + ["modules"]

    def get_modules(self, course) -> list:
        return [
            {
                "id": m.id,
                "title": m.title,
                "lessons": [
                    {"id": l.id, "title": l.title, "type": l.type, "duration_min": l.duration_min}
                    for l in m.lessons.all()
                ],
            }
            for m in course.modules.prefetch_related("lessons")
        ]


# --- назначения и прогресс ---

class AssignmentSerializer(serializers.ModelSerializer):
    course = CourseShortSerializer(read_only=True)
    employee = serializers.SerializerMethodField()
    assigned_by_name = serializers.SerializerMethodField()
    can_restart = serializers.SerializerMethodField()
    can_reassign = serializers.SerializerMethodField()

    class Meta:
        model = CourseAssignment
        fields = [
            "id", "course", "employee", "status", "progress_pct", "score", "best_score", "cycle", "due_date",
            "assigned_by_name", "created_at", "started_at", "completed_at", "can_restart", "can_reassign",
        ]

    def _user(self):
        request = self.context.get("request")
        return request.user if request is not None else None

    def get_can_restart(self, a) -> bool:
        """Сотрудник может перепройти сданный курс."""
        user = self._user()
        return bool(user and services.can_restart_self(user, a))

    def get_can_reassign(self, a) -> bool:
        """HR / руководитель может назначить курс повторно (несданный или завершённый)."""
        user = self._user()
        return bool(user and services.can_reassign(user, a))

    def get_employee(self, a) -> dict:
        return {"id": a.employee_id, "full_name": a.employee.full_name}

    def get_assigned_by_name(self, a) -> str | None:
        if a.assigned_by is None:
            return None
        if a.assigned_by.employee_id == a.employee_id:
            return None  # сам записался из каталога
        return a.assigned_by.employee.full_name if a.assigned_by.employee else a.assigned_by.username


def _quiz_state(assignment, quiz) -> dict:
    attempts = list(services.cycle_attempts(assignment, quiz))
    return {
        "id": quiz.id,
        "pass_score": quiz.pass_score,
        "max_attempts": quiz.max_attempts,
        "attempts_used": len(attempts),
        "attempts_left": services.attempts_left(assignment, quiz),
        "best_score": max((a.score for a in attempts), default=None),
        "passed": any(a.passed for a in attempts),
    }


class AssignmentDetailSerializer(AssignmentSerializer):
    modules = serializers.SerializerMethodField()

    class Meta(AssignmentSerializer.Meta):
        fields = AssignmentSerializer.Meta.fields + ["modules"]

    def get_modules(self, a) -> list:
        lessons = services.ordered_lessons(a.course)
        done = services.completed_lesson_ids(a)
        locked = services.locked_lesson_ids(a, lessons, done)
        modules: dict[int, dict] = {}
        for lesson in lessons:
            m = modules.setdefault(lesson.module_id, {"id": lesson.module_id, "title": lesson.module.title, "lessons": []})
            item = {
                "id": lesson.id,
                "title": lesson.title,
                "type": lesson.type,
                "duration_min": lesson.duration_min,
                "status": "completed" if lesson.id in done else "locked" if lesson.id in locked else "available",
            }
            if lesson.type == LessonType.QUIZ and hasattr(lesson, "quiz"):
                item["quiz"] = _quiz_state(a, lesson.quiz)
            m["lessons"].append(item)
        return list(modules.values())


# --- урок и тест (без правильных ответов) ---

def _public_question(q, assignment_id: int) -> dict:
    options = [{"id": o.id, "text": o.text} for o in q.options.all()]
    if q.type in (QuestionType.ORDERING, QuestionType.FILL_BLANKS):
        # стабильное перемешивание для конкретного сотрудника, чтобы порядок не прыгал при обновлении
        rnd = random.Random(assignment_id * 100_003 + q.id)
        original = [o["id"] for o in options]
        rnd.shuffle(options)
        if q.type == QuestionType.ORDERING and [o["id"] for o in options] == original and len(options) > 1:
            options = options[1:] + options[:1]  # не показывать сразу правильный порядок
    data = {"id": q.id, "type": q.type, "text": q.text, "points": q.points, "options": options}
    if q.type == QuestionType.FILL_BLANKS:
        data["blanks"] = sorted({int(n) for n in BLANK_RE.findall(q.text)})
    return data


YOUTUBE_RE = re.compile(r"(?:youtube\.com/(?:watch\?v=|embed/|shorts/)|youtu\.be/)([\w-]{11})")


def block_payload(block) -> dict:
    """Блок урока для фронта. Для YouTube сразу отдаём адрес для встраивания."""
    url = block.file.url if block.file else block.url
    match = YOUTUBE_RE.search(block.url or "")
    return {
        "id": block.id,
        "type": block.type,
        "text": block.text,
        "url": url,
        "file_name": block.file.name.rsplit("/", 1)[-1] if block.file else "",
        "embed_url": f"https://www.youtube-nocookie.com/embed/{match.group(1)}" if match else "",
    }


def lesson_payload(assignment, lesson) -> dict:
    lessons = services.ordered_lessons(assignment.course)
    done = services.completed_lesson_ids(assignment)
    ids = [l.id for l in lessons]
    idx = ids.index(lesson.id)
    data = {
        "id": lesson.id,
        "title": lesson.title,
        "type": lesson.type,
        "blocks": [block_payload(b) for b in lesson.blocks.all()],
        "module": lesson.module.title,
        "completed": lesson.id in done,
        "prev_lesson_id": ids[idx - 1] if idx > 0 else None,
        "next_lesson_id": ids[idx + 1] if idx + 1 < len(ids) else None,
    }
    if lesson.type == LessonType.QUIZ and hasattr(lesson, "quiz"):
        quiz = lesson.quiz
        state = _quiz_state(assignment, quiz)
        last = services.cycle_attempts(assignment, quiz).last()
        data["quiz"] = {
            **state,
            "questions": [_public_question(q, assignment.id) for q in quiz.questions.prefetch_related("options")],
            "last_attempt": attempt_payload(last, state) if last else None,
        }
    return data


def attempt_payload(attempt: QuizAttempt, state: dict | None = None) -> dict:
    state = state or _quiz_state(attempt.assignment, attempt.quiz)
    # Правильные ответы показываем, только когда тест сдан или попыток не осталось.
    reveal = attempt.passed or state["attempts_left"] == 0
    questions = {q.id: q for q in attempt.quiz.questions.prefetch_related("options")}
    details = []
    for d in attempt.details:
        q = questions.get(d["question_id"])
        item = {**d, "your_answer": attempt.answers.get(str(d["question_id"]))}
        if reveal and q:
            item["correct_answer"] = correct_answer(q)
            item["explanation"] = q.explanation
        details.append(item)
    return {
        "id": attempt.id,
        "score": attempt.score,
        "passed": attempt.passed,
        "created_at": attempt.created_at,
        "pass_score": attempt.quiz.pass_score,
        "attempts_left": state["attempts_left"],
        "answers_revealed": reveal,
        "details": details,
    }


class AssignInputSerializer(serializers.Serializer):
    course_id = serializers.IntegerField()
    employee_ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=False)
    due_date = serializers.DateField(required=False, allow_null=True)


class AttemptInputSerializer(serializers.Serializer):
    answers = serializers.DictField()


class RestartInputSerializer(serializers.Serializer):
    due_date = serializers.DateField(required=False, allow_null=True)
