"""Part 11C concurrency: the emergency block (ARCHITECTURE §4b). Real threads on real connections
(`transaction=True`).

The account's lock serialises every writer of its block, and its block rows are strictly increasing
in time, so `users.emergency_blocked_until` always equals `rules.standing_block_end` of the rows,
whatever order things commit in. A test here proves its own point: the same race without the
time rule ends wrong."""

import time
from datetime import timedelta

import pytest
from django.db import connection, transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.tests.conftest import run_together
from apps.moderation import rules, services
from apps.moderation.models import ActionKind, ModerationAction
from apps.moderation.tests.factories import moderator_user, senior_user
from apps.moderation.tests.test_races import moderator_task, start
from apps.posts import services as post_services
from apps.posts.models import FlaggedReason, Post, PostStatus, PostType
from apps.posts.tests.factories import PostFactory, VerifiedUserFactory

pytestmark = pytest.mark.django_db(transaction=True)


def elder():
    return VerifiedUserFactory(created_at=timezone.now() - timedelta(days=30))


def reported_emergency(author, *, hours_old=2):
    made = timezone.now() - timedelta(hours=hours_old)
    return PostFactory(
        author=author,
        post_type=PostType.FACT,
        status=PostStatus.UNDER_REVIEW,
        flagged_reason=FlaggedReason.REPORTS,
        pre_review_status=PostStatus.PENDING,
        is_emergency=True,
        created_at=made,
        emergency_expires_at=made + timedelta(hours=24),
    )


def block_rows(user):
    return list(
        ModerationAction.objects.filter(
            subject_user=user,
            action__in=[ActionKind.EMERGENCY_BLOCKED, ActionKind.EMERGENCY_UNBLOCKED],
        ).order_by("created_at", "id")
    )


def column(user):
    return User.objects.values_list("emergency_blocked_until", flat=True).get(pk=user.pk)


def end_of_rows(user):
    rows = [rules.BlockRow(r.action, r.post_id, r.blocked_until) for r in block_rows(user)]
    return rules.standing_block_end(rows)


def wait_until_someone_waits_for_a_lock(timeout=10):
    """Poll Postgres until another transaction is queued behind a row lock."""
    deadline = time.monotonic() + timeout
    with connection.cursor() as cursor:
        while time.monotonic() < deadline:
            cursor.execute("SELECT count(*) FROM pg_locks WHERE NOT granted")
            if cursor.fetchone()[0]:
                return
            time.sleep(0.02)
    raise AssertionError("the other transaction never waited for the lock")


def mark_false_while_an_unblock_commits_first(author, post):
    """The Mark FALSE locks the post and takes its time, then waits for the author's row, which
    this thread holds; meanwhile this thread unblocks the author (a later time) and commits. Then
    the Mark FALSE goes on and writes its automatic block."""
    thread, done, outcome = start(moderator_task("mark_false", post, moderator_user()))
    with transaction.atomic():
        User.objects.select_for_update(no_key=True).get(pk=author.pk)
        wait_until_someone_waits_for_a_lock()
        services.unblock_emergency_posting(author.pk, moderator=senior_user())
    thread.join(timeout=30)
    assert done.is_set() and outcome["result"] == "done"


def test_a_mark_false_and_an_unblock_of_its_author_at_once_leave_the_new_block_standing():
    """The review's case: the Unblock committed first but stamped a later time than the waiting
    Mark FALSE's own. The block row comes after the Unblock (`last + 1 µs`), so it stands."""
    author = elder()
    post = reported_emergency(author)
    services.block_emergency_posting(author.pk, moderator=senior_user())
    mark_false_while_an_unblock_commits_first(author, post)
    actions = [row.action for row in block_rows(author)]
    assert actions == [
        ActionKind.EMERGENCY_BLOCKED,  # the manual one
        ActionKind.EMERGENCY_UNBLOCKED,
        ActionKind.EMERGENCY_BLOCKED,  # Mark FALSE's, after the unblock
    ]
    assert column(author) is not None
    assert column(author) == end_of_rows(author) == block_rows(author)[-1].blocked_until
    marked = ModerationAction.objects.get(post=post, action=ActionKind.MARKED_FALSE)
    assert marked.created_at < block_rows(author)[1].created_at  # its own time was older


def test_without_the_time_rule_the_unblock_would_erase_the_new_block(monkeypatch):
    """What strictly increasing rows prevent: the block is stamped with the Mark FALSE's older
    time, sorts before the Unblock, and reads as lifted."""
    monkeypatch.setattr(services, "_next_block_time", lambda user_id, now: now)
    author = elder()
    post = reported_emergency(author)
    services.block_emergency_posting(author.pk, moderator=senior_user())
    mark_false_while_an_unblock_commits_first(author, post)
    assert [row.action for row in block_rows(author)][-1] == ActionKind.EMERGENCY_UNBLOCKED
    assert column(author) is None


def test_a_block_and_an_emergency_post_at_once_refuse_the_post_or_follow_it():
    author = elder()

    def block():
        services.block_emergency_posting(author.pk, moderator=moderator_user())
        return "blocked"

    def post():
        try:
            post_services.create_post(
                author=author,
                content="Bridge closed after the storm",
                post_type=PostType.FACT,
                is_emergency=True,
            )
        except post_services.EmergencyNotAllowed as exc:
            return f"refused:{exc.reason}"
        return "created"

    results = run_together(block, post)
    assert results[0] == "blocked"
    assert results[1] in ("created", "refused:blocked")
    made = Post.objects.filter(author=author, is_emergency=True).count()
    assert made == (1 if results[1] == "created" else 0)
    assert column(author) == end_of_rows(author) is not None


def test_a_mark_false_while_the_author_posts_another_emergency_does_not_deadlock(monkeypatch):
    """The author's post holds their row (counting slowly); the Mark FALSE holds the old post and
    waits for that row. No cycle: the new post is created (it came first) or refused as blocked."""
    original = post_services._fact_post_times

    def slow(author, since):
        rows = original(author, since)
        time.sleep(0.3)
        return rows

    monkeypatch.setattr(post_services, "_fact_post_times", slow)
    author = elder()
    old = reported_emergency(author, hours_old=25)  # outside the daily limit's 24 hours

    def post():
        try:
            post_services.create_post(
                author=author,
                content="Second warning",
                post_type=PostType.FACT,
                is_emergency=True,
            )
        except post_services.EmergencyNotAllowed as exc:
            return f"refused:{exc.reason}"
        return "created"

    results = run_together(post, moderator_task("mark_false", old, moderator_user()))
    assert results[1] == "done"
    assert results[0] in ("created", "refused:blocked")
    assert Post.objects.get(pk=old.pk).status == PostStatus.VERIFIED_FALSE
    assert column(author) == end_of_rows(author) is not None
