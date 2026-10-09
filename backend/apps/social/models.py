from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


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
