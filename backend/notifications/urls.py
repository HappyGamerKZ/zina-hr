from django.urls import path
from rest_framework.routers import SimpleRouter

from notifications.stream import notification_stream
from notifications.views import NotificationViewSet

router = SimpleRouter(trailing_slash=False)
router.register("notifications", NotificationViewSet, basename="notifications")

urlpatterns = [
    path("notifications/stream", notification_stream, name="notifications-stream"),  # SSE, до роутера
] + router.urls
