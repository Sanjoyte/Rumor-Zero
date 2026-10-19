import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone


class EventKind(models.TextChoices):
    """Every kind of credibility event (ARCHITECTURE §4a). The weights live in `scoring.WEIGHTS`;
    the labels are what people read (the public profile's recent list, your own ledger, the
    admin)."""

    FACT_TRUE = "fact_true", "Fact verified true"
    FACT_FALSE = "fact_false", "Fact labelled FALSE"
    EMERGENCY_FALSE = "emergency_false", "Emergency post labelled FALSE"
    POST_REMOVED = "post_removed", "Post removed by a moderator"
    REPOST_TRUE = "repost_true", "Repost of a fact verified true"
    REPOST_FALSE = "repost_false", "Repost of a fact labelled FALSE"
    REPOST_EMERGENCY_FALSE = (
        "repost_emergency_false",
        "Repost of an emergency post labelled FALSE",
    )
    REPOST_REMOVED = "repost_removed", "Repost of a post a moderator removed"
    REPORT_UPHELD = "report_upheld", "Report upheld by a moderator"
    REVERSAL = "reversal", "Reversal"


class ReputationEvent(models.Model):
    """One row of a person's credibility ledger (ARCHITECTURE §2, §4a).

    **Append-only:** written once by `apps/reputation/services.py` and never changed or deleted
    (`save` and `delete` refuse). An outcome that is overturned gets a `reversal` row that carries
    the negated weights and points at the row it cancels (`reverses`, unique: a row is reversed
    once). The score is computed from the sums of every row, reversals included, and `score_after`
    is the person's score right after the row was written. Deleting an account takes its rows with
    it (CASCADE); a post's hard delete only nulls the link (`SET_NULL` is a queryset `UPDATE`, which
    calls neither method).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # No FK index of its own: `repevent_user_created_idx` leads with the user.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reputation_events",
        db_index=False,
    )
    kind = models.CharField(max_length=30, choices=EventKind.choices)
    positive = models.DecimalField(max_digits=6, decimal_places=2)
    negative = models.DecimalField(max_digits=6, decimal_places=2)
    # Indexed: `settle_post` reads a post's rows.
    post = models.ForeignKey(
        "posts.Post",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reputation_events",
    )
    moderation_action = models.ForeignKey(
        "moderation.ModerationAction",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        db_index=False,
    )
    reverses = models.OneToOneField(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="reversed_by",
    )
    score_after = models.SmallIntegerField()
    # Not auto_now_add: the service passes the time (strictly increasing per person), and tests
    # place rows in time.
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        # "Credibility" in everything people read, `reputation` in code (ANALYSIS f-5).
        verbose_name = "credibility event"
        verbose_name_plural = "credibility events"
        constraints = [
            models.CheckConstraint(
                condition=Q(kind__in=EventKind.values), name="reputation_event_kind_valid"
            ),
            # A reversal carries the negated weights of the row it cancels; every other row adds.
            models.CheckConstraint(
                condition=(
                    Q(kind=EventKind.REVERSAL, positive__lte=0, negative__lte=0)
                    | (~Q(kind=EventKind.REVERSAL) & Q(positive__gte=0, negative__gte=0))
                ),
                name="reputation_event_weights_sign",
            ),
            models.CheckConstraint(
                condition=(
                    Q(kind=EventKind.REVERSAL, reverses__isnull=False)
                    | (~Q(kind=EventKind.REVERSAL) & Q(reverses__isnull=True))
                ),
                name="reputation_event_reverses_iff_reversal",
            ),
            models.CheckConstraint(
                condition=Q(score_after__gte=0, score_after__lte=100),
                name="reputation_event_score_after_range",
            ),
        ]
        indexes = [
            # A person's ledger in order: the totals, the reporter cap, both endpoints, the trend.
            models.Index(fields=["user", "created_at"], name="repevent_user_created_idx"),
        ]

    def __str__(self):
        return f"{self.get_kind_display()} ({self.user_id})"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise RuntimeError("Credibility events are append-only: a saved row can't change.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError("Credibility events are append-only: a row can't be deleted.")
