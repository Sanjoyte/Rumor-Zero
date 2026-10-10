from django.contrib import admin, messages
from django.utils.text import Truncator

from apps.social.models import Comment, Follow, Like


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


@admin.register(Like)
class LikeAdmin(admin.ModelAdmin):
    """Read-only: likes change only through `social.services`."""

    list_display = ("user", "post", "created_at")
    search_fields = ("user__username",)
    list_select_related = ("user", "post")
    show_full_result_count = False
    ordering = ("-created_at",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    """Read-only, with two actions: **Hide comments** and **Unhide comments** (ARCHITECTURE §8).

    A moderator hides rather than edits or deletes; a hidden comment is in no list and no count
    until it is unhidden. Unhide doesn't undelete what its author deleted. There is no
    `moderation_actions` row for this (that table arrives in Part 10 and has no comment kind), so
    each change is written to Django's own admin log. The actions need `social.change_comment`
    (Part 10 gives it to the Moderators group; today a superuser has it).
    """

    list_display = ("excerpt", "author", "post", "is_hidden", "deleted_at", "created_at")
    list_filter = (
        "is_hidden",
        ("deleted_at", admin.EmptyFieldListFilter),
        "created_at",
    )
    search_fields = ("content", "author__username")
    list_select_related = ("author", "post")
    show_full_result_count = False
    ordering = ("-created_at",)
    actions = ["hide_comments", "unhide_comments"]

    @admin.display(description="Comment")
    def excerpt(self, comment):
        return Truncator(comment.content).chars(80)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_hide_permission(self, request):
        return request.user.has_perm("social.change_comment")

    def _set_hidden(self, request, queryset, hidden):
        """Change only the comments that need it, log each one, and say how many changed."""
        word = "Hidden" if hidden else "Unhidden"
        changed = 0
        for comment in queryset.filter(is_hidden=not hidden):
            comment.is_hidden = hidden
            comment.save(update_fields=["is_hidden"])
            self.log_change(request, comment, word)
            changed += 1
        self.message_user(
            request, f"{word}: {changed} comment{'' if changed == 1 else 's'}.", messages.SUCCESS
        )

    @admin.action(description="Hide selected comments", permissions=["hide"])
    def hide_comments(self, request, queryset):
        self._set_hidden(request, queryset, True)

    @admin.action(description="Unhide selected comments", permissions=["hide"])
    def unhide_comments(self, request, queryset):
        self._set_hidden(request, queryset, False)
