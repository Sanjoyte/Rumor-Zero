"""Following, likes, comments, reposts and bookmarks (ARCHITECTURE §2, §4d, §9). No HTTP here: the
views map the errors.

Only this module writes `Follow`, `Like`, `Comment`, `Repost` and `Bookmark` rows (the admin's
Hide/Unhide aside). Each follow or repost change forgets the actor's cached Following feed
(`feed.bust_following_feed`); the people you follow reach you after at most `FEED_CACHE_SECONDS`.
Likes, comments and bookmarks need no cache bust: the feed caches only keys and the counts are read
fresh.
"""

import re

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.validators import normalize_username
from apps.notifications import services as notification_services
from apps.posts.models import Post, PostStatus
from apps.social.feed import bust_following_feed
from apps.social.models import Bookmark, Comment, Follow, Like, Repost

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
    and Django reads the row back. A new follow tells the target (Part 13), in the same transaction;
    following again, or after an unfollow, tells nobody twice.
    """
    if follower.pk == target.pk:
        raise SelfFollow
    with transaction.atomic():
        _, created = Follow.objects.get_or_create(follower=follower, following=target)
        if created:
            notification_services.followed(follower=follower, target=target)
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
    post = Post.objects.visible().only("id", "author_id").filter(pk=post_id).first()
    if post is None:
        raise PostNotFound
    return post


def like(*, user, post_id):
    """Like a post. True if this created the like, False if it already existed.

    `get_or_create` survives two simultaneous requests: the unique pair refuses the second insert
    and Django reads the row back.
    """
    post = get_visible_post(post_id)
    with transaction.atomic():
        _, created = Like.objects.get_or_create(user=user, post=post)
        if created:
            notification_services.liked(user=user, post=post)
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
    now = now or timezone.now()
    with transaction.atomic():
        comment = Comment.objects.create(post=post, author=author, content=content, created_at=now)
        notification_services.commented(author=author, post=post, comment=comment, now=now)
    return comment


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
        # The post author's "commented on your post" goes with the comment (Part 13).
        notification_services.discard_for_comment(comment.pk)
    return comment


class CannotRepostOwn(Exception):
    """You can't repost your own post."""


class CannotRepostFalse(Exception):
    """A post labelled FALSE can't be reposted."""


def repost(*, user, post_id, now=None):
    """Repost a post. True if this created the repost, False if it already existed.

    The post row is locked (`FOR NO KEY UPDATE`: it waits for a status change and for another
    repost of the same post, but not for the `FOR KEY SHARE` locks that likes, comments and
    bookmarks take), so `status_at_repost` is the status at commit and two simultaneous reposts by
    one user make one row. Order: a post the public can see (else `PostNotFound`), then an existing
    repost (so a post that turned FALSE after you reposted it doesn't refuse you), then your own
    post, then FALSE (a post under review that was FALSE before the review counts as FALSE). A
    repost has no id in the API: it is always of this post, so "reposting a repost" is reposting
    the original.
    """
    now = now or timezone.now()
    with transaction.atomic():
        post = (
            Post.objects.visible()
            .select_for_update(no_key=True, of=("self",))
            .only("id", "author_id", "status", "pre_review_status")
            .filter(pk=post_id)
            .first()
        )
        if post is None:
            raise PostNotFound
        if Repost.objects.filter(user=user, post=post).exists():
            created = False
        else:
            if post.author_id == user.pk:
                raise CannotRepostOwn
            if post.status == PostStatus.VERIFIED_FALSE or (
                # Reports can move a FALSE post to review; it keeps its label until a moderator
                # decides, so it stays closed to reposts meanwhile (user decision 2026-10-10).
                post.status == PostStatus.UNDER_REVIEW
                and post.pre_review_status == PostStatus.VERIFIED_FALSE
            ):
                raise CannotRepostFalse
            _, created = Repost.objects.get_or_create(
                user=user, post=post, defaults={"status_at_repost": post.status, "created_at": now}
            )
            if created:
                notification_services.reposted(user=user, post=post, now=now)
        bust_following_feed(user.pk)
    return created


def unrepost(*, user, post_id):
    """Take a repost back. Quietly does nothing if there was none.

    Works whatever became of the original (deleted and removed included): your own "no longer
    available" card must always be removable. Only an unknown id is `PostNotFound`.
    """
    if not Post.objects.filter(pk=post_id).exists():
        raise PostNotFound
    Repost.objects.filter(user=user, post_id=post_id).delete()
    bust_following_feed(user.pk)


def bookmark(*, user, post_id):
    """Save a post privately. True if this created the bookmark, False if it already existed.

    Any post the public can see, your own and FALSE ones included; no verified email is needed.
    """
    post = get_visible_post(post_id)
    _, created = Bookmark.objects.get_or_create(user=user, post=post)
    return created


def unbookmark(*, user, post_id):
    """Take a bookmark back. Quietly does nothing if there was none; works on a removed post
    (like `unlike`). Only an unknown or deleted post is `PostNotFound`."""
    if not Post.objects.not_deleted().filter(pk=post_id).exists():
        raise PostNotFound
    Bookmark.objects.filter(user=user, post_id=post_id).delete()
