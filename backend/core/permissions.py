from rest_framework.permissions import BasePermission

from accounts.models import Role


class IsManagerOrHR(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in (Role.MANAGER, Role.HR_ADMIN)


class IsHR(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == Role.HR_ADMIN
