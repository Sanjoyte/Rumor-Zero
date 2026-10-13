"""The moderator actions on a post, and the author's appeal (ARCHITECTURE §4, §8). Only this module
and `apps/posts/services.py` change `Post.status`.

Each action runs in one `transaction.atomic()` and does the same things:

1. lock the post row with `FOR NO KEY UPDATE`, the lock reports, reposts, appeals and the
   pipeline's apply use, so a report or a pipeline answer that arrives meanwhile waits and then sees
   the new state; the post's open appeal is read under that lock (every writer of an appeal takes
   the post's lock first, so the appeal needs none of its own);
2. re-check `rules.refusal` against the locked rows (the screen the moderator saw may be old);
3. apply `rules.transition` and save exactly those fields;
4. resolve the post's open reports through `reports.services.resolve_open_reports`, and its open
   appeal when the action decides it;
5. append the `ModerationAction`, linked to the appeal it resolved.

A refusal raises `ActionRefused` and writes nothing. There is no HTTP here: the admin turns the
exception into a message. Part 11B adds the reputation calls and Part 13 the notifications, in this
same transaction.
"""

from django.db import transaction
from django.utils import timezone

from apps.moderation import rules
from apps.moderation.models import (
    ActionKind,
    Appeal,
    AppealKind,
    AppealStatus,
    ModerationAction,
)
from apps.pipeline import routing
from apps.posts import services as post_services
from apps.posts.models import FlaggedReason, Post, PostStatus, VerdictSource
from apps.posts.services import NotPostAuthor, PostNotFound
from apps.reports import services as report_services

# Exactly what `rules.transition` can change, plus `updated_at` (auto_now needs to be listed).
_SAVED_FIELDS = [
    "status",
    "flagged_reason",
    "pre_review_status",
    "pre_removal_status",
    "review_started_at",
    "escalated_at",
    "verdict_source",
    "verdict_note",
    "moderated_by",
    "moderated_at",
    "updated_at",
]


class ActionRefused(Exception):
    """The action isn't allowed on this post (see `rules.refusal`): nothing was written."""

    def __init__(self, refusal):
        super().__init__(refusal.text)
        self.refusal = refusal


class AlreadyAppealed(Exception):
    """The post has an appeal already: one per post for life, whatever became of it."""


class NotAppealable(Exception):
    """Only a post labelled FALSE or removed can be appealed."""


def open_appeal(post):
    """The post's open appeal, or None (no lock: the admin and the pure rules read it)."""
    return Appeal.objects.filter(post=post, status=AppealStatus.OPEN).first()


def _perform(act, post_id, *, moderator, notes, public_note, now):
    with transaction.atomic():
        post = (
            Post.objects.select_for_update(no_key=True, of=("self",))
            .defer("pipeline_result")
            .filter(pk=post_id)
            .first()
        )
        # After the lock, not before: a moderator who waited stamps a later time than the one
        # whose change they saw, so the audit trail's order is the order things really happened.
        now = now or timezone.now()
        if post is None:
            # Not a post at all (a stale id): the same refusal as a post its author deleted.
            raise ActionRefused(rules.DELETED)
        # No lock of its own: every writer of an appeal holds this post's lock first.
        appeal = Appeal.objects.filter(post=post, status=AppealStatus.OPEN).first()
        refusal = rules.refusal(act, post, moderator, appeal=appeal)
        if refusal is not None:
            raise ActionRefused(refusal)
        effect = rules.transition(
            act, post, moderator=moderator, now=now, appeal=appeal, public_note=public_note
        )
        post.save(update_fields=_SAVED_FIELDS)
        if effect.report_status is not None:
            report_services.resolve_open_reports(
                post, status=effect.report_status, moderator=moderator, now=now
            )
        resolved = None
        if effect.appeal_status is not None:
            # One write: the database check wants `status` and `resolved_at` to change together.
            appeal.status = effect.appeal_status
            appeal.resolved_by = moderator
            appeal.resolved_at = now
            appeal.save(update_fields=["status", "resolved_by", "resolved_at"])
            resolved = appeal
        entry = ModerationAction.objects.create(
            post=post,
            post_snapshot=post.content,
            moderator=moderator,
            action=effect.kind,
            from_status=effect.from_status,
            to_status=effect.to_status,
            public_note=public_note,
            appeal=resolved,
            notes=notes,
            created_at=now,
        )
        if effect.kind == ActionKind.RESTORED and post.status == PostStatus.PENDING:
            # Restored and not yet checked: check it now, like a new fact (the sweeper is the
            # fallback).
            post_services.kick_pipeline_after_commit(post.pk)
        return entry


def mark_verified(post_id, *, moderator, notes="", public_note="", now=None):
    """A fact under review is true: `verified_true`, `verdict_source=moderator`. `public_note`
    becomes the post's `verdict_note` (blank clears it). Open reports become `actioned`."""
    return _perform(
        rules.Act.MARK_VERIFIED,
        post_id,
        moderator=moderator,
        notes=notes,
        public_note=public_note,
        now=now,
    )


