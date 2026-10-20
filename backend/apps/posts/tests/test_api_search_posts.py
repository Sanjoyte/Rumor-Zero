"""`GET /api/v1/search/?type=posts` (Part 12).

Every post here sets `content` explicitly: the factory's default ("Post number 7") would match
"post" and "number".
"""

from datetime import timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.posts.models import Post, PostStatus
from apps.posts.tests.factories import PostFactory, UserFactory, VerifiedUserFactory
from apps.social.tests.factories import LikeFactory

pytestmark = pytest.mark.django_db

URL = "/api/v1/search/"


def search(client, q, **params):
    return client.get(URL, {"q": q, **params})


def ids(response):
    return [item["post"]["id"] for item in response.json()["results"]]


def texts(response):
    return [item["post"]["content"] for item in response.json()["results"]]


def make(content, *, minutes_ago=0, **kwargs):
    return PostFactory(
        content=content, created_at=timezone.now() - timedelta(minutes=minutes_ago), **kwargs
    )


# ---- matching ----------------------------------------------------------------------------


def test_running_finds_run_and_runs(api_client):
    run = make("I run every morning")
    runs = make("She runs far", minutes_ago=1)
    make("A runway is not a run", minutes_ago=2)  # "run" is in it too
    make("Walking is nice", minutes_ago=3)
    response = search(api_client, "running")
    assert response.status_code == 200
    found = set(ids(response))
    assert {str(run.id), str(runs.id)} <= found
    assert "Walking is nice" not in texts(response)


def test_runner_and_runway_are_other_words(api_client):
    make("A runway at dawn")
    make("The runner won")
    assert ids(search(api_client, "run")) == []


def test_an_exact_phrase_needs_the_words_together(api_client):
    together = make("Heavy rain is coming tonight")
    make("The rain was heavy and it is coming", minutes_ago=1)
    assert ids(search(api_client, '"rain is coming"')) == [str(together.id)]


def test_a_minus_word_excludes(api_client):
    keep = make("storm over the coast")
    make("storm over the city", minutes_ago=1)
    make("storm and flood", minutes_ago=2)
    response = search(api_client, "storm -flood -city")
    assert ids(response) == [str(keep.id)]


def test_or_matches_either_word(api_client):
    a = make("flood warning")
    b = make("fire warning", minutes_ago=1)
    make("calm weather", minutes_ago=2)
    assert set(ids(search(api_client, "flood or fire"))) == {str(a.id), str(b.id)}


def test_matching_ignores_case(api_client):
    post = make("Breaking NEWS from the harbour")
    assert ids(search(api_client, "news HARBOUR")) == [str(post.id)]


def test_stop_word_only_queries_match_nothing(api_client):
    make("the and of")
    response = search(api_client, "the")
    assert response.status_code == 200
    assert response.json() == {"pinned": [], "pinned_total": 0, "results": [], "next_cursor": None}


def test_a_negation_only_query_is_an_empty_200_with_no_database_query(api_client):
    make("anything at all")
    with CaptureQueriesContext(connection) as queries:
        response = search(api_client, "-anything")
    assert response.status_code == 200
    assert response.json()["results"] == []
    assert len(queries) == 0


def test_a_negation_only_query_costs_the_signed_in_user_lookup_only(auth_client):
    make("anything at all")
    client = auth_client(VerifiedUserFactory())
    with CaptureQueriesContext(connection) as queries:
        response = search(client, "-anything or -other")
    assert response.json()["results"] == []
    assert len(queries) == 1


def test_a_unicode_query_works(api_client):
    post = make("Café opens near the station")
    assert ids(search(api_client, "café")) == [str(post.id)]


# ---- ranking ------------------------------------------------------------------------------


def test_more_occurrences_rank_higher(api_client):
    once = make("storm", minutes_ago=0)
    thrice = make("storm warning storm", minutes_ago=5)
    assert ids(search(api_client, "storm")) == [str(thrice.id), str(once.id)]


