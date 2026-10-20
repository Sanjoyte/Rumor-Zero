"""The pipeline half of the §4 routing table (pure: no database, no clock). One test per row that
concerns a pipeline result or failure, plus the rows where it must change nothing. Part 11C adds
the emergency rows: a FALSE on an active emergency is never applied automatically."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest

from apps.pipeline.clients import PipelineError
from apps.pipeline.contract import PipelineResult
from apps.pipeline.routing import (
    MAX_ATTEMPTS,
    Outcome,
    apply_pipeline_failure,
    apply_pipeline_result,
    backoff,
    is_awaiting_check,
)
from apps.posts.models import FlaggedReason as Flag
from apps.posts.models import PostStatus as Status
from apps.posts.models import PostType

NOW = datetime(2026, 10, 11, 9, 0, tzinfo=UTC)
LEASE_END = NOW + timedelta(minutes=5)
CFG = SimpleNamespace(confidence_threshold=85)


def post(status=Status.PENDING, **fields):
    """A fact in memory with every field the routing reads or writes."""
    values = {
        "post_type": PostType.FACT,
        "status": status,
        "deleted_at": None,
        "verdict_source": None,
        "flagged_reason": None,
        "pre_review_status": None,
        "pipeline_verdict": None,
        "confidence_score": None,
        "pipeline_result": None,
        "pipeline_checked_at": None,
        "pipeline_next_attempt_at": LEASE_END,  # claimed: the lease is running
        "pipeline_attempts": 1,
        "is_emergency": False,
        "emergency_expires_at": None,
        "emergency_demoted_at": None,
        **fields,
    }
    return SimpleNamespace(**values)


def emergency(status=Status.PENDING, *, expires_in=timedelta(hours=20), demoted=False, **fields):
    """An emergency fact, active unless it has expired (`expires_in` ≤ 0) or was demoted."""
    return post(
        status,
        is_emergency=True,
        emergency_expires_at=NOW + expires_in,
        emergency_demoted_at=NOW - timedelta(hours=1) if demoted else None,
        **fields,
    )


def reported(**fields):
    """Under review for reports before the pipeline answered (pre_review_status=pending)."""
    return post(
        Status.UNDER_REVIEW,
        **{"flagged_reason": Flag.REPORTS, "pre_review_status": Status.PENDING, **fields},
    )


def result(verdict, confidence, raw=None):
    return PipelineResult(verdict, Decimal(str(confidence)), raw or {"stub": True})


# ---------- pending ----------


@pytest.mark.parametrize(
    ("verdict", "label"), [("true", Status.VERIFIED_TRUE), ("false", Status.VERIFIED_FALSE)]
)
def test_a_decisive_result_labels_a_pending_post(verdict, label):
    p = post()
    assert (
        apply_pipeline_result(p, result(verdict, 95, {"rule": "x"}), CFG, NOW) == Outcome.LABELLED
    )
    assert p.status == label
    assert p.verdict_source == "pipeline"
    assert p.pipeline_verdict == verdict
    assert p.confidence_score == Decimal("95.00")
    assert p.pipeline_result == {"rule": "x"}
    assert p.pipeline_checked_at == NOW
    assert p.pipeline_next_attempt_at is None
    assert p.flagged_reason is None
    assert p.pre_review_status is None


def test_a_confidence_exactly_at_the_threshold_is_decisive_and_a_hundredth_below_is_not():
    at = post()
    assert apply_pipeline_result(at, result("true", "85.00"), CFG, NOW) == Outcome.LABELLED
    below = post()
    assert apply_pipeline_result(below, result("true", "84.99"), CFG, NOW) == Outcome.ENTERED_REVIEW
    assert below.status == Status.UNDER_REVIEW


@pytest.mark.parametrize(
    ("verdict", "confidence"),
    [("inconclusive", 99), ("inconclusive", 40), ("true", 60), ("false", 84)],
    ids=["inconclusive-high", "inconclusive-low", "true-low", "false-low"],
)
def test_an_undecided_result_sends_a_pending_post_to_review_for_the_pipeline(verdict, confidence):
    p = post()
    assert apply_pipeline_result(p, result(verdict, confidence), CFG, NOW) == Outcome.ENTERED_REVIEW
    assert p.status == Status.UNDER_REVIEW
    assert p.flagged_reason == Flag.PIPELINE
    assert p.pre_review_status == Status.PENDING
    assert p.verdict_source is None  # nothing decided: no source, so no % is ever shown
    assert p.pipeline_verdict == verdict
    assert p.confidence_score == Decimal(confidence)
    assert p.pipeline_checked_at == NOW
    assert p.pipeline_next_attempt_at is None


@pytest.mark.parametrize(
    ("threshold", "confidence", "decisive"),
    [(0, 50, True), (100, "99.99", False), (100, 100, True)],
)
def test_the_threshold_comes_from_the_settings(threshold, confidence, decisive):
    p = post()
    outcome = apply_pipeline_result(
        p, result("false", confidence), SimpleNamespace(confidence_threshold=threshold), NOW
    )
    assert outcome == (Outcome.LABELLED if decisive else Outcome.ENTERED_REVIEW)


# ---------- Part 11C: emergencies (§4, §4b) ----------


def test_a_decisive_false_on_a_pending_active_emergency_goes_to_a_moderator_never_false():
    p = emergency()
    assert apply_pipeline_result(p, result("false", 92), CFG, NOW) == Outcome.ENTERED_REVIEW
    assert (p.status, p.flagged_reason, p.pre_review_status) == (
        Status.UNDER_REVIEW,
        Flag.PIPELINE,
        Status.PENDING,
    )
    assert p.review_started_at == NOW
    assert p.verdict_source is None  # no label, so no % and no FALSE anywhere
    assert p.emergency_demoted_at is None  # the priority is kept
    # The answer is stored for the moderator.
    assert (p.pipeline_verdict, p.confidence_score) == ("false", Decimal("92.00"))
    assert p.pipeline_checked_at == NOW


def test_a_decisive_true_on_an_active_emergency_labels_it_and_it_stays_pinned():
    p = emergency()
    assert apply_pipeline_result(p, result("true", 95), CFG, NOW) == Outcome.LABELLED
    assert (p.status, p.verdict_source) == (Status.VERIFIED_TRUE, "pipeline")
    assert p.emergency_demoted_at is None


@pytest.mark.parametrize(
    ("verdict", "confidence"), [("inconclusive", 99), ("true", 60), ("false", 84)]
)
def test_an_undecided_result_on_an_active_emergency_sends_it_to_review(verdict, confidence):
    p = emergency()
    assert apply_pipeline_result(p, result(verdict, confidence), CFG, NOW) == (
        Outcome.ENTERED_REVIEW
    )
    assert (p.status, p.flagged_reason) == (Status.UNDER_REVIEW, Flag.PIPELINE)
    assert p.emergency_demoted_at is None


@pytest.mark.parametrize(
    "make",
    [
        lambda: emergency(expires_in=-timedelta(seconds=1)),
        lambda: emergency(expires_in=timedelta(0)),  # expires this very instant
        lambda: emergency(demoted=True),
    ],
    ids=["expired", "expires_now", "demoted"],
)
def test_a_false_after_expiry_or_demotion_is_applied_normally(make):
    p = make()
    assert apply_pipeline_result(p, result("false", 92), CFG, NOW) == Outcome.LABELLED
    assert (p.status, p.verdict_source) == (Status.VERIFIED_FALSE, "pipeline")


def test_the_emergency_rule_follows_the_clock_it_is_given():
    """Pinned at 23 h 59 min, not at 24 h 01 min: the same post, two clocks."""
    created = NOW - timedelta(hours=2)
    expires = created + timedelta(hours=24)
    at_23_59 = created + timedelta(hours=23, minutes=59)
    at_24_01 = created + timedelta(hours=24, minutes=1)
    early = emergency(expires_in=expires - NOW)
    assert apply_pipeline_result(early, result("false", 92), CFG, at_23_59) == (
        Outcome.ENTERED_REVIEW
    )
    late = emergency(expires_in=expires - NOW)
    assert apply_pipeline_result(late, result("false", 92), CFG, at_24_01) == Outcome.LABELLED


def test_a_late_false_on_an_active_emergency_under_review_for_reports_makes_the_reason_both():
    """§4's row: the same as for every post since Part 9 (no hidden FALSE is stored), checked
    explicitly for an active emergency."""
    p = emergency(
        Status.UNDER_REVIEW,
        flagged_reason=Flag.REPORTS,
        pre_review_status=Status.PENDING,
        review_started_at=NOW - timedelta(hours=1),
    )
    assert apply_pipeline_result(p, result("false", 92), CFG, NOW) == Outcome.UPDATED_REVIEW
    assert (p.status, p.flagged_reason, p.pre_review_status) == (
        Status.UNDER_REVIEW,
        Flag.BOTH,
        Status.PENDING,
    )
    assert p.verdict_source is None
    assert p.emergency_demoted_at is None


# ---------- under review for reports, result arrives late ----------


def test_a_late_decisive_true_on_a_reported_post_is_kept_for_when_the_reports_are_dismissed():
    p = reported()
    assert apply_pipeline_result(p, result("true", 95), CFG, NOW) == Outcome.UPDATED_REVIEW
    assert p.status == Status.UNDER_REVIEW
    assert p.flagged_reason == Flag.REPORTS
    assert p.pre_review_status == Status.VERIFIED_TRUE
    assert p.verdict_source == "pipeline"
    assert p.confidence_score == Decimal("95.00")
    assert p.pipeline_checked_at == NOW


def test_a_late_decisive_false_on_a_reported_post_goes_to_a_moderator_and_stores_no_label():
    """User decision 2026-10-11: no hidden FALSE is kept, so nothing (the repost refusal) can
    reveal it, and dismissing the reports can't make the post FALSE without a human."""
    p = reported()
    assert apply_pipeline_result(p, result("false", 92), CFG, NOW) == Outcome.UPDATED_REVIEW
    assert p.status == Status.UNDER_REVIEW
    assert p.flagged_reason == Flag.BOTH
    assert p.pre_review_status == Status.PENDING
    assert p.verdict_source is None
    # The answer is still stored for the moderator.
    assert (p.pipeline_verdict, p.confidence_score) == ("false", Decimal("92.00"))


