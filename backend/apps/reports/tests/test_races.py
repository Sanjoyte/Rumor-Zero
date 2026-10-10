"""Concurrency (ARCHITECTURE §5): the post row lock is what keeps two reports from both missing the
threshold, from both counting the same `report_count`, or from filing against a post that a
concurrent delete or removal has just hidden. Real threads on real connections
(`transaction=True`)."""

import threading

import pytest
from django.db import connection, transaction
from django.utils import timezone

from apps.accounts.tests.conftest import run_together
from apps.posts.models import FlaggedReason, Post, PostStatus
from apps.reports import services
from apps.reports.models import Report, ReportReason
from apps.reports.tests.factories import ReportFactory, aged_user
from apps.social.services import like
from apps.social.tests.factories import PostFactory

pytestmark = pytest.mark.django_db(transaction=True)


def reporter_task(reporter, post):
    """One person's report, answering a marker instead of raising (`run_together` asserts that no
    thread raised)."""

    def go():
        try:
            services.file_report(
                reporter=reporter, post_id=post.pk, reason=ReportReason.SPAM, details=""
            )
            return "reported"
        except services.AlreadyReported:
            return "already_reported"
        except services.PostNotFound:
            return "not_found"
        except services.CannotReportOwn:
            return "own"
        finally:
            connection.close()

    return go


def seed_counting(post, n):
    """`n` counting reports committed beforehand, with the lifetime counter in step."""
    for _ in range(n):
        ReportFactory(post=post, reporter=aged_user(now=timezone.now()))
    Post.objects.filter(pk=post.pk).update(report_count=n)


def test_the_same_person_reporting_twice_at_once_makes_one_report():
    post = PostFactory()
    reporter = aged_user(now=timezone.now())
    results = run_together(reporter_task(reporter, post), reporter_task(reporter, post))
    assert sorted(results) == ["already_reported", "reported"]
    assert Report.objects.filter(post=post).count() == 1
    assert Post.objects.get(pk=post.pk).report_count == 1


def test_six_people_reporting_at_once_are_all_counted_and_the_post_reaches_review():
    post = PostFactory()
    people = [aged_user(now=timezone.now()) for _ in range(6)]
    results = run_together(*[reporter_task(person, post) for person in people])
    assert results == ["reported"] * 6
    after = Post.objects.get(pk=post.pk)
    assert after.report_count == 6
    assert Report.objects.filter(post=post).count() == 6
    assert after.status == PostStatus.UNDER_REVIEW
    assert after.flagged_reason == FlaggedReason.REPORTS
    assert after.pre_review_status == PostStatus.PUBLISHED


def hold_the_row(post, on_release=None):
    """Context for the lock-wait tests: this thread holds the post row with `FOR NO KEY UPDATE`
    (the lock a status write takes) until the block ends; `on_release` runs inside the same
    transaction first (a delete or a removal)."""

    class Holder:
        def __enter__(self):
            self.transaction = transaction.atomic()
            self.transaction.__enter__()
            self.locked = Post.objects.select_for_update(no_key=True).get(pk=post.pk)
            return self.locked

        def __exit__(self, *exc):
            if on_release and exc[0] is None:
                on_release(self.locked)
            return self.transaction.__exit__(*exc)

    return Holder()


def start(task):
    """Run `task` in its own thread; returns (thread, done event, outcome dict)."""
    done = threading.Event()
    outcome = {}

    def runner():
        try:
            outcome["result"] = task()
        finally:
            done.set()

    thread = threading.Thread(target=runner)
    thread.start()
    return thread, done, outcome


def delete(post):
    post.deleted_at = timezone.now()
    post.save(update_fields=["deleted_at", "updated_at"])


def remove(post):
    post.status = PostStatus.REMOVED
    post.save(update_fields=["status", "updated_at"])


@pytest.mark.parametrize("hide", [delete, remove], ids=["deleted", "removed"])
def test_a_report_that_waited_for_a_delete_or_a_removal_is_not_found(hide):
    post = PostFactory()
    reporter = aged_user(now=timezone.now())
    with hold_the_row(post, on_release=hide):
        thread, done, outcome = start(reporter_task(reporter, post))
        assert not done.wait(0.5)  # blocked on our row lock
    thread.join(timeout=30)
    assert outcome["result"] == "not_found"
    after = Post.objects.get(pk=post.pk)
    assert Report.objects.filter(post=post).count() == 0
    assert after.report_count == 0


def test_two_reports_waiting_on_the_row_together_reach_the_threshold():
    """Three counting reports are committed (threshold 5) and two more wait behind a held row
    lock. Whichever runs first, the second counts the first's committed row, so the post ends
    under review with exactly five. Without the lock both would count four and miss it, and each
    would write `report_count = 4`."""
    post = PostFactory()
    seed_counting(post, 3)
    first, second = aged_user(now=timezone.now()), aged_user(now=timezone.now())
    with hold_the_row(post):
        runs = [start(reporter_task(person, post)) for person in (first, second)]
        for _, done, _ in runs:
            assert not done.wait(0.5)  # both blocked on our row lock
    for thread, _, outcome in runs:
        thread.join(timeout=30)
        assert outcome["result"] == "reported"
    after = Post.objects.get(pk=post.pk)
    assert after.status == PostStatus.UNDER_REVIEW
    assert after.flagged_reason == FlaggedReason.REPORTS
    assert after.pre_review_status == PostStatus.PUBLISHED
    assert after.report_count == 5
    assert Report.objects.filter(post=post).count() == 5


def test_a_like_or_a_comment_on_the_post_does_not_wait_for_a_report():
    """`FOR NO KEY UPDATE` doesn't conflict with the `FOR KEY SHARE` that inserts take: reporting
    a busy post must not stall the likes on it."""
    post = PostFactory()
    fan = aged_user(now=timezone.now())
    with hold_the_row(post):

        def liker():
            try:
                return like(user=fan, post_id=post.pk)
            finally:
                connection.close()

        thread, done, outcome = start(liker)
        assert done.wait(5)  # not blocked
    thread.join(timeout=30)
    assert outcome["result"] is True
