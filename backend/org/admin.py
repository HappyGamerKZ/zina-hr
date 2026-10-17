from django.contrib import admin

from org.models import Company, Department, Employee, LeaveBalance, Position

admin.site.register(Company)
admin.site.register(Department)
admin.site.register(Position)


class LeaveBalanceInline(admin.TabularInline):
    model = LeaveBalance
    extra = 0


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ("full_name", "position", "department", "manager", "hire_date", "source")
    list_filter = ("department", "source")
    search_fields = ("full_name", "external_id")
    inlines = [LeaveBalanceInline]
