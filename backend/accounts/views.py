from django.contrib.auth import authenticate, login, logout
from django.db.models import Q
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from accounts.serializers import LoginSerializer, MeSerializer


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(responses={204: None})
    def get(self, request):
        return Response(status=status.HTTP_204_NO_CONTENT)


@method_decorator(csrf_protect, name="dispatch")
class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(request=LoginSerializer, responses=MeSerializer)
    def post(self, request):
        data = LoginSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        username = data.validated_data["username"].strip()
        if "@" in username:  # вход по рабочей почте (из 1С:ЗУП) вместо логина
            found = User.objects.filter(Q(email__iexact=username) | Q(employee__email__iexact=username)).first()
            username = found.username if found else username
        user = authenticate(request, username=username, password=data.validated_data["password"])
        if user is None:
            return Response(
                {"error": {"code": "INVALID_CREDENTIALS", "message": "Неверный логин или пароль"}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        login(request, user)
        return Response(MeSerializer(user).data)


class LogoutView(APIView):
    @extend_schema(request=None, responses={204: None})
    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    @extend_schema(responses=MeSerializer)
    def get(self, request):
        return Response(MeSerializer(request.user).data)

    @extend_schema(request=MeSerializer, responses=MeSerializer)
    def patch(self, request):
        # Пользователь может менять только язык интерфейса — кадровые данные read-only.
        serializer = MeSerializer(request.user, data={"locale": request.data.get("locale")}, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
