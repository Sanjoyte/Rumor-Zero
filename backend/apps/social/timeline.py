"""The mixed timeline: posts and reposts in one list, paged by a keyset cursor (ARCHITECTURE §9).

The Following feed and the profile lists hold two kinds of item: a post (its own time) and a
repost (the time it was made). DRF's cursor filters one queryset, and Django refuses `filter()`
after `union()`, so this module does the paging itself: the "after the cursor" filter goes into
each side, each side is sliced, and the two are united and ordered again.

**The key.** Every item sorts, newest first, by `(at, kind, ref, by)`, all non-null:

- a post is `(post.created_at, 0, post.id, ZERO_UUID)`;
- a repost is `(repost.created_at, 1, repost.post_id, repost.user_id)`.

A post is unique by id and a repost by (user, post), so the key is unique without the repost's own
bigint id (post ids are uuids: there is no one "item id" column both tables share). `ref` is always
the post the item is about, which is what the per-page dedupe compares.

**The page.** A page is the longest prefix of the next `2 × size` rows that holds at most `size`
distinct posts, showing the first (most recent) row of each. Rows hidden that way are consumed: the
cursor moves past them. The first row is always kept, so every page advances; a page holds at most
`size` items and may hold fewer. Lists that can't repeat a post (a profile: you can't repost your
own post) fetch `size` rows and never dedupe, so their pages are full.

**Stability.** A new post or repost always sorts above any cursor, so nothing is skipped or
repeated across pages while they arrive. As with any timestamp cursor, a row that commits after a
reader paged past its time is missed by that walk.
"""

import base64
import uuid
from datetime import UTC, datetime, timedelta
from typing import NamedTuple

from django.db.models import F, IntegerField, Q, UUIDField, Value
from rest_framework.exceptions import NotFound

from apps.posts.pagination import FeedPagination

EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
ZERO_UUID = uuid.UUID(int=0)
POST, REPOST = 0, 1
_MICROSECOND = timedelta(microseconds=1)


class Key(NamedTuple):
    """The sort key of one item; plain tuple order is the feed order (newest first)."""

    at: datetime
    kind: int
    ref: uuid.UUID
    by: uuid.UUID

    def micros(self):
        return (self.at - EPOCH) // _MICROSECOND

    def token(self):
        """The opaque cursor for "everything after this item"."""
        raw = f"{self.micros()}|{self.kind}|{self.ref}|{self.by}".encode("ascii")
        return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")

    def cache_row(self):
        """`[micros, kind, post id, reposter id]`: what the Following cache stores."""
        return [self.micros(), self.kind, str(self.ref), str(self.by)]


def _uuid(text):
    value = uuid.UUID(text)
    if str(value) != text:
        raise ValueError("not canonical")
    return value


def key_from_parts(micros, kind, ref, by):
    """A `Key` from the four stored values, or None if they aren't exactly what `Key` writes."""
    try:
        if isinstance(micros, bool) or not isinstance(micros, int) or micros < 0:
            return None
        if kind not in (POST, REPOST) or isinstance(kind, bool):
            return None
        key = Key(EPOCH + micros * _MICROSECOND, kind, _uuid(ref), _uuid(by))
    except (ValueError, TypeError, OverflowError, AttributeError):
        return None
    if key.kind == POST and key.by != ZERO_UUID:
        return None
    return key


def key_from_cache_row(row):
    if not isinstance(row, list) or len(row) != 4:
        return None
    return key_from_parts(*row)


def decode_token(token):
    """The `Key` a cursor names. Anything else is a 404, like every other crafted cursor."""
    try:
        padded = token + "=" * (-len(token) % 4)
        parts = base64.urlsafe_b64decode(padded.encode("ascii")).decode("ascii").split("|")
        if len(parts) != 4 or not all(p.isascii() and p.isdigit() for p in parts[:2]):
            raise ValueError("shape")
        key = key_from_parts(int(parts[0]), int(parts[1]), parts[2], parts[3])
        # The canonical form only: junk that base64 would silently skip is not a cursor.
        if key is None or key.token() != token:
            raise ValueError("not canonical")
    except (ValueError, TypeError, OverflowError):
        raise NotFound("Invalid cursor.") from None
    return key


def _posts_after(cursor):
    """Posts that sort after `cursor`. The `<=` is redundant, but a bare OR can't become an index
    condition, so without it a deep page would scan from the newest post."""
    at = cursor.at
    if cursor.kind == REPOST:  # a repost sorts above every post of the same instant
        return Q(created_at__lte=at)
    return Q(created_at__lte=at) & (Q(created_at__lt=at) | Q(id__lt=cursor.ref))


def _reposts_after(cursor):
    at = cursor.at
    if cursor.kind == POST:  # every repost of the same instant sorts above a post
        return Q(created_at__lt=at)
    return Q(created_at__lte=at) & (
        Q(created_at__lt=at)
        | Q(post_id__lt=cursor.ref)
        | Q(post_id=cursor.ref, user_id__lt=cursor.by)
    )


def page_request(request):
    """`(size, cursor key or None)` from `?page_size=` and `?cursor=`. The size follows DRF's rules
    (junk is 20, more than 50 is 50); an empty cursor is the first page."""
    size = FeedPagination().get_page_size(request)
    token = request.query_params.get("cursor")
    return size, (decode_token(token) if token else None)


def fetch_limit(size, dedupe):
    """Rows to read: the window the page can use, plus one to learn whether more follow."""
    return (2 * size if dedupe else size) + 1


def take_page(rows, size, *, dedupe):
    """`(kept, next_key)` for one page of `rows` (`Key`s, newest first, at most `fetch_limit`).

    `next_key` is the last row the page consumed (kept or hidden) when any fetched row follows it,
    else None.
    """
    window = rows[: 2 * size if dedupe else size]
    kept, seen, last = [], set(), -1
    for index, row in enumerate(window):
        if dedupe and row.ref in seen:
            last = index  # an older activity of a post already on this page: consumed, not shown
            continue
        if len(kept) == size:
            break
        seen.add(row.ref)
        kept.append(row)
        last = index
    more = len(rows) > last + 1
    return kept, (rows[last] if kept and more else None)


def page(posts, reposts, *, size, cursor, dedupe):
    """One page of the union of `posts` (a `Post` queryset) and `reposts` (a `Repost` queryset).

    Callers pass the querysets already limited to what the list shows; this adds the cursor, the
    keys, the slices and the union. Returns `(kept keys, next key or None)`.
    """
    limit = fetch_limit(size, dedupe)
    if cursor is not None:
        posts = posts.filter(_posts_after(cursor))
        reposts = reposts.filter(_reposts_after(cursor))
    post_rows = (
        posts.order_by("-created_at", "-id")
        .annotate(
            at=F("created_at"),
            kind=Value(POST, output_field=IntegerField()),
            ref=F("id"),
            by=Value(ZERO_UUID, output_field=UUIDField()),
        )
        .values_list("at", "kind", "ref", "by")[:limit]
    )
    repost_rows = (
        reposts.order_by("-created_at", "-post_id", "-user_id")
        .annotate(
            at=F("created_at"),
            kind=Value(REPOST, output_field=IntegerField()),
            ref=F("post_id"),
            by=F("user_id"),
        )
        .values_list("at", "kind", "ref", "by")[:limit]
    )
    united = post_rows.union(repost_rows, all=True).order_by("-at", "-kind", "-ref", "-by")[:limit]
    return take_page([Key(*row) for row in united], size, dedupe=dedupe)
