from django.urls import path

from apps.notifications import views

urlpatterns = [
    path("v1/notifications/", views.NotificationListView.as_view(), name="notifications"),
    path(
        "v1/notifications/unread-count/",
        views.UnreadCountView.as_view(),
        name="notifications-unread-count",
    ),
    path(
        "v1/notifications/mark-read/",
        views.MarkReadView.as_view(),
        name="notifications-mark-read",
    ),
]
