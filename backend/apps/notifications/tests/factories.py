"""Helpers for the notification tests. The hook tests drive the real services; `NotificationFactory`
writes rows directly for the read endpoints and the admin."""

from datetime import timedelta

import factory
from django.utils import timezone

from apps.notifications.models import Notification, NotificationOutcome, NotificationType
from apps.posts.tests.factories import PostFactory, VerifiedUserFactory
from apps.social.models import Comment

NOTE_TYPES_WITHOUT_ACTOR = (
    NotificationType.VERDICT,
    NotificationType.UNDER_REVIEW,
    NotificationType.REMOVED,
    NotificationType.EMERGENCY_DEMOTED,
    NotificationType.APPEAL_RESOLVED,
)


class NotificationFactory(factory.django.DjangoModelFactory):
    """A `like` of the recipient's own post by someone else. Other types need the matching
    fields (`follow`: no post; `comment`: a comment; `verdict`: an outcome)."""

    class Meta:
        model = Notification

    recipient = factory.SubFactory(VerifiedUserFactory)
    actor = factory.SubFactory(VerifiedUserFactory)
    type = NotificationType.LIKE
    post = factory.LazyAttribute(lambda row: PostFactory(author=row.recipient))
    created_at = factory.LazyFunction(timezone.now)


def follow_item(recipient, actor, **fields):
    return NotificationFactory(
        recipient=recipient, actor=actor, type=NotificationType.FOLLOW, post=None, **fields
    )


def comment_item(recipient, actor, **fields):
    post = fields.pop("post", None) or PostFactory(author=recipient)
    comment = fields.pop("comment", None) or Comment.objects.create(
        post=post, author=actor, content="A comment", created_at=timezone.now()
    )
    return NotificationFactory(
        recipient=recipient,
        actor=actor,
        type=NotificationType.COMMENT,
        post=post,
        comment=comment,
        **fields,
    )


def system_item(recipient, type=NotificationType.UNDER_REVIEW, **fields):
    outcome = fields.pop("outcome", "")
    if type == NotificationType.VERDICT and not outcome:
        outcome = NotificationOutcome.TRUE
    if type == NotificationType.APPEAL_RESOLVED and not outcome:
        outcome = NotificationOutcome.UPHELD
    return NotificationFactory(
        recipient=recipient, actor=None, type=type, outcome=outcome, **fields
    )


def spaced(count, *, newest=None):
    """`count` timestamps, newest first, one second apart (each row its own `created_at`)."""
    newest = newest or timezone.now()
    return [newest - timedelta(seconds=n) for n in range(count)]
