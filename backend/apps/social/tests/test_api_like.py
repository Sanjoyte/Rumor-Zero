"""`POST` / `DELETE /api/v1/posts/{id}/like/`: idempotent, verified-only, throttled."""

import uuid

import pytest

from apps.accounts.tests.factories import UserFactory
from apps.social.models import Like
from apps.social.tests.factories import LikeFactory, PostFactory, VerifiedUserFactory

pytestmark = pytest.mark.django_db


def url(post_id):
    return f"/api/v1/posts/{post_id}/like/"


@pytest.fixture
def post():
    return PostFactory()


@pytest.fixture
def ada():
    return VerifiedUserFactory(username="ada")


def test_the_first_like_is_201_and_the_second_is_200(auth_client, ada, post):
    client = auth_client(ada)
    first = client.post(url(post.pk))
    assert (first.status_code, first.json()) == (201, {"liked": True})
    second = client.post(url(post.pk))
    assert (second.status_code, second.json()) == (200, {"liked": True})
    assert Like.objects.filter(user=ada, post=post).count() == 1


def test_unlike_is_204_every_time(auth_client, ada, post):
    LikeFactory(user=ada, post=post)
    client = auth_client(ada)
    first = client.delete(url(post.pk))
    assert first.status_code == 204
    assert not first.content
    assert client.delete(url(post.pk)).status_code == 204
    assert Like.objects.count() == 0


def test_a_like_by_someone_else_is_untouched(auth_client, ada, post):
    other = LikeFactory(post=post)
    auth_client(ada).delete(url(post.pk))
    assert list(Like.objects.all()) == [other]


def test_you_can_like_your_own_post(auth_client, ada):
    mine = PostFactory(author=ada)
    assert auth_client(ada).post(url(mine.pk)).status_code == 201


@pytest.mark.parametrize("trait", ["fact", "under_review", "verified_pipeline"])
def test_every_visible_status_can_be_liked(auth_client, ada, trait):
    assert auth_client(ada).post(url(PostFactory(**{trait: True}).pk)).status_code == 201


def test_anonymous_is_401(api_client, post):
    assert api_client.post(url(post.pk)).status_code == 401
    assert api_client.delete(url(post.pk)).status_code == 401


def test_an_unverified_user_cannot_like(auth_client, post):
    response = auth_client(UserFactory()).post(url(post.pk))
    assert response.status_code == 403
    assert response.json()["code"] == "email_unverified"
    assert Like.objects.count() == 0


def test_an_unverified_user_can_still_take_a_like_back(auth_client, post):
    user = UserFactory()
    LikeFactory(user=user, post=post)
    assert auth_client(user).delete(url(post.pk)).status_code == 204
    assert Like.objects.count() == 0


@pytest.mark.parametrize("trait", ["removed", "deleted"])
def test_a_removed_or_deleted_post_cannot_be_liked(auth_client, ada, trait):
    response = auth_client(ada).post(url(PostFactory(**{trait: True}).pk))
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"
    assert Like.objects.count() == 0


@pytest.mark.parametrize("post_id", [str(uuid.uuid4()), "not-a-uuid", "123"])
def test_an_unknown_or_malformed_id_is_a_json_404(auth_client, ada, post_id):
    client = auth_client(ada)
    for response in (client.post(url(post_id)), client.delete(url(post_id))):
        assert response.status_code == 404
        assert response.json()["code"] == "not_found"


def test_a_like_can_be_taken_back_from_a_removed_post(auth_client, ada):
    removed = PostFactory(removed=True)
    LikeFactory(user=ada, post=removed)
    assert auth_client(ada).delete(url(removed.pk)).status_code == 204
    assert Like.objects.count() == 0


def test_a_deleted_post_is_404_even_for_unlike(auth_client, ada):
    deleted = PostFactory(deleted=True)
    assert auth_client(ada).delete(url(deleted.pk)).status_code == 404


def test_liking_moves_the_post_counts(auth_client, api_client, ada, post):
    client = auth_client(ada)
    client.post(url(post.pk))
    body = client.get(f"/api/v1/posts/{post.pk}/").json()
    assert (body["like_count"], body["liked_by_me"]) == (1, True)
    assert api_client.get(f"/api/v1/posts/{post.pk}/").json()["liked_by_me"] is False
    client.delete(url(post.pk))
    assert client.get(f"/api/v1/posts/{post.pk}/").json()["like_count"] == 0


# ---------- the throttle (the real number of requests: rates are bound at import) ----------


def test_the_301st_like_request_in_an_hour_is_throttled(auth_client, ada):
    posts = [PostFactory() for _ in range(3)]
    client = auth_client(ada)
    for i in range(300):
        assert client.post(url(posts[i % 3].pk)).status_code in (200, 201)
    response = client.post(url(posts[0].pk))
    assert response.status_code == 429
    assert response.json()["code"] == "throttled"
    assert "Retry-After" in response


def test_unlike_shares_the_like_allowance(auth_client, ada, post):
    client = auth_client(ada)
    for _ in range(300):
        client.delete(url(post.pk))
    assert client.delete(url(post.pk)).status_code == 429


def test_a_401_or_403_never_counts_against_the_allowance(api_client, auth_client, ada, post):
    for _ in range(305):
        assert api_client.post(url(post.pk)).status_code == 401
    unverified = auth_client(UserFactory())
    for _ in range(305):
        assert unverified.post(url(post.pk)).status_code == 403
    assert auth_client(ada).post(url(post.pk)).status_code == 201
