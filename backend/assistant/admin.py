from django.contrib import admin
from unfold.admin import ModelAdmin

from assistant.models import AssistantQuestion


@admin.register(AssistantQuestion)
class AssistantQuestionAdmin(ModelAdmin):
    list_display = ("question", "user", "status", "created_at", "answered_by")
    list_filter = ("status", "lang")
    search_fields = ("question", "hr_answer")
    readonly_fields = ("user", "question", "ai_answer", "lang", "created_at", "answered_by", "answered_at")
