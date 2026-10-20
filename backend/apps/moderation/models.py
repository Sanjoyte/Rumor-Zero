import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.posts.models import PostStatus

MAX_PUBLIC_NOTE_LENGTH = 500
MAX_APPEAL_REASON_LENGTH = 500


class ActionKind(models.TextChoices):
    """Every kind the audit trail holds (ARCHITECTURE §2). Part 10 writes the first five; Part 11
    writes `restored` and `kept_removed` (the latter was added then: "Keep removed" had no kind),
    Part 11C the three `emergency_*` kinds (`emergency_unblocked` was added then: an Unblock, or the
    automatic lift when a FALSE label is overturned, had no kind) and `avatar_*` is Part 14B."""

    VERIFIED = "verified", "Marked verified"
    MARKED_FALSE = "marked_false", "Marked FALSE"
    DISMISSED_REPORT = "dismissed_report", "Dismissed reports"
    REMOVED = "removed", "Removed"
    ESCALATED = "escalated", "Escalated"
    RESTORED = "restored", "Restored"
    KEPT_REMOVED = "kept_removed", "Kept removed"
    EMERGENCY_DEMOTED = "emergency_demoted", "Emergency demoted"
    EMERGENCY_BLOCKED = "emergency_blocked", "Emergency posting blocked"
    EMERGENCY_UNBLOCKED = "emergency_unblocked", "Emergency posting unblocked"
    AVATAR_REMOVED = "avatar_removed", "Photo removed"
    AVATAR_BLOCKED = "avatar_blocked", "Photo uploads blocked"


def _in_or_null(field, choices):
    return Q(**{f"{field}__in": choices.values}) | Q(**{f"{field}__isnull": True})


class AppealKind(models.TextChoices):
    LABEL = "label", "FALSE label"
    REMOVAL = "removal", "Removal"


class AppealStatus(models.TextChoices):
    OPEN = "open", "Open"
    UPHELD = "upheld", "Upheld"  # the original decision stands
    OVERTURNED = "overturned", "Overturned"


class Appeal(models.Model):
    """An author's request for another look at a FALSE label or a removal (ARCHITECTURE §2, §4).

    One per post for life (`post` is one-to-one: a unique foreign key in Django's idiom), so a
    resolved appeal can't be followed by another. Written only by `apps/moderation/services.py`
    (`file_appeal` and the five actions that resolve one); a row changes once, from `open` to
    `upheld` or `overturned`, and goes only with the post or the account (CASCADE).
    `original_moderator` is who made the call being appealed, so someone else looks again: null for
    a pipeline FALSE, or when the moderator's account is gone.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    post = models.OneToOneField("posts.Post", on_delete=models.CASCADE, related_name="appeal")
    # The post's author (the service checks it). Its index serves account deletion and export.
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="appeals"
    )
    kind = models.CharField(max_length=10, choices=AppealKind.choices)
    reason = models.CharField(max_length=MAX_APPEAL_REASON_LENGTH, blank=True)
    status = models.CharField(
        max_length=10, choices=AppealStatus.choices, default=AppealStatus.OPEN
    )
    original_moderator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    # Not auto_now_add: the service passes `now`, and tests place appeals in time.
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(kind__in=AppealKind.values), name="appeals_kind_valid"
            ),
            models.CheckConstraint(
                condition=Q(status__in=AppealStatus.values), name="appeals_status_valid"
            ),
            # Open exactly while it has no resolution time, as for reports.
            models.CheckConstraint(
                condition=(
                    Q(status=AppealStatus.OPEN, resolved_at__isnull=True)
                    | (~Q(status=AppealStatus.OPEN) & Q(resolved_at__isnull=False))
                ),
                name="appeals_resolution_consistent",
            ),
        ]

    def __str__(self):
        # The reason is the author's own words: it stays out of logs and the admin's breadcrumbs.
        return f"{self.get_kind_display()} appeal ({self.post_id})"


class ModerationAction(models.Model):
    """One moderator decision, kept for good (ARCHITECTURE §2 "moderation_actions").

    **Append-only:** a row is written once by `apps/moderation/services.py` and never changed or
    deleted (`save` and `delete` refuse). Deleting the post or an account only nulls the link
    (`SET_NULL` is an UPDATE the collector issues without calling `save`), and `post_snapshot`
    keeps what the post said. `public_note` is what the author may be shown (the verdict note, or
    the reason for a removal, user decision 2026-10-11); `notes` stay internal.

    Part 11C: an `emergency_blocked` row carries the end of its block (`blocked_until`, set on
    exactly those rows), and `subject_user` names the account. An account's block and unblock rows
    are strictly increasing in time, so `rules.standing_block_end` reads them in the order they
    happened.
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
    # Set on the row of the action that resolves an appeal (not on Escalate).
    appeal = models.ForeignKey(
        Appeal,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="moderation_actions",
    )
    notes = models.TextField(blank=True)
    # The end of an `emergency_blocked` row's block (Part 11C); null on every other row.
    blocked_until = models.DateTimeField(null=True, blank=True)
    # Not auto_now_add: the services pass `now`, and tests place rows in time.
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        # Block / Unblock emergency posting, on `UserAdmin` (Part 11C; user decision 2026-10-19:
        # moderators and up).
        permissions = [("block_emergency_posting", "Can block or unblock emergency posting")]
        constraints = [
            models.CheckConstraint(
                condition=Q(action__in=ActionKind.values), name="moderation_action_valid"
            ),
            models.CheckConstraint(
                condition=(
                    Q(action=ActionKind.EMERGENCY_BLOCKED, blocked_until__isnull=False)
                    | (~Q(action=ActionKind.EMERGENCY_BLOCKED) & Q(blocked_until__isnull=True))
                ),
                name="moderation_action_blocked_until_kind",
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
