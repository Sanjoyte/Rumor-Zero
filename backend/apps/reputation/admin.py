"""The credibility ledger in Django Admin (ARCHITECTURE §8): read-only for everyone, and viewable
by moderators and up (`reputation.view_reputationevent`, user decision 2026-10-13). A post's page
shows its own rows as an inline (`apps/moderation/admin.py`), and an account's page links to its
rows (`apps/accounts/admin.py`)."""

from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.utils.text import Truncator

from apps.core.admin_mixins import HistoryNeedsLog
from apps.reputation.models import ReputationEvent
from apps.reputation.serializers import is_reversed


def weights(row):
    """The weights as people read them: "P +1", "N +2", or a reversal's "P −0.25"."""
    parts = []
    for letter, value in (("P", row.positive), ("N", row.negative)):
        if value:
            sign = "+" if value > 0 else "−"
            parts.append(f"{letter} {sign}{format(abs(value).normalize(), 'f')}")
    return " ".join(parts) or "0"


@admin.register(ReputationEvent)
class ReputationEventAdmin(HistoryNeedsLog, admin.ModelAdmin):
    """Every credibility event, newest first. Nothing is edited here: the reputation service is
    the ledger's only writer, and a row is never changed or deleted."""

    list_display = ("created_at", "user", "kind", "weight", "score_after", "post_link", "reversed")
    list_filter = ("kind", "created_at")
    search_fields = ("user__username",)
    list_select_related = ("user", "post")
    show_full_result_count = False
    ordering = ("-created_at",)
    fields = (
        "created_at",
        "user",
        "kind",
        "positive",
        "negative",
        "score_after",
        "post",
        "moderation_action",
        "reverses",
    )
    readonly_fields = fields

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .defer("post__pipeline_result")
            .annotate(is_reversed=is_reversed())
        )

    @admin.display(description="P / N")
    def weight(self, row):
        return weights(row)

    @admin.display(description="Post")
    def post_link(self, row):
        if row.post_id is None:
            return "—"
        url = reverse("admin:posts_post_change", args=[row.post_id])
        return format_html('<a href="{}">{}</a>', url, Truncator(row.post.content).chars(60))

    @admin.display(boolean=True, description="Reversed")
    def reversed(self, row):
        return row.is_reversed

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class ReputationInline(admin.TabularInline):
    """A post's credibility events, oldest first, on its admin page."""

    model = ReputationEvent
    fk_name = "post"
    verbose_name_plural = "Credibility events"
    extra = 0
    can_delete = False
    ordering = ("created_at", "id")
    fields = ("created_at", "user", "kind", "weight", "score_after")
    readonly_fields = fields

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user")

    @admin.display(description="P / N")
    def weight(self, row):
        return weights(row)

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


def events_url(user):
    return f"{reverse('admin:reputation_reputationevent_changelist')}?user__id__exact={user.pk}"
