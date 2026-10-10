"""The Following feed: followed accounts plus your own posts (ARCHITECTURE §9).

Only the **ids** of the first page are cached (user decision 2026-10-09). The posts are loaded
again on every request, so a deleted or removed post disappears at once, and likes and counts
(Part 7) are never stale. What the cache saves is the expensive part, finding those 20 ids.
"""

import uuid

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.db.models import Q

from apps.posts.models import Post
from apps.social.models import Follow

CACHE_KEY = "social:following-feed:v1:{user_id}"


def cache_key(user_id):
    return CACHE_KEY.format(user_id=user_id)


def bust_following_feed(user_id):
    """Forget `user_id`'s cached first page: now, and again once the transaction has committed
    (a reader can refill the cache from old rows in between; the PlatformSettings pattern)."""
    key = cache_key(user_id)
    cache.delete(key)
    transaction.on_commit(lambda: cache.delete(key))


def following_queryset(user):
    """Visible posts by the people `user` follows, and by `user`."""
    followed = Follow.objects.filter(follower=user).values("following_id")
    return Post.objects.visible().filter(Q(author_id=user.pk) | Q(author_id__in=followed))


def load_posts(ids, viewer):
    """The posts for `ids`, in that order, with the counts and `viewer`'s likes. One that is no
    longer visible is dropped."""
    queryset = Post.objects.visible().for_list(viewer).filter(pk__in=ids)
    posts = {str(post.pk): post for post in queryset}
    return [posts[i] for i in ids if i in posts]


def _is_entry(value):
    """Is this what we stored? A malformed value is treated as a miss."""
    if not isinstance(value, dict) or not isinstance(value.get("ids"), list):
        return False
    next_cursor = value.get("next")
    if next_cursor is not None and not isinstance(next_cursor, str):
        return False
    try:
        return all(str(uuid.UUID(i)) == i for i in value["ids"])
    except (ValueError, AttributeError, TypeError):
        return False


def following_page(request, view, user, paginator):
    """`(posts, next_cursor)` for one page. A first page asked with the defaults is cached."""
    ttl = settings.FEED_CACHE_SECONDS
    cacheable = (
        ttl > 0 and "cursor" not in request.query_params and "page_size" not in request.query_params
    )
    key = cache_key(user.pk)
    if cacheable:
        entry = cache.get(key)
        if _is_entry(entry):
            return load_posts(entry["ids"], user), entry["next"]
    rows = paginator.paginate_queryset(
        following_queryset(user).values("id", "created_at"), request, view=view
    )
    ids = [str(row["id"]) for row in rows]
    next_cursor = paginator.get_next_link()
    if cacheable:
        cache.set(key, {"ids": ids, "next": next_cursor}, ttl)
    return load_posts(ids, user), next_cursor
