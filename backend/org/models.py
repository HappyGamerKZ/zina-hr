"""Кадровые данные. Источник истины — 1С:ЗУП; здесь read-only копия.

Пользователь не меняет эти данные через API: их обновляет только
синхронизация через integrations.HRISProvider (сейчас mock).
"""
from django.db import models


class Company(models.Model):
    name_ru = models.CharField(max_length=200)
    name_kk = models.CharField(max_length=200, blank=True)
    external_id = models.CharField(max_length=64, unique=True)

    class Meta:
        verbose_name = "компания"
        verbose_name_plural = "компании"

    def __str__(self):
        return self.name_ru


class Department(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="departments")
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL)
    name_ru = models.CharField(max_length=200)
    name_kk = models.CharField(max_length=200, blank=True)
    external_id = models.CharField(max_length=64, unique=True)

    class Meta:
        verbose_name = "подразделение"
        verbose_name_plural = "подразделения"

    def __str__(self):
        return self.name_ru


class Position(models.Model):
    title_ru = models.CharField(max_length=200)
    title_kk = models.CharField(max_length=200, blank=True)
    external_id = models.CharField(max_length=64, unique=True)

    class Meta:
        verbose_name = "должность"
        verbose_name_plural = "должности"

    def __str__(self):
        return self.title_ru


class Employee(models.Model):
    full_name = models.CharField(max_length=200)
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="employees")
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="employees")
    position = models.ForeignKey(Position, on_delete=models.PROTECT, related_name="employees")
    manager = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="reports"
    )
    hire_date = models.DateField()
    email = models.EmailField(blank=True)
    external_id = models.CharField("табельный номер в 1С:ЗУП", max_length=64, unique=True)
    dismissed_on = models.DateField("дата увольнения", null=True, blank=True)
    source = models.CharField(max_length=32, default="mock_zup")
    synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "сотрудник"
        verbose_name_plural = "сотрудники"
        ordering = ["full_name"]

    def __str__(self):
        return self.full_name


class Delegation(models.Model):
    """Исполняющий обязанности руководителя на время отпуска или командировки.

    Пока замещение действует, заявки команды на шаге руководителя согласует И.О.
    И.О. — сотрудник из команды руководителя (прямой подчинённый) или из того же подразделения.
    """

    manager = models.ForeignKey(Employee, verbose_name="руководитель", on_delete=models.CASCADE, related_name="delegations")
    deputy = models.ForeignKey(Employee, verbose_name="исполняющий обязанности", on_delete=models.CASCADE,
                               related_name="acting_for")
    date_from = models.DateField("с")
    date_to = models.DateField("по")
    created_by = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField("отменено", null=True, blank=True)

    class Meta:
        verbose_name = "замещение руководителя"
        verbose_name_plural = "замещения руководителей"
        ordering = ["-date_from"]

    def __str__(self):
        return f"{self.deputy} за {self.manager}: {self.date_from:%d.%m}–{self.date_to:%d.%m.%Y}"


class LeaveBalance(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="leave_balances")
    leave_type = models.CharField(max_length=32, default="annual")
    days_total = models.PositiveIntegerField()
    days_used = models.PositiveIntegerField(default=0)
    as_of = models.DateField()
    synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "остаток отпуска"
        verbose_name_plural = "остатки отпуска"
        constraints = [
            models.UniqueConstraint(fields=["employee", "leave_type"], name="uniq_leave_balance")
        ]

    def __str__(self):
        return f"{self.employee}: {self.days_total - self.days_used} дн."
