from django.conf import settings
from django.db import models

from org.models import Employee


class RequestType(models.TextChoices):
    VACATION = "vacation", "Отпуск"
    ADVANCE = "advance", "Аванс"


class Status(models.TextChoices):
    DRAFT = "draft", "Черновик"
    WAITING_MANAGER_APPROVAL = "waiting_manager_approval", "На согласовании у руководителя"
    WAITING_HR_APPROVAL = "waiting_hr_approval", "В обработке HR"
    APPROVED_SENT_TO_1C = "approved_sent_to_1c", "Утверждено / Передано в 1С"
    REJECTED = "rejected", "Отклонено"
    CANCELLED = "cancelled", "Отменено"


# Заявки на отпуск в этих статусах «резервируют» дни из остатка.
# После утверждения дни списываются в LeaveBalance.days_used (mock проводки в 1С:ЗУП).
RESERVING_STATUSES = [Status.WAITING_MANAGER_APPROVAL, Status.WAITING_HR_APPROVAL]


class VacationType(models.TextChoices):
    ANNUAL = "annual", "Ежегодный оплачиваемый"
    UNPAID = "unpaid", "Без сохранения заработной платы"


class HrRequest(models.Model):
    type = models.CharField(max_length=16, choices=RequestType.choices)
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="hr_requests")
    status = models.CharField(
        max_length=32, choices=Status.choices, default=Status.WAITING_MANAGER_APPROVAL
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # Заполняются интеграциями после утверждения (сейчас mock).
    external_doc_id = models.CharField("id документа в Documentolog", max_length=64, blank=True)
    external_zup_id = models.CharField("id документа в 1С:ЗУП", max_length=64, blank=True)
    external_accounting_id = models.CharField("№ в бухгалтерии", max_length=64, blank=True)

    class Meta:
        verbose_name = "заявка"
        verbose_name_plural = "заявки"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["employee", "status"])]

    @property
    def number(self) -> str:
        return f"ZR-{self.created_at:%Y}-{self.pk:04d}"

    def __str__(self):
        return f"{self.number} {self.get_type_display()} — {self.employee}"


class VacationDetails(models.Model):
    request = models.OneToOneField(HrRequest, on_delete=models.CASCADE, related_name="vacation")
    date_from = models.DateField()
    date_to = models.DateField()
    days = models.PositiveIntegerField()
    vacation_type = models.CharField(
        max_length=16, choices=VacationType.choices, default=VacationType.ANNUAL
    )
    comment = models.TextField(blank=True)


class AdvanceDetails(models.Model):
    request = models.OneToOneField(HrRequest, on_delete=models.CASCADE, related_name="advance")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.TextField(blank=True)
    pay_date = models.DateField(null=True, blank=True)


class RequestEvent(models.Model):
    """История заявки: каждый переход статуса."""

    request = models.ForeignKey(HrRequest, on_delete=models.CASCADE, related_name="events")
    from_status = models.CharField(max_length=32, choices=Status.choices, blank=True)
    to_status = models.CharField(max_length=32, choices=Status.choices)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