@pytest.mark.parametrize(
    ("verdict", "confidence"), [("inconclusive", 99), ("true", 60), ("false", 10)]
)
def test_a_late_weak_result_on_a_reported_post_makes_the_reason_both(verdict, confidence):
    p = reported()
    assert apply_pipeline_result(p, result(verdict, confidence), CFG, NOW) == Outcome.UPDATED_REVIEW
    assert (p.status, p.flagged_reason, p.pre_review_status) == (
        Status.UNDER_REVIEW,
        Flag.BOTH,
        Status.PENDING,
    )
    assert p.verdict_source is None


# ---------- posts the pipeline must not touch ----------

NOT_WAITING = {
    "removed": lambda: post(Status.REMOVED),
    "moderator verdict": lambda: post(Status.VERIFIED_TRUE, verdict_source="moderator"),
    "pipeline verdict": lambda: post(
        Status.VERIFIED_FALSE, verdict_source="pipeline", confidence_score=Decimal("92.00")
    ),
    "opinion": lambda: post(post_type=PostType.OPINION, status=Status.PUBLISHED),
    "reported opinion": lambda: post(
        Status.UNDER_REVIEW,
        post_type=PostType.OPINION,
        flagged_reason=Flag.REPORTS,
        pre_review_status=Status.PUBLISHED,
    ),
    "deleted": lambda: post(deleted_at=NOW),
    "under review for the pipeline": lambda: post(
        Status.UNDER_REVIEW, flagged_reason=Flag.PIPELINE, pre_review_status=Status.PENDING
    ),
    "under review for both": lambda: post(
        Status.UNDER_REVIEW, flagged_reason=Flag.BOTH, pre_review_status=Status.PENDING
    ),
    "late true already stored": lambda: reported(
        pre_review_status=Status.VERIFIED_TRUE, verdict_source="pipeline"
    ),
    "appeal": lambda: post(
        Status.UNDER_REVIEW,
        flagged_reason=Flag.APPEAL,
        pre_review_status=Status.VERIFIED_FALSE,
        verdict_source="pipeline",
    ),
    "reported after a verdict": lambda: reported(
        pre_review_status=Status.VERIFIED_TRUE, verdict_source="moderator"
    ),
}


