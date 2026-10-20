"""Pinned emergencies on the Recent feed and `GET /api/v1/posts/emergencies/` (ARCHITECTURE §4b,
§9; Part 11C). Expiry depends only on time: posts are placed in time, no job runs."""

from datetime import timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.posts.models import PostStatus
from apps.posts.tests.factories import PostFactory, VerifiedUserFactory
from apps.posts.tests.test_api_create import POST_KEYS

pytestmark = pytest.mark.django_db

URL = "/api/v1/posts/"
ALL = "/api/v1/posts/emergencies/"


def emergency(content, *, hours_old=1.0, **fields):
    made = timezone.now() - timedelta(hours=hours_old)
    return PostFactory(
        fact=True,
        content=content,
        is_emergency=True,
        created_at=made,
        emergency_expires_at=made + timedelta(hours=24),
        **fields,
    )


def plain(content, *, minutes_old=30):
    return PostFactory(content=content, created_at=timezone.now() - timedelta(minutes=minutes_old))


def pinned(body):
    return [post["content"] for post in body["pinned"]]


def results(body):
    return [item["post"]["content"] for item in body["results"]]


def walk(client):
    """Every page's contents, following `next_cursor`, and the first page's body."""
    pages, first, cursor = [], None, None
    while True:
        body = client.get(URL, {"cursor": cursor} if cursor else {}).json()
        first = first or body
        pages.append(results(body))
        cursor = body["next_cursor"]
        if not cursor:
            return pages, first


# ---------- Recent ----------


def test_an_active_emergency_is_pinned_and_left_out_of_the_results(api_client):
    plain("An ordinary post")
    emergency("Flood warning")
    body = api_client.get(URL).json()
    assert pinned(body) == ["Flood warning"]
    assert body["pinned_total"] == 1
    assert results(body) == ["An ordinary post"]
    [shown] = body["pinned"]
    assert set(shown) == POST_KEYS
    assert (shown["is_emergency"], shown["emergency_active"], shown["emergency_demoted"]) == (
        True,
        True,
        False,
    )


def test_at_most_three_newest_are_pinned_and_the_total_counts_them_all(api_client):
    for i in range(5):
        emergency(f"Warning {i}", hours_old=1 + i)  # 0 is the newest
    body = api_client.get(URL).json()
    assert pinned(body) == ["Warning 0", "Warning 1", "Warning 2"]
    assert body["pinned_total"] == 5
    # Every pinnable post is out of the results, the two not shown included.
    assert results(body) == []


def test_no_pinnable_post_is_on_any_page_and_nothing_is_repeated(api_client):
    for i in range(45):
        plain(f"Post {i}", minutes_old=i + 1)
    for i in range(4):
        emergency(f"Warning {i}", hours_old=0.01 * (i + 1))
    pages, first = walk(api_client)
    everything = [content for page in pages for content in page]
    assert len(everything) == len(set(everything)) == 45
    assert not any(content.startswith("Warning") for content in everything)
    assert len(first["pinned"]) == 3 and first["pinned_total"] == 4


def test_the_pinned_list_is_on_the_first_page_only(api_client):
    for i in range(25):
        plain(f"Post {i}", minutes_old=i + 1)
    emergency("Flood warning")
    first = api_client.get(URL).json()
    assert pinned(first) == ["Flood warning"]
    later = api_client.get(URL, {"cursor": first["next_cursor"]}).json()
    assert (later["pinned"], later["pinned_total"]) == ([], 0)
    # An empty cursor is the first page.
    assert pinned(api_client.get(URL, {"cursor": ""}).json()) == ["Flood warning"]


def test_pinned_at_23_hours_59_and_not_at_24_hours_01(api_client):
    emergency("Nearly over", hours_old=23 + 59 / 60)
    emergency("Just over", hours_old=24 + 1 / 60)
    body = api_client.get(URL).json()
    assert pinned(body) == ["Nearly over"]
    # The expired one is an ordinary post again, in the results, without the active flag.
    [item] = body["results"]
    assert item["post"]["content"] == "Just over"
    assert (item["post"]["emergency_active"], item["post"]["emergency_demoted"]) == (False, False)


@pytest.mark.parametrize(
    "fields",
    [
        {"emergency_demoted_at": timezone.now()},
        {"status": PostStatus.REMOVED},
        {"deleted_at": timezone.now()},
    ],
    ids=["demoted", "removed", "deleted"],
)
def test_a_demoted_removed_or_deleted_emergency_is_never_pinned(api_client, fields):
    emergency("Not pinned", **fields)
    body = api_client.get(URL).json()
    assert (body["pinned"], body["pinned_total"]) == ([], 0)


