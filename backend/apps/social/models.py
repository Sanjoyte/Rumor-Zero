import uuid

from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.db.models.functions import Length
from django.db.models.lookups import GreaterThanOrEqual, LessThanOrEqual
from django.utils import timezone

from apps.posts.models import MAX_CONTENT_LENGTH


class Follow(models.Model):
    """`follower` follows `following` (ARCHITECTURE §2, "Social graph").

    A bigint id plus a unique pair (Django's admin has no composite primary keys). Written only by
    `apps/social/services.py`. The two composite indexes serve the lists, newest follow first:
    `follows_following_idx` the followers of someone, `follows_follower_idx` who someone follows.
    """

    follower = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="follows_given",
        db_index=False,
    )
    following = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="follows_received",
        db_index=False,
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["follower", "following"], name="follows_pair_unique"),
            models.CheckConstraint(condition=~Q(follower=F("following")), name="follows_not_self"),
        ]
        indexes = [
            models.Index(fields=["following", "-created_at", "-id"], name="follows_following_idx"),
            models.Index(fields=["follower", "-created_at", "-id"], name="follows_follower_idx"),
        ]

    def __str__(self):
        return f"{self.follower_id} follows {self.following_id}"


class Like(models.Model):
    """`user` likes `post` (ARCHITECTURE §2, "Social graph").

    A bigint id plus a unique pair, which also serves "did I like this?" (user first).
    `likes_post_created_idx` serves the per-post count and the daily stats of Part 11D. Written
    only by `apps/social/services.py`.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="likes_given",
        db_index=False,
    )
    post = models.ForeignKey(
        "posts.Post", on_delete=models.CASCADE, related_name="likes", db_index=False
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "post"], name="likes_pair_unique"),
        ]
        indexes = [
            models.Index(fields=["post", "created_at"], name="likes_post_created_idx"),
        ]

    def __str__(self):
        return f"{self.user_id} likes {self.post_id}"


class Comment(models.Model):
    """A flat comment on a post (ARCHITECTURE §2): 1 to 500 characters, no replies.

    Two ways to disappear, neither deleting the row: a moderator **hides** it (`is_hidden`, in
    Django Admin) and its author **deletes** it (`deleted_at`, soft, like posts). A hidden or
    deleted comment is in no list and no count. `comments_post_visible_idx` is a partial index
    over exactly those that are shown, so it serves both the list and the count. Written only by
    `apps/social/services.py` (and the admin's Hide/Unhide).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    post = models.ForeignKey(
        "posts.Post", on_delete=models.CASCADE, related_name="comments", db_index=False
    )
    # Keeps its own index: deleting an account or exporting its data looks comments up by author.
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="comments"
    )
    content = models.TextField()
    is_hidden = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    GreaterThanOrEqual(Length("content"), 1)
                    & LessThanOrEqual(Length("content"), MAX_CONTENT_LENGTH)
                ),
                name="comments_content_length",
            ),
        ]
        indexes = [
            models.Index(
                fields=["post", "created_at", "id"],
                condition=Q(is_hidden=False, deleted_at__isnull=True),
                name="comments_post_visible_idx",
            ),
        ]

    def __str__(self):
        return f"{self.author_id} on {self.post_id}: {self.content[:30]}"
