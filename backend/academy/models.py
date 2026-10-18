"""Jana Academy: курс → модули → уроки (блоки: заголовки, текст, фото, видео, файлы; тест) → вопросы → варианты.

Типы вопросов и как хранится правильный ответ:
    single       — один верный вариант:            Option.is_correct
    multiple     — несколько верных вариантов:     Option.is_correct
    ordering     — расставить в правильном порядке: Option.correct_position = 1..N
    fill_blanks  — перетащить слова в пропуски текста: Question.text содержит {{1}}, {{2}}…,
                   Option.correct_position = номер пропуска, None = лишнее слово (дистрактор)

Правильные ответы (is_correct, correct_position) никогда не отдаются на фронт до проверки.
"""
import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models

from org.models import Employee


class CoverIcon(models.TextChoices):
    TRAINING = "training", "Обучение"
    POLICIES = "policies", "Правила и безопасность"
    ONBOARDING = "onboarding", "Адаптация"
    PERFORMANCE = "performance", "Развитие"
    COMPANY = "company", "Компания"
    PEOPLE = "people", "Команда и клиенты"
    DOCUMENTS = "documents", "Документы"
    CERTIFICATE = "certificate", "Сертификат"


class Course(models.Model):
    title_ru = models.CharField("название (рус.)", max_length=200)
    title_kk = models.CharField("название (каз.)", max_length=200, blank=True)
    description_ru = models.TextField("описание (рус.)", blank=True)
    description_kk = models.TextField("описание (каз.)", blank=True)
    cover_emoji = models.CharField("значок (эмодзи, устарело)", max_length=8, default="📘")
    # иконка из набора Jana HR (frontend/src/components/icons.ts)
    cover_icon = models.CharField("иконка", max_length=16, choices=CoverIcon.choices, default=CoverIcon.TRAINING)
    duration_min = models.PositiveIntegerField("длительность, мин", default=30)
    is_published = models.BooleanField("опубликован", default=True)
    created_at = models.DateTimeField("создан", auto_now_add=True)

    class Meta:
        verbose_name = "курс"
        verbose_name_plural = "курсы"
        ordering = ["id"]

    def __str__(self):
        return self.title_ru


class CourseModule(models.Model):
    course = models.ForeignKey(Course, verbose_name="курс", on_delete=models.CASCADE, related_name="modules")
    order = models.PositiveIntegerField("порядок", default=1)
    title = models.CharField("название", max_length=200)
    title_kk = models.CharField("название (каз.)", max_length=200, blank=True)

    class Meta:
        verbose_name = "модуль"
        verbose_name_plural = "модули"
        ordering = ["course", "order", "id"]

    def __str__(self):
        return f"{self.course} / {self.title}"


class LessonType(models.TextChoices):
    TEXT = "text", "Материал"  # содержимое собирается из блоков (LessonBlock)
    QUIZ = "quiz", "Тест"      # блоки — вступление, затем вопросы теста


class Lesson(models.Model):
    module = models.ForeignKey(CourseModule, verbose_name="модуль", on_delete=models.CASCADE, related_name="lessons")
    order = models.PositiveIntegerField("порядок", default=1)
    title = models.CharField("название", max_length=200)
    title_kk = models.CharField("название (каз.)", max_length=200, blank=True)
    type = models.CharField("тип урока", max_length=8, choices=LessonType.choices, default=LessonType.TEXT)
    duration_min = models.PositiveIntegerField("длительность, мин", default=5)

    class Meta:
        verbose_name = "урок"
        verbose_name_plural = "уроки"
        ordering = ["module__order", "order", "id"]

    def __str__(self):
        return f"{self.module} / {self.title}"


class BlockType(models.TextChoices):
    HEADING = "heading", "Заголовок"
    TEXT = "text", "Текст"
    NOTE = "note", "Важно (выделенный текст)"
    IMAGE = "image", "Изображение"
    VIDEO = "video", "Видео"
    FILE = "file", "Файл (PDF, презентация, документ)"


IMAGE_EXT = ["jpg", "jpeg", "png", "gif", "webp", "svg"]
VIDEO_EXT = ["mp4", "webm"]
FILE_EXT = ["pdf", "doc", "docx", "ppt", "pptx", "xls", "xlsx"]


