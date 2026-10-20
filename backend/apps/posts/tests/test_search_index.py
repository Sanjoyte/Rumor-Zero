"""The search column and its index (Part 12): the database's own guarantees."""

import random

import pytest
from django.db import connection, transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.posts.models import Post
from apps.posts.search import search_posts
from apps.posts.tests.factories import PostFactory

pytestmark = pytest.mark.django_db

WORDS = [
    "storm",
    "flood",
    "fire",
    "harbour",
    "bridge",
    "council",
    "school",
    "vaccine",
    "election",
    "budget",
    "river",
    "coast",
    "market",
    "energy",
    "water",
    "health",
    "transport",
    "library",
    "airport",
    "festival",
    "weather",
]


def column(name):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT is_generated, generation_expression FROM information_schema.columns "
            "WHERE table_name = 'posts_post' AND column_name = %s",
            [name],
        )
        return cursor.fetchone()


def vector_of(post):
    with connection.cursor() as cursor:
        cursor.execute("SELECT search_vector::text FROM posts_post WHERE id = %s", [post.pk])
        return cursor.fetchone()[0]


def test_the_vector_is_always_generated_from_the_content():
    is_generated, expression = column("search_vector")
    assert is_generated == "ALWAYS"
    assert "to_tsvector" in expression and "english" in expression and "content" in expression


def test_the_vector_follows_the_content():
    post = PostFactory(content="running quickly")
    assert vector_of(post) == "'quick':2 'run':1"
    Post.objects.filter(pk=post.pk).update(content="flooding")
    assert vector_of(post) == "'flood':1"


def test_the_vector_cannot_be_written():
    post = PostFactory(content="something")
    update = "UPDATE posts_post SET search_vector = to_tsvector('x') WHERE id = %s"
    with pytest.raises(Exception, match="generated column"), transaction.atomic():
        connection.cursor().execute(update, [post.pk])


def test_the_gin_index_is_on_the_vector():
    with connection.cursor() as cursor:
        cursor.execute("SELECT indexdef FROM pg_indexes WHERE indexname = 'posts_search_idx'")
        (definition,) = cursor.fetchone()
    assert "USING gin (search_vector)" in definition


def test_the_username_like_index_that_prefix_search_uses_exists():
    """People search is `username LIKE 'abc%'`: only a `varchar_pattern_ops` index serves it."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT indexdef FROM pg_indexes WHERE tablename = %s AND indexdef ILIKE %s",
            [User._meta.db_table, "%(username varchar_pattern_ops)%"],
        )
        assert cursor.fetchone() is not None


def test_the_search_query_uses_the_gin_index():
    """The very queryset the view runs, on a table big enough for the planner to prefer the
    index: 3,000 posts, one in a hundred with a rare word. Sequential scans are disabled for
    this transaction so a small table can't pick them."""
    rng = random.Random(7)
    author = PostFactory().author
    now = timezone.now()
    Post.objects.bulk_create(
        Post(
            author=author,
            content=" ".join(rng.choices(WORDS, k=6)) + (" zeppelin" if n % 100 == 0 else ""),
            post_type="opinion",
            status="published",
            created_at=now,
        )
        for n in range(3000)
    )
    with connection.cursor() as cursor:
        cursor.execute("ANALYZE posts_post")
        cursor.execute("SET LOCAL enable_seqscan = off")
    plan = search_posts("zeppelin storm", None).explain(format="json")
    assert "Bitmap Index Scan" in plan
    assert "posts_search_idx" in plan
