"""`GET /api/v1/posts/status/?ids=` (ARCHITECTURE §9): the badge poller's public endpoint."""

import uuid
from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.posts.models import PostStatus
from apps.posts.tests.factories import PostFactory, VerifiedUserFactory

pytestmark = pytest.mark.django_db

URL = "/api/v1/posts/status/"
KEYS = {"id", "status", "confidence_score", "verdict_source"}


def ask(client, ids, **extra):
    joined = ids if isinstance(ids, str) else ",".join(str(i) for i in ids)
    return client.get(URL, {"ids": joined}, **extra)


def test_it_is_public_and_a_garbage_token_is_ignored(api_client):
    post = PostFactory(fact=True)
    response = ask(api_client, [post.pk], HTTP_AUTHORIZATION="Bearer not-a-token")
    assert response.status_code == 200
    assert response.json() == {
        "results": [
            {
                "id": str(post.pk),
                "status": "pending",
                "confidence_score": None,
                "verdict_source": None,
            }
        ]
    }
    assert "no-store" in response["Cache-Control"]


def test_every_status_is_reported_with_only_the_four_keys(api_client):
    posts = [
        PostFactory(fact=True),
        PostFactory(),
        PostFactory(verified_pipeline=True),
        PostFactory(moderator_verdict=True),
        PostFactory(under_review=True),
    ]
    results = ask(api_client, [p.pk for p in posts]).json()["results"]
    assert [r["status"] for r in results] == [
        "pending",
        "published",
        "verified_true",
        "verified_false",
        "under_review",
    ]
    assert all(set(r) == KEYS for r in results)
    by_id = {r["id"]: r for r in results}
    assert by_id[str(posts[2].pk)]["confidence_score"] == "94.00"
    assert by_id[str(posts[2].pk)]["verdict_source"] == "pipeline"
    assert by_id[str(posts[3].pk)]["confidence_score"] is None
    assert by_id[str(posts[3].pk)]["verdict_source"] == "moderator"


def test_confidence_is_hidden_unless_it_is_a_pipeline_verdict(api_client):
    post = PostFactory(fact=True, status=PostStatus.UNDER_REVIEW, confidence_score=Decimal("88.00"))
    assert ask(api_client, [post.pk]).json()["results"][0]["confidence_score"] is None


def test_a_removed_post_says_only_that_it_is_removed(api_client):
    post = PostFactory(
        removed=True, fact=True, verdict_source="moderator", confidence_score=Decimal("70.00")
    )
    post.status = PostStatus.REMOVED
    post.save()
    assert ask(api_client, [post.pk]).json()["results"] == [
        {"id": str(post.pk), "status": "removed", "confidence_score": None, "verdict_source": None}
    ]


def test_deleted_and_unknown_ids_are_left_out(api_client):
    live = PostFactory(fact=True)
    gone = PostFactory(fact=True, deleted_at=timezone.now())
    results = ask(api_client, [gone.pk, uuid.uuid4(), live.pk]).json()["results"]
    assert [r["id"] for r in results] == [str(live.pk)]


def test_results_follow_the_order_asked_and_duplicates_collapse(api_client):
    a, b = PostFactory(fact=True), PostFactory(fact=True)
    results = ask(api_client, [b.pk, a.pk, b.pk]).json()["results"]
    assert [r["id"] for r in results] == [str(b.pk), str(a.pk)]


@pytest.mark.parametrize("raw", ["", " , ,", None])
def test_no_ids_is_a_400_on_ids(raw, api_client):
    response = api_client.get(URL) if raw is None else api_client.get(URL, {"ids": raw})
    assert response.status_code == 400
    assert response.json() == {"ids": ["Send the ids of the posts to check."]}


def test_a_malformed_id_is_a_400_on_ids(api_client):
    response = ask(api_client, f"{uuid.uuid4()},nope")
    assert response.status_code == 400
    assert list(response.json()) == ["ids"]
    assert "nope" in response.json()["ids"][0]


