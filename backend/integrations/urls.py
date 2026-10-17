from django.urls import path

from integrations.views import DocumentologWebhookView

urlpatterns = [
    path("integrations/documentolog/webhook", DocumentologWebhookView.as_view()),
]
