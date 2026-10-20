"""The notification objects of `GET /api/v1/notifications/` (ARCHITECTURE §9)."""

from rest_framework import serializers

from apps.accounts.serializers import user_summary
from apps.notifications.models import NotificationType
from apps.posts.serializers import iso

EXCERPT_LENGTH = 140


def excerpt(text, limit=EXCERPT_LENGTH):
    """The first `limit` code points of `text` with whitespace collapsed, and `…` when cut. Made on
    the server so a long post never travels in a list."""
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit].rstrip() + "…"


def _actor(notification):
    """The person who did it, or None ("Someone"): a system message, a deleted account (SET_NULL)
    or a suspended one. Only a follow carries `following` (the Follow back button)."""
    actor = notification.actor
    if actor is None or not actor.is_active:
        return None
    data = user_summary(actor)
    if notification.type == NotificationType.FOLLOW:
        data["following"] = bool(notification.actor_following)
    return data


def notification_data(notification):
    """One item (8 keys). `post` and `comment` are small summaries, never the whole object."""
    post = notification.post
    comment = notification.comment
    return {
        "id": str(notification.pk),
        "type": notification.type,
        "outcome": notification.outcome,
        "is_read": notification.is_read,
        "created_at": iso(notification.created_at),
        "actor": _actor(notification),
        "post": None
        if post is None
        else {
            "id": str(post.pk),
            "excerpt": excerpt(post.content),
            "post_type": post.post_type,
            "status": post.status,
        },
        "comment": None
        if comment is None
        else {"id": str(comment.pk), "excerpt": excerpt(comment.content)},
    }


MAX_MARK_READ_IDS = 50


class MarkReadSerializer(serializers.Serializer):
    """`POST /api/v1/notifications/mark-read/`: exactly one of `ids` (1 to 50 uuids) or
    `{"all": true}`. Undeclared fields are ignored."""

    ids = serializers.ListField(
        child=serializers.UUIDField(),
        allow_empty=False,
        max_length=MAX_MARK_READ_IDS,
        required=False,
    )
    all = serializers.BooleanField(required=False)

    def validate(self, attrs):
        if ("ids" in attrs) == ("all" in attrs):
            raise serializers.ValidationError("Send either ids or all, not both.")
        if "all" in attrs and attrs["all"] is not True:
            raise serializers.ValidationError("all can only be true.")
        return attrs
