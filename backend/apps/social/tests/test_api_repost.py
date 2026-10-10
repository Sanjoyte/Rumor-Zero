"""`POST` / `DELETE /api/v1/posts/{id}/repost/`: idempotent, verified-only, throttled, with the
refusals of ARCHITECTURE §4d."""

import uuid

import pytest

from apps.accounts.tests.factories import UserFactory
from apps.posts.models import PostStatus
from apps.social.models import Repost
from apps.social.tests.factories import PostFactory, RepostFactory, VerifiedUserFactory

pytestmark = pytest.mark.django_db


def url(post_id):
    return f"/api/v1/posts/{post_id}/repost/"


@pytest.fixture
def post():
    return PostFactory()


@pytest.fixture
def ada():
    return VerifiedUserFactory(username="ada")


def test_the_first_repost_is_201_and_the_second_is_200(auth_client, ada, post):
    client = auth_client(ada)
    first = client.post(url(post.pk))
    assert (first.status_code, first.json()) == (201, {"reposted": True})
    second = client.post(url(post.pk))
    assert (second.status_code, second.json()) == (200, {"reposted": True})
    assert Repost.objects.filter(user=ada, post=post).count() == 1


def test_unrepost_is_204_every_time(auth_client, ada, post):
    RepostFactory(user=ada, post=post)
    client = auth_client(ada)
    first = client.delete(url(post.pk))
    assert first.status_code == 204 and not first.content
    assert client.delete(url(post.pk)).status_code == 204
    assert Repost.objects.count() == 0


def test_someone_elses_repost_is_untouched(auth_client, ada, post):
    other = RepostFactory(post=post)
    auth_client(ada).delete(url(post.pk))
    assert list(Repost.objects.all()) == [other]


def test_the_status_at_repost_is_the_status_at_the_time(auth_client, ada):
    fact = PostFactory(fact=True)
    auth_client(ada).post(url(fact.pk))
    assert Repost.objects.get().status_at_repost == PostStatus.PENDING


def test_your_own_post_is_409_cannot_repost_own(auth_client, ada):
    mine = PostFactory(author=ada)
    response = auth_client(ada).post(url(mine.pk))
    assert response.status_code == 409
    assert response.json()["code"] == "cannot_repost_own"
    assert response.json()["detail"] == "You can't repost your own post."
    assert Repost.objects.count() == 0


def test_a_false_post_is_409_cannot_repost_false(auth_client, ada):
    false = PostFactory(moderator_verdict=True)
    response = auth_client(ada).post(url(false.pk))
    assert response.status_code == 409
    assert response.json()["code"] == "cannot_repost_false"
    assert "FALSE" in response.json()["detail"]
    assert Repost.objects.count() == 0


def test_a_post_under_review_after_being_false_is_409_cannot_repost_false(auth_client, ada):
    reviewed = PostFactory(
        moderator_verdict=True,
        status=PostStatus.UNDER_REVIEW,
        pre_review_status=PostStatus.VERIFIED_FALSE,
    )
    response = auth_client(ada).post(url(reviewed.pk))
    assert response.status_code == 409
    assert response.json()["code"] == "cannot_repost_false"
    assert Repost.objects.count() == 0


@pytest.mark.parametrize("trait", ["fact", "under_review", "verified_pipeline"])
def test_every_other_visible_status_can_be_reposted(auth_client, ada, trait):
    assert auth_client(ada).post(url(PostFactory(**{trait: True}).pk)).status_code == 201


def test_a_post_that_turned_false_after_you_reposted_it_is_still_200(auth_client, ada):
    false = PostFactory(fact=True)
    client = auth_client(ada)
    assert client.post(url(false.pk)).status_code == 201
    false.status = PostStatus.VERIFIED_FALSE
    false.verdict_source = "moderator"
    false.save()
    assert client.post(url(false.pk)).status_code == 200
    assert client.delete(url(false.pk)).status_code == 204


def test_anonymous_is_401(api_client, post):
    assert api_client.post(url(post.pk)).status_code == 401
    assert api_client.delete(url(post.pk)).status_code == 401


