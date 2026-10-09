from django.contrib import admin

from apps.posts.models import Post


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    """Read-only until Part 10: every change goes through `posts.services` (and, for moderator
    actions, `moderation.services`), so nothing may bypass them from here."""

    list_display = ("excerpt", "post_type", "status", "author", "created_at", "deleted_at")
    list_filter = ("post_type", "status")
    search_fields = ("content", "author__username")
    list_select_related = ("author",)
    show_full_result_count = False
    ordering = ("-created_at",)

    @admin.display(description="Post")
    def excerpt(self, post):
        return str(post)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
