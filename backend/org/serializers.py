from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

from hr_requests.models import HrRequest, RESERVING_STATUSES
from hr_requests.services import vacation_balance
from org.models import Delegation, Employee


class ManagerSerializer(serializers.ModelSerializer):
    position = serializers.CharField(source="position.title_ru")

    class Meta:
        model = Employee
        fields = ["id", "full_name", "position"]


class VacationBalanceSerializer(serializers.Serializer):
    days_total = serializers.IntegerField()
    days_used = serializers.IntegerField()
    days_reserved = serializers.IntegerField()
    days_available = serializers.IntegerField()
    as_of = serializers.DateField(allow_null=True)
    synced_at = serializers.DateTimeField(allow_null=True)


class ProfileSerializer(serializers.ModelSerializer):
    """Профиль сотрудника. Все поля — read-only копия данных 1С:ЗУП."""

    company = serializers.CharField(source="company.name_ru")
    department = serializers.CharField(source="department.name_ru")
    position = serializers.CharField(source="position.title_ru")
    manager = ManagerSerializer(allow_null=True)
    vacation_balance = serializers.SerializerMethodField()
    learning = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = [
            "id", "full_name", "company", "department", "position", "manager",
            "hire_date", "email", "external_id", "source", "synced_at", "vacation_balance", "learning",
        ]
        read_only_fields = fields

    def get_vacation_balance(self, emp) -> VacationBalanceSerializer:
        return VacationBalanceSerializer(vacation_balance(emp)).data

    def get_learning(self, emp) -> list:
        """Jana Academy в профиле: назначенные курсы, прогресс и результат."""
        from academy.serializers import AssignmentSerializer

        assignments = emp.course_assignments.select_related("course", "employee", "assigned_by__employee")
        return AssignmentSerializer(assignments, many=True, context=self.context).data


class TeamMemberSerializer(serializers.ModelSerializer):
    department = serializers.CharField(source="department.name_ru")
    position = serializers.CharField(source="position.title_ru")
    vacation_days_available = serializers.SerializerMethodField()
    active_requests = serializers.SerializerMethodField()
    absence = serializers.SerializerMethodField()
    deputy = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = [
            "id", "full_name", "department", "position", "hire_date",
            "vacation_days_available", "active_requests", "absence", "deputy",
        ]

    def get_vacation_days_available(self, emp) -> int:
        return vacation_balance(emp)["days_available"]

    def get_active_requests(self, emp) -> int:
        return HrRequest.objects.filter(employee=emp, status__in=RESERVING_STATUSES).count()

    def get_absence(self, emp) -> dict | None:
        """Уволен, сейчас в отпуске или отпуск в ближайшие 30 дней (только утверждённые)."""
        return team_absence(emp)

    def get_deputy(self, emp) -> dict | None:
        """И.О. на время отсутствия (или действующее сейчас замещение) — только у руководителей."""
        absence = team_absence(emp)
        today = timezone.localdate()
        start, end = (absence["date_from"], absence["date_to"]) if absence and absence["date_from"] else (today, today)
        d = (Delegation.objects.filter(manager=emp, revoked_at__isnull=True, date_from__lte=end, date_to__gte=start)
             .select_related("deputy").order_by("date_from").first())
        return {"id": d.deputy_id, "full_name": d.deputy.full_name, "date_from": d.date_from, "date_to": d.date_to} \
            if d else None


UPCOMING_DAYS = 30


def team_absence(emp) -> dict | None:
    """{state: dismissed | vacation | planned, date_from, date_to} или None — на месте."""
    from hr_requests.models import RequestType, Status, VacationDetails

    today = timezone.localdate()
    if emp.dismissed_on and emp.dismissed_on <= today:
        return {"state": "dismissed", "date_from": emp.dismissed_on, "date_to": None}
    v = (VacationDetails.objects.filter(request__employee=emp, request__type=RequestType.VACATION,
                                        request__status=Status.APPROVED_SENT_TO_1C, date_to__gte=today,
                                        date_from__lte=today + timedelta(days=UPCOMING_DAYS))
         .order_by("date_from").first())
    if v is None:
        return None
    return {"state": "vacation" if v.date_from <= today else "planned", "date_from": v.date_from, "date_to": v.date_to}


# --- замещение руководителя (И.О.) ---

class DelegationSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    manager = ManagerSerializer()
    deputy = ManagerSerializer()
    date_from = serializers.DateField()
    date_to = serializers.DateField()
    revoked_at = serializers.DateTimeField(allow_null=True)
    state = serializers.SerializerMethodField()  # planned | active | finished | revoked

    def get_state(self, d) -> str:
        today = self.context["today"]
        if d.revoked_at:
            return "revoked"
        return "planned" if d.date_from > today else "finished" if d.date_to < today else "active"


class DelegationInputSerializer(serializers.Serializer):
    deputy_id = serializers.IntegerField()
    date_from = serializers.DateField()
    date_to = serializers.DateField()
