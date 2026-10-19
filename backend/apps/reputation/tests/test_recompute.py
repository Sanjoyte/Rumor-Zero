"""`python manage.py recompute_reputation [--user] [--check]`: the rebuild of the stored score
from the ledger, and the audit of the ledger itself (ARCHITECTURE §4a)."""

from datetime import timedelta
from decimal import Decimal
from io import StringIO

import pytest
from django.core.management import CommandError, call_command
from django.utils import timezone

from apps.accounts.models import User
from apps.moderation import services as moderation
from apps.reputation.models import EventKind, ReputationEvent
from apps.reputation.tests.factories import (
    FALSE_95,
    TRUE_95,
    EventFactory,
    VerifiedUserFactory,
    label_by_pipeline,
    moderator_user,
    pending_fact,
    reposted,
    reversal_of,
    stored,
)

pytestmark = pytest.mark.django_db


def run(*args):
    out = StringIO()
    call_command("recompute_reputation", *args, stdout=out)
    return out.getvalue().strip()


def failure(*args):
    with pytest.raises(CommandError) as raised:
        run(*args)
    return str(raised.value)


def a_real_ledger():
    """Three authors and a reposter with rows written by the services."""
    authors = [VerifiedUserFactory() for _ in range(3)]
    for author, result in zip(authors, (TRUE_95, FALSE_95, TRUE_95), strict=True):
        post = pending_fact(author)
        reposted(post)
        label_by_pipeline(post, result)
    post = pending_fact(authors[2])
    label_by_pipeline(post, FALSE_95)
    moderation.remove_post(post.pk, moderator=moderator_user())
    return authors


def test_check_passes_on_a_ledger_the_services_wrote():
    a_real_ledger()
    count = User.objects.count()
    assert run("--check") == f"Checked {count} accounts: every stored score matches the ledger."


def test_a_rebuild_with_nothing_to_fix_changes_nothing():
    a_real_ledger()
    assert run().endswith(": 0 changed.")


def test_a_rebuild_fixes_tampered_fields():
    first, *_ = a_real_ledger()
    expected = stored(first)
    User.objects.filter(pk=first.pk).update(reputation_score=99, reputation_sample=7)
    assert run().endswith(": 1 changed.")
    assert stored(first) == expected == (55, 1)
    assert run("--check").startswith("Checked")


def test_a_user_with_no_rows_expects_the_start():
    person = VerifiedUserFactory()
    User.objects.filter(pk=person.pk).update(reputation_score=70, reputation_sample=4)
    message = failure("--check")
    assert f"{person.username}: stored score 70 from 4 counted events" in message
    assert "the ledger gives 50 from 0" in message
    run()
    assert stored(person) == (50, 0)


def test_check_fails_on_a_tampered_score_and_writes_nothing():
    first, *_ = a_real_ledger()
    User.objects.filter(pk=first.pk).update(reputation_score=54)
    message = failure("--check")
    assert message.startswith("1 problem found:")
    assert f"{first.username}: stored score 54 from 1 counted events" in message
    assert stored(first) == (54, 1)  # --check never writes


def test_check_fails_on_a_tampered_score_after():
    first, *_ = a_real_ledger()
    ReputationEvent.objects.filter(user=first).update(score_after=60)
    message = failure("--check")
    assert "has score_after 60, the rows up to it give 55" in message


def test_check_fails_on_times_out_of_order():
    person = VerifiedUserFactory()
    now = timezone.now()
    EventFactory(user=person, created_at=now, score_after=55)
    EventFactory(user=person, created_at=now, score_after=59)  # the same instant: not later
    message = failure("--check")
    assert "is not later than the row before it" in message


def test_check_fails_on_a_reversal_of_someone_elses_row():
    mine = EventFactory(score_after=55)
    theirs = EventFactory(score_after=55)
    reversal_of(theirs, user=mine.user, score_after=50)
    message = failure("--check")
    assert "cancels someone else's row" in message


def test_check_fails_on_a_reversal_of_a_reversal():
    original = EventFactory(score_after=55)
    first = reversal_of(original, score_after=50)
    reversal_of(first, positive=Decimal("0"), negative=Decimal("0"), score_after=50)
    assert "cancels another reversal" in failure("--check")


def test_check_fails_on_a_reversal_that_does_not_exactly_cancel():
    original = EventFactory(kind=EventKind.FACT_FALSE, score_after=45)
    reversal_of(original, negative=Decimal("-0.5"), score_after=48)
    assert "doesn't exactly cancel its row" in failure("--check")


def test_check_lists_every_problem():
    first, second, _ = a_real_ledger()
    User.objects.filter(pk__in=[first.pk, second.pk]).update(reputation_sample=9)
    message = failure("--check")
    assert message.startswith("2 problems found:")
    assert first.username in message and second.username in message


def test_impossible_sums_are_a_problem_not_a_crash():
    person = VerifiedUserFactory()
    EventFactory(user=person, kind=EventKind.FACT_TRUE, positive=Decimal("0.1"), score_after=50)
    assert "the ledger's sums are impossible" in failure("--check")
    assert "the ledger's sums are impossible" in failure()


def test_one_user_only():
    first, second, _ = a_real_ledger()
    User.objects.filter(pk__in=[first.pk, second.pk]).update(reputation_score=1)
    assert run("--user", first.username) == "Recomputed 1 account: 1 changed."
    assert stored(first) == (55, 1)
    assert stored(second) == (1, 1)
    assert run("--user", first.username.upper(), "--check").startswith("Checked 1 account:")


@pytest.mark.parametrize("name", ["nobody_here", "x", "bad name!"])
def test_an_unknown_user_is_an_error(name):
    assert failure("--user", name) == f"No account is called {name!r}."


def test_a_long_ledger_replays_to_the_stored_score():
    author = VerifiedUserFactory()
    for i in range(12):
        label_by_pipeline(
            pending_fact(author), TRUE_95 if i % 3 else FALSE_95, now=timezone.now() + timedelta(i)
        )
    assert run("--user", author.username, "--check").startswith("Checked")
