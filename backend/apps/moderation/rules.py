"""What a moderator may do to a post, and what each action changes (ARCHITECTURE §4, §8).

Pure: no database, no clock. `refusal()` says why an action can't be taken on a post (or None),
`transition()` applies one to a post in memory. `apps/moderation/services.py` calls both inside
`transaction.atomic()` with the post row locked, and does every write. The admin calls `refusal()`
too, to decide which buttons and rows to offer.

The first five actions are the ones Part 10 builds. Part 11 adds Restore and Keep removed (the
two ways to resolve a removal appeal) and the appeal rules; Part 11C adds Demote emergency, the
emergency effects of Mark FALSE, the two account acts (Block / Unblock emergency posting) and the
rule that says how long an account's emergency posting stays blocked (`standing_block_end`).

**Time.** `now` is a required keyword of `refusal`, as `appeal` is: whether a post is an active
emergency depends on it, and a call site that forgot it must fail loudly.

**Appeals.** `appeal` is the post's *open* appeal, or None, and a required keyword everywhere:
whether an action resolves an appeal comes from it, never from `flagged_reason` alone (a flagged
post with no appeal row must not crash). Reading `post.appeal` can query, so the caller finds it.
"""

import enum
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import NamedTuple
from uuid import UUID

from apps.accounts.models import Role
from apps.moderation.models import ActionKind, AppealKind, AppealStatus
from apps.pipeline import routing
from apps.posts.emergency import is_active_emergency
from apps.posts.models import FlaggedReason, PostStatus, PostType, VerdictSource
from apps.reports.models import ReportStatus


class Act(enum.StrEnum):
    MARK_VERIFIED = "mark_verified"
    MARK_FALSE = "mark_false"
    DISMISS_REPORTS = "dismiss_reports"
    REMOVE = "remove"
    ESCALATE = "escalate"
    RESTORE = "restore"
    KEEP_REMOVED = "keep_removed"
    DEMOTE_EMERGENCY = "demote_emergency"


VERDICT_ACTS = (Act.MARK_VERIFIED, Act.MARK_FALSE)
REMOVAL_APPEAL_ACTS = (Act.RESTORE, Act.KEEP_REMOVED)

# An appeal must be resolved by someone other than who made the call, unless the resolver is a
# senior moderator or a superuser (ARCHITECTURE §4).
APPEAL_REQUIRE_DIFFERENT_MODERATOR = True

# The status a post could go back to when its review ends without a verdict. An opinion has one
# state to return to; a fact never goes back to `published` (the database refuses it), and an
# opinion never to a fact status.
_RETURNABLE = {
    PostType.OPINION: (PostStatus.PUBLISHED,),
    PostType.FACT: (PostStatus.PENDING, PostStatus.VERIFIED_TRUE, PostStatus.VERIFIED_FALSE),
}


@dataclass(frozen=True)
class Refusal:
    code: str
    text: str


DELETED = Refusal("deleted", "deleted by its author")
OWN_POST = Refusal("own_post", "your own post")
OPINION = Refusal("opinion", "opinion: no verdict")
NOT_UNDER_REVIEW = Refusal("not_under_review", "not under review")
NO_REPORTS = Refusal("no_reports", "no reports to dismiss")
NO_PRIOR_STATUS = Refusal("no_prior_status", "no status to return to")
ALREADY_REMOVED = Refusal("already_removed", "already removed")
ALREADY_ESCALATED = Refusal("already_escalated", "already escalated")
NO_REMOVAL_APPEAL = Refusal("no_removal_appeal", "no open removal appeal")
ORIGINAL_MODERATOR = Refusal("original_moderator", "you made the first decision")
NOT_ACTIVE_EMERGENCY = Refusal("not_active_emergency", "not an active emergency")


