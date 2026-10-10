"""The Following feed with reposts (Part 7B): mixed items, "no longer available" stubs, the
once-per-page rule, the key cache, and the query counts."""

from datetime import timedelta

import pytest
from django.core.cache import cache
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.accounts.tests.conftest import clock  # noqa: F401  (fixture)
from apps.accounts.tests.factories import UserFactory
from apps.posts.models import Post, PostStatus
from apps.social import feed
from apps.social.tests.factories import (
    FollowFactory,
    PostFactory,
    RepostFactory,
    VerifiedUserFactory,
)

pytestmark = pytest.mark.django_db

URL = "/api/v1/feed/"


@pytest.fixture
def me():
    return VerifiedUserFactory(username="myself")


@pytest.fixture
def bo(me):
    star = VerifiedUserFactory(username="bob", display_name="Bob")
    FollowFactory(follower=me, following=star)
    return star


def ago(minutes):
    return timezone.now() - timedelta(minutes=minutes)


def post(author, content, minutes, **kwargs):
    return PostFactory(author=author, content=content, created_at=ago(minutes), **kwargs)


def repost(user, original, minutes):
    return RepostFactory(user=user, post=original, created_at=ago(minutes))


def shape_body(body):
    """`kind:content-or-gone[:reposter]` per item of a page, in order."""
    out = []
    for item in body["results"]:
        text = "gone" if item["post"].get("unavailable") else item["post"]["content"]
        who = f":{item['reposted_by']['username']}" if item["reposted_by"] else ""
        out.append(f"{item['kind']}:{text}{who}")
    return out


def shape(response):
    return shape_body(response.json())


# ---------- what a feed shows ----------


def test_a_repost_by_someone_you_follow_is_an_item_with_the_reposter_and_the_repost_time(
    auth_client, me, bo
):
    original = post(VerifiedUserFactory(), "from a stranger", 60)
    made = repost(bo, original, 5)
    item = auth_client(me).get(URL).json()["results"][0]
    assert set(item) == {"kind", "post", "reposted_by", "activity_at"}
    assert item["kind"] == "repost"
    assert item["post"]["content"] == "from a stranger"
    assert item["post"]["id"] == str(original.pk)
    assert item["reposted_by"] == {
        "id": str(bo.pk),
        "username": "bob",
        "display_name": "Bob",
        "avatar_url": None,
    }
    assert item["activity_at"].startswith(made.created_at.strftime("%Y-%m-%dT%H:%M"))
    assert item["activity_at"] != item["post"]["created_at"]


def test_posts_and_reposts_are_mixed_by_activity_time(auth_client, me, bo):
    old = post(VerifiedUserFactory(), "old original", 100)
    post(bo, "bobs post", 50)
    repost(bo, old, 10)
    post(me, "mine", 5)
    # the stranger's own post is not in the feed (not followed): three items
    assert shape(auth_client(me).get(URL)) == [
        "post:mine",
        "repost:old original:bob",
        "post:bobs post",
    ]


def test_your_own_reposts_and_reposts_of_your_posts_show(auth_client, me, bo):
    repost(me, post(VerifiedUserFactory(), "i liked this", 30), 20)
    repost(bo, post(me, "my own", 40), 10)
    # bob's repost of my post (10 min) is newer than the post (40 min), so it hides the post
    assert shape(auth_client(me).get(URL)) == ["repost:my own:bob", "repost:i liked this:myself"]


def test_a_repost_by_someone_you_do_not_follow_is_not_shown(auth_client, me, bo):
    repost(VerifiedUserFactory(), post(bo, "bobs", 30), 5)
    assert shape(auth_client(me).get(URL)) == ["post:bobs"]


def test_the_original_shows_its_live_label_and_counts(auth_client, me, bo):
    original = post(VerifiedUserFactory(), "a claim", 60, fact=True)
    repost(bo, original, 5)
    client = auth_client(me)
    assert client.get(URL).json()["results"][0]["post"]["status"] == "pending"
    Post.objects.filter(pk=original.pk).update(
        status="verified_true", verdict_source="pipeline", confidence_score=90
    )
    item = client.get(URL).json()["results"][0]["post"]
    assert (item["status"], item["confidence_score"]) == ("verified_true", "90.00")
    assert item["repost_count"] == 1


def test_the_viewers_flags_are_filled_on_a_repost_item(auth_client, me, bo):
    original = post(VerifiedUserFactory(), "x", 60)
    repost(bo, original, 5)
    repost(me, original, 4)
    body = auth_client(me).get(URL).json()["results"][0]["post"]
    assert (body["repost_count"], body["reposted_by_me"]) == (2, True)


