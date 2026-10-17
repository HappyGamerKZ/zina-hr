from django.core.validators import RegexValidator
from rest_framework import serializers

from recruitment import services
from recruitment.models import Candidate, CandidateEvent, Interview, Vacancy


def _user_name(user) -> str | None:
    if user is None:
        return None
    return user.employee.full_name if getattr(user, "employee", None) else user.username


# --- публичная форма ---

class PublicVacancySerializer(serializers.ModelSerializer):
    department = serializers.CharField(source="department.name_ru", default="")

    class Meta:
        model = Vacancy
        fields = ["id", "title_ru", "title_kk", "department", "description"]


class ApplicationInputSerializer(serializers.Serializer):
    vacancy_id = serializers.IntegerField()
    full_name = serializers.CharField(max_length=200)
    email = serializers.EmailField()
    phone = serializers.CharField(
        max_length=32, validators=[RegexValidator(r"^\+?[\d\s()-]{7,20}$", "Укажите телефон, например +7 701 123 45 67")]
    )
    social = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")
    profile_url = serializers.URLField(required=False, allow_blank=True, default="")
    resume_pdf = serializers.FileField(required=False, allow_null=True, default=None)
    expected_salary = serializers.IntegerField(required=False, allow_null=True, min_value=0, max_value=100_000_000)
    comment = serializers.CharField(max_length=2000, required=False, allow_blank=True, default="")
    consent = serializers.BooleanField()
    website = serializers.CharField(required=False, allow_blank=True, default="")  # ловушка для ботов, скрыта в форме

    def validate_consent(self, value):
        if not value:
            raise serializers.ValidationError("Нужно согласие на обработку персональных данных")
        return value


# --- раздел HR ---

class VacancyShortSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vacancy
        fields = ["id", "title_ru", "title_kk"]


class VacancyWithCountsSerializer(VacancyShortSerializer):
    candidates_count = serializers.IntegerField(read_only=True)

    class Meta(VacancyShortSerializer.Meta):
        fields = VacancyShortSerializer.Meta.fields + ["is_open", "candidates_count"]


class InterviewSerializer(serializers.ModelSerializer):
    interviewer = serializers.SerializerMethodField()

    class Meta:
        model = Interview
        fields = ["id", "kind", "scheduled_at", "duration_min", "interviewer", "location", "status", "feedback"]

    def get_interviewer(self, i) -> dict | None:
        return {"id": i.interviewer_id, "full_name": _user_name(i.interviewer)} if i.interviewer_id else None


class UpcomingInterviewSerializer(InterviewSerializer):
    candidate = serializers.SerializerMethodField()

    class Meta(InterviewSerializer.Meta):
        fields = InterviewSerializer.Meta.fields + ["candidate"]

    def get_candidate(self, i) -> dict:
        c = i.candidate
        return {"id": c.id, "full_name": c.full_name, "vacancy": VacancyShortSerializer(c.vacancy).data, "stage": c.stage}


class CandidateListSerializer(serializers.ModelSerializer):
    vacancy = VacancyShortSerializer(read_only=True)
    reviewed = serializers.SerializerMethodField()
    next_interview = serializers.SerializerMethodField()

    class Meta:
        model = Candidate
        fields = ["id", "full_name", "vacancy", "stage", "reviewed", "expected_salary", "created_at", "next_interview"]

    def get_reviewed(self, c) -> bool:
        return c.reviewed_at is not None

    def get_next_interview(self, c) -> dict | None:
        i = c.interviews.filter(status=Interview.InterviewStatus.SCHEDULED).order_by("scheduled_at").first()
        return {"kind": i.kind, "scheduled_at": i.scheduled_at} if i else None


class CandidateEventSerializer(serializers.ModelSerializer):
    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = CandidateEvent
        fields = ["id", "action", "stage", "actor_name", "comment", "created_at"]

    def get_actor_name(self, e) -> str | None:
        return _user_name(e.actor)


class CandidateDetailSerializer(CandidateListSerializer):
    resume_url = serializers.SerializerMethodField()
    steps = serializers.SerializerMethodField()
    allowed_actions = serializers.SerializerMethodField()
    interviews = InterviewSerializer(many=True, read_only=True)
    events = CandidateEventSerializer(many=True, read_only=True)

    class Meta(CandidateListSerializer.Meta):
        fields = CandidateListSerializer.Meta.fields + [
            "email", "phone", "social", "profile_url", "resume_url", "comment", "decision_stage",
            "steps", "allowed_actions", "interviews", "events",
        ]

    def get_resume_url(self, c) -> str | None:
        # PDF отдаётся только через API с проверкой прав, прямой ссылки на файл нет
        return f"/api/v1/recruitment/candidates/{c.id}/resume" if c.resume_pdf else None

    def get_steps(self, c) -> list[dict]:
        return services.steps(c)

    def get_allowed_actions(self, c) -> list[str]:
        return services.allowed_actions(self.context["request"].user, c)


class ActionInputSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=[services.REVIEW, services.NEXT, services.REJECT, services.HIRE])
    comment = serializers.CharField(required=False, allow_blank=True, default="")


class ScheduleInputSerializer(serializers.Serializer):
    scheduled_at = serializers.DateTimeField()
    duration_min = serializers.IntegerField(required=False, default=60, min_value=15, max_value=480)
    interviewer_id = serializers.IntegerField(required=False, allow_null=True, default=None)
    location = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")


class FeedbackInputSerializer(serializers.Serializer):
    feedback = serializers.CharField(max_length=4000)
