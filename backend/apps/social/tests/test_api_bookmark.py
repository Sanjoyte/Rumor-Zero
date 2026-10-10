"""`POST` / `DELETE /api/v1/posts/{id}/bookmark/`: idempotent, private, any signed-in user."""

import uuid

import pytest

from apps.accounts.tests.factories import UserFactory
from apps.social.models import Bookmark
from apps.social.tests.factories import BookmarkFactory, PostFactory, VerifiedUserFactory

pytestmark = pytest.mark.django_db


def url(post_id):
    return f"/api/v1/posts/{post_id}/bookmark/"


@pytest.fixture
def post():
    return PostFactory()


@pytest.fixture
def ada():
    return VerifiedUserFactory(username="ada")


def test_the_first_bookmark_is_201_and_the_second_is_200(auth_client, ada, post):
    client = auth_client(ada)
    first = client.post(url(post.pk))
    assert (first.status_code, first.json()) == (201, {"bookmarked": True})
    second = client.post(url(post.pk))
    assert (second.status_code, second.json()) == (200, {"bookmarked": True})
    assert Bookmark.objects.filter(user=ada, post=post).count() == 1


def test_remove_is_204_every_time(auth_client, ada, post):
    BookmarkFactory(user=ada, post=post)
    client = auth_client(ada)
    first = client.delete(url(post.pk))
    assert first.status_code == 204 and not first.content
    assert client.delete(url(post.pk)).status_code == 204
    assert Bookmark.objects.count() == 0


def test_someone_elses_bookmark_is_untouched(auth_client, ada, post):
    other = BookmarkFactory(post=post)
    auth_client(ada).delete(url(post.pk))
    assert list(Bookmark.objects.all()) == [other]


def test_you_can_bookmark_your_own_false_and_pending_posts(auth_client, ada):
    client = auth_client(ada)
    for post in (
        PostFactory(author=ada),
        PostFactory(moderator_verdict=True),
        PostFactory(fact=True),
    ):
        assert client.post(url(post.pk)).status_code == 201


def test_an_unverified_user_can_bookmark_because_bookmarks_are_private(auth_client, post):
    user = UserFactory()
    assert auth_client(user).post(url(post.pk)).status_code == 201
    assert auth_client(user).delete(url(post.pk)).status_code == 204


def test_anonymous_is_401(api_client, post):
    assert api_client.post(url(post.pk)).status_code == 401
    assert api_client.delete(url(post.pk)).status_code == 401


@pytest.mark.parametrize("trait", ["removed", "deleted"])
def test_a_removed_or_deleted_post_cannot_be_bookmarked(auth_client, ada, trait):
    response = auth_client(ada).post(url(PostFactory(**{trait: True}).pk))
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"
    assert Bookmark.objects.count() == 0


def test_a_bookmark_can_be_removed_from_a_removed_post_but_a_deleted_one_is_404(auth_client, ada):
    removed, deleted = PostFactory(removed=True), PostFactory(deleted=True)
    BookmarkFactory(user=ada, post=removed)
    client = auth_client(ada)
    assert client.delete(url(removed.pk)).status_code == 204
    assert client.delete(url(deleted.pk)).status_code == 404


@pytest.mark.parametrize("post_id", [str(uuid.uuid4()), "not-a-uuid", "123"])
def test_an_unknown_or_malformed_id_is_a_json_404(auth_client, ada, post_id):
    client = auth_client(ada)
    for response in (client.post(url(post_id)), client.delete(url(post_id))):
        assert response.status_code == 404
        assert response.json()["code"] == "not_found"


def test_the_flag_is_yours_alone_and_nothing_counts_bookmarks(auth_client, api_client, ada, post):
    client = auth_client(ada)
    client.post(url(post.pk))
    mine = client.get(f"/api/v1/posts/{post.pk}/").json()
    assert mine["bookmarked_by_me"] is True
    other = auth_client(VerifiedUserFactory()).get(f"/api/v1/posts/{post.pk}/").json()
    anonymous = api_client.get(f"/api/v1/posts/{post.pk}/").json()
    assert other["bookmarked_by_me"] is False and anonymous["bookmarked_by_me"] is False
    # no bookmark count anywhere in the object
    assert not [key for key in mine if "bookmark" in key and key != "bookmarked_by_me"]
    client.delete(url(post.pk))
    assert client.get(f"/api/v1/posts/{post.pk}/").json()["bookmarked_by_me"] is False


# ---------- the throttle (the real number of requests: rates are bound at import) ----------


def test_the_301st_bookmark_request_in_an_hour_is_throttled(auth_client, ada):
    posts = [PostFactory() for _ in range(3)]
    client = auth_client(ada)
    for i in range(300):
        assert client.post(url(posts[i % 3].pk)).status_code in (200, 201)
    response = client.post(url(posts[0].pk))
    assert response.status_code == 429
    assert response.json()["code"] == "throttled"
    assert "Retry-After" in response


def test_bookmarks_have_their_own_allowance_not_the_like_one(auth_client, ada):
    """Both are 300 an hour, so only a second action tells the two buckets apart."""
    posts = [PostFactory() for _ in range(3)]
    client = auth_client(ada)
    for i in range(300):
        assert client.post(url(posts[i % 3].pk)).status_code in (200, 201)
    assert client.post(url(posts[0].pk)).status_code == 429
    assert client.post(f"/api/v1/posts/{posts[0].pk}/like/").status_code == 201


def test_remove_shares_the_bookmark_allowance(auth_client, ada, post):
    client = auth_client(ada)
    for _ in range(300):
        client.delete(url(post.pk))
    assert client.delete(url(post.pk)).status_code == 429


def test_a_401_never_counts_against_the_allowance(api_client, auth_client, ada, post):
    for _ in range(305):
        assert api_client.post(url(post.pk)).status_code == 401
    assert auth_client(ada).post(url(post.pk)).status_code == 201
