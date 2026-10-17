from django.db.models import Count, Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from accounts.models import Role, User
from recruitment import services
from recruitment.models import Interview, Vacancy
from recruitment.serializers import (
    ActionInputSerializer,
    ApplicationInputSerializer,
    CandidateDetailSerializer,
    CandidateListSerializer,
    FeedbackInputSerializer,
    InterviewSerializer,
    PublicVacancySerializer,
    ScheduleInputSerializer,
    UpcomingInterviewSerializer,
    VacancyWithCountsSerializer,
)


# --- публичная часть (без входа): страница входа → «Отправить резюме» ---

class PublicVacanciesView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(responses=PublicVacancySerializer(many=True))
    def get(self, request):
        vacancies = Vacancy.objects.filter(is_open=True).select_related("department")
        return Response(PublicVacancySerializer(vacancies, many=True).data)


class PublicApplicationView(APIView):
    """Отправка резюме кандидатом. Без входа; не больше 5 отправок в час с одного IP."""

    authentication_classes = []
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "careers"

    @extend_schema(request=ApplicationInputSerializer, responses={201: None})
    def post(self, request):
        data = ApplicationInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        if data.validated_data["website"]:  # заполнено скрытое поле — бот: делаем вид, что всё хорошо
            return Response({"status": "ok"}, status=status.HTTP_201_CREATED)
        services.submit_application(data.validated_data, data.validated_data.get("resume_pdf"))
        return Response({"status": "ok"}, status=status.HTTP_201_CREATED)


# --- раздел HR / интервьюера ---

class CandidateViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Кандидаты. HR — все; руководитель — только те, у кого он интервьюер; сотрудник — 403."""

    def get_queryset(self):
        user = self.request.user
        if user.role not in (Role.HR_ADMIN, Role.MANAGER):
            raise PermissionDenied()
        qs = services.visible_candidates(user)
        if self.action == "list":
            params = self.request.query_params
            if vacancy := params.get("vacancy"):
                qs = qs.filter(vacancy_id=vacancy)
            if stage := params.get("stage"):
                qs = qs.filter(stage=stage)
            if q := params.get("q"):
                qs = qs.filter(Q(full_name__icontains=q) | Q(email__icontains=q) | Q(phone__icontains=q))
        else:
            qs = qs.prefetch_related("interviews__interviewer__employee", "events__actor__employee")
        return qs

    def get_serializer_class(self):
        return CandidateListSerializer if self.action == "list" else CandidateDetailSerializer

    @extend_schema(parameters=[
        OpenApiParameter("vacancy", int), OpenApiParameter("stage", str), OpenApiParameter("q", str),
    ])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def _detail(self, request, candidate):
        candidate = self.get_queryset().get(pk=candidate.pk)
        return Response(CandidateDetailSerializer(candidate, context={"request": request}).data)

    @extend_schema(request=ActionInputSerializer, responses=CandidateDetailSerializer)
    @action(detail=True, methods=["post"], url_path="actions")
    def take_action(self, request, pk=None):
        """«Ознакомлен» (review), «Следующий этап» (next), «Отклонить» (reject), «Нанять» (hire) — только HR."""
        candidate = self.get_object()
        data = ActionInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        services.apply_action(request.user, candidate, data.validated_data["action"], data.validated_data["comment"])
        return self._detail(request, candidate)

    @extend_schema(request=ScheduleInputSerializer, responses=CandidateDetailSerializer)
    @action(detail=True, methods=["post"])
    def interviews(self, request, pk=None):
        """Назначить или перенести интервью текущего этапа (только HR)."""
        candidate = self.get_object()
        data = ScheduleInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        interviewer = None
        if data.validated_data["interviewer_id"]:
            interviewer = get_object_or_404(User, pk=data.validated_data["interviewer_id"], is_active=True)
        services.schedule_interview(
            request.user, candidate, data.validated_data["scheduled_at"], data.validated_data["duration_min"],
            interviewer, data.validated_data["location"],
        )
        return self._detail(request, candidate)

    @extend_schema(responses={(200, "application/pdf"): bytes})
    @action(detail=True, methods=["get"])
    def resume(self, request, pk=None):
        """PDF резюме — только тем, кто видит кандидата."""
        candidate = self.get_object()
        if not candidate.resume_pdf:
            raise Http404
        response = FileResponse(
            candidate.resume_pdf.open("rb"), content_type="application/pdf",
            filename=f"resume-{candidate.pk}.pdf",
        )
        response["Content-Disposition"] = f'inline; filename="resume-{candidate.pk}.pdf"'
        response["X-Frame-Options"] = "SAMEORIGIN"  # можно показывать PDF во встроенном окне на сайте
        response["X-Content-Type-Options"] = "nosniff"
        response["Cache-Control"] = "private, no-store"
        return response


class RecruitmentSummaryView(APIView):
    """Дашборд: новые резюме, воронка по этапам (HR), ближайшие интервью (HR — все, руководитель — свои)."""

    @extend_schema(responses=inline_serializer("RecruitmentSummary", {
        "new_resumes": serializers.IntegerField(required=False),
        "by_stage": serializers.DictField(child=serializers.IntegerField(), required=False),
        "upcoming_interviews": UpcomingInterviewSerializer(many=True),
    }))
    def get(self, request):
        if request.user.role not in (Role.HR_ADMIN, Role.MANAGER):
            raise PermissionDenied()
        data = services.summary(request.user)
        data["upcoming_interviews"] = UpcomingInterviewSerializer(data["upcoming_interviews"], many=True).data
        return Response(data)


class HrOnlyMixin:
    def check_permissions(self, request):
        super().check_permissions(request)
        if not services.is_hr(request.user):
            raise PermissionDenied()


class RecruitmentVacanciesView(HrOnlyMixin, APIView):
    """Все вакансии с числом кандидатов — для фильтра в списке резюме."""

    @extend_schema(responses=VacancyWithCountsSerializer(many=True))
    def get(self, request):
        vacancies = Vacancy.objects.annotate(candidates_count=Count("candidates"))
        return Response(VacancyWithCountsSerializer(vacancies, many=True).data)


class InterviewersView(HrOnlyMixin, APIView):
    """Кого можно назначить интервьюером: HR и руководители."""

    @extend_schema(responses=inline_serializer("Interviewer", {
        "id": serializers.IntegerField(), "full_name": serializers.CharField(), "role": serializers.CharField(),
    }, many=True))
    def get(self, request):
        users = User.objects.filter(role__in=[Role.HR_ADMIN, Role.MANAGER], is_active=True).select_related("employee")
        return Response([
            {"id": u.id, "full_name": u.employee.full_name if u.employee else u.username, "role": u.role}
            for u in users.order_by("employee__full_name")
        ])


class InterviewFeedbackView(APIView):
    """Отзыв по итогам интервью — интервьюер или HR."""

    @extend_schema(request=FeedbackInputSerializer, responses=InterviewSerializer)
    def post(self, request, interview_id: int):
        interview = get_object_or_404(Interview.objects.select_related("candidate"), pk=interview_id)
        if not services.visible_candidates(request.user).filter(pk=interview.candidate_id).exists():
            raise Http404
        data = FeedbackInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        interview = services.leave_feedback(request.user, interview, data.validated_data["feedback"])
        return Response(InterviewSerializer(interview).data)
