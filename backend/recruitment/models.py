"""Подбор персонала: вакансии → кандидаты (резюме с публичной формы) → этапы и интервью.

Этапы кандидата:
    screening      Скрининг резюме — галочка после «Ознакомлен», «Отклонить» или перехода дальше
    hr_interview   HR-интервью (дата и время)
    tech_interview Техническое интервью (дата, время, интервьюер-руководитель)
    hired          Принят (финал)
    rejected       Отказ (финал); decision_stage — на каком этапе принято решение (отказ или найм)
На любом незавершённом этапе HR может «Отклонить» или «Нанять».
"""
from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models

from org.models import Department, Employee
from recruitment.storage import private_storage


class VacancyStatus(models.TextChoices):
    DRAFT = "draft", "Черновик"
    ACTIVE = "active", "Открыта"
    CLOSED = "closed", "Закрыта"


class EmploymentType(models.TextChoices):
    FULL_TIME = "full_time", "Полная занятость"
    PART_TIME = "part_time", "Частичная занятость"
    CONTRACT = "contract", "Договор ГПХ"
    INTERNSHIP = "internship", "Стажировка"


class Vacancy(models.Model):
    title_ru = models.CharField("название (рус.)", max_length=200)
    title_kk = models.CharField("название (каз.)", max_length=200, blank=True)
    department = models.ForeignKey(
        Department, verbose_name="подразделение", null=True, blank=True, on_delete=models.SET_NULL
    )
    hiring_manager = models.ForeignKey(
        Employee, verbose_name="руководитель (техинтервью по умолчанию)", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
    )
    description = models.TextField("описание", blank=True)
    employment_type = models.CharField(
        "тип занятости", max_length=16, choices=EmploymentType.choices, default=EmploymentType.FULL_TIME
    )
    salary_from = models.PositiveIntegerField("зарплата от, ₸", null=True, blank=True)
    salary_to = models.PositiveIntegerField("зарплата до, ₸", null=True, blank=True)
    # в публичной форме видны только открытые; черновик ещё готовится, закрытая резюме не принимает
    status = models.CharField("статус", max_length=8, choices=VacancyStatus.choices, default=VacancyStatus.ACTIVE)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="создал", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="+",
    )
    created_at = models.DateTimeField("создана", auto_now_add=True)

    class Meta:
        verbose_name = "вакансия"
        verbose_name_plural = "вакансии"
        ordering = ["title_ru"]

    def __str__(self):
        return self.title_ru

    @property
    def is_open(self) -> bool:
        return self.status == VacancyStatus.ACTIVE


class Stage(models.TextChoices):
    SCREENING = "screening", "Скрининг резюме"
    HR_INTERVIEW = "hr_interview", "HR-интервью"
    TECH_INTERVIEW = "tech_interview", "Техническое интервью"
    HIRED = "hired", "Принят"
    REJECTED = "rejected", "Отказ"


PIPELINE = [Stage.SCREENING, Stage.HR_INTERVIEW, Stage.TECH_INTERVIEW]
FINAL_STAGES = [Stage.HIRED, Stage.REJECTED]


class Candidate(models.Model):
    vacancy = models.ForeignKey(Vacancy, verbose_name="позиция", on_delete=models.PROTECT, related_name="candidates")
    full_name = models.CharField("имя", max_length=200)
    email = models.EmailField("почта")
    phone = models.CharField("телефон", max_length=32)
    social = models.CharField("соцсеть (Telegram / Instagram)", max_length=200, blank=True)
    profile_url = models.URLField("профиль hh.kz / LinkedIn", blank=True)
    resume_pdf = models.FileField(
        "резюме (PDF)", storage=private_storage, upload_to="resumes/%Y/%m/", blank=True,
        validators=[FileExtensionValidator(["pdf"])],
    )
    expected_salary = models.PositiveIntegerField("ожидаемая зарплата, ₸", null=True, blank=True)
    comment = models.TextField("комментарий кандидата", blank=True)
    consent_at = models.DateTimeField("согласие на обработку ПДн")

    stage = models.CharField("этап", max_length=16, choices=Stage.choices, default=Stage.SCREENING)
    reviewed_at = models.DateTimeField("резюме просмотрено", null=True, blank=True)
    decision_stage = models.CharField("этап, на котором принято решение", max_length=16, choices=Stage.choices, blank=True)
    created_at = models.DateTimeField("получено", auto_now_add=True)
    updated_at = models.DateTimeField("изменено", auto_now=True)

    class Meta:
        verbose_name = "кандидат"
        verbose_name_plural = "кандидаты"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["vacancy", "stage"])]

    def __str__(self):
        return f"{self.full_name} — {self.vacancy}"

    @property
    def number(self) -> str:
        """Номер заявки: по нему и почте кандидат смотрит статус на сайте."""
        return f"CV-{self.pk:04d}"


class InterviewKind(models.TextChoices):
    HR = "hr", "HR-интервью"
    TECH = "tech", "Техническое интервью"


class Interview(models.Model):
    class InterviewStatus(models.TextChoices):
        SCHEDULED = "scheduled", "Назначено"
        DONE = "done", "Проведено"
        CANCELLED = "cancelled", "Отменено"

    candidate = models.ForeignKey(Candidate, verbose_name="кандидат", on_delete=models.CASCADE, related_name="interviews")
    kind = models.CharField("вид", max_length=8, choices=InterviewKind.choices)
    scheduled_at = models.DateTimeField("дата и время")
    duration_min = models.PositiveIntegerField("длительность, мин", default=60)
    interviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="интервьюер", null=True, on_delete=models.SET_NULL, related_name="+"
    )
    location = models.CharField("где (кабинет или ссылка на звонок)", max_length=300, blank=True)
    status = models.CharField("статус", max_length=16, choices=InterviewStatus.choices, default=InterviewStatus.SCHEDULED)
    feedback = models.TextField("отзыв интервьюера", blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "интервью"
        verbose_name_plural = "интервью"
        ordering = ["scheduled_at"]


class CandidateEvent(models.Model):
    """История кандидата: кто, когда и что сделал."""

    class Action(models.TextChoices):
        SUBMITTED = "submitted", "Резюме получено"
        REVIEWED = "reviewed", "Резюме просмотрено"
        ADVANCED = "advanced", "Переведён на следующий этап"
        SCHEDULED = "scheduled", "Назначено интервью"
        FEEDBACK = "feedback", "Отзыв интервьюера"
        REJECTED = "rejected", "Отказ"
        HIRED = "hired", "Принят"

    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name="events")
    action = models.CharField(max_length=16, choices=Action.choices)
    stage = models.CharField(max_length=16, choices=Stage.choices)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
