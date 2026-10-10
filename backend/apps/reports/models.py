import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

MAX_DETAILS_LENGTH = 500


class ReportReason(models.TextChoices):
    """The five plain-language reasons (ANALYSIS b-5); the labels are what the page shows."""

    INACCURATE = "inaccurate", "False or inaccurate"
    MISLEADING = "misleading", "Missing context or misleading"
    HARASSMENT = "harassment", "Harassment or defamation"
    SPAM = "spam", "Spam or fake accounts"
    OTHER = "other", "Something else"


class ReportStatus(models.TextChoices):
    """`open` reports can count toward the threshold; the other two never do again (§2)."""

    OPEN = "open", "Open"
    DISMISSED = "dismissed", "Dismissed"
    ACTIONED = "actioned", "Actioned"


class Report(models.Model):
    """One person's report of one post (ARCHITECTURE §2 "reports" and §5).

    One per (post, reporter) for life: a dismissed or actioned report is not a free second try.
    `counts_toward_threshold` is decided once, at insert (a young account with no activity
    doesn't count); the threshold itself is a windowed count over these rows, never Redis. The
    text and the reporter are never shown to anyone but moderators. Written only by
    `apps/reports/services.py` (and, from Part 10, the moderation services that resolve it).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # No index of its own: `reports_pair_unique` and `reports_post_created_idx` both lead with it.
    post = models.ForeignKey(
        "posts.Post", on_delete=models.CASCADE, related_name="reports", db_index=False
    )
    # Keeps its index: deleting an account or exporting its data looks reports up by reporter.
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reports_made"
    )
    reason = models.CharField(max_length=20, choices=ReportReason.choices)
    details = models.CharField(max_length=MAX_DETAILS_LENGTH, blank=True, default="")
    status = models.CharField(
        max_length=20, choices=ReportStatus.choices, default=ReportStatus.OPEN
    )
    counts_toward_threshold = models.BooleanField()
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reports_resolved",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["post", "reporter"], name="reports_pair_unique"),
            models.CheckConstraint(
                condition=Q(reason__in=[r.value for r in ReportReason]),
                name="reports_reason_valid",
            ),
            models.CheckConstraint(
                condition=Q(status__in=[s.value for s in ReportStatus]),
                name="reports_status_valid",
            ),
            # "Something else" says nothing by itself, so it needs words.
            models.CheckConstraint(
                condition=~Q(reason=ReportReason.OTHER, details=""),
                name="reports_other_needs_details",
            ),
            # Open exactly while nobody has resolved it: Part 10 sets the two together.
            models.CheckConstraint(
                condition=(
                    Q(status=ReportStatus.OPEN, resolved_at__isnull=True)
                    | (~Q(status=ReportStatus.OPEN) & Q(resolved_at__isnull=False))
                ),
                name="reports_resolution_consistent",
            ),
        ]
        indexes = [
            # The windowed threshold count, and the report list on a post (11D, Part 10's inline).
            models.Index(fields=["post", "created_at"], name="reports_post_created_idx"),
        ]

    def __str__(self):
        # Never the details: report text is for moderators only (§9).
        return f"{self.reporter_id} reported {self.post_id}"
