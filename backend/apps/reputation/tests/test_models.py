"""`ReputationEvent`: the database checks, append-only rows, and what account and post deletion do
to the ledger (ARCHITECTURE §2)."""

from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction

from apps.reputation.models import EventKind, ReputationEvent
from apps.reputation.tests.factories import (
    EventFactory,
    PostFactory,
    VerifiedUserFactory,
    reversal_of,
)

pytestmark = pytest.mark.django_db


def refused(**fields):
    with pytest.raises(IntegrityError), transaction.atomic():
        EventFactory(**fields)


def test_a_row_with_the_tables_weights_is_accepted():
    row = EventFactory(kind=EventKind.FACT_FALSE)
    assert (row.positive, row.negative) == (Decimal("0"), Decimal("1"))
    assert row.reverses is None


def test_an_unknown_kind_is_refused():
    refused(kind="fact_maybe", positive=Decimal("1"), negative=Decimal("0"))


@pytest.mark.parametrize(("positive", "negative"), [("-1", "0"), ("0", "-0.25")])
def test_an_ordinary_row_never_subtracts(positive, negative):
    refused(kind=EventKind.FACT_TRUE, positive=Decimal(positive), negative=Decimal(negative))


def test_a_reversal_never_adds():
    original = EventFactory()
    with pytest.raises(IntegrityError), transaction.atomic():
        reversal_of(original, positive=Decimal("1"))


def test_a_reversal_must_point_at_the_row_it_cancels():
    refused(kind=EventKind.REVERSAL, positive=Decimal("-1"), negative=Decimal("0"))


def test_only_a_reversal_may_point_at_a_row():
    original = EventFactory()
    refused(kind=EventKind.FACT_TRUE, reverses=original)


def test_a_row_can_be_reversed_only_once():
    original = EventFactory()
    reversal_of(original)
    with pytest.raises(IntegrityError), transaction.atomic():
        reversal_of(original)


@pytest.mark.parametrize("score_after", [-1, 101])
def test_score_after_stays_between_0_and_100(score_after):
    refused(score_after=score_after)


@pytest.mark.parametrize("score_after", [0, 100])
def test_score_after_accepts_the_bounds(score_after):
    assert EventFactory(score_after=score_after).score_after == score_after


def test_a_saved_row_cannot_change():
    row = EventFactory()
    row.score_after = 99
    with pytest.raises(RuntimeError, match="append-only"):
        row.save()
    assert ReputationEvent.objects.get(pk=row.pk).score_after == 55


def test_a_row_cannot_be_deleted_one_by_one():
    row = EventFactory()
    with pytest.raises(RuntimeError, match="append-only"):
        row.delete()
    assert ReputationEvent.objects.filter(pk=row.pk).exists()


def test_deleting_the_account_takes_its_ledger_with_it():
    person = VerifiedUserFactory()
    other = EventFactory()
    row = EventFactory(user=person)
    reversal_of(row)
    person.delete()
    assert list(ReputationEvent.objects.values_list("pk", flat=True)) == [other.pk]


def test_a_hard_deleted_post_only_loses_its_link():
    """A post's own deletion is the author's soft delete (the row stays); a hard delete (the
    author's account going) nulls the link on everyone else's rows."""
    post = PostFactory()
    reposter_row = EventFactory(kind=EventKind.REPOST_TRUE, post=post)
    post.delete()
    reposter_row = ReputationEvent.objects.get(pk=reposter_row.pk)
    assert reposter_row.post_id is None
    assert reposter_row.kind == EventKind.REPOST_TRUE


def test_the_string_names_the_kind_and_the_person_only():
    row = EventFactory(kind=EventKind.REPORT_UPHELD)
    assert str(row) == f"Report upheld by a moderator ({row.user_id})"
