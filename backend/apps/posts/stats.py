"""`GET /api/v1/posts/{id}/stats/`: how a fact post was checked and how it spread (Part 11D).

The builders here are pure: they take the rows the view loaded and never read the clock, so the
bucket edges (UTC midnight, the 14-day window) are tested with given times.
"""

from datetime import UTC, datetime, time, timedelta

from apps.posts.models import PostStatus, VerdictSource
from apps.posts.serializers import iso, shown_confidence, shown_verdict_source

DAYS = 14
SERIES = ("reposts", "likes", "comments")
_LABELLED = (PostStatus.VERIFIED_TRUE, PostStatus.VERIFIED_FALSE)


def window(created_at):
    """The UTC midnight that opens day 0 (the post's own UTC date) and the one that closes day
    13: the first `DAYS` calendar days, the first of them partial."""
    start = datetime.combine(created_at.astimezone(UTC).date(), time.min, tzinfo=UTC)
    return start, start + timedelta(days=DAYS)


def daily_buckets(created_at, counts):
    """Exactly `DAYS` entries `{date, reposts, likes, comments}`, zero-filled. `counts` maps
    `(series, date)` to a number; a date outside the window is ignored."""
    start, _ = window(created_at)
    first = start.date()
    buckets = []
    for offset in range(DAYS):
        day = first + timedelta(days=offset)
        buckets.append(
            {"date": day.isoformat(), **{name: counts.get((name, day), 0) for name in SERIES}}
        )
    return buckets


def verdict_at(post):
    """When the label was decided, only for a labelled post: the pipeline's check time, or the
    moderator's audit row (`moderator_verdict_at`, not `moderated_at`, which every later moderator
    action overwrites). None when there is no time to show."""
    if post.status not in _LABELLED:
        return None
    if post.verdict_source == VerdictSource.PIPELINE:
        return post.pipeline_checked_at
    return getattr(post, "moderator_verdict_at", None)


def seconds_to_verdict(post, decided_at):
    if decided_at is None:
        return None
    return max(0, int((decided_at - post.created_at).total_seconds()))


def stats_data(post, counts, threshold):
    """The 6-key payload. `threshold` is today's `confidence_threshold`, shown only next to a
    confidence the post itself shows (a pipeline label)."""
    decided_at = verdict_at(post)
    confidence = shown_confidence(post)
    return {
        "confidence_score": confidence,
        "confidence_threshold": None if confidence is None else threshold,
        "verdict_source": shown_verdict_source(post),
        "seconds_to_verdict": seconds_to_verdict(post, decided_at),
        "verdict_at": iso(decided_at),
        "daily": daily_buckets(post.created_at, counts),
    }
