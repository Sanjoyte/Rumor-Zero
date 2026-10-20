import base64
from datetime import timedelta
from urllib.parse import urlencode

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.posts.models import Post
from apps.posts.tests.factories import PostFactory, UserFactory, VerifiedUserFactory

pytestmark = pytest.mark.django_db

URL = "/api/v1/posts/"


def make_posts(count, *, base=None, **kwargs):
    """Newest first by index: post 0 is the newest. Every post has its own timestamp."""
    base = base or timezone.now() - timedelta(minutes=5)
    return [
        PostFactory(content=f"Post {i}", created_at=base - timedelta(seconds=i), **kwargs)
        for i in range(count)
    ]


def cursor_for(**tokens):
    query = urlencode(tokens)
    return base64.urlsafe_b64encode(query.encode()).decode().rstrip("=")


def contents(response):
    return [item["post"]["content"] for item in response.json()["results"]]


def walk(client, url=URL, **params):
    """Follow `next_cursor` to the end; return every page's contents."""
    pages = []
    cursor = None
    while True:
        query = {**params, **({"cursor": cursor} if cursor else {})}
        body = client.get(url, query).json()
        pages.append([item["post"]["content"] for item in body["results"]])
        cursor = body["next_cursor"]
        if not cursor:
            return pages


# ---------- shape ----------


def test_an_empty_feed(api_client):
    response = api_client.get(URL)
    assert response.status_code == 200
    assert response.json() == {"pinned": [], "pinned_total": 0, "results": [], "next_cursor": None}


def test_the_envelope_and_item_shape(api_client):
    post = PostFactory()
    body = api_client.get(URL).json()
    assert set(body) == {"pinned", "pinned_total", "results", "next_cursor"}
    assert body["pinned"] == [] and body["pinned_total"] == 0
    (item,) = body["results"]
    assert set(item) == {"kind", "post", "reposted_by", "activity_at"}
    assert item["kind"] == "post"
    assert item["reposted_by"] is None
    assert item["post"]["id"] == str(post.pk)
    assert item["activity_at"] == item["post"]["created_at"]


def test_the_feed_is_public_and_never_cached(api_client):
    response = api_client.get(URL)
    assert response.status_code == 200
    assert "no-store" in response["Cache-Control"]


def test_an_unverified_user_can_read_the_feed(auth_client):
    assert auth_client(UserFactory()).get(URL).status_code == 200


# ---------- what is listed, and in what order ----------


def test_newest_first(api_client):
    make_posts(5)
    assert contents(api_client.get(URL)) == [f"Post {i}" for i in range(5)]


def test_ties_are_broken_by_id_newest_first(api_client):
    moment = timezone.now() - timedelta(minutes=1)
    posts = [PostFactory(created_at=moment) for _ in range(4)]
    ids = [item["post"]["id"] for item in api_client.get(URL).json()["results"]]
    assert ids == [str(p.pk) for p in sorted(posts, key=lambda p: p.pk, reverse=True)]


def test_every_status_is_listed_except_removed_and_deleted(api_client):
    pending = PostFactory(content="pending", fact=True)
    review = PostFactory(content="review", under_review=True)
    verified = PostFactory(content="verified", verified_pipeline=True)
    opinion = PostFactory(content="opinion")
    PostFactory(content="removed", removed=True)
    PostFactory(content="deleted", deleted=True)
    PostFactory(content="removed fact", fact=True, removed=True)
    listed = {item["post"]["id"] for item in api_client.get(URL).json()["results"]}
    assert listed == {str(p.pk) for p in (pending, review, verified, opinion)}


def test_a_deleted_and_removed_post_is_still_in_the_database(api_client):
    PostFactory(deleted=True)
    PostFactory(removed=True)
    assert Post.objects.count() == 2
    assert api_client.get(URL).json()["results"] == []


def test_sources_are_listed_with_their_kind(api_client):
    PostFactory(fact=True, sources=["10.1000/xyz", "https://example.org/a"])
    PostFactory(content="An opinion")
    by_content = {i["post"]["content"]: i["post"] for i in api_client.get(URL).json()["results"]}
    fact = next(p for c, p in by_content.items() if p["post_type"] == "fact")
    assert fact["sources"] == [
        {"value": "10.1000/xyz", "kind": "doi"},
        {"value": "https://example.org/a", "kind": "url"},
    ]
    assert by_content["An opinion"]["sources"] == []


def test_is_mine_depends_on_the_viewer(api_client, auth_client):
    author = VerifiedUserFactory()
    PostFactory(author=author)
    PostFactory()
    mine = {i["post"]["is_mine"] for i in auth_client(author).get(URL).json()["results"]}
    assert mine == {True, False}
    assert {i["post"]["is_mine"] for i in api_client.get(URL).json()["results"]} == {False}


def test_confidence_is_only_shown_for_pipeline_verdicts(api_client):
    PostFactory(content="pipeline", verified_pipeline=True)
    PostFactory(content="moderator", moderator_verdict=True, confidence_score="88.00")
    PostFactory(content="pending", fact=True)
    posts = {i["post"]["content"]: i["post"] for i in api_client.get(URL).json()["results"]}
    assert posts["pipeline"]["confidence_score"] == "94.00"
    assert posts["pipeline"]["verdict_source"] == "pipeline"
    assert posts["moderator"]["confidence_score"] is None
    assert posts["moderator"]["verdict_source"] == "moderator"
    assert posts["pending"]["confidence_score"] is None


