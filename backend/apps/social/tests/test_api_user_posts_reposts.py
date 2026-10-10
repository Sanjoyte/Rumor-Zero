"""`GET /api/v1/users/{username}/posts/` with reposts (Part 7B): a person's posts and reposts,
the filter chips by the original's type, stubs, and full pages."""

from datetime import timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.social.tests.factories import PostFactory, RepostFactory, VerifiedUserFactory

pytestmark = pytest.mark.django_db


def url(name="ada"):
    return f"/api/v1/users/{name}/posts/"


@pytest.fixture
def ada():
    return VerifiedUserFactory(username="ada", display_name="Ada")


def ago(minutes):
    return timezone.now() - timedelta(minutes=minutes)


def post(author, content, minutes, **kwargs):
    return PostFactory(author=author, content=content, created_at=ago(minutes), **kwargs)


def repost(user, original, minutes):
    return RepostFactory(user=user, post=original, created_at=ago(minutes))


def shape_body(body):
    out = []
    for item in body["results"]:
        text = "gone" if item["post"].get("unavailable") else item["post"]["content"]
        out.append(f"{item['kind']}:{text}")
    return out


def shape(response):
    return shape_body(response.json())


def test_a_profile_lists_the_persons_posts_and_reposts_by_activity(api_client, ada):
    other = VerifiedUserFactory()
    post(ada, "ada post", 30)
    repost(ada, post(other, "liked this", 90), 10)
    post(ada, "newest", 1)
    assert shape(api_client.get(url())) == ["post:newest", "repost:liked this", "post:ada post"]


def test_a_repost_item_names_the_profile_owner_and_the_repost_time(api_client, ada):
    made = repost(ada, post(VerifiedUserFactory(), "x", 90), 10)
    (item,) = api_client.get(url()).json()["results"]
    assert item["kind"] == "repost"
    assert item["reposted_by"] == {
        "id": str(ada.pk),
        "username": "ada",
        "display_name": "Ada",
        "avatar_url": None,
    }
    assert item["activity_at"].startswith(made.created_at.strftime("%Y-%m-%dT%H:%M"))


def test_someone_elses_reposts_are_not_on_this_profile(api_client, ada):
    repost(VerifiedUserFactory(), post(ada, "ada post", 30), 10)
    assert shape(api_client.get(url())) == ["post:ada post"]


@pytest.mark.parametrize("trait", ["deleted", "removed"])
def test_a_repost_of_a_deleted_or_removed_original_is_a_stub(api_client, ada, trait):
    original = post(VerifiedUserFactory(), "secret words", 90, **{trait: True})
    repost(ada, original, 10)
    response = api_client.get(url())
    (item,) = response.json()["results"]
    assert item["post"] == {"id": str(original.pk), "unavailable": True}
    assert "secret words" not in response.content.decode()


def test_the_viewers_flags_are_filled_on_a_reposted_post(auth_client, ada):
    original = post(VerifiedUserFactory(), "x", 90)
    repost(ada, original, 10)
    viewer = VerifiedUserFactory()
    repost(viewer, original, 5)
    body = auth_client(viewer).get(url()).json()["results"][0]["post"]
    assert (body["repost_count"], body["reposted_by_me"]) == (2, True)


# ---------- the chips filter reposts by the original's type ----------


@pytest.fixture
def mixed(ada):
    other = VerifiedUserFactory()
    post(ada, "my fact", 50, fact=True)
    post(ada, "my opinion", 49)
    repost(ada, post(other, "their fact", 100, fact=True), 20)
    repost(ada, post(other, "their opinion", 100), 19)
    repost(ada, post(other, "gone fact", 100, fact=True, deleted=True), 18)
    repost(ada, post(other, "gone opinion", 100, removed=True), 17)


def test_all_shows_everything(api_client, mixed):
    assert len(shape(api_client.get(url()))) == 6


def test_facts_shows_my_facts_and_reposts_of_facts_including_a_stub(api_client, mixed):
    assert shape(api_client.get(url(), {"post_type": "fact"})) == [
        "repost:gone",  # the deleted fact (its type is known although its text is not shown)
        "repost:their fact",
        "post:my fact",
    ]


def test_opinions_shows_my_opinions_and_reposts_of_opinions_including_a_stub(api_client, mixed):
    assert shape(api_client.get(url(), {"post_type": "opinion"})) == [
        "repost:gone",  # the removed opinion
        "repost:their opinion",
        "post:my opinion",
    ]


def test_a_bad_filter_is_still_a_400(api_client, mixed):
    response = api_client.get(url(), {"post_type": "gossip"})
    assert response.status_code == 400
    assert "post_type" in response.json()


def test_the_filter_survives_paging(api_client, ada, mixed):
    first = api_client.get(url(), {"post_type": "fact", "page_size": 2}).json()
    second = api_client.get(
        url(), {"post_type": "fact", "page_size": 2, "cursor": first["next_cursor"]}
    ).json()
    assert shape_body(first) + shape_body(second) == [
        "repost:gone",
        "repost:their fact",
        "post:my fact",
    ]
    assert second["next_cursor"] is None


# ---------- pages and the cursor ----------


def test_pages_are_full_and_the_walk_has_no_repeat_or_gap_while_items_arrive(api_client, ada):
    other = VerifiedUserFactory()
    for i in range(5):
        post(ada, f"p{i}", 10 + i)
        repost(ada, post(other, f"s{i}", 500 + i), 20 + i)
    first = api_client.get(url(), {"page_size": 4}).json()
    post(ada, "late", 0)
    repost(ada, post(other, "late original", 700), 0)
    pages = [first]
    cursor = first["next_cursor"]
    while cursor:
        pages.append(api_client.get(url(), {"page_size": 4, "cursor": cursor}).json())
        cursor = pages[-1]["next_cursor"]
    assert [len(p["results"]) for p in pages] == [4, 4, 2]  # no page is short but the last
    assert [x for p in pages for x in shape_body(p)] == (
        [f"post:p{i}" for i in range(5)] + [f"repost:s{i}" for i in range(5)]
    )


@pytest.mark.parametrize("cursor", ["cD1ub3QtYS1kYXRl", "!!!", "x" * 200])
def test_a_crafted_cursor_is_a_404(api_client, ada, cursor):
    assert api_client.get(url(), {"cursor": cursor}).status_code == 404


def test_a_profile_is_public_and_a_stale_bearer_is_still_a_401(api_client, ada):
    post(ada, "x", 5)
    assert api_client.get(url()).status_code == 200
    api_client.credentials(HTTP_AUTHORIZATION="Bearer nope")
    assert api_client.get(url()).status_code == 401


def test_three_queries_anonymous_and_four_signed_in_whatever_the_size(api_client, auth_client, ada):
    viewer = auth_client(VerifiedUserFactory())
    other = VerifiedUserFactory()

    def counts():
        out = []
        for client in (api_client, viewer):
            with CaptureQueriesContext(connection) as captured:
                assert client.get(url()).status_code == 200
            out.append(len(captured))
        return tuple(out)

    for i in range(3):
        post(ada, f"p{i}", 10 + i)
        repost(ada, post(other, f"s{i}", 500 + i), 20 + i)
    small = counts()
    for i in range(3, 9):
        post(ada, f"p{i}", 10 + i)
        repost(ada, post(other, f"s{i}", 500 + i), 20 + i)
    assert small == counts() == (3, 4)  # the lookup, the keys (a union), the posts, the viewer
