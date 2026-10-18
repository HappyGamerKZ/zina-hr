from django.urls import path

from org import views

urlpatterns = [
    path("me/profile", views.ProfileView.as_view()),
    path("me/dashboard", views.DashboardView.as_view()),
    path("team", views.TeamView.as_view()),
    path("team/<int:employee_id>", views.TeamMemberView.as_view()),
    path("me/delegations", views.DelegationsView.as_view()),
    path("me/delegations/<int:delegation_id>/revoke", views.DelegationRevokeView.as_view()),
]