def test_an_unverified_user_can_read_a_feed_with_reposts(auth_client, bo):
    reader = UserFactory()
    FollowFactory(follower=reader, following=bo)
    repost(bo, post(VerifiedUserFactory(), "x", 60), 5)
    assert shape(auth_client(reader).get(URL)) == ["repost:x:bob"]


# ---------- "no longer available" ----------


@pytest.mark.parametrize("trait", ["deleted", "removed"])
def test_a_repost_of_a_deleted_or_removed_original_is_a_stub(auth_client, me, bo, trait):
    original = post(VerifiedUserFactory(), "secret words", 60, **{trait: True})
    made = repost(bo, original, 5)
    response = auth_client(me).get(URL)
    (item,) = response.json()["results"]
    assert item["kind"] == "repost"
    assert item["post"] == {"id": str(original.pk), "unavailable": True}
    assert item["reposted_by"]["username"] == "bob"
    assert item["activity_at"].startswith(made.created_at.strftime("%Y-%m-%dT%H:%M"))
    assert "secret words" not in response.content.decode()


def test_an_original_that_vanishes_after_the_page_was_cached_becomes_a_stub_at_once(
    auth_client, me, bo
):
    original = post(VerifiedUserFactory(), "x", 60)
    repost(bo, original, 5)
    client = auth_client(me)
    assert shape(client.get(URL)) == ["repost:x:bob"]
    assert cache.get(feed.cache_key(me.pk)) is not None
    Post.objects.filter(pk=original.pk).update(status=PostStatus.REMOVED)
    assert shape(client.get(URL)) == ["repost:gone:bob"]
    Post.objects.filter(pk=original.pk).update(status=PostStatus.PUBLISHED, deleted_at=ago(1))
    assert shape(client.get(URL)) == ["repost:gone:bob"]


def test_two_stubs_of_one_post_on_a_page_are_one_item(auth_client, me, bo):
    carol = VerifiedUserFactory(username="carol")
    FollowFactory(follower=me, following=carol)
    original = post(VerifiedUserFactory(), "x", 90, deleted=True)
    repost(bo, original, 20)
    repost(carol, original, 10)
    assert shape(auth_client(me).get(URL)) == ["repost:gone:carol"]


# ---------- once per page ----------


def test_a_post_and_its_repost_on_one_page_show_once_the_most_recent_activity_wins(
    auth_client, me, bo
):
    original = post(bo, "bobs", 60)
    repost(me, original, 5)
    assert shape(auth_client(me).get(URL)) == ["repost:bobs:myself"]


def test_the_original_wins_when_it_is_the_more_recent_activity(auth_client, me, bo):
    """The rule is "the first row of a post on the page", i.e. the most recent activity: a repost
    that is older than its post (clock skew) loses to it."""
    carol = VerifiedUserFactory(username="carol")
    FollowFactory(follower=me, following=carol)
    original = post(bo, "bobs", 5)
    repost(carol, original, 60)
    assert shape(auth_client(me).get(URL)) == ["post:bobs"]


def test_one_post_reposted_by_two_followed_people_shows_once_with_the_latest_reposter(
    auth_client, me, bo
):
    carol = VerifiedUserFactory(username="carol")
    FollowFactory(follower=me, following=carol)
    original = post(VerifiedUserFactory(), "x", 90)
    repost(bo, original, 30)
    repost(carol, original, 10)
    assert shape(auth_client(me).get(URL)) == ["repost:x:carol"]


def test_the_same_post_can_come_back_on_a_later_page_as_a_different_item(auth_client, me, bo):
    """The API only promises once per *page*; the client hides the repeat."""
    original = post(bo, "x", 100)
    repost(me, original, 1)  # the newest activity
    post(bo, "y", 90)
    post(bo, "z", 80)
    client = auth_client(me)
    seen, cursor = [], None
    for _ in range(10):
        body = client.get(URL, {"page_size": 1, **({"cursor": cursor} if cursor else {})}).json()
        seen += shape_body(body)
        cursor = body["next_cursor"]
        if cursor is None:
            break
    assert seen == ["repost:x:myself", "post:z", "post:y", "post:x"]


# ---------- the cursor ----------


