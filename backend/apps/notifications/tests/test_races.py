"""Two simultaneous requests make one item: the database's partial unique indexes decide, not a
check-then-write in Python."""

import pytest
from django.db import connection

from apps.accounts.tests.conftest import run_together
from apps.notifications.models import Notification
from apps.posts.tests.factories import PostFactory, VerifiedUserFactory
from apps.social import services

pytestmark = pytest.mark.django_db(transaction=True)


def together(task):
    def go():
        try:
            return task()
        finally:
            connection.close()

    return run_together(go, go, go)


def test_three_simultaneous_follows_make_one_item():
    me, fan = VerifiedUserFactory(), VerifiedUserFactory()
    together(lambda: services.follow(follower=fan, target=me))
    assert Notification.objects.filter(type="follow").count() == 1


def test_three_simultaneous_likes_make_one_item():
    post, fan = PostFactory(), VerifiedUserFactory()
    together(lambda: services.like(user=fan, post_id=post.pk))
    assert Notification.objects.filter(type="like").count() == 1


def test_three_simultaneous_reposts_make_one_item():
    post, fan = PostFactory(), VerifiedUserFactory()
    together(lambda: services.repost(user=fan, post_id=post.pk))
    assert Notification.objects.filter(type="repost").count() == 1


def test_the_notification_notify_does_not_hide_a_conflict_that_is_not_the_dedupe():
    """The like and its item commit together: if the item cannot be written, no like stays."""
    from unittest import mock

    post, fan = PostFactory(), VerifiedUserFactory()
    with (
        mock.patch("apps.notifications.services.notify", side_effect=RuntimeError("boom")),
        pytest.raises(RuntimeError),
    ):
        services.like(user=fan, post_id=post.pk)
    from apps.social.models import Like

    assert Like.objects.count() == 0
