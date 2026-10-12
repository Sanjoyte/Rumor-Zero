"""The pure routing functions (ARCHITECTURE §4): no I/O, no clock, no database.

They only read and write fields on the `post` they are given. The services that own the status
write (`apps/posts/services.py`, and `apps/moderation/services.py` from Part 10) call them inside
`transaction.atomic()` with the post row locked, so nothing here saves anything. `now` is a
parameter everywhere so tests control time. Part 8 built the report half and Part 9 the pipeline
half; Part 11C adds the emergency branches. `is_active_emergency` lives in
`apps/posts/emergency.py`, because `posts` can't import this app (it would be circular).
"""

import enum
from datetime import timedelta

from django.db.models import Q

from apps.posts.models import FlaggedReason, PipelineVerdict, PostStatus, PostType, VerdictSource

# A failing check is tried this many times in all (each claim counts one), then a moderator decides.
MAX_ATTEMPTS = 5
_BACKOFF_CAP = timedelta(minutes=60)


class Outcome(enum.StrEnum):
    """What a pipeline result or failure did to a post. Part 13 notifies the author on `LABELLED`
    (a verdict) and `ENTERED_REVIEW`."""

    IGNORED = "ignored"  # the post isn't waiting for a check any more: nothing was written
    LABELLED = "labelled"
    ENTERED_REVIEW = "entered_review"
    UPDATED_REVIEW = (
        "updated_review"  # already under review for reports: the reason or the label kept
    )
    RETRY = "retry"


# What can happen to a post, as opposed to the merged state `both`.
_EVENTS = (FlaggedReason.PIPELINE, FlaggedReason.REPORTS, FlaggedReason.APPEAL)


def merge_flag(existing, new):
    """The `flagged_reason` of a post that is flagged for `new` while `existing` is already set.

    `None` + x = x; x + x = x; pipeline + reports (either way round) = both; `both` stays
    `both`; `appeal` stays `appeal`. A post already under review for the pipeline, reports or
    both can't get an appeal (a label appeal starts from a FALSE post, a removal appeal from a
    removed one): that is a bug in the caller, so it raises `ValueError`, as does anything that
    isn't a flag.
    """
    if new not in _EVENTS:
        raise ValueError(f"not a reason to flag a post: {new!r}")
    if existing is None:
        return new
    if existing not in FlaggedReason.values:
        raise ValueError(f"not a flagged reason: {existing!r}")
    if existing == FlaggedReason.APPEAL:
        return FlaggedReason.APPEAL
    if new == FlaggedReason.APPEAL:
        raise ValueError(f"a post under review for {existing!r} can't be flagged for an appeal")
    if existing == new:
        return existing
    return FlaggedReason.BOTH


def enter_review(post, reason, now):
    """Send `post` to the moderators, remembering what it was so a dismissal can restore it.

    Entering starts the queue's clock (`review_started_at = now`). Already under review: only the
    reason is merged (the status it came from, and how long it has waited, are kept).
    """
    if post.status == PostStatus.UNDER_REVIEW:
        post.flagged_reason = merge_flag(post.flagged_reason, reason)
    else:
        post.pre_review_status = post.status
        post.status = PostStatus.UNDER_REVIEW
        post.flagged_reason = reason
        post.review_started_at = now


def apply_report_threshold(post, counting_reports, cfg, now):
    """Move `post` to review when `counting_reports` has reached the report threshold.

    `counting_reports` is the windowed count of its open, counting reports, the new one included
    (§5). A removed post is never touched. A post that is already under review only has its
    reason merged. Returns True when the post **entered** review on this call (the moment Part 13
    tells its author), False otherwise. `now` starts the queue's clock; Part 11C also uses it,
    where an active emergency uses `cfg.emergency_report_threshold` instead.
    """
    if post.status == PostStatus.REMOVED or counting_reports < cfg.report_threshold:
        return False
    was_under_review = post.status == PostStatus.UNDER_REVIEW
    enter_review(post, FlaggedReason.REPORTS, now)
    return not was_under_review


# ---------- The pipeline (Part 9) ----------


def awaiting_check_q():
    """The posts the pipeline still owes a check, as a query (the queue adds "due").

    A fact the author hasn't deleted and nobody has decided, that is either `pending`, or under
    review **for reports only** while it was still `pending` (reports can arrive before the check,
    §4). Every way a check ends changes the status, the reason or `pre_review_status`, so a post
    leaves this set as soon as its check is over. `is_awaiting_check` is the same rule in Python.
    """
    return Q(post_type=PostType.FACT, deleted_at__isnull=True, verdict_source__isnull=True) & (
        Q(status=PostStatus.PENDING)
        | Q(
            status=PostStatus.UNDER_REVIEW,
            flagged_reason=FlaggedReason.REPORTS,
            pre_review_status=PostStatus.PENDING,
        )
    )