def test_equal_rank_is_newest_first(api_client):
    old = make("storm update", minutes_ago=30)
    new = make("storm update", minutes_ago=1)
    mid = make("storm update", minutes_ago=10)
    assert ids(search(api_client, "storm")) == [str(new.id), str(mid.id), str(old.id)]


# ---- what is never found --------------------------------------------------------------------


def test_removed_and_deleted_posts_are_never_found(api_client, auth_client):
    shown = make("flood shown")
    removed = make("flood removed", removed=True, minutes_ago=1)
    deleted = make("flood deleted", deleted=True, minutes_ago=2)
    both = make("flood both", removed=True, deleted=True, minutes_ago=3)
    for client in (api_client, auth_client(removed.author), auth_client(deleted.author)):
        found = ids(search(client, "flood"))
        assert found == [str(shown.id)]
    assert {removed.id, deleted.id, both.id}.isdisjoint(
        set(Post.objects.visible().values_list("id", flat=True))
    )


def test_a_removed_status_filter_is_a_400(api_client):
    response = search(api_client, "flood", status="removed")
    assert response.status_code == 400
    assert "status" in response.json()


def test_a_post_the_pipeline_would_clear_stays_under_review(api_client):
    post = make(
        "late verdict flood",
        fact=True,
        status=PostStatus.UNDER_REVIEW,
        flagged_reason="reports",
        pre_review_status=PostStatus.VERIFIED_TRUE,
        verdict_source="pipeline",
        pipeline_verdict="true",
    )
    (item,) = search(api_client, "flood").json()["results"]
    assert item["post"]["id"] == str(post.id)
    assert item["post"]["status"] == "under_review"


# ---- what is found as in the feeds ------------------------------------------------------------


def test_pending_review_emergency_and_suspended_authors_are_found(api_client):
    now = timezone.now()
    pending = make("flood pending", fact=True)
    review = make("flood review", under_review=True, minutes_ago=1)
    emergency = make(
        "flood emergency",
        fact=True,
        is_emergency=True,
        emergency_expires_at=now + timedelta(hours=20),
        minutes_ago=2,
    )
    suspended = make("flood suspended", author=UserFactory(is_active=False), minutes_ago=3)
    expected = {str(p.id) for p in (pending, review, emergency, suspended)}
    assert set(ids(search(api_client, "flood"))) == expected


# ---- filters ------------------------------------------------------------------------------


@pytest.fixture
def mixed():
    return {
        "opinion": make("flood opinion", minutes_ago=0),
        "pending": make("flood pending", fact=True, minutes_ago=1),
        "true": make("flood true", verified_pipeline=True, minutes_ago=2),
        "false": make("flood false", moderator_verdict=True, minutes_ago=3),
        "review": make("flood review", under_review=True, minutes_ago=4),
    }


def pick(mixed, *names):
    return [str(mixed[name].id) for name in names]


def test_post_type_filter(api_client, mixed):
    assert ids(search(api_client, "flood", post_type="opinion")) == pick(mixed, "opinion", "review")
    assert set(ids(search(api_client, "flood", post_type="fact"))) == set(
        pick(mixed, "pending", "true", "false")
    )


@pytest.mark.parametrize(
    ("status", "name"),
    [
        ("pending", "pending"),
        ("published", "opinion"),
        ("verified_true", "true"),
        ("verified_false", "false"),
        ("under_review", "review"),
    ],
)
def test_status_filter(api_client, mixed, status, name):
    assert ids(search(api_client, "flood", status=status)) == pick(mixed, name)


def test_filters_are_anded(api_client, mixed):
    assert ids(search(api_client, "flood", post_type="fact", status="verified_true")) == pick(
        mixed, "true"
    )
    assert ids(search(api_client, "flood", post_type="opinion", status="verified_true")) == []


