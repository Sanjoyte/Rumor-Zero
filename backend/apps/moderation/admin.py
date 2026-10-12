"""Django Admin as the moderation panel (ARCHITECTURE §8).

`PostAdmin` is the review queue. It stays **read-only for everyone** (`has_change_permission` is
always False, so the page has no Save and a POST to its change URL is a 403): every change goes
through `apps/moderation/services.py`, which locks the row, re-checks the rules and writes the
audit trail. The five actions are bulk actions with a confirmation page; the same actions are
offered as buttons on a post's own page.

`ModerationActionAdmin` (the full moderation log) and `LogEntryAdmin` (Django's own admin log,
where account and settings changes are recorded with their values) are read-only and seniors-only.
"""

import copy
import uuid
from collections import Counter

from django.contrib import admin, messages
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.contrib.admin.models import LogEntry
from django.db.models import F
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.text import Truncator
from django.utils.timesince import timesince

from apps.core.admin_mixins import HistoryNeedsLog
from apps.moderation import rules, services
from apps.moderation.forms import ConfirmActionForm
from apps.moderation.models import ModerationAction
from apps.moderation.rules import Act
from apps.posts.emergency import is_active_emergency
from apps.posts.models import Post, PostStatus, PostType
from apps.reports.models import Report

BATCH_CAP = 100  # posts per action: the admin's page size, and what a person can read and weigh

# action name -> (rule, label in the dropdown, the service, what it says when done)
ACTIONS = {
    "mark_verified": (
        Act.MARK_VERIFIED,
        "Mark verified",
        services.mark_verified,
        lambda n: f"Marked {n} {'post' if n == 1 else 'posts'} verified.",
    ),
    "mark_false": (
        Act.MARK_FALSE,
        "Mark FALSE",
        services.mark_false,
        lambda n: f"Marked {n} {'post' if n == 1 else 'posts'} FALSE.",
    ),
    "dismiss_reports": (
        Act.DISMISS_REPORTS,
        "Dismiss reports",
        services.dismiss_reports,
        lambda n: f"Dismissed the reports on {n} {'post' if n == 1 else 'posts'}.",
    ),
    "remove_posts": (
        Act.REMOVE,
        "Remove posts",
        services.remove_post,
        lambda n: f"Removed {n} {'post' if n == 1 else 'posts'}.",
    ),
    "escalate": (
        Act.ESCALATE,
        "Escalate to senior",
        services.escalate,
        lambda n: f"Escalated {n} {'post' if n == 1 else 'posts'} to a senior moderator.",
    ),
}
BUTTON_LABELS = {
    "mark_verified": "Mark verified",
    "mark_false": "Mark FALSE",
    "dismiss_reports": "Dismiss reports",
    "remove_posts": "Remove post",
    "escalate": "Escalate to senior",
}


def pipeline_text(post):
    """What the pipeline said, for the queue: "FALSE 92%", "TRUE 95%", "Inconclusive 40%", "—"."""
    if post.pipeline_verdict is None or post.confidence_score is None:
        return "—"
    word = (
        "Inconclusive" if post.pipeline_verdict == "inconclusive" else post.pipeline_verdict.upper()
    )
    return f"{word} {format(post.confidence_score.normalize(), 'f')}%"


# ---------- the filters ----------


class QueueFilter(admin.SimpleListFilter):
    """The "Show" filter: the review queue (the default) or every post. Choosing a status or
    "deleted by author" is a look at other posts, so it leaves the queue too (otherwise
    "removed" on top of the queue would always be empty)."""

    title = "show"
    parameter_name = "queue"
    LEAVES_THE_QUEUE = ("status__exact", "deleted_at__isempty")

    def lookups(self, request, model_admin):
        return [("all", "All posts")]

    def queryset(self, request, queryset):
        if self.value() == "all" or any(key in request.GET for key in self.LEAVES_THE_QUEUE):
            return queryset
        return queryset.filter(status=PostStatus.UNDER_REVIEW, deleted_at__isnull=True)

    def choices(self, changelist):
        yield {
            "selected": self.value() is None,
            "query_string": changelist.get_query_string(remove=[self.parameter_name]),
            "display": "Review queue",
        }
        yield {
            "selected": self.value() == "all",
            "query_string": changelist.get_query_string({self.parameter_name: "all"}),
            "display": "All posts",
        }


