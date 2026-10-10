"""Following, likes and comments (ARCHITECTURE §2, §9). No HTTP here: the views map the errors.

Only this module writes `Follow`, `Like` and `Comment` rows (the admin's Hide/Unhide aside). Each
follow change forgets the follower's cached Following feed (`feed.bust_following_feed`); the people
you follow reach you after at most `FEED_CACHE_SECONDS`. Likes and comments need no cache bust:
the feed caches only post ids and the counts are read fresh.
"""

import re

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.validators import normalize_username
from apps.posts.models import Post, PostStatus
from apps.social.feed import bust_following_feed
from apps.social.models import Comment, Follow, Like

# A longer name can't be a username (30 at most), so it is cut before it is normalised.
MAX_LOOKUP_LENGTH = 64


class SelfFollow(Exception):
    """You can't follow yourself."""


_USERNAME_RE = re.compile(r"[a-z0-9_]{3,30}")


def lookup_name(raw):
    """The stored form of a username typed in a URL, or None if it can't be one.

    Anything that isn't a valid username is refused here, before the database: a NUL byte, for
    one, makes Postgres raise (a 500), and a valid name never contains one.
    """
    if not isinstance(raw, str):
        return None
    username = normalize_username(raw[:MAX_LOOKUP_LENGTH])
    return username if _USERNAME_RE.fullmatch(username) else None


def find_active_user(raw):
    """The active user called `raw` (case-insensitive), or None.

    Usernames are stored lowercase, so this is an exact hit on the unique index.
    """
    username = lookup_name(raw)
    if username is None:
        return None
    return User.objects.filter(username=username, is_active=True).first()


def follow(*, follower, target):
    """Follow `target`. True if this created the follow, False if it already existed.

    `get_or_create` survives two simultaneous requests: the unique pair refuses the second insert
    and Django reads the row back.
    """
    if follower.pk == target.pk:
        raise SelfFollow
    _, created = Follow.objects.get_or_create(follower=follower, following=target)
    bust_following_feed(follower.pk)
    return created


def unfollow(*, follower, target):
    """Stop following `target`. Quietly does nothing if you weren't."""
    Follow.objects.filter(follower=follower, following=target).delete()
    bust_following_feed(follower.pk)


class PostNotFound(Exception):
    """No post the public can see has this id (unknown, deleted, or removed)."""


class CommentNotFound(Exception):
    """No comment the public can see has this id (unknown, hidden, deleted, or on a hidden post)."""


class NotCommentAuthor(Exception):
    """Only a comment's author can delete it."""


def get_visible_post(post_id):
    """The post with this id that the public can see, or `PostNotFound`.

    Likes and comments are allowed on every such post, pending and under review included
    (ANALYSIS c1); a deleted or removed post has none (a removed post's author gets 404 too).
    """
    post = Post.objects.visible().only("id").filter(pk=post_id).first()
    if post is None:
        raise PostNotFound
    return post


def like(*, user, post_id):
    """Like a post. True if this created the like, False if it already existed.

    `get_or_create` survives two simultaneous requests: the unique pair refuses the second insert
    and Django reads the row back.
    """
    post = get_visible_post(post_id)
    _, created = Like.objects.get_or_create(user=user, post=post)
    return created


def unlike(*, user, post_id):
    """Take a like back. Quietly does nothing if there was none.

    Works on a removed post too (a like can always be taken back); only an unknown or deleted
    post is `PostNotFound`.
    """
    if not Post.objects.not_deleted().filter(pk=post_id).exists():
        raise PostNotFound
    Like.objects.filter(user=user, post_id=post_id).delete()


def add_comment(*, author, post_id, content, now=None):
    """Add a comment (already trimmed and length-checked by the serializer)."""
    post = get_visible_post(post_id)
    return Comment.objects.create(
        post=post, author=author, content=content, created_at=now or timezone.now()
    )


def delete_comment(*, comment_id, user, now=None):
    """The author's soft delete: `deleted_at` is set and the row stays (like posts, D6).

    The row is locked and re-read as "still shown", so two simultaneous deletes give one success
    and one `CommentNotFound`. A comment on a post the public can't see counts as gone.
    """
    now = now or timezone.now()
    with transaction.atomic():
        comment = (
            Comment.objects.select_for_update(of=("self",))
            .filter(
                pk=comment_id,
                is_hidden=False,
                deleted_at__isnull=True,
                post__deleted_at__isnull=True,
            )
            .exclude(post__status=PostStatus.REMOVED)
            .first()
        )
        if comment is None:
            raise CommentNotFound
        if comment.author_id != user.pk:
            raise NotCommentAuthor
        comment.deleted_at = now
        comment.save(update_fields=["deleted_at"])
    return comment
