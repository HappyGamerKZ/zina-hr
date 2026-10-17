from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from org.models import Company, Department, Employee, LeaveBalance, Position

admin.site.register(Company, ModelAdmin)
admin.site.register(Department, ModelAdmin)
admin.site.register(Position, ModelAdmin)


class LeaveBalanceInline(TabularInline):
    model = LeaveBalance
    extra = 0


@admin.register(Employee)
class EmployeeAdmin(ModelAdmin):
    list_display = ("full_name", "position", "department", "manager", "hire_date", "source")
    list_filter = ("department", "source")
    search_fields = ("full_name", "external_id")
    inlines = [LeaveBalanceInline]
