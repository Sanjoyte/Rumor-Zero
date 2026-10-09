"""`POST` / `DELETE /api/v1/users/{username}/follow/`: idempotent, verified-only, throttled."""

import pytest

from apps.accounts.tests.factories import UserFactory
from apps.social.models import Follow
from apps.social.tests.factories import FollowFactory, VerifiedUserFactory

pytestmark = pytest.mark.django_db


def url(username):
    return f"/api/v1/users/{username}/follow/"


@pytest.fixture
def bo():
    return VerifiedUserFactory(username="bob")


@pytest.fixture
def ada():
    return VerifiedUserFactory(username="ada")


def test_the_first_follow_is_201_and_the_second_is_200(auth_client, ada, bo):
    client = auth_client(ada)
    first = client.post(url("bob"))
    assert (first.status_code, first.json()) == (201, {"is_following": True})
    second = client.post(url("bob"))
    assert (second.status_code, second.json()) == (200, {"is_following": True})
    assert Follow.objects.filter(follower=ada, following=bo).count() == 1


def test_the_target_name_is_case_insensitive(auth_client, ada, bo):
    assert auth_client(ada).post(url("BOB")).status_code == 201


def test_unfollow_is_204_every_time(auth_client, ada, bo):
    FollowFactory(follower=ada, following=bo)
    client = auth_client(ada)
    first = client.delete(url("bob"))
    assert first.status_code == 204
    assert not first.content
    assert client.delete(url("bob")).status_code == 204
    assert Follow.objects.count() == 0


def test_following_yourself_is_400_with_a_code(auth_client, ada):
    response = auth_client(ada).post(url("ada"))
    assert response.status_code == 400
    assert response.json()["code"] == "cannot_follow_self"
    assert Follow.objects.count() == 0


def test_unfollowing_yourself_is_quiet(auth_client, ada):
    assert auth_client(ada).delete(url("ada")).status_code == 204


def test_anonymous_is_401(api_client, bo):
    assert api_client.post(url("bob")).status_code == 401
    assert api_client.delete(url("bob")).status_code == 401


def test_an_unverified_user_cannot_follow(auth_client, bo):
    response = auth_client(UserFactory()).post(url("bob"))
    assert response.status_code == 403
    assert response.json()["code"] == "email_unverified"
    assert Follow.objects.count() == 0


def test_an_unverified_user_can_still_unfollow(auth_client, bo):
    unverified = UserFactory()
    FollowFactory(follower=unverified, following=bo)
    assert auth_client(unverified).delete(url("bob")).status_code == 204
    assert Follow.objects.count() == 0


@pytest.mark.parametrize("method", ["post", "delete"])
@pytest.mark.parametrize("name", ["nobody", "a", "x" * 200, "bo\x00b"])
def test_an_unknown_or_malformed_target_is_404(auth_client, ada, method, name):
    response = getattr(auth_client(ada), method)(url(name))
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_an_inactive_target_is_404(auth_client, ada):
    VerifiedUserFactory(username="gone", is_active=False)
    assert auth_client(ada).post(url("gone")).status_code == 404


def test_other_methods_are_refused(auth_client, ada, bo):
    assert auth_client(ada).get(url("bob")).status_code == 405
    assert auth_client(ada).put(url("bob")).status_code == 405


def test_following_moves_the_counts(auth_client, api_client, ada, bo):
    client = auth_client(ada)
    client.post(url("bob"))
    assert api_client.get("/api/v1/users/bob/").json()["counts"]["followers"] == 1
    assert api_client.get("/api/v1/users/ada/").json()["counts"]["following"] == 1
    client.delete(url("bob"))
    assert api_client.get("/api/v1/users/bob/").json()["counts"]["followers"] == 0


# ---------- the throttle (the real number of requests: rates are bound at import) ----------


def test_the_101st_follow_request_in_an_hour_is_throttled(auth_client, ada, bo):
    client = auth_client(ada)
    for _ in range(100):
        assert client.post(url("bob")).status_code in (200, 201)
    response = client.post(url("bob"))
    assert response.status_code == 429
    assert response.json()["code"] == "throttled"
    assert "Retry-After" in response


def test_unfollow_shares_the_follow_allowance(auth_client, ada, bo):
    client = auth_client(ada)
    for _ in range(100):
        client.delete(url("bob"))
    assert client.delete(url("bob")).status_code == 429


def test_refused_requests_do_not_use_the_allowance(auth_client, api_client, ada, bo):
    for _ in range(120):
        assert api_client.post(url("bob")).status_code == 401
    unverified = auth_client(UserFactory())
    for _ in range(120):
        assert unverified.post(url("bob")).status_code == 403
    client = auth_client(ada)
    for _ in range(100):
        assert client.post(url("bob")).status_code in (200, 201)
    assert client.post(url("bob")).status_code == 429


def test_the_allowance_is_per_user(auth_client, ada, bo):
    for _ in range(101):
        auth_client(ada).post(url("bob"))
    assert auth_client(VerifiedUserFactory()).post(url("bob")).status_code == 201