def is_awaiting_check(post):
    """`awaiting_check_q()` for one post in memory: the guard of the two apply functions, so a
    result can never land on a post whose check is already over (a lease that ran out)."""
    return (
        post.post_type == PostType.FACT
        and post.deleted_at is None
        and post.verdict_source is None
        and (
            post.status == PostStatus.PENDING
            or (
                post.status == PostStatus.UNDER_REVIEW
                and post.flagged_reason == FlaggedReason.REPORTS
                and post.pre_review_status == PostStatus.PENDING
            )
        )
    )


def backoff(attempts):
    """How long to wait after the `attempts`-th failed try: 2^attempts minutes, at most 60 (§3)."""
    return min(timedelta(minutes=2 ** min(attempts, 6)), _BACKOFF_CAP)


def apply_pipeline_result(post, result, cfg, now):
    """Route a pipeline result (§4). Returns an `Outcome`.

    Ignored, with nothing written, unless the post is still waiting for a check: removed posts,
    moderator decisions and finished checks win. Otherwise the result is stored and:
    `pending` + decisive → the label (`verdict_source=pipeline`); `pending` + not decisive →
    under review for the pipeline. On a post already under review for reports (a "late" result) a
    decisive TRUE becomes `pre_review_status=verified_true` (dismissing the reports restores it);
    a decisive FALSE or a weak result makes the reason `both`, so a moderator decides (user
    decision 2026-10-11: no hidden FALSE is ever stored). Decisive = true/false with
    `confidence ≥ cfg.confidence_threshold`. Part 11C adds the emergency rule (`now`).
    """
    if not is_awaiting_check(post):
        return Outcome.IGNORED
    post.pipeline_verdict = result.verdict
    post.confidence_score = result.confidence_score
    post.pipeline_result = result.raw_result
    post.pipeline_checked_at = now
    post.pipeline_next_attempt_at = None
    decisive = (
        result.verdict in (PipelineVerdict.TRUE, PipelineVerdict.FALSE)
        and result.confidence_score >= cfg.confidence_threshold
    )
    if post.status == PostStatus.PENDING:
        if not decisive:
            enter_review(post, FlaggedReason.PIPELINE, now)
            return Outcome.ENTERED_REVIEW
        post.status = (
            PostStatus.VERIFIED_TRUE
            if result.verdict == PipelineVerdict.TRUE
            else PostStatus.VERIFIED_FALSE
        )
        post.verdict_source = VerdictSource.PIPELINE
        return Outcome.LABELLED
    if decisive and result.verdict == PipelineVerdict.TRUE:
        post.pre_review_status = PostStatus.VERIFIED_TRUE
        post.verdict_source = VerdictSource.PIPELINE
    else:
        post.flagged_reason = merge_flag(post.flagged_reason, FlaggedReason.PIPELINE)
    return Outcome.UPDATED_REVIEW


def apply_pipeline_failure(post, error, now):
    """Record a failed try (`error` has `kind` and `detail`). Returns an `Outcome`.

    The same guard as a result. The error is kept in `pipeline_result`; below `MAX_ATTEMPTS` the
    next try waits `backoff(attempts)`; at `MAX_ATTEMPTS` the pipeline gives up and a moderator
    decides: a `pending` post goes under review for the pipeline, a post under review for reports
    gets the reason `both`. `pipeline_attempts` was counted when the try was claimed.
    """
    if not is_awaiting_check(post):
        return Outcome.IGNORED
    post.pipeline_result = {
        "error": error.kind,
        "detail": error.detail,
        "attempt": post.pipeline_attempts,
    }
    if post.pipeline_attempts < MAX_ATTEMPTS:
        post.pipeline_next_attempt_at = now + backoff(post.pipeline_attempts)
        return Outcome.RETRY
    post.pipeline_next_attempt_at = None
    if post.status == PostStatus.PENDING:
        enter_review(post, FlaggedReason.PIPELINE, now)
        return Outcome.ENTERED_REVIEW
    post.flagged_reason = merge_flag(post.flagged_reason, FlaggedReason.PIPELINE)
    return Outcome.UPDATED_REVIEW
