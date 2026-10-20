"""Notifications in Django Admin: read-only, for support (ARCHITECTURE §8). They are written only by
`apps/notifications/services.py` and go with the post, comment or account they point at."""

from django.contrib import admin
from django.utils.text import Truncator

from apps.core.admin_mixins import HistoryNeedsLog
from apps.notifications.models import Notification


@admin.register(Notification)
class NotificationAdmin(HistoryNeedsLog, admin.ModelAdmin):
    list_display = ("created_at", "recipient", "type", "outcome", "actor", "excerpt", "is_read")
    list_filter = ("type", "is_read", "created_at")
    search_fields = ("recipient__username", "actor__username")
    list_select_related = ("recipient", "actor", "post")
    show_full_result_count = False
    ordering = ("-created_at",)
    fields = ("created_at", "recipient", "actor", "type", "outcome", "post", "comment", "is_read")
    readonly_fields = fields

    def get_queryset(self, request):
        return super().get_queryset(request).defer("post__pipeline_result", "post__search_vector")

    @admin.display(description="Post")
    def excerpt(self, notification):
        return Truncator(notification.post.content).chars(60) if notification.post else ""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
