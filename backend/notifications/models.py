from django.conf import settings
from django.db import models


class NotificationType(models.TextChoices):
    REQUEST_SUBMITTED = "request_submitted", "Новая заявка на согласование"
    REQUEST_STATUS_CHANGED = "request_status_changed", "Статус заявки изменён"
    COURSE_ASSIGNED = "course_assigned", "Назначен курс"
    COURSE_COMPLETED = "course_completed", "Курс завершён"
    COURSE_FAILED = "course_failed", "Курс не сдан"
    HR_TICKET_ANSWERED = "hr_ticket_answered", "HR ответил на вопрос"


class Notification(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    type = models.CharField(max_length=32, choices=NotificationType.choices)
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    link = models.CharField(max_length=200, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "уведомление"
        verbose_name_plural = "уведомления"
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["user", "is_read"])]
