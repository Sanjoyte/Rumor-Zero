"""The pipeline's label, its give-up and the report threshold tell the author (Part 13): in the
transaction that changes the post, once, and never about who reported."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.notifications.models import Notification, NotificationType
from apps.pipeline.clients import PipelineError
from apps.pipeline.contract import PipelineResult
from apps.pipeline.routing import MAX_ATTEMPTS, Outcome
from apps.pipeline.tests.conftest import fact, reported_fact
from apps.posts import services as post_services
from apps.posts.models import Post, PostStatus
from apps.posts.tests.factories import PostFactory
from apps.reports import services as report_services
from apps.reports.models import ReportReason
from apps.reports.tests.factories import NOW, ReportFactory, aged_user

pytestmark = pytest.mark.django_db

TRUE_95 = PipelineResult("true", Decimal("95"), {"stub": True, "rule": "#true"})
FALSE_95 = PipelineResult("false", Decimal("95"), {"stub": True, "rule": "#false"})
LOW_40 = PipelineResult("true", Decimal("40"), {"stub": True, "rule": "low"})


def claim(post, attempts=1):
    Post.objects.filter(pk=post.pk).update(
        pipeline_attempts=attempts,
        pipeline_next_attempt_at=timezone.now() + timedelta(minutes=5),
    )
    return post


def record(post, result, attempts=1):
    claim(post, attempts)
    return post_services.record_pipeline_result(
        post.pk, result, claimed_attempts=attempts, now=timezone.now()
    )


def only_item():
    return Notification.objects.get()


@pytest.mark.parametrize(
    ("result", "outcome"), [(TRUE_95, "true"), (FALSE_95, "false")], ids=["true", "false"]
)
def test_a_pipeline_label_tells_the_author_the_verdict(result, outcome):
    post = fact()
    assert record(post, result) == Outcome.LABELLED
    item = only_item()
    assert (item.type, item.recipient_id, item.post_id) == (
        NotificationType.VERDICT,
        post.author_id,
        post.pk,
    )
    assert item.outcome == outcome
    assert item.actor_id is None
    assert item.is_read is False


def test_a_low_confidence_answer_sends_the_post_to_review_and_says_so():
    post = fact()
    assert record(post, LOW_40) == Outcome.ENTERED_REVIEW
    item = only_item()
    assert (item.type, item.recipient_id, item.post_id) == (
        NotificationType.UNDER_REVIEW,
        post.author_id,
        post.pk,
    )
    assert item.outcome == ""


def test_the_last_failed_try_sends_the_post_to_review_and_says_so():
    post = claim(fact(), MAX_ATTEMPTS)
    outcome = post_services.record_pipeline_failure(
        post.pk, PipelineError("timeout", "no answer"), claimed_attempts=MAX_ATTEMPTS, now=NOW
    )
    assert outcome == Outcome.ENTERED_REVIEW
    assert only_item().type == NotificationType.UNDER_REVIEW


def test_a_failed_try_below_the_limit_says_nothing():
    post = claim(fact(), 2)
    post_services.record_pipeline_failure(
        post.pk, PipelineError("timeout"), claimed_attempts=2, now=NOW
    )
    assert Notification.objects.count() == 0


def test_an_answer_for_a_post_already_under_review_for_reports_says_nothing():
    post = reported_fact()
    assert record(post, FALSE_95) == Outcome.UPDATED_REVIEW
    assert Notification.objects.count() == 0


def test_a_last_failed_try_on_a_reported_post_says_nothing_more():
    post = claim(reported_fact(), MAX_ATTEMPTS)
    outcome = post_services.record_pipeline_failure(
        post.pk, PipelineError("timeout"), claimed_attempts=MAX_ATTEMPTS, now=NOW
    )
    assert outcome == Outcome.UPDATED_REVIEW
    assert Notification.objects.count() == 0


def test_a_dropped_answer_says_nothing():
    post = fact()
    claim(post, 2)
    assert (
        post_services.record_pipeline_result(
            post.pk, TRUE_95, claimed_attempts=1, now=timezone.now()
        )
        is None
    )
    assert Notification.objects.count() == 0


def test_an_answer_for_a_post_already_decided_says_nothing():
    post = fact(status=PostStatus.REMOVED)
    assert record(post, TRUE_95) == Outcome.IGNORED
    assert Notification.objects.count() == 0


def test_a_rolled_back_label_leaves_no_item():
    post = claim(fact())
    # The label and the item share a transaction: if the write fails, neither stays.
    from unittest import mock

    with (
        mock.patch("apps.notifications.services.notify", side_effect=RuntimeError("boom")),
        pytest.raises(RuntimeError),
    ):
        post_services.record_pipeline_result(
            post.pk, TRUE_95, claimed_attempts=1, now=timezone.now()
        )
    assert Post.objects.get(pk=post.pk).status == PostStatus.PENDING


# ---------- the report threshold ----------


def seed(post, count):
    for number in range(count):
        ReportFactory(post=post, created_at=NOW - timedelta(minutes=number + 1))
    Post.objects.filter(pk=post.pk).update(report_count=count)


def file(post):
    return report_services.file_report(
        reporter=aged_user(), post_id=post.pk, reason=ReportReason.INACCURATE, details="", now=NOW
    )


def test_the_report_that_reaches_the_threshold_tells_the_author_without_naming_anyone():
    post = PostFactory()
    seed(post, 4)
    file(post)
    item = only_item()
    assert (item.type, item.recipient_id, item.post_id) == (
        NotificationType.UNDER_REVIEW,
        post.author_id,
        post.pk,
    )
    assert item.actor_id is None


def test_a_report_below_the_threshold_says_nothing():
    post = PostFactory()
    seed(post, 2)
    file(post)
    assert Notification.objects.count() == 0


def test_reports_after_the_post_entered_review_say_nothing_more():
    post = PostFactory()
    seed(post, 4)
    file(post)
    file(post)
    file(post)
    assert Notification.objects.count() == 1


def test_a_report_on_a_post_the_pipeline_already_holds_says_nothing_new():
    """The pipeline's review was told when it began; reports merging in change only the reason."""
    post = PostFactory(fact=True)
    claim(post)
    record(post, LOW_40)
    seed(post, 4)
    file(post)
    assert Notification.objects.filter(type=NotificationType.UNDER_REVIEW).count() == 1


def test_an_unreportable_post_writes_no_item():
    post = PostFactory(removed=True)
    with pytest.raises(report_services.PostNotFound):
        file(post)
    assert Notification.objects.count() == 0
