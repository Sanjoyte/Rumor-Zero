from django.contrib import admin, messages
from django.db import transaction
from django.utils.text import Truncator

from apps.core.admin_mixins import HistoryNeedsLog
from apps.notifications import services as notification_services
from apps.social.models import Bookmark, Comment, Follow, Like, Repost


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
class CommentAdmin(HistoryNeedsLog, admin.ModelAdmin):
    """Read-only, with two actions: **Hide comments** and **Unhide comments** (ARCHITECTURE §8).

    A moderator hides rather than edits or deletes; a hidden comment is in no list and no count
    until it is unhidden. Unhide doesn't undelete what its author deleted. There is no
    `moderation_actions` row for this (it has no comment kind), so each change is written to
    Django's own admin log. The actions need `social.change_comment`, which the Moderators group
    holds (Part 10). The object's History page is seniors-only, like the log it reads.
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
            # Django's changelist actions run outside a transaction: one per comment, so a hidden
            # comment and the removal of its notification (Part 13) stand or fall together.
            with transaction.atomic():
                comment.is_hidden = hidden
                comment.save(update_fields=["is_hidden"])
                if hidden:
                    notification_services.discard_for_comment(comment.pk)
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


@admin.register(Repost)
class RepostAdmin(admin.ModelAdmin):
    """Read-only: reposts change only through `social.services`, so the feed cache stays right."""

    list_display = ("user", "post", "status_at_repost", "created_at")
    list_filter = ("status_at_repost",)
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


@admin.register(Bookmark)
class BookmarkAdmin(admin.ModelAdmin):
    """Read-only and **superusers only** (user decision 2026-10-10).

    Bookmarks are private (ARCHITECTURE §4d): no moderator, whatever permissions Part 10 grants,
    can open the list. A superuser can already read the database, so this adds no new reach.
    """

    list_display = ("user", "post", "created_at")
    search_fields = ("user__username",)
    list_select_related = ("user", "post")
    show_full_result_count = False
    ordering = ("-created_at",)

    def has_view_permission(self, request, obj=None):
        # With no view permission Django also leaves the model off the admin index.
        return request.user.is_superuser

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
