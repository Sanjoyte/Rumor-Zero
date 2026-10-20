"""The pure emergency rules (ARCHITECTURE §4, §4b): whether a post is an active emergency, and
whether someone may post one now.

They live here, where Part 4's serializer already reads them, and not in `apps/pipeline/routing.py`
(Part 8): `apps/pipeline` sits above `posts` (its routing reads the post models and `posts.services`
calls it), so the post object can't depend on it. The routing branches import them. "Active" is
computed at read time from the stored columns: no job ever flips a flag.

No database and no clock: `now` is a parameter, and `refusal` is given the person's locked row and
their fact quota.
"""

import enum
from dataclasses import dataclass
from datetime import datetime, timedelta

from django.db.models import Q

from apps.posts.models import PostStatus

# The daily limit counts the emergencies of the rolling 24 hours, like the fact quota.
EMERGENCY_WINDOW = timedelta(hours=24)


def is_active_emergency(post, now):
    """True while an emergency is still pinned: not demoted, expired, removed or deleted."""
    return bool(
        post.is_emergency
        and post.emergency_demoted_at is None
        and post.emergency_expires_at is not None
        and now < post.emergency_expires_at
        and post.status != PostStatus.REMOVED
        and post.deleted_at is None
    )


def active_emergency_q(now):
    """`is_active_emergency` as a query: one rule in two forms (Part 9's pattern for the queue), and
    a test compares them over every state the database checks allow. `now` may be a value or an
    expression (`Now()`, the admin's ordering). A null expiry never compares greater."""
    return Q(
        is_emergency=True,
        emergency_demoted_at__isnull=True,
        emergency_expires_at__gt=now,
        deleted_at__isnull=True,
    ) & ~Q(status=PostStatus.REMOVED)


class EmergencyReason(enum.StrEnum):
    """Why someone may not post an emergency now (§4b), in the order the rules are checked."""

    UNVERIFIED = "unverified"
    ACCOUNT_TOO_NEW = "account_too_new"
    SCORE_TOO_LOW = "score_too_low"
    BLOCKED = "blocked"
    DAILY_LIMIT = "daily_limit"
    FACT_QUOTA = "fact_quota"


@dataclass(frozen=True)
class EmergencyRefusal:
    reason: EmergencyReason
    # When the rule stops refusing, or None when no time will (a paused limit, an unverified email,
    # a score that only better posts can raise).
    next_allowed_at: datetime | None


def refusal(user, *, quota, cfg, now):
    """Why `user` may not post an emergency at `now`, or None. The first failing rule wins.

    `user` is the author's locked row (`posts.services._lock_author`), so a block or a score that
    committed meanwhile is seen. `quota` is their `FactQuota`: its `emergency_times` are the
    emergencies of the rolling 24 hours, oldest first, deleted and removed ones included (the fact
    quota's principle). `cfg` is the platform settings.
    """
    if not user.is_email_verified:
        return EmergencyRefusal(EmergencyReason.UNVERIFIED, None)
    old_enough_at = user.created_at + timedelta(days=cfg.emergency_min_account_age_days)
    if old_enough_at > now:  # exactly N days old passes
        return EmergencyRefusal(EmergencyReason.ACCOUNT_TOO_NEW, old_enough_at)
    if user.reputation_score < cfg.emergency_min_reputation:
        # The stored score, public or not (§4a).
        return EmergencyRefusal(EmergencyReason.SCORE_TOO_LOW, None)
    blocked_until = user.emergency_blocked_until
    if blocked_until is not None and blocked_until > now:  # a block ending now is over
        return EmergencyRefusal(EmergencyReason.BLOCKED, blocked_until)
    limit = cfg.emergency_posts_per_day
    times = quota.emergency_times
    if len(times) >= limit:
        # The (used - limit + 1)-th oldest must age out first, which is right even after the limit
        # was lowered. A limit of 0 pauses emergencies: no time will do.
        next_at = times[len(times) - limit] + EMERGENCY_WINDOW if limit > 0 else None
        return EmergencyRefusal(EmergencyReason.DAILY_LIMIT, next_at)
    if quota.remaining == 0:
        # Emergencies are fact posts. `next_slot_at` is None while fact posts are paused.
        return EmergencyRefusal(EmergencyReason.FACT_QUOTA, quota.next_slot_at)
    return None


def _when(moment):
    return f"{moment:%b} {moment.day}, {moment:%Y} at {moment:%H:%M} UTC"


def refusal_text(refused, cfg):
    """The plain words of a refusal, for the 403's `detail`. The composer has its own copy for the
    toggle's hint; these are what a person reads when a post is refused after all."""
    reason, at = refused.reason, refused.next_allowed_at
    if reason == EmergencyReason.UNVERIFIED:
        return "Verify your email before posting an emergency."
    if reason == EmergencyReason.ACCOUNT_TOO_NEW:
        return f"Your account is too new to post an emergency. You can from {_when(at)}."
    if reason == EmergencyReason.SCORE_TOO_LOW:
        return (
            "Your credibility score is below "
            f"{cfg.emergency_min_reputation}, the minimum for emergency posts."
        )
    if reason == EmergencyReason.BLOCKED:
        return f"Emergency posting is blocked on your account until {_when(at)}."
    if reason == EmergencyReason.DAILY_LIMIT:
        if at is None:
            return "Emergency posts are paused right now."
        limit = cfg.emergency_posts_per_day
        return (
            f"You've posted {limit} emergency {'post' if limit == 1 else 'posts'} in the last "
            f"24 hours. You can post another from {_when(at)}."
        )
    if at is None:
        return "Fact posts are paused right now, so emergency posts are too."
    return (
        "You've used all your fact posts for the last 24 hours. "
        f"You can post another from {_when(at)}."
    )
