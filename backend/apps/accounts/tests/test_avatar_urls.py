"""`avatar_url` in every payload that carries a user (ARCHITECTURE §9): null for initials, the 96 px
image in lists, the 256 px image on `/me` and a profile, and never an extra query for it."""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.accounts.serializers import avatar_url
from apps.accounts.tests import photo_fixtures as fx
from apps.accounts.tests.conftest import access_token_for
from apps.notifications.models import NotificationType
from apps.notifications.tests.factories import NotificationFactory
from apps.posts.tests.factories import PostFactory, VerifiedUserFactory
from apps.social.tests.factories import CommentFactory, FollowFactory, RepostFactory

pytestmark = pytest.mark.django_db


def person(**kwargs):
    """A verified user with a photo, and the two URLs that photo can have."""
    user = VerifiedUserFactory(**kwargs)
    version = fx.give_photo(user)
    return (
        user,
        f"/api/v1/avatars/{user.pk}/{version}-96.webp",
        f"/api/v1/avatars/{user.pk}/{version}-256.webp",
    )


def auth(user):
    return {"HTTP_AUTHORIZATION": f"Bearer {access_token_for(user)}"}


def test_the_url_is_built_from_the_version_and_is_null_without_a_photo():
    user = VerifiedUserFactory(avatar_version="0123456789abcdef")
    assert avatar_url(user) == f"/api/v1/avatars/{user.pk}/0123456789abcdef-96.webp"
    assert avatar_url(user, 256) == f"/api/v1/avatars/{user.pk}/0123456789abcdef-256.webp"
    assert avatar_url(VerifiedUserFactory()) is None


# ---------- 256 px: /me and the profile ----------


def test_me_and_a_profile_use_the_256_image(api_client):
    user, _small, large = person(username="photo_person")
    me = api_client.get("/api/v1/me/", **auth(user))
    profile = api_client.get("/api/v1/users/photo_person/")

    assert me.json()["avatar_url"] == large
    assert profile.json()["avatar_url"] == large


def test_me_and_a_profile_are_null_without_a_photo(api_client):
    user = VerifiedUserFactory(username="plain_person")
    assert api_client.get("/api/v1/me/", **auth(user)).json()["avatar_url"] is None
    assert api_client.get("/api/v1/users/plain_person/").json()["avatar_url"] is None


# ---------- 96 px: every list ----------


def test_post_authors_in_the_feed_and_on_the_post_page_use_the_96_image(api_client):
    author, small, _large = person()
    post = PostFactory(author=author)

    feed = api_client.get("/api/v1/posts/").json()["results"]
    detail = api_client.get(f"/api/v1/posts/{post.pk}/").json()

    assert feed[0]["post"]["author"]["avatar_url"] == small
    assert detail["author"]["avatar_url"] == small


def test_comment_authors_use_the_96_image(api_client):
    commenter, small, _large = person()
    post = PostFactory()
    CommentFactory(post=post, author=commenter)

    rows = api_client.get(f"/api/v1/posts/{post.pk}/comments/").json()["results"]
    assert rows[0]["author"]["avatar_url"] == small


def test_followers_and_following_rows_use_the_96_image(api_client):
    star = VerifiedUserFactory(username="the_star")
    fan, fan_small, _ = person(username="the_fan")
    idol, idol_small, _ = person(username="the_idol")
    FollowFactory(follower=fan, following=star)
    FollowFactory(follower=star, following=idol)

    followers = api_client.get("/api/v1/users/the_star/followers/").json()["results"]
    following = api_client.get("/api/v1/users/the_star/following/").json()["results"]
    assert followers[0]["avatar_url"] == fan_small
    assert following[0]["avatar_url"] == idol_small


def test_the_reposter_in_the_following_feed_uses_the_96_image(api_client):
    me = VerifiedUserFactory()
    reposter, small, _large = person()
    FollowFactory(follower=me, following=reposter)
    RepostFactory(user=reposter, post=PostFactory())

    item = api_client.get("/api/v1/feed/", **auth(me)).json()["results"][0]
    assert item["kind"] == "repost" and item["reposted_by"]["avatar_url"] == small


def test_a_notifications_actor_uses_the_96_image(api_client):
    me = VerifiedUserFactory()
    actor, small, _large = person()
    NotificationFactory(recipient=me, actor=actor, type=NotificationType.LIKE)

    item = api_client.get("/api/v1/notifications/", **auth(me)).json()["results"][0]
    assert item["actor"]["avatar_url"] == small


def test_people_search_uses_the_96_image(api_client):
    _user, small, _large = person(username="searchable_ada")
    rows = api_client.get("/api/v1/search/", {"q": "searchable", "type": "users"}).json()["results"]
    assert rows[0]["avatar_url"] == small


def test_every_list_has_null_avatars_for_people_without_a_photo(api_client):
    me = VerifiedUserFactory()
    author = VerifiedUserFactory(username="no_photo")
    post = PostFactory(author=author)
    CommentFactory(post=post, author=author)
    FollowFactory(follower=me, following=author)
    NotificationFactory(recipient=me, actor=author, type=NotificationType.LIKE)

    feed = api_client.get("/api/v1/posts/").json()["results"]
    assert feed[0]["post"]["author"]["avatar_url"] is None
    comments = api_client.get(f"/api/v1/posts/{post.pk}/comments/").json()["results"]
    assert comments[0]["author"]["avatar_url"] is None
    followers = api_client.get("/api/v1/users/no_photo/followers/").json()["results"]
    assert followers[0]["avatar_url"] is None
    item = api_client.get("/api/v1/notifications/", **auth(me)).json()["results"][0]
    assert item["actor"]["avatar_url"] is None


# ---------- A photo costs no query ----------


def test_photos_add_no_query_to_the_feed_or_to_a_profile(api_client):
    def counted(url):
        with CaptureQueriesContext(connection) as queries:
            assert api_client.get(url).status_code == 200
        return len(queries)

    plain = VerifiedUserFactory(username="plain_one")
    PostFactory(author=plain)
    before = (counted("/api/v1/posts/"), counted("/api/v1/users/plain_one/"))

    photo_author, _small, _large = person(username="photo_one")
    PostFactory(author=photo_author)
    after = (counted("/api/v1/posts/"), counted("/api/v1/users/photo_one/"))

    assert before == after
