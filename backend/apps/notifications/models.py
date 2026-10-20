import uuid

from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


class NotificationType(models.TextChoices):
    """Every notification type (ARCHITECTURE §2): nine, and no tenth. `follow`, `like`, `comment`
    and `repost` have an actor; the five moderation types are system messages with none."""

    FOLLOW = "follow", "Follow"
    LIKE = "like", "Like"
    COMMENT = "comment", "Comment"
    REPOST = "repost", "Repost"
    VERDICT = "verdict", "Verdict"
    UNDER_REVIEW = "under_review", "Under review"
    REMOVED = "removed", "Removed"
    EMERGENCY_DEMOTED = "emergency_demoted", "Emergency priority removed"
    APPEAL_RESOLVED = "appeal_resolved", "Appeal resolved"


class NotificationOutcome(models.TextChoices):
    """What a `verdict` or an `appeal_resolved` item says, stored so an old item can't change
    meaning when the post is labelled again. Blank for every other type."""

    TRUE = "true", "Verified true"
    FALSE = "false", "FALSE"
    UPHELD = "upheld", "Upheld"
    OVERTURNED = "overturned", "Overturned"


# The types a recipient is told about once per actor and post (or per actor, for a follow): a like
# taken back and given again is one item.
DEDUPED_TYPES = (NotificationType.LIKE, NotificationType.REPOST)
# Types whose item points at a post and nothing else.
POST_ONLY_TYPES = (
    NotificationType.LIKE,
    NotificationType.REPOST,
    NotificationType.VERDICT,
    NotificationType.UNDER_REVIEW,
    NotificationType.REMOVED,
    NotificationType.EMERGENCY_DEMOTED,
    NotificationType.APPEAL_RESOLVED,
)


class Notification(models.Model):
    """One item in a person's notifications (ARCHITECTURE §2).

    Written only by `apps/notifications/services.py`, called explicitly from the write services in
    the same transaction (no signals). `type` decides the shape: a `follow` points at nobody's post,
    a `comment` at a post and the comment, the other seven at a post. `outcome` is blank except for
    a `verdict` (`true` / `false`) and an `appeal_resolved` (`upheld` / `overturned`).

    An item is a record, not a live state: it stays after a like is taken back, and it goes with
    the post or comment it points at (CASCADE here; `delete_post` and `delete_comment` discard the
    items of a soft-deleted one). A suspended or deleted actor shows as "Someone": the account
    deletion nulls `actor` (SET_NULL).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # No FK index of its own: `notifications_list_idx` leads with the recipient.
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
        db_index=False,
    )
    # Partial index `notifications_actor_idx` serves the SET_NULL of an account deletion.
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        db_index=False,
    )
    type = models.CharField(max_length=20, choices=NotificationType.choices)
    post = models.ForeignKey(
        "posts.Post",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
        db_index=False,
    )
    comment = models.ForeignKey(
        "social.Comment",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
        db_index=False,
    )
    outcome = models.CharField(
        max_length=12, choices=NotificationOutcome.choices, blank=True, default=""
    )
    is_read = models.BooleanField(default=False)
    # Not auto_now_add: the service passes the time (an action's items are 1 µs apart so their
    # order is stable), and tests place rows in time.
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(type__in=NotificationType.values), name="notifications_type_valid"
            ),
            models.CheckConstraint(
                condition=(
                    (
                        Q(type=NotificationType.VERDICT)
                        & Q(outcome__in=[NotificationOutcome.TRUE, NotificationOutcome.FALSE])
                    )
                    | (
                        Q(type=NotificationType.APPEAL_RESOLVED)
                        & Q(
                            outcome__in=[
                                NotificationOutcome.UPHELD,
                                NotificationOutcome.OVERTURNED,
                            ]
                        )
                    )
                    | (
                        ~Q(type__in=[NotificationType.VERDICT, NotificationType.APPEAL_RESOLVED])
                        & Q(outcome="")
                    )
                ),
                name="notifications_outcome_valid",
            ),
            models.CheckConstraint(
                condition=(
                    Q(type=NotificationType.FOLLOW, post__isnull=True, comment__isnull=True)
                    | Q(type=NotificationType.COMMENT, post__isnull=False, comment__isnull=False)
                    | Q(type__in=POST_ONLY_TYPES, post__isnull=False, comment__isnull=True)
                ),
                name="notifications_shape_valid",
            ),
            # NULL passes: a deleted account's items keep a null actor.
            models.CheckConstraint(
                condition=~Q(actor=F("recipient")), name="notifications_not_self"
            ),
            # A like and a repost of one post by one person are two items, so `type` is in the key.
            models.UniqueConstraint(
                fields=["recipient", "actor", "type", "post"],
                condition=Q(type__in=DEDUPED_TYPES),
                name="notifications_post_event_unique",
            ),
            models.UniqueConstraint(
                fields=["recipient", "actor"],
                condition=Q(type=NotificationType.FOLLOW),
                name="notifications_follow_unique",
            ),
        ]
        indexes = [
            # The page, newest first.
            models.Index(fields=["recipient", "-created_at", "-id"], name="notifications_list_idx"),
            # The unread count: the query must filter with `is_read=False`, the index's predicate.
            models.Index(
                fields=["recipient"],
                condition=Q(is_read=False),
                name="notifications_unread_idx",
            ),
            # The cleanups: a deleted post or comment, an account deletion's SET_NULL.
            models.Index(
                fields=["post"], condition=Q(post__isnull=False), name="notifications_post_idx"
            ),
            models.Index(
                fields=["comment"],
                condition=Q(comment__isnull=False),
                name="notifications_comment_idx",
            ),
            models.Index(
                fields=["actor"], condition=Q(actor__isnull=False), name="notifications_actor_idx"
            ),
        ]

    def __str__(self):
        return f"{self.get_type_display()} for {self.recipient_id}"
