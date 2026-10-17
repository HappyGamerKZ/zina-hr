from django.contrib import admin

from academy.models import (
    Course,
    CourseAssignment,
    CourseModule,
    Lesson,
    Option,
    Question,
    Quiz,
    QuizAttempt,
)

# Контент курсов редактирует HR в Django Admin: курс → модули → уроки → тест → вопросы → варианты.


class ModuleInline(admin.TabularInline):
    model = CourseModule
    extra = 0
    show_change_link = True


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("title_ru", "duration_min", "is_published")
    list_filter = ("is_published",)
    inlines = [ModuleInline]


class LessonInline(admin.StackedInline):
    model = Lesson
    extra = 0
    show_change_link = True
    fields = ("order", "title", "type", "duration_min", "content", "media_url")


@admin.register(CourseModule)
class CourseModuleAdmin(admin.ModelAdmin):
    list_display = ("title", "course", "order")
    list_filter = ("course",)
    inlines = [LessonInline]


class QuizInline(admin.StackedInline):
    model = Quiz
    extra = 0
    show_change_link = True


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ("title", "module", "type", "order")
    list_filter = ("type", "module__course")
    inlines = [QuizInline]


class QuestionInline(admin.StackedInline):
    model = Question
    extra = 0
    show_change_link = True
    fields = ("order", "type", "text", "points", "explanation")


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ("lesson", "pass_score", "max_attempts")
    inlines = [QuestionInline]


class OptionInline(admin.TabularInline):
    model = Option
    extra = 2


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("text", "type", "quiz", "order")
    list_filter = ("type", "quiz")
    inlines = [OptionInline]


@admin.register(CourseAssignment)
class CourseAssignmentAdmin(admin.ModelAdmin):
    list_display = ("employee", "course", "status", "progress_pct", "score", "due_date")
    list_filter = ("status", "course")
    search_fields = ("employee__full_name",)


@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = ("assignment", "quiz", "score", "passed", "created_at")
    list_filter = ("passed", "quiz")
    readonly_fields = ("assignment", "quiz", "answers", "details", "score", "passed", "created_at")
