from datetime import timedelta

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from accounts.models import Role, User
from notifications.models import Notification, NotificationType
from recruitment.models import (
    FINAL_STAGES,
    PIPELINE,
    Candidate,
    CandidateEvent,
    Interview,
    InterviewKind,
    Stage,
    Vacancy,
)

REVIEW, NEXT, REJECT, HIRE, SCHEDULE = "review", "next", "reject", "hire", "schedule"
MAX_PDF_BYTES = 10 * 1024 * 1024
Action = CandidateEvent.Action


# --- доступ ---

def is_hr(user) -> bool:
    return user.is_authenticated and user.role == Role.HR_ADMIN


def visible_candidates(user):
    """HR — все кандидаты; руководитель — только те, у кого он интервьюер; остальные — никто."""
    qs = Candidate.objects.select_related("vacancy")
    if is_hr(user):
        return qs
    if user.is_authenticated and user.role == Role.MANAGER:
        return qs.filter(interviews__interviewer=user).distinct()
    return qs.none()


def _notify(user, title, body, candidate):
    if user is not None:
        Notification.objects.create(
            user=user, type=NotificationType.RECRUITMENT, title=title, body=body,
            link=f"/recruitment/{candidate.pk}",
        )


def _event(candidate, action, actor=None, comment=""):
    CandidateEvent.objects.create(candidate=candidate, action=action, stage=candidate.stage, actor=actor, comment=comment)


# --- публичная форма ---

def _validate_pdf(file) -> None:
    if file.size > MAX_PDF_BYTES:
        raise ValidationError({"resume_pdf": "Файл больше 10 МБ"})
    head = file.read(5)
    file.seek(0)
    if not file.name.lower().endswith(".pdf") or head != b"%PDF-":
        raise ValidationError({"resume_pdf": "Загрузите резюме в формате PDF"})


@transaction.atomic
def submit_application(data: dict, resume_pdf=None) -> Candidate:
    vacancy = Vacancy.objects.filter(pk=data["vacancy_id"], is_open=True).first()
    if vacancy is None:
        raise ValidationError({"vacancy_id": "Вакансия не найдена или закрыта"})
    if not data.get("profile_url") and resume_pdf is None:
        raise ValidationError({"resume_pdf": "Приложите PDF или укажите ссылку на профиль hh.kz"})
    if resume_pdf is not None:
        _validate_pdf(resume_pdf)

    candidate = Candidate.objects.create(
        vacancy=vacancy,
        full_name=data["full_name"].strip(),
        email=data["email"],
        phone=data["phone"].strip(),
        social=data.get("social", "").strip(),
        profile_url=data.get("profile_url", ""),
        resume_pdf=resume_pdf,
        expected_salary=data.get("expected_salary"),
        comment=data.get("comment", "").strip(),
        consent_at=timezone.now(),
    )
    _event(candidate, Action.SUBMITTED)
    for hr in User.objects.filter(role=Role.HR_ADMIN, is_active=True):
        _notify(hr, f"Новое резюме: {candidate.full_name}", f"Позиция: {vacancy.title_ru}", candidate)
    return candidate


# --- этапы ---

def allowed_actions(user, c: Candidate) -> list[str]:
    if not is_hr(user) or c.stage in FINAL_STAGES:
        return []
    actions = []
    if c.stage == Stage.SCREENING and c.reviewed_at is None:
        actions.append(REVIEW)
    if c.stage in (Stage.SCREENING, Stage.HR_INTERVIEW):
        actions.append(NEXT)
    if c.stage in (Stage.HR_INTERVIEW, Stage.TECH_INTERVIEW):
        actions.append(SCHEDULE)
    return actions + [REJECT, HIRE]


def _close_open_interviews(c: Candidate) -> None:
    c.interviews.filter(status=Interview.InterviewStatus.SCHEDULED, scheduled_at__gt=timezone.now()).update(
        status=Interview.InterviewStatus.CANCELLED
    )


@transaction.atomic
def apply_action(user, candidate: Candidate, action: str, comment: str = "") -> Candidate:
    c = Candidate.objects.select_for_update().get(pk=candidate.pk)
    if action not in allowed_actions(user, c) or action == SCHEDULE:
        raise ValidationError({"action": f"Действие «{action}» недоступно на этапе «{c.get_stage_display()}»"})
    now = timezone.now()
    if c.stage == Stage.SCREENING and c.reviewed_at is None:
        c.reviewed_at = now  # галочка скрининга: «Ознакомлен», отказ или приглашение на интервью

    if action == REVIEW:
        _event(c, Action.REVIEWED, user, comment)
    elif action == NEXT:
        c.stage = PIPELINE[PIPELINE.index(c.stage) + 1]
        _event(c, Action.ADVANCED, user, comment)
    elif action in (REJECT, HIRE):
        c.decision_stage = c.stage
        c.stage = Stage.REJECTED if action == REJECT else Stage.HIRED
        _close_open_interviews(c)
        _event(c, Action.REJECTED if action == REJECT else Action.HIRED, user, comment)
        if action == HIRE and c.vacancy.hiring_manager:
            _notify(getattr(c.vacancy.hiring_manager, "user", None),
                    f"Принят кандидат: {c.full_name}", f"Позиция: {c.vacancy.title_ru}", c)
    c.save()
    return c