@pytest.mark.parametrize("make", NOT_WAITING.values(), ids=NOT_WAITING.keys())
def test_a_result_for_a_post_not_waiting_for_a_check_changes_nothing(make):
    p = make()
    before = dict(vars(p))
    assert not is_awaiting_check(p)
    assert apply_pipeline_result(p, result("false", 99), CFG, NOW) == Outcome.IGNORED
    assert vars(p) == before


@pytest.mark.parametrize("make", NOT_WAITING.values(), ids=NOT_WAITING.keys())
def test_a_failure_for_a_post_not_waiting_for_a_check_changes_nothing(make):
    p = make()
    before = dict(vars(p))
    assert apply_pipeline_failure(p, PipelineError("timeout", "slow"), NOW) == Outcome.IGNORED
    assert vars(p) == before


def test_a_second_result_is_ignored_so_a_label_never_shows_another_runs_confidence():
    p = post()
    apply_pipeline_result(p, result("true", 95), CFG, NOW)
    labelled = dict(vars(p))
    assert (
        apply_pipeline_result(p, result("false", 99), CFG, NOW + timedelta(minutes=9))
        == Outcome.IGNORED
    )
    assert vars(p) == labelled


def test_routing_the_same_undecided_result_twice_changes_nothing_the_second_time():
    p = post()
    apply_pipeline_result(p, result("inconclusive", 40), CFG, NOW)
    once = dict(vars(p))
    assert apply_pipeline_result(p, result("inconclusive", 40), CFG, NOW) == Outcome.IGNORED
    assert vars(p) == once


