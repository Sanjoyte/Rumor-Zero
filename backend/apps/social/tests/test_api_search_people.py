"""`GET /api/v1/search/?type=users` (Part 12): people by username prefix and display-name word."""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.accounts.tests.factories import UserFactory
from apps.posts.tests.factories import PostFactory
from apps.social.search import MAX_PEOPLE_QUERY_LENGTH, clean_people_query
from apps.social.tests.factories import FollowFactory, VerifiedUserFactory

pytestmark = pytest.mark.django_db

URL = "/api/v1/search/"
ROW_KEYS = {
    "id",
    "username",
    "display_name",
    "bio",
    "avatar_url",
    "reputation",
    "counts",
    "is_following",
    "is_me",
}


def people(client, q, **params):
    return client.get(URL, {"q": q, "type": "users", **params})


def names(response):
    assert response.status_code == 200, response.content
    return [row["username"] for row in response.json()["results"]]


# ---- the query cleaner ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "cleaned"),
    [
        ("Ada", "ada"),
        ("  ada  ", "ada"),
        ("@ada", "ada"),
        ("@@ada", "@ada"),
        ("ada   lovelace", "ada lovelace"),
        ("ada\x00\x7f\x1b", "ada"),
        ("ada\tlovelace", "ada lovelace"),
        ("ＡＤＡ", "ada"),  # fullwidth, NFKC
        ("a_c", "a_c"),
        ("_", "_"),
    ],
)
def test_cleaning(raw, cleaned):
    assert clean_people_query(raw) == cleaned


@pytest.mark.parametrize("raw", ["", "   ", "-", "'", "@", "'-'", "!!", "\x00", "@ -"])
def test_nothing_searchable_is_empty(raw):
    assert clean_people_query(raw) == ""


def test_the_query_is_cut_at_sixty_four_after_normalising():
    assert clean_people_query("a" * 100) == "a" * MAX_PEOPLE_QUERY_LENGTH
    # NFKC turns one "㌀" into several characters: the cut comes after that.
    assert len(clean_people_query("㌀" * 40)) == MAX_PEOPLE_QUERY_LENGTH


# ---- matching -------------------------------------------------------------------------------


def test_a_username_prefix_matches_case_insensitively(api_client):
    VerifiedUserFactory(username="ada_lovelace")
    VerifiedUserFactory(username="adam")
    VerifiedUserFactory(username="nada")
    assert names(people(api_client, "ADA")) == ["ada_lovelace", "adam"]


def test_the_username_must_start_with_the_query(api_client):
    VerifiedUserFactory(username="nada")
    assert names(people(api_client, "ada")) == []


def test_underscore_percent_and_backslash_are_literal(api_client):
    VerifiedUserFactory(username="abc")
    VerifiedUserFactory(username="a_c")
    VerifiedUserFactory(username="a_cat")
    assert names(people(api_client, "a_c")) == ["a_c", "a_cat"]
    assert names(people(api_client, "a%")) == []
    assert names(people(api_client, "a\\")) == []
    assert names(people(api_client, "%")) == []


def test_nfkc_is_applied_to_the_query(api_client):
    VerifiedUserFactory(username="ada")
    assert names(people(api_client, "ＡＤＡ")) == ["ada"]


def test_a_leading_at_sign_is_dropped(api_client):
    VerifiedUserFactory(username="ada")
    assert names(people(api_client, "@ada")) == ["ada"]


@pytest.mark.parametrize(
    ("display_name", "q", "found"),
    [
        ("Ada Lovelace", "love", True),  # a word after a space
        ("Ada Lovelace", "ada", True),  # the start
        ("Ada Lovelace", "ada love", True),  # a phrase prefix, as typed
        ("Mary-Jane Watson", "jane", True),  # after a hyphen
        ("Conan O'Brien", "brien", True),  # after an apostrophe
        ("Conan O’Brien", "brien", True),  # after a typographic apostrophe
        ("Ada Lovelace", "velace", False),  # mid-word
        ("Ada Lovelace", "lovelace ada", False),  # not word by word
        ("", "zed", False),  # a blank name never matches
    ],
)
def test_a_display_name_word_matches(api_client, display_name, q, found):
    VerifiedUserFactory(username="zz_person", display_name=display_name)
    assert names(people(api_client, q)) == (["zz_person"] if found else [])


@pytest.mark.parametrize("q", ["-", "'", "@", "@-", "'-'"])
def test_a_query_with_nothing_searchable_is_an_empty_200(api_client, q):
    VerifiedUserFactory(username="ada", display_name="Mary-Jane O'Brien")
    response = people(api_client, q)
    assert response.status_code == 200
    assert response.json() == {"results": [], "next_cursor": None}


def test_the_blank_and_missing_query_are_a_400(api_client):
    # Whitespace or control characters only count as blank, before the people rules apply.
    for blank in ("", " ", "\t", "\x00"):
        assert people(api_client, blank).status_code == 400
    assert api_client.get(URL, {"type": "users"}).status_code == 400


def test_an_inactive_user_is_not_found(api_client):
    UserFactory(username="gone_ada", is_active=False)
    VerifiedUserFactory(username="here_ada")
    assert names(people(api_client, "gone")) == []
    assert names(people(api_client, "here")) == ["here_ada"]


# ---- the rows -------------------------------------------------------------------------------


