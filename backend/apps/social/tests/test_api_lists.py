"""`GET /api/v1/users/{username}/followers/` and `…/following/`."""

import base64
from datetime import timedelta
from urllib.parse import urlencode

import pytest
from django.utils import timezone

from apps.social.tests.factories import FollowFactory, VerifiedUserFactory

pytestmark = pytest.mark.django_db

ROW_KEYS = {
    "id",
    "username",
    "display_name",
    "bio",
    "avatar_url",
    "reputation",
    "is_following",
    "is_me",
}


def followers(name="ada"):
    return f"/api/v1/users/{name}/followers/"


def following(name="ada"):
    return f"/api/v1/users/{name}/following/"


def names(response):
    return [row["username"] for row in response.json()["results"]]


@pytest.fixture
def ada():
    return VerifiedUserFactory(username="ada")


def fans(ada, count, *, base=None):
    """`count` followers of ada; follower 0 followed most recently. Own timestamps."""
    base = base or timezone.now() - timedelta(minutes=5)
    return [
        FollowFactory(
            follower=VerifiedUserFactory(username=f"fan_{i:02d}"),
            following=ada,
            created_at=base - timedelta(seconds=i),
        ).follower
        for i in range(count)
    ]


def test_followers_are_users_newest_follow_first(api_client, ada):
    fans(ada, 3)
    response = api_client.get(followers())
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"results", "next_cursor"}
    assert names(response) == ["fan_00", "fan_01", "fan_02"]
    assert set(body["results"][0]) == ROW_KEYS
    assert body["next_cursor"] is None
    assert "no-store" in response["Cache-Control"]


def test_following_lists_who_the_user_follows(api_client, ada):
    base = timezone.now() - timedelta(minutes=5)
    for i in range(3):
        FollowFactory(
            follower=ada,
            following=VerifiedUserFactory(username=f"star_{i}"),
            created_at=base - timedelta(seconds=i),
        )
    FollowFactory(following=ada)  # a follower, not someone ada follows
    assert names(api_client.get(following())) == ["star_0", "star_1", "star_2"]


def test_the_two_lists_are_not_mixed_up(api_client, ada):
    bo = VerifiedUserFactory(username="bob")
    FollowFactory(follower=bo, following=ada)
    assert names(api_client.get(followers())) == ["bob"]
    assert names(api_client.get(following())) == []
    assert names(api_client.get(followers("bob"))) == []
    assert names(api_client.get(following("bob"))) == ["ada"]


def test_empty_lists(api_client, ada):
    assert api_client.get(followers()).json() == {"results": [], "next_cursor": None}
    assert api_client.get(following()).json() == {"results": [], "next_cursor": None}


def test_inactive_users_are_left_out(api_client, ada):
    fans(ada, 2)
    FollowFactory(follower=VerifiedUserFactory(username="gone", is_active=False), following=ada)
    assert names(api_client.get(followers())) == ["fan_00", "fan_01"]
    FollowFactory(follower=ada, following=VerifiedUserFactory(username="gone2", is_active=False))
    assert names(api_client.get(following())) == []


@pytest.mark.parametrize("name", ["nobody", "x" * 200, "a\x00b"])
def test_an_unknown_user_is_a_404(api_client, name):
    assert api_client.get(followers(name)).status_code == 404
    assert api_client.get(following(name)).status_code == 404


def test_an_inactive_owner_is_a_404(api_client):
    VerifiedUserFactory(username="gone", is_active=False)
    assert api_client.get(followers("gone")).status_code == 404


def test_the_lookup_is_case_insensitive(api_client, ada):
    fans(ada, 1)
    assert names(api_client.get(followers("ADA"))) == ["fan_00"]


def test_is_following_and_is_me_are_the_viewers(auth_client, ada):
    fan0, fan1, fan2 = fans(ada, 3)
    viewer = VerifiedUserFactory(username="viewer")
    FollowFactory(follower=viewer, following=fan1)
    FollowFactory(follower=viewer, following=ada)
    rows = {r["username"]: r for r in auth_client(viewer).get(followers()).json()["results"]}
    assert rows["fan_01"]["is_following"] is True
    assert rows["fan_00"]["is_following"] is False
    assert rows["viewer"]["is_me"] is True
    assert rows["viewer"]["is_following"] is False
    assert all(r["is_me"] is False for n, r in rows.items() if n != "viewer")


