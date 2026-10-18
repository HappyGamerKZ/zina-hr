from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from accounts.models import Role
from assistant import services
from assistant.llm import AssistantUnavailable
from assistant.models import AssistantQuestion


class AskInput(serializers.Serializer):
    question = serializers.CharField(max_length=1000)
    history = serializers.ListField(child=serializers.DictField(), required=False, default=list, max_length=10)


class EscalateInput(serializers.Serializer):
    question = serializers.CharField(max_length=1000)
    ai_answer = serializers.CharField(max_length=4000, required=False, allow_blank=True, default="")


class AnswerInput(serializers.Serializer):
    answer = serializers.CharField(max_length=4000)


class QuestionSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()
    answered_by = serializers.SerializerMethodField()

    class Meta:
        model = AssistantQuestion
        fields = ["id", "author", "question", "ai_answer", "lang", "status", "hr_answer", "answered_by",
                  "answered_at", "created_at"]

    def _name(self, user) -> str | None:
        if user is None:
            return None
        return user.employee.full_name if user.employee else user.username

    def get_author(self, q) -> str | None:
        return self._name(q.user)

    def get_answered_by(self, q) -> str | None:
        return self._name(q.answered_by)


AnswerSchema = inline_serializer("AiAnswer", {
    "answer": serializers.CharField(),
    "lang": serializers.CharField(),
    "found": serializers.BooleanField(),
    "can_escalate": serializers.BooleanField(),
    "sources": inline_serializer("AiSource", {"id": serializers.CharField(), "title": serializers.CharField()},
                                 many=True),
    "draft": serializers.DictField(allow_null=True),
})


class AskView(APIView):
    """Вопрос AI Jana. Роль и личные данные берутся из сессии, а не из запроса."""

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "ai"

    @extend_schema(request=AskInput, responses={200: AnswerSchema, 503: None})
    def post(self, request):
        data = AskInput(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            answer = services.ask(request.user, data.validated_data["question"], data.validated_data["history"])
        except AssistantUnavailable:
            return Response(
                {"error": {"code": "AI_UNAVAILABLE",
                           "message": "AI Jana сейчас недоступна. Попробуйте позже или передайте вопрос в HR."},
                 "can_escalate": True},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response(answer.__dict__)


class EscalateView(APIView):
    """«Передать в HR»: вопрос без надёжного ответа уходит HR, ответ придёт в уведомлениях."""

    @extend_schema(request=EscalateInput, responses={201: QuestionSerializer})
    def post(self, request):
        data = EscalateInput(data=request.data)
        data.is_valid(raise_exception=True)
        q = services.escalate(request.user, data.validated_data["question"], data.validated_data["ai_answer"])
        return Response(QuestionSerializer(q).data, status=status.HTTP_201_CREATED)


class QuestionsView(APIView):
    """HR — все вопросы из AI Jana (сначала открытые); остальные — только свои."""

    @extend_schema(responses=QuestionSerializer(many=True))
    def get(self, request):
        qs = AssistantQuestion.objects.select_related("user__employee", "answered_by__employee").order_by(
            "-status", "-created_at"  # open > answered по алфавиту
        )
        if request.user.role != Role.HR_ADMIN:
            qs = qs.filter(user=request.user)
        return Response(QuestionSerializer(qs[:100], many=True).data)


class AnswerView(APIView):
    @extend_schema(request=AnswerInput, responses=QuestionSerializer)
    def post(self, request, question_id: int):
        if request.user.role != Role.HR_ADMIN:
            raise PermissionDenied()
        q = AssistantQuestion.objects.filter(pk=question_id).first()
        if q is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        data = AnswerInput(data=request.data)
        data.is_valid(raise_exception=True)
        q = services.answer_question(request.user, q, data.validated_data["answer"])
        return Response(QuestionSerializer(q).data)
