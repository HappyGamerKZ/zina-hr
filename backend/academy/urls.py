from rest_framework.routers import SimpleRouter

from academy.views import AssignmentViewSet, CourseViewSet

router = SimpleRouter(trailing_slash=False)
router.register("academy/courses", CourseViewSet, basename="academy-courses")
router.register("academy/assignments", AssignmentViewSet, basename="academy-assignments")

urlpatterns = router.urls
