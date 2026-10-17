from rest_framework.routers import SimpleRouter

from notifications.views import NotificationViewSet

router = SimpleRouter(trailing_slash=False)
router.register("notifications", NotificationViewSet, basename="notifications")

urlpatterns = router.urls
