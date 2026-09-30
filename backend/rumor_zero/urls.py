"""Root URL configuration."""

from django.conf import settings
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("api/", include("apps.core.urls")),
    path(settings.ADMIN_URL_PATH, admin.site.urls),
]
