"""Concurrency (ARCHITECTURE §6): real threads on real connections (`transaction=True`). The
sweeper skips locked rows, never holds the post row while the pipeline thinks, the kick waits for a
moment's lock instead of skipping, and two processors never check the same post."""

import threading
import time

import pytest
from django.db import connection, transaction
from django.utils import timezone

from apps.accounts.tests.conftest import run_together
from apps.pipeline import processor
from apps.pipeline.tests.conftest import FakeClient, fact
from apps.posts.models import Post, PostStatus
from apps.reports import services as report_services
from apps.reports.models import ReportReason
from apps.reports.tests.factories import aged_user
from apps.reports.tests.test_races import hold_the_row, start

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.usefixtures("pipeline_cfg")]


def closing(task):
    """Run `task`, then close this thread's connection (the thread is ours, not Django's)."""

    def run():
        try:
            return task()
        finally:
            connection.close()

    return run


def test_the_sweeper_skips_a_locked_post_and_takes_the_next_one_without_waiting():
    oldest = fact("oldest", age_seconds=50)
    newer = fact("newer #true", age_seconds=10)
    with hold_the_row(oldest):
        thread, done, outcome = start(closing(lambda: processor.process_pending(limit=1)))
        assert done.wait(5)  # it did not wait for our lock
    thread.join(timeout=30)
    assert outcome["result"] == 1
    assert Post.objects.get(pk=newer.pk).status == PostStatus.VERIFIED_TRUE
    untouched = Post.objects.get(pk=oldest.pk)
    assert (untouched.status, untouched.pipeline_attempts) == (PostStatus.PENDING, 0)


def test_the_post_row_is_not_locked_while_the_pipeline_is_being_asked():
    post = fact("A claim #true")
    seen = {}

    def try_to_lock(request):
        def lock_now():
            with transaction.atomic():
                Post.objects.select_for_update(nowait=True).get(pk=post.pk)
            return "locked"

        thread, done, outcome = start(closing(lock_now))
        thread.join(timeout=30)
        seen["result"] = outcome.get("result")

    assert processor.process_pending(client=FakeClient(during=try_to_lock)) == 1
    assert seen["result"] == "locked"  # NOWAIT would raise if the processor held the row
    assert Post.objects.get(pk=post.pk).status == PostStatus.VERIFIED_TRUE


def test_a_report_filed_while_the_pipeline_is_being_asked_does_not_wait_for_it():
    post = fact("A claim #true")
    seen = {}

    def report_meanwhile(request):
        task = closing(
            lambda: report_services.file_report(
                reporter=aged_user(now=timezone.now()),
                post_id=post.pk,
                reason=ReportReason.SPAM,
                details="",
            )
        )
        thread, done, outcome = start(task)
        seen["finished"] = done.wait(5)
        thread.join(timeout=30)

    processor.process_pending(client=FakeClient(during=report_meanwhile))
    assert seen["finished"] is True
    after = Post.objects.get(pk=post.pk)
    assert after.report_count == 1
    assert after.status == PostStatus.VERIFIED_TRUE


def test_the_kick_waits_for_a_moments_lock_instead_of_skipping_the_post():
    post = fact("A new claim #true")
    with hold_the_row(post):
        thread, done, outcome = start(closing(lambda: processor.process_post(post.pk)))
        assert not done.wait(0.5)  # waiting on our row lock, not skipping
    thread.join(timeout=30)
    assert outcome["result"] is True
    assert Post.objects.get(pk=post.pk).status == PostStatus.VERIFIED_TRUE


def test_two_processors_at_once_never_check_the_same_post():
    posts = [fact(f"Claim {n} #true", age_seconds=100 - n) for n in range(8)]
    lock = threading.Lock()
    calls = {}

    def slow(request):
        with lock:
            calls[request.post_id] = calls.get(request.post_id, 0) + 1
        time.sleep(0.05)  # keep both processors busy at the same time

    client = FakeClient(during=slow)
    handled = run_together(
        closing(lambda: processor.process_pending(limit=10, client=client)),
        closing(lambda: processor.process_pending(limit=10, client=client)),
    )
    assert sum(handled) == 8
    assert all(count > 0 for count in handled)  # both took part
    assert calls == {post.pk: 1 for post in posts}
    assert all(
        status == PostStatus.VERIFIED_TRUE
        for status in Post.objects.filter(pk__in=[p.pk for p in posts]).values_list(
            "status", flat=True
        )
    )