class EscalatedFilter(admin.SimpleListFilter):
    title = "escalated"
    parameter_name = "escalated"

    def lookups(self, request, model_admin):
        return [("yes", "Yes"), ("no", "No")]

    def queryset(self, request, queryset):
        if self.value() in ("yes", "no"):
            return queryset.filter(escalated_at__isnull=self.value() == "no")
        return queryset


# ---------- the inlines on a post's page ----------


class ReportInline(admin.TabularInline):
    model = Report
    extra = 0
    can_delete = False
    ordering = ("created_at",)
    fields = (
        "created_at",
        "reporter",
        "reporter_age",
        "reason",
        "details",
        "counts_toward_threshold",
        "status",
    )
    readonly_fields = fields

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("reporter")

    @admin.display(description="Reporter's account was")
    def reporter_age(self, report):
        """How old their account was when they reported: a day-old account is cheap to make."""
        return timesince(report.reporter.created_at, report.created_at) or "less than a minute"

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class ModerationHistoryInline(admin.TabularInline):
    """What moderators did to this post. Viewable with `posts.view_post`, so a moderator sees it
    without the full log (user decision 2026-10-11)."""

    model = ModerationAction
    verbose_name_plural = "Moderation history"
    extra = 0
    can_delete = False
    ordering = ("-created_at",)
    fields = ("created_at", "action", "moderator", "change", "public_note", "notes")
    readonly_fields = fields

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("moderator")

    @admin.display(description="Status")
    def change(self, row):
        if row.from_status is None and row.to_status is None:
            return "—"
        return f"{row.from_status or '—'} → {row.to_status or '—'}"

    def has_view_permission(self, request, obj=None):
        return request.user.has_perm("posts.view_post")

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# ---------- the review queue ----------


