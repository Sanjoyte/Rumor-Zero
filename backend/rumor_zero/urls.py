"""Root URL configuration."""

from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from apps.accounts.views import logout_view

urlpatterns = [
    # Before allauth's include, which owns the rest of /api/auth/ (ARCHITECTURE §7).
    path("api/auth/logout/", logout_view, name="auth-logout"),
    path("api/auth/", include("allauth.headless.urls")),
    path("api/", include("apps.accounts.urls")),
    path("api/", include("apps.posts.urls")),
    path("api/", include("apps.core.urls")),
    path(settings.ADMIN_URL_PATH, admin.site.urls),
]