def test_fifty_ids_are_fine_and_fifty_one_are_not(api_client):
    ids = [uuid.uuid4() for _ in range(51)]
    assert ask(api_client, ids[:50]).status_code == 200
    response = ask(api_client, ids)
    assert response.status_code == 400
    assert response.json() == {"ids": ["Check at most 50 posts at a time."]}


def test_duplicates_do_not_count_toward_the_limit(api_client):
    one = uuid.uuid4()
    assert ask(api_client, [one] * 60).status_code == 200


def test_fifty_posts_cost_one_query(api_client, django_assert_num_queries):
    posts = [PostFactory(fact=True) for _ in range(50)]
    with django_assert_num_queries(1):
        results = ask(api_client, [p.pk for p in posts]).json()["results"]
    assert len(results) == 50


def test_the_query_leaves_out_the_heavy_columns(api_client):
    post = PostFactory(fact=True)
    with CaptureQueriesContext(connection) as queries:
        ask(api_client, [post.pk])
    sql = queries[0]["sql"]
    assert "pipeline_result" not in sql and '"content"' not in sql and "join" not in sql.lower()


def test_polling_does_not_use_up_the_posting_throttle(auth_client):
    author = VerifiedUserFactory()
    client = auth_client(author)
    post = PostFactory(fact=True)
    for _ in range(35):
        assert ask(client, [post.pk]).status_code == 200
    # Still allowed to post: the poll never touched `post_create`.
    assert (
        client.post("/api/v1/posts/", {"content": "x", "post_type": "opinion"}).status_code == 201
    )


def test_120_requests_a_minute_per_ip_then_429(api_client, settings):
    settings.PROXY_SHARED_SECRET = "test-relay-secret"
    relay = {"HTTP_X_RZ_PROXY_SECRET": "test-relay-secret"}
    post = PostFactory(fact=True)
    for _ in range(120):
        response = ask(api_client, [post.pk], HTTP_X_RZ_CLIENT_IP="203.0.113.7", **relay)
        assert response.status_code == 200
    response = ask(api_client, [post.pk], HTTP_X_RZ_CLIENT_IP="203.0.113.7", **relay)
    assert response.status_code == 429
    assert response.json()["code"] == "throttled"
    assert "Retry-After" in response
    other = ask(api_client, [post.pk], HTTP_X_RZ_CLIENT_IP="203.0.113.8", **relay)
    assert other.status_code == 200


def test_reading_the_feed_does_not_use_up_the_status_throttle(api_client, settings):
    settings.PROXY_SHARED_SECRET = "test-relay-secret"
    relay = {
        "HTTP_X_RZ_PROXY_SECRET": "test-relay-secret",
        "HTTP_X_RZ_CLIENT_IP": "203.0.113.9",
    }
    for _ in range(130):
        assert api_client.get("/api/v1/posts/", **relay).status_code == 200
    assert ask(api_client, [uuid.uuid4()], **relay).status_code == 200


def late_true_under_review():
    """A fact that reports sent to review, then the pipeline's late decisive TRUE (Part 9): the
    TRUE is kept for when the reports are dismissed, and must stay private until then."""
    return PostFactory(
        fact=True,
        status=PostStatus.UNDER_REVIEW,
        flagged_reason="reports",
        pre_review_status=PostStatus.VERIFIED_TRUE,
        verdict_source="pipeline",
        pipeline_verdict="true",
        confidence_score=Decimal("95.00"),
    )


def test_who_decided_is_public_only_with_the_label(api_client):
    hidden = late_true_under_review()
    appealed = PostFactory(
        fact=True,
        status=PostStatus.UNDER_REVIEW,
        flagged_reason="appeal",
        pre_review_status=PostStatus.VERIFIED_FALSE,
        verdict_source="moderator",
    )
    shown = PostFactory(verified_pipeline=True)
    results = ask(api_client, [hidden.pk, appealed.pk, shown.pk]).json()["results"]
    assert [(r["status"], r["verdict_source"], r["confidence_score"]) for r in results] == [
        ("under_review", None, None),
        ("under_review", None, None),
        ("verified_true", "pipeline", "94.00"),
    ]
