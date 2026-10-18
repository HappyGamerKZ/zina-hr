from datetime import timedelta

from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import IsManagerOrHR
from hr_requests.models import HrRequest
from hr_requests.serializers import HrRequestListSerializer
from hr_requests.views import approvals_queryset
from notifications.models import Notification
from notifications.serializers import NotificationSerializer
from org import delegation
from org.models import Delegation
from org.scopes import team_members, visible_employees
from org.serializers import (
    DelegationInputSerializer,
    DelegationSerializer,
    ManagerSerializer,
    ProfileSerializer,
    TeamMemberSerializer,
)

PROFILE_RELATED = ("company", "department", "position", "manager__position")


def _own_employee(user):
    if user.employee_id is None:
        raise NotFound("Учётная запись не связана с сотрудником")
    return get_object_or_404(visible_employees(user).select_related(*PROFILE_RELATED), pk=user.employee_id)


class ProfileView(APIView):
    @extend_schema(responses=ProfileSerializer)
    def get(self, request):
        return Response(ProfileSerializer(_own_employee(request.user), context={"request": request}).data)


class DashboardView(APIView):
    """Главная одним запросом: профиль, быстрые сервисы, заявки, обучение, уведомления."""

    def get(self, request):
        user = request.user
        employee = _own_employee(user)
        my_requests = HrRequest.objects.filter(employee=employee).select_related(
            "employee", "vacation", "advance"
        )[:5]
        notifications = Notification.objects.filter(user=user)
        profile = ProfileSerializer(employee, context={"request": request}).data
        # незавершённые курсы — первыми
        courses = sorted(profile["learning"], key=lambda a: a["status"] in ("completed", "failed"))
        return Response({
            "profile": profile,
            "quick_services": [
                {"key": "vacation", "link": "/requests/new?type=vacation"},
                {"key": "advance", "link": "/requests/new?type=advance"},
                {"key": "ai", "link": "/ai"},
                {"key": "academy", "link": "/academy"},
            ],
            "recent_requests": HrRequestListSerializer(my_requests, many=True).data,
            "approvals_count": approvals_queryset(user, HrRequest.objects.all()).count(),
            "courses": courses[:4],
            "notifications": NotificationSerializer(notifications[:5], many=True).data,
            "unread_notifications": notifications.filter(is_read=False).count(),
        })


class TeamView(APIView):
    permission_classes = [IsManagerOrHR]

    @extend_schema(responses=TeamMemberSerializer(many=True))
    def get(self, request):
        members = team_members(request.user).select_related("department", "position")
        return Response(TeamMemberSerializer(members, many=True).data)


class TeamMemberView(APIView):
    permission_classes = [IsManagerOrHR]

    @extend_schema(responses=ProfileSerializer)
    def get(self, request, employee_id: int):
        # Чужой сотрудник не попадает в выборку → 404, а не 403.
        emp = get_object_or_404(
            team_members(request.user).select_related(*PROFILE_RELATED), pk=employee_id
        )
        return Response(ProfileSerializer(emp, context={"request": request}).data)


class DelegationsView(APIView):
    """Замещение: мои назначения И.О. (как руководитель), за кого я И.О., кого можно назначить."""

    @extend_schema(responses=inline_serializer("Delegations", {
        "can_delegate": serializers.BooleanField(),
        "candidates": ManagerSerializer(many=True),
        "delegations": DelegationSerializer(many=True),
        "acting_for": DelegationSerializer(many=True),
    }))
    def get(self, request):
        employee = request.user.employee
        today = timezone.localdate()
        ctx = {"today": today}
        if employee is None:
            return Response({"can_delegate": False, "candidates": [], "delegations": [], "acting_for": []})
        recent = Q(date_to__gte=today - timedelta(days=30))
        mine = Delegation.objects.filter(recent, manager=employee).select_related("manager__position", "deputy__position")
        acting = (Delegation.objects.filter(deputy=employee, revoked_at__isnull=True, date_to__gte=today)
                  .select_related("manager__position", "deputy__position"))
        can = delegation.can_delegate(employee)
        return Response({
            "can_delegate": can,
            "candidates": ManagerSerializer(delegation.candidates(employee) if can else [], many=True).data,
            "delegations": DelegationSerializer(mine, many=True, context=ctx).data,
            "acting_for": DelegationSerializer(acting, many=True, context=ctx).data,
        })

    @extend_schema(request=DelegationInputSerializer, responses={201: DelegationSerializer})
    def post(self, request):
        data = DelegationInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        d = delegation.create(request.user, **data.validated_data)
        return Response(DelegationSerializer(d, context={"today": timezone.localdate()}).data, status=201)


class DelegationRevokeView(APIView):
    @extend_schema(request=None, responses=DelegationSerializer)
    def post(self, request, delegation_id: int):
        d = get_object_or_404(Delegation, pk=delegation_id, manager_id=request.user.employee_id)
        d = delegation.revoke(request.user, d)
        return Response(DelegationSerializer(d, context={"today": timezone.localdate()}).data)
