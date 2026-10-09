"""The Following feed's cache (user decision 2026-10-09): only the ids of page 1 are kept, the
posts are read fresh, and your own changes show at once."""

from datetime import timedelta

import pytest
from django.core.cache import cache
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.accounts.tests.conftest import clock  # noqa: F401  (fixture)
from apps.posts.models import Post
from apps.social import feed, services
from apps.social.tests.factories import FollowFactory, PostFactory, VerifiedUserFactory

pytestmark = pytest.mark.django_db

URL = "/api/v1/feed/"


@pytest.fixture
def me():
    return VerifiedUserFactory(username="myself")


@pytest.fixture
def bo(me):
    star = VerifiedUserFactory(username="bob")
    FollowFactory(follower=me, following=star)
    return star


def post(author, content, ago=1, **kwargs):
    return PostFactory(
        author=author, content=content, created_at=timezone.now() - timedelta(minutes=ago), **kwargs
    )


def contents(response):
    return [item["post"]["content"] for item in response.json()["results"]]


def say(client, text="mine"):
    """Post an opinion through the API (the path that must bust your own cache)."""
    body = {"content": text, "post_type": "opinion"}
    response = client.post("/api/v1/posts/", body, format="json")
    assert response.status_code == 201
    return response


def count_queries(client, params=None):
    with CaptureQueriesContext(connection) as captured:
        assert client.get(URL, params or {}).status_code == 200
    return len(captured)


def test_the_first_request_fills_the_cache_and_the_second_reads_it(auth_client, me, bo):
    post(bo, "hello")
    client = auth_client(me)
    assert cache.get(feed.cache_key(me.pk)) is None
    assert count_queries(client) == 3  # the user, the page of ids, the posts
    assert cache.get(feed.cache_key(me.pk)) is not None
    assert count_queries(client) == 2  # the user, the posts: no query for the ids
    assert contents(client.get(URL)) == ["hello"]


def test_the_cache_holds_only_ids_and_the_next_cursor(auth_client, me, bo):
    for i in range(3):
        post(bo, f"secret text {i}", i + 1)
    auth_client(me).get(URL, {})
    stored = cache.get(feed.cache_key(me.pk))
    assert set(stored) == {"ids", "next"}
    assert stored["next"] is None
    assert [str(p.pk) for p in Post.objects.order_by("-created_at")] == stored["ids"]
    assert "secret text" not in repr(stored)


def test_the_ttl_is_feed_cache_seconds(auth_client, me, bo, clock):  # noqa: F811
    post(bo, "hello")
    client = auth_client(me)
    client.get(URL)
    clock["seconds"] = 29
    assert cache.get(feed.cache_key(me.pk)) is not None
    clock["seconds"] = 31
    assert cache.get(feed.cache_key(me.pk)) is None


def test_a_followed_users_new_post_shows_after_the_ttl_not_before(auth_client, me, bo, clock):  # noqa: F811
    post(bo, "old", 10)
    client = auth_client(me)
    assert contents(client.get(URL)) == ["old"]
    post(bo, "new", 0)
    assert contents(client.get(URL)) == ["old"]  # accepted: at most FEED_CACHE_SECONDS late
    clock["seconds"] = 31
    assert contents(client.get(URL)) == ["new", "old"]


def test_your_own_new_post_shows_at_once(auth_client, me, bo):
    client = auth_client(me)
    post(bo, "theirs", 5)
    assert contents(client.get(URL)) == ["theirs"]
    response = client.post(
        "/api/v1/posts/", {"content": "mine", "post_type": "opinion"}, format="json"
    )
    assert response.status_code == 201
    assert contents(client.get(URL)) == ["mine", "theirs"]


def test_following_someone_shows_their_posts_at_once(auth_client, me):
    star = VerifiedUserFactory(username="star")
    post(star, "from the star")
    client = auth_client(me)
    assert contents(client.get(URL)) == []
    assert client.post("/api/v1/users/star/follow/").status_code == 201
    assert contents(client.get(URL)) == ["from the star"]


def test_unfollowing_hides_their_posts_at_once(auth_client, me, bo):
    post(bo, "theirs")
    client = auth_client(me)
    assert contents(client.get(URL)) == ["theirs"]
    assert client.delete("/api/v1/users/bob/follow/").status_code == 204
    assert contents(client.get(URL)) == []


def test_a_follow_through_the_service_busts_too(auth_client, me):
    star = VerifiedUserFactory()
    post(star, "x")
    client = auth_client(me)
    client.get(URL)
    services.follow(follower=me, target=star)
    assert contents(client.get(URL)) == ["x"]


def test_another_users_cache_is_untouched(auth_client, me, bo):
    other = VerifiedUserFactory()
    FollowFactory(follower=other, following=bo)
    post(bo, "hi")
    auth_client(other).get(URL)
    key = feed.cache_key(other.pk)
    assert cache.get(key) is not None
    auth_client(me).post(
        "/api/v1/posts/", {"content": "mine", "post_type": "opinion"}, format="json"
    )
    assert cache.get(key) is not None


