"""`GET /api/v1/feed/`: posts by the people you follow and by you, newest first (§9)."""

from datetime import timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.accounts.tests.factories import UserFactory
from apps.posts.tests.test_api_create import POST_KEYS
from apps.social.tests.factories import FollowFactory, PostFactory, VerifiedUserFactory

pytestmark = pytest.mark.django_db

URL = "/api/v1/feed/"


@pytest.fixture
def me():
    return VerifiedUserFactory(username="myself")


def contents(response):
    return [item["post"]["content"] for item in response.json()["results"]]


def post(author, content, ago, **kwargs):
    return PostFactory(
        author=author, content=content, created_at=timezone.now() - timedelta(minutes=ago), **kwargs
    )


def test_anonymous_is_401(api_client):
    assert api_client.get(URL).status_code == 401


def test_an_unverified_user_can_read_it(auth_client):
    assert auth_client(UserFactory()).get(URL).status_code == 200


def test_nothing_followed_and_no_posts_is_an_empty_feed(auth_client, me):
    assert auth_client(me).get(URL).json() == {
        "pinned": [],
        "pinned_total": 0,
        "results": [],
        "next_cursor": None,
    }


def test_the_envelope_and_the_items_are_the_feed_shape(auth_client, me):
    post(me, "mine", 1)
    response = auth_client(me).get(URL)
    body = response.json()
    assert set(body) == {"pinned", "pinned_total", "results", "next_cursor"}
    item = body["results"][0]
    assert set(item) == {"kind", "post", "reposted_by", "activity_at"}
    assert set(item["post"]) == POST_KEYS
    assert item["post"]["is_mine"] is True
    assert "no-store" in response["Cache-Control"]


def test_followed_plus_own_newest_first_and_nobody_else(auth_client, me):
    bo, cy, stranger = (VerifiedUserFactory() for _ in range(3))
    FollowFactory(follower=me, following=bo)
    FollowFactory(follower=me, following=cy)
    FollowFactory(follower=stranger, following=me)  # follows me; I don't follow them
    post(bo, "bo old", 50)
    post(me, "mine", 40)
    post(cy, "cy", 30)
    post(bo, "bo new", 10)
    post(stranger, "stranger", 5)
    assert contents(auth_client(me).get(URL)) == ["bo new", "cy", "mine", "bo old"]


def test_removed_and_deleted_posts_are_left_out(auth_client, me):
    bo = VerifiedUserFactory()
    FollowFactory(follower=me, following=bo)
    post(bo, "ok", 5)
    post(bo, "removed", 4, removed=True)
    post(bo, "deleted", 3, deleted=True)
    post(me, "my removed", 2, removed=True)
    post(me, "my deleted", 1, deleted=True)
    assert contents(auth_client(me).get(URL)) == ["ok"]


def test_removed_posts_do_not_shorten_a_full_page(auth_client, me):
    """The page of ids is filtered in the query, not only when the posts are loaded."""
    for i in range(25):
        post(me, f"p{i:02d}", i + 1, removed=i in (1, 5, 9))
    first = auth_client(me).get(URL).json()
    assert len(first["results"]) == 20
    assert first["next_cursor"]


def test_every_other_status_appears(auth_client, me):
    post(me, "pending", 4, fact=True)
    post(me, "true", 3, verified_pipeline=True)
    post(me, "review", 2, under_review=True)
    post(me, "opinion", 1)
    assert contents(auth_client(me).get(URL)) == ["opinion", "review", "true", "pending"]


def test_following_someone_with_no_posts_adds_nothing(auth_client, me):
    FollowFactory(follower=me, following=VerifiedUserFactory())
    assert contents(auth_client(me).get(URL)) == []


def test_following_an_inactive_user_still_hides_their_posts_from_nobody(auth_client, me):
    """Inactive accounts keep their follows; the feed filters posts, not authors."""
    bo = VerifiedUserFactory(is_active=False)
    FollowFactory(follower=me, following=bo)
    post(bo, "from an inactive account", 1)
    assert contents(auth_client(me).get(URL)) == ["from an inactive account"]


def test_paging_has_no_repeat_or_gap_when_posts_arrive(auth_client, me):
    bo = VerifiedUserFactory()
    FollowFactory(follower=me, following=bo)
    for i in range(7):
        post(bo if i % 2 else me, f"p{i}", i + 5)
    client = auth_client(me)
    first = client.get(URL, {"page_size": 3}).json()
    post(bo, "late", 0)
    seen = [i["post"]["content"] for i in first["results"]]
    cursor = first["next_cursor"]
    while cursor:
        page = client.get(URL, {"page_size": 3, "cursor": cursor}).json()
        seen += [i["post"]["content"] for i in page["results"]]
        cursor = page["next_cursor"]
    assert seen == [f"p{i}" for i in range(7)]


def test_a_crafted_cursor_is_a_404(auth_client, me):
    assert auth_client(me).get(URL, {"cursor": "cD1ub3QtYS1kYXRl"}).status_code == 404


def test_page_size_is_honoured_and_capped(auth_client, me):
    for i in range(5):
        post(me, f"p{i}", i + 1)
    client = auth_client(me)
    assert len(client.get(URL, {"page_size": 2}).json()["results"]) == 2
    assert len(client.get(URL, {"page_size": 500}).json()["results"]) == 5


def queries(client):
    with CaptureQueriesContext(connection) as captured:
        assert client.get(URL).status_code == 200
    return len(captured)


def test_the_query_count_is_constant_with_the_cache_off(auth_client, me, settings):
    settings.FEED_CACHE_SECONDS = 0
    client = auth_client(me)
    bo = VerifiedUserFactory()
    FollowFactory(follower=me, following=bo)
    for i in range(3):
        post(bo, f"p{i}", i + 1, verified_pipeline=True)
    small = queries(client)
    for i in range(17):
        post(bo, f"q{i}", i + 10, verified_pipeline=True)
    for _ in range(5):
        FollowFactory(follower=me, following=VerifiedUserFactory())
    large = queries(client)
    # The signed-in user, the page of ids, the posts, and the pinned emergencies (Part 11C).
    assert small == large == 4
