from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from academy.grading import grade_quiz
from academy.models import (
    AssignmentStatus,
    Course,
    CourseAssignment,
    Lesson,
    LessonProgress,
    LessonType,
    Quiz,
    QuizAttempt,
)
from accounts.models import Role
from core import events
from org.scopes import team_members


def ordered_lessons(course: Course) -> list[Lesson]:
    return list(
        Lesson.objects.filter(module__course=course)
        .select_related("module")
        .order_by("module__order", "module_id", "order", "id")
    )


def completed_lesson_ids(assignment: CourseAssignment) -> set[int]:
    return set(assignment.lesson_progress.values_list("lesson_id", flat=True))


def locked_lesson_ids(assignment: CourseAssignment, lessons=None, done=None) -> set[int]:
    """Уроки открываются по порядку: следующий доступен, когда пройдены все предыдущие."""
    lessons = lessons if lessons is not None else ordered_lessons(assignment.course)
    done = done if done is not None else completed_lesson_ids(assignment)
    locked, blocked = set(), False
    for lesson in lessons:
        if blocked:
            locked.add(lesson.id)
        elif lesson.id not in done:
            blocked = True
    return locked


def attempts_left(assignment: CourseAssignment, quiz: Quiz) -> int | None:
    if quiz.max_attempts == 0:
        return None  # без ограничений
    used = assignment.attempts.filter(quiz=quiz).count()
    return max(quiz.max_attempts - used, 0)


def _check_owner(user, assignment: CourseAssignment) -> None:
    if assignment.employee_id != user.employee_id:
        raise PermissionDenied("Проходить курс может только сам сотрудник")


def _check_unlocked(assignment: CourseAssignment, lesson: Lesson) -> None:
    if lesson.module.course_id != assignment.course_id:
        raise ValidationError({"lesson": "Урок не относится к этому курсу"})
    if lesson.id in locked_lesson_ids(assignment):
        raise ValidationError({"lesson": "Сначала пройдите предыдущие уроки"})


def _start(assignment: CourseAssignment) -> None:
    if assignment.status == AssignmentStatus.ASSIGNED:
        assignment.status = AssignmentStatus.IN_PROGRESS
        assignment.started_at = timezone.now()


def _recalc(assignment: CourseAssignment) -> None:
    lessons = ordered_lessons(assignment.course)
    done = completed_lesson_ids(assignment)
    assignment.progress_pct = round(len(done & {l.id for l in lessons}) / len(lessons) * 100) if lessons else 0

    if lessons and all(l.id in done for l in lessons) and assignment.status != AssignmentStatus.COMPLETED:
        best = (
            assignment.attempts.filter(passed=True).order_by().values("quiz")
            .annotate(best=Max("score")).values_list("best", flat=True)
        )
        best = list(best)  # лучший результат по каждому тесту курса
        assignment.score = round(sum(best) / len(best)) if best else None
        assignment.status = AssignmentStatus.COMPLETED
        assignment.completed_at = timezone.now()
        transaction.on_commit(lambda: events.publish(events.COURSE_COMPLETED, assignment=assignment))
    assignment.save()


@transaction.atomic
def complete_lesson(user, assignment: CourseAssignment, lesson: Lesson) -> CourseAssignment:
    _check_owner(user, assignment)
    if lesson.type == LessonType.QUIZ:
        raise ValidationError({"lesson": "Тест засчитывается только после успешной сдачи"})
    _check_unlocked(assignment, lesson)
    _start(assignment)
    LessonProgress.objects.get_or_create(assignment=assignment, lesson=lesson)
    _recalc(assignment)
    return assignment


@transaction.atomic
def submit_attempt(user, assignment: CourseAssignment, quiz: Quiz, answers: dict) -> QuizAttempt:
    assignment = CourseAssignment.objects.select_for_update().get(pk=assignment.pk)
    _check_owner(user, assignment)
    _check_unlocked(assignment, quiz.lesson)
    if assignment.attempts.filter(quiz=quiz, passed=True).exists():
        raise ValidationError({"quiz": "Тест уже сдан"})
    if attempts_left(assignment, quiz) == 0:
        raise ValidationError({"quiz": "Попытки закончились — обратитесь в HR"})

    score, details = grade_quiz(quiz, answers)
    passed = score >= quiz.pass_score
    attempt = QuizAttempt.objects.create(
        assignment=assignment, quiz=quiz, answers=answers, details=details, score=score, passed=passed
    )
    _start(assignment)
    if passed:
        LessonProgress.objects.get_or_create(assignment=assignment, lesson=quiz.lesson)
    elif attempts_left(assignment, quiz) == 0 and assignment.status != AssignmentStatus.COMPLETED:
        assignment.status = AssignmentStatus.FAILED
    _recalc(assignment)
    return attempt


@transaction.atomic
def enroll(user, course: Course) -> CourseAssignment:
    """Сотрудник сам записывается на курс из каталога."""
    if user.employee_id is None:
        raise PermissionDenied("Учётная запись не связана с сотрудником")
    if not course.is_published:
        raise ValidationError({"course": "Курс недоступен"})
    assignment, _ = CourseAssignment.objects.get_or_create(
        course=course, employee_id=user.employee_id, defaults={"assigned_by": user}
    )
    return assignment


@transaction.atomic
def assign(user, course: Course, employee_ids: list[int], due_date=None) -> list[CourseAssignment]:
    """HR назначает курс любому сотруднику, руководитель — только своим подчинённым."""
    if user.role not in (Role.MANAGER, Role.HR_ADMIN):
        raise PermissionDenied()
    allowed = team_members(user).filter(id__in=employee_ids)
    if allowed.count() != len(set(employee_ids)):
        raise ValidationError({"employee_ids": "Можно назначать курс только своим сотрудникам"})
    created = []
    for emp in allowed:
        assignment, is_new = CourseAssignment.objects.get_or_create(
            course=course, employee=emp, defaults={"assigned_by": user, "due_date": due_date}
        )
        if is_new:
            created.append(assignment)
            transaction.on_commit(
                lambda a=assignment: events.publish(events.COURSE_ASSIGNED, assignment=a, actor=user)
            )
    return created