def test_an_unverified_user_cannot_repost(auth_client, post):
    response = auth_client(UserFactory()).post(url(post.pk))
    assert response.status_code == 403
    assert response.json()["code"] == "email_unverified"
    assert Repost.objects.count() == 0


def test_an_unverified_user_can_still_take_a_repost_back(auth_client, post):
    user = UserFactory()
    RepostFactory(user=user, post=post)
    assert auth_client(user).delete(url(post.pk)).status_code == 204
    assert Repost.objects.count() == 0


@pytest.mark.parametrize("trait", ["removed", "deleted"])
def test_a_removed_or_deleted_post_cannot_be_reposted_not_even_by_its_author(
    auth_client, ada, trait
):
    post = PostFactory(**{trait: True})
    for user in (ada, post.author):
        response = auth_client(user).post(url(post.pk))
        assert response.status_code == 404
        assert response.json()["code"] == "not_found"
    assert Repost.objects.count() == 0


@pytest.mark.parametrize("trait", ["removed", "deleted"])
def test_a_repost_of_a_removed_or_deleted_post_can_be_taken_back(auth_client, ada, trait):
    """User decision 2026-10-10: the 'no longer available' card can always be undone."""
    post = PostFactory(**{trait: True})
    RepostFactory(user=ada, post=post)
    assert auth_client(ada).delete(url(post.pk)).status_code == 204
    assert Repost.objects.count() == 0


@pytest.mark.parametrize("post_id", [str(uuid.uuid4()), "not-a-uuid", "123"])
def test_an_unknown_or_malformed_id_is_a_json_404(auth_client, ada, post_id):
    client = auth_client(ada)
    for response in (client.post(url(post_id)), client.delete(url(post_id))):
        assert response.status_code == 404
        assert response.json()["code"] == "not_found"


def test_reposting_moves_the_post_counts_and_flags(auth_client, api_client, ada, post):
    client = auth_client(ada)
    client.post(url(post.pk))
    body = client.get(f"/api/v1/posts/{post.pk}/").json()
    assert (body["repost_count"], body["reposted_by_me"]) == (1, True)
    anonymous = api_client.get(f"/api/v1/posts/{post.pk}/").json()
    assert (anonymous["repost_count"], anonymous["reposted_by_me"]) == (1, False)
    client.delete(url(post.pk))
    assert client.get(f"/api/v1/posts/{post.pk}/").json()["repost_count"] == 0


def test_a_repost_item_acts_on_the_original(auth_client, ada, post):
    """ "Reposting a repost reposts the original": the API has no repost id, only the post's."""
    bo = VerifiedUserFactory()
    RepostFactory(user=bo, post=post)
    assert auth_client(ada).post(url(post.pk)).status_code == 201
    assert set(Repost.objects.values_list("post_id", flat=True)) == {post.pk}
    assert Repost.objects.count() == 2


# ---------- the throttle (the real number of requests: rates are bound at import) ----------


def test_the_101st_repost_request_in_an_hour_is_throttled(auth_client, ada):
    posts = [PostFactory() for _ in range(3)]
    client = auth_client(ada)
    for i in range(100):
        assert client.post(url(posts[i % 3].pk)).status_code in (200, 201)
    response = client.post(url(posts[0].pk))
    assert response.status_code == 429
    assert response.json()["code"] == "throttled"
    assert "Retry-After" in response


def test_unrepost_shares_the_repost_allowance(auth_client, ada, post):
    client = auth_client(ada)
    for _ in range(100):
        client.delete(url(post.pk))
    assert client.delete(url(post.pk)).status_code == 429


def test_a_401_or_403_never_counts_against_the_allowance(api_client, auth_client, ada, post):
    for _ in range(105):
        assert api_client.post(url(post.pk)).status_code == 401
    unverified = auth_client(UserFactory())
    for _ in range(105):
        assert unverified.post(url(post.pk)).status_code == 403
    assert auth_client(ada).post(url(post.pk)).status_code == 201


def test_a_409_does_count_but_a_404_is_after_the_throttle_too(auth_client, ada):
    mine = PostFactory(author=ada)
    client = auth_client(ada)
    for _ in range(100):
        assert client.post(url(mine.pk)).status_code == 409
    assert client.post(url(mine.pk)).status_code == 429
