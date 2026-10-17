from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from academy import services
from academy.models import Course, CourseAssignment, Lesson, Quiz
from academy.serializers import (
    AssignInputSerializer,
    AssignmentDetailSerializer,
    AssignmentSerializer,
    AttemptInputSerializer,
    RestartInputSerializer,
    CourseDetailSerializer,
    CourseListSerializer,
    attempt_payload,
    lesson_payload,
)
from accounts.models import Role
from org.scopes import visible_employees


class CourseViewSet(viewsets.ReadOnlyModelViewSet):
    """Каталог курсов Jana Academy."""

    queryset = Course.objects.filter(is_published=True)

    def get_serializer_class(self):
        return CourseDetailSerializer if self.action == "retrieve" else CourseListSerializer

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        user = self.request.user
        ctx["my_assignments"] = {
            a.course_id: a for a in CourseAssignment.objects.filter(employee_id=user.employee_id)
        } if user.employee_id else {}
        return ctx

    @extend_schema(request=None, responses={201: AssignmentSerializer})
    @action(detail=True, methods=["post"])
    def enroll(self, request, pk=None):
        """Записаться на курс самому."""
        assignment = services.enroll(request.user, self.get_object())
        return Response(AssignmentSerializer(assignment, context={"request": request}).data, status=status.HTTP_201_CREATED)


class AssignmentViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Курсы сотрудников. Видимость: свои; руководитель — свои + команда; HR — все."""

    def get_queryset(self):
        user = self.request.user
        qs = CourseAssignment.objects.filter(employee__in=visible_employees(user)).select_related(
            "course", "employee", "assigned_by__employee"
        )
        if self.action != "list":
            return qs
        scope = self.request.query_params.get("scope", "my")
        if scope == "team":
            if user.role not in (Role.MANAGER, Role.HR_ADMIN):
                raise PermissionDenied()
            return qs.exclude(employee_id=user.employee_id)
        if scope == "all":
            if user.role != Role.HR_ADMIN:
                raise PermissionDenied()
            return qs
        return qs.filter(employee_id=user.employee_id)

    def get_serializer_class(self):
        return AssignmentDetailSerializer if self.action == "retrieve" else AssignmentSerializer

    @extend_schema(parameters=[OpenApiParameter("scope", enum=["my", "team", "all"])])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(request=AssignInputSerializer, responses={201: AssignmentSerializer(many=True)})
    def create(self, request):
        """Назначить курс: HR — любому сотруднику, руководитель — своим подчинённым."""
        data = AssignInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        course = get_object_or_404(Course, pk=data.validated_data["course_id"], is_published=True)
        created = services.assign(
            request.user, course, data.validated_data["employee_ids"], data.validated_data.get("due_date")
        )
        return Response(AssignmentSerializer(created, many=True, context={"request": request}).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=RestartInputSerializer, responses=AssignmentDetailSerializer)
    @action(detail=True, methods=["post"])
    def restart(self, request, pk=None):
        """Пройти курс заново (сотрудник — сданный курс) или назначить повторно (HR / руководитель)."""
        data = RestartInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        assignment = services.restart(request.user, self.get_object(), data.validated_data.get("due_date"))
        return Response(AssignmentDetailSerializer(assignment, context={"request": request}).data)

    def _own_lesson(self, request, lesson_id):
        assignment = self.get_object()  # 404 вне зоны видимости
        if assignment.employee_id != request.user.employee_id:
            raise PermissionDenied("Материалы курса доступны только самому сотруднику")
        lesson = get_object_or_404(
            Lesson.objects.select_related("module"), pk=lesson_id, module__course_id=assignment.course_id
        )
        return assignment, lesson

    @action(detail=True, methods=["get"], url_path=r"lessons/(?P<lesson_id>\d+)")
    def lesson(self, request, pk=None, lesson_id=None):
        """Материал урока; для теста — вопросы без правильных ответов."""
        assignment, lesson = self._own_lesson(request, lesson_id)
        if lesson.id in services.locked_lesson_ids(assignment):
            raise PermissionDenied("Сначала пройдите предыдущие уроки")
        return Response(lesson_payload(assignment, lesson))

    @extend_schema(request=None)
    @action(detail=True, methods=["post"], url_path=r"lessons/(?P<lesson_id>\d+)/complete")
    def complete_lesson(self, request, pk=None, lesson_id=None):
        assignment, lesson = self._own_lesson(request, lesson_id)
        assignment = services.complete_lesson(request.user, assignment, lesson)
        return Response(AssignmentDetailSerializer(assignment, context={"request": request}).data)

    @extend_schema(request=AttemptInputSerializer)
    @action(detail=True, methods=["post"], url_path=r"quizzes/(?P<quiz_id>\d+)/attempts")
    def attempt(self, request, pk=None, quiz_id=None):
        """Отправить ответы теста. Проверка — только на сервере."""
        assignment = self.get_object()
        quiz = get_object_or_404(
            Quiz.objects.select_related("lesson__module"), pk=quiz_id,
            lesson__module__course_id=assignment.course_id,
        )
        data = AttemptInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        attempt = services.submit_attempt(request.user, assignment, quiz, data.validated_data["answers"])
        return Response(attempt_payload(attempt), status=status.HTTP_201_CREATED)
