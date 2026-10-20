"""An account's deletion against a verdict on one of its posts, in real threads (Part 14).

`settle_post` locks the post and then the author's user row; the deletion therefore locks **every
post of the account first and the user second**. These tests prove the order is what keeps the two
apart: the same race with the order reversed ends in a deadlock that Postgres has to break.

`transaction=True`: each thread has its own connection and commits for real.
"""

import threading

import pytest
from django.db import OperationalError, connection, transaction

from apps.accounts import deletion
from apps.accounts.models import User
from apps.moderation import services as moderation
from apps.moderation.services import ActionRefused
from apps.posts.models import Post
from apps.posts.tests.factories import VerifiedUserFactory
from apps.reputation import services as reputation
from apps.reputation.models import ReputationEvent
from apps.reputation.tests.factories import moderator_user, reported_fact

pytestmark = pytest.mark.django_db(transaction=True)


def go(*tasks, timeout=30):
    """Run the tasks in threads, each on its own connection. Returns [(result, error), …]."""
    outcomes = [None] * len(tasks)

    def runner(index, task):
        try:
            outcomes[index] = (task(), None)
        except Exception as exc:  # judged by the test
            outcomes[index] = (None, exc)
        finally:
            connection.close()

    threads = [threading.Thread(target=runner, args=item) for item in enumerate(tasks)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=timeout)
        assert not thread.is_alive(), "a thread is stuck"
    return outcomes


@pytest.fixture
def verdict_waits_for(monkeypatch):
    """Make the verdict pause after it locked its post, just before it asks for the user row, until
    `event` is set (or `seconds` pass). `at_pause` is set when it gets there."""

    def install(event, seconds, at_pause=None):
        real = reputation._lock_users

        def paused(user_ids):
            if at_pause is not None:
                at_pause.set()
            event.wait(timeout=seconds)
            return real(user_ids)

        monkeypatch.setattr(reputation, "_lock_users", paused)

    return install


def mark_false(post, moderator):
    def task():
        try:
            return moderation.mark_false(post.pk, moderator=moderator)
        except ActionRefused:
            return "refused"  # the deletion won: the post is gone

    return task


def test_a_verdict_and_the_deletion_of_its_author_never_deadlock(verdict_waits_for):
    """The verdict holds the post and is about to lock the user; the deletion starts now. It has to
    wait for the post, so the verdict finishes first, and then the account goes."""
    author = VerifiedUserFactory()
    post = reported_fact(author)
    deleting, holds_the_post = threading.Event(), threading.Event()
    verdict_waits_for(deleting, seconds=1.5, at_pause=holds_the_post)

    def delete():
        assert holds_the_post.wait(timeout=10)
        deleting.set()
        return deletion.delete_account(author)

    (verdict, verdict_error), (deleted, delete_error) = go(
        mark_false(post, moderator_user()), delete
    )

    assert verdict_error is None and delete_error is None
    assert deleted is True
    assert verdict != "refused"  # the verdict got the post first and finished
    assert not User.objects.filter(pk=author.pk).exists()
    assert not Post.objects.filter(pk=post.pk).exists()
    assert not ReputationEvent.objects.filter(user_id=author.pk).exists()


def test_the_same_race_with_the_user_locked_first_does_deadlock(verdict_waits_for):
    """The control: lock the user before the posts and Postgres has to abort one of the two."""
    author = VerifiedUserFactory()
    post = reported_fact(author)
    user_locked = threading.Event()
    verdict_waits_for(user_locked, seconds=10)

    def user_first_delete():
        with transaction.atomic():
            list(User.objects.select_for_update().filter(pk=author.pk).values_list("pk"))
            user_locked.set()
            list(Post.objects.select_for_update().filter(author_id=author.pk).values_list("pk"))
            User.objects.filter(pk=author.pk).delete()

    outcomes = go(mark_false(post, moderator_user()), user_first_delete)

    errors = [error for _, error in outcomes if error is not None]
    assert len(errors) == 1  # one is the victim, the other goes through
    assert isinstance(errors[0], OperationalError)
    assert "deadlock" in str(errors[0]).lower()


@pytest.mark.parametrize("trial", range(4))
def test_a_verdict_and_a_deletion_started_together_end_consistently(trial):
    author = VerifiedUserFactory()
    post = reported_fact(author)
    barrier = threading.Barrier(2)

    def together(task):
        def run():
            barrier.wait()
            return task()

        return run

    outcomes = go(
        together(mark_false(post, moderator_user())),
        together(lambda: deletion.delete_account(author)),
    )

    assert [error for _, error in outcomes] == [None, None]
    assert outcomes[1][0] is True
    assert not User.objects.filter(pk=author.pk).exists()
    assert not Post.objects.filter(pk=post.pk).exists()
    assert not ReputationEvent.objects.filter(user_id=author.pk).exists()


def test_two_deletions_of_one_account_at_once_give_one_true_and_one_false():
    author = VerifiedUserFactory()
    reported_fact(author)
    barrier = threading.Barrier(2)

    def delete():
        barrier.wait()
        return deletion.delete_account(author)

    outcomes = go(delete, delete)

    assert [error for _, error in outcomes] == [None, None]
    assert sorted(result for result, _ in outcomes) == [False, True]
    assert not User.objects.filter(pk=author.pk).exists()
