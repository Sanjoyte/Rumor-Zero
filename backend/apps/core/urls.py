from django.urls import path

from apps.core import views

urlpatterns = [
    path("health/", views.HealthView.as_view(), name="health"),
    path("health/deep/", views.DeepHealthView.as_view(), name="health-deep"),
]
