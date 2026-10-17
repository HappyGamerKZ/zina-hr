from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from recruitment.models import Candidate, CandidateEvent, Interview, Vacancy

# Вакансии ведёт HR здесь; работа с кандидатами — в разделе «Подбор» на сайте.


@admin.register(Vacancy)
class VacancyAdmin(ModelAdmin):
    list_display = ("title_ru", "department", "hiring_manager", "is_open", "candidates_count")
    list_filter = ("is_open", "department")
    search_fields = ("title_ru", "title_kk")

    @admin.display(description="кандидатов")
    def candidates_count(self, obj):
        return obj.candidates.count()


class InterviewInline(TabularInline):
    model = Interview
    extra = 0
    fields = ("kind", "scheduled_at", "interviewer", "status", "feedback")


class EventInline(TabularInline):
    model = CandidateEvent
    extra = 0
    can_delete = False
    readonly_fields = ("action", "stage", "actor", "comment", "created_at")


@admin.register(Candidate)
class CandidateAdmin(ModelAdmin):
    list_display = ("full_name", "vacancy", "stage", "expected_salary", "created_at")
    list_filter = ("stage", "vacancy")
    search_fields = ("full_name", "email", "phone")
    # этап меняется только через действия на сайте (история и уведомления), не вручную
    readonly_fields = ("stage", "reviewed_at", "decision_stage", "consent_at", "created_at", "updated_at")
    inlines = [InterviewInline, EventInline]