def test_is_following_works_on_the_following_list_too(auth_client, ada):
    star = VerifiedUserFactory(username="star")
    FollowFactory(follower=ada, following=star)
    viewer = VerifiedUserFactory()
    FollowFactory(follower=viewer, following=star)
    rows = auth_client(viewer).get(following()).json()["results"]
    assert [r["is_following"] for r in rows] == [True]
    other = auth_client(VerifiedUserFactory()).get(following()).json()["results"]
    assert [r["is_following"] for r in other] == [False]


def test_a_visitor_sees_false_flags(api_client, ada):
    fans(ada, 2)
    rows = api_client.get(followers()).json()["results"]
    assert all(r["is_following"] is False and r["is_me"] is False for r in rows)


def test_a_row_shows_only_public_things(api_client, ada):
    fan = VerifiedUserFactory(username="fanx", display_name="Fan X", bio="Hello")
    FollowFactory(follower=fan, following=ada)
    text = api_client.get(followers()).content.decode()
    assert fan.email not in text
    row = api_client.get(followers()).json()["results"][0]
    assert (row["display_name"], row["bio"], row["avatar_url"]) == ("Fan X", "Hello", None)
    assert row["reputation"] == {"score": None, "sample": 0}


def test_pages_have_no_repeat_and_no_gap_even_when_follows_arrive(api_client, ada):
    fans(ada, 7)
    first = api_client.get(followers(), {"page_size": 3}).json()
    assert len(first["results"]) == 3 and first["next_cursor"]
    # Someone follows meanwhile: newer than everything, so it must not shift the next page.
    FollowFactory(follower=VerifiedUserFactory(username="late"), following=ada)
    seen = [r["username"] for r in first["results"]]
    cursor = first["next_cursor"]
    while cursor:
        page = api_client.get(followers(), {"page_size": 3, "cursor": cursor}).json()
        seen += [r["username"] for r in page["results"]]
        cursor = page["next_cursor"]
    assert seen == [f"fan_{i:02d}" for i in range(7)]


def test_follows_with_the_same_timestamp_are_not_repeated_or_lost(api_client, ada):
    moment = timezone.now() - timedelta(minutes=1)
    for i in range(5):
        FollowFactory(
            follower=VerifiedUserFactory(username=f"tie_{i}"), following=ada, created_at=moment
        )
    seen, cursor = [], None
    while True:
        params = {"page_size": 2, **({"cursor": cursor} if cursor else {})}
        body = api_client.get(followers(), params).json()
        seen += [r["username"] for r in body["results"]]
        cursor = body["next_cursor"]
        if not cursor:
            break
    assert sorted(seen) == [f"tie_{i}" for i in range(5)]


def cursor_for(**tokens):
    return base64.urlsafe_b64encode(urlencode(tokens).encode()).decode().rstrip("=")


@pytest.mark.parametrize(
    "cursor",
    [
        cursor_for(p="not a date"),
        cursor_for(p="2026-01-01T00:00:00"),  # no time zone
        cursor_for(p="9999-99-99T00:00:00+00:00"),
        cursor_for(o="x"),
    ],
)
def test_a_crafted_cursor_is_a_404_never_a_500(api_client, ada, cursor):
    fans(ada, 3)
    assert api_client.get(followers(), {"cursor": cursor}).status_code == 404
    assert api_client.get(following(), {"cursor": cursor}).status_code == 404


def test_page_size_is_capped_at_50(api_client, ada):
    fans(ada, 3)
    assert len(api_client.get(followers(), {"page_size": 500}).json()["results"]) == 3


def queries(client, url):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    with CaptureQueriesContext(connection) as captured:
        assert client.get(url).status_code == 200
    return len(captured)


@pytest.mark.parametrize("make_url", [followers, following])
def test_the_query_count_is_constant(api_client, auth_client, ada, make_url):
    viewer = auth_client(VerifiedUserFactory())

    def add(n):
        for _ in range(n):
            other = VerifiedUserFactory()
            FollowFactory(follower=other, following=ada)
            FollowFactory(follower=ada, following=other)

    add(3)
    small = (queries(api_client, make_url()), queries(viewer, make_url()))
    add(17)
    large = (queries(api_client, make_url()), queries(viewer, make_url()))
    assert small == large == (2, 3)
