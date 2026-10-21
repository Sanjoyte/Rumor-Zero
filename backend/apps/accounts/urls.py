from django.urls import path

from apps.accounts import views

urlpatterns = [
    path("v1/me/", views.MeView.as_view(), name="me"),
    path("v1/me/password/", views.PasswordChangeView.as_view(), name="me-password"),
    path("v1/me/avatar/", views.AvatarView.as_view(), name="me-avatar"),
    path("v1/avatars/<str:user_id>/<str:name>", views.AvatarImageView.as_view(), name="avatar"),
    path("v1/me/export/", views.ExportView.as_view(), name="me-export"),
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
