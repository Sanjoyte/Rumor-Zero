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


# ---------- Part 11: appeals, Restore and the pipeline ----------


def removed_with_appeal(before, **fields):
    post = fact(
        "Removed, then appealed", status=PostStatus.REMOVED, pre_removal_status=before, **fields
    )
    services.file_appeal(author=post.author, post_id=post.pk, now=timezone.now())
    return Post.objects.get(pk=post.pk)


def test_a_post_restored_to_pending_is_due_and_the_pipeline_checks_it():
    """The fact was removed before its check ever finished: Restore puts it back in the queue."""
    post = removed_with_appeal(PostStatus.PENDING)
    services.restore_post(post.pk, moderator=moderator_user())
    after = Post.objects.get(pk=post.pk)
    assert after.status == PostStatus.PENDING and is_awaiting_check(after)
    assert Post.objects.filter(awaiting_check_q(), pk=post.pk).exists()
    outcome = post_services.record_pipeline_result(
        post.pk, TRUE_95, claimed_attempts=after.pipeline_attempts, now=timezone.now()
    )
    assert outcome == Outcome.LABELLED
    assert Post.objects.get(pk=post.pk).status == PostStatus.VERIFIED_TRUE


def test_a_post_restored_into_review_is_not_in_the_pipelines_queue_and_its_answer_is_ignored():
    post = removed_with_appeal(PostStatus.PENDING, pipeline_checked_at=timezone.now())
    services.restore_post(post.pk, moderator=moderator_user())
    after = Post.objects.get(pk=post.pk)
    assert after.status == PostStatus.UNDER_REVIEW and not is_awaiting_check(after)
    assert not Post.objects.filter(awaiting_check_q(), pk=post.pk).exists()
    outcome = post_services.record_pipeline_result(
        post.pk, FALSE_95, claimed_attempts=after.pipeline_attempts, now=timezone.now()
    )
    assert outcome == Outcome.IGNORED
    assert Post.objects.get(pk=post.pk).verdict_source is None  # a moderator gives the label


def test_a_post_under_a_label_appeal_ignores_a_pipeline_answer():
    post = fact(
        "Labelled FALSE by the pipeline",
        status=PostStatus.VERIFIED_FALSE,
        verdict_source=VerdictSource.PIPELINE,
        pipeline_attempts=1,
        pipeline_checked_at=timezone.now(),
    )
    services.file_appeal(author=post.author, post_id=post.pk)
    after = Post.objects.get(pk=post.pk)
    assert after.status == PostStatus.UNDER_REVIEW and not is_awaiting_check(after)
    outcome = post_services.record_pipeline_result(
        post.pk, TRUE_95, claimed_attempts=1, now=timezone.now()
    )
    assert outcome == Outcome.IGNORED
    assert Post.objects.get(pk=post.pk).status == PostStatus.UNDER_REVIEW


def test_an_answer_dropped_by_a_removal_does_not_stop_a_restored_post_being_checked_again():
    """The try was claimed (`pipeline_attempts=1`) and the post removed meanwhile: its answer is
    dropped. After the appeal and a Restore the post is `pending` with the same claim token, so
    the next try is a fresh claim: nothing in the moderation path touched the token."""
    post = fact("In flight", status=PostStatus.PENDING)
    Post.objects.filter(pk=post.pk).update(
        pipeline_attempts=1, pipeline_next_attempt_at=timezone.now() + timedelta(minutes=5)
    )
    services.remove_post(post.pk, moderator=moderator_user())
    ignored = post_services.record_pipeline_result(
        post.pk, TRUE_95, claimed_attempts=1, now=timezone.now()
    )
    assert ignored == Outcome.IGNORED  # removed: the answer is dropped
    services.file_appeal(author=post.author, post_id=post.pk)
    services.restore_post(post.pk, moderator=moderator_user())
    after = Post.objects.get(pk=post.pk)
    assert (after.status, after.pipeline_attempts) == (PostStatus.PENDING, 1)
    assert is_awaiting_check(after)


@pytest.mark.parametrize("name", ["restore_post", "keep_removed"])
def test_the_new_actions_do_not_change_the_claim_token_either(name):
    post = removed_with_appeal(PostStatus.PENDING, pipeline_attempts=3)
    getattr(services, name)(post.pk, moderator=moderator_user())
    assert Post.objects.get(pk=post.pk).pipeline_attempts == 3