def mark_false(post_id, *, moderator, notes="", public_note="", now=None):
    """A fact under review is FALSE: `verified_false`, `verdict_source=moderator`, as above."""
    return _perform(
        rules.Act.MARK_FALSE,
        post_id,
        moderator=moderator,
        notes=notes,
        public_note=public_note,
        now=now,
    )


def dismiss_reports(post_id, *, moderator, notes="", now=None):
    """The reports were not enough: a post flagged only by reports goes back to the status it had;
    one also flagged by the pipeline stays under review for the pipeline. Open reports become
    `dismissed` and never count again."""
    return _perform(
        rules.Act.DISMISS_REPORTS,
        post_id,
        moderator=moderator,
        notes=notes,
        public_note="",
        now=now,
    )


def remove_post(post_id, *, moderator, notes="", public_note="", now=None):
    """Take the post down. Its status before review (or its current one) is kept in
    `pre_removal_status`. `public_note` is the reason shown to the author; it lives on the audit
    row only, never in `Post.verdict_note`. Open reports become `actioned`."""
    return _perform(
        rules.Act.REMOVE,
        post_id,
        moderator=moderator,
        notes=notes,
        public_note=public_note,
        now=now,
    )


def escalate(post_id, *, moderator, notes="", now=None):
    """Mark a post under review for a senior moderator (`escalated_at`). It never locks the post:
    any moderator can still act on it."""
    return _perform(
        rules.Act.ESCALATE,
        post_id,
        moderator=moderator,
        notes=notes,
        public_note="",
        now=now,
    )


def restore_post(post_id, *, moderator, notes="", now=None):
    """Put a removed post back, resolving its open removal appeal as `overturned`. The post goes
    back to `pre_removal_status`; a fact the pipeline had already checked goes to review instead
    (`rules._restore`). Internal notes only: the author is told the outcome in plain words."""
    return _perform(
        rules.Act.RESTORE,
        post_id,
        moderator=moderator,
        notes=notes,
        public_note="",
        now=now,
    )


def keep_removed(post_id, *, moderator, notes="", now=None):
    """The removal stands: the post stays `removed` and its open removal appeal is `upheld`."""
    return _perform(
        rules.Act.KEEP_REMOVED,
        post_id,
        moderator=moderator,
        notes=notes,
        public_note="",
        now=now,
    )


# ---------- The author's appeal ----------


def _original_moderator(post):
    """Who made the call being appealed, so someone else looks again (null: any moderator may).

    A FALSE label appeals the latest `marked_false` row, **only when a moderator gave the label**
    (a pipeline FALSE has no one to avoid, and `post.moderated_by` would name whoever last dismissed
    its reports). A removal appeals the latest `removed` row. Two moderators who each marked a post
    FALSE over time: only the latest counts.
    """
    if post.status == PostStatus.REMOVED:
        kind = ActionKind.REMOVED
    elif post.verdict_source == VerdictSource.MODERATOR:
        kind = ActionKind.MARKED_FALSE
    else:
        return None
    row = (
        ModerationAction.objects.filter(post=post, action=kind)
        .order_by("-created_at")
        .only("moderator_id")
        .first()
    )
    return row.moderator_id if row is not None else None


def file_appeal(*, author, post_id, reason="", now=None):
    """Ask for another look at a FALSE label or a removal. Returns the `Appeal`.

    Raises `PostNotFound` (unknown, or the author deleted it), `NotPostAuthor`, `AlreadyAppealed`
    (any earlier appeal, open or resolved) and `NotAppealable` (a status other than FALSE or
    removed; a FALSE post under review for reports isn't appealable until that review ends).
    The post row is locked with `FOR NO KEY UPDATE`, the lock reports, reposts, the pipeline and
    moderators use, so the duplicate check is race-free and an appeal serialises with a Mark FALSE.
    A **label** appeal sends the post to the review queue (`under_review`, flag `appeal`); a
    **removal** appeal only sets the flag: the post stays removed, hidden, and is listed in the
    queue next to the posts under review.
    """
    with transaction.atomic():
        post = (
            Post.objects.not_deleted()
            .select_for_update(no_key=True, of=("self",))
            .defer("pipeline_result")
            .filter(pk=post_id)
            .first()
        )
        # After the lock, not before: the time is when the appeal really happened.
        now = now or timezone.now()
        if post is None:
            raise PostNotFound
        if post.author_id != author.pk:
            raise NotPostAuthor
        if Appeal.objects.filter(post=post).exists():
            raise AlreadyAppealed
        if post.status == PostStatus.VERIFIED_FALSE:
            kind = AppealKind.LABEL
        elif post.status == PostStatus.REMOVED:
            kind = AppealKind.REMOVAL
        else:
            raise NotAppealable
        original = _original_moderator(post)
        if kind == AppealKind.LABEL:
            routing.enter_review(post, FlaggedReason.APPEAL, now)
            fields = ["status", "flagged_reason", "pre_review_status", "review_started_at"]
        else:
            post.flagged_reason = FlaggedReason.APPEAL
            fields = ["flagged_reason"]
        post.save(update_fields=[*fields, "updated_at"])
        return Appeal.objects.create(
            post=post,
            author=author,
            kind=kind,
            reason=reason,
            original_moderator_id=original,
            created_at=now,
        )
