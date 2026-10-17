import secrets
from datetime import date, datetime, time, timedelta

from django.db.models import Count, Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from accounts.models import Role, User
from org.models import Department
from recruitment import services
from recruitment.models import Interview, Vacancy, VacancyStatus
from recruitment.serializers import (
    ActionInputSerializer,
    ApplicationInputSerializer,
    CandidateDetailSerializer,
    CandidateListSerializer,
    FeedbackInputSerializer,
    InterviewSerializer,
    PublicVacancySerializer,
    ScheduleInputSerializer,
    TrackInputSerializer,
    TrackSerializer,
    UpcomingInterviewSerializer,
    VacancyInputSerializer,
    VacancyWithCountsSerializer,
)


# --- публичная часть (без входа): страница входа → «Отправить резюме» ---

class PublicVacanciesView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(responses=PublicVacancySerializer(many=True))
    def get(self, request):
        vacancies = Vacancy.objects.filter(status=VacancyStatus.ACTIVE).select_related("department")
        return Response(PublicVacancySerializer(vacancies, many=True).data)


class PublicApplicationView(APIView):
    """Отправка резюме кандидатом. Без входа; не больше 5 отправок в час с одного IP."""

    authentication_classes = []
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "careers"

    @extend_schema(request=ApplicationInputSerializer, responses={201: inline_serializer("ApplicationCreated", {
        "status": serializers.CharField(), "number": serializers.CharField(),
    })})
    def post(self, request):
        data = ApplicationInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        if data.validated_data["website"]:  # заполнено скрытое поле — бот: делаем вид, что всё хорошо
            fake = f"CV-{secrets.randbelow(9000) + 1000}"
            return Response({"status": "ok", "number": fake}, status=status.HTTP_201_CREATED)
        candidate = services.submit_application(data.validated_data, data.validated_data.get("resume_pdf"))
        return Response({"status": "ok", "number": candidate.number}, status=status.HTTP_201_CREATED)


class PublicTrackView(APIView):
    """Кандидат смотрит этап своей заявки по номеру и почте. Без входа; не больше 20 запросов в час с IP."""

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "careers_track"

    @extend_schema(request=TrackInputSerializer, responses=TrackSerializer)
    def post(self, request):
        data = TrackInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        candidate = services.track_application(data.validated_data["number"], data.validated_data["email"])
        if candidate is None:
            raise NotFound("Заявка не найдена: проверьте номер и почту")
        return Response(TrackSerializer(candidate).data)


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
            qs = qs.prefetch_related("interviews")
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
        services.apply_action(
            request.user, candidate, data.validated_data["action"], data.validated_data["comment"],
            data.validated_data["close_vacancy"],
        )
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
        "upcoming_count": serializers.IntegerField(),
        "open_vacancies": serializers.IntegerField(required=False),
        "active_candidates": serializers.IntegerField(required=False),
        "pending_requests": serializers.IntegerField(required=False),
        "top_candidates": CandidateListSerializer(many=True, required=False),
    }))
    def get(self, request):
        if request.user.role not in (Role.HR_ADMIN, Role.MANAGER):
            raise PermissionDenied()
        data = services.summary(request.user)
        data["upcoming_interviews"] = UpcomingInterviewSerializer(data["upcoming_interviews"], many=True).data
        if "top_candidates" in data:
            data["top_candidates"] = CandidateListSerializer(data["top_candidates"], many=True).data
        return Response(data)


class HrOnlyMixin:
    def check_permissions(self, request):
        super().check_permissions(request)
        if not services.is_hr(request.user):
            raise PermissionDenied()


VACANCY_LIST_PARAMS = [OpenApiParameter("status", str), OpenApiParameter("q", str)]


def _vacancies():
    return Vacancy.objects.select_related("department").annotate(
        candidates_count=Count("candidates", distinct=True),
        active_candidates_count=Count("candidates", filter=Q(candidates__stage__in=services.PIPELINE), distinct=True),
    )


