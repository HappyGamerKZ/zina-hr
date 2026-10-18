from django.contrib import admin
from django.db import transaction
from unfold.admin import ModelAdmin, TabularInline

from org.models import Company, Delegation, Department, Employee, LeaveBalance, Position

admin.site.register(Company, ModelAdmin)
admin.site.register(Department, ModelAdmin)
admin.site.register(Position, ModelAdmin)


def _resync():
    from hr_requests.routing import sync_pending

    transaction.on_commit(sync_pending)


class LeaveBalanceInline(TabularInline):
    model = LeaveBalance
    extra = 0


@admin.register(Employee)
class EmployeeAdmin(ModelAdmin):
    list_display = ("full_name", "position", "department", "manager", "hire_date", "dismissed_on", "source")
    list_filter = ("department", "source")
    search_fields = ("full_name", "external_id")
    inlines = [LeaveBalanceInline]

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if {"manager", "dismissed_on"} & set(form.changed_data):
            _resync()  # заявки, ждущие этого руководителя, перейдут к И.О. или вышестоящему


@admin.register(Delegation)
class DelegationAdmin(ModelAdmin):
    """HR может назначить И.О. за руководителя, если тот не успел (например, внезапный больничный)."""

    list_display = ("manager", "deputy", "date_from", "date_to", "revoked_at")
    list_filter = ("revoked_at",)
    search_fields = ("manager__full_name", "deputy__full_name")
    autocomplete_fields = ("manager", "deputy")
    readonly_fields = ("created_by", "created_at")

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
        _resync()
