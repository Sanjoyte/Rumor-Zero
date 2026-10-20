"""Creating, deleting and reporting posts, the fact quota, and writing pipeline results
(ARCHITECTURE §3, §4, §4b, §5, §6). A pipeline label also settles the author's and the reposters'
credibility events (§4a) in the same transaction, and a FALSE emergency blocks its author's
emergency posting (§4b, through `apps/moderation/services.py`, the block's only writer). The
author is told of a label or a review (Part 13), also in that transaction.

Only this module and `apps/moderation/services.py` change `Post.status`. There is no HTTP
here: the views turn these domain errors into responses.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.core.services import get_platform_settings
from apps.notifications import services as notification_services
from apps.pipeline import routing
from apps.posts import emergency
from apps.posts.models import Post, PostStatus, PostType
from apps.reputation import services as reputation_services
from apps.social.feed import bust_following_feed

logger = logging.getLogger(__name__)

# The quota is a rolling window, not a calendar day (user decision 2026-10-08): a slot frees up 24
# hours after the post that used it. It counts every fact post made in the window, **including ones
# deleted or removed later**, or deleting and reposting would get around it.
FACT_QUOTA_WINDOW = timedelta(hours=24)


class EmergencyNotAllowed(Exception):
    """The author may not post an emergency now (§4b): `reason` is an `EmergencyReason`,
    `next_allowed_at` when that rule stops refusing (or None), `text` the plain words."""

    def __init__(self, refused, text):
        super().__init__(text)
        self.reason = refused.reason
        self.next_allowed_at = refused.next_allowed_at
        self.text = text


class FactPostsPaused(Exception):
    """`fact_posts_per_day` is 0: the platform setting doubles as a kill switch."""


class FactQuotaExceeded(Exception):
    def __init__(self, *, limit, next_slot_at):
        super().__init__(f"{limit} fact posts in 24 hours")
        self.limit = limit
        self.next_slot_at = next_slot_at


class PostNotFound(Exception):
    """No such post, or the author already deleted it (a deleted post is hidden everywhere)."""


class NotPostAuthor(Exception):
    """Only the author can delete a post."""


@dataclass(frozen=True)
class FactQuota:
    limit: int
    used: int
    remaining: int
    # When a slot frees up: set only when nothing is left and posting isn't paused (limit 0).
    next_slot_at: datetime | None
    # When each emergency of the same window was made, oldest first (§4b's daily limit, Part 11C).
    emergency_times: tuple = ()


def _lock_author(author):
    """Lock the author's row and return it fresh: the second of two fact posts counts after the
    first one's insert, and the emergency rules see a block, a score or a verification that
    committed meanwhile (Part 11C).

    `FOR NO KEY UPDATE`, the lock every writer of a user row takes (Part 11B's rule): it still
    serialises two posts, a block and `settle_post`, but not the `KEY SHARE` that every insert
    pointing at the author takes at commit. A separate function so the race test can switch it
    off and show what happens without it.
    """
    return (
        User.objects.select_for_update(no_key=True)
        .only(
            "pk", "created_at", "is_email_verified", "reputation_score", "emergency_blocked_until"
        )
        .get(pk=author.pk)
    )


def _fact_post_times(author, since):
    """`(created_at, is_emergency)` of each of the author's fact posts since `since`, oldest
    first. Deleted and removed posts are included on purpose. Separate so the race test can widen
    the window."""
    return list(
        Post.objects.filter(author=author, post_type=PostType.FACT, created_at__gt=since)
        .order_by("created_at")
        .values_list("created_at", "is_emergency")
    )


def fact_quota(user, *, now=None):
    """How many fact posts `user` has left in the rolling 24 hours, and when they posted their
    emergencies in it (at most one query)."""
    now = now or timezone.now()
    limit = get_platform_settings().fact_posts_per_day
    rows = _fact_post_times(user, now - FACT_QUOTA_WINDOW)
    times = [created_at for created_at, _ in rows]
    used = len(times)
    remaining = max(limit - used, 0)
    next_slot_at = None
    if limit > 0 and remaining == 0:
        # The (used - limit + 1)-th oldest post must age out before there is room again. That is
        # right even after the limit was lowered (used 8, limit 5: the 4th oldest).
        next_slot_at = times[used - limit] + FACT_QUOTA_WINDOW
    return FactQuota(
        limit=limit,
        used=used,
        remaining=remaining,
        next_slot_at=next_slot_at,
        emergency_times=tuple(created_at for created_at, urgent in rows if urgent),
    )


def emergency_refusal(user, *, quota, now):
    """Why `user` may not post an emergency now (`emergency.refusal`, §4b), or None."""
    return emergency.refusal(user, quota=quota, cfg=get_platform_settings(), now=now)


def create_post(*, author, content, post_type, sources=(), is_emergency=False, now=None):
    """Create an opinion (`published`) or a fact (`pending`). Raises the errors above.

    A fact shows "Checking facts…" until the pipeline answers. With `PIPELINE_INLINE_KICK` on, a
    background thread checks it right after the commit (§6); otherwise the sweeper does.

    An emergency (`is_emergency`, a fact only) is checked against §4b's rules under the author's
    lock, so two at once let one through and a block that committed first is seen; it stores
    `emergency_expires_at = now + emergency_duration_hours` (Part 11C). A refusal of any of its
    rules, a full fact quota included, is `EmergencyNotAllowed`.
    """
    now = now or timezone.now()
    sources = list(sources)
    if post_type != PostType.FACT and sources:
        # The serializer refuses this first; the DB check behind it is the last line.
        raise ValidationError({"sources": ["Only fact posts can have sources."]})
    if post_type != PostType.FACT and is_emergency:
        # The same: the serializer first, the check `posts_post_emergency_fact_only` last.
        raise ValidationError({"is_emergency": ["Only fact posts can be emergencies."]})
    expires_at = None
    with transaction.atomic():
        if post_type == PostType.FACT:
            locked = _lock_author(author)
            quota = fact_quota(locked, now=now)
            if is_emergency:
                cfg = get_platform_settings()
                refused = emergency.refusal(locked, quota=quota, cfg=cfg, now=now)
                if refused is not None:
                    raise EmergencyNotAllowed(refused, emergency.refusal_text(refused, cfg))
                expires_at = now + timedelta(hours=cfg.emergency_duration_hours)
            if quota.limit == 0:
                raise FactPostsPaused
            if quota.remaining == 0:
                raise FactQuotaExceeded(limit=quota.limit, next_slot_at=quota.next_slot_at)
            status = PostStatus.PENDING
        else:
            status = PostStatus.PUBLISHED
        post = Post.objects.create(
            author=author,
            content=content,
            post_type=post_type,
            sources=sources,
            status=status,
            is_emergency=is_emergency,
            emergency_expires_at=expires_at,
            created_at=now,
        )
        # Your own Following feed must show the new post at once, despite its cache (Part 6).
        bust_following_feed(author.pk)
        if post_type == PostType.FACT:
            kick_pipeline_after_commit(post.pk)
        return post


def kick_pipeline_after_commit(post_id):
    """With `PIPELINE_INLINE_KICK` on, check the fact in a background thread once the current
    transaction commits (§6). A new fact uses it, and so does a restored one that is `pending`
    again (`apps/moderation/services.py`); the sweeper is the fallback either way."""
    if settings.PIPELINE_INLINE_KICK:
        transaction.on_commit(lambda: _kick_pipeline(post_id))


def _kick_pipeline(post_id):
    """After the commit, check the new fact post in a background thread (the inline kick).

    It never raises: the post is already saved, and an error here would escape the commit and
    turn the 201 into a 500, so the client would post it again (a duplicate that uses quota). The
    import is local: `apps.pipeline.processor` imports this module.
    """
    try:
        from apps.pipeline.processor import start_kick

        start_kick(post_id)
    except Exception:
        logger.exception("Could not start the inline pipeline check of post %s", post_id)


def delete_post(*, post_id, user, now=None):
    """The author's soft delete (D6): `deleted_at` is set and nothing else changes.

    The status stays as it was, the row stays for the audit trail and the admin, and the post still
    counts toward the fact quota. The row is locked and re-read as "not deleted", so two
    simultaneous deletes give one success and one `PostNotFound`.
    """
    now = now or timezone.now()
    with transaction.atomic():
        post = (
            Post.objects.select_for_update()
            .not_deleted()
            .only("id", "author_id", "deleted_at", "updated_at")
            .filter(pk=post_id)
            .first()
        )
        if post is None:
            raise PostNotFound
        if post.author_id != user.pk:
            raise NotPostAuthor
        post.deleted_at = now
        post.save(update_fields=["deleted_at", "updated_at"])
        # Every notification about the post goes with it (Part 13): a plain DELETE, no new lock.
        notification_services.discard_for_post(post.pk)
    return post


def record_report(post, *, counting_reports, cfg, now):
    """Count one more report on `post` and send it to review if the threshold is reached (§5).

    `report_count` is the lifetime counter (every report, counting or not); `counting_reports` is
    the windowed count of open, counting ones that `apps/reports/services.py` just worked out, the
    new report included. The routing is the pure `apply_report_threshold`; this function owns the
    write, so every status change stays in `posts` and `moderation`. **The caller must hold the
    post's row lock inside `transaction.atomic()`:** two reports would otherwise both read the
    same `report_count` and miss the threshold together. Returns True when the post entered
    review on this call (Part 13 notifies its author then).
    """
    post.report_count += 1
    entered = routing.apply_report_threshold(post, counting_reports, cfg, now)
    post.save(
        update_fields=[
            "report_count",
            "status",
            "flagged_reason",
            "pre_review_status",
            "review_started_at",
            "updated_at",
        ]
    )
    return entered


# ---------- Pipeline results (Part 9; ARCHITECTURE §4, §6) ----------

_RESULT_FIELDS = [
    "status",
    "flagged_reason",
    "pre_review_status",
    "review_started_at",
    "verdict_source",
    "pipeline_verdict",
    "confidence_score",
    "pipeline_result",
    "pipeline_checked_at",
    "pipeline_next_attempt_at",
    "updated_at",
]
_FAILURE_FIELDS = [
    "status",
    "flagged_reason",
    "pre_review_status",
    "review_started_at",
    "pipeline_result",
    "pipeline_next_attempt_at",
    "updated_at",
]


def _lock_claimed_post(post_id, claimed_attempts):
    """The post a pipeline try was claimed for, locked, or None when the answer must be dropped:
    the author deleted the post meanwhile, or a newer claim took it over (its lease ran out, so
    `pipeline_attempts` moved on). The lock is Part 8's `FOR NO KEY UPDATE`: it waits for a report,
    a repost or a delete, not for likes, comments or bookmarks."""
    post = (
        Post.objects.not_deleted()
        .select_for_update(no_key=True, of=("self",))
        .filter(pk=post_id)
        .first()
    )
    if post is None or post.pipeline_attempts != claimed_attempts:
        return None
    return post


def record_pipeline_result(post_id, result, *, claimed_attempts, now):
    """Write a pipeline result through `routing.apply_pipeline_result` (§4).

    `claimed_attempts` is the post's `pipeline_attempts` when the processor claimed the try (the
    claim token). Returns the `Outcome`, or None when the answer was dropped (see
    `_lock_claimed_post`); an `IGNORED` post (removed, decided by a moderator, already checked) is
    not written at all, so its fields and `updated_at` stay as they were. `durable=True`: this
    must never run inside a caller's transaction, which would hold the row lock across the call.
    """
    with transaction.atomic(durable=True):
        post = _lock_claimed_post(post_id, claimed_attempts)
        if post is None:
            return None
        outcome = routing.apply_pipeline_result(post, result, get_platform_settings(), now)
        if outcome != routing.Outcome.IGNORED:
            post.save(update_fields=_RESULT_FIELDS)
        if outcome == routing.Outcome.LABELLED:
            # The label is public now, so it counts (§4a). A result held back for a review
            # (`entered_review`, `updated_review`) records nothing: a late TRUE stays private.
            rows = reputation_services.settle_post(post, now=now)
            # A FALSE emergency blocks its author's emergency posting (§4b). Only an expired or
            # demoted emergency can be labelled FALSE here: an active one goes to review. The
            # import is local: `apps.moderation.services` imports this module.
            from apps.moderation.services import block_after_emergency_false

            block_after_emergency_false(post, rows, now=now, moderator=None)
            notification_services.verdict_reached(post=post, label=post.status, now=now)
        elif outcome == routing.Outcome.ENTERED_REVIEW:
            notification_services.entered_review(post=post, now=now)
        return outcome


def record_pipeline_failure(post_id, error, *, claimed_attempts, now):
    """Write a failed try through `routing.apply_pipeline_failure` (the backoff, or after
    `MAX_ATTEMPTS` a moderator's review). Same rules as `record_pipeline_result`."""
    with transaction.atomic(durable=True):
        post = _lock_claimed_post(post_id, claimed_attempts)
        if post is None:
            return None
        outcome = routing.apply_pipeline_failure(post, error, now)
        if outcome != routing.Outcome.IGNORED:
            post.save(update_fields=_FAILURE_FIELDS)
        if outcome == routing.Outcome.ENTERED_REVIEW:
            notification_services.entered_review(post=post, now=now)
        return outcome
