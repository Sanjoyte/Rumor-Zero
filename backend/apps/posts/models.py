import uuid

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.db.models import Func, IntegerField, Q, Value
from django.db.models.functions import Length
from django.db.models.lookups import GreaterThanOrEqual, IsNull, LessThanOrEqual
from django.utils import timezone

MAX_CONTENT_LENGTH = 500
MAX_SOURCES = 5
MAX_SOURCE_LENGTH = 500


class PostType(models.TextChoices):
    OPINION = "opinion", "Opinion"
    FACT = "fact", "Fact"


class PostStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    PUBLISHED = "published", "Published"
    VERIFIED_TRUE = "verified_true", "Verified true"
    VERIFIED_FALSE = "verified_false", "Verified false"
    UNDER_REVIEW = "under_review", "Under review"
    REMOVED = "removed", "Removed"


class FlaggedReason(models.TextChoices):
    PIPELINE = "pipeline", "Pipeline"
    REPORTS = "reports", "Reports"
    BOTH = "both", "Both"
    APPEAL = "appeal", "Appeal"


class PipelineVerdict(models.TextChoices):
    TRUE = "true", "True"
    FALSE = "false", "False"
    INCONCLUSIVE = "inconclusive", "Inconclusive"


class VerdictSource(models.TextChoices):
    PIPELINE = "pipeline", "Pipeline"
    MODERATOR = "moderator", "Moderator"


class ArrayPosition(Func):
    """`array_position(array, value)`: the 1-based index of the value, NULL when absent."""

    function = "array_position"
    output_field = IntegerField()


class PostQuerySet(models.QuerySet):
    def visible(self):
        """What every public list shows: not deleted by the author, not removed by a moderator."""
        return self.filter(deleted_at__isnull=True).exclude(status=PostStatus.REMOVED)

    def for_list(self):
        """One query for a list of cards: the author joined in, the raw pipeline blob left out."""
        return self.select_related("author").defer("pipeline_result")


def _in_or_null(field, choices):
    return Q(**{f"{field}__in": choices.values}) | Q(**{f"{field}__isnull": True})


