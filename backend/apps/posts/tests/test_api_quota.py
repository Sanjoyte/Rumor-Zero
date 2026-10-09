from datetime import timedelta

import pytest
from django.utils import timezone

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
