from django.db import models


class AccountingExport(models.Model):
    """Журнал передачи утверждённых заявок в бухгалтерию."""

    class ExportStatus(models.TextChoices):
        SENT = "sent", "Передано"
        FAILED = "failed", "Ошибка"

    request = models.ForeignKey(
        "hr_requests.HrRequest", on_delete=models.CASCADE, related_name="accounting_exports"
    )
    provider = models.CharField(max_length=32)
    payload = models.JSONField()
    status = models.CharField(max_length=16, choices=ExportStatus.choices)
    external_id = models.CharField("№ в бухгалтерии", max_length=64, blank=True)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "передача в бухгалтерию"
        verbose_name_plural = "передачи в бухгалтерию"
        ordering = ["-created_at"]
