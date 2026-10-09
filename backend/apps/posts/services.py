"""Creating and deleting posts, and the fact quota (ARCHITECTURE §3, §4, §4b).

Only this module and `apps/moderation/services.py` (Part 10) change `Post.status`. There is no HTTP
here: the views turn these domain errors into responses.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.core.services import get_platform_settings
from apps.posts.models import Post, PostStatus, PostType

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

    The pipeline is Part 9: a fact post just waits as `pending` ("Checking facts…").
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
        return Post.objects.create(
            author=author,
            content=content,
            post_type=post_type,
            sources=sources,
            status=status,
            created_at=now,
        )


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