def test_each_user_has_their_own_page(auth_client, me, bo):
    other = VerifiedUserFactory()
    post(bo, "for me")
    post(other, "for other")
    assert contents(auth_client(me).get(URL)) == ["for me"]
    assert contents(auth_client(other).get(URL)) == ["for other"]
    assert contents(auth_client(me).get(URL)) == ["for me"]


def test_a_deleted_post_disappears_without_waiting_for_the_ttl(auth_client, me, bo):
    keep, gone = post(bo, "keep", 2), post(bo, "gone", 1)
    client = auth_client(me)
    assert contents(client.get(URL)) == ["gone", "keep"]
    auth_client(bo).delete(f"/api/v1/posts/{gone.pk}/")
    assert cache.get(feed.cache_key(me.pk)) is not None  # the cache was not touched
    assert contents(client.get(URL)) == ["keep"]
    assert keep.pk


def test_a_removed_post_loses_its_text_at_once(auth_client, me, bo):
    target = post(bo, "harmful text")
    client = auth_client(me)
    client.get(URL)
    Post.objects.filter(pk=target.pk).update(status="removed")
    assert contents(client.get(URL)) == []


def test_a_status_change_shows_at_once(auth_client, me, bo):
    target = post(bo, "a claim", fact=True)
    client = auth_client(me)
    assert client.get(URL).json()["results"][0]["post"]["status"] == "pending"
    Post.objects.filter(pk=target.pk).update(
        status="verified_true", verdict_source="pipeline", confidence_score=90
    )
    item = client.get(URL).json()["results"][0]["post"]
    assert (item["status"], item["confidence_score"]) == ("verified_true", "90.00")


def test_a_post_that_became_invisible_leaves_a_shorter_page_not_an_error(auth_client, me, bo):
    posts = [post(bo, f"p{i}", i + 1) for i in range(3)]
    client = auth_client(me)
    client.get(URL)
    Post.objects.filter(pk=posts[1].pk).update(deleted_at=timezone.now())
    assert contents(client.get(URL)) == ["p0", "p2"]


def test_the_cached_next_cursor_leads_to_page_two(auth_client, me, bo):
    for i in range(25):
        post(bo, f"p{i:02d}", i + 1)
    client = auth_client(me)
    first = client.get(URL).json()
    assert len(first["results"]) == 20 and first["next_cursor"]
    again = client.get(URL).json()
    assert again["next_cursor"] == first["next_cursor"]
    second = client.get(URL, {"cursor": first["next_cursor"]}).json()
    assert [i["post"]["content"] for i in second["results"]] == [f"p{i:02d}" for i in range(20, 25)]


def test_a_cursor_or_page_size_skips_the_cache(auth_client, me, bo):
    for i in range(5):
        post(bo, f"p{i}", i + 1)
    client = auth_client(me)
    client.get(URL, {"page_size": 2})
    assert cache.get(feed.cache_key(me.pk)) is None
    first = client.get(URL, {"page_size": 2}).json()
    client.get(URL, {"cursor": first["next_cursor"]})
    assert cache.get(feed.cache_key(me.pk)) is None
    client.get(URL, {"cursor": ""})
    assert cache.get(feed.cache_key(me.pk)) is None


def test_zero_turns_the_cache_off(auth_client, me, bo, settings):
    settings.FEED_CACHE_SECONDS = 0
    post(bo, "hi")
    client = auth_client(me)
    client.get(URL)
    assert cache.get(feed.cache_key(me.pk)) is None
    post(bo, "again", 0)
    assert contents(client.get(URL)) == ["again", "hi"]


@pytest.mark.parametrize(
    "junk",
    [
        "text",
        {"ids": "x", "next": None},
        {"ids": ["not-a-uuid"], "next": None},
        {"ids": [1], "next": None},
        {"ids": [], "next": 5},
        {"next": None},
    ],
)
def test_a_malformed_cache_value_is_treated_as_a_miss(auth_client, me, bo, junk):
    post(bo, "hi")
    cache.set(feed.cache_key(me.pk), junk, 60)
    assert contents(auth_client(me).get(URL)) == ["hi"]


def test_a_cached_id_in_the_wrong_case_is_a_miss_not_a_match(me, bo):
    entry = {"ids": ["ABCDEF12-0000-4000-8000-000000000000"], "next": None}
    assert feed._is_entry(entry) is False


def test_bust_forgets_now_and_after_commit(me, django_capture_on_commit_callbacks):
    key = feed.cache_key(me.pk)
    cache.set(key, {"ids": [], "next": None}, 60)
    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        feed.bust_following_feed(me.pk)
    assert cache.get(key) is None  # forgotten immediately
    cache.set(key, {"ids": [], "next": None}, 60)  # a reader refills it mid-transaction
    for callback in callbacks:
        callback()
    assert cache.get(key) is None  # and again at commit
