"""`GET /api/v1/posts/{id}/` (ARCHITECTURE §9): who sees what, tombstones, query counts."""

import uuid
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.posts.models import PostStatus, PostType
from apps.posts.tests.factories import PostFactory, UserFactory, VerifiedUserFactory
from apps.posts.tests.test_api_create import POST_KEYS

pytestmark = pytest.mark.django_db

BLANKED = {"content", "sources", "verdict_note", "confidence_score", "verdict_source"}


def url(post):
    return f"/api/v1/posts/{post.pk}/"


def make(status, **extra):
    """A post in each of the six statuses, shaped the way the status is reached."""
    if status == PostStatus.PUBLISHED:
        return PostFactory(**extra)
    kwargs = {"fact": True, "status": status}
    if status in (PostStatus.VERIFIED_TRUE, PostStatus.VERIFIED_FALSE):
        kwargs.update(verdict_source="pipeline", confidence_score=Decimal("91.50"))
    kwargs.update(extra)
    return PostFactory(sources=["10.1038/s41558-024-02102", "https://example.org/report"], **kwargs)


ALL = [
    PostStatus.PENDING,
    PostStatus.PUBLISHED,
    PostStatus.VERIFIED_TRUE,
    PostStatus.VERIFIED_FALSE,
    PostStatus.UNDER_REVIEW,
    PostStatus.REMOVED,
]


@pytest.mark.parametrize("status", ALL)
def test_anyone_can_read_a_post_in_every_status_with_the_25_keys(status, api_client, auth_client):
    post = make(status)
    other = auth_client(VerifiedUserFactory())
    author = auth_client(post.author)
    for client in (api_client, other, author):
        response = client.get(url(post))
        assert response.status_code == 200
        body = response.json()
        assert set(body) == POST_KEYS
        assert body["id"] == str(post.pk)
        assert body["status"] == status
        assert body["author"]["username"] == post.author.username
        assert "no-store" in response["Cache-Control"]


@pytest.mark.parametrize("status", [s for s in ALL if s != PostStatus.REMOVED])
def test_a_live_post_is_the_same_for_everyone_except_is_mine_and_the_appeal_button(
    status, api_client, auth_client
):
    post = make(status)
    anonymous = api_client.get(url(post)).json()
    other = auth_client(VerifiedUserFactory()).get(url(post)).json()
    author = auth_client(post.author).get(url(post)).json()
    assert anonymous == other
    assert anonymous["content"] == post.content
    assert anonymous["is_mine"] is False and author["is_mine"] is True
    # Only the author of a FALSE-labelled post may ask for another look (Part 11).
    assert anonymous["can_appeal"] is False and other["can_appeal"] is False
    assert author["can_appeal"] is (status == PostStatus.VERIFIED_FALSE)
    assert {**author, "is_mine": False, "can_appeal": False} == anonymous


def test_sources_come_with_their_kind_in_the_order_entered(api_client):
    post = make(PostStatus.PENDING)
    assert api_client.get(url(post)).json()["sources"] == [
        {"value": "10.1038/s41558-024-02102", "kind": "doi"},
        {"value": "https://example.org/report", "kind": "url"},
    ]


def test_confidence_is_shown_only_for_a_pipeline_verdict(api_client):
    pipeline = make(PostStatus.VERIFIED_TRUE)
    assert api_client.get(url(pipeline)).json()["confidence_score"] == "91.50"
    assert api_client.get(url(pipeline)).json()["verdict_source"] == "pipeline"
    moderator = make(
        PostStatus.VERIFIED_FALSE, verdict_source="moderator", confidence_score=Decimal("70.00")
    )
    body = api_client.get(url(moderator)).json()
    assert body["confidence_score"] is None
    assert body["verdict_source"] == "moderator"
    assert api_client.get(url(make(PostStatus.PENDING))).json()["confidence_score"] is None


def test_a_moderators_note_is_public_on_a_live_post(api_client):
    post = make(PostStatus.VERIFIED_FALSE, verdict_source="moderator", verdict_note="No source.")
    assert api_client.get(url(post)).json()["verdict_note"] == "No source."


