from django.urls import path

from apps.accounts import views

urlpatterns = [
    path("v1/me/", views.MeView.as_view(), name="me"),
    path(
        "v1/me/verification-email/",
        views.VerificationEmailView.as_view(),
        name="me-verification-email",
    ),
    path(
        "v1/auth/username-available/",
        views.UsernameAvailableView.as_view(),
        name="username-available",
    ),
]