def test_a_demoted_emergency_says_so_in_the_list(api_client):
    emergency("Demoted", emergency_demoted_at=timezone.now())
    [item] = api_client.get(URL).json()["results"]
    assert (item["post"]["emergency_active"], item["post"]["emergency_demoted"]) == (False, True)


def test_the_pinned_posts_carry_the_viewers_flags(auth_client):
    from apps.social.tests.factories import LikeFactory

    reader = VerifiedUserFactory()
    post = emergency("Flood warning")
    LikeFactory(user=reader, post=post)
    [shown] = auth_client(reader).get(URL).json()["pinned"]
    assert (shown["like_count"], shown["liked_by_me"]) == (1, True)
    assert shown["is_mine"] is False


def test_a_profile_never_pins(api_client):
    author = VerifiedUserFactory(username="writer")
    emergency("Flood warning", author=author)
    body = api_client.get("/api/v1/users/writer/posts/").json()
    assert (body["pinned"], body["pinned_total"]) == ([], 0)
    assert results(body) == ["Flood warning"]  # inline, with its chip


# ---------- GET /api/v1/posts/emergencies/ ----------


def test_every_active_emergency_newest_first(api_client):
    for i in range(5):
        emergency(f"Warning {i}", hours_old=1 + i)
    emergency("Over", hours_old=25)
    plain("Ordinary")
    body = api_client.get(ALL).json()
    assert set(body) == {"results", "next_cursor"}
    assert [post["content"] for post in body["results"]] == [f"Warning {i}" for i in range(5)]
    assert all(set(post) == POST_KEYS for post in body["results"])
    assert body["next_cursor"] is None
    assert "no-store" in api_client.get(ALL)["Cache-Control"]


def test_the_list_pages_with_a_cursor(api_client):
    for i in range(23):
        emergency(f"Warning {i:02}", hours_old=0.5 + i / 60)
    first = api_client.get(ALL).json()
    assert len(first["results"]) == 20 and first["next_cursor"]
    rest = api_client.get(ALL, {"cursor": first["next_cursor"]}).json()
    seen = [p["content"] for p in first["results"]] + [p["content"] for p in rest["results"]]
    assert seen == [f"Warning {i:02}" for i in range(23)]
    assert api_client.get(ALL, {"page_size": 50}).json()["next_cursor"] is None


def test_a_crafted_cursor_is_a_404(api_client):
    import base64

    token = base64.urlsafe_b64encode(b"p=not-a-time").decode().rstrip("=")
    response = api_client.get(ALL, {"cursor": token})
    assert response.status_code == 404


def test_an_unknown_feed_is_a_400_on_the_field(api_client):
    response = api_client.get(ALL, {"feed": "everything"})
    assert response.status_code == 400
    assert response.json() == {"feed": ["Choose recent or following."]}


def test_the_following_scope_needs_a_login(api_client):
    response = api_client.get(ALL, {"feed": "following"})
    assert response.status_code == 401
    assert response.json()["code"] == "not_authenticated"


def test_the_following_scope_lists_the_people_you_follow_and_you(auth_client):
    from apps.social.tests.factories import FollowFactory

    me = VerifiedUserFactory()
    followed = VerifiedUserFactory()
    FollowFactory(follower=me, following=followed)
    emergency("Mine", author=me, hours_old=1)
    emergency("Theirs", author=followed, hours_old=2)
    emergency("A stranger's", hours_old=3)
    body = auth_client(me).get(ALL, {"feed": "following"}).json()
    assert [post["content"] for post in body["results"]] == ["Mine", "Theirs"]
    everyone = auth_client(me).get(ALL).json()
    assert len(everyone["results"]) == 3


def count(client, **params):
    with CaptureQueriesContext(connection) as captured:
        assert client.get(ALL, params).status_code == 200
    return len(captured)


def test_the_list_is_one_query_anonymous_and_two_signed_in(api_client, auth_client):
    from apps.social.tests.factories import FollowFactory

    me = VerifiedUserFactory()
    reader = auth_client(me)
    emergency("Warning")
    small = (count(api_client), count(reader), count(reader, feed="following"))
    for i in range(10):
        post = emergency(f"More {i}", hours_old=2 + i / 60)
        FollowFactory(follower=me, following=post.author)
    large = (count(api_client), count(reader), count(reader, feed="following"))
    assert small == large == (1, 2, 2)
