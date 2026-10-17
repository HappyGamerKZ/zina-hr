from django.contrib import admin

from hr_requests.models import AdvanceDetails, HrRequest, RequestEvent, VacationDetails


class VacationInline(admin.StackedInline):
    model = VacationDetails
    extra = 0


class AdvanceInline(admin.StackedInline):
    model = AdvanceDetails
    extra = 0


class EventInline(admin.TabularInline):
    model = RequestEvent
    extra = 0
    readonly_fields = ("from_status", "to_status", "actor", "comment", "created_at")
    can_delete = False


@admin.register(HrRequest)
class HrRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "type", "employee", "status", "created_at")
    list_filter = ("type", "status")
    search_fields = ("employee__full_name",)
    # Статусы меняются только через API (state machine), не вручную.
    readonly_fields = ("status", "created_at", "updated_at")
    inlines = [VacationInline, AdvanceInline, EventInline]
