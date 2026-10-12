"""Concurrency (ARCHITECTURE §4): the post row lock is what makes two moderators, a moderator and
the author, or a moderator and a report take turns. Real threads on real connections
(`transaction=True`)."""

import threading

import pytest
from django.db import connection, transaction
from django.utils import timezone

from apps.accounts.tests.conftest import run_together
from apps.moderation import services
from apps.moderation.models import ModerationAction
from apps.moderation.tests.factories import moderator_user
from apps.posts.models import FlaggedReason, Post, PostStatus
from apps.posts.tests.factories import PostFactory
from apps.reports import services as report_services
from apps.reports.models import Report, ReportReason, ReportStatus
from apps.reports.tests.factories import ReportFactory, aged_user

pytestmark = pytest.mark.django_db(transaction=True)


def under_review(**fields):
    fields.setdefault("review_started_at", timezone.now())
    return PostFactory(
        status=PostStatus.UNDER_REVIEW,
        flagged_reason=FlaggedReason.REPORTS,
        pre_review_status=PostStatus.PUBLISHED,
        **fields,
    )


def moderator_task(name, post, moderator, **kwargs):
    """One moderator's action, answering a marker instead of raising (`run_together` asserts that
    no thread raised)."""

    def go():
        try:
            getattr(services, name)(post.pk, moderator=moderator, **kwargs)
            return "done"
        except services.ActionRefused as refused:
            return refused.refusal.code
        finally:
            connection.close()

    return go


def start(task):
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


class hold_the_row:
    """This thread holds the post row with `FOR NO KEY UPDATE` (the lock a status write takes)
    until the block ends; `on_release` runs inside the same transaction first."""

    def __init__(self, post, on_release=None):
        self.post, self.on_release = post, on_release

    def __enter__(self):
        self.transaction = transaction.atomic()
        self.transaction.__enter__()
        self.locked = Post.objects.select_for_update(no_key=True).get(pk=self.post.pk)
        return self.locked

    def __exit__(self, *exc):
        if self.on_release and exc[0] is None:
            self.on_release(self.locked)
        return self.transaction.__exit__(*exc)


def test_two_moderators_dismissing_the_same_post_at_once_make_one_row_and_one_refusal():
    post = under_review()
    for _ in range(3):
        ReportFactory(post=post)
    results = run_together(
        moderator_task("dismiss_reports", post, moderator_user()),
        moderator_task("dismiss_reports", post, moderator_user()),
    )
    assert sorted(results) == ["done", "not_under_review"]
    assert ModerationAction.objects.filter(post=post).count() == 1
    assert Post.objects.get(pk=post.pk).status == PostStatus.PUBLISHED
    assert (
        list(Report.objects.filter(post=post).values_list("status", flat=True))
        == [ReportStatus.DISMISSED] * 3
    )


def test_two_moderators_removing_the_same_post_at_once_make_one_row():
    post = under_review()
    results = run_together(
        moderator_task("remove_post", post, moderator_user()),
        moderator_task("remove_post", post, moderator_user()),
    )
    assert sorted(results) == ["already_removed", "done"]
    assert ModerationAction.objects.filter(post=post).count() == 1


def test_an_action_that_waited_sees_what_the_other_transaction_committed():
    """The first action holds the row; Remove waits. The holder commits another removal: the
    waiting Remove re-reads the row and is refused as already removed."""

    def remove(locked):
        locked.status = PostStatus.REMOVED
        locked.review_started_at = None
        locked.flagged_reason = None
        locked.pre_review_status = None
        locked.save(
            update_fields=[
                "status",
                "review_started_at",
                "flagged_reason",
                "pre_review_status",
                "updated_at",
            ]
        )

    post = under_review()
    with hold_the_row(post, on_release=remove):
        thread, done, outcome = start(moderator_task("remove_post", post, moderator_user()))
        assert not done.wait(0.5)  # blocked on our row lock
    thread.join(timeout=30)
    assert outcome["result"] == "already_removed"
    assert ModerationAction.objects.count() == 0


def test_an_action_that_waited_for_the_authors_delete_is_refused_as_deleted():
    def delete(locked):
        locked.deleted_at = timezone.now()
        locked.save(update_fields=["deleted_at", "updated_at"])

    post = under_review()
    with hold_the_row(post, on_release=delete):
        thread, done, outcome = start(moderator_task("escalate", post, moderator_user()))
        assert not done.wait(0.5)
    thread.join(timeout=30)
    assert outcome["result"] == "deleted"
    assert ModerationAction.objects.count() == 0
    assert Post.objects.get(pk=post.pk).escalated_at is None


def test_a_report_and_a_removal_at_once_leave_no_open_report_on_the_removed_post():
    """Whichever gets the lock first: the report is filed and then closed by the removal, or the
    removal wins and the report finds no post. An open report can never be left behind."""
    post = under_review()
    reporter = aged_user(now=timezone.now())

    def report():
        try:
            report_services.file_report(
                reporter=reporter, post_id=post.pk, reason=ReportReason.SPAM, details=""
            )
            return "reported"
        except report_services.PostNotFound:
            return "not_found"
        finally:
            connection.close()

    with hold_the_row(post):
        runs = [
            start(moderator_task("remove_post", post, moderator_user())),
            start(report),
        ]
        for _, done, _ in runs:
            assert not done.wait(0.5)  # both blocked on our row lock
    for thread, _, _ in runs:
        thread.join(timeout=30)
    assert runs[0][2]["result"] == "done"
    assert runs[1][2]["result"] in ("reported", "not_found")
    assert Post.objects.get(pk=post.pk).status == PostStatus.REMOVED
    assert not Report.objects.filter(post=post, status=ReportStatus.OPEN).exists()
    if runs[1][2]["result"] == "reported":
        assert Report.objects.get(post=post).status == ReportStatus.ACTIONED


def test_two_different_actions_at_once_leave_a_chain_of_rows_that_fits_together():
    """Mark FALSE and Remove at once: Mark FALSE then Remove (two rows), or Remove first and Mark
    FALSE refused. Either way every row starts where the one before it ended."""
    post = PostFactory(
        fact=True,
        status=PostStatus.UNDER_REVIEW,
        flagged_reason=FlaggedReason.REPORTS,
        pre_review_status=PostStatus.PENDING,
        review_started_at=timezone.now(),
    )
    results = run_together(
        moderator_task("mark_false", post, moderator_user()),
        moderator_task("remove_post", post, moderator_user()),
    )
    rows = list(ModerationAction.objects.filter(post=post).order_by("created_at", "pk"))
    final = Post.objects.get(pk=post.pk)
    if results[1] == "done" and results[0] == "done":
        assert [r.to_status for r in rows] == sorted(
            [r.to_status for r in rows], key=["verified_false", "removed"].index
        )
        assert rows[0].from_status == "under_review"
        assert rows[1].from_status == rows[0].to_status
    else:
        assert results[0] == "not_under_review"
        assert len(rows) == 1
    assert final.status == rows[-1].to_status


def test_a_moderator_who_waited_stamps_the_time_after_the_wait():
    """`created_at` is taken once the lock is held, so the audit trail's order is the order in
    which the changes really happened (a time taken before the wait could be older than the
    change the moderator is now looking at)."""
    post = under_review()
    with hold_the_row(post):
        thread, done, outcome = start(moderator_task("escalate", post, moderator_user()))
        assert not done.wait(0.5)
        released = timezone.now()
    thread.join(timeout=30)
    assert outcome["result"] == "done"
    row = ModerationAction.objects.get()
    assert row.created_at >= released
    assert Post.objects.get(pk=post.pk).moderated_at == row.created_at