# ---------- failures ----------


@pytest.mark.parametrize(("attempts", "minutes"), [(1, 2), (2, 4), (3, 8), (4, 16)])
def test_a_failed_try_is_retried_after_the_backoff(attempts, minutes):
    p = post(pipeline_attempts=attempts)
    assert apply_pipeline_failure(p, PipelineError("http_status", "HTTP 503"), NOW) == Outcome.RETRY
    assert p.status == Status.PENDING
    assert p.pipeline_next_attempt_at == NOW + timedelta(minutes=minutes)
    assert p.pipeline_result == {"error": "http_status", "detail": "HTTP 503", "attempt": attempts}
    assert p.pipeline_checked_at is None
    assert p.verdict_source is None


def test_after_five_tries_a_pending_post_goes_to_review_with_the_error_kept():
    p = post(pipeline_attempts=MAX_ATTEMPTS)
    assert (
        apply_pipeline_failure(p, PipelineError("timeout", "no answer in time"), NOW)
        == Outcome.ENTERED_REVIEW
    )
    assert (p.status, p.flagged_reason, p.pre_review_status) == (
        Status.UNDER_REVIEW,
        Flag.PIPELINE,
        Status.PENDING,
    )
    assert p.pipeline_next_attempt_at is None
    assert p.pipeline_result == {"error": "timeout", "detail": "no answer in time", "attempt": 5}
    assert p.pipeline_checked_at is None  # the pipeline never answered


def test_after_five_tries_a_reported_post_gets_the_reason_both():
    p = reported(pipeline_attempts=MAX_ATTEMPTS)
    assert (
        apply_pipeline_failure(p, PipelineError("network", "URLError"), NOW)
        == Outcome.UPDATED_REVIEW
    )
    assert (p.status, p.flagged_reason, p.pre_review_status) == (
        Status.UNDER_REVIEW,
        Flag.BOTH,
        Status.PENDING,
    )
    assert p.pipeline_next_attempt_at is None


def test_a_reported_post_that_fails_below_the_limit_waits_like_any_other():
    p = reported(pipeline_attempts=2)
    assert apply_pipeline_failure(p, PipelineError("timeout"), NOW) == Outcome.RETRY
    assert p.flagged_reason == Flag.REPORTS
    assert p.pipeline_next_attempt_at == NOW + timedelta(minutes=4)


@pytest.mark.parametrize(
    ("attempts", "minutes"), [(0, 1), (1, 2), (4, 16), (5, 32), (6, 60), (7, 60), (1000, 60)]
)
def test_backoff_doubles_and_is_capped_at_an_hour(attempts, minutes):
    assert backoff(attempts) == timedelta(minutes=minutes)


def test_each_failed_try_replaces_the_error_kept_from_the_one_before():
    p = post(
        pipeline_attempts=2,
        pipeline_result={"error": "timeout", "detail": "no answer in time", "attempt": 1},
    )
    apply_pipeline_failure(p, PipelineError("http_status", "HTTP 502"), NOW)
    assert p.pipeline_result == {"error": "http_status", "detail": "HTTP 502", "attempt": 2}
