"""`daily_engagement` (Part 11D): grouped counts of a post's reposts, likes and shown comments by
UTC day, in one query."""

from datetime import UTC, date, datetime, timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.posts.tests.factories import PostFactory
from apps.social.engagement import daily_engagement
from apps.social.tests.factories import CommentFactory, LikeFactory, RepostFactory

pytestmark = pytest.mark.django_db

START = datetime(2026, 10, 1, tzinfo=UTC)
END = START + timedelta(days=14)


def test_it_groups_by_series_and_utc_day():
    post = PostFactory(fact=True)
    LikeFactory(post=post, created_at=START + timedelta(hours=23, minutes=59))
    LikeFactory(post=post, created_at=START + timedelta(days=1))
    RepostFactory(post=post, created_at=START + timedelta(days=1, hours=5))
    CommentFactory(post=post, created_at=START + timedelta(days=2))
    assert daily_engagement(post.pk, START, END) == {
        ("likes", date(2026, 10, 1)): 1,
        ("likes", date(2026, 10, 2)): 1,
        ("reposts", date(2026, 10, 2)): 1,
        ("comments", date(2026, 10, 3)): 1,
    }


def test_the_window_is_half_open():
    post = PostFactory(fact=True)
    LikeFactory(post=post, created_at=START - timedelta(microseconds=1))
    LikeFactory(post=post, created_at=START)
    LikeFactory(post=post, created_at=END - timedelta(microseconds=1))
    LikeFactory(post=post, created_at=END)
    result = daily_engagement(post.pk, START, END)
    assert result == {("likes", date(2026, 10, 1)): 1, ("likes", date(2026, 10, 14)): 1}


def test_an_empty_post_is_an_empty_result():
    assert daily_engagement(PostFactory().pk, START, END) == {}


def test_only_shown_comments_count():
    post = PostFactory(fact=True)
    CommentFactory(post=post, created_at=START)
    CommentFactory(post=post, created_at=START + timedelta(seconds=1), hidden=True)
    CommentFactory(post=post, created_at=START + timedelta(seconds=2), deleted=True)
    assert daily_engagement(post.pk, START, END) == {("comments", date(2026, 10, 1)): 1}


def test_one_query_whatever_the_activity():
    post = PostFactory(fact=True)
    for i in range(20):
        LikeFactory(post=post, created_at=START + timedelta(hours=i))
        RepostFactory(post=post, created_at=START + timedelta(hours=i))
    with CaptureQueriesContext(connection) as captured:
        daily_engagement(post.pk, START, END)
    assert len(captured) == 1
