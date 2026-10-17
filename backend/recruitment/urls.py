from django.urls import path
from rest_framework.routers import SimpleRouter

from recruitment import views

router = SimpleRouter(trailing_slash=False)
router.register("recruitment/candidates", views.CandidateViewSet, basename="recruitment-candidates")

urlpatterns = [
    # публичная форма на странице входа (без авторизации)
    path("careers/vacancies", views.PublicVacanciesView.as_view()),
    path("careers/applications", views.PublicApplicationView.as_view()),
    path("careers/status", views.PublicTrackView.as_view()),
    # раздел «Подбор» для HR и руководителей-интервьюеров
    path("recruitment/summary", views.RecruitmentSummaryView.as_view()),
    path("recruitment/vacancies", views.RecruitmentVacanciesView.as_view()),
    path("recruitment/vacancies/<int:vacancy_id>", views.RecruitmentVacancyView.as_view()),
    path("recruitment/departments", views.DepartmentsView.as_view()),
    path("recruitment/interviewers", views.InterviewersView.as_view()),
    path("recruitment/interviews", views.InterviewCalendarView.as_view()),
    path("recruitment/interviews/<int:interview_id>/feedback", views.InterviewFeedbackView.as_view()),
] + router.urls
