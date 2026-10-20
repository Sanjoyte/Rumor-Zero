"""The pinned emergencies of the feeds (ARCHITECTURE §4b, §9; Part 11C).

Recent pins every active emergency, Following those by the people you follow and by you: newest
first, at most `PINNED_SHOWN`, with how many there are in all for "Show all"
(`GET /api/v1/posts/emergencies/`). Every pinnable post is left out of the feed's `results`, on
every page. "Active" is `active_emergency_q(now)`, read at request time: no job ever unpins one.
"""

from django.db.models import Count, Window

from apps.posts.emergency import active_emergency_q
from apps.posts.models import Post

PINNED_SHOWN = 3  # §3: "Pinned emergencies shown per feed"


def recent_pinnable(now):
    """Every active emergency (they are all visible: not deleted, not removed)."""
    return Post.objects.filter(active_emergency_q(now))


def pinned_page(pinnable, viewer):
    """`(posts, total)`: the newest `PINNED_SHOWN` of `pinnable`, with the viewer's counts and
    flags, and how many there are in all. One query: the total is a window count over the whole
    set, computed before the LIMIT."""
    posts = list(
        pinnable.for_list(viewer)
        .annotate(pinned_total=Window(Count("pk")))
        .order_by("-created_at", "-id")[:PINNED_SHOWN]
    )
    return posts, (posts[0].pinned_total if posts else 0)


def is_first_page(request):
    """`pinned` belongs to a feed's first page: no `cursor`, or an empty one."""
    return not request.query_params.get("cursor")
