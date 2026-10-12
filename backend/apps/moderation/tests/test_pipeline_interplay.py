"""How a moderator's action and a pipeline answer meet (ARCHITECTURE §4, §6; Part 9's claim token):
a moderator never touches `pipeline_attempts`, so an in-flight answer is applied or dropped by the
post's state alone."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.moderation import services
from apps.moderation.tests.factories import moderator_user
from apps.pipeline.contract import PipelineResult
from apps.pipeline.routing import Outcome, awaiting_check_q, is_awaiting_check
from apps.pipeline.tests.conftest import fact, reported_fact
from apps.posts import services as post_services
from apps.posts.models import FlaggedReason, Post, PostStatus, VerdictSource

pytestmark = pytest.mark.django_db

TRUE_95 = PipelineResult("true", Decimal("95"), {"stub": True})
FALSE_95 = PipelineResult("false", Decimal("95"), {"stub": True})


def claimed(post):
    """As if the processor had claimed the post's first try (the lease is running)."""
    Post.objects.filter(pk=post.pk).update(
        review_started_at=timezone.now(),
        pipeline_attempts=1,
        pipeline_next_attempt_at=timezone.now() + timedelta(minutes=5),
    )
    return Post.objects.get(pk=post.pk)


@pytest.mark.parametrize("answer", [TRUE_95, FALSE_95], ids=["true", "false"])
@pytest.mark.parametrize("verdict", ["mark_verified", "mark_false"])
def test_a_pipeline_answer_after_a_moderator_verdict_is_ignored(verdict, answer):
    post = claimed(reported_fact())
    getattr(services, verdict)(post.pk, moderator=moderator_user())
    before = Post.objects.get(pk=post.pk)
    outcome = post_services.record_pipeline_result(
        post.pk, answer, claimed_attempts=1, now=timezone.now()
    )
    assert outcome == Outcome.IGNORED
    after = Post.objects.get(pk=post.pk)
    assert after.verdict_source == VerdictSource.MODERATOR
    assert after.status == before.status
    assert after.confidence_score is None and after.pipeline_verdict is None
    assert after.updated_at == before.updated_at  # not even written


def test_a_pipeline_answer_after_a_removal_is_ignored():
    post = claimed(reported_fact())
    services.remove_post(post.pk, moderator=moderator_user())
    outcome = post_services.record_pipeline_result(
        post.pk, TRUE_95, claimed_attempts=1, now=timezone.now()
    )
    assert outcome == Outcome.IGNORED
    assert Post.objects.get(pk=post.pk).status == PostStatus.REMOVED


def test_a_claimed_answer_after_a_dismissal_back_to_pending_still_applies():
    """The check is still owed after Dismiss, and the claim token (`pipeline_attempts`) is exactly
    what the processor wrote: the answer labels the post as if it had never been reported."""
    post = claimed(reported_fact())
    services.dismiss_reports(post.pk, moderator=moderator_user())
    assert Post.objects.get(pk=post.pk).status == PostStatus.PENDING
    outcome = post_services.record_pipeline_result(
        post.pk, TRUE_95, claimed_attempts=1, now=timezone.now()
    )
    assert outcome == Outcome.LABELLED
    after = Post.objects.get(pk=post.pk)
    assert (after.status, after.verdict_source) == (
        PostStatus.VERIFIED_TRUE,
        VerdictSource.PIPELINE,
    )
    assert after.pipeline_attempts == 1


def test_a_post_also_flagged_by_the_pipeline_is_not_checked_again_after_a_dismissal():
    """Dismiss with `both` leaves the post under review for the pipeline: the pipeline has already
    answered (or given up), so nothing more is owed and a moderator decides."""
    post = fact(
        "Reported and unsure",
        status=PostStatus.UNDER_REVIEW,
        flagged_reason=FlaggedReason.BOTH,
        pre_review_status=PostStatus.PENDING,
        review_started_at=timezone.now(),
    )
    services.dismiss_reports(post.pk, moderator=moderator_user())
    after = Post.objects.get(pk=post.pk)
    assert (after.status, after.flagged_reason) == (PostStatus.UNDER_REVIEW, FlaggedReason.PIPELINE)
    assert not is_awaiting_check(after)
    assert not Post.objects.filter(awaiting_check_q()).exists()


@pytest.mark.parametrize(
    "name", ["mark_verified", "mark_false", "dismiss_reports", "remove_post", "escalate"]
)
def test_no_action_changes_the_claim_token(name):
    post = claimed(reported_fact())
    getattr(services, name)(post.pk, moderator=moderator_user())
    assert Post.objects.get(pk=post.pk).pipeline_attempts == 1
