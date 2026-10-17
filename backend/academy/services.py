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

# Прогресс и попытки считаются только в текущем цикле (assignment.cycle).
# Повторное прохождение начинает новый цикл: история прошлых остаётся в базе.


def ordered_lessons(course: Course) -> list[Lesson]:
    return list(
        Lesson.objects.filter(module__course=course)
        .select_related("module")
        .order_by("module__order", "module_id", "order", "id")
    )


def completed_lesson_ids(assignment: CourseAssignment) -> set[int]:
    return set(
        assignment.lesson_progress.filter(cycle=assignment.cycle).values_list("lesson_id", flat=True)
    )


def cycle_attempts(assignment: CourseAssignment, quiz: Quiz | None = None):
    qs = assignment.attempts.filter(cycle=assignment.cycle)
    return qs.filter(quiz=quiz) if quiz is not None else qs


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
    return max(quiz.max_attempts - cycle_attempts(assignment, quiz).count(), 0)


def _check_owner(user, assignment: CourseAssignment) -> None:
    if assignment.employee_id != user.employee_id:
        raise PermissionDenied("Проходить курс может только сам сотрудник")


def _check_active(assignment: CourseAssignment) -> None:
    if assignment.status == AssignmentStatus.FAILED:
        raise ValidationError({"assignment": "Курс не сдан — попросите HR или руководителя назначить его повторно"})


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
        best = list(  # лучший результат по каждому тесту курса в этом цикле
            cycle_attempts(assignment).filter(passed=True).order_by().values("quiz")
            .annotate(best=Max("score")).values_list("best", flat=True)
        )
        assignment.score = round(sum(best) / len(best)) if best else None
        if assignment.score is not None:
            assignment.best_score = max(assignment.best_score or 0, assignment.score)
        assignment.status = AssignmentStatus.COMPLETED
        assignment.completed_at = timezone.now()
        transaction.on_commit(lambda: events.publish(events.COURSE_COMPLETED, assignment=assignment))
    assignment.save()


@transaction.atomic
def complete_lesson(user, assignment: CourseAssignment, lesson: Lesson) -> CourseAssignment:
    _check_owner(user, assignment)
    _check_active(assignment)
    if lesson.type == LessonType.QUIZ:
        raise ValidationError({"lesson": "Тест засчитывается только после успешной сдачи"})
    _check_unlocked(assignment, lesson)
    _start(assignment)
    LessonProgress.objects.get_or_create(assignment=assignment, lesson=lesson, cycle=assignment.cycle)
    _recalc(assignment)
    return assignment


@transaction.atomic
def submit_attempt(user, assignment: CourseAssignment, quiz: Quiz, answers: dict) -> QuizAttempt:
    assignment = CourseAssignment.objects.select_for_update().get(pk=assignment.pk)
    _check_owner(user, assignment)
    _check_active(assignment)
    _check_unlocked(assignment, quiz.lesson)
    if cycle_attempts(assignment, quiz).filter(passed=True).exists():
        raise ValidationError({"quiz": "Тест уже сдан"})
    if attempts_left(assignment, quiz) == 0:
        raise ValidationError({"quiz": "Попытки закончились — обратитесь в HR"})

    score, details = grade_quiz(quiz, answers)
    passed = score >= quiz.pass_score
    attempt = QuizAttempt.objects.create(
        assignment=assignment, quiz=quiz, cycle=assignment.cycle,
        answers=answers, details=details, score=score, passed=passed,
    )
    _start(assignment)
    if passed:
        LessonProgress.objects.get_or_create(assignment=assignment, lesson=quiz.lesson, cycle=assignment.cycle)
    elif attempts_left(assignment, quiz) == 0 and assignment.status != AssignmentStatus.COMPLETED:
        assignment.status = AssignmentStatus.FAILED
        transaction.on_commit(lambda: events.publish(events.COURSE_FAILED, assignment=assignment))
    _recalc(assignment)
    return attempt


def _new_cycle(assignment: CourseAssignment, by_user, due_date=None, keep_due=False) -> None:
    """Новое прохождение с нуля; best_score и история прошлых циклов сохраняются."""
    assignment.cycle += 1
    assignment.progress_pct = 0
    assignment.score = None
    assignment.completed_at = None
    assignment.assigned_by = by_user
    if not keep_due:
        assignment.due_date = due_date
    if by_user is not None and by_user.employee_id == assignment.employee_id:
        assignment.status = AssignmentStatus.IN_PROGRESS  # сам начал заново — сразу в процессе
        assignment.started_at = timezone.now()
    else:
        assignment.status = AssignmentStatus.ASSIGNED
        assignment.started_at = None
    assignment.save()


def can_reassign(user, assignment: CourseAssignment) -> bool:
    """HR — любому, руководитель — своим подчинённым; только завершённый или несданный курс."""
    return (
        assignment.status in (AssignmentStatus.FAILED, AssignmentStatus.COMPLETED)
        and user.role in (Role.MANAGER, Role.HR_ADMIN)
        and team_members(user).filter(pk=assignment.employee_id).exists()
    )


def can_restart_self(user, assignment: CourseAssignment) -> bool:
    """Сотрудник может перепройти уже сданный курс (несданный — только через переназначение)."""
    return assignment.employee_id == user.employee_id and assignment.status == AssignmentStatus.COMPLETED


@transaction.atomic
def restart(user, assignment: CourseAssignment, due_date=None) -> CourseAssignment:
    assignment = CourseAssignment.objects.select_for_update().get(pk=assignment.pk)
    if can_restart_self(user, assignment):
        _new_cycle(assignment, user, keep_due=True)
        return assignment
    if can_reassign(user, assignment):
        _new_cycle(assignment, user, due_date=due_date)
        transaction.on_commit(
            lambda: events.publish(events.COURSE_ASSIGNED, assignment=assignment, actor=user, repeat=True)
        )
        return assignment
    raise ValidationError({"assignment": "Перепройти можно завершённый курс; несданный назначает повторно HR или руководитель"})


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
    """HR назначает курс любому сотруднику, руководитель — только своим подчинённым.

    Курс уже был и завершён или не сдан → назначается повторно (новый цикл).
    Курс сейчас в процессе → пропускается.
    """
    if user.role not in (Role.MANAGER, Role.HR_ADMIN):
        raise PermissionDenied()
    allowed = team_members(user).filter(id__in=employee_ids)
    if allowed.count() != len(set(employee_ids)):
        raise ValidationError({"employee_ids": "Можно назначать курс только своим сотрудникам"})
    result = []
    for emp in allowed:
        assignment, is_new = CourseAssignment.objects.get_or_create(
            course=course, employee=emp, defaults={"assigned_by": user, "due_date": due_date}
        )
        repeat = False
        if not is_new:
            if assignment.status not in (AssignmentStatus.FAILED, AssignmentStatus.COMPLETED):
                continue
            _new_cycle(assignment, user, due_date=due_date)
            repeat = True
        result.append(assignment)
        transaction.on_commit(
            lambda a=assignment, r=repeat: events.publish(events.COURSE_ASSIGNED, assignment=a, actor=user, repeat=r)
        )
    return result
