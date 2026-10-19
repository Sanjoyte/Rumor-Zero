from django.urls import path

from apps.reputation import views

urlpatterns = [
    path(
        "v1/users/<str:username>/reputation/",
        views.ReputationView.as_view(),
        name="reputation",
    ),
    path(
        "v1/me/reputation/events/",
        views.MyReputationEventsView.as_view(),
        name="reputation-events",
    ),
]
