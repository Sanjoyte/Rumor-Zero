from django.urls import path

from apps.posts import views

urlpatterns = [
    path("v1/posts/", views.PostListView.as_view(), name="posts"),
    path("v1/me/fact-quota/", views.FactQuotaView.as_view(), name="me-fact-quota"),
]
