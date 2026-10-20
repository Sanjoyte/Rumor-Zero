"""`trend` on `GET /api/v1/users/{username}/reputation/` (Part 11D): 30 daily points from the
ledger's `score_after`, null while the score is hidden, 3 queries when public and 2 when hidden."""

from datetime import UTC, timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.accounts.models import User
from apps.reputation.models import EventKind as K
from apps.reputation.tests.factories import EventFactory, VerifiedUserFactory

pytestmark = pytest.mark.django_db


def url(name="ada"):
    return f"/api/v1/users/{name}/reputation/"


def make_public(user, score=60):
    User.objects.filter(pk=user.pk).update(reputation_score=score, reputation_sample=3)


@pytest.fixture
def ada():
    return VerifiedUserFactory(username="ada")


def midnight_today():
    now = timezone.now().astimezone(UTC)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def points(client):
    return client.get(url()).json()["trend"]


def test_the_trend_is_null_while_the_score_is_hidden(api_client, ada):
    EventFactory(user=ada)
    assert points(api_client) is None


def test_a_public_account_without_rows_is_a_flat_fifty_line(api_client, ada):
    make_public(ada, 50)
    trend = points(api_client)
    assert len(trend) == 30 and {p["score"] for p in trend} == {50}


def test_thirty_points_ending_today_each_with_only_date_and_score(api_client, ada):
    make_public(ada)
    trend = points(api_client)
    assert [set(p) for p in trend] == [{"date", "score"}] * 30
    assert trend[-1]["date"] == timezone.now().astimezone(UTC).date().isoformat()
    assert (
        trend[0]["date"] == (timezone.now().astimezone(UTC).date() - timedelta(days=29)).isoformat()
    )


def test_the_last_row_of_a_day_wins_and_quiet_days_carry_forward(api_client, ada):
    make_public(ada)
    day = midnight_today() - timedelta(days=10)
    EventFactory(user=ada, score_after=55, created_at=day + timedelta(hours=1))
    EventFactory(user=ada, score_after=58, created_at=day + timedelta(hours=9))
    EventFactory(user=ada, score_after=61, created_at=day + timedelta(days=3, hours=2))
    trend = {p["date"]: p["score"] for p in points(api_client)}
    d = lambda n: (day + timedelta(days=n)).date().isoformat()  # noqa: E731
    assert trend[d(-1)] == 50
    assert trend[d(0)] == 58
    assert trend[d(2)] == 58
    assert trend[d(3)] == 61
    assert trend[d(10)] == 61


def test_the_baseline_is_the_last_score_before_the_window(api_client, ada):
    make_public(ada)
    old = midnight_today() - timedelta(days=45)
    EventFactory(user=ada, score_after=70, created_at=old)
    EventFactory(user=ada, score_after=66, created_at=old + timedelta(days=1))
    assert {p["score"] for p in points(api_client)} == {66}


def test_a_row_just_before_the_window_is_the_baseline_and_one_at_its_midnight_is_in(
    api_client, ada
):
    make_public(ada)
    first_midnight = midnight_today() - timedelta(days=29)
    EventFactory(user=ada, score_after=70, created_at=first_midnight - timedelta(microseconds=1))
    EventFactory(user=ada, score_after=72, created_at=first_midnight)
    trend = points(api_client)
    assert trend[0]["score"] == 72
    assert {p["score"] for p in trend} == {72}


def test_a_row_in_the_last_microsecond_before_the_window_is_the_baseline(api_client, ada):
    make_public(ada)
    first_midnight = midnight_today() - timedelta(days=29)
    EventFactory(user=ada, score_after=70, created_at=first_midnight - timedelta(microseconds=1))
    assert {p["score"] for p in points(api_client)} == {70}


def test_a_row_made_just_now_shows_on_the_last_point(api_client, ada):
    make_public(ada)
    EventFactory(user=ada, score_after=64, created_at=timezone.now())
    assert points(api_client)[-1]["score"] == 64


def test_other_peoples_rows_are_not_mixed_in(api_client, ada):
    make_public(ada)
    EventFactory(user=VerifiedUserFactory(), score_after=99, created_at=timezone.now())
    assert {p["score"] for p in points(api_client)} == {50}


def test_reversal_rows_count_like_any_row_for_the_score_after(api_client, ada):
    make_public(ada)
    row = EventFactory(
        user=ada, kind=K.FACT_FALSE, score_after=45, created_at=midnight_today() - timedelta(days=2)
    )
    from apps.reputation.tests.factories import reversal_of

    reversal_of(row, score_after=50)
    assert points(api_client)[-1]["score"] == 50


def queries(client):
    with CaptureQueriesContext(connection) as captured:
        assert client.get(url()).status_code == 200
    return len(captured)


def test_three_queries_when_public_and_two_when_hidden_however_many_rows(api_client, ada):
    EventFactory(user=ada)
    hidden = queries(api_client)
    make_public(ada)
    one = queries(api_client)
    for i in range(40):
        EventFactory(
            user=ada,
            score_after=50 + i % 5,
            created_at=timezone.now() - timedelta(days=i % 30, seconds=i),
        )
    many = queries(api_client)
    assert (hidden, one, many) == (2, 3, 3)
