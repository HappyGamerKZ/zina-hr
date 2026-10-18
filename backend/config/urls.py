from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

admin.site.site_header = "JanaHR — администрирование"
admin.site.site_title = "JanaHR"

api_v1 = [
    path("", include("accounts.urls")),
    path("", include("org.urls")),
    path("", include("hr_requests.urls")),
    path("", include("notifications.urls")),
    path("", include("academy.urls")),
    path("", include("integrations.urls")),
    path("", include("recruitment.urls")),
    path("", include("assistant.urls")),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include(api_v1)),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
]

# В режиме разработки файлы отдаёт Django; в обычном режиме — nginx из общего тома.
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
