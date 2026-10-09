"""The pure emergency rule (ARCHITECTURE §4, §4b).

It lives here and not in `apps/pipeline/routing.py` because `apps/pipeline` doesn't exist until
Part 9 (a bare package folder now would make that part's `startapp` refuse it). Part 9's routing
module imports it. It is computed at read time from the stored columns: no job ever flips a flag.
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
