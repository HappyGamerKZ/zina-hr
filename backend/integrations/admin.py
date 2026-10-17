from django.contrib import admin
from unfold.admin import ModelAdmin

from integrations.models import AccountingExport


@admin.register(AccountingExport)
class AccountingExportAdmin(ModelAdmin):
    list_display = ("created_at", "request", "provider", "status", "external_id")
    list_filter = ("status", "provider")
    readonly_fields = ("request", "provider", "payload", "status", "external_id", "error", "created_at")
