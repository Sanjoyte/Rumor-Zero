import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.posts.models import PostStatus

MAX_PUBLIC_NOTE_LENGTH = 500


class ActionKind(models.TextChoices):
    """Every kind the audit trail will ever hold (ARCHITECTURE §2), created now so later parts
    never alter the database check. Part 10 writes the first five; `restored` is Part 11,
    `emergency_*` Part 11C and `avatar_*` Part 14B."""

    VERIFIED = "verified", "Marked verified"
    MARKED_FALSE = "marked_false", "Marked FALSE"
    DISMISSED_REPORT = "dismissed_report", "Dismissed reports"
    REMOVED = "removed", "Removed"
    ESCALATED = "escalated", "Escalated"
    RESTORED = "restored", "Restored"
    EMERGENCY_DEMOTED = "emergency_demoted", "Emergency demoted"
    EMERGENCY_BLOCKED = "emergency_blocked", "Emergency posting blocked"
    AVATAR_REMOVED = "avatar_removed", "Photo removed"
    AVATAR_BLOCKED = "avatar_blocked", "Photo uploads blocked"


def _in_or_null(field, choices):
    return Q(**{f"{field}__in": choices.values}) | Q(**{f"{field}__isnull": True})


class ModerationAction(models.Model):
    """One moderator decision, kept for good (ARCHITECTURE §2 "moderation_actions").

    **Append-only:** a row is written once by `apps/moderation/services.py` and never changed or
    deleted (`save` and `delete` refuse). Deleting the post or an account only nulls the link
    (`SET_NULL` is an UPDATE the collector issues without calling `save`), and `post_snapshot`
    keeps what the post said. `public_note` is what the author may be shown (the verdict note, or
    the reason for a removal, user decision 2026-10-11); `notes` stay internal.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # No FK index of its own: `modaction_post_created_idx` leads with the post.
    post = models.ForeignKey(
        "posts.Post",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="moderation_actions",
        db_index=False,
    )
    # The account acted on (emergency block, photo removal): null for a post action.
    subject_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    post_snapshot = models.TextField(blank=True)
    moderator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    action = models.CharField(max_length=20, choices=ActionKind.choices)
    from_status = models.CharField(  # noqa: DJ001
        max_length=20, choices=PostStatus.choices, null=True, blank=True
    )
    to_status = models.CharField(  # noqa: DJ001
        max_length=20, choices=PostStatus.choices, null=True, blank=True
    )
    public_note = models.CharField(max_length=MAX_PUBLIC_NOTE_LENGTH, blank=True)
    notes = models.TextField(blank=True)
    # Not auto_now_add: the services pass `now`, and tests place rows in time.
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(action__in=ActionKind.values), name="moderation_action_valid"
            ),
            models.CheckConstraint(
                condition=_in_or_null("from_status", PostStatus),
                name="moderation_action_from_status_valid",
            ),
            models.CheckConstraint(
                condition=_in_or_null("to_status", PostStatus),
                name="moderation_action_to_status_valid",
            ),
        ]
        indexes = [
            # The history inline on a post page.
            models.Index(fields=["post", "-created_at"], name="modaction_post_created_idx"),
            # The seniors' full log, newest first.
            models.Index(fields=["-created_at"], name="modaction_created_idx"),
        ]

    def __str__(self):
        return f"{self.get_action_display()} ({self.post_id})"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise RuntimeError("Moderation actions are append-only: a saved row can't change.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError("Moderation actions are append-only: a row can't be deleted.")
