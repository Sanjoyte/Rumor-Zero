from django.urls import path

from apps.posts import views

urlpatterns = [
    path("v1/posts/", views.PostListView.as_view(), name="posts"),
    # The literal routes must come before the id route, which would take them for an id.
    path("v1/posts/status/", views.PostStatusView.as_view(), name="posts-status"),
    path("v1/posts/emergencies/", views.EmergencyListView.as_view(), name="posts-emergencies"),
    path("v1/posts/<str:post_id>/", views.PostDetailView.as_view(), name="post-detail"),
    path("v1/posts/<str:post_id>/stats/", views.PostStatsView.as_view(), name="post-stats"),
    path("v1/me/fact-quota/", views.FactQuotaView.as_view(), name="me-fact-quota"),
]
