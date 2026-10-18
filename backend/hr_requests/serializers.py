from rest_framework import serializers

from hr_requests import routing, state_machine
from hr_requests.models import (
    AdvanceDetails,
    HrRequest,
    RequestEvent,
    RequestType,
    Status,
    VacationDetails,
    VacationType,
)


class VacationDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = VacationDetails
        fields = ["date_from", "date_to", "days", "vacation_type", "comment"]


class AdvanceDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdvanceDetails
        fields = ["amount", "reason", "pay_date"]


class RequestEventSerializer(serializers.ModelSerializer):
    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = RequestEvent
        fields = ["id", "from_status", "to_status", "actor_name", "comment", "created_at"]

    def get_actor_name(self, ev) -> str | None:
        if ev.actor is None:
            return None
        return ev.actor.employee.full_name if ev.actor.employee else ev.actor.username


class EmployeeShortSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    full_name = serializers.CharField()


class HrRequestListSerializer(serializers.ModelSerializer):
    number = serializers.CharField(read_only=True)
    employee = EmployeeShortSerializer(read_only=True)
    vacation = VacationDetailsSerializer(read_only=True)
    advance = AdvanceDetailsSerializer(read_only=True)

    class Meta:
        model = HrRequest
        fields = [
            "id", "number", "type", "status", "employee",
            "vacation", "advance", "created_at", "updated_at",
        ]


class HrRequestDetailSerializer(HrRequestListSerializer):
    events = RequestEventSerializer(many=True, read_only=True)
    allowed_actions = serializers.SerializerMethodField()
    approver = serializers.SerializerMethodField()

    class Meta(HrRequestListSerializer.Meta):
        fields = HrRequestListSerializer.Meta.fields + [
            "events", "allowed_actions", "external_doc_id", "external_zup_id", "external_accounting_id",
            "doc_status", "doc_registration_number", "approver",
        ]

    def get_allowed_actions(self, req) -> list[str]:
        return state_machine.allowed_actions(self.context["request"].user, req)

    def get_approver(self, req) -> dict | None:
        """Кто сейчас согласует шаг руководителя (только пока заявка на этом шаге)."""
        if req.status != Status.WAITING_MANAGER_APPROVAL:
            return None
        route = routing.resolve_approver(req.employee)
        if route is None:
            return None

        def short(e):
            return {"id": e.pk, "full_name": e.full_name} if e else None

        return {
            "kind": route.kind, "employee": short(route.approver), "acting_for": short(route.acting_for),
            "note": routing.describe(route),
        }


class VacationInputSerializer(serializers.Serializer):
    date_from = serializers.DateField()
    date_to = serializers.DateField()
    vacation_type = serializers.ChoiceField(choices=VacationType.choices, default=VacationType.ANNUAL)
    comment = serializers.CharField(required=False, allow_blank=True, default="")


class AdvanceInputSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    reason = serializers.CharField(required=False, allow_blank=True, default="")


class HrRequestCreateSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=RequestType.choices)
    vacation = VacationInputSerializer(required=False)
    advance = AdvanceInputSerializer(required=False)
    as_draft = serializers.BooleanField(default=False)

    def validate(self, attrs):
        if attrs["type"] not in attrs:
            raise serializers.ValidationError({attrs["type"]: "Заполните данные заявки"})
        return attrs


class BusyVacationSerializer(serializers.ModelSerializer):
    request_id = serializers.IntegerField(source="request.id")
    number = serializers.CharField(source="request.number")
    status = serializers.CharField(source="request.status")

    class Meta:
        model = VacationDetails
        fields = ["request_id", "number", "status", "date_from", "date_to", "days"]


class CommentSerializer(serializers.Serializer):
    comment = serializers.CharField(required=False, allow_blank=True, default="")
