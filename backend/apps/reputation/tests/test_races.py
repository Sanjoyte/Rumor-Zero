"""Two writers for one person at once, in real threads (ARCHITECTURE §4a).

Each writer pauses right after reading the person's totals, so without the users' lock both would
compute from the same sums and the second write would undo the first. A test here proves its own
point: the same race with the lock helper switched off ends wrong.

`transaction=True`: each thread has its own connection and commits for real.
"""

import contextlib
import threading

import pytest

from apps.accounts.tests.conftest import run_together
from apps.moderation import services as moderation
from apps.posts.models import PostStatus
from apps.reputation import services
from apps.reputation.models import EventKind, ReputationEvent
from apps.reputation.tests.factories import (
    EventFactory,
    VerifiedUserFactory,
    kinds,
    moderator_user,
    open_reports,
    reported_fact,
    stored,
)

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def pause_after_totals(monkeypatch):
    """Make every settle wait for the other writer right after it read the totals. With the
    users' lock the second writer is still waiting for the lock, so the first one's wait times
    out and it goes on (a broken barrier then lets everyone through)."""
    barrier = threading.Barrier(2, timeout=1.5)
    read = services._read_totals

    def paused(user_ids):
        totals = read(user_ids)
        with contextlib.suppress(threading.BrokenBarrierError):
            barrier.wait()
        return totals

    monkeypatch.setattr(services, "_read_totals", paused)


@pytest.fixture
def no_user_lock(monkeypatch):
    def unlocked(user_ids):
        from apps.accounts.models import User

        return list(User.objects.filter(pk__in=list(user_ids)).order_by("pk"))

    monkeypatch.setattr(services, "_lock_users", unlocked)


def two_false_verdicts_for_one_author():
    author = VerifiedUserFactory()
    posts = [reported_fact(author), reported_fact(author)]
    moderators = [moderator_user(), moderator_user()]
    run_together(
        *[
            (lambda post=post, mod=mod: moderation.mark_false(post.pk, moderator=mod))
            for post, mod in zip(posts, moderators, strict=True)
        ]
    )
    return author


@pytest.mark.usefixtures("pause_after_totals")
def test_two_verdicts_for_one_author_at_once_both_count():
    author = two_false_verdicts_for_one_author()
    assert stored(author) == (42, 2)  # 100 · 5 / 12
    rows = list(ReputationEvent.objects.filter(user=author).order_by("created_at"))
    assert [row.score_after for row in rows] == [45, 42]
    assert rows[0].created_at < rows[1].created_at


@pytest.mark.usefixtures("pause_after_totals", "no_user_lock")
def test_without_the_user_lock_the_second_verdict_undoes_the_first():
    """The race is real: this is what the lock prevents."""
    author = two_false_verdicts_for_one_author()
    assert stored(author) == (45, 1)
    assert [row.score_after for row in ReputationEvent.objects.filter(user=author)] == [45, 45]


def two_credits_at_the_cap_boundary():
    reporter = VerifiedUserFactory()
    for _ in range(3):
        EventFactory(user=reporter, kind=EventKind.REPORT_UPHELD, score_after=51)
    posts = [reported_fact(), reported_fact()]
    for post in posts:
        open_reports(post, reporter=reporter)
    moderators = [moderator_user(), moderator_user()]
    run_together(
        *[
            (lambda post=post, mod=mod: moderation.mark_false(post.pk, moderator=mod))
            for post, mod in zip(posts, moderators, strict=True)
        ]
    )
    return reporter


@pytest.mark.usefixtures("pause_after_totals")
def test_two_credits_at_the_cap_boundary_give_exactly_one():
    reporter = two_credits_at_the_cap_boundary()
    assert kinds(reporter).count(EventKind.REPORT_UPHELD) == 4


@pytest.mark.usefixtures("pause_after_totals", "no_user_lock")
def test_without_the_user_lock_the_cap_is_crossed():
    reporter = two_credits_at_the_cap_boundary()
    assert kinds(reporter).count(EventKind.REPORT_UPHELD) == 5


@pytest.mark.usefixtures("pause_after_totals")
def test_two_moderators_deciding_each_others_posts_at_once_do_not_deadlock():
    """Each one's audit row and `moderated_by` take `KEY SHARE` on the other's user row at commit
    (the foreign keys are deferred), while the other holds that row for their own score. `FOR NO
    KEY UPDATE` doesn't conflict with `KEY SHARE`; a plain `FOR UPDATE` deadlocks here."""
    first, second = moderator_user(), moderator_user()
    by_second = reported_fact(second)
    by_first = reported_fact(first)
    run_together(
        lambda: moderation.mark_false(by_second.pk, moderator=first),
        lambda: moderation.mark_false(by_first.pk, moderator=second),
    )
    assert stored(first) == stored(second) == (45, 1)
    assert by_second.__class__.objects.get(pk=by_second.pk).status == PostStatus.VERIFIED_FALSE
