from datetime import timedelta

import pytest
from django.utils import timezone

from apps.posts.models import Post
from apps.posts.tests.factories import PostFactory, UserFactory, VerifiedUserFactory

pytestmark = pytest.mark.django_db

URL = "/api/v1/me/fact-quota/"


@pytest.fixture
def user(fact_limit):
    return VerifiedUserFactory()


def test_anonymous_gets_401(api_client):
    response = api_client.get(URL)
    assert response.status_code == 401
    assert response.json()["code"] == "not_authenticated"


def test_an_unverified_user_can_ask(auth_client):
    # Reading the quota needs a login, not a verified email (the composer shows its own prompt).
    assert auth_client(UserFactory()).get(URL).status_code == 200


def test_a_fresh_account_has_all_ten(auth_client, user):
    response = auth_client(user).get(URL)
    assert response.status_code == 200
    assert response.json() == {
        "limit": 10,
        "used": 0,
        "remaining": 10,
        "window_hours": 24,
        "next_slot_at": None,
        # A fresh account is too new for an emergency (Part 11C).
        "emergency": {
            "allowed": False,
            "reason": "account_too_new",
            "next_allowed_at": response.json()["emergency"]["next_allowed_at"],
            "block_days": 30,
        },
    }
    assert "no-store" in response["Cache-Control"]


def test_it_counts_the_fact_posts_of_the_last_24_hours(auth_client, user):
    now = timezone.now()
    PostFactory(author=user, fact=True, created_at=now - timedelta(hours=2))
    PostFactory(author=user, fact=True, created_at=now - timedelta(hours=30))  # aged out
    PostFactory(author=user)  # an opinion
    PostFactory(fact=True)  # someone else's
    body = auth_client(user).get(URL).json()
    assert (body["used"], body["remaining"]) == (1, 9)


def test_next_slot_is_shown_when_nothing_is_left(auth_client, user):
    now = timezone.now()
    oldest = now - timedelta(hours=9)
    PostFactory(author=user, fact=True, created_at=oldest)
    for i in range(9):
        PostFactory(author=user, fact=True, created_at=now - timedelta(hours=1, seconds=i))
    body = auth_client(user).get(URL).json()
    assert body["remaining"] == 0
    expected = (oldest + timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%S")
    assert body["next_slot_at"].startswith(expected)
    assert body["next_slot_at"].endswith("Z")


def test_the_limit_comes_from_the_platform_settings(auth_client, user, fact_limit):
    fact_limit(3)
    PostFactory(author=user, fact=True)
    body = auth_client(user).get(URL).json()
    assert (body["limit"], body["used"], body["remaining"]) == (3, 1, 2)


def test_a_limit_of_zero_is_reported_as_paused(auth_client, user, fact_limit):
    fact_limit(0)
    body = auth_client(user).get(URL).json()
    assert (body["limit"], body["remaining"], body["next_slot_at"]) == (0, 0, None)


# ---------- Part 11C: the `emergency` block ----------


@pytest.fixture
def elder(fact_limit):
    return VerifiedUserFactory(created_at=timezone.now() - timedelta(days=30))


def emergency_of(client):
    return client.get(URL).json()["emergency"]


def test_an_eligible_person_may_post_an_emergency(auth_client, elder):
    assert emergency_of(auth_client(elder)) == {
        "allowed": True,
        "reason": None,
        "next_allowed_at": None,
        "block_days": 30,
    }


def test_the_block_length_is_the_current_setting(auth_client, elder, emergency_settings):
    emergency_settings(emergency_false_cooldown_days=12)
    assert emergency_of(auth_client(elder))["block_days"] == 12


def test_an_unverified_account_learns_its_reason_here(auth_client):
    """The create endpoint's permission answers `email_unverified` first; this is where the
    composer reads the reason."""
    person = UserFactory(created_at=timezone.now() - timedelta(days=30))
    block = emergency_of(auth_client(person))
    assert (block["allowed"], block["reason"], block["next_allowed_at"]) == (
        False,
        "unverified",
        None,
    )


def test_a_new_account_is_told_when_it_may(auth_client, fact_limit):
    created = timezone.now() - timedelta(days=3)
    block = emergency_of(auth_client(VerifiedUserFactory(created_at=created)))
    assert block["reason"] == "account_too_new"
    assert block["next_allowed_at"].startswith(
        (created + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%S")
    )


def test_each_other_reason_is_reported(auth_client, elder, fact_limit):
    from apps.accounts.models import User

    client = auth_client(elder)
    User.objects.filter(pk=elder.pk).update(reputation_score=39)
    assert emergency_of(client)["reason"] == "score_too_low"
    until = timezone.now() + timedelta(days=5)
    User.objects.filter(pk=elder.pk).update(reputation_score=40, emergency_blocked_until=until)
    block = emergency_of(client)
    assert block["reason"] == "blocked"
    assert block["next_allowed_at"].startswith(until.strftime("%Y-%m-%dT%H:%M:%S"))
    User.objects.filter(pk=elder.pk).update(emergency_blocked_until=None)
    made = timezone.now() - timedelta(hours=2)
    PostFactory(
        author=elder,
        fact=True,
        is_emergency=True,
        emergency_expires_at=made + timedelta(hours=24),
        created_at=made,
    )
    block = emergency_of(client)
    assert block["reason"] == "daily_limit"
    assert block["next_allowed_at"].startswith(
        (made + timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%S")
    )
    fact_limit(1)
    Post.objects.update(is_emergency=False, emergency_expires_at=None)
    assert emergency_of(client)["reason"] == "fact_quota"


def test_paused_emergencies_have_no_time(auth_client, elder, emergency_settings):
    emergency_settings(emergency_posts_per_day=0)
    block = emergency_of(auth_client(elder))
    assert (block["reason"], block["next_allowed_at"]) == ("daily_limit", None)


def test_the_quota_still_costs_two_queries(auth_client, elder, django_assert_num_queries):
    """You (the authentication) and your fact posts of the window: the emergency block reads
    the same rows."""
    client = auth_client(elder)
    client.get(URL)  # the platform settings are cached from here on
    with django_assert_num_queries(2):
        assert client.get(URL).status_code == 200
