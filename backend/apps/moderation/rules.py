"""What a moderator may do to a post, and what each action changes (ARCHITECTURE §4, §8).

Pure: no database, no clock. `refusal()` says why an action can't be taken on a post (or None),
`transition()` applies one to a post in memory. `apps/moderation/services.py` calls both inside
`transaction.atomic()` with the post row locked, and does every write. The admin calls `refusal()`
too, to decide which buttons and rows to offer.

The five actions are the ones Part 10 builds. Part 11 adds Restore and Keep removed, Part 11C
Demote emergency.
"""

import enum
from dataclasses import dataclass

from apps.moderation.models import ActionKind
from apps.posts.models import FlaggedReason, PostStatus, PostType, VerdictSource
from apps.reports.models import ReportStatus


class Act(enum.StrEnum):
    MARK_VERIFIED = "mark_verified"
    MARK_FALSE = "mark_false"
    DISMISS_REPORTS = "dismiss_reports"
    REMOVE = "remove"
    ESCALATE = "escalate"


VERDICT_ACTS = (Act.MARK_VERIFIED, Act.MARK_FALSE)

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


@dataclass(frozen=True)
class Effect:
    """What `transition` did: the audit row's kind and statuses, and what happens to the post's
    open reports (a `ReportStatus`, or None to leave them alone)."""

    kind: str
    from_status: str
    to_status: str
    report_status: str | None


def can_return_to(post):
    """Whether `post.pre_review_status` is a status this post could go back to (see above)."""
    return post.pre_review_status in _RETURNABLE[post.post_type]


def refusal(act, post, moderator):
    """Why `moderator` can't do `act` to `post`, or None. Checked in this order."""
    if post.deleted_at is not None:
        return DELETED
    if post.author_id == moderator.pk and not moderator.is_superuser:
        return OWN_POST
    if act in VERDICT_ACTS and post.post_type != PostType.FACT:
        return OPINION
    if act != Act.REMOVE and post.status != PostStatus.UNDER_REVIEW:
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
    if act == Act.ESCALATE and post.escalated_at is not None:
        return ALREADY_ESCALATED
    return None


def _leave_review(post):
    """The review is over: the flag, the saved status, the clock and the escalation go (a later
    review must not look old or escalated; the audit trail keeps the `escalated` row)."""
    post.flagged_reason = None
    post.pre_review_status = None
    post.review_started_at = None
    post.escalated_at = None


def transition(act, post, *, moderator, now, public_note=""):
    """Apply `act` to `post` in memory (the caller has checked `refusal`) and return its `Effect`.

    Only these fields change: `status`, `flagged_reason`, `pre_review_status`,
    `pre_removal_status`, `review_started_at`, `escalated_at`, `verdict_source`, `verdict_note`,
    `moderated_by` and `moderated_at` (the services add `updated_at` by saving). **No `pipeline_*`
    field and no `confidence_score`** is touched: `pipeline_attempts` is Part 9's claim token, so a
    moderator can't make an in-flight answer be dropped or applied.
    """
    from_status = post.status
    report_status = None
    if act in VERDICT_ACTS:
        verified = act == Act.MARK_VERIFIED
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
    elif act == Act.ESCALATE:
        post.escalated_at = now
        kind = ActionKind.ESCALATED
    else:
        raise ValueError(f"not an action: {act!r}")
    post.moderated_by = moderator
    post.moderated_at = now
    return Effect(kind, from_status, post.status, report_status)
