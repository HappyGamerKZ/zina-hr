from django.db.models import Q
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from accounts.models import Role
from hr_requests import services, state_machine
from hr_requests.models import HrRequest, Status
from hr_requests.serializers import (
    CommentSerializer,
    HrRequestCreateSerializer,
    HrRequestDetailSerializer,
    HrRequestListSerializer,
)
from org.scopes import visible_employees


def approvals_queryset(user, qs):
    """Заявки, которые ждут действия именно этого пользователя (зеркало state_machine)."""
    as_manager = Q(status=Status.WAITING_MANAGER_APPROVAL, employee__manager_id=user.employee_id)
    if user.role == Role.HR_ADMIN:
        return qs.filter(as_manager | Q(status=Status.WAITING_HR_APPROVAL)).exclude(
            employee_id=user.employee_id
        )
    if user.role == Role.MANAGER:
        return qs.filter(as_manager)
    return qs.none()


class HrRequestViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet
):
    """Заявки. Видимость ограничена сервером: свои, команды (руководитель), все (HR)."""

    def get_queryset(self):
        user = self.request.user
        qs = HrRequest.objects.filter(employee__in=visible_employees(user)).select_related(
            "employee", "vacation", "advance"
        )
        if self.action != "list":
            return qs.prefetch_related("events__actor__employee")

        scope = self.request.query_params.get("scope", "my")
        if scope == "team":
            if user.role not in (Role.MANAGER, Role.HR_ADMIN):
                raise PermissionDenied()
            qs = qs.exclude(employee_id=user.employee_id)
        elif scope == "approvals":
            qs = approvals_queryset(user, qs)
        elif scope == "all":
            if user.role != Role.HR_ADMIN:
                raise PermissionDenied()
        else:
            qs = qs.filter(employee_id=user.employee_id)

        if status_param := self.request.query_params.get("status"):
            qs = qs.filter(status=status_param)
        if type_param := self.request.query_params.get("type"):
            qs = qs.filter(type=type_param)
        return qs

    def get_serializer_class(self):
        if self.action == "list":
            return HrRequestListSerializer
        if self.action == "create":
            return HrRequestCreateSerializer
        # имена action во ViewSet совпадают с переходами state machine
        if self.action in state_machine.ALL_ACTIONS:
            return CommentSerializer
        return HrRequestDetailSerializer

    @extend_schema(
        parameters=[
            OpenApiParameter("scope", enum=["my", "team", "approvals", "all"]),
            OpenApiParameter("status", str),
            OpenApiParameter("type", enum=["vacation", "advance"]),
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(request=HrRequestCreateSerializer, responses={201: HrRequestDetailSerializer})
    def create(self, request, *args, **kwargs):
        data = HrRequestCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        req_type = data.validated_data["type"]
        req = services.create_request(
            request.user,
            req_type,
            data.validated_data[req_type],
            as_draft=data.validated_data["as_draft"],
        )
        req = self.get_queryset().get(pk=req.pk)
        return Response(
            HrRequestDetailSerializer(req, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    def _run(self, request, transition: str):
        req = self.get_object()  # 404, если заявка вне зоны видимости
        data = CommentSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        services.apply_transition(request.user, req, transition, data.validated_data["comment"])
        req = self.get_queryset().get(pk=req.pk)
        return Response(HrRequestDetailSerializer(req, context={"request": request}).data)

    @extend_schema(request=CommentSerializer, responses=HrRequestDetailSerializer)
    @action(detail=True, methods=["patch"], url_path="approve-manager")
    def approve_manager(self, request, pk=None):
        """Руководитель: «Одобрить». Сотрудник → HR, HR-специалист → сразу в 1С."""
        return self._run(request, state_machine.APPROVE_MANAGER)

    @extend_schema(request=CommentSerializer, responses=HrRequestDetailSerializer)
    @action(detail=True, methods=["patch"], url_path="approve-hr")
    def approve_hr(self, request, pk=None):
        """HR: «Оформить приказ» → утверждено и передано в 1С."""
        return self._run(request, state_machine.APPROVE_HR)

    @extend_schema(request=CommentSerializer, responses=HrRequestDetailSerializer)
    @action(detail=True, methods=["patch"])
    def reject(self, request, pk=None):
        return self._run(request, state_machine.REJECT)

    @extend_schema(request=CommentSerializer, responses=HrRequestDetailSerializer)
    @action(detail=True, methods=["patch"])
    def cancel(self, request, pk=None):
        return self._run(request, state_machine.CANCEL)

    @extend_schema(request=CommentSerializer, responses=HrRequestDetailSerializer)
    @action(detail=True, methods=["patch"])
    def submit(self, request, pk=None):
        """Отправить черновик (например, подготовленный AI Jana)."""
        return self._run(request, state_machine.SUBMIT)
