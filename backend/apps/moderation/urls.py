from django.urls import path

from apps.moderation import views

urlpatterns = [
    path("v1/posts/<str:post_id>/appeal/", views.AppealView.as_view(), name="appeal"),
]
