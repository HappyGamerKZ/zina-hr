from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from accounts.models import User


@admin.register(User)
class JanaUserAdmin(UserAdmin):
    list_display = ("username", "role", "employee", "is_active")
    list_filter = ("role", "is_active")
    fieldsets = UserAdmin.fieldsets + (("JanaМен", {"fields": ("role", "locale", "employee")}),)
