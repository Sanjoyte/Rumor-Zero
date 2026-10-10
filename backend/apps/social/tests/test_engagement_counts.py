"""`like_count`, `comment_count` and `liked_by_me` are real in every list and the detail, with a
constant number of queries (ARCHITECTURE §9)."""

from datetime import timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.posts.serializers import PostSerializer
from apps.social.models import Follow
from apps.social.tests.factories import (
    CommentFactory,
    FollowFactory,
    LikeFactory,
    PostFactory,
    VerifiedUserFactory,
)

pytestmark = pytest.mark.django_db


def engagement(post_json):
    return post_json["like_count"], post_json["comment_count"], post_json["liked_by_me"]


@pytest.fixture
def ada():
    return VerifiedUserFactory(username="ada")


@pytest.fixture
def post(ada):
    """A post with 3 likes (one by `ada`) and 2 shown comments, plus a hidden and a deleted one."""
    post = PostFactory(content="Counted")
    LikeFactory(post=post, user=ada)
    LikeFactory.create_batch(2, post=post)
    base = timezone.now() - timedelta(hours=1)
    CommentFactory(post=post, created_at=base)
    CommentFactory(post=post, created_at=base + timedelta(seconds=2))
    CommentFactory(post=post, hidden=True, created_at=base + timedelta(seconds=4))
    CommentFactory(post=post, deleted=True, created_at=base + timedelta(seconds=6))
    return post


def test_a_post_with_nothing_has_zeros(api_client):
    body = api_client.get(f"/api/v1/posts/{PostFactory().pk}/").json()
    assert engagement(body) == (0, 0, False)


def test_the_detail_counts_likes_and_only_the_comments_that_are_shown(api_client, post):
    assert engagement(api_client.get(f"/api/v1/posts/{post.pk}/").json()) == (3, 2, False)


def test_liked_by_me_is_per_viewer(api_client, auth_client, ada, post):
    other = auth_client(VerifiedUserFactory())
    assert engagement(auth_client(ada).get(f"/api/v1/posts/{post.pk}/").json()) == (3, 2, True)
    assert engagement(other.get(f"/api/v1/posts/{post.pk}/").json()) == (3, 2, False)


def test_the_recent_feed_counts(api_client, auth_client, ada, post):
    anonymous = api_client.get("/api/v1/posts/").json()["results"][0]["post"]
    assert engagement(anonymous) == (3, 2, False)
    mine = auth_client(ada).get("/api/v1/posts/").json()["results"][0]["post"]
    assert engagement(mine) == (3, 2, True)


def test_a_persons_posts_count(api_client, auth_client, ada, post):
    username = post.author.username
    anonymous = api_client.get(f"/api/v1/users/{username}/posts/").json()["results"][0]["post"]
    assert engagement(anonymous) == (3, 2, False)
    mine = auth_client(ada).get(f"/api/v1/users/{username}/posts/").json()["results"][0]["post"]
    assert engagement(mine) == (3, 2, True)


def test_the_following_feed_counts_and_stays_fresh_on_a_cache_hit(auth_client, ada, post):
    FollowFactory(follower=ada, following=post.author)
    client = auth_client(ada)
    first = client.get("/api/v1/feed/").json()["results"][0]["post"]
    assert engagement(first) == (3, 2, True)
    # The second request is a cache hit (ids only), and the counts are read fresh.
    LikeFactory(post=post)
    CommentFactory(post=post, created_at=timezone.now())
    second = client.get("/api/v1/feed/").json()["results"][0]["post"]
    assert engagement(second) == (4, 3, True)
    assert Follow.objects.count() == 1


def test_the_new_post_answer_has_zero_counts(auth_client, ada):
    body = auth_client(ada).post(
        "/api/v1/posts/", {"content": "New", "post_type": "opinion"}, format="json"
    )
    assert body.status_code == 201
    assert engagement(body.json()) == (0, 0, False)


def test_a_removed_posts_tombstone_keeps_its_counts_and_leaks_nothing(api_client, auth_client):
    removed = PostFactory(removed=True, content="secret text")
    LikeFactory(post=removed)
    body = api_client.get(f"/api/v1/posts/{removed.pk}/").json()
    assert body["content"] == ""
    assert engagement(body) == (1, 0, False)


def test_a_viewers_like_on_a_removed_post_is_still_reported_to_that_viewer(auth_client, ada):
    removed = PostFactory(removed=True)
    LikeFactory(post=removed, user=ada)
    body = auth_client(ada).get(f"/api/v1/posts/{removed.pk}/").json()
    assert body["liked_by_me"] is True


def test_the_serializer_refuses_a_post_that_was_not_annotated():
    post = PostFactory()
    with pytest.raises(AttributeError):
        PostSerializer(post, context={}).data  # noqa: B018  (a list that forgot for_list(viewer))


# ---------- the query count stays constant ----------


def count_queries(client, path):
    with CaptureQueriesContext(connection) as captured:
        assert client.get(path).status_code == 200
    return len(captured)


def add_posts(author, n, *, hours):
    base = timezone.now() - timedelta(hours=hours)
    for i in range(n):
        post = PostFactory(author=author, created_at=base - timedelta(seconds=2 * i))
        LikeFactory.create_batch(2, post=post)
        CommentFactory(post=post, created_at=base)


def test_every_list_keeps_a_constant_number_of_queries(api_client, auth_client, ada, settings):
    settings.FEED_CACHE_SECONDS = 0  # a cache hit is one query fewer; count the misses
    author = VerifiedUserFactory(username="writer")
    FollowFactory(follower=ada, following=author)
    viewer = auth_client(ada)
    # path -> the expected (anonymous, signed-in) counts; the Following feed has no anonymous view
    expected = {
        "/api/v1/posts/": (1, 2),
        "/api/v1/users/writer/posts/": (2, 3),
        "/api/v1/feed/": (None, 3),
    }

    def measure():
        return {
            path: (None if want[0] is None else count_queries(api_client, path),)
            + (count_queries(viewer, path),)
            for path, want in expected.items()
        }

    add_posts(author, 3, hours=2)
    small = measure()
    add_posts(author, 17, hours=1)
    assert measure() == small == expected
