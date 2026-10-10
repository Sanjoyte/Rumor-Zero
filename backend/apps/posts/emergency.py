"""The pure emergency rule (ARCHITECTURE §4, §4b).

It lives here, where Part 4's serializer already reads it, and not in `apps/pipeline/routing.py`
(Part 8): `apps/pipeline` sits above `posts` (its routing reads the post models and `posts.services`
calls it), so the post object can't depend on it. Part 11C's routing branches import it. It is
computed at read time from the stored columns: no job ever flips a flag.
"""

from apps.posts.models import PostStatus


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
