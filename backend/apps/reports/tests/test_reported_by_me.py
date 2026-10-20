"""`reported_by_me` in every list and on the detail page (ARCHITECTURE §9): true only for the
person who reported, false for everyone else and for visitors, and never an extra query."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.moderation.queries import appeal_defaults
from apps.posts.serializers import PostSerializer
from apps.reports.tests.factories import ReportFactory
from apps.social.engagement import engagement_defaults
from apps.social.tests.factories import (
    BookmarkFactory,
    FollowFactory,
    PostFactory,
    VerifiedUserFactory,
)

pytestmark = pytest.mark.django_db


def flags(response):
    """`reported_by_me` of every post in a feed answer, by the post's content."""
    return {
        item["post"]["content"]: item["post"]["reported_by_me"]
        for item in response.json()["results"]
    }


@pytest.fixture
def scene():
    """`reader` reported 'mine', not 'theirs'; `other` reported 'theirs' too."""
    reader, other, author = (VerifiedUserFactory() for _ in range(3))
    base = timezone.now() - timedelta(minutes=5)
    mine = PostFactory(author=author, content="mine", created_at=base)
    theirs = PostFactory(author=author, content="theirs", created_at=base - timedelta(seconds=1))
    ReportFactory(post=mine, reporter=reader)
    ReportFactory(post=theirs, reporter=other)
    return reader, other, author


def test_recent_marks_only_my_reports(scene, auth_client, api_client):
    reader, other, _ = scene
    assert flags(auth_client(reader).get("/api/v1/posts/")) == {"mine": True, "theirs": False}
    assert flags(auth_client(other).get("/api/v1/posts/")) == {"mine": False, "theirs": True}
    assert flags(api_client.get("/api/v1/posts/")) == {"mine": False, "theirs": False}


def test_the_detail_page_marks_my_report(scene, auth_client, api_client):
    reader, other, _ = scene
    mine = PostFactory._meta.model.objects.get(content="mine")
    assert auth_client(reader).get(f"/api/v1/posts/{mine.pk}/").json()["reported_by_me"] is True
    assert auth_client(other).get(f"/api/v1/posts/{mine.pk}/").json()["reported_by_me"] is False
    assert api_client.get(f"/api/v1/posts/{mine.pk}/").json()["reported_by_me"] is False


def test_the_following_feed_marks_my_report(scene, auth_client):
    reader, _, author = scene
    FollowFactory(follower=reader, following=author)
    assert flags(auth_client(reader).get("/api/v1/feed/")) == {"mine": True, "theirs": False}


def test_a_profiles_posts_mark_my_report(scene, auth_client, api_client):
    reader, _, author = scene
    url = f"/api/v1/users/{author.username}/posts/"
    assert flags(auth_client(reader).get(url)) == {"mine": True, "theirs": False}
    assert flags(api_client.get(url)) == {"mine": False, "theirs": False}


def test_the_bookmarks_page_marks_my_report(scene, auth_client):
    reader, _, _ = scene
    for post in PostFactory._meta.model.objects.all():
        BookmarkFactory(user=reader, post=post)
    assert flags(auth_client(reader).get("/api/v1/me/bookmarks/")) == {
        "mine": True,
        "theirs": False,
    }


def test_a_dismissed_report_is_still_mine(scene, auth_client):
    """The flag says "you reported this", which stays true for life (one report per post)."""
    reader, _, _ = scene
    ReportFactory(post=PostFactory(content="old"), reporter=reader, dismissed=True)
    assert flags(auth_client(reader).get("/api/v1/posts/"))["old"] is True


def test_a_report_leaves_the_query_count_unchanged(
    scene, auth_client, api_client, django_assert_num_queries
):
    reader, _, author = scene
    for i in range(18):
        post = PostFactory(author=author, content=f"extra {i}")
        ReportFactory(post=post, reporter=reader)
    client = auth_client(reader)  # (building the client mints a token: keep it out of the count)
    # A first page also reads the pinned emergencies (Part 11C).
    with django_assert_num_queries(2):  # a visitor: the page and the pinned list
        assert len(api_client.get("/api/v1/posts/").json()["results"]) == 20
    with django_assert_num_queries(3):  # signed in: the user too
        assert len(client.get("/api/v1/posts/").json()["results"]) == 20


def test_a_new_post_is_not_reported_yet():
    data = PostSerializer(appeal_defaults(engagement_defaults(PostFactory()))).data
    assert data["reported_by_me"] is False
