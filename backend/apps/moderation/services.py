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
5. append the `ModerationAction`, linked to the appeal it resolved;
6. bring the credibility ledger in line with the post's new state (`reputation.services
   .settle_post`, Part 11B), crediting the reporters whose reports the action upheld when it changed
   the post (`Effect.credits_reporters`), never the deciding moderator. Escalate changes nothing
   and settles nothing;
7. (Part 11C) when a Mark FALSE ended an active emergency's priority, log `emergency_demoted`
   too; when the settle wrote the author's `emergency_false` row, block their emergency posting;
   when it reversed one (the FALSE was overturned), lift that post's block;
8. (Part 13) tell the post's author, in this same transaction (`_notify_author`).

A refusal raises `ActionRefused` and writes nothing. There is no HTTP here: the admin turns the
exception into a message.

**The emergency block** (Part 11C, §4b). This module is the only writer of
`users.emergency_blocked_until` and of the `emergency_blocked` / `emergency_unblocked` rows. The
column always equals `rules.standing_block_end` of the account's rows, recomputed under the
account's lock after each row; the rows are strictly increasing in time per account, so the order
they are read in is the order they happened. A block that follows a post's FALSE runs inside the
caller's transaction, after `settle_post` has locked the post and then the author, so the order
"post first, then users" holds; a manual Block or Unblock locks only the account.
"""

from datetime import timedelta

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from apps.accounts import avatars
from apps.accounts.models import User
from apps.core.services import get_platform_settings
from apps.moderation import rules
from apps.moderation.models import (
    ActionKind,
    Appeal,
    AppealKind,
    AppealStatus,
    ModerationAction,
)
from apps.notifications import services as notification_services
from apps.pipeline import routing
from apps.posts import services as post_services
from apps.posts.models import FlaggedReason, Post, PostStatus, VerdictSource
from apps.posts.services import NotPostAuthor, PostNotFound
from apps.reports import services as report_services
from apps.reputation import services as reputation_services
from apps.reputation.models import EventKind, ReputationEvent

_TICK = timedelta(microseconds=1)
BLOCK_KINDS = (ActionKind.EMERGENCY_BLOCKED, ActionKind.EMERGENCY_UNBLOCKED)

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
    "emergency_demoted_at",
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


def _notify_author(post, effect, appeal, *, label_before, moderator, now):
    """Tell the author what the action did (Part 13); `appeal` is the one it resolved, or None.

    Up to three items, 1 µs apart so they read in this order: the outcome (`verdict` when the
    label changed, or `removed`), `emergency_demoted`, then `appeal_resolved` on top. A Mark FALSE
    on a post that was FALSE already (a report review, an upheld label appeal) sends no repeat
    verdict. Dismiss and Escalate are silent, and so is a moderator acting on their own post (only
    a superuser can). No item names the moderator.
    """
    if moderator.pk == post.author_id:
        return
    sends = []
    if effect.kind in (ActionKind.VERIFIED, ActionKind.MARKED_FALSE):
        if label_before != post.status:
            sends.append(
                lambda at: notification_services.verdict_reached(
                    post=post, label=post.status, now=at
                )
            )
    elif effect.kind == ActionKind.REMOVED:
        sends.append(lambda at: notification_services.removed(post=post, now=at))
    if effect.demoted or effect.kind == ActionKind.EMERGENCY_DEMOTED:
        sends.append(lambda at: notification_services.emergency_demoted(post=post, now=at))
    if appeal is not None:
        sends.append(
            lambda at: notification_services.appeal_resolved(post=post, appeal=appeal, now=at)
        )
    for number, send in enumerate(sends):
        send(now + number * notification_services.TICK)


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
        refusal = rules.refusal(act, post, moderator, appeal=appeal, now=now)
        if refusal is not None:
            raise ActionRefused(refusal)
        # Read before the review fields are cleared: the author hears of a label that changed.
        label_before = post.pre_review_status
        effect = rules.transition(
            act, post, moderator=moderator, now=now, appeal=appeal, public_note=public_note
        )
        post.save(update_fields=_SAVED_FIELDS)
        credited = ()
        if effect.report_status is not None:
            reporters = report_services.resolve_open_reports(
                post, status=effect.report_status, moderator=moderator, now=now
            )
            if effect.credits_reporters:
                # No self-credit: the deciding moderator's own report earns nothing from their
                # decision (user decision 2026-10-13).
                credited = [pk for pk in reporters if pk != moderator.pk]
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
        # Part 11C: the history reads in order, 1 µs apart (the action, its demotion, a block).
        stamp = now
        if effect.demoted:
            stamp += _TICK
            ModerationAction.objects.create(
                post=post,
                post_snapshot=post.content,
                moderator=moderator,
                action=ActionKind.EMERGENCY_DEMOTED,
                from_status=effect.to_status,
                to_status=effect.to_status,
                notes="Automatic: the post was marked FALSE while it was pinned.",
                created_at=stamp,
            )
        if act != rules.Act.ESCALATE:
            # Demote changes no label and finds nothing to settle (two reads), but every action
            # that can change the status settles, so §4's rule stays simple.
            rows = reputation_services.settle_post(
                post, now=now, action=entry, credited_reporters=credited
            )
            if post.is_emergency:
                block_after_emergency_false(post, rows, now=stamp + _TICK, moderator=moderator)
                lift_after_overturn(post, rows, now=stamp + _TICK, moderator=moderator)
        _notify_author(
            post, effect, resolved, label_before=label_before, moderator=moderator, now=now
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


def demote_emergency(post_id, *, moderator, notes="", now=None):
    """End an active emergency's priority early (`emergency_demoted_at`), whatever its status: it
    leaves the pinned list at once and is checked in normal order. The label, a review and the
    reports stay as they are. Internal notes only (Part 11C)."""
    return _perform(
        rules.Act.DEMOTE_EMERGENCY,
        post_id,
        moderator=moderator,
        notes=notes,
        public_note="",
        now=now,
    )


# ---------- Part 11C: the emergency block ----------


def _lock_account(user_id):
    """The account's row, locked with `FOR NO KEY UPDATE` (Part 11B's rule for user rows), or
    None. Inside a post's transaction `settle_post` already holds it, so this costs nothing new."""
    return (
        User.objects.select_for_update(no_key=True)
        .only(
            "pk",
            "is_superuser",
            "emergency_blocked_until",
            "avatar_version",
            "avatar_uploads_blocked",
        )
        .filter(pk=user_id)
        .first()
    )


def _block_rows(user_id):
    return [
        rules.BlockRow(**row)
        for row in ModerationAction.objects.filter(subject_user_id=user_id, action__in=BLOCK_KINDS)
        .order_by("created_at", "id")
        .values("action", "post_id", "blocked_until")
    ]


def _next_block_time(user_id, now):
    """`now`, or 1 µs after the account's last block row: the rows are strictly increasing per
    account (the ledger's rule), so a writer that waited for the lock with an older `now` still
    comes after the row it waited for. Without it, an Unblock that committed first but stamped a
    later time than a waiting Mark FALSE would read the new block as already lifted."""
    last = ModerationAction.objects.filter(
        subject_user_id=user_id, action__in=BLOCK_KINDS
    ).aggregate(last=Max("created_at"))["last"]
    return now if last is None else max(now, last + _TICK)


def _write_block_row(user_id, *, post, moderator, action, now, notes, days=None):
    """Append one block or unblock row and bring the account's column in line with its rows.
    The caller holds the account's lock."""
    at = _next_block_time(user_id, now)
    entry = ModerationAction.objects.create(
        post=post,
        subject_user_id=user_id,
        post_snapshot=post.content if post is not None else "",
        moderator=moderator,
        action=action,
        blocked_until=at + timedelta(days=days) if days is not None else None,
        notes=notes,
        created_at=at,
    )
    end = rules.standing_block_end(_block_rows(user_id))
    # Not `save()`: only this column, and `User.save` never writes it (Part 11C).
    User.objects.filter(pk=user_id).update(emergency_blocked_until=end)
    return entry


def _require_transaction():
    if not transaction.get_connection().in_atomic_block:
        raise RuntimeError("the emergency block runs inside the caller's transaction")


def block_after_emergency_false(post, rows, *, now, moderator):
    """Block the author's emergency posting for `emergency_false_cooldown_days` when the ledger
    rows `settle_post` just wrote hold the author's `emergency_false` (§4b: any FALSE label on an
    emergency, the pipeline's after expiry or demotion included). A re-sent verdict, an upheld
    label appeal or a Dismiss back to FALSE writes no such row, so a post never blocks twice.
    `moderator` is None for the pipeline. Returns the block row, or None.

    Inside the caller's transaction (the pipeline's is durable), after `settle_post`: the post is
    locked, and so is the author, whose row it wrote. A setting of 0 days blocks nothing.
    """
    if not any(r.kind == EventKind.EMERGENCY_FALSE and r.user_id == post.author_id for r in rows):
        return None
    _require_transaction()
    days = get_platform_settings().emergency_false_cooldown_days
    if days <= 0:
        return None
    _lock_account(post.author_id)
    return _write_block_row(
        post.author_id,
        post=post,
        moderator=moderator,
        action=ActionKind.EMERGENCY_BLOCKED,
        now=now,
        notes="Automatic: the emergency post was labelled FALSE.",
        days=days,
    )


def lift_after_overturn(post, rows, *, now, moderator):
    """Lift the block a post's FALSE label brought when that label is overturned (user decision
    2026-10-19): `settle_post` just reversed the author's `emergency_false` row. Another block that
    still stands (a manual one, another FALSE emergency) keeps the account blocked. A Restore
    reverses only the removal's rows, so it lifts nothing. Returns the unblock row, or None.

    A reversal row doesn't carry the kind of the row it reverses: one primary-key lookup, made
    only when the author's own rows were reversed.
    """
    reversed_ids = [
        r.reverses_id for r in rows if r.kind == EventKind.REVERSAL and r.user_id == post.author_id
    ]
    if not reversed_ids:
        return None
    if not ReputationEvent.objects.filter(
        pk__in=reversed_ids, kind=EventKind.EMERGENCY_FALSE
    ).exists():
        return None
    _require_transaction()
    _lock_account(post.author_id)
    standing = rules.standing_blocks(_block_rows(post.author_id))
    if not any(block.post_id == post.pk for block in standing):
        return None
    return _write_block_row(
        post.author_id,
        post=post,
        moderator=moderator,
        action=ActionKind.EMERGENCY_UNBLOCKED,
        now=now,
        notes="Automatic: the FALSE label was overturned.",
    )


def _write_photo_row(user_id, *, moderator, action, at, notes):
    """Append one `avatar_*` row about the account (no post); the caller holds its lock."""
    return ModerationAction.objects.create(
        post=None,
        subject_user_id=user_id,
        post_snapshot="",
        moderator=moderator,
        action=action,
        notes=notes,
        created_at=at,
    )


def _photo_action(act, target, *, moderator, notes, now):
    """The three photo actions (Part 14B), inside `_account_action`'s transaction and lock.

    Block photo uploads also takes down the current photo (user decision 2026-10-21), logged as
    `avatar_removed` and then `avatar_blocked`, 1 µs apart so the log reads in that order.
    """
    write = {"moderator": moderator, "notes": notes}
    if act == rules.AccountAct.REMOVE_PHOTO:
        avatars.delete_photo(target.pk)
        return _write_photo_row(target.pk, action=ActionKind.AVATAR_REMOVED, at=now, **write)
    if act == rules.AccountAct.ALLOW_PHOTO_UPLOADS:
        User.objects.filter(pk=target.pk).update(avatar_uploads_blocked=False)
        return _write_photo_row(target.pk, action=ActionKind.AVATAR_UNBLOCKED, at=now, **write)
    at = now
    if target.avatar_version:
        avatars.delete_photo(target.pk)
        _write_photo_row(target.pk, action=ActionKind.AVATAR_REMOVED, at=at, **write)
        at += _TICK
    User.objects.filter(pk=target.pk).update(avatar_uploads_blocked=True)
    return _write_photo_row(target.pk, action=ActionKind.AVATAR_BLOCKED, at=at, **write)


def _account_action(act, user_id, *, moderator, notes, now):
    with transaction.atomic():
        target = _lock_account(user_id)
        # After the lock, not before: the time is when it really happened.
        now = now or timezone.now()
        if target is None:
            raise ActionRefused(rules.NO_ACCOUNT)
        days = (
            get_platform_settings().emergency_false_cooldown_days
            if act in rules.EMERGENCY_ACTS
            else 0
        )
        refusal = rules.account_refusal(act, target, moderator, block_days=days, now=now)
        if refusal is not None:
            raise ActionRefused(refusal)
        if act in rules.PHOTO_ACTS:
            return _photo_action(act, target, moderator=moderator, notes=notes, now=now)
        if act == rules.AccountAct.BLOCK_EMERGENCY:
            return _write_block_row(
                target.pk,
                post=None,
                moderator=moderator,
                action=ActionKind.EMERGENCY_BLOCKED,
                now=now,
                notes=notes,
                days=days,
            )
        return _write_block_row(
            target.pk,
            post=None,
            moderator=moderator,
            action=ActionKind.EMERGENCY_UNBLOCKED,
            now=now,
            notes=notes,
        )


def block_emergency_posting(user_id, *, moderator, notes="", now=None):
    """A moderator blocks an account's emergency posting for `emergency_false_cooldown_days`, as
    long as a FALSE emergency would (user decision 2026-10-19). Logged `emergency_blocked` with
    `subject_user` and no post. Refusals (`rules.account_refusal`) raise `ActionRefused`."""
    return _account_action(
        rules.AccountAct.BLOCK_EMERGENCY, user_id, moderator=moderator, notes=notes, now=now
    )


def unblock_emergency_posting(user_id, *, moderator, notes="", now=None):
    """A moderator lifts every block on an account's emergency posting early, automatic ones
    included. Logged `emergency_unblocked` with `subject_user` and no post."""
    return _account_action(
        rules.AccountAct.UNBLOCK_EMERGENCY, user_id, moderator=moderator, notes=notes, now=now
    )


def remove_photo(user_id, *, moderator, notes="", now=None):
    """A moderator takes down an account's profile photo: initials show everywhere at once.
    Logged `avatar_removed` with `subject_user` and no post. The account may upload another one
    unless uploads are blocked too. Refusals (`rules.account_refusal`) raise `ActionRefused`."""
    return _account_action(
        rules.AccountAct.REMOVE_PHOTO, user_id, moderator=moderator, notes=notes, now=now
    )


def block_photo_uploads(user_id, *, moderator, notes="", now=None):
    """A moderator turns off photo uploads for an account and takes down its current photo (user
    decision 2026-10-21). Logged `avatar_removed` (when there was a photo) and then
    `avatar_blocked`; returns the `avatar_blocked` row. Uploads then answer 403 until someone
    allows them again."""
    return _account_action(
        rules.AccountAct.BLOCK_PHOTO_UPLOADS, user_id, moderator=moderator, notes=notes, now=now
    )


def allow_photo_uploads(user_id, *, moderator, notes="", now=None):
    """A moderator lifts a photo-upload block. Logged `avatar_unblocked`. The photo that was taken
    down stays gone: the account uploads a new one."""
    return _account_action(
        rules.AccountAct.ALLOW_PHOTO_UPLOADS, user_id, moderator=moderator, notes=notes, now=now
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