def test_a_removed_post_is_a_tombstone_for_the_public_and_for_other_users(api_client, auth_client):
    post = make(
        PostStatus.REMOVED,
        verdict_source="moderator",
        verdict_note="Internal reason shown nowhere.",
        confidence_score=Decimal("80.00"),
    )
    for client in (api_client, auth_client(VerifiedUserFactory())):
        body = client.get(url(post)).json()
        assert set(body) == POST_KEYS
        assert body["status"] == "removed"
        assert body["content"] == ""
        assert body["sources"] == []
        assert body["verdict_note"] == ""
        assert body["confidence_score"] is None
        assert body["verdict_source"] is None
        assert body["is_mine"] is False
        # The author's name and the post time stay visible.
        assert body["author"]["username"] == post.author.username
        assert body["created_at"].endswith("Z")
        assert post.content not in str(body)


def test_the_author_sees_their_removed_post_in_full(auth_client):
    post = make(PostStatus.REMOVED, verdict_note="Please cite.", verdict_source="moderator")
    body = auth_client(post.author).get(url(post)).json()
    assert body["status"] == "removed"
    assert body["content"] == post.content
    assert len(body["sources"]) == 2
    assert body["verdict_note"] == "Please cite."
    assert body["is_mine"] is True
    assert body["can_appeal"] is True  # Part 11: a removed post can be appealed, once
    assert body["appeal_status"] is None
    assert body["removal_reason"] == ""  # no removal row: the factory removed it directly


def test_a_staff_member_who_is_not_the_author_gets_the_tombstone(auth_client):
    post = make(PostStatus.REMOVED)
    moderator = auth_client(VerifiedUserFactory(role="moderator"))
    assert moderator.get(url(post)).json()["content"] == ""


@pytest.mark.parametrize("status", ALL)
def test_a_deleted_post_is_404_for_everyone_the_author_included(status, api_client, auth_client):
    post = make(status, deleted_at=timezone.now())
    for client in (api_client, auth_client(VerifiedUserFactory()), auth_client(post.author)):
        response = client.get(url(post))
        assert response.status_code == 404
        assert response.json() == {"detail": "Not found.", "code": "not_found"}


@pytest.mark.parametrize("bad", ["nope", "123", "status-ish", "g" * 36, f"{uuid.uuid4()}x"])
def test_a_malformed_id_is_a_json_404(bad, api_client):
    response = api_client.get(f"/api/v1/posts/{bad}/")
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_an_unknown_id_is_a_json_404(api_client):
    response = api_client.get(f"/api/v1/posts/{uuid.uuid4()}/")
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_the_detail_is_one_query_anonymous_and_two_signed_in(
    api_client, auth_client, django_assert_num_queries
):
    post = make(PostStatus.PENDING)
    viewer = auth_client(VerifiedUserFactory())
    with django_assert_num_queries(1):
        assert api_client.get(url(post)).status_code == 200
    with django_assert_num_queries(2):
        assert viewer.get(url(post)).status_code == 200


def test_a_stale_token_on_this_public_read_is_a_401(api_client):
    """The client refreshes and retries (lib/api/client.ts); the status endpoint avoids it."""
    post = make(PostStatus.PENDING)
    response = api_client.get(url(post), HTTP_AUTHORIZATION="Bearer not-a-token")
    assert response.status_code == 401


def test_an_opinion_has_no_sources_and_no_confidence(api_client):
    post = PostFactory(post_type=PostType.OPINION)
    body = api_client.get(url(post)).json()
    assert body["sources"] == []
    assert body["confidence_score"] is None
    assert body["post_type"] == "opinion"


def test_the_post_does_not_need_its_author_to_be_verified(api_client):
    post = PostFactory(author=UserFactory())
    assert api_client.get(url(post)).status_code == 200


def test_a_late_pipeline_verdict_on_a_post_under_review_stays_private_for_everyone(
    api_client, auth_client
):
    """Part 9: the pipeline's late TRUE on a reported post is kept for a dismissal, but neither
    the source nor the confidence shows while the post is under review, its author included."""
    post = make(
        PostStatus.UNDER_REVIEW,
        flagged_reason="reports",
        pre_review_status=PostStatus.VERIFIED_TRUE,
        verdict_source="pipeline",
        pipeline_verdict="true",
        confidence_score=Decimal("95.00"),
    )
    for client in (api_client, auth_client(VerifiedUserFactory()), auth_client(post.author)):
        body = client.get(url(post)).json()
        assert body["status"] == "under_review"
        assert body["verdict_source"] is None
        assert body["confidence_score"] is None


def test_the_author_of_a_removed_post_sees_no_verdict_source_either(auth_client):
    post = make(PostStatus.REMOVED, verdict_source="pipeline", confidence_score=Decimal("90.00"))
    body = auth_client(post.author).get(url(post)).json()
    assert body["content"] == post.content
    assert body["verdict_source"] is None
    assert body["confidence_score"] is None
