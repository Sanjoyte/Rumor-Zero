"""The pure routing functions (ARCHITECTURE §4): no I/O, no clock, no database.

They only read and write fields on the `post` they are given. The services that own the status
write (`apps/posts/services.py`, and `apps/moderation/services.py` from Part 10) call them inside
`transaction.atomic()` with the post row locked, so nothing here saves anything. `now` is a
parameter everywhere so tests control time. Part 8 holds the report half; Part 9 adds
`apply_pipeline_result` and Part 11C the emergency branches. `is_active_emergency` lives in
`apps/posts/emergency.py`, because `posts` can't import this app (it would be circular).
"""

from apps.posts.models import FlaggedReason, PostStatus

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


def enter_review(post, reason):
    """Send `post` to the moderators, remembering what it was so a dismissal can restore it.

    Already under review: only the reason is merged (the status it came from is kept).
    """
    if post.status == PostStatus.UNDER_REVIEW:
        post.flagged_reason = merge_flag(post.flagged_reason, reason)
    else:
        post.pre_review_status = post.status
        post.status = PostStatus.UNDER_REVIEW
        post.flagged_reason = reason


def apply_report_threshold(post, counting_reports, cfg, now):
    """Move `post` to review when `counting_reports` has reached the report threshold.

    `counting_reports` is the windowed count of its open, counting reports, the new one included
    (§5). A removed post is never touched. A post that is already under review only has its
    reason merged. Returns True when the post **entered** review on this call (the moment Part 13
    tells its author), False otherwise. `now` is unused until Part 11C, where an active emergency
    uses `cfg.emergency_report_threshold` instead.
    """
    if post.status == PostStatus.REMOVED or counting_reports < cfg.report_threshold:
        return False
    was_under_review = post.status == PostStatus.UNDER_REVIEW
    enter_review(post, FlaggedReason.REPORTS)
    return not was_under_review
