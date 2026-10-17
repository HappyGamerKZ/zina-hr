from rest_framework import serializers

from hr_requests.models import HrRequest, RESERVING_STATUSES
from hr_requests.services import vacation_balance
from org.models import Employee


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
        return AssignmentSerializer(assignments, many=True).data


class TeamMemberSerializer(serializers.ModelSerializer):
    department = serializers.CharField(source="department.name_ru")
    position = serializers.CharField(source="position.title_ru")
    vacation_days_available = serializers.SerializerMethodField()
    active_requests = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = [
            "id", "full_name", "department", "position", "hire_date",
            "vacation_days_available", "active_requests",
        ]

    def get_vacation_days_available(self, emp) -> int:
        return vacation_balance(emp)["days_available"]

    def get_active_requests(self, emp) -> int:
        return HrRequest.objects.filter(employee=emp, status__in=RESERVING_STATUSES).count()