@dataclass(frozen=True)
class Effect:
    """What `transition` did: the audit row's kind and statuses, what happens to the post's open
    reports (a `ReportStatus`, or None to leave them alone) and to its open appeal (an
    `AppealStatus` it is resolved as, or None when this action resolves none).

    `credits_reporters` (Part 11B): whether the reporters whose open reports this action upholds
    earn a `report_upheld` credit. Only when the decision changed the post (user decision
    2026-10-13): Remove always; Mark FALSE unless the post was already FALSE before the review (a
    pipeline FALSE that reports sent to review, or a label appeal).

    `demoted` (Part 11C): a Mark FALSE ended an active emergency's priority, so the services log
    an `emergency_demoted` row after the action's own (Demote's own row is its `kind`)."""

    kind: str
    from_status: str
    to_status: str
    report_status: str | None
    appeal_status: str | None = None
    credits_reporters: bool = False
    demoted: bool = False


def can_return_to(post):
    """Whether `post.pre_review_status` is a status this post could go back to (see above)."""
    return post.pre_review_status in _RETURNABLE[post.post_type]


def _open_appeal(appeal, kind):
    return appeal is not None and appeal.status == AppealStatus.OPEN and appeal.kind == kind


def resolves_appeal(act, post, appeal):
    """Whether `act` on `post` would close its open `appeal`: a verdict or Remove on a label
    appeal (the post is under review for it), Restore or Keep removed on a removal appeal."""
    if act in REMOVAL_APPEAL_ACTS:
        return _open_appeal(appeal, AppealKind.REMOVAL)
    if act in (*VERDICT_ACTS, Act.REMOVE):
        return post.status == PostStatus.UNDER_REVIEW and _open_appeal(appeal, AppealKind.LABEL)
    return False


def _made_the_first_decision(appeal, moderator):
    if not APPEAL_REQUIRE_DIFFERENT_MODERATOR or appeal.original_moderator_id != moderator.pk:
        return False
    return not (moderator.is_superuser or moderator.role == Role.SENIOR_MODERATOR)


def refusal(act, post, moderator, *, appeal, now):
    """Why `moderator` can't do `act` to `post` at `now`, or None. Checked in this order."""
    if post.deleted_at is not None:
        return DELETED
    if post.author_id == moderator.pk and not moderator.is_superuser:
        return OWN_POST
    if act == Act.DEMOTE_EMERGENCY:
        # Any status: a removed post is never active, and Demote resolves no appeal.
        return None if is_active_emergency(post, now) else NOT_ACTIVE_EMERGENCY
    if act in VERDICT_ACTS and post.post_type != PostType.FACT:
        return OPINION
    if act in REMOVAL_APPEAL_ACTS:
        if post.status != PostStatus.REMOVED or not _open_appeal(appeal, AppealKind.REMOVAL):
            return NO_REMOVAL_APPEAL
    elif act == Act.ESCALATE:
        removal_appeal = post.status == PostStatus.REMOVED and _open_appeal(
            appeal, AppealKind.REMOVAL
        )
        if post.status != PostStatus.UNDER_REVIEW and not removal_appeal:
            return NOT_UNDER_REVIEW
    elif act != Act.REMOVE and post.status != PostStatus.UNDER_REVIEW:
        return NOT_UNDER_REVIEW
    if act == Act.DISMISS_REPORTS:
        if post.flagged_reason not in (FlaggedReason.REPORTS, FlaggedReason.BOTH):
            return NO_REPORTS
        if post.flagged_reason == FlaggedReason.REPORTS and not can_return_to(post):
            return NO_PRIOR_STATUS
    if act == Act.REMOVE:
        if post.status == PostStatus.REMOVED:
            return ALREADY_REMOVED
        if post.status == PostStatus.UNDER_REVIEW and not can_return_to(post):
            return NO_PRIOR_STATUS
    if act == Act.RESTORE and post.pre_removal_status not in _RETURNABLE[post.post_type]:
        return NO_PRIOR_STATUS
    if act == Act.ESCALATE and post.escalated_at is not None:
        return ALREADY_ESCALATED
    # Escalating resolves nothing (`resolves_appeal` is False for it), so the first moderator may.
    if resolves_appeal(act, post, appeal) and _made_the_first_decision(appeal, moderator):
        return ORIGINAL_MODERATOR
    return None


def _leave_review(post):
    """The review is over: the flag, the saved status, the clock and the escalation go (a later
    review must not look old or escalated; the audit trail keeps the `escalated` row)."""
    post.flagged_reason = None
    post.pre_review_status = None
    post.review_started_at = None
    post.escalated_at = None