@pytest.mark.parametrize(
    "params",
    [{"post_type": "other"}, {"status": "nope"}, {"status": "removed"}, {"type": "videos"}],
)
def test_a_bad_filter_value_is_a_400_on_that_field(api_client, params):
    response = search(api_client, "flood", **params)
    assert response.status_code == 400
    assert set(response.json()) & set(params)


def test_the_filters_are_ignored_for_people(api_client):
    UserFactory(username="floodwatch")
    response = search(api_client, "flood", type="users", post_type="other", status="removed")
    assert response.status_code == 200
    assert [row["username"] for row in response.json()["results"]] == ["floodwatch"]


# ---- the query itself ---------------------------------------------------------------------


@pytest.mark.parametrize("q", ["", "   ", "\x00", "\t\n"])
def test_a_blank_query_is_a_400(api_client, q):
    response = search(api_client, q)
    assert response.status_code == 400
    assert response.json()["q"] == ["Enter something to search for."]


def test_a_missing_query_is_a_400(api_client):
    response = api_client.get(URL)
    assert response.status_code == 400
    assert response.json()["q"] == ["Enter something to search for."]


def test_a_query_over_two_hundred_characters_is_a_400(api_client):
    response = search(api_client, "x" * 201)
    assert response.status_code == 400
    assert response.json()["q"] == ["Keep it to 200 characters."]
    assert search(api_client, "x" * 200).status_code == 200


def test_a_nul_byte_is_not_a_500(api_client):
    post = make("flood warning")
    response = search(api_client, "flood\x00 warning")
    assert response.status_code == 200
    assert ids(response) == [str(post.id)]


def test_a_del_character_and_other_controls_are_removed(api_client):
    post = make("flood warning")
    assert ids(search(api_client, "flo\x7fod\x1b warning")) == [str(post.id)]


# ---- pagination ---------------------------------------------------------------------------


def seed(count):
    """`count` equally ranked matches, each with its own timestamp (newest has the lowest n)."""
    base = timezone.now() - timedelta(hours=1)
    return [
        PostFactory(content="storm update", created_at=base - timedelta(seconds=n))
        for n in range(count)
    ]


def walk(client, **params):
    """Every page, in order: [(ids, next_cursor)]."""
    pages, cursor = [], None
    while True:
        extra = {"cursor": cursor} if cursor else {}
        body = search(client, "storm", **params, **extra).json()
        pages.append(([i["post"]["id"] for i in body["results"]], body["next_cursor"]))
        cursor = body["next_cursor"]
        if not cursor:
            return pages


def test_pages_hold_twenty_and_the_cursor_is_the_next_page_number(api_client):
    posts = seed(45)
    pages = walk(api_client)
    assert [(len(page), cursor) for page, cursor in pages] == [(20, "2"), (20, "3"), (5, None)]
    flat = [i for page, _ in pages for i in page]
    assert flat == [str(p.id) for p in posts]  # newest first, no repeats, none missing


def test_exactly_twenty_matches_have_no_next_page(api_client):
    posts = seed(20)
    (page,) = walk(api_client)
    assert page == ([str(p.id) for p in posts], None)


def test_twenty_one_matches_look_ahead_to_a_second_page(api_client):
    seed(21)
    pages = walk(api_client)
    assert [(len(page), cursor) for page, cursor in pages] == [(20, "2"), (1, None)]


def test_the_cap_is_five_pages(api_client):
    seed(110)
    pages = walk(api_client)
    assert [len(page) for page, _ in pages] == [20] * 5
    assert pages[-1][1] is None
    flat = [i for page, _ in pages for i in page]
    assert len(set(flat)) == 100


def test_an_empty_cursor_is_page_one(api_client):
    seed(25)
    first = search(api_client, "storm").json()
    empty = search(api_client, "storm", cursor="").json()
    assert first == empty