class LessonBlock(models.Model):
    """Блок урока — как в конструкторе сайта: заголовки, текст, фото, видео и файлы в любом порядке."""

    lesson = models.ForeignKey(Lesson, verbose_name="урок", on_delete=models.CASCADE, related_name="blocks")
    order = models.PositiveIntegerField("порядок", default=0)
    type = models.CharField("тип блока", max_length=8, choices=BlockType.choices, default=BlockType.TEXT)
    text = models.TextField("текст / подпись", blank=True)
    text_kk = models.TextField("текст / подпись (каз.)", blank=True)
    file = models.FileField(
        "файл",
        upload_to="academy/%Y/%m/", blank=True,
        validators=[FileExtensionValidator(IMAGE_EXT + VIDEO_EXT + FILE_EXT)],
    )
    url = models.URLField("ссылка (YouTube или внешнее видео)", blank=True)

    class Meta:
        verbose_name = "блок урока"
        verbose_name_plural = "блоки урока"
        ordering = ["lesson", "order", "id"]

    def __str__(self):
        return f"{self.get_type_display()}: {(self.text or self.file.name or self.url)[:60]}"

    def clean(self):
        ext = self.file.name.rsplit(".", 1)[-1].lower() if self.file else ""
        if self.type in (BlockType.HEADING, BlockType.TEXT, BlockType.NOTE) and not self.text.strip():
            raise ValidationError({"text": "Заполните текст блока"})
        if self.type == BlockType.IMAGE and ext not in IMAGE_EXT:
            raise ValidationError({"file": f"Загрузите изображение: {', '.join(IMAGE_EXT)}"})
        if self.type == BlockType.VIDEO and not self.url and ext not in VIDEO_EXT:
            raise ValidationError({"file": "Загрузите видео (mp4, webm) или укажите ссылку"})
        if self.type == BlockType.FILE and ext not in FILE_EXT:
            raise ValidationError({"file": f"Загрузите файл: {', '.join(FILE_EXT)}"})


class Quiz(models.Model):
    lesson = models.OneToOneField(Lesson, verbose_name="урок", on_delete=models.CASCADE, related_name="quiz")
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
    quiz = models.ForeignKey(Quiz, verbose_name="тест", on_delete=models.CASCADE, related_name="questions")
    order = models.PositiveIntegerField("порядок", default=1)
    type = models.CharField("тип вопроса", max_length=16, choices=QuestionType.choices)
    text = models.TextField("текст вопроса", help_text="Для «слов в пропуски» пропуски обозначаются {{1}}, {{2}}, …")
    text_kk = models.TextField("текст вопроса (каз.)", blank=True, help_text="Те же пропуски {{1}}, {{2}}, что и в русском")
    points = models.PositiveIntegerField("баллы", default=1)
    explanation = models.TextField("пояснение после проверки", blank=True)
    explanation_kk = models.TextField("пояснение (каз.)", blank=True)

    class Meta:
        verbose_name = "вопрос"
        verbose_name_plural = "вопросы"
        ordering = ["quiz", "order", "id"]

    def __str__(self):
        return self.text[:80]

    def clean(self):
        # в казахской версии те же пропуски, что и в русской: ответы проверяются по номерам пропусков
        if self.type == QuestionType.FILL_BLANKS and self.text_kk:
            blanks = lambda s: sorted(re.findall(r"\{\{(\d+)\}\}", s))  # noqa: E731
            if blanks(self.text_kk) != blanks(self.text):
                raise ValidationError({"text_kk": "Пропуски {{N}} должны совпадать с русским текстом"})


class Option(models.Model):
    question = models.ForeignKey(Question, verbose_name="вопрос", on_delete=models.CASCADE, related_name="options")
    text = models.CharField("текст варианта", max_length=300)
    text_kk = models.CharField("текст варианта (каз.)", max_length=300, blank=True)
    is_correct = models.BooleanField("верный вариант", default=False, help_text="один / несколько вариантов")
    correct_position = models.PositiveIntegerField(
        "место / номер пропуска",
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

    course = models.ForeignKey(Course, verbose_name="курс", on_delete=models.CASCADE, related_name="assignments")
    employee = models.ForeignKey(Employee, verbose_name="сотрудник", on_delete=models.CASCADE, related_name="course_assignments")
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, verbose_name="назначил(а)", on_delete=models.SET_NULL, related_name="+"
    )
    due_date = models.DateField("срок", null=True, blank=True)
    status = models.CharField("статус", max_length=16, choices=AssignmentStatus.choices, default=AssignmentStatus.ASSIGNED)
    progress_pct = models.PositiveIntegerField("прогресс, %", default=0)
    score = models.PositiveIntegerField("результат текущего прохождения", null=True, blank=True)
    best_score = models.PositiveIntegerField("лучший результат за все прохождения", null=True, blank=True)
    # Номер прохождения: повторное прохождение / переназначение начинает новый цикл,
    # прогресс и попытки прошлых циклов остаются в истории.
    cycle = models.PositiveIntegerField("прохождение №", default=1)
    created_at = models.DateTimeField("назначен", auto_now_add=True)
    started_at = models.DateTimeField("начат", null=True, blank=True)
    completed_at = models.DateTimeField("завершён", null=True, blank=True)

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
    cycle = models.PositiveIntegerField(default=1)
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["assignment", "lesson", "cycle"], name="uniq_lesson_progress_cycle")
        ]


class QuizAttempt(models.Model):
    assignment = models.ForeignKey(CourseAssignment, verbose_name="назначение", on_delete=models.CASCADE, related_name="attempts")
    quiz = models.ForeignKey(Quiz, verbose_name="тест", on_delete=models.CASCADE, related_name="attempts")
    cycle = models.PositiveIntegerField("прохождение №", default=1)
    answers = models.JSONField("ответы", )
    details = models.JSONField("разбор", help_text="результат по каждому вопросу")
    score = models.PositiveIntegerField("результат, %", )
    passed = models.BooleanField("сдан", )
    created_at = models.DateTimeField("дата", auto_now_add=True)

    class Meta:
        verbose_name = "попытка теста"
        verbose_name_plural = "попытки теста"
        ordering = ["created_at", "id"]
