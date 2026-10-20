"""The table's own rules (ARCHITECTURE §2): every shape and outcome check, the partial unique
indexes, and what a deleted post, comment or account does to an item."""

import pytest
from django.db import IntegrityError, transaction

from apps.notifications.models import Notification, NotificationOutcome, NotificationType
from apps.notifications.tests.factories import (
    NotificationFactory,
    comment_item,
    follow_item,
    system_item,
)
from apps.posts.tests.factories import PostFactory, VerifiedUserFactory
from apps.social.models import Comment

pytestmark = pytest.mark.django_db


def refused(**fields):
    """Whether the database refuses a row made by the factory with these fields."""
    try:
        with transaction.atomic():
            NotificationFactory(**fields)
    except IntegrityError as error:
        return str(error)
    return None


def test_there_are_nine_types_and_no_tenth():
    assert set(NotificationType.values) == {
        "follow",
        "like",
        "comment",
        "repost",
        "verdict",
        "under_review",
        "removed",
        "emergency_demoted",
        "appeal_resolved",
    }


def test_a_row_of_a_type_that_does_not_exist_is_refused():
    # Postgres names the first check it finds broken: the shape and outcome checks list the nine
    # types too, so a ninth-and-a-half type breaks several at once.
    assert refused(type="shout") is not None


@pytest.mark.parametrize("type_", NotificationType.values)
def test_every_valid_shape_is_accepted(type_):
    recipient = VerifiedUserFactory()
    actor = VerifiedUserFactory()
    if type_ == NotificationType.FOLLOW:
        follow_item(recipient, actor)
    elif type_ == NotificationType.COMMENT:
        comment_item(recipient, actor)
    elif type_ in (NotificationType.LIKE, NotificationType.REPOST):
        NotificationFactory(recipient=recipient, actor=actor, type=type_)
    else:
        system_item(recipient, type_)
    assert Notification.objects.count() == 1


def test_a_follow_points_at_no_post_and_no_comment():
    assert "notifications_shape_valid" in refused(type=NotificationType.FOLLOW)


def test_a_comment_item_needs_its_comment():
    assert "notifications_shape_valid" in refused(type=NotificationType.COMMENT)


def test_a_like_has_no_comment():
    post = PostFactory()
    comment = Comment.objects.create(post=post, author=VerifiedUserFactory(), content="Hi")
    assert "notifications_shape_valid" in refused(
        type=NotificationType.LIKE, recipient=post.author, post=post, comment=comment
    )


@pytest.mark.parametrize("type_", [t for t in NotificationType.values if t != "follow"])
def test_every_type_but_a_follow_needs_a_post(type_):
    outcomes = {"verdict": "true", "appeal_resolved": "upheld"}
    assert "notifications_shape_valid" in refused(
        type=type_, post=None, actor=None, outcome=outcomes.get(type_, "")
    )


def test_a_verdict_needs_true_or_false():
    assert "notifications_outcome_valid" in refused(
        type=NotificationType.VERDICT, actor=None, outcome=""
    )
    assert "notifications_outcome_valid" in refused(
        type=NotificationType.VERDICT, actor=None, outcome=NotificationOutcome.UPHELD
    )


def test_an_appeal_resolved_needs_upheld_or_overturned():
    assert "notifications_outcome_valid" in refused(
        type=NotificationType.APPEAL_RESOLVED, actor=None, outcome=NotificationOutcome.TRUE
    )
    assert "notifications_outcome_valid" in refused(
        type=NotificationType.APPEAL_RESOLVED, actor=None, outcome=""
    )


def test_every_other_type_has_a_blank_outcome():
    assert "notifications_outcome_valid" in refused(
        type=NotificationType.LIKE, outcome=NotificationOutcome.TRUE
    )


def test_nobody_is_notified_of_their_own_action():
    me = VerifiedUserFactory()
    assert "notifications_not_self" in refused(recipient=me, actor=me)


def test_an_item_with_no_actor_passes_the_self_check():
    system_item(VerifiedUserFactory())
    assert Notification.objects.count() == 1


def test_one_person_likes_a_post_once_but_may_also_repost_it():
    post = PostFactory()
    fan = VerifiedUserFactory()
    NotificationFactory(recipient=post.author, actor=fan, post=post)
    assert "notifications_post_event_unique" in refused(recipient=post.author, actor=fan, post=post)
    NotificationFactory(
        recipient=post.author, actor=fan, post=post, type=NotificationType.REPOST
    )  # type is in the key: a like and a repost are two items
    assert Notification.objects.count() == 2


def test_two_people_may_like_one_post():
    post = PostFactory()
    NotificationFactory(recipient=post.author, post=post)
    NotificationFactory(recipient=post.author, post=post)
    assert Notification.objects.count() == 2


def test_a_follower_follows_once():
    me, fan = VerifiedUserFactory(), VerifiedUserFactory()
    follow_item(me, fan)
    assert "notifications_follow_unique" in refused(
        recipient=me, actor=fan, type=NotificationType.FOLLOW, post=None
    )


def test_comments_and_verdicts_are_not_deduplicated():
    post = PostFactory()
    fan = VerifiedUserFactory()
    comment_item(post.author, fan, post=post)
    comment_item(post.author, fan, post=post)
    system_item(post.author, NotificationType.UNDER_REVIEW, post=post)
    system_item(post.author, NotificationType.UNDER_REVIEW, post=post)
    assert Notification.objects.count() == 4


def test_deleting_the_recipient_deletes_their_items():
    recipient = VerifiedUserFactory()
    NotificationFactory(recipient=recipient)
    recipient.delete()
    assert Notification.objects.count() == 0


def test_deleting_the_actor_keeps_the_item_with_no_actor():
    item = NotificationFactory()
    item.actor.delete()
    item.refresh_from_db()
    assert item.actor is None


def test_deleting_the_post_deletes_its_items():
    item = NotificationFactory()
    item.post.delete()
    assert Notification.objects.count() == 0


def test_deleting_the_comment_deletes_its_item():
    item = comment_item(VerifiedUserFactory(), VerifiedUserFactory())
    item.comment.delete()
    assert Notification.objects.count() == 0


def test_str_names_the_type_and_the_recipient():
    item = NotificationFactory()
    assert str(item) == f"Like for {item.recipient_id}"
