from django.urls import path

from apps.reports import views

urlpatterns = [
    path("v1/posts/<str:post_id>/report/", views.ReportView.as_view(), name="report"),
]