def _restore(post, now):
    """Put a removed post back to the status it had (`pre_removal_status`).

    A fact the pipeline had already checked and left to a moderator (`pending` with its say made)
    isn't checked again: it goes under review for the pipeline, and a moderator gives the label
    (user decision 2026-10-13). A fact it never finished goes back to `pending` and is checked as
    usual. The verdict fields and every `pipeline_*` field stay as they were.
    """
    target = post.pre_removal_status
    post.pre_removal_status = None
    post.escalated_at = None
    if target == PostStatus.PENDING and routing.pipeline_had_its_say(post):
        post.status = PostStatus.PENDING
        post.flagged_reason = None
        routing.enter_review(post, FlaggedReason.PIPELINE, now)
        return
    post.status = target
    post.flagged_reason = None


def transition(act, post, *, moderator, now, appeal, public_note=""):
    """Apply `act` to `post` in memory (the caller has checked `refusal`) and return its `Effect`.

    Only these fields change: `status`, `flagged_reason`, `pre_review_status`,
    `pre_removal_status`, `review_started_at`, `escalated_at`, `verdict_source`, `verdict_note`,
    `emergency_demoted_at`, `moderated_by` and `moderated_at` (the services add `updated_at` by
    saving). **No `pipeline_*` field and no `confidence_score`** is touched: `pipeline_attempts` is
    Part 9's claim token, so a moderator can't make an in-flight answer be dropped or applied.

    Part 11C: Mark FALSE on an active emergency also ends its priority (`emergency_demoted_at`,
    `Effect.demoted`); Demote does only that. Mark verified, Dismiss, Remove and Escalate leave the
    priority alone (a removed post is never active, and a Restore inside the 24 hours pins it
    again: its removal was the mistake).

    `appeal` is the post's open appeal (see the module text). `Effect.appeal_status` says how the
    action closes it: Mark verified overturns a label appeal, Mark FALSE and Remove uphold it
    (Remove on a post under a label appeal is a decision, user decision 2026-10-13), Restore
    overturns a removal appeal and Keep removed upholds it.
    """
    from_status = post.status
    report_status = None
    appeal_status = None
    credits_reporters = False
    demoted = False
    if resolves_appeal(act, post, appeal):
        appeal_status = (
            AppealStatus.OVERTURNED
            if act in (Act.MARK_VERIFIED, Act.RESTORE)
            else AppealStatus.UPHELD
        )
    if act in VERDICT_ACTS:
        verified = act == Act.MARK_VERIFIED
        # Read before the review fields are cleared: a post that was FALSE already isn't changed.
        credits_reporters = not verified and post.pre_review_status != PostStatus.VERIFIED_FALSE
        # Read before the status changes: a FALSE always ends an active emergency's priority.
        demoted = not verified and is_active_emergency(post, now)
        if demoted:
            post.emergency_demoted_at = now
        post.status = PostStatus.VERIFIED_TRUE if verified else PostStatus.VERIFIED_FALSE
        post.verdict_source = VerdictSource.MODERATOR
        post.verdict_note = public_note
        _leave_review(post)
        kind = ActionKind.VERIFIED if verified else ActionKind.MARKED_FALSE
        report_status = ReportStatus.ACTIONED
    elif act == Act.DISMISS_REPORTS:
        if post.flagged_reason == FlaggedReason.REPORTS:
            post.status = post.pre_review_status
            _leave_review(post)
        else:
            # Also flagged by the pipeline: only the reports go away, a moderator still decides.
            post.flagged_reason = FlaggedReason.PIPELINE
        kind = ActionKind.DISMISSED_REPORT
        report_status = ReportStatus.DISMISSED
    elif act == Act.REMOVE:
        post.pre_removal_status = (
            post.pre_review_status if post.status == PostStatus.UNDER_REVIEW else post.status
        )
        post.status = PostStatus.REMOVED
        _leave_review(post)
        kind = ActionKind.REMOVED
        report_status = ReportStatus.ACTIONED
        credits_reporters = True
    elif act == Act.ESCALATE:
        post.escalated_at = now
        kind = ActionKind.ESCALATED
    elif act == Act.RESTORE:
        _restore(post, now)
        kind = ActionKind.RESTORED
    elif act == Act.KEEP_REMOVED:
        post.flagged_reason = None
        post.escalated_at = None
        kind = ActionKind.KEPT_REMOVED
    elif act == Act.DEMOTE_EMERGENCY:
        # The priority ends early; the label, the review and the reports stay as they are.
        post.emergency_demoted_at = now
        kind = ActionKind.EMERGENCY_DEMOTED
    else:
        raise ValueError(f"not an action: {act!r}")
    post.moderated_by = moderator
    post.moderated_at = now
    return Effect(
        kind, from_status, post.status, report_status, appeal_status, credits_reporters, demoted
    )


