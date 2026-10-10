import pytest
from django.core.cache import cache
from django.db import connection

from apps.accounts.tests.conftest import run_together
from apps.social import feed, services
from apps.social.models import Follow
from apps.social.tests.factories import FollowFactory, UserFactory, VerifiedUserFactory

pytestmark = pytest.mark.django_db


def test_follow_creates_once_and_then_reports_it_already_existed():
    ada, bo = VerifiedUserFactory(), VerifiedUserFactory()
    assert services.follow(follower=ada, target=bo) is True
    assert services.follow(follower=ada, target=bo) is False
    assert Follow.objects.filter(follower=ada, following=bo).count() == 1


def test_following_yourself_raises_and_writes_nothing():
    ada = VerifiedUserFactory()
    with pytest.raises(services.SelfFollow):
        services.follow(follower=ada, target=ada)
    assert Follow.objects.count() == 0


def test_unfollow_removes_the_follow_and_is_quiet_when_there_is_none():
    follow = FollowFactory()
    services.unfollow(follower=follow.follower, target=follow.following)
    assert Follow.objects.count() == 0
    services.unfollow(follower=follow.follower, target=follow.following)  # no error


def test_unfollow_only_removes_that_pair():
    ada, bo, cy = (VerifiedUserFactory() for _ in range(3))
    FollowFactory(follower=ada, following=bo)
    FollowFactory(follower=ada, following=cy)
    FollowFactory(follower=cy, following=bo)
    services.unfollow(follower=ada, target=bo)
    assert set(Follow.objects.values_list("follower_id", "following_id")) == {
        (ada.pk, cy.pk),
        (cy.pk, bo.pk),
    }


@pytest.mark.django_db(transaction=True)
def test_two_simultaneous_follows_make_one_row_and_no_error():
    ada, bo = VerifiedUserFactory(), VerifiedUserFactory()

    def go():
        try:
            return services.follow(follower=ada, target=bo)
        finally:
            connection.close()

    results = run_together(go, go)
    assert sorted(results) == [False, True]
    assert Follow.objects.filter(follower=ada, following=bo).count() == 1


def test_follow_and_unfollow_forget_the_followers_cached_feed():
    ada, bo = VerifiedUserFactory(), VerifiedUserFactory()
    key = feed.cache_key(ada.pk)
    cache.set(key, {"items": [], "next": None}, 60)
    services.follow(follower=ada, target=bo)
    assert cache.get(key) is None
    cache.set(key, {"items": [], "next": None}, 60)
    services.unfollow(follower=ada, target=bo)
    assert cache.get(key) is None


def test_a_refused_self_follow_leaves_the_cache_alone():
    ada = VerifiedUserFactory()
    key = feed.cache_key(ada.pk)
    cache.set(key, {"items": [], "next": None}, 60)
    with pytest.raises(services.SelfFollow):
        services.follow(follower=ada, target=ada)
    assert cache.get(key) is not None


def test_find_active_user_is_case_insensitive_and_skips_inactive_and_junk():
    ada = VerifiedUserFactory(username="ada")
    VerifiedUserFactory(username="gone", is_active=False)
    assert services.find_active_user("ada") == ada
    assert services.find_active_user("ADA") == ada
    assert services.find_active_user("  Ada ") == ada
    assert services.find_active_user("ａｄａ") == ada  # fullwidth, NFKC-normalised
    assert services.find_active_user("gone") is None
    assert services.find_active_user("nobody") is None
    assert services.find_active_user("x" * 500) is None
    assert services.find_active_user(None) is None


def test_unverified_users_can_still_be_found():
    ada = UserFactory(username="adaunv")
    assert services.find_active_user("adaunv") == ada


@pytest.mark.parametrize("raw", ["ad\x00a", "ada\x00", "a\nda", "ab", "x" * 31, "ada!", "", "   "])
def test_lookup_name_refuses_anything_that_cannot_be_a_username(raw):
    assert services.lookup_name(raw) is None


def test_lookup_name_normalises():
    assert services.lookup_name("  ADA_1 ") == "ada_1"