def test_the_cursor_walk_has_no_repeat_or_gap_when_posts_and_reposts_arrive(auth_client, me, bo):
    stranger = VerifiedUserFactory()
    originals = [post(stranger, f"s{i}", 200 + i) for i in range(4)]
    for i in range(7):
        post(bo, f"b{i}", 10 + i)
    for i, original in enumerate(originals):
        repost(bo, original, 50 + i)
    client = auth_client(me)
    first = client.get(URL, {"page_size": 3}).json()
    post(bo, "late", 0)
    repost(bo, post(stranger, "late original", 300), 0)
    seen = shape_body(first)
    cursor = first["next_cursor"]
    while cursor:
        page = client.get(URL, {"page_size": 3, "cursor": cursor}).json()
        seen += shape_body(page)
        cursor = page["next_cursor"]
    assert seen == [f"post:b{i}" for i in range(7)] + [f"repost:s{i}:bob" for i in range(4)]


@pytest.mark.parametrize(
    "cursor",
    [
        "cD1ub3QtYS1kYXRl",  # a DRF-style crafted cursor
        "cD0yMDI2LTEwLTEwVDEyOjAwOjAwKzAwOjAw",  # a DRF cursor with a real time (the v1 format)
        "!!!",
        "x" * 300,
    ],
)
def test_a_cursor_that_is_not_ours_is_a_404(auth_client, me, cursor):
    response = auth_client(me).get(URL, {"cursor": cursor})
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_an_empty_cursor_is_the_first_page_and_skips_the_cache(auth_client, me, bo):
    post(bo, "hi", 5)
    assert shape(auth_client(me).get(URL, {"cursor": ""})) == ["post:hi"]
    assert cache.get(feed.cache_key(me.pk)) is None


def test_the_page_size_follows_the_feed_rules(auth_client, me, bo):
    for i in range(3):
        post(bo, f"p{i}", i + 1)
    client = auth_client(me)
    assert len(client.get(URL, {"page_size": 2}).json()["results"]) == 2
    assert len(client.get(URL, {"page_size": "junk"}).json()["results"]) == 3
    assert len(client.get(URL, {"page_size": 0}).json()["results"]) == 3
    assert len(client.get(URL, {"page_size": 999}).json()["results"]) == 3


# ---------- the cache ----------


def test_cached_page_one_plus_a_live_page_two_equals_the_uncached_walk(
    auth_client, me, bo, settings
):
    stranger = VerifiedUserFactory()
    for i in range(30):
        post(bo, f"p{i:02d}", 10 + i)
    for i in range(5):
        repost(bo, post(stranger, f"s{i}", 500 + i), 1 + i)
    client = auth_client(me)

    def walk():
        pages, cursor = [], None
        while True:
            body = client.get(URL, {"cursor": cursor} if cursor else {}).json()
            pages.append(shape_body(body))
            cursor = body["next_cursor"]
            if cursor is None:
                return pages

    cached = walk()
    assert cache.get(feed.cache_key(me.pk)) is not None
    assert walk() == cached  # the second walk's first page is a cache hit
    settings.FEED_CACHE_SECONDS = 0
    assert walk() == cached


def test_the_cached_next_cursor_still_works_after_new_items_arrive(auth_client, me, bo):
    for i in range(25):
        post(bo, f"p{i:02d}", 100 + i)
    client = auth_client(me)
    first = client.get(URL).json()
    post(bo, "late", 0)
    repost(bo, post(VerifiedUserFactory(), "late original", 400), 0)
    again = client.get(URL).json()
    assert again["next_cursor"] == first["next_cursor"]  # the cached page didn't see them
    second = client.get(URL, {"cursor": first["next_cursor"]}).json()
    assert shape_body(second) == [f"post:p{i:02d}" for i in range(20, 25)]


def test_an_undone_repost_drops_out_of_a_cached_page_at_once(auth_client, me, bo):
    original = post(VerifiedUserFactory(), "x", 60)
    made = repost(bo, original, 5)
    post(bo, "keep", 30)
    client = auth_client(me)
    assert shape(client.get(URL)) == ["repost:x:bob", "post:keep"]
    made.delete()
    assert cache.get(feed.cache_key(me.pk)) is not None
    assert shape(client.get(URL)) == ["post:keep"]


def test_an_undone_and_redone_repost_does_not_show_at_its_old_position(auth_client, me, bo):
    original = post(VerifiedUserFactory(), "x", 60)
    made = repost(bo, original, 20)
    post(bo, "keep", 5)
    client = auth_client(me)
    assert shape(client.get(URL)) == ["post:keep", "repost:x:bob"]
    made.delete()
    repost(bo, original, 1)  # redone: it now belongs at the top, not where the cache has it
    assert shape(client.get(URL)) == ["post:keep"]  # cached page: the stale key is dropped
    cache.delete(feed.cache_key(me.pk))
    assert shape(client.get(URL)) == ["repost:x:bob", "post:keep"]


