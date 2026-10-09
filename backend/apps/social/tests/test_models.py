"""`social.Follow` (ARCHITECTURE §2): the pair is unique, nobody follows themselves, and the two
list indexes exist."""

import pytest
from django.db import IntegrityError, connection, transaction

from apps.accounts.models import User
from apps.social.models import Follow
from apps.social.tests.factories import FollowFactory, VerifiedUserFactory

pytestmark = pytest.mark.django_db


def test_a_follow_links_two_users():
    follow = FollowFactory()
    assert follow.follower != follow.following
    assert str(follow) == f"{follow.follower_id} follows {follow.following_id}"


def test_the_pair_is_unique_at_the_database_level():
    follow = FollowFactory()
    with pytest.raises(IntegrityError) as caught, transaction.atomic():
        Follow.objects.create(follower=follow.follower, following=follow.following)
    assert "follows_pair_unique" in str(caught.value)


def test_the_opposite_direction_is_a_different_follow():
    follow = FollowFactory()
    Follow.objects.create(follower=follow.following, following=follow.follower)
    assert Follow.objects.count() == 2


def test_nobody_can_follow_themselves_at_the_database_level():
    user = VerifiedUserFactory()
    with pytest.raises(IntegrityError) as caught, transaction.atomic():
        Follow.objects.create(follower=user, following=user)
    assert "follows_not_self" in str(caught.value)


def test_the_two_list_indexes_exist_and_are_ordered_newest_first():
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'social_follow'"
        )
        indexes = dict(cursor.fetchall())
    assert "(following_id, created_at DESC, id DESC)" in indexes["follows_following_idx"]
    assert "(follower_id, created_at DESC, id DESC)" in indexes["follows_follower_idx"]


def test_deleting_a_user_deletes_their_follows_in_both_directions():
    ada, bo, cy = (VerifiedUserFactory() for _ in range(3))
    FollowFactory(follower=ada, following=bo)
    FollowFactory(follower=cy, following=ada)
    FollowFactory(follower=bo, following=cy)
    ada.delete()
    assert list(Follow.objects.values_list("follower_id", "following_id")) == [(bo.pk, cy.pk)]
    assert User.objects.filter(pk=bo.pk).exists()
