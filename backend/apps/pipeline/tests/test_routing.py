"""The pure routing functions of ARCHITECTURE §4 (Part 8's half): no database, no clock."""

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from apps.pipeline.routing import apply_report_threshold, enter_review, merge_flag
from apps.posts.models import FlaggedReason as Flag
from apps.posts.models import PostStatus as Status

NOW = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)
CFG = SimpleNamespace(report_threshold=5, emergency_report_threshold=2)


def post(status, flagged_reason=None, pre_review_status=None):
    return SimpleNamespace(
        status=status, flagged_reason=flagged_reason, pre_review_status=pre_review_status
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
    enter_review(target, Flag.REPORTS)
    assert target.status == Status.UNDER_REVIEW
    assert target.pre_review_status == status
    assert target.flagged_reason == Flag.REPORTS


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
    target = post(Status.UNDER_REVIEW, flagged_reason=flag, pre_review_status=Status.PENDING)
    enter_review(target, Flag.REPORTS)
    assert target.status == Status.UNDER_REVIEW
    assert target.pre_review_status == Status.PENDING  # the status it came from is kept
    assert target.flagged_reason == expected


def test_entering_review_for_the_pipeline_on_a_fresh_post():
    target = post(Status.PENDING)
    enter_review(target, Flag.PIPELINE)
    assert (target.status, target.flagged_reason) == (Status.UNDER_REVIEW, Flag.PIPELINE)
    assert target.pre_review_status == Status.PENDING


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


def test_the_normal_threshold_applies_whatever_the_emergency_one_is():
    """Part 11C adds the emergency branch; until then only `report_threshold` is read."""
    cfg = SimpleNamespace(report_threshold=5, emergency_report_threshold=1)
    assert apply_report_threshold(post(Status.PENDING), 4, cfg, NOW) is False
