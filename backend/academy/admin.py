from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from unfold.admin import ModelAdmin, StackedInline, TabularInline

from academy.models import (
    BlockType,
    Course,
    CourseAssignment,
    CourseModule,
    Lesson,
    LessonBlock,
    Option,
    Question,
    Quiz,
    QuizAttempt,
)

# Контент курсов редактирует HR в Django Admin (тема django-unfold):
# курс → модули → уроки (конструктор из блоков) → тест → вопросы → варианты.
# Порядок модулей, уроков, блоков и вопросов меняется перетаскиванием (ordering_field).


def edit_link(obj, label="Открыть"):
    if not obj or not obj.pk:
        return "—"
    url = reverse(f"admin:{obj._meta.app_label}_{obj._meta.model_name}_change", args=[obj.pk])
    return format_html('<a href="{}" class="text-primary-600 font-medium">{} →</a>', url, label)


# --- курс и модули ---

class ModuleInline(TabularInline):
    model = CourseModule
    extra = 0
    fields = ("order", "title", "lessons_link")
    readonly_fields = ("lessons_link",)
    ordering_field = "order"
    hide_ordering_field = True

    @admin.display(description="Уроки")
    def lessons_link(self, obj):
        return edit_link(obj, f"Уроки ({obj.lessons.count()})" if obj.pk else "Уроки")


@admin.register(Course)
class CourseAdmin(ModelAdmin):
    list_display = ("cover_emoji", "title_ru", "duration_min", "is_published", "assignments_count")
    list_display_links = ("title_ru",)
    list_filter = ("is_published",)
    search_fields = ("title_ru", "title_kk")
    fieldsets = (
        (None, {"fields": ("cover_emoji", "title_ru", "title_kk", "duration_min", "is_published")}),
        ("Описание для каталога", {"fields": ("description_ru", "description_kk")}),
    )
    inlines = [ModuleInline]

    @admin.display(description="Назначений")
    def assignments_count(self, obj):
        return obj.assignments.count()


class LessonInline(TabularInline):
    model = Lesson
    extra = 0
    fields = ("order", "title", "type", "duration_min", "builder_link")
    readonly_fields = ("builder_link",)
    ordering_field = "order"
    hide_ordering_field = True

    @admin.display(description="Содержимое")
    def builder_link(self, obj):
        return edit_link(obj, "Конструктор урока")


@admin.register(CourseModule)
class CourseModuleAdmin(ModelAdmin):
    list_display = ("title", "course", "order")
    list_filter = ("course",)
    inlines = [LessonInline]


# --- урок: конструктор из блоков ---

class LessonBlockInline(StackedInline):
    model = LessonBlock
    extra = 0
    fields = ("type", "text", "file", "url", "preview")
    readonly_fields = ("preview",)
    ordering_field = "order"
    hide_ordering_field = True
    verbose_name = "блок"
    verbose_name_plural = "Содержимое урока — добавляйте блоки и перетаскивайте их в нужном порядке"

    @admin.display(description="Предпросмотр")
    def preview(self, obj):
        if not obj or not obj.pk:
            return "Появится после сохранения"
        if obj.type == BlockType.IMAGE and obj.file:
            return format_html('<img src="{}" style="max-height:160px;border-radius:8px">', obj.file.url)
        if obj.file:
            return format_html('<a href="{}" target="_blank">{}</a>', obj.file.url, obj.file.name.rsplit("/", 1)[-1])
        if obj.url:
            return format_html('<a href="{}" target="_blank">{}</a>', obj.url, obj.url)
        return obj.text[:200]


class QuizInline(StackedInline):
    model = Quiz
    extra = 0
    fields = ("pass_score", "max_attempts", "questions_link")
    readonly_fields = ("questions_link",)

    @admin.display(description="Вопросы")
    def questions_link(self, obj):
        return edit_link(obj, f"Вопросы ({obj.questions.count()})" if obj.pk else "Вопросы")


@admin.register(Lesson)
class LessonAdmin(ModelAdmin):
    list_display = ("title", "module", "type", "order", "blocks_count")
    list_filter = ("type", "module__course")
    search_fields = ("title",)
    fields = ("module", "title", "type", "duration_min")
    inlines = [LessonBlockInline, QuizInline]
    warn_unsaved_form = True

    @admin.display(description="Блоков")
    def blocks_count(self, obj):
        return obj.blocks.count()


# --- тест, вопросы, варианты ---

class QuestionInline(StackedInline):
    model = Question
    extra = 0
    fields = ("type", "text", "points", "explanation", "options_link")
    readonly_fields = ("options_link",)
    ordering_field = "order"
    hide_ordering_field = True

    @admin.display(description="Варианты")
    def options_link(self, obj):
        return edit_link(obj, f"Варианты ответа ({obj.options.count()})" if obj.pk else "Варианты ответа")


@admin.register(Quiz)
class QuizAdmin(ModelAdmin):
    list_display = ("lesson", "pass_score", "max_attempts")
    inlines = [QuestionInline]


class OptionInline(TabularInline):
    model = Option
    extra = 2
    fields = ("text", "is_correct", "correct_position")


@admin.register(Question)
class QuestionAdmin(ModelAdmin):
    list_display = ("text", "type", "quiz", "order")
    list_filter = ("type", "quiz")
    fieldsets = (
        (None, {"fields": ("quiz", "order", "type", "text", "points", "explanation")}),
        ("Как отмечать правильный ответ", {
            "description": (
                "Один / несколько вариантов — галочка «верный вариант». "
                "Правильный порядок — «место / номер пропуска» = 1, 2, 3… "
                "Слова в пропуски — в тексте пишите {{1}}, {{2}}; у слова — номер пропуска, "
                "пусто — лишнее слово."
            ),
            "fields": (),
        }),
    )
    inlines = [OptionInline]


# --- прохождение ---

@admin.register(CourseAssignment)
class CourseAssignmentAdmin(ModelAdmin):
    list_display = ("employee", "course", "status", "progress_pct", "score", "best_score", "cycle", "due_date")
    list_filter = ("status", "course")
    search_fields = ("employee__full_name",)


@admin.register(QuizAttempt)
class QuizAttemptAdmin(ModelAdmin):
    list_display = ("assignment", "quiz", "cycle", "score", "passed", "created_at")
    list_filter = ("passed", "quiz")
    readonly_fields = ("assignment", "quiz", "cycle", "answers", "details", "score", "passed", "created_at")
