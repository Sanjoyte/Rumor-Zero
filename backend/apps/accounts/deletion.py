"""Deleting an account (ARCHITECTURE §2, §7; Part 14).

One routine for the owner's `DELETE /api/v1/me/` and for Django Admin, so both leave the same
things behind. The database does the removing (`on_delete` per ARCHITECTURE §2): the account's
posts, comments, likes, follows, bookmarks, reposts, reports, appeals, credibility-ledger rows,
notifications received, and allauth's `EmailAddress` and `SocialAccount` go with it. Moderation
records keep their `post_snapshot` (post, subject and moderator become NULL), other people's ledger
rows about its posts lose their `post`, and `report_count` is never decremented.
"""

from django.contrib.sessions.models import Session
from django.db import transaction

from apps.accounts.models import User
from apps.notifications import services as notifications
from apps.posts.models import Post


def delete_account(user, *, session_key=None):
    """Delete `user` and everything that goes with the account. Returns False when it is already
    gone (a second request, or two admins), so the call is idempotent.

    `session_key` is the token session the request came in on; it is deleted too. Every other
    session of the account ends at its next refresh, because the user row is gone.

    The caller must not hold any lock. The order is the point: **every post of the account first,
    then the user**, which is the order `settle_post` takes (the post, then the author's score).
    Locking the user first would let a verdict landing on one of its posts wait on this
    transaction while this one waits on the post. Posts are locked in primary-key order, as
    `delete_post` locks one. A post created while this runs, and settled at that very moment, can
    still deadlock; Postgres aborts one side and the client may retry (accepted in the plan).
    """
    with transaction.atomic():
        list(
            Post.objects.select_for_update()
            .filter(author_id=user.pk)
            .order_by("pk")
            .values_list("pk", flat=True)
        )
        if not User.objects.select_for_update().filter(pk=user.pk).exists():
            return False
        notifications.discard_for_actor(user.pk)
        if session_key:
            Session.objects.filter(session_key=session_key).delete()
        User.objects.filter(pk=user.pk).delete()
    return True
