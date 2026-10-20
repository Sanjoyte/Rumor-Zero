"""Writing and reading notifications (ARCHITECTURE §2, §9; guide §11). No HTTP here.

`notify()` is called explicitly, with no signals, from the write services (follow, like, comment,
repost, the pipeline's result and failure, a report that sends a post to review, the moderator
actions), **inside their transaction**: the item exists exactly when the event does. It never opens
a transaction of its own, so `atomic(durable=True)` callers stay valid, and it raises when called
outside one. The named helpers below keep each call site to one line.

Rules every item follows:

- never to yourself (`actor == recipient` is dropped; the table has the same check);
- `like`, `repost` and `follow` are de-duplicated by the database (a partial unique index), so a
  like taken back and given again, or two simultaneous requests, make one item;
- the five moderation types have **no actor**: the author is never told which moderator acted,
  and a reporter is never revealed.
"""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.notifications.models import Notification, NotificationOutcome, NotificationType
from apps.posts.models import PostStatus

# One action's items are stamped this far apart, so their order in the list is stable (the cursor's
# position is the first ordering key, and ids break ties at random).
TICK = timedelta(microseconds=1)


def _require_transaction():
    if not transaction.get_connection().in_atomic_block:
        raise RuntimeError("notify() runs inside the caller's transaction")


def notify(
    *,
    type,
    recipient_id,
    actor_id=None,
    post_id=None,
    comment_id=None,
    outcome="",
    now=None,
):
    """Write one notification and return it, or None when nothing was written for this call.

    Nothing is written for a notification to yourself. For a de-duplicated type the insert is
    `ON CONFLICT DO NOTHING` against the partial unique indexes, so a second one is dropped
    quietly (the returned object is then not a stored row). Every CHECK still raises: a wrong
    shape is a bug in the caller.
    """
    _require_transaction()
    if actor_id is not None and actor_id == recipient_id:
        return None
    item = Notification(
        type=type,
        recipient_id=recipient_id,
        actor_id=actor_id,
        post_id=post_id,
        comment_id=comment_id,
        outcome=outcome,
        created_at=now or timezone.now(),
    )
    Notification.objects.bulk_create([item], ignore_conflicts=True)
    return item


# ---------- The events (called from the write services) ----------


def followed(*, follower, target, now=None):
    return notify(
        type=NotificationType.FOLLOW, recipient_id=target.pk, actor_id=follower.pk, now=now
    )


def liked(*, user, post, now=None):
    """`post` needs `author_id`."""
    return notify(
        type=NotificationType.LIKE,
        recipient_id=post.author_id,
        actor_id=user.pk,
        post_id=post.pk,
        now=now,
    )


def commented(*, author, post, comment, now=None):
    return notify(
        type=NotificationType.COMMENT,
        recipient_id=post.author_id,
        actor_id=author.pk,
        post_id=post.pk,
        comment_id=comment.pk,
        now=now,
    )


def reposted(*, user, post, now=None):
    return notify(
        type=NotificationType.REPOST,
        recipient_id=post.author_id,
        actor_id=user.pk,
        post_id=post.pk,
        now=now,
    )


def verdict_reached(*, post, label, now=None):
    """The author's fact got a label. `label` is the post's new status (`verified_true` or
    `verified_false`); the item stores `true` / `false` so it never changes meaning."""
    outcome = (
        NotificationOutcome.TRUE if label == PostStatus.VERIFIED_TRUE else NotificationOutcome.FALSE
    )
    return notify(
        type=NotificationType.VERDICT,
        recipient_id=post.author_id,
        post_id=post.pk,
        outcome=outcome,
        now=now,
    )


def entered_review(*, post, now=None):
    return notify(
        type=NotificationType.UNDER_REVIEW, recipient_id=post.author_id, post_id=post.pk, now=now
    )


def removed(*, post, now=None):
    return notify(
        type=NotificationType.REMOVED, recipient_id=post.author_id, post_id=post.pk, now=now
    )


def emergency_demoted(*, post, now=None):
    return notify(
        type=NotificationType.EMERGENCY_DEMOTED,
        recipient_id=post.author_id,
        post_id=post.pk,
        now=now,
    )


def appeal_resolved(*, post, appeal, now=None):
    """`appeal.status` is `upheld` or `overturned`; the recipient is the appeal's author."""
    return notify(
        type=NotificationType.APPEAL_RESOLVED,
        recipient_id=appeal.author_id,
        post_id=post.pk,
        outcome=appeal.status,
        now=now,
    )


# ---------- Cleanup: an item goes with what it points at ----------


def discard_for_post(post_id):
    """Delete every item about a post (the author soft-deleted it). A plain `DELETE`, so the one
    `FOR UPDATE` that `delete_post` takes is unchanged."""
    Notification.objects.filter(post_id=post_id).delete()


def discard_for_comment(comment_id):
    """Delete the item about a comment (its author deleted it, or a moderator hid it)."""
    Notification.objects.filter(comment_id=comment_id).delete()


# ---------- Reading ----------


def unread_count(user):
    """The exact number of unread items: one query on the partial index (the filter has to be
    `is_read=False`, the index's predicate)."""
    return Notification.objects.filter(recipient=user, is_read=False).count()


def mark_read(user, *, ids=None):
    """Mark your unread items read: those in `ids`, or all of them when `ids` is None. Other
    people's and unknown ids are ignored. Returns the unread count left.

    The rows are locked in id order first, so two mark-alls (or one racing a discard) take their
    locks in the same order.
    """
    unread = Notification.objects.filter(recipient=user, is_read=False)
    if ids is not None:
        unread = unread.filter(pk__in=ids)
    with transaction.atomic():
        locked = list(unread.order_by("id").select_for_update().values_list("pk", flat=True))
        if locked:
            Notification.objects.filter(pk__in=locked).update(is_read=True)
    return unread_count(user)
