from django.urls import path

from assistant import views

urlpatterns = [
    path("ai/ask", views.AskView.as_view()),
    path("ai/escalate", views.EscalateView.as_view()),
    path("ai/questions", views.QuestionsView.as_view()),
    path("ai/questions/<int:question_id>/answer", views.AnswerView.as_view()),
]