class RecruitmentVacanciesView(HrOnlyMixin, APIView):
    """Вакансии с числом кандидатов (фильтр в списке резюме, страница «Вакансии») и создание новой."""

    @extend_schema(parameters=VACANCY_LIST_PARAMS, responses=VacancyWithCountsSerializer(many=True))
    def get(self, request):
        vacancies = _vacancies()
        if value := request.query_params.get("status"):
            vacancies = vacancies.filter(status=value)
        if q := request.query_params.get("q"):
            vacancies = vacancies.filter(Q(title_ru__icontains=q) | Q(title_kk__icontains=q))
        return Response(VacancyWithCountsSerializer(vacancies, many=True).data)

    @extend_schema(request=VacancyInputSerializer, responses={201: VacancyWithCountsSerializer})
    def post(self, request):
        data = VacancyInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        vacancy = data.save(created_by=request.user)
        return Response(VacancyWithCountsSerializer(_vacancies().get(pk=vacancy.pk)).data, status=status.HTTP_201_CREATED)


class RecruitmentVacancyView(HrOnlyMixin, APIView):
    """Изменить вакансию: поля формы или статус (открыть, закрыть, вернуть в черновик)."""

    @extend_schema(request=VacancyInputSerializer, responses=VacancyWithCountsSerializer)
    def patch(self, request, vacancy_id: int):
        vacancy = get_object_or_404(Vacancy, pk=vacancy_id)
        data = VacancyInputSerializer(vacancy, data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        data.save()
        return Response(VacancyWithCountsSerializer(_vacancies().get(pk=vacancy.pk)).data)


class DepartmentsView(HrOnlyMixin, APIView):
    """Подразделения для формы вакансии."""

    @extend_schema(responses=inline_serializer("DepartmentOption", {
        "id": serializers.IntegerField(), "name": serializers.CharField(),
    }, many=True))
    def get(self, request):
        return Response([{"id": d.id, "name": d.name_ru} for d in Department.objects.order_by("name_ru")])


class InterviewersView(HrOnlyMixin, APIView):
    """Кого можно назначить интервьюером: HR и руководители."""

    @extend_schema(responses=inline_serializer("Interviewer", {
        "id": serializers.IntegerField(), "full_name": serializers.CharField(), "role": serializers.CharField(),
        "employee_id": serializers.IntegerField(allow_null=True),
    }, many=True))
    def get(self, request):
        users = User.objects.filter(role__in=[Role.HR_ADMIN, Role.MANAGER], is_active=True).select_related("employee")
        return Response([
            {"id": u.id, "full_name": u.employee.full_name if u.employee else u.username, "role": u.role,
             "employee_id": u.employee_id}
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


class InterviewCalendarView(APIView):
    """Интервью за период (по умолчанию — с сегодняшнего дня на 31 день): HR — все, руководитель — свои."""

    @extend_schema(parameters=[OpenApiParameter("from", str), OpenApiParameter("days", int)],
                   responses=UpcomingInterviewSerializer(many=True))
    def get(self, request):
        if request.user.role not in (Role.HR_ADMIN, Role.MANAGER):
            raise PermissionDenied()
        try:
            start = date.fromisoformat(request.query_params.get("from", "")) if request.query_params.get("from") \
                else timezone.localdate()
            days = min(max(int(request.query_params.get("days", 31)), 1), 92)
        except ValueError:
            raise ValidationError({"from": "Дата в формате ГГГГ-ММ-ДД, days — число"}) from None
        begin = timezone.make_aware(datetime.combine(start, time.min))
        interviews = (Interview.objects.exclude(status=Interview.InterviewStatus.CANCELLED)
                      .filter(scheduled_at__gte=begin, scheduled_at__lt=begin + timedelta(days=days))
                      .select_related("candidate__vacancy", "interviewer__employee"))
        if not services.is_hr(request.user):
            interviews = interviews.filter(interviewer=request.user)
        return Response(UpcomingInterviewSerializer(interviews, many=True).data)
