"""The pure routing functions of ARCHITECTURE §4 (Part 8's half, and Part 11C's emergency report
threshold): no database, no clock."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from apps.pipeline.routing import (
    MAX_ATTEMPTS,
    apply_report_threshold,
    enter_review,
    merge_flag,
    pipeline_had_its_say,
)
from apps.posts.models import FlaggedReason as Flag
from apps.posts.models import PostStatus as Status

NOW = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)
CFG = SimpleNamespace(report_threshold=5, emergency_report_threshold=2)


def post(status, flagged_reason=None, pre_review_status=None, review_started_at=None, **emergency):
    """A post in memory; not an emergency unless `emergency` says so (Part 11C's fields)."""
    return SimpleNamespace(
        status=status,
        flagged_reason=flagged_reason,
        pre_review_status=pre_review_status,
        review_started_at=review_started_at,
        is_emergency=emergency.get("is_emergency", False),
        emergency_expires_at=emergency.get("emergency_expires_at"),
        emergency_demoted_at=emergency.get("emergency_demoted_at"),
        deleted_at=emergency.get("deleted_at"),
    )


def emergency(status, *, expires_in=timedelta(hours=1), demoted=False, **fields):
    """An emergency that expires `expires_in` after NOW (negative: already expired)."""
    return post(
        status,
        is_emergency=True,
        emergency_expires_at=NOW + expires_in,
        emergency_demoted_at=NOW - timedelta(minutes=5) if demoted else None,
        **fields,
    )


# ---------- merge_flag ----------


@pytest.mark.parametrize(
    ("existing", "new", "expected"),
    [
        (None, Flag.PIPELINE, Flag.PIPELINE),
        (None, Flag.REPORTS, Flag.REPORTS),
        (None, Flag.APPEAL, Flag.APPEAL),
        (Flag.PIPELINE, Flag.PIPELINE, Flag.PIPELINE),
        (Flag.REPORTS, Flag.REPORTS, Flag.REPORTS),
        (Flag.APPEAL, Flag.APPEAL, Flag.APPEAL),
        (Flag.PIPELINE, Flag.REPORTS, Flag.BOTH),
        (Flag.REPORTS, Flag.PIPELINE, Flag.BOTH),
        (Flag.BOTH, Flag.PIPELINE, Flag.BOTH),
        (Flag.BOTH, Flag.REPORTS, Flag.BOTH),
        (Flag.APPEAL, Flag.PIPELINE, Flag.APPEAL),
        (Flag.APPEAL, Flag.REPORTS, Flag.APPEAL),
    ],
)
def test_merge_flag_table(existing, new, expected):
    assert merge_flag(existing, new) == expected


@pytest.mark.parametrize("existing", [Flag.PIPELINE, Flag.REPORTS, Flag.BOTH])
def test_a_post_under_review_for_the_pipeline_or_reports_can_not_get_an_appeal(existing):
    with pytest.raises(ValueError, match="appeal"):
        merge_flag(existing, Flag.APPEAL)


@pytest.mark.parametrize("new", [None, "", "nonsense", Flag.BOTH])
def test_merge_flag_refuses_something_that_is_not_a_reason_to_flag(new):
    with pytest.raises(ValueError, match="reason to flag"):
        merge_flag(Flag.PIPELINE, new)
    with pytest.raises(ValueError, match="reason to flag"):
        merge_flag(None, new)


def test_merge_flag_refuses_an_unknown_existing_value():
    with pytest.raises(ValueError, match="flagged reason"):
        merge_flag("nonsense", Flag.REPORTS)


# ---------- enter_review ----------


@pytest.mark.parametrize(
    "status",
    [Status.PENDING, Status.PUBLISHED, Status.VERIFIED_TRUE, Status.VERIFIED_FALSE],
)
def test_entering_review_remembers_the_old_status(status):
    target = post(status)
    enter_review(target, Flag.REPORTS, NOW)
    assert target.status == Status.UNDER_REVIEW
    assert target.pre_review_status == status
    assert target.flagged_reason == Flag.REPORTS
    assert target.review_started_at == NOW  # the queue's clock starts


@pytest.mark.parametrize(
    ("flag", "expected"),
    [
        (Flag.PIPELINE, Flag.BOTH),
        (Flag.REPORTS, Flag.REPORTS),
        (Flag.BOTH, Flag.BOTH),
        (Flag.APPEAL, Flag.APPEAL),
        (None, Flag.REPORTS),
    ],
)
def test_entering_review_again_only_merges_the_reason(flag, expected):
    started = NOW - timedelta(hours=3)
    target = post(
        Status.UNDER_REVIEW,
        flagged_reason=flag,
        pre_review_status=Status.PENDING,
        review_started_at=started,
    )
    enter_review(target, Flag.REPORTS, NOW)
    assert target.status == Status.UNDER_REVIEW
    assert target.pre_review_status == Status.PENDING  # the status it came from is kept
    assert target.flagged_reason == expected
    assert target.review_started_at == started  # a merge never restarts the wait


def test_entering_review_for_the_pipeline_on_a_fresh_post():
    target = post(Status.PENDING)
    enter_review(target, Flag.PIPELINE, NOW)
    assert (target.status, target.flagged_reason) == (Status.UNDER_REVIEW, Flag.PIPELINE)
    assert target.pre_review_status == Status.PENDING
    assert target.review_started_at == NOW


# ---------- apply_report_threshold ----------


@pytest.mark.parametrize("count", [0, 1, 4])
def test_below_the_threshold_nothing_changes(count):
    target = post(Status.PUBLISHED)
    assert apply_report_threshold(target, count, CFG, NOW) is False
    assert (target.status, target.flagged_reason, target.pre_review_status) == (
        Status.PUBLISHED,
        None,
        None,
    )


@pytest.mark.parametrize("count", [5, 6, 50])
def test_at_or_above_the_threshold_the_post_enters_review(count):
    target = post(Status.VERIFIED_TRUE)
    assert apply_report_threshold(target, count, CFG, NOW) is True
    assert target.status == Status.UNDER_REVIEW
    assert target.flagged_reason == Flag.REPORTS
    assert target.pre_review_status == Status.VERIFIED_TRUE
    assert target.review_started_at == NOW


def test_the_threshold_is_read_from_the_settings():
    low = SimpleNamespace(report_threshold=1)
    assert apply_report_threshold(post(Status.PENDING), 1, low, NOW) is True
    high = SimpleNamespace(report_threshold=9)
    assert apply_report_threshold(post(Status.PENDING), 8, high, NOW) is False
    assert apply_report_threshold(post(Status.PENDING), 9, high, NOW) is True


@pytest.mark.parametrize("count", [0, 5, 50])
def test_a_removed_post_is_never_touched(count):
    target = post(Status.REMOVED)
    assert apply_report_threshold(target, count, CFG, NOW) is False
    assert (target.status, target.flagged_reason, target.pre_review_status) == (
        Status.REMOVED,
        None,
        None,
    )


@pytest.mark.parametrize(
    ("flag", "expected"),
    [
        (Flag.REPORTS, Flag.REPORTS),
        (Flag.PIPELINE, Flag.BOTH),
        (Flag.BOTH, Flag.BOTH),
        (Flag.APPEAL, Flag.APPEAL),
    ],
)
def test_a_post_already_under_review_only_merges_and_does_not_count_as_entering(flag, expected):
    target = post(Status.UNDER_REVIEW, flagged_reason=flag, pre_review_status=Status.VERIFIED_FALSE)
    assert apply_report_threshold(target, 5, CFG, NOW) is False
    assert target.status == Status.UNDER_REVIEW
    assert target.flagged_reason == expected
    assert target.pre_review_status == Status.VERIFIED_FALSE


def test_the_normal_threshold_applies_to_a_post_that_is_not_an_emergency():
    cfg = SimpleNamespace(report_threshold=5, emergency_report_threshold=1)
    assert apply_report_threshold(post(Status.PENDING), 4, cfg, NOW) is False


# ---------- Part 11C: the emergency report threshold (§4, §4b) ----------


@pytest.mark.parametrize(
    "status", [Status.PENDING, Status.VERIFIED_TRUE, Status.VERIFIED_FALSE, Status.PUBLISHED]
)
def test_two_counting_reports_send_an_active_emergency_to_review(status):
    target = emergency(status)
    assert apply_report_threshold(target, 1, CFG, NOW) is False
    assert target.status == status
    assert apply_report_threshold(target, 2, CFG, NOW) is True
    assert (target.status, target.flagged_reason) == (Status.UNDER_REVIEW, Flag.REPORTS)
    assert target.pre_review_status == status
    assert target.review_started_at == NOW


@pytest.mark.parametrize(
    "target",
    [
        emergency(Status.PENDING, expires_in=-timedelta(minutes=1)),
        emergency(Status.PENDING, expires_in=timedelta(0)),  # expires this very instant
        emergency(Status.PENDING, demoted=True),
        emergency(Status.PENDING, deleted_at=NOW - timedelta(minutes=1)),
    ],
    ids=["expired", "expires_now", "demoted", "deleted"],
)
def test_an_emergency_that_is_no_longer_active_needs_the_usual_five(target):
    assert apply_report_threshold(target, 4, CFG, NOW) is False
    assert target.status == Status.PENDING
    assert apply_report_threshold(target, 5, CFG, NOW) is True


def test_the_threshold_follows_the_clock_it_is_given():
    """23 h 59 min into a 24 h emergency two reports are enough; at 24 h 01 min they are not."""
    created = NOW - timedelta(hours=24)
    expires = created + timedelta(hours=24)
    early = emergency(Status.PENDING, expires_in=expires - NOW)
    at_23_59 = created + timedelta(hours=23, minutes=59)
    assert apply_report_threshold(early, 2, CFG, at_23_59) is True
    late = emergency(Status.PENDING, expires_in=expires - NOW)
    at_24_01 = created + timedelta(hours=24, minutes=1)
    assert apply_report_threshold(late, 2, CFG, at_24_01) is False


@pytest.mark.parametrize("count", [2, 50])
def test_a_removed_emergency_is_never_touched(count):
    target = emergency(Status.REMOVED)
    assert apply_report_threshold(target, count, CFG, NOW) is False
    assert target.status == Status.REMOVED


def test_an_active_emergency_already_under_review_only_merges_the_reason():
    target = emergency(
        Status.UNDER_REVIEW,
        flagged_reason=Flag.PIPELINE,
        pre_review_status=Status.PENDING,
        review_started_at=NOW - timedelta(hours=1),
    )
    assert apply_report_threshold(target, 2, CFG, NOW) is False
    assert target.flagged_reason == Flag.BOTH
    assert target.review_started_at == NOW - timedelta(hours=1)


def test_the_emergency_threshold_is_read_from_the_settings():
    cfg = SimpleNamespace(report_threshold=5, emergency_report_threshold=3)
    assert apply_report_threshold(emergency(Status.PENDING), 2, cfg, NOW) is False
    assert apply_report_threshold(emergency(Status.PENDING), 3, cfg, NOW) is True


# ---------- pipeline_had_its_say (Part 11: a restored post isn't checked twice) ----------


@pytest.mark.parametrize(
    ("checked_at", "attempts", "said"),
    [
        (None, 0, False),
        (None, 1, False),
        (None, MAX_ATTEMPTS - 1, False),
        (None, MAX_ATTEMPTS, True),  # gave up: a moderator was handed the post
        (None, MAX_ATTEMPTS + 2, True),
        (NOW, 0, True),  # it answered
        (NOW, 1, True),
    ],
)
def test_the_pipeline_had_its_say_when_it_answered_or_used_up_its_tries(checked_at, attempts, said):
    checked = SimpleNamespace(pipeline_checked_at=checked_at, pipeline_attempts=attempts)
    assert pipeline_had_its_say(checked) is said