@pytest.mark.parametrize("cursor", ["1", "0", "6", "02", "abc", " ", "-3", "2.5", "999"])
def test_a_crafted_cursor_is_a_404(api_client, cursor):
    seed(3)
    response = search(api_client, "storm", cursor=cursor)
    assert response.status_code == 404
    assert response.json() == {"detail": "Invalid cursor", "code": "not_found"}


def test_a_crafted_cursor_is_a_404_even_for_a_negation_only_query(api_client):
    assert search(api_client, "-storm", cursor="abc").status_code == 404


def test_a_page_past_the_end_is_empty(api_client):
    seed(3)
    body = search(api_client, "storm", cursor="2").json()
    assert body["results"] == [] and body["next_cursor"] is None


# ---- the answer ---------------------------------------------------------------------------


def test_the_answer_is_the_feed_envelope_with_the_post_keys(api_client):
    post = make("flood warning")
    body = search(api_client, "flood").json()
    assert set(body) == {"pinned", "pinned_total", "results", "next_cursor"}
    assert body["pinned"] == [] and body["pinned_total"] == 0
    (item,) = body["results"]
    assert set(item) == {"kind", "post", "reposted_by", "activity_at"}
    assert item["kind"] == "post" and item["reposted_by"] is None
    assert item["activity_at"] == item["post"]["created_at"]
    assert len(item["post"]) == 25
    assert item["post"]["id"] == str(post.id)


def test_the_flags_are_right_for_the_viewer(auth_client):
    viewer = VerifiedUserFactory()
    liked = make("flood liked")
    make("flood plain", minutes_ago=1)
    LikeFactory(user=viewer, post=liked)
    results = search(auth_client(viewer), "flood").json()["results"]
    flags = {item["post"]["content"]: item["post"]["liked_by_me"] for item in results}
    assert flags == {"flood liked": True, "flood plain": False}


def test_an_author_sees_is_mine(auth_client):
    post = make("flood mine")
    (item,) = search(auth_client(post.author), "flood").json()["results"]
    assert item["post"]["is_mine"] is True


def test_anonymous_works_and_has_no_flags_set(api_client):
    make("flood warning")
    (item,) = search(api_client, "flood").json()["results"]
    assert item["post"]["liked_by_me"] is False and item["post"]["is_mine"] is False


def test_a_stale_token_is_a_401_like_every_list(api_client):
    api_client.credentials(HTTP_AUTHORIZATION="Bearer not-a-token")
    assert search(api_client, "flood").status_code == 401


def test_the_answer_is_never_cached(api_client):
    make("flood warning")
    response = search(api_client, "flood")
    assert "no-cache" in response["Cache-Control"] or "max-age=0" in response["Cache-Control"]


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_only_get_is_allowed(auth_client, method):
    client = auth_client(VerifiedUserFactory())
    assert getattr(client, method)(URL + "?q=flood").status_code == 405


# ---- queries ------------------------------------------------------------------------------


def busy_page():
    """20 matching posts with likes, an appeal-able removal state and several authors."""
    posts = seed(20)
    for post in posts[:10]:
        LikeFactory(post=post)
    return posts


def test_a_page_is_one_query_for_a_visitor(api_client, django_assert_num_queries):
    busy_page()
    with django_assert_num_queries(1):
        assert search(api_client, "storm").status_code == 200


def test_a_page_is_two_queries_for_a_signed_in_viewer(auth_client, django_assert_num_queries):
    viewer = VerifiedUserFactory()
    busy_page()
    client = auth_client(viewer)
    with django_assert_num_queries(2):
        assert search(client, "storm").status_code == 200


def test_the_sql_ranks_with_the_stored_vector_and_matches_with_the_operator(api_client):
    make("flood warning")
    with CaptureQueriesContext(connection) as queries:
        search(api_client, "flood")
    sql = queries[0]["sql"]
    assert "@@" in sql
    # A string rank would re-parse the stored vector's text with the default configuration.
    assert "to_tsvector(COALESCE(" not in sql
    assert "ts_rank(" in sql