class Post(models.Model):
    """A post (ARCHITECTURE §2). Status changes go through `apps/posts/services.py` only."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # No separate FK index: `(author, -created_at)` below covers it.
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="posts", db_index=False
    )
    content = models.TextField()
    post_type = models.CharField(max_length=10, choices=PostType.choices)
    # Fact posts only: 0-5 normalised URLs or bare DOIs in the order entered (§4c). Never fetched.
    sources = ArrayField(models.CharField(max_length=MAX_SOURCE_LENGTH), default=list, blank=True)

    # Emergency columns exist now; the logic arrives in Part 11C (§4b).
    is_emergency = models.BooleanField(default=False)
    emergency_expires_at = models.DateTimeField(null=True, blank=True)
    emergency_demoted_at = models.DateTimeField(null=True, blank=True)

    status = models.CharField(max_length=20, choices=PostStatus.choices)
    flagged_reason = models.CharField(  # noqa: DJ001
        max_length=10, choices=FlaggedReason.choices, null=True, blank=True
    )
    pre_review_status = models.CharField(  # noqa: DJ001
        max_length=20, choices=PostStatus.choices, null=True, blank=True
    )
    pre_removal_status = models.CharField(  # noqa: DJ001
        max_length=20, choices=PostStatus.choices, null=True, blank=True
    )

    confidence_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    pipeline_verdict = models.CharField(  # noqa: DJ001
        max_length=12, choices=PipelineVerdict.choices, null=True, blank=True
    )
    pipeline_result = models.JSONField(null=True, blank=True)
    pipeline_attempts = models.PositiveSmallIntegerField(default=0)
    pipeline_next_attempt_at = models.DateTimeField(null=True, blank=True)
    pipeline_checked_at = models.DateTimeField(null=True, blank=True)
    verdict_source = models.CharField(  # noqa: DJ001
        max_length=10, choices=VerdictSource.choices, null=True, blank=True
    )
    verdict_note = models.CharField(max_length=500, blank=True)

    report_count = models.PositiveIntegerField(default=0)
    escalated_at = models.DateTimeField(null=True, blank=True)
    moderated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    moderated_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    # Not auto_now_add: the service passes `now`, and tests place posts in the past.
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    objects = PostQuerySet.as_manager()

    class Meta:
        constraints = [
            # `Length` is char_length: it counts code points, as the serializer and the client do.
            models.CheckConstraint(
                condition=(
                    GreaterThanOrEqual(Length("content"), 1)
                    & LessThanOrEqual(Length("content"), MAX_CONTENT_LENGTH)
                ),
                name="posts_post_content_length",
            ),
            models.CheckConstraint(
                condition=Q(post_type__in=PostType.values), name="posts_post_type_valid"
            ),
            models.CheckConstraint(
                condition=Q(status__in=PostStatus.values), name="posts_post_status_valid"
            ),
            models.CheckConstraint(
                condition=_in_or_null("flagged_reason", FlaggedReason),
                name="posts_post_flagged_reason_valid",
            ),
            models.CheckConstraint(
                condition=_in_or_null("pre_review_status", PostStatus),
                name="posts_post_pre_review_status_valid",
            ),
            models.CheckConstraint(
                condition=_in_or_null("pre_removal_status", PostStatus),
                name="posts_post_pre_removal_status_valid",
            ),
            models.CheckConstraint(
                condition=_in_or_null("pipeline_verdict", PipelineVerdict),
                name="posts_post_pipeline_verdict_valid",
            ),
            models.CheckConstraint(
                condition=_in_or_null("verdict_source", VerdictSource),
                name="posts_post_verdict_source_valid",
            ),
            # opinion => published, under_review or removed; fact => anything but published.
            models.CheckConstraint(
                condition=Q(post_type=PostType.FACT)
                | Q(
                    status__in=[
                        PostStatus.PUBLISHED,
                        PostStatus.UNDER_REVIEW,
                        PostStatus.REMOVED,
                    ]
                ),
                name="posts_post_opinion_status",
            ),
            models.CheckConstraint(
                condition=~Q(post_type=PostType.FACT, status=PostStatus.PUBLISHED),
                name="posts_post_fact_not_published",
            ),
            # `__len` compiles to coalesce(array_length(sources, 1), 0): an empty array is 0.
            models.CheckConstraint(
                condition=Q(sources__len__lte=MAX_SOURCES), name="posts_post_sources_max"
            ),
            models.CheckConstraint(
                condition=Q(post_type=PostType.FACT) | Q(sources__len=0),
                name="posts_post_sources_fact_only",
            ),
            models.CheckConstraint(
                condition=~Q(sources__contains=[""]), name="posts_post_sources_not_empty"
            ),
            models.CheckConstraint(
                condition=IsNull(ArrayPosition("sources", Value(None)), True),
                name="posts_post_sources_not_null",
            ),
            models.CheckConstraint(
                condition=Q(is_emergency=False) | Q(post_type=PostType.FACT),
                name="posts_post_emergency_fact_only",
            ),
            models.CheckConstraint(
                condition=Q(is_emergency=True, emergency_expires_at__isnull=False)
                | Q(is_emergency=False, emergency_expires_at__isnull=True),
                name="posts_post_emergency_expiry",
            ),
            models.CheckConstraint(
                condition=Q(confidence_score__isnull=True)
                | Q(confidence_score__gte=0, confidence_score__lte=100),
                name="posts_post_confidence_range",
            ),
        ]
        indexes = [
            models.Index(fields=["status", "-created_at"], name="posts_status_created_idx"),
            models.Index(fields=["author", "-created_at"], name="posts_author_created_idx"),
            # The pending queue, emergencies first (Part 9).
            models.Index(
                fields=["-is_emergency", "created_at"],
                condition=Q(post_type=PostType.FACT, status=PostStatus.PENDING)
                & Q(deleted_at__isnull=True),
                name="posts_pending_queue_idx",
            ),
            models.Index(
                fields=["created_at"],
                condition=Q(status=PostStatus.UNDER_REVIEW),
                name="posts_review_queue_idx",
            ),
            models.Index(
                fields=["emergency_expires_at"],
                condition=Q(
                    is_emergency=True, emergency_demoted_at__isnull=True, deleted_at__isnull=True
                ),
                name="posts_pinned_emerg_idx",
            ),
            # Recent: every status except removed, newest first. The (status, created_at)
            # index can't serve that.
            models.Index(
                fields=["-created_at", "-id"],
                condition=Q(deleted_at__isnull=True) & ~Q(status=PostStatus.REMOVED),
                name="posts_recent_idx",
            ),
        ]

    def __str__(self):
        text = self.content.replace("\n", " ")
        return text if len(text) <= 60 else text[:59] + "…"
