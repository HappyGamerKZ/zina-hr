from rest_framework.routers import SimpleRouter

from hr_requests.views import HrRequestViewSet

router = SimpleRouter(trailing_slash=False)
router.register("requests", HrRequestViewSet, basename="requests")

urlpatterns = router.urls
