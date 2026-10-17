from django.db import models
from django.utils import timezone


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


class SyncRun(models.Model):
    """Журнал синхронизаций кадровых данных из 1С:ЗУП."""

    class RunStatus(models.TextChoices):
        OK = "ok", "Успешно"
        FAILED = "failed", "Ошибка"

    provider = models.CharField("источник", max_length=32)
    trigger = models.CharField("запуск", max_length=16, default="manual")  # startup | manual | admin
    status = models.CharField("статус", max_length=16, choices=RunStatus.choices)
    stats = models.JSONField("изменения", default=dict, blank=True)
    error = models.TextField("ошибка", blank=True)
    started_at = models.DateTimeField("начало", auto_now_add=True)
    finished_at = models.DateTimeField("окончание", null=True, blank=True)

    class Meta:
        verbose_name = "синхронизация с 1С:ЗУП"
        verbose_name_plural = "синхронизации с 1С:ЗУП"
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.started_at:%d.%m %H:%M} {self.get_status_display()}"


class OutboxTask(models.Model):
    """Очередь отправок во внешние системы (паттерн outbox).

    Задача создаётся в той же транзакции, что и утверждение заявки, поэтому не теряется.
    Отправляет её worker (manage.py run_worker) с повторами; сбой внешней системы не ломает утверждение.
    """

    class Target(models.TextChoices):
        ACCOUNTING = "accounting", "1С / бухгалтерия"
        ZUP = "zup", "1С:ЗУП"
        DOCUMENTOLOG = "documentolog", "Documentolog"

    class TaskStatus(models.TextChoices):
        PENDING = "pending", "В очереди"
        SENT = "sent", "Отправлено"
        FAILED = "failed", "Ошибка (попытки закончились)"

    request = models.ForeignKey(
        "hr_requests.HrRequest", verbose_name="заявка", on_delete=models.CASCADE, related_name="outbox_tasks"
    )
    target = models.CharField("система", max_length=16, choices=Target.choices)
    status = models.CharField("статус", max_length=16, choices=TaskStatus.choices, default=TaskStatus.PENDING)
    attempts = models.PositiveIntegerField("попыток", default=0)
    next_attempt_at = models.DateTimeField("следующая попытка", default=timezone.now)
    last_error = models.TextField("последняя ошибка", blank=True)
    external_id = models.CharField("номер во внешней системе", max_length=64, blank=True)
    created_at = models.DateTimeField("создано", auto_now_add=True)
    sent_at = models.DateTimeField("отправлено", null=True, blank=True)

    class Meta:
        verbose_name = "отправка во внешнюю систему"
        verbose_name_plural = "очередь отправок (outbox)"
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["request", "target"], name="uniq_outbox_request_target")]
        indexes = [models.Index(fields=["status", "next_attempt_at"])]

    def __str__(self):
        return f"{self.get_target_display()}: {self.request}"
