"""The two pipeline writes in `posts.services` (ARCHITECTURE §4, §6): the claim token, the lock,
and "nothing is written" for a post whose check is over."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.db import connection, transaction
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.pipeline.clients import PipelineError
from apps.pipeline.contract import PipelineResult
from apps.pipeline.routing import MAX_ATTEMPTS, Outcome
from apps.pipeline.tests.conftest import fact, pipeline_cfg  # noqa: F401  (fixture)
from apps.posts import services
from apps.posts.models import FlaggedReason, Post, PostStatus

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("pipeline_cfg")]

TRUE_95 = PipelineResult("true", Decimal("95"), {"stub": True, "rule": "#true"})


def claimed(post, attempts=1):
    """As if the processor had claimed `post` for its `attempts`-th try (lease running)."""
    Post.objects.filter(pk=post.pk).update(
        pipeline_attempts=attempts,
        pipeline_next_attempt_at=timezone.now() + timedelta(minutes=5),
    )
    return Post.objects.get(pk=post.pk)


def test_a_result_for_the_current_claim_labels_the_post_and_moves_updated_at():
    post = claimed(fact())
    now = timezone.now()
    outcome = services.record_pipeline_result(post.pk, TRUE_95, claimed_attempts=1, now=now)
    assert outcome == Outcome.LABELLED
    after = Post.objects.get(pk=post.pk)
    assert after.status == PostStatus.VERIFIED_TRUE
    assert after.verdict_source == "pipeline"
    assert after.pipeline_verdict == "true"
    assert after.confidence_score == Decimal("95.00")
    assert after.pipeline_result == {"stub": True, "rule": "#true"}
    assert after.pipeline_checked_at == now
    assert after.pipeline_next_attempt_at is None
    assert after.updated_at > post.updated_at


def test_the_threshold_comes_from_the_platform_settings(pipeline_cfg):  # noqa: F811
    pipeline_cfg(confidence_threshold=96)
    post = claimed(fact())
    outcome = services.record_pipeline_result(
        post.pk, TRUE_95, claimed_attempts=1, now=timezone.now()
    )
    assert outcome == Outcome.ENTERED_REVIEW
    assert Post.objects.get(pk=post.pk).flagged_reason == FlaggedReason.PIPELINE


@pytest.mark.parametrize("token", [0, 2])
def test_an_answer_for_an_older_or_unknown_claim_is_dropped(token):
    post = claimed(fact())
    before = Post.objects.get(pk=post.pk)
    assert (
        services.record_pipeline_result(
            post.pk, TRUE_95, claimed_attempts=token, now=timezone.now()
        )
        is None
    )
    failure = PipelineError("timeout")
    assert (
        services.record_pipeline_failure(
            post.pk, failure, claimed_attempts=token, now=timezone.now()
        )
        is None
    )
    after = Post.objects.get(pk=post.pk)
    assert after.status == PostStatus.PENDING
    assert after.pipeline_next_attempt_at == before.pipeline_next_attempt_at  # the lease stays
    assert after.updated_at == before.updated_at


def test_an_answer_for_a_post_the_author_deleted_meanwhile_is_dropped():
    post = claimed(fact())
    services.delete_post(post_id=post.pk, user=post.author)
    assert (
        services.record_pipeline_result(post.pk, TRUE_95, claimed_attempts=1, now=timezone.now())
        is None
    )
    after = Post.objects.get(pk=post.pk)
    assert after.status == PostStatus.PENDING
    assert after.verdict_source is None
    assert after.pipeline_checked_at is None


@pytest.mark.parametrize(
    "change",
    [
        {"status": PostStatus.REMOVED},
        {"status": PostStatus.VERIFIED_FALSE, "verdict_source": "moderator"},
    ],
    ids=["removed", "moderator"],
)
def test_an_answer_for_a_post_removed_or_decided_meanwhile_writes_nothing(change):
    post = claimed(fact())
    Post.objects.filter(pk=post.pk).update(**change)
    before = Post.objects.get(pk=post.pk)
    outcome = services.record_pipeline_result(
        post.pk, TRUE_95, claimed_attempts=1, now=timezone.now()
    )
    assert outcome == Outcome.IGNORED
    after = Post.objects.get(pk=post.pk)
    for field in ("status", "verdict_source", "pipeline_verdict", "confidence_score"):
        assert getattr(after, field) == getattr(before, field), field
    assert after.updated_at == before.updated_at
    assert after.pipeline_next_attempt_at == before.pipeline_next_attempt_at


def test_a_second_answer_for_a_labelled_post_changes_no_field_and_not_updated_at():
    post = claimed(fact())
    services.record_pipeline_result(post.pk, TRUE_95, claimed_attempts=1, now=timezone.now())
    labelled = Post.objects.get(pk=post.pk)
    false_99 = PipelineResult("false", Decimal("99"), {"other": "run"})
    outcome = services.record_pipeline_result(
        post.pk, false_99, claimed_attempts=1, now=timezone.now()
    )
    assert outcome == Outcome.IGNORED
    after = Post.objects.get(pk=post.pk)
    assert {f.name: getattr(after, f.name) for f in Post._meta.fields} == {
        f.name: getattr(labelled, f.name) for f in Post._meta.fields
    }


def test_a_failed_try_below_the_limit_waits_for_the_backoff():
    post = claimed(fact(), attempts=3)
    now = timezone.now()
    outcome = services.record_pipeline_failure(
        post.pk, PipelineError("http_status", "HTTP 503"), claimed_attempts=3, now=now
    )
    assert outcome == Outcome.RETRY
    after = Post.objects.get(pk=post.pk)
    assert after.status == PostStatus.PENDING
    assert after.pipeline_next_attempt_at == now + timedelta(minutes=8)
    assert after.pipeline_result == {"error": "http_status", "detail": "HTTP 503", "attempt": 3}


def test_the_last_failed_try_sends_the_post_to_review():
    post = claimed(fact(), attempts=MAX_ATTEMPTS)
    outcome = services.record_pipeline_failure(
        post.pk,
        PipelineError("timeout", "no answer in time"),
        claimed_attempts=5,
        now=timezone.now(),
    )
    assert outcome == Outcome.ENTERED_REVIEW
    after = Post.objects.get(pk=post.pk)
    assert (after.status, after.flagged_reason) == (PostStatus.UNDER_REVIEW, FlaggedReason.PIPELINE)
    assert after.pre_review_status == PostStatus.PENDING
    assert after.pipeline_next_attempt_at is None


def test_the_write_locks_the_post_row_with_for_no_key_update():
    post = claimed(fact())
    with CaptureQueriesContext(connection) as queries:
        services.record_pipeline_result(post.pk, TRUE_95, claimed_attempts=1, now=timezone.now())
    locking = [q["sql"] for q in queries if "FOR NO KEY UPDATE" in q["sql"]]
    assert len(locking) == 1
    assert '"posts_post"."deleted_at" IS NULL' in locking[0]


@pytest.mark.parametrize("write", ["result", "failure"])
def test_the_writes_refuse_to_run_inside_a_callers_transaction(write):
    """`durable=True`: inside an outer transaction the row lock would last across the call."""
    post = claimed(fact())
    with pytest.raises(RuntimeError, match="durable"), transaction.atomic():
        if write == "result":
            services.record_pipeline_result(
                post.pk, TRUE_95, claimed_attempts=1, now=timezone.now()
            )
        else:
            services.record_pipeline_failure(
                post.pk, PipelineError("timeout"), claimed_attempts=1, now=timezone.now()
            )