def test_nothing_internal_leaks(api_client):
    PostFactory(
        fact=True,
        flagged_reason="reports",
        report_count=7,
        pipeline_result={"secret": "blob"},
        pipeline_verdict="false",
        moderated_by=VerifiedUserFactory(),
    )
    text = api_client.get(URL).content.decode()
    for word in ("flagged_reason", "report_count", "pipeline_result", "pipeline_verdict", "blob"):
        assert word not in text
    assert "moderated_by" not in text and "@example.test" not in text


# ---------- pagination ----------


def test_pages_of_20_by_default_and_a_cap_of_50(api_client):
    make_posts(55)
    first = api_client.get(URL).json()
    assert len(first["results"]) == 20 and first["next_cursor"]
    assert len(api_client.get(URL, {"page_size": 500}).json()["results"]) == 50


def test_load_more_never_repeats_or_skips_when_new_posts_arrive(api_client):
    posts = make_posts(45)
    page_one = api_client.get(URL).json()
    assert len(page_one["results"]) == 20
    # Five newer posts arrive after the reader loaded the first page.
    newest = timezone.now()
    for i in range(5):
        PostFactory(content=f"Newer {i}", created_at=newest + timedelta(seconds=i))
    cursor = page_one["next_cursor"]
    seen = [item["post"]["content"] for item in page_one["results"]]
    while cursor:
        body = api_client.get(URL, {"cursor": cursor}).json()
        seen += [item["post"]["content"] for item in body["results"]]
        cursor = body["next_cursor"]
    assert seen == [p.content for p in posts]  # exactly the original 45, in order, once each


def test_a_post_removed_between_pages_skips_nothing_else(api_client):
    posts = make_posts(45)
    page_one = api_client.get(URL).json()
    posts[25].delete()  # gone from the middle of page two
    cursor = page_one["next_cursor"]
    seen = [item["post"]["content"] for item in page_one["results"]]
    while cursor:
        body = api_client.get(URL, {"cursor": cursor}).json()
        seen += [item["post"]["content"] for item in body["results"]]
        cursor = body["next_cursor"]
    assert seen == [p.content for i, p in enumerate(posts) if i != 25]


def test_posts_with_equal_timestamps_are_neither_repeated_nor_lost(api_client):
    base = timezone.now() - timedelta(minutes=5)
    tie = base - timedelta(seconds=1)
    PostFactory(content="newest", created_at=base)
    for i in range(3):
        PostFactory(content=f"tie {i}", created_at=tie)
    PostFactory(content="oldest", created_at=base - timedelta(seconds=2))
    pages = walk(api_client, page_size=2)
    flat = [content for page in pages for content in page]
    assert sorted(flat) == sorted(["newest", "tie 0", "tie 1", "tie 2", "oldest"])
    assert len(flat) == len(set(flat))


@pytest.mark.parametrize(
    "cursor",
    [
        "not-a-cursor!!",
        cursor_for(p="garbage"),
        cursor_for(p="2026-01-01 00:00:00"),  # no time zone
        cursor_for(p="2026-13-45 99:00:00+00:00"),  # well-formed but impossible
        cursor_for(p="'; DROP TABLE posts_post; --"),
        cursor_for(o="abc"),
    ],
)
def test_a_crafted_cursor_is_a_404_not_a_500(api_client, cursor):
    PostFactory()
    response = api_client.get(URL, {"cursor": cursor})
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_a_real_cursor_still_works_after_the_guard(api_client):
    make_posts(25)
    cursor = api_client.get(URL).json()["next_cursor"]
    assert api_client.get(URL, {"cursor": cursor}).status_code == 200


# ---------- queries ----------


def feed_queries(client):
    with CaptureQueriesContext(connection) as queries:
        assert client.get(URL).status_code == 200
    return len(queries)


def make_emergencies(count, *, minutes_old=10):
    now = timezone.now()
    return [
        PostFactory(
            fact=True,
            content=f"Emergency {i}",
            is_emergency=True,
            created_at=now - timedelta(minutes=minutes_old, seconds=i),
            emergency_expires_at=now + timedelta(hours=20),
        )
        for i in range(count)
    ]


def test_the_number_of_queries_does_not_grow_with_the_posts(api_client, auth_client):
    reader = auth_client(VerifiedUserFactory())
    sources = [f"10.1000/s{i}" for i in range(5)]
    make_posts(5, fact=True, sources=sources)
    make_emergencies(1)
    small = (feed_queries(api_client), feed_queries(reader))
    make_posts(15, base=timezone.now() - timedelta(hours=1), fact=True, sources=sources)
    make_emergencies(4, minutes_old=20)
    large = (feed_queries(api_client), feed_queries(reader))
    # Anonymous: the page and the pinned list (Part 11C); signed in: the user too.
    assert small == large == (2, 3)


def test_a_later_page_has_no_pinned_list_and_costs_what_it_did(api_client, auth_client):
    make_posts(25)
    make_emergencies(2)
    cursor = api_client.get(URL).json()["next_cursor"]
    reader = auth_client(VerifiedUserFactory())
    for client, expected in ((api_client, 1), (reader, 2)):
        with CaptureQueriesContext(connection) as queries:
            body = client.get(URL, {"cursor": cursor}).json()
        assert (body["pinned"], body["pinned_total"]) == ([], 0)
        assert len(queries) == expected


def test_a_full_page_of_20_is_two_queries_for_an_anonymous_reader(
    api_client, django_assert_num_queries
):
    make_posts(20, fact=True, sources=["10.1000/xyz", "https://example.org/"])
    with django_assert_num_queries(2):  # the page, and the pinned list (Part 11C)
        assert len(api_client.get(URL).json()["results"]) == 20