def test_when_the_winning_repost_is_undone_a_followers_cached_page_loses_the_post_until_the_ttl(
    auth_client,
    me,
    bo,
    clock,  # noqa: F811
):
    """The accepted limit (ARCHITECTURE §9): the original item was hidden by the repost on that
    page, and the repost is gone, so the cached page has no item for the post until it expires."""
    original = post(bo, "bobs", 60)
    made = repost(me, original, 5)
    carol = VerifiedUserFactory(username="carol")
    FollowFactory(follower=carol, following=bo)
    FollowFactory(follower=carol, following=me)
    as_carol = auth_client(carol)  # the token is minted before the clock moves
    assert shape(as_carol.get(URL)) == ["repost:bobs:myself"]
    made.delete()  # a service call would bust *my* cache, not carol's: do it at the table
    assert shape(as_carol.get(URL)) == []  # stale cached key, no item for the post
    clock["seconds"] = 31
    assert shape(as_carol.get(URL)) == ["post:bobs"]


def test_reposting_and_unreposting_through_the_api_bust_the_reposters_cache_only(
    auth_client, me, bo
):
    original = post(VerifiedUserFactory(), "x", 60)
    other = VerifiedUserFactory()
    FollowFactory(follower=other, following=bo)
    post(bo, "hello", 5)
    client = auth_client(me)
    key_me, key_other = feed.cache_key(me.pk), feed.cache_key(other.pk)

    def fill():
        client.get(URL)
        auth_client(other).get(URL)
        assert cache.get(key_me) is not None and cache.get(key_other) is not None

    fill()
    assert client.post(f"/api/v1/posts/{original.pk}/repost/").status_code == 201
    assert cache.get(key_me) is None
    assert cache.get(key_other) is not None  # someone else's cache is not touched
    fill()
    assert client.delete(f"/api/v1/posts/{original.pk}/repost/").status_code == 204
    assert cache.get(key_me) is None
    assert cache.get(key_other) is not None


def test_your_own_repost_shows_at_once(auth_client, me, bo):
    original = post(VerifiedUserFactory(), "x", 60)
    client = auth_client(me)
    post(bo, "hello", 5)
    assert shape(client.get(URL)) == ["post:hello"]
    assert client.post(f"/api/v1/posts/{original.pk}/repost/").status_code == 201
    assert shape(client.get(URL)) == ["repost:x:myself", "post:hello"]
    assert client.delete(f"/api/v1/posts/{original.pk}/repost/").status_code == 204
    assert shape(client.get(URL)) == ["post:hello"]


# ---------- queries ----------


def queries(client):
    with CaptureQueriesContext(connection) as captured:
        assert client.get(URL).status_code == 200
    return len(captured)


def test_the_query_count_with_reposts_is_four_on_a_miss_and_three_on_a_hit(auth_client, me, bo):
    stranger = VerifiedUserFactory()
    client = auth_client(me)

    def counts():
        cache.delete(feed.cache_key(me.pk))
        miss = queries(client)
        return miss, queries(client)

    for i in range(3):
        repost(bo, post(stranger, f"s{i}", 300 + i), 10 + i)
        post(bo, f"b{i}", 20 + i)
    small = counts()
    for i in range(3, 9):
        repost(bo, post(stranger, f"s{i}", 300 + i), 10 + i)
        post(bo, f"b{i}", 20 + i)
    assert small == counts() == (4, 3)  # the user, the keys (a union), the posts, the reposts


def test_the_query_count_without_reposts_is_three_and_two(auth_client, me, bo):
    client = auth_client(me)

    def counts():
        cache.delete(feed.cache_key(me.pk))
        miss = queries(client)
        return miss, queries(client)

    for i in range(3):
        post(bo, f"b{i}", 20 + i)
    small = counts()
    for i in range(3, 20):
        post(bo, f"b{i}", 20 + i)
    assert small == counts() == (3, 2)  # no reposts on the page: no query for them


def test_a_cursor_page_costs_the_same_as_a_miss(auth_client, me, bo):
    stranger = VerifiedUserFactory()
    for i in range(30):
        repost(bo, post(stranger, f"s{i}", 300 + i), 10 + i)
    client = auth_client(me)
    first = client.get(URL).json()
    with CaptureQueriesContext(connection) as captured:
        assert client.get(URL, {"cursor": first["next_cursor"]}).status_code == 200
    assert len(captured) == 4
