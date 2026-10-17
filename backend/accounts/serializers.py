from rest_framework import serializers

from accounts.models import User


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)


class MeSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    permissions = serializers.ListField(source="permissions_list", read_only=True)

    class Meta:
        model = User
        fields = ["id", "username", "role", "locale", "employee_id", "full_name", "permissions"]
        read_only_fields = ["id", "username", "role", "employee_id"]

    def get_full_name(self, user) -> str:
        return user.employee.full_name if user.employee else user.get_full_name() or user.username
