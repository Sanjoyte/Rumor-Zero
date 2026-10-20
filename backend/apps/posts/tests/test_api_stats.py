"""`GET /api/v1/posts/{id}/stats/` (Part 11D): visibility per status and viewer, the verdict
fields, the 14 UTC-day buckets and a constant number of queries."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.core.services import get_platform_settings
from apps.moderation import services as moderation
from apps.moderation.models import ActionKind
from apps.moderation.tests.factories import ModerationActionFactory, moderator_user
from apps.posts.models import PostStatus, PostType, VerdictSource
from apps.posts.tests.factories import PostFactory, VerifiedUserFactory
from apps.reputation.tests.factories import (
    FALSE_95,
    TRUE_95,
    label_by_pipeline,
    pending_fact,
    reported_fact,
)
from apps.social.tests.factories import CommentFactory, LikeFactory, RepostFactory

pytestmark = pytest.mark.django_db

KEYS = {
    "confidence_score",
    "confidence_threshold",
    "verdict_source",
    "seconds_to_verdict",
    "verdict_at",
    "daily",
}


def url(post):
    return f"/api/v1/posts/{post.pk}/stats/"


def at(*args, **kwargs):
    return datetime(*args, tzinfo=UTC, **kwargs)


def totals(body):
    return {
        name: sum(day[name] for day in body["daily"]) for name in ("reposts", "likes", "comments")
    }


def test_the_shape_of_a_pending_fact(api_client):
    post = pending_fact()
    body = api_client.get(url(post)).json()
    assert set(body) == KEYS
    assert [body[k] for k in KEYS - {"daily"}] == [None] * 5
    assert len(body["daily"]) == 14


def test_an_opinion_answers_with_null_check_fields(api_client):
    post = PostFactory()
    body = api_client.get(url(post)).json()
    assert [body[k] for k in KEYS - {"daily"}] == [None] * 5
    assert len(body["daily"]) == 14


def test_a_pipeline_label_carries_confidence_threshold_and_time(api_client, fact_limit):
    post = pending_fact(created_at=at(2026, 10, 1, 12))
    label_by_pipeline(post, TRUE_95, now=at(2026, 10, 1, 12, 0, 9))
    body = api_client.get(url(post)).json()
    assert body["confidence_score"] == "95.00"
    assert body["confidence_threshold"] == get_platform_settings().confidence_threshold
    assert body["verdict_source"] == "pipeline"
    assert body["seconds_to_verdict"] == 9
    assert body["verdict_at"] == "2026-10-01T12:00:09Z"


def test_a_false_pipeline_label_has_the_same_fields(api_client):
    post = pending_fact()
    label_by_pipeline(post, FALSE_95)
    body = api_client.get(url(post)).json()
    assert body["confidence_score"] == "95.00"
    assert body["confidence_threshold"] is not None


def test_a_moderator_label_has_no_confidence_but_a_time_from_its_audit_row(api_client):
    post = reported_fact(created_at=at(2026, 10, 1, 12))
    moderation.mark_false(post.pk, moderator=moderator_user(), now=at(2026, 10, 1, 14))
    body = api_client.get(url(post)).json()
    assert body["verdict_source"] == "moderator"
    assert body["confidence_score"] is None and body["confidence_threshold"] is None
    assert body["verdict_at"] == "2026-10-01T14:00:00Z"
    assert body["seconds_to_verdict"] == 7200


def test_a_later_moderator_action_does_not_move_the_verdict_time(api_client):
    """`moderated_at` is overwritten by every moderator action; the audit row is not."""
    post = reported_fact(created_at=at(2026, 10, 1, 12), is_emergency=False)
    moderation.mark_verified(post.pk, moderator=moderator_user(), now=at(2026, 10, 1, 14))
    PostFactory._meta.model.objects.filter(pk=post.pk).update(moderated_at=at(2026, 10, 3, 9))
    body = api_client.get(url(post)).json()
    assert body["verdict_at"] == "2026-10-01T14:00:00Z"


def test_the_latest_decision_into_the_current_status_is_used(api_client):
    """Rows into another status, and other kinds of row, are not the verdict."""
    post = PostFactory(
        moderator_verdict=True, status=PostStatus.VERIFIED_TRUE, created_at=at(2026, 10, 1, 12)
    )

    def row(kind, to, when):
        ModerationActionFactory(
            post=post,
            action=kind,
            from_status=PostStatus.UNDER_REVIEW,
            to_status=to,
            created_at=when,
        )

    row(ActionKind.VERIFIED, PostStatus.VERIFIED_TRUE, at(2026, 10, 1, 13))
    row(ActionKind.MARKED_FALSE, PostStatus.VERIFIED_FALSE, at(2026, 10, 1, 14))
    row(ActionKind.VERIFIED, PostStatus.VERIFIED_TRUE, at(2026, 10, 1, 15))
    row(ActionKind.EMERGENCY_DEMOTED, PostStatus.VERIFIED_TRUE, at(2026, 10, 1, 16))
    row(ActionKind.MARKED_FALSE, PostStatus.VERIFIED_FALSE, at(2026, 10, 1, 17))
    body = api_client.get(url(post)).json()
    assert body["verdict_at"] == "2026-10-01T15:00:00Z"


def test_a_moderator_label_without_an_audit_row_has_no_time(api_client):
    post = PostFactory(
        moderator_verdict=True, status=PostStatus.VERIFIED_TRUE, created_at=at(2026, 10, 1, 12)
    )
    body = api_client.get(url(post)).json()
    assert body["verdict_at"] is None and body["seconds_to_verdict"] is None
    assert body["verdict_source"] == "moderator"


def test_a_late_true_held_under_review_stays_private(api_client):
    post = PostFactory(
        post_type=PostType.FACT,
        status=PostStatus.UNDER_REVIEW,
        flagged_reason="reports",
        pre_review_status=PostStatus.PENDING,
        verdict_source=VerdictSource.PIPELINE,
        confidence_score=Decimal("95.00"),
        pipeline_checked_at=at(2026, 10, 1, 12, 5),
    )
    body = api_client.get(url(post)).json()
    assert [body[k] for k in KEYS - {"daily"}] == [None] * 5


@pytest.mark.parametrize("as_whom", ["anonymous", "other", "author"])
def test_the_answer_does_not_depend_on_who_asks(api_client, auth_client, as_whom):
    post = pending_fact()
    label_by_pipeline(post, TRUE_95)
    client = {
        "anonymous": api_client,
        "other": auth_client(VerifiedUserFactory()),
        "author": auth_client(post.author),
    }[as_whom]
    assert client.get(url(post)).json() == api_client.get(url(post)).json()


def test_a_stale_token_is_not_a_401(api_client):
    post = pending_fact()
    response = api_client.get(url(post), HTTP_AUTHORIZATION="Bearer not-a-token")
    assert response.status_code == 200


def test_it_is_never_cached(api_client):
    assert "no-store" in api_client.get(url(pending_fact()))["Cache-Control"]


@pytest.mark.parametrize(
    "fields", [{"deleted": True, "status": PostStatus.PENDING}, {"removed": True}]
)
def test_a_deleted_or_removed_post_is_a_404_for_everyone(api_client, auth_client, fields):
    post = PostFactory(post_type=PostType.FACT, **fields)
    assert api_client.get(url(post)).status_code == 404
    assert auth_client(post.author).get(url(post)).status_code == 404


@pytest.mark.parametrize(
    "raw", ["nope", "00000000-0000-0000-0000-000000000000", "1234", "%00", "a" * 80]
)
def test_an_unknown_or_malformed_id_is_a_json_404(api_client, raw):
    response = api_client.get(f"/api/v1/posts/{raw}/stats/")
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_the_detail_route_is_not_shadowed(api_client):
    post = pending_fact()
    assert "content" in api_client.get(f"/api/v1/posts/{post.pk}/").json()


# ---------- the buckets ----------


def test_an_empty_post_has_fourteen_zero_days(api_client):
    body = api_client.get(url(PostFactory(created_at=at(2026, 10, 1, 12)))).json()
    assert [d["date"] for d in body["daily"]][:2] == ["2026-10-01", "2026-10-02"]
    assert body["daily"][-1]["date"] == "2026-10-14"
    assert totals(body) == {"reposts": 0, "likes": 0, "comments": 0}


def test_rows_either_side_of_utc_midnight_land_in_adjacent_days(api_client):
    post = PostFactory(fact=True, created_at=at(2026, 10, 1, 23, 59, 30))
    LikeFactory(post=post, created_at=at(2026, 10, 1, 23, 59, 59, microsecond=999999))
    LikeFactory(post=post, created_at=at(2026, 10, 2, 0, 0, 0))
    body = api_client.get(url(post)).json()
    assert [d["likes"] for d in body["daily"][:3]] == [1, 1, 0]
    assert body["daily"][0]["date"] == "2026-10-01"


def test_each_series_counts_in_its_own_column(api_client):
    post = PostFactory(fact=True, created_at=at(2026, 10, 1, 10))
    day2 = at(2026, 10, 2, 8)
    LikeFactory(post=post, created_at=day2)
    LikeFactory(post=post, created_at=day2 + timedelta(minutes=1))
    RepostFactory(post=post, created_at=day2)
    CommentFactory(post=post, created_at=day2)
    body = api_client.get(url(post)).json()
    assert body["daily"][1] == {"date": "2026-10-02", "reposts": 1, "likes": 2, "comments": 1}
    assert totals(body) == {"reposts": 1, "likes": 2, "comments": 1}


def test_the_fourteenth_day_is_in_and_the_fifteenth_is_out(api_client):
    post = PostFactory(fact=True, created_at=at(2026, 10, 1, 10))
    LikeFactory(post=post, created_at=at(2026, 10, 14, 23, 59, 59))
    LikeFactory(post=post, created_at=at(2026, 10, 15, 0, 0, 0))
    body = api_client.get(url(post)).json()
    assert body["daily"][13] == {"date": "2026-10-14", "reposts": 0, "likes": 1, "comments": 0}
    assert totals(body)["likes"] == 1


def test_hidden_and_deleted_comments_never_count(api_client):
    post = PostFactory(fact=True, created_at=at(2026, 10, 1, 10))
    when = at(2026, 10, 1, 11)
    CommentFactory(post=post, created_at=when)
    CommentFactory(post=post, created_at=when + timedelta(seconds=1), hidden=True)
    CommentFactory(post=post, created_at=when + timedelta(seconds=2), deleted=True)
    assert totals(api_client.get(url(post)).json())["comments"] == 1


def test_a_like_taken_back_is_gone(api_client, auth_client):
    post = PostFactory(fact=True)
    fan = VerifiedUserFactory()
    client = auth_client(fan)
    assert client.post(f"/api/v1/posts/{post.pk}/like/").status_code in (200, 201)
    assert totals(api_client.get(url(post)).json())["likes"] == 1
    assert client.delete(f"/api/v1/posts/{post.pk}/like/").status_code in (200, 204)
    assert totals(api_client.get(url(post)).json())["likes"] == 0


def test_other_posts_activity_is_not_counted(api_client):
    post = PostFactory(fact=True)
    LikeFactory(post=PostFactory(fact=True))
    assert totals(api_client.get(url(post)).json())["likes"] == 0


# ---------- queries and privacy ----------


def queries(client, post):
    with CaptureQueriesContext(connection) as captured:
        assert client.get(url(post)).status_code == 200
    return len(captured)


def test_two_queries_however_much_activity(api_client, django_assert_max_num_queries):
    get_platform_settings()  # warm the settings cache: a cold read is one more query
    quiet = pending_fact(created_at=at(2026, 10, 1, 10))
    label_by_pipeline(quiet, TRUE_95)
    busy = pending_fact(created_at=at(2026, 10, 1, 10))
    label_by_pipeline(busy, TRUE_95)
    for i in range(50):
        when = at(2026, 10, 1, 10) + timedelta(hours=i * 5)
        LikeFactory(post=busy, created_at=when)
        RepostFactory(post=busy, created_at=when)
        CommentFactory(post=busy, created_at=when)
    one, many = queries(api_client, quiet), queries(api_client, busy)
    assert one == many == 2


def test_a_moderator_verdict_costs_no_extra_query(api_client):
    post = reported_fact(created_at=at(2026, 10, 1, 12))
    moderation.mark_false(post.pk, moderator=moderator_user(), now=at(2026, 10, 1, 14))
    assert queries(api_client, post) == 2


def test_nothing_private_is_in_the_answer(api_client):
    reporter = VerifiedUserFactory()
    post = reported_fact()
    from apps.reputation.tests.factories import open_reports

    open_reports(post, reporter=reporter)
    entry = moderation.mark_false(post.pk, moderator=moderator_user(), notes="internal note")
    text = api_client.get(url(post)).content.decode()
    for secret in (
        reporter.username,
        str(reporter.pk),
        str(entry.pk),
        entry.moderator.username,
        "internal note",
        post.author.username,
        post.content,
        str(post.pk),
    ):
        assert secret not in text
