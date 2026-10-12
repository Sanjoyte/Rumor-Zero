"""Creating, deleting and reporting posts, the fact quota, and writing pipeline results
(ARCHITECTURE §3, §4, §4b, §5, §6).

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
from apps.pipeline import routing
from apps.posts.models import Post, PostStatus, PostType
from apps.social.feed import bust_following_feed

logger = logging.getLogger(__name__)

# The quota is a rolling window, not a calendar day (user decision 2026-10-08): a slot frees up 24
# hours after the post that used it. It counts every fact post made in the window, **including ones
# deleted or removed later**, or deleting and reposting would get around it.
FACT_QUOTA_WINDOW = timedelta(hours=24)


class EmergencyUnavailable(Exception):
    """Emergency posts arrive in Part 11C; until then `is_emergency=true` is refused."""


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


def _lock_author(author):
    """Serialise one person's fact posts: the second request counts after the first one's insert.

    A separate function so the race test can switch it off and show what happens without it.
    """
    User.objects.select_for_update().only("pk").get(pk=author.pk)


def _fact_post_times(author, since):
    """When each of the author's fact posts since `since` was made, oldest first. Deleted and
    removed posts are included on purpose. Separate so the race test can widen the window."""
    return list(
        Post.objects.filter(author=author, post_type=PostType.FACT, created_at__gt=since)
        .order_by("created_at")
        .values_list("created_at", flat=True)
    )


def fact_quota(user, *, now=None):
    """How many fact posts `user` has left in the rolling 24 hours (at most one query)."""
    now = now or timezone.now()
    limit = get_platform_settings().fact_posts_per_day
    times = _fact_post_times(user, now - FACT_QUOTA_WINDOW)
    used = len(times)
    remaining = max(limit - used, 0)
    next_slot_at = None
    if limit > 0 and remaining == 0:
        # The (used - limit + 1)-th oldest post must age out before there is room again. That is
        # right even after the limit was lowered (used 8, limit 5: the 4th oldest).
        next_slot_at = times[used - limit] + FACT_QUOTA_WINDOW
    return FactQuota(limit=limit, used=used, remaining=remaining, next_slot_at=next_slot_at)


def create_post(*, author, content, post_type, sources=(), is_emergency=False, now=None):
    """Create an opinion (`published`) or a fact (`pending`). Raises the errors above.

    A fact shows "Checking facts…" until the pipeline answers. With `PIPELINE_INLINE_KICK` on, a
    background thread checks it right after the commit (§6); otherwise the sweeper does.
    """
    now = now or timezone.now()
    if is_emergency:
        raise EmergencyUnavailable
    sources = list(sources)
    if post_type != PostType.FACT and sources:
        # The serializer refuses this first; the DB check behind it is the last line.
        raise ValidationError({"sources": ["Only fact posts can have sources."]})
    with transaction.atomic():
        if post_type == PostType.FACT:
            _lock_author(author)
            quota = fact_quota(author, now=now)
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
            created_at=now,
        )
        # Your own Following feed must show the new post at once, despite its cache (Part 6).
        bust_following_feed(author.pk)
        if post_type == PostType.FACT and settings.PIPELINE_INLINE_KICK:
            post_id = post.pk
            transaction.on_commit(lambda: _kick_pipeline(post_id))
        return post


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
        return outcome