# ---------- Part 11C: blocking an account's emergency posting ----------


class AccountAct(enum.StrEnum):
    BLOCK_EMERGENCY = "block_emergency"
    UNBLOCK_EMERGENCY = "unblock_emergency"


NO_ACCOUNT = Refusal("no_account", "no such account")
SUPERUSER_ACCOUNT = Refusal("superuser_account", "a superuser's account")
OWN_ACCOUNT = Refusal("own_account", "your own account")
NO_BLOCK_LENGTH = Refusal("no_block_length", "the block length is 0 days")
ALREADY_BLOCKED = Refusal("already_blocked", "already blocked at least that long")
NOT_BLOCKED = Refusal("not_blocked", "not blocked")


def account_refusal(act, target, moderator, *, block_days, now):
    """Why `moderator` can't block or unblock `target`'s emergency posting at `now`, or None.

    Nobody but a superuser may act on a superuser's account or their own (`UserAdmin._may_touch`'s
    rule). A Block lasts `block_days` (the platform's `emergency_false_cooldown_days`): refused
    when that is 0, or when the current block already ends at or after `now + block_days`. An
    Unblock needs a block that hasn't ended. `target` is the account's locked row.
    """
    if not moderator.is_superuser:
        if target.is_superuser:
            return SUPERUSER_ACCOUNT
        if target.pk == moderator.pk:
            return OWN_ACCOUNT
    blocked_until = target.emergency_blocked_until
    if act == AccountAct.BLOCK_EMERGENCY:
        if block_days <= 0:
            return NO_BLOCK_LENGTH
        if blocked_until is not None and blocked_until >= now + timedelta(days=block_days):
            return ALREADY_BLOCKED
        return None
    if act == AccountAct.UNBLOCK_EMERGENCY:
        if blocked_until is None or blocked_until <= now:
            return NOT_BLOCKED
        return None
    raise ValueError(f"not an account action: {act!r}")


class BlockRow(NamedTuple):
    """What `standing_block_end` reads of an `emergency_blocked` / `emergency_unblocked` row."""

    action: str
    post_id: UUID | None
    blocked_until: datetime | None


def standing_blocks(rows):
    """The blocks still standing after an account's block and unblock `rows` (in time order).

    A block stands until an unblock lifts it. An unblock with no post (a moderator's Unblock) lifts
    every block before it; an unblock with post P (the automatic lift when P's FALSE label is
    overturned) lifts P's own blocks only, so a manual block or another FALSE emergency still
    stands. A post-linked row loses its post only when the post is hard-deleted, which happens only
    with the account (ARCHITECTURE §2), so a row with no post is a manual one.
    """
    standing = []
    for row in rows:
        if row.action == ActionKind.EMERGENCY_BLOCKED:
            standing.append(row)
        elif row.action == ActionKind.EMERGENCY_UNBLOCKED:
            if row.post_id is None:
                standing = []
            else:
                standing = [block for block in standing if block.post_id != row.post_id]
    return standing


def standing_block_end(rows):
    """When the account's emergency posting is free again: the latest end among the blocks still
    standing, or None. `users.emergency_blocked_until` always equals this; an end in the past is
    harmless (the eligibility rule compares it with `now`)."""
    return max((block.blocked_until for block in standing_blocks(rows)), default=None)
