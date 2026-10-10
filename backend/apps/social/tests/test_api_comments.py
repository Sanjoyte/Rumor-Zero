"""`GET /api/v1/posts/{id}/comments/`: public, oldest first, cursor-paged, hidden ones left out."""

import uuid
from datetime import timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.social.tests.factories import CommentFactory, PostFactory, VerifiedUserFactory

pytestmark = pytest.mark.django_db

COMMENT_KEYS = {"id", "author", "content", "is_mine", "created_at"}


def url(post_id):
    return f"/api/v1/posts/{post_id}/comments/"


@pytest.fixture
def post():
    return PostFactory()


def comments_on(post, count, *, base=None, **extra):
    """`count` comments, each with its own timestamp, the first the oldest."""
    base = base or timezone.now() - timedelta(hours=1)
    return [
        CommentFactory(
            post=post, content=f"c{i}", created_at=base + timedelta(seconds=2 * i), **extra
        )
        for i in range(count)
    ]


def test_an_empty_post_has_no_comments(api_client, post):
    response = api_client.get(url(post.pk))
    assert response.status_code == 200
    assert response.json() == {"results": [], "next_cursor": None}


def test_comments_come_oldest_first(api_client, post):
    base = timezone.now() - timedelta(hours=1)
    CommentFactory(post=post, content="second", created_at=base + timedelta(minutes=2))
    CommentFactory(post=post, content="first", created_at=base)
    CommentFactory(post=post, content="third", created_at=base + timedelta(minutes=3))
    assert [c["content"] for c in api_client.get(url(post.pk)).json()["results"]] == [
        "first",
        "second",
        "third",
    ]


def test_a_comment_has_five_keys_and_nothing_about_moderation(api_client, post):
    author = VerifiedUserFactory(username="bobby", display_name="Bo")
    CommentFactory(post=post, author=author, content="Hello there")
    comment = api_client.get(url(post.pk)).json()["results"][0]
    assert set(comment) == COMMENT_KEYS
    assert comment["author"] == {
        "id": str(author.pk),
        "username": "bobby",
        "display_name": "Bo",
        "avatar_url": None,
    }
    assert (comment["content"], comment["is_mine"]) == ("Hello there", False)
    assert comment["created_at"].endswith("Z")


def test_is_mine_is_true_only_for_the_signed_in_author(auth_client, post):
    ada, bo = VerifiedUserFactory(), VerifiedUserFactory()
    comments_on(post, 1, author=ada)
    assert auth_client(ada).get(url(post.pk)).json()["results"][0]["is_mine"] is True
    assert auth_client(bo).get(url(post.pk)).json()["results"][0]["is_mine"] is False


def test_hidden_and_deleted_comments_are_in_no_list_not_even_their_authors(auth_client, post):
    author = VerifiedUserFactory()
    CommentFactory(post=post, author=author, content="shown")
    CommentFactory(post=post, author=author, content="hidden", hidden=True)
    CommentFactory(post=post, author=author, content="deleted", deleted=True)
    assert [c["content"] for c in auth_client(author).get(url(post.pk)).json()["results"]] == [
        "shown"
    ]


def test_other_posts_comments_are_left_out(api_client, post):
    CommentFactory(post=PostFactory())
    CommentFactory(post=post, content="mine")
    assert [c["content"] for c in api_client.get(url(post.pk)).json()["results"]] == ["mine"]


@pytest.mark.parametrize("trait", ["fact", "under_review", "verified_pipeline"])
def test_every_visible_status_has_comments(api_client, trait):
    post = PostFactory(**{trait: True})
    comments_on(post, 1)
    assert len(api_client.get(url(post.pk)).json()["results"]) == 1


@pytest.mark.parametrize("trait", ["removed", "deleted"])
def test_a_removed_or_deleted_post_has_no_comment_list(api_client, trait):
    post = PostFactory(**{trait: True})
    comments_on(post, 2)
    response = api_client.get(url(post.pk))
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_a_removed_post_is_404_for_its_author_too(auth_client):
    post = PostFactory(removed=True)
    assert auth_client(post.author).get(url(post.pk)).status_code == 404


@pytest.mark.parametrize("post_id", [str(uuid.uuid4()), "not-a-uuid"])
def test_an_unknown_or_malformed_post_id_is_a_json_404(api_client, post_id):
    response = api_client.get(url(post_id))
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_paging_walks_every_comment_once_in_order(api_client, post):
    comments_on(post, 7)
    seen, cursor = [], None
    for _ in range(5):
        params = {"page_size": 3, **({"cursor": cursor} if cursor else {})}
        body = api_client.get(url(post.pk), params).json()
        seen += [c["content"] for c in body["results"]]
        cursor = body["next_cursor"]
        if cursor is None:
            break
    assert seen == [f"c{i}" for i in range(7)]


def test_the_default_page_is_20_and_the_maximum_50(api_client, post):
    comments_on(post, 55)
    first = api_client.get(url(post.pk)).json()
    assert (len(first["results"]), first["next_cursor"] is not None) == (20, True)
    assert len(api_client.get(url(post.pk), {"page_size": 500}).json()["results"]) == 50


def test_a_comment_arriving_between_pages_is_neither_skipped_nor_repeated(api_client, post):
    comments_on(post, 6)
    first = api_client.get(url(post.pk), {"page_size": 3}).json()
    CommentFactory(post=post, content="late", created_at=timezone.now())
    second = api_client.get(url(post.pk), {"page_size": 3, "cursor": first["next_cursor"]}).json()
    seen = [c["content"] for c in first["results"] + second["results"]]
    assert seen[:6] == [f"c{i}" for i in range(6)]
    assert len(seen) == len(set(seen))


@pytest.mark.parametrize("cursor", ["cD1ub3QtYS1kYXRl", "cD0yMDI2LTEwLTAxVDEyOjAwOjAw"])
def test_a_crafted_cursor_is_a_404_not_a_500(api_client, post, cursor):
    # base64 of "p=not-a-date" and of a naive (time-zone-less) timestamp
    comments_on(post, 1)
    response = api_client.get(url(post.pk), {"cursor": cursor})
    assert response.status_code == 404


def test_a_stale_token_is_a_401_as_on_the_post_detail(api_client, post):
    api_client.credentials(HTTP_AUTHORIZATION="Bearer not-a-real-token")
    assert api_client.get(url(post.pk)).status_code == 401


def test_the_list_is_never_cached(api_client, post):
    assert "no-cache" in api_client.get(url(post.pk))["Cache-Control"]


def queries(client, post):
    with CaptureQueriesContext(connection) as captured:
        assert client.get(url(post.pk)).status_code == 200
    return len(captured)


def test_the_query_count_is_constant(api_client, auth_client, post):
    viewer = auth_client(VerifiedUserFactory())
    comments_on(post, 3)
    small = (queries(api_client, post), queries(viewer, post))
    comments_on(post, 17, base=timezone.now() - timedelta(hours=3))
    CommentFactory(post=post, hidden=True)
    large = (queries(api_client, post), queries(viewer, post))
    assert small == large == (2, 3)
