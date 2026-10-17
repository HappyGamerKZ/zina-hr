from django.contrib import admin, messages
from django.shortcuts import redirect
from django.urls import reverse
from unfold.admin import ModelAdmin
from unfold.decorators import action

from integrations import outbox
from integrations.models import AccountingExport, OutboxTask, SyncRun
from integrations.zup_sync import sync_from_zup


@admin.register(AccountingExport)
class AccountingExportAdmin(ModelAdmin):
    list_display = ("created_at", "request", "provider", "status", "external_id")
    list_filter = ("status", "provider")
    readonly_fields = ("request", "provider", "payload", "status", "external_id", "error", "created_at")


@admin.register(SyncRun)
class SyncRunAdmin(ModelAdmin):
    """Журнал синхронизаций с 1С:ЗУП + кнопка «Синхронизировать сейчас»."""

    list_display = ("started_at", "trigger", "provider", "status", "stats", "error")
    list_filter = ("status", "trigger")
    readonly_fields = ("provider", "trigger", "status", "stats", "error", "started_at", "finished_at")
    actions_list = ["sync_now"]

    def has_add_permission(self, request):
        return False

    @action(description="Синхронизировать с 1С:ЗУП сейчас", url_path="sync-now", icon="sync")
    def sync_now(self, request):
        run = sync_from_zup(trigger="admin")
        if run.status == SyncRun.RunStatus.OK:
            messages.success(request, f"Синхронизация выполнена: {run.stats}")
        else:
            messages.error(request, f"Синхронизация не выполнена: {run.error}")
        return redirect(reverse("admin:integrations_syncrun_changelist"))


@admin.register(OutboxTask)
class OutboxTaskAdmin(ModelAdmin):
    """Очередь отправок в 1С и Documentolog: что ушло, что ждёт повтора, где ошибка."""

    list_display = ("request", "target", "status", "attempts", "next_attempt_at", "external_id", "short_error")
    list_filter = ("status", "target")
    search_fields = ("request__employee__full_name", "external_id")
    readonly_fields = (
        "request", "target", "status", "attempts", "next_attempt_at", "last_error", "external_id",
        "created_at", "sent_at",
    )
    actions = ["retry_selected"]
    actions_row = ["retry_row"]

    def has_add_permission(self, request):
        return False

    @admin.display(description="ошибка")
    def short_error(self, obj):
        return obj.last_error[:80]

    @admin.action(description="Отправить повторно сейчас")
    def retry_selected(self, request, queryset):
        ids = list(queryset.values_list("id", flat=True))
        count = outbox.retry_now(queryset)
        outbox.dispatch(ids)
        messages.success(request, f"Поставлено на повторную отправку: {count}")

    @action(description="Отправить повторно", url_path="retry", icon="refresh")
    def retry_row(self, request, object_id):
        tasks = OutboxTask.objects.filter(pk=object_id)
        outbox.retry_now(tasks)
        outbox.dispatch([int(object_id)])
        task = tasks.first()
        level = messages.SUCCESS if task.status == OutboxTask.TaskStatus.SENT else messages.WARNING
        messages.add_message(request, level, f"{task}: {task.get_status_display()} {task.last_error}")
        return redirect(reverse("admin:integrations_outboxtask_changelist"))
