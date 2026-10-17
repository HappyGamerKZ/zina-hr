"""Jana Academy: курс → модули → уроки (текст / видео / PDF / тест) → вопросы → варианты.

Типы вопросов и как хранится правильный ответ:
    single       — один верный вариант:            Option.is_correct
    multiple     — несколько верных вариантов:     Option.is_correct
    ordering     — расставить в правильном порядке: Option.correct_position = 1..N
    fill_blanks  — перетащить слова в пропуски текста: Question.text содержит {{1}}, {{2}}…,
                   Option.correct_position = номер пропуска, None = лишнее слово (дистрактор)

Правильные ответы (is_correct, correct_position) никогда не отдаются на фронт до проверки.
"""
from django.conf import settings
from django.db import models

from org.models import Employee


class Course(models.Model):
    title_ru = models.CharField(max_length=200)
    title_kk = models.CharField(max_length=200, blank=True)
    description_ru = models.TextField(blank=True)
    description_kk = models.TextField(blank=True)
    cover_emoji = models.CharField(max_length=8, default="📘")
    duration_min = models.PositiveIntegerField(default=30)
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "курс"
        verbose_name_plural = "курсы"
        ordering = ["id"]

    def __str__(self):
        return self.title_ru


class CourseModule(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="modules")
    order = models.PositiveIntegerField(default=1)
    title = models.CharField(max_length=200)

    class Meta:
        verbose_name = "модуль"
        verbose_name_plural = "модули"
        ordering = ["course", "order", "id"]

    def __str__(self):
        return f"{self.course} / {self.title}"


class LessonType(models.TextChoices):
    TEXT = "text", "Текст"
    VIDEO = "video", "Видео"
    PDF = "pdf", "PDF"
    QUIZ = "quiz", "Тест"


class Lesson(models.Model):
    module = models.ForeignKey(CourseModule, on_delete=models.CASCADE, related_name="lessons")
    order = models.PositiveIntegerField(default=1)
    title = models.CharField(max_length=200)
    type = models.CharField(max_length=8, choices=LessonType.choices, default=LessonType.TEXT)
    content = models.TextField("текст урока", blank=True)
    media_url = models.URLField("ссылка на видео / PDF", blank=True)
    duration_min = models.PositiveIntegerField(default=5)

    class Meta:
        verbose_name = "урок"
        verbose_name_plural = "уроки"
        ordering = ["module__order", "order", "id"]

    def __str__(self):
        return f"{self.module} / {self.title}"


class Quiz(models.Model):
    lesson = models.OneToOneField(Lesson, on_delete=models.CASCADE, related_name="quiz")
    pass_score = models.PositiveIntegerField("проходной балл, %", default=70)
    max_attempts = models.PositiveIntegerField("попыток (0 — без ограничений)", default=3)

    class Meta:
        verbose_name = "тест"
        verbose_name_plural = "тесты"

    def __str__(self):
        return f"Тест: {self.lesson.title}"


class QuestionType(models.TextChoices):
    SINGLE = "single", "Один вариант"
    MULTIPLE = "multiple", "Несколько вариантов"
    ORDERING = "ordering", "Правильный порядок"
    FILL_BLANKS = "fill_blanks", "Перетащить слова в пропуски"


class Question(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="questions")
    order = models.PositiveIntegerField(default=1)
    type = models.CharField(max_length=16, choices=QuestionType.choices)
    text = models.TextField(help_text="Для fill_blanks пропуски обозначаются {{1}}, {{2}}, …")
    points = models.PositiveIntegerField(default=1)
    explanation = models.TextField("пояснение после проверки", blank=True)

    class Meta:
        verbose_name = "вопрос"
        verbose_name_plural = "вопросы"
        ordering = ["quiz", "order", "id"]

    def __str__(self):
        return self.text[:80]


class Option(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="options")
    text = models.CharField(max_length=300)
    is_correct = models.BooleanField(default=False, help_text="single / multiple")
    correct_position = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="ordering: место в правильном порядке (1..N); fill_blanks: номер пропуска, пусто — лишнее слово",
    )

    class Meta:
        verbose_name = "вариант ответа"
        verbose_name_plural = "варианты ответа"
        ordering = ["question", "id"]

    def __str__(self):
        return self.text


class AssignmentStatus(models.TextChoices):
    ASSIGNED = "assigned", "Назначен"
    IN_PROGRESS = "in_progress", "В процессе"
    COMPLETED = "completed", "Завершён"
    FAILED = "failed", "Не сдан"


class CourseAssignment(models.Model):
    """Курс у конкретного сотрудника: назначен HR / руководителем или выбран самим из каталога."""

    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="assignments")
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="course_assignments")
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=AssignmentStatus.choices, default=AssignmentStatus.ASSIGNED)
    progress_pct = models.PositiveIntegerField(default=0)
    score = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "назначение курса"
        verbose_name_plural = "назначения курсов"
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["course", "employee"], name="uniq_course_employee")]

    def __str__(self):
        return f"{self.employee} — {self.course}"


class LessonProgress(models.Model):
    assignment = models.ForeignKey(CourseAssignment, on_delete=models.CASCADE, related_name="lesson_progress")
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name="+")
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["assignment", "lesson"], name="uniq_lesson_progress")]


class QuizAttempt(models.Model):
    assignment = models.ForeignKey(CourseAssignment, on_delete=models.CASCADE, related_name="attempts")
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="attempts")
    answers = models.JSONField()
    details = models.JSONField(help_text="результат по каждому вопросу")
    score = models.PositiveIntegerField()
    passed = models.BooleanField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "попытка теста"
        verbose_name_plural = "попытки теста"
        ordering = ["created_at", "id"]
