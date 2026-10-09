"""`GET /api/v1/users/{username}/` (ARCHITECTURE §9): the profile, its counts, who is asking."""

import pytest

from apps.accounts.tests.factories import UserFactory
from apps.posts.models import PostStatus
from apps.social.tests.factories import FollowFactory, PostFactory, VerifiedUserFactory

pytestmark = pytest.mark.django_db

PROFILE_KEYS = {
    "id",
    "username",
    "display_name",
    "bio",
    "avatar_url",
    "created_at",
    "counts",
    "reputation",
    "is_following",
    "is_me",
}
COUNT_KEYS = {"followers", "following", "posts", "verified", "false"}


def url(username):
    return f"/api/v1/users/{username}/"


@pytest.fixture
def ada():
    return VerifiedUserFactory(username="ada", display_name="Ada L", bio="Counting things.")


def test_the_profile_has_exactly_these_keys(api_client, ada):
    response = api_client.get(url("ada"))
    assert response.status_code == 200
    body = response.json()
    assert set(body) == PROFILE_KEYS
    assert set(body["counts"]) == COUNT_KEYS
    assert body["id"] == str(ada.pk)
    assert (body["username"], body["display_name"], body["bio"]) == (
        "ada",
        "Ada L",
        "Counting things.",
    )
    assert body["avatar_url"] is None
    assert body["created_at"].endswith("Z")
    assert "no-store" in response["Cache-Control"]


def test_nothing_private_leaks(api_client, ada):
    text = api_client.get(url("ada")).content.decode()
    assert ada.email not in text
    for word in ("email", "role", "is_staff", "password"):
        assert word not in text


@pytest.mark.parametrize("name", ["ada", "ADA", "Ada", "%20ada", "ａｄａ"])
def test_lookup_is_case_insensitive(api_client, ada, name):
    assert api_client.get(url(name)).json()["username"] == "ada"


@pytest.mark.parametrize("name", ["nobody", "a", "x" * 300, "a b", "ada.", "%00"])
def test_unknown_and_malformed_names_are_a_json_404(api_client, ada, name):
    response = api_client.get(url(name))
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_an_inactive_user_is_a_404(api_client):
    VerifiedUserFactory(username="gone", is_active=False)
    assert api_client.get(url("gone")).status_code == 404


def test_an_unverified_user_has_a_profile(api_client):
    UserFactory(username="newbie")
    assert api_client.get(url("newbie")).status_code == 200


def test_counts_follow_the_rules(api_client, ada):
    for _ in range(3):
        FollowFactory(following=ada)
    for _ in range(2):
        FollowFactory(follower=ada)
    FollowFactory()  # unrelated
    # Visible: a published opinion, a pending fact, a verified one, a FALSE one, one under review.
    PostFactory(author=ada)
    PostFactory(author=ada, fact=True)
    PostFactory(author=ada, verified_pipeline=True)
    PostFactory(author=ada, moderator_verdict=True)
    PostFactory(author=ada, fact=True, status=PostStatus.UNDER_REVIEW)
    # Not visible: removed. Deleted: hidden, but its verdict still counts.
    PostFactory(author=ada, removed=True)
    PostFactory(author=ada, verified_pipeline=True, deleted=True)
    PostFactory(author=ada, moderator_verdict=True, deleted=True)
    PostFactory(author=ada, moderator_verdict=True, deleted=True)
    PostFactory(author=ada, deleted=True)
    PostFactory(verified_pipeline=True)  # someone else's
    counts = api_client.get(url("ada")).json()["counts"]
    assert counts == {"followers": 3, "following": 2, "posts": 5, "verified": 2, "false": 3}


def test_a_removed_post_that_was_verified_counts_in_neither_verdict(api_client, ada):
    PostFactory(
        author=ada, fact=True, status=PostStatus.REMOVED, pre_removal_status="verified_true"
    )
    counts = api_client.get(url("ada")).json()["counts"]
    assert (counts["posts"], counts["verified"], counts["false"]) == (0, 0, 0)


def test_a_brand_new_account_has_all_zeros(api_client, ada):
    counts = api_client.get(url("ada")).json()["counts"]
    assert counts == {"followers": 0, "following": 0, "posts": 0, "verified": 0, "false": 0}


def test_a_visitor_is_not_following_and_is_not_me(api_client, ada):
    FollowFactory(following=ada)
    body = api_client.get(url("ada")).json()
    assert (body["is_following"], body["is_me"]) == (False, False)


def test_is_following_and_is_me_for_the_signed_in(auth_client, ada):
    bo, cy = VerifiedUserFactory(), VerifiedUserFactory()
    FollowFactory(follower=bo, following=ada)
    as_bo = auth_client(bo).get(url("ada")).json()
    as_cy = auth_client(cy).get(url("ada")).json()
    as_ada = auth_client(ada).get(url("ada")).json()
    assert (as_bo["is_following"], as_bo["is_me"]) == (True, False)
    assert (as_cy["is_following"], as_cy["is_me"]) == (False, False)
    assert (as_ada["is_following"], as_ada["is_me"]) == (False, True)


def test_following_is_one_way(auth_client, ada):
    bo = VerifiedUserFactory(username="bob")
    FollowFactory(follower=ada, following=bo)
    assert auth_client(ada).get(url("bob")).json()["is_following"] is True
    assert auth_client(bo).get(url("ada")).json()["is_following"] is False


def test_the_reputation_block_hides_the_score_until_three_events(api_client):
    UserFactory(username="fresh", reputation_score=77, reputation_sample=2)
    UserFactory(username="known", reputation_score=77, reputation_sample=3)
    assert api_client.get(url("fresh")).json()["reputation"] == {"score": None, "sample": 2}
    assert api_client.get(url("known")).json()["reputation"] == {"score": 77, "sample": 3}


def test_a_photo_builds_the_avatar_url(api_client):
    user = VerifiedUserFactory(username="pic", avatar_version="abc123")
    expected = f"/api/v1/avatars/{user.pk}/abc123-96.webp"
    assert api_client.get(url("pic")).json()["avatar_url"] == expected


def test_a_stale_token_on_this_public_read_is_a_401(api_client, ada):
    response = api_client.get(url("ada"), HTTP_AUTHORIZATION="Bearer not-a-token")
    assert response.status_code == 401


def test_the_profile_is_one_query_anonymous_and_two_signed_in(
    api_client, auth_client, ada, django_assert_num_queries
):
    viewer = auth_client(VerifiedUserFactory())
    with django_assert_num_queries(1):
        assert api_client.get(url("ada")).status_code == 200
    with django_assert_num_queries(2):
        assert viewer.get(url("ada")).status_code == 200


def test_the_query_count_does_not_grow_with_the_data(
    api_client, auth_client, ada, django_assert_num_queries
):
    for _ in range(25):
        FollowFactory(following=ada)
        PostFactory(author=ada, verified_pipeline=True)
    viewer = auth_client(VerifiedUserFactory())
    with django_assert_num_queries(1):
        assert api_client.get(url("ada")).status_code == 200
    with django_assert_num_queries(2):
        assert viewer.get(url("ada")).status_code == 200