@admin.register(Post)
class PostAdmin(HistoryNeedsLog, admin.ModelAdmin):
    list_display = (
        "claim",
        "kind",
        "status",
        "reason",
        "pipeline",
        "report_total",
        "waiting",
        "posted",
        "escalated",
        "emergency",
        "author",
    )
    list_filter = (
        QueueFilter,
        "flagged_reason",
        "post_type",
        "status",
        EscalatedFilter,
        # "Deleted by author": the author's soft delete keeps the row, so a moderator can find it.
        ("deleted_at", admin.EmptyFieldListFilter),
    )
    search_fields = ("content", "author__username")
    list_select_related = ("author",)
    list_per_page = BATCH_CAP
    show_full_result_count = False
    # Most reported first, then the longest wait, then the newest: the same shape as the Part 11C
    # ordering, which puts active emergencies above all of it.
    ordering = ("-report_count", F("review_started_at").asc(nulls_last=True), "-created_at")
    actions = list(ACTIONS)
    inlines = (ReportInline, ModerationHistoryInline)
    change_form_template = "moderation/admin/post_change_form.html"
    change_list_template = "moderation/admin/post_change_list.html"

    fieldsets = (
        (
            "Post",
            {"fields": ("author", "post_type", "content", "sources", "created_at", "deleted_at")},
        ),
        (
            "Review",
            {
                "fields": (
                    "status",
                    "flagged_reason",
                    "pre_review_status",
                    "pre_removal_status",
                    "review_started_at",
                    "report_count",
                    "escalated_at",
                    "verdict_source",
                    "verdict_note",
                    "moderated_by",
                    "moderated_at",
                )
            },
        ),
        (
            "Pipeline",
            {
                "fields": (
                    "pipeline_verdict",
                    "confidence_score",
                    "pipeline_checked_at",
                    "pipeline_attempts",
                    "pipeline_next_attempt_at",
                    "pipeline_result",
                )
            },
        ),
        ("Emergency", {"fields": ("is_emergency", "emergency_expires_at", "emergency_demoted_at")}),
    )
    readonly_fields = tuple(field for _, section in fieldsets for field in section["fields"]) + (
        "updated_at",
    )

    def get_queryset(self, request):
        return super().get_queryset(request).defer("pipeline_result")

    # --- columns ---

    @admin.display(description="Post", ordering="content")
    def claim(self, post):
        return Truncator(post.content).chars(80)

    @admin.display(description="Type", ordering="post_type")
    def kind(self, post):
        return post.get_post_type_display()

    # Not called `reports`: that is also the reverse relation to `Report`, which the admin would
    # find first (`opts.get_field`) and show and sort instead of this method.
    @admin.display(description="Reports", ordering="report_count")
    def report_total(self, post):
        return post.report_count

    @admin.display(description="Posted", ordering="created_at")
    def posted(self, post):
        return post.created_at

    @admin.display(description="Reason", ordering="flagged_reason")
    def reason(self, post):
        return post.get_flagged_reason_display() if post.flagged_reason else "—"

    @admin.display(description="Pipeline", ordering="confidence_score")
    def pipeline(self, post):
        return pipeline_text(post)

    @admin.display(description="Waiting", ordering="review_started_at")
    def waiting(self, post):
        return timesince(post.review_started_at, timezone.now()) if post.review_started_at else "—"

    @admin.display(boolean=True, description="Escalated", ordering="escalated_at")
    def escalated(self, post):
        return post.escalated_at is not None

    @admin.display(description="Emergency")
    def emergency(self, post):
        if not post.is_emergency:
            return "—"
        return "Active" if is_active_emergency(post, timezone.now()) else "Ended"

    # --- nothing is edited here: the services own every change ---

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_moderate_permission(self, request):
        """The actions are gated on `posts.change_post`, as Hide on `social.change_comment`."""
        return request.user.has_perm("posts.change_post")

    def get_actions(self, request):
        actions = super().get_actions(request)
        if request.GET.get("post_type__exact") == PostType.OPINION:
            # An opinion gets no verdict: don't offer one in a list that shows only opinions.
            for name in ("mark_verified", "mark_false"):
                actions.pop(name, None)
        return actions

    # --- the buttons on a post's own page ---

    def render_change_form(self, request, context, add=False, change=False, form_url="", obj=None):
        if obj is not None and self.has_moderate_permission(request):
            context["moderation_buttons"] = [
                {"action": name, "label": BUTTON_LABELS[name]}
                for name, (act, *_rest) in ACTIONS.items()
                if rules.refusal(act, obj, request.user) is None
            ]
        return super().render_change_form(request, context, add, change, form_url, obj)

    def response_action(self, request, queryset):
        """Django filters by the posted ids itself, and an id that isn't a UUID would raise
        `ValidationError` (a 500). Drop such ids first; none left reads as "nothing selected"."""
        posted = request.POST.copy()
        valid = []
        for value in posted.getlist(ACTION_CHECKBOX_NAME):
            try:
                valid.append(str(uuid.UUID(value)))
            except ValueError:
                continue
        posted.setlist(ACTION_CHECKBOX_NAME, valid)
        request.POST = posted
        return super().response_action(request, queryset)

    # --- the five actions ---

    @admin.action(description="Mark verified (facts only)", permissions=["moderate"])
    def mark_verified(self, request, queryset):
        return self._moderate(request, queryset, "mark_verified")

    @admin.action(description="Mark FALSE (facts only)", permissions=["moderate"])
    def mark_false(self, request, queryset):
        return self._moderate(request, queryset, "mark_false")

    @admin.action(description="Dismiss reports", permissions=["moderate"])
    def dismiss_reports(self, request, queryset):
        return self._moderate(request, queryset, "dismiss_reports")

    @admin.action(description="Remove posts", permissions=["moderate"])
    def remove_posts(self, request, queryset):
        return self._moderate(request, queryset, "remove_posts")

    @admin.action(description="Escalate to senior", permissions=["moderate"])
    def escalate(self, request, queryset):
        return self._moderate(request, queryset, "escalate")

    def _moderate(self, request, queryset, name):
        """First POST: show what would change and what would be skipped, with the note fields.
        The confirmation POST (it carries `apply`): do it, post by post, through the service.

        The confirmation names the posts it showed, so the apply step acts on exactly those: it
        never trusts `select_across`, which would make Django re-run the whole filtered queryset
        and could pick up a post that entered the queue meanwhile.
        """
        act, label, service, done_text = ACTIONS[name]
        applying = "apply" in request.POST
        if applying:
            # `response_action` has already dropped malformed ids (below).
            ids = request.POST.getlist(ACTION_CHECKBOX_NAME)
            queryset = self.get_queryset(request).filter(pk__in=ids)
        posts = list(queryset.select_related("author").order_by("pk")[: BATCH_CAP + 1])
        if len(posts) > BATCH_CAP:
            self.message_user(
                request,
                f"Select at most {BATCH_CAP} posts at a time (narrow the list or tick fewer).",
                messages.ERROR,
            )
            return None
        if not posts:
            self.message_user(request, "No posts to act on.", messages.WARNING)
            return None

        form = ConfirmActionForm(request.POST if applying else None, act=act)
        from_post = bool(request.POST.get("_from_post"))
        if applying and form.is_valid():
            return self._apply(
                request, posts, act, service, done_text, form.cleaned_data, from_post
            )

        now = timezone.now()
        changing, skipped = [], []
        for post in posts:
            refusal = rules.refusal(act, post, request.user)
            if refusal is not None:
                skipped.append({"row": self._row(post), "why": refusal.text})
                continue
            after = rules.transition(act, copy.copy(post), moderator=request.user, now=now)
            row = self._row(post)
            row["after"] = PostStatus(after.to_status).label
            changing.append(row)
        cancel_url = (
            reverse("admin:posts_post_change", args=[posts[0].pk])
            if from_post
            else request.get_full_path()
        )
        context = {
            **self.admin_site.each_context(request),
            "title": f"{label}: are you sure?",
            "opts": self.opts,
            "action": name,
            "label": label,
            "form": form,
            "changing": changing,
            "skipped": skipped,
            "selected": [str(post.pk) for post in posts],
            "from_post": from_post,
            "form_action": request.get_full_path(),
            "cancel_url": cancel_url,
        }
        return TemplateResponse(request, "moderation/admin/confirm_action.html", context)

    def _row(self, post):
        return {
            "post": post,
            "claim": Truncator(post.content).chars(120),
            "type": post.get_post_type_display(),
            "before": post.get_status_display(),
            "reason": self.reason(post),
            "reports": post.report_count,
            "pipeline": pipeline_text(post),
            "author": post.author.username,
        }

    def _apply(self, request, posts, act, service, done_text, cleaned, from_post):
        kwargs = {"notes": cleaned["notes"].strip()}
        if "public_note" in cleaned:
            kwargs["public_note"] = cleaned["public_note"].strip()
        done = 0
        skipped = Counter()
        for post in posts:
            try:
                service(post.pk, moderator=request.user, **kwargs)
                done += 1
            except services.ActionRefused as refused:
                skipped[refused.refusal.text] += 1
        if done:
            self.message_user(request, done_text(done), messages.SUCCESS)
        if skipped:
            detail = ", ".join(f"{count} {why}" for why, count in sorted(skipped.items()))
            self.message_user(
                request, f"Skipped {sum(skipped.values())}: {detail}.", messages.WARNING
            )
        if from_post:
            return HttpResponseRedirect(reverse("admin:posts_post_change", args=[posts[0].pk]))
        return HttpResponseRedirect(request.get_full_path())


