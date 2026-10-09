from django.contrib import admin

from apps.social.models import Follow


@admin.register(Follow)
class FollowAdmin(admin.ModelAdmin):
    """Read-only: follows change only through `social.services`, so the feed cache stays right."""

    list_display = ("follower", "following", "created_at")
    search_fields = ("follower__username", "following__username")
    list_select_related = ("follower", "following")
    show_full_result_count = False
    ordering = ("-created_at",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
