"""The Following feed: followed accounts plus your own posts, and their reposts (ARCHITECTURE §9).

Only the **keys** of the first page are cached (user decision 2026-10-09; the keys, not just ids,
since Part 7B: a post and a repost are different items). The posts and reposts are loaded again on
every request, so a deleted or removed post disappears at once, an undone repost drops out, and
likes, reposts and counts are never stale. What the cache saves is the expensive part, finding the
page's keys.

**Pinned emergencies** (Part 11C, §4b): the active emergencies by `followed ∪ me` are pinned above
the feed (`following_emergencies`) and left out of its pages: the posts side excludes them, and
the reposts side excludes reposts **of** them (reposts never pin; a repost of someone else's
emergency stays, with its chip). The pinned list is computed on every first-page request, cache
hits included; the cached keys were filtered when they were cached. An emergency that ends while
a follower's first page is cached is in neither list until the cache's 30 s run out (accepted).
"""

from typing import NamedTuple

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.db.models import Q

from apps.accounts.models import User
from apps.posts.emergency import active_emergency_q
from apps.posts.models import Post, PostStatus
from apps.social import timeline
from apps.social.models import Follow, Repost

CACHE_KEY = "social:following-feed:v2:{user_id}"


def cache_key(user_id):
    return CACHE_KEY.format(user_id=user_id)


def bust_following_feed(user_id):
    """Forget `user_id`'s cached first page: now, and again once the transaction has committed
    (a reader can refill the cache from old rows in between; the PlatformSettings pattern)."""
    key = cache_key(user_id)
    cache.delete(key)
    transaction.on_commit(lambda: cache.delete(key))


def _followed(user):
    return Follow.objects.filter(follower=user).values("following_id")


def following_posts(user):
    """Visible posts by the people `user` follows, and by `user`."""
    return Post.objects.visible().filter(Q(author_id=user.pk) | Q(author_id__in=_followed(user)))


def following_reposts(user):
    """Every repost by the people `user` follows, and by `user`, whatever became of the original
    (one that is gone shows as "no longer available")."""
    return Repost.objects.filter(Q(user_id=user.pk) | Q(user_id__in=_followed(user)))


def following_emergencies(user, now):
    """The active emergencies by the people `user` follows, and by `user`: what Following pins."""
    return following_posts(user).filter(active_emergency_q(now))


def load_posts(ids, viewer):
    """The posts for `ids`, in that order, with the counts and `viewer`'s flags. One that is no
    longer visible is dropped."""
    queryset = Post.objects.visible().for_list(viewer).filter(pk__in=ids)
    posts = {str(post.pk): post for post in queryset}
    return [posts[i] for i in ids if i in posts]


class Entry(NamedTuple):
    """One item of a page, loaded: its key, the original (None when it is no longer visible) and,
    for a repost, who made it."""

    key: timeline.Key
    post: Post | None
    reposter: User | None


def load_entries(keys, viewer, *, reposter=None, own_removed=False):
    """The items for `keys`, in order. One path for a cache hit and a miss.

    A post item whose post is no longer visible is dropped; a repost item whose original is no
    longer visible stays, with `post=None` ("This post is no longer available"). `own_removed`
    (the viewer's own profile) also loads the viewer's own removed posts, and only theirs: a repost
    of someone else's removed post is still the stub. Reposts are read
    again, matched on the pair **and** its time, so one that was undone (or undone and made again,
    which moves it to the top) leaves a cached page instead of showing out of order. A list that
    belongs to one person passes `reposter` and skips that read. An empty list of ids makes no
    query, so the number of queries depends on what the page holds.
    """
    post_ids = {key.ref for key in keys}
    loadable = Post.objects.visible()
    if own_removed:
        loadable = Post.objects.not_deleted().exclude(
            Q(status=PostStatus.REMOVED) & ~Q(author=viewer)
        )
    posts = (
        {post.pk: post for post in loadable.for_list(viewer).filter(pk__in=post_ids)}
        if post_ids
        else {}
    )
    reposts = {}
    repost_keys = [key for key in keys if key.kind == timeline.REPOST]
    if repost_keys and reposter is None:
        pairs = Q()
        for key in repost_keys:
            pairs |= Q(user_id=key.by, post_id=key.ref)
        reposts = {
            (row.user_id, row.post_id): row
            for row in Repost.objects.filter(pairs).select_related("user")
        }
    entries = []
    for key in keys:
        post = posts.get(key.ref)
        if key.kind == timeline.POST:
            if post is not None:
                entries.append(Entry(key, post, None))
            continue
        who = reposter
        if who is None:
            row = reposts.get((key.by, key.ref))
            if row is None or row.created_at != key.at:
                continue
            who = row.user
        entries.append(Entry(key, post, who))
    return entries


def _read_entry(value):
    """`(keys, next cursor)` from what we stored, or None: a malformed value is a miss."""
    if not isinstance(value, dict) or not isinstance(value.get("items"), list):
        return None
    next_cursor = value.get("next")
    if next_cursor is not None and not isinstance(next_cursor, str):
        return None
    keys = [timeline.key_from_cache_row(row) for row in value["items"]]
    return None if None in keys else (keys, next_cursor)


def following_page(request, user, *, now):
    """`(entries, next_cursor)` for one page. A first page asked with the defaults is cached.

    The posts that Following pins at `now` are left out, and so are reposts of them (in the same
    SQL: `post_id NOT IN` the pinnable ids, both columns non-null)."""
    ttl = settings.FEED_CACHE_SECONDS
    cacheable = (
        ttl > 0 and "cursor" not in request.query_params and "page_size" not in request.query_params
    )
    key = cache_key(user.pk)
    if cacheable:
        stored = _read_entry(cache.get(key))
        if stored is not None:
            return load_entries(stored[0], user), stored[1]
    size, cursor = timeline.page_request(request)
    pinned = following_emergencies(user, now)
    keys, next_key = timeline.page(
        following_posts(user).exclude(active_emergency_q(now)),
        following_reposts(user).exclude(post_id__in=pinned.values("id")),
        size=size,
        cursor=cursor,
        dedupe=True,
    )
    next_cursor = next_key.token() if next_key else None
    if cacheable:
        cache.set(key, {"items": [k.cache_row() for k in keys], "next": next_cursor}, ttl)
    return load_entries(keys, user), next_cursor
