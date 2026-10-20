"""The pure builders of `GET /api/v1/posts/{id}/stats/` (Part 11D): the 14 UTC-day window and the
verdict fields, with given times (no clock, no database)."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest

from apps.posts import stats
from apps.posts.models import PostStatus, VerdictSource


def at(*args, **kwargs):
    return datetime(*args, tzinfo=UTC, **kwargs)


def post(**fields):
    values = {
        "status": PostStatus.PUBLISHED,
        "verdict_source": None,
        "confidence_score": None,
        "pipeline_checked_at": None,
        "created_at": at(2026, 10, 1, 12),
    }
    return SimpleNamespace(**{**values, **fields})


def test_the_window_is_fourteen_utc_days_from_the_posts_own_date():
    start, end = stats.window(at(2026, 10, 1, 23, 59, 30))
    assert start == at(2026, 10, 1)
    assert end == at(2026, 10, 15)


def test_the_window_reads_the_utc_date_of_a_non_utc_time():
    # 2026-10-02 01:30 in UTC+2 is still 2026-10-01 in UTC.
    tz = timedelta(hours=2)
    from datetime import timezone as tzmod

    created = datetime(2026, 10, 2, 1, 30, tzinfo=tzmod(tz))
    assert stats.window(created)[0] == at(2026, 10, 1)


def test_fourteen_zero_filled_days_in_order():
    buckets = stats.daily_buckets(at(2026, 10, 30, 8), {})
    assert len(buckets) == 14
    assert buckets[0] == {"date": "2026-10-30", "reposts": 0, "likes": 0, "comments": 0}
    assert buckets[2]["date"] == "2026-11-01"  # across a month end
    assert buckets[-1]["date"] == "2026-11-12"
    assert all(set(b) == {"date", "reposts", "likes", "comments"} for b in buckets)


def test_counts_land_in_their_day_and_series():
    counts = {
        ("likes", date(2026, 10, 1)): 3,
        ("reposts", date(2026, 10, 1)): 1,
        ("comments", date(2026, 10, 14)): 2,
    }
    buckets = stats.daily_buckets(at(2026, 10, 1, 12), counts)
    assert buckets[0] == {"date": "2026-10-01", "reposts": 1, "likes": 3, "comments": 0}
    assert buckets[13] == {"date": "2026-10-14", "reposts": 0, "likes": 0, "comments": 2}


def test_a_day_outside_the_window_is_ignored():
    counts = {("likes", date(2026, 10, 15)): 9, ("likes", date(2026, 9, 30)): 9}
    buckets = stats.daily_buckets(at(2026, 10, 1, 12), counts)
    assert sum(b["likes"] for b in buckets) == 0


def test_a_pipeline_label_reports_the_check_time():
    checked = at(2026, 10, 1, 12, 0, 7)
    p = post(
        status=PostStatus.VERIFIED_TRUE,
        verdict_source=VerdictSource.PIPELINE,
        pipeline_checked_at=checked,
        confidence_score=Decimal("95.00"),
    )
    assert stats.verdict_at(p) == checked
    assert stats.seconds_to_verdict(p, checked) == 7


def test_a_moderator_label_reports_the_audit_row_time():
    decided = at(2026, 10, 2, 9)
    p = post(
        status=PostStatus.VERIFIED_FALSE,
        verdict_source=VerdictSource.MODERATOR,
        pipeline_checked_at=at(2026, 10, 1, 13),  # an earlier pipeline try must not be used
        moderator_verdict_at=decided,
    )
    assert stats.verdict_at(p) == decided


def test_a_moderator_label_without_an_audit_row_has_no_time():
    p = post(status=PostStatus.VERIFIED_TRUE, verdict_source=VerdictSource.MODERATOR)
    assert stats.verdict_at(p) is None
    assert stats.seconds_to_verdict(p, None) is None


@pytest.mark.parametrize(
    "status", [PostStatus.PENDING, PostStatus.PUBLISHED, PostStatus.UNDER_REVIEW]
)
def test_an_unlabelled_post_has_no_verdict_time(status):
    p = post(
        status=status,
        verdict_source=VerdictSource.PIPELINE,
        pipeline_checked_at=at(2026, 10, 1, 13),
    )
    assert stats.verdict_at(p) is None


def test_seconds_never_go_negative():
    p = post(created_at=at(2026, 10, 1, 12))
    assert stats.seconds_to_verdict(p, at(2026, 10, 1, 11)) == 0
    assert stats.seconds_to_verdict(p, at(2026, 10, 1, 12, 2, 14)) == 134


def labelled(**fields):
    return post(
        status=PostStatus.VERIFIED_TRUE,
        verdict_source=VerdictSource.PIPELINE,
        pipeline_checked_at=at(2026, 10, 1, 12, 0, 1),
        confidence_score=Decimal("95.00"),
        **fields,
    )


def test_the_payload_has_six_keys_and_the_threshold_travels_with_the_confidence():
    data = stats.stats_data(labelled(), {}, 85)
    assert set(data) == {
        "confidence_score",
        "confidence_threshold",
        "verdict_source",
        "seconds_to_verdict",
        "verdict_at",
        "daily",
    }
    assert data["confidence_score"] == "95.00"
    assert data["confidence_threshold"] == 85
    assert data["verdict_at"] == "2026-10-01T12:00:01Z"
    assert data["seconds_to_verdict"] == 1


def test_a_moderator_label_has_no_confidence_and_no_threshold():
    p = post(
        status=PostStatus.VERIFIED_TRUE,
        verdict_source=VerdictSource.MODERATOR,
        confidence_score=Decimal("95.00"),  # a leftover from an earlier pipeline try
        moderator_verdict_at=at(2026, 10, 1, 13),
    )
    data = stats.stats_data(p, {}, 85)
    assert data["confidence_score"] is None
    assert data["confidence_threshold"] is None
    assert data["verdict_source"] == "moderator"
    assert data["seconds_to_verdict"] == 3600


def test_a_late_true_held_under_review_stays_private():
    p = post(
        status=PostStatus.UNDER_REVIEW,
        verdict_source=VerdictSource.PIPELINE,
        confidence_score=Decimal("95.00"),
        pipeline_checked_at=at(2026, 10, 1, 12, 5),
    )
    data = stats.stats_data(p, {}, 85)
    assert [data[k] for k in ("confidence_score", "confidence_threshold", "verdict_source")] == [
        None,
        None,
        None,
    ]
    assert data["seconds_to_verdict"] is None and data["verdict_at"] is None