def test_a_row_has_the_nine_keys_of_a_follower_row(api_client):
    VerifiedUserFactory(username="ada", display_name="Ada", bio="Hello there")
    (row,) = people(api_client, "ada").json()["results"]
    assert set(row) == ROW_KEYS
    assert set(row["counts"]) == {"verified"}
    assert set(row["reputation"]) == {"score", "sample"}
    assert row["is_following"] is False and row["is_me"] is False


def test_the_answer_has_no_pinned_keys(api_client):
    VerifiedUserFactory(username="ada")
    assert set(people(api_client, "ada").json()) == {"results", "next_cursor"}


def test_the_verified_count_includes_deleted_posts(api_client):
    ada = VerifiedUserFactory(username="ada")
    PostFactory(author=ada, verified_pipeline=True)
    PostFactory(author=ada, verified_pipeline=True, deleted=True)
    PostFactory(author=ada, fact=True)
    (row,) = people(api_client, "ada").json()["results"]
    assert row["counts"]["verified"] == 2


def test_the_score_is_null_until_three_events_count(api_client):
    UserFactory(username="fresh", reputation_score=77, reputation_sample=2)
    UserFactory(username="known", reputation_score=77, reputation_sample=3)
    (fresh,) = people(api_client, "fresh").json()["results"]
    (known,) = people(api_client, "known").json()["results"]
    assert fresh["reputation"] == {"score": None, "sample": 2}
    assert known["reputation"] == {"score": 77, "sample": 3}


def test_is_following_and_is_me_for_a_signed_in_viewer(auth_client):
    me = VerifiedUserFactory(username="adam_me")
    followed = VerifiedUserFactory(username="adam_followed")
    VerifiedUserFactory(username="adam_other")
    FollowFactory(follower=me, following=followed)
    rows = {r["username"]: r for r in people(auth_client(me), "adam").json()["results"]}
    assert rows["adam_me"]["is_me"] is True and rows["adam_me"]["is_following"] is False
    assert rows["adam_followed"]["is_following"] is True
    assert rows["adam_other"]["is_following"] is False and rows["adam_other"]["is_me"] is False


# ---- order ----------------------------------------------------------------------------------


def test_exact_username_then_prefix_then_name_matches(api_client):
    VerifiedUserFactory(username="zoe_name", display_name="Someone ada")
    VerifiedUserFactory(username="aaa_name", display_name="Someone Ada")  # A to Z puts it first
    VerifiedUserFactory(username="ada_b")
    VerifiedUserFactory(username="ada")
    VerifiedUserFactory(username="ada_a")
    VerifiedUserFactory(username="amy", display_name="Ada Amy")
    assert names(people(api_client, "ada")) == [
        "ada",
        "ada_a",
        "ada_b",
        "aaa_name",
        "amy",
        "zoe_name",
    ]


def test_a_higher_score_never_jumps_ahead(api_client):
    UserFactory(username="ada_low", reputation_score=10, reputation_sample=50)
    UserFactory(username="ada_top", reputation_score=99, reputation_sample=50)
    VerifiedUserFactory(username="ada_new")
    assert names(people(api_client, "ada")) == ["ada_low", "ada_new", "ada_top"]


def test_followers_do_not_change_the_order(api_client):
    popular = VerifiedUserFactory(username="ada_z")
    VerifiedUserFactory(username="ada_a")
    for _ in range(3):
        FollowFactory(following=popular)
    assert names(people(api_client, "ada")) == ["ada_a", "ada_z"]


# ---- pagination -----------------------------------------------------------------------------


def test_pages_hold_twenty_in_a_stable_order_up_to_a_hundred(api_client):
    for n in range(110):
        VerifiedUserFactory(username=f"pat_{n:03d}")
    seen, cursor, sizes = [], None, []
    while True:
        extra = {"cursor": cursor} if cursor else {}
        body = people(api_client, "pat", **extra).json()
        sizes.append(len(body["results"]))
        seen += [r["username"] for r in body["results"]]
        cursor = body["next_cursor"]
        if not cursor:
            break
    assert sizes == [20] * 5
    assert seen == [f"pat_{n:03d}" for n in range(100)]


def test_a_crafted_cursor_is_a_404(api_client):
    VerifiedUserFactory(username="ada")
    for cursor in ("1", "6", "abc", "02"):
        assert people(api_client, "ada", cursor=cursor).status_code == 404


# ---- queries --------------------------------------------------------------------------------


def test_a_page_is_one_query_for_a_visitor(api_client, django_assert_num_queries):
    for n in range(20):
        person = VerifiedUserFactory(username=f"sam_{n:02d}")
        PostFactory(author=person, verified_pipeline=True)
    with django_assert_num_queries(1):
        assert people(api_client, "sam").status_code == 200


def test_a_page_is_two_queries_for_a_signed_in_viewer(auth_client, django_assert_num_queries):
    viewer = VerifiedUserFactory()
    for n in range(20):
        FollowFactory(follower=viewer, following=VerifiedUserFactory(username=f"sam_{n:02d}"))
    client = auth_client(viewer)
    with django_assert_num_queries(2):
        assert people(client, "sam").status_code == 200


def test_an_unsearchable_query_makes_no_database_query_for_a_visitor(api_client):
    with CaptureQueriesContext(connection) as queries:
        assert people(api_client, "-").json()["results"] == []
    assert len(queries) == 0
