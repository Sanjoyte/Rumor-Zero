"""`GET /api/v1/me/bookmarks/`: only your own, newest bookmark first, the §9 envelope."""

from datetime import timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.accounts.tests.factories import UserFactory
from apps.posts.tests.test_api_create import POST_KEYS
from apps.social.tests.factories import BookmarkFactory, PostFactory, VerifiedUserFactory

pytestmark = pytest.mark.django_db

URL = "/api/v1/me/bookmarks/"


@pytest.fixture
def ada():
    return VerifiedUserFactory(username="ada")


def save(user, count, *, content="saved", base=None):
    """`count` posts bookmarked by `user`, the first one the oldest bookmark."""
    base = base or timezone.now() - timedelta(hours=1)
    posts = []
    for i in range(count):
        post = PostFactory(content=f"{content} {i}", created_at=base - timedelta(days=1, hours=i))
        BookmarkFactory(user=user, post=post, created_at=base + timedelta(seconds=i))
        posts.append(post)
    return posts


def contents(response):
    return [item["post"]["content"] for item in response.json()["results"]]


def test_anonymous_is_401(api_client):
    assert api_client.get(URL).status_code == 401


def test_a_stale_bearer_is_401(api_client):
    api_client.credentials(HTTP_AUTHORIZATION="Bearer not-a-token")
    assert api_client.get(URL).status_code == 401


def test_an_unverified_user_can_read_their_bookmarks(auth_client):
    user = UserFactory()
    save(user, 1)
    assert contents(auth_client(user).get(URL)) == ["saved 0"]


def test_an_empty_list_is_the_empty_envelope(auth_client, ada):
    assert auth_client(ada).get(URL).json() == {
        "pinned": [],
        "pinned_total": 0,
        "results": [],
        "next_cursor": None,
    }


def test_the_items_are_posts_and_activity_at_is_the_bookmark_time(auth_client, ada):
    (post,) = save(ada, 1)
    response = auth_client(ada).get(URL)
    assert "no-store" in response["Cache-Control"]
    item = response.json()["results"][0]
    assert set(item) == {"kind", "post", "reposted_by", "activity_at"}
    assert set(item["post"]) == POST_KEYS
    assert (item["kind"], item["reposted_by"]) == ("post", None)
    assert item["post"]["bookmarked_by_me"] is True
    assert item["activity_at"] != item["post"]["created_at"]
    assert item["post"]["id"] == str(post.pk)


def test_the_newest_bookmark_comes_first_whatever_the_age_of_the_post(auth_client, ada):
    save(ada, 3)
    assert contents(auth_client(ada).get(URL)) == ["saved 2", "saved 1", "saved 0"]


def test_only_your_own_bookmarks_are_returned_never_anyone_elses(auth_client, ada):
    other = VerifiedUserFactory()
    save(other, 2, content="theirs")
    save(ada, 1, content="mine")
    assert contents(auth_client(ada).get(URL)) == ["mine 0"]
    assert contents(auth_client(other).get(URL)) == ["theirs 1", "theirs 0"]


def test_there_is_no_way_to_ask_for_another_users_list(auth_client, ada):
    other = VerifiedUserFactory(username="bob")
    save(other, 1, content="theirs")
    client = auth_client(ada)
    assert client.get(URL, {"user": str(other.pk)}).json()["results"] == []
    assert client.get("/api/v1/users/bob/bookmarks/").status_code == 404


def test_deleted_and_removed_posts_are_dropped_and_pages_stay_full(auth_client, ada):
    posts = save(ada, 8)
    posts[7].status, posts[6].deleted_at = "removed", timezone.now()
    posts[7].save()
    posts[6].save()
    first = auth_client(ada).get(URL, {"page_size": 3}).json()
    assert [i["post"]["content"] for i in first["results"]] == ["saved 5", "saved 4", "saved 3"]
    second = auth_client(ada).get(URL, {"page_size": 3, "cursor": first["next_cursor"]}).json()
    assert [i["post"]["content"] for i in second["results"]] == ["saved 2", "saved 1", "saved 0"]
    assert second["next_cursor"] is None


def test_a_post_removed_after_it_was_bookmarked_is_in_no_page_and_the_row_survives(
    auth_client, ada
):
    (post,) = save(ada, 1)
    post.status = "removed"
    post.save()
    assert auth_client(ada).get(URL).json()["results"] == []
    assert ada.bookmarks.count() == 1  # only hidden: restoring the post restores the bookmark


def test_the_cursor_walks_without_repeat_or_gap_while_a_bookmark_arrives(auth_client, ada):
    save(ada, 7)
    client = auth_client(ada)
    first = client.get(URL, {"page_size": 3}).json()
    BookmarkFactory(user=ada, post=PostFactory(content="late"))
    seen = [i["post"]["content"] for i in first["results"]]
    cursor = first["next_cursor"]
    while cursor:
        page = client.get(URL, {"page_size": 3, "cursor": cursor}).json()
        seen += [i["post"]["content"] for i in page["results"]]
        cursor = page["next_cursor"]
    assert seen == [f"saved {i}" for i in range(6, -1, -1)]


@pytest.mark.parametrize("cursor", ["cD1ub3QtYS1kYXRl", "cD0yMDI2LTEwLTEwVDEyOjAwOjAw"])
def test_a_crafted_cursor_is_a_404(auth_client, ada, cursor):
    assert auth_client(ada).get(URL, {"cursor": cursor}).status_code == 404


def test_the_page_size_follows_the_feed_rules(auth_client, ada):
    save(ada, 3)
    client = auth_client(ada)
    assert len(client.get(URL, {"page_size": 2}).json()["results"]) == 2
    assert len(client.get(URL, {"page_size": "junk"}).json()["results"]) == 3
    assert len(client.get(URL, {"page_size": 1000}).json()["results"]) == 3  # capped at 50


def test_the_counts_and_flags_are_filled_for_the_viewer(auth_client, ada):
    (post,) = save(ada, 1)
    from apps.social.tests.factories import LikeFactory, RepostFactory

    LikeFactory(user=ada, post=post)
    RepostFactory(user=ada, post=post)
    RepostFactory(post=post)
    body = auth_client(ada).get(URL).json()["results"][0]["post"]
    assert (body["liked_by_me"], body["reposted_by_me"], body["repost_count"]) == (True, True, 2)


def test_three_queries_whatever_the_size(auth_client, ada):
    client = auth_client(ada)

    def count():
        with CaptureQueriesContext(connection) as captured:
            assert client.get(URL).status_code == 200
        return len(captured)

    save(ada, 3)
    small = count()
    save(ada, 17, content="more", base=timezone.now() - timedelta(minutes=30))
    assert small == count() == 3  # the user, the bookmark page, the posts