@transaction.atomic
def schedule_interview(user, candidate: Candidate, scheduled_at, duration_min=60, interviewer=None, location=""):
    """HR назначает (или переносит) интервью текущего этапа. Техинтервью — с руководителем."""
    c = Candidate.objects.select_for_update().get(pk=candidate.pk)
    if SCHEDULE not in allowed_actions(user, c):
        raise ValidationError({"stage": "Интервью назначается на этапах HR-интервью и техническое интервью"})
    if scheduled_at <= timezone.now():
        raise ValidationError({"scheduled_at": "Выберите дату и время в будущем"})
    kind = InterviewKind.HR if c.stage == Stage.HR_INTERVIEW else InterviewKind.TECH
    if interviewer is None:
        manager = c.vacancy.hiring_manager
        interviewer = getattr(manager, "user", None) if kind == InterviewKind.TECH and manager else user
    if interviewer.role not in (Role.HR_ADMIN, Role.MANAGER):
        raise ValidationError({"interviewer_id": "Интервьюер — HR или руководитель"})

    interview = c.interviews.filter(kind=kind, status=Interview.InterviewStatus.SCHEDULED).first()
    rescheduled = interview is not None
    interview = interview or Interview(candidate=c, kind=kind, created_by=user)
    interview.scheduled_at = scheduled_at
    interview.duration_min = duration_min
    interview.interviewer = interviewer
    interview.location = location
    interview.save()

    when = timezone.localtime(scheduled_at).strftime("%d.%m.%Y %H:%M")
    _event(c, Action.SCHEDULED, user, f"{interview.get_kind_display()}: {when}" + (" (перенесено)" if rescheduled else ""))
    if interviewer != user:
        _notify(interviewer, f"{interview.get_kind_display()}: {c.full_name}, {when}",
                f"Позиция: {c.vacancy.title_ru}. {location}".strip(), c)
    c.save(update_fields=["updated_at"])
    return interview


@transaction.atomic
def leave_feedback(user, interview: Interview, feedback: str) -> Interview:
    if not (is_hr(user) or interview.interviewer_id == user.id):
        raise PermissionDenied("Отзыв оставляет интервьюер или HR")
    interview.feedback = feedback.strip()
    interview.status = Interview.InterviewStatus.DONE
    interview.save(update_fields=["feedback", "status"])
    _event(interview.candidate, Action.FEEDBACK, user, f"{interview.get_kind_display()}: {interview.feedback}")
    return interview


# --- отображение ---

def steps(c: Candidate) -> list[dict]:
    """Шаги для карточки: done (галочка) | current | rejected | pending (серый) | skipped."""
    result = []
    final = c.stage in FINAL_STAGES
    # для принятых и отклонённых «текущий» шаг — тот, на котором принято решение
    current_idx = PIPELINE.index((c.decision_stage or Stage.SCREENING) if final else c.stage)
    for idx, stage in enumerate(PIPELINE):
        if final:
            if idx < current_idx:
                state = "done"
            elif idx == current_idx:
                state = "rejected" if c.stage == Stage.REJECTED else "done"
            else:
                state = "skipped"
        elif idx < current_idx:
            state = "done"
        elif idx == current_idx:
            state = "done" if (stage == Stage.SCREENING and c.reviewed_at) else "current"
        else:
            state = "pending"
        result.append({"key": stage, "label": Stage(stage).label, "state": state})
    decision = "hired" if c.stage == Stage.HIRED else "rejected" if c.stage == Stage.REJECTED else "pending"
    result.append({"key": "decision", "label": "Решение", "state": decision})
    return result


def summary(user) -> dict:
    """Дашборд: новые резюме, воронка, ближайшие интервью (у руководителя — только свои)."""
    now = timezone.now()
    interviews = Interview.objects.filter(
        status=Interview.InterviewStatus.SCHEDULED,
        scheduled_at__gte=now - timedelta(hours=1), scheduled_at__lte=now + timedelta(days=30),
    ).select_related("candidate__vacancy", "interviewer__employee")
    if not is_hr(user):
        interviews = interviews.filter(interviewer=user)
    data = {"upcoming_interviews": interviews[:10]}
    if is_hr(user):
        counts = Candidate.objects.aggregate(
            new=Count("id", filter=Q(stage=Stage.SCREENING, reviewed_at__isnull=True)),
            **{stage: Count("id", filter=Q(stage=stage)) for stage in Stage.values},
        )
        data["new_resumes"] = counts.pop("new")
        data["by_stage"] = counts
    return data