# ---------- the logs (seniors only) ----------


@admin.register(ModerationAction)
class ModerationActionAdmin(admin.ModelAdmin):
    """The full moderation log: read-only, and only for those holding
    `moderation.view_moderationaction` (seniors). A moderator sees a post's own history on the
    post's page instead."""

    list_display = ("created_at", "action", "moderator", "post_link", "change")
    list_filter = ("action", "created_at")
    search_fields = ("post_snapshot", "moderator__username")
    list_select_related = ("moderator", "post")
    show_full_result_count = False
    ordering = ("-created_at",)
    fields = (
        "created_at",
        "action",
        "moderator",
        "post",
        "post_snapshot",
        "subject_user",
        "from_status",
        "to_status",
        "public_note",
        "notes",
    )
    readonly_fields = fields

    @admin.display(description="Post")
    def post_link(self, row):
        excerpt = Truncator(row.post_snapshot).chars(80) or "—"
        if row.post_id is None:
            return excerpt
        url = reverse("admin:posts_post_change", args=[row.post_id])
        return format_html('<a href="{}">{}</a>', url, excerpt)

    @admin.display(description="Status")
    def change(self, row):
        if row.from_status is None and row.to_status is None:
            return "—"
        return f"{row.from_status or '—'} → {row.to_status or '—'}"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(LogEntry)
class LogEntryAdmin(admin.ModelAdmin):
    """Django's admin log, read-only and seniors-only (`admin.view_logentry`). It holds what has
    no `moderation_actions` kind: role and suspension changes, Mark email verified, platform
    settings, and Hide/Unhide of comments, with old → new values."""

    list_display = ("action_time", "user", "content_type", "object_repr", "action_flag", "message")
    list_filter = ("content_type", "action_flag")
    search_fields = ("object_repr", "change_message", "user__username")
    list_select_related = ("user", "content_type")
    show_full_result_count = False
    ordering = ("-action_time",)

    @admin.display(description="Change")
    def message(self, entry):
        return entry.get_change_message()

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
