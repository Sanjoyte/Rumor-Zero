"""The pure 30-day trend builder (Part 11D): midnight edges, carry-forward and the 50 baseline,
with a given `today`."""

from datetime import UTC, date, datetime, timedelta

from apps.reputation import trend

TODAY = date(2026, 10, 20)


def test_thirty_points_ending_today_oldest_first():
    points = trend.build_trend(None, {}, TODAY)
    assert len(points) == 30
    assert points[0]["date"] == "2026-09-21"
    assert points[-1]["date"] == "2026-10-20"
    assert all(set(p) == {"date", "score"} for p in points)


def test_a_new_ledger_starts_at_fifty():
    assert {p["score"] for p in trend.build_trend(None, {}, TODAY)} == {50}


def test_the_baseline_is_the_score_before_the_window():
    assert {p["score"] for p in trend.build_trend(71, {}, TODAY)} == {71}


def test_quiet_days_carry_the_last_score_forward():
    points = trend.build_trend(60, {date(2026, 10, 1): 64, date(2026, 10, 10): 58}, TODAY)
    by_date = {p["date"]: p["score"] for p in points}
    assert by_date["2026-09-30"] == 60
    assert by_date["2026-10-01"] == 64
    assert by_date["2026-10-09"] == 64
    assert by_date["2026-10-10"] == 58
    assert by_date["2026-10-20"] == 58


def test_a_row_today_shows_on_the_last_point():
    points = trend.build_trend(60, {TODAY: 66}, TODAY)
    assert points[-1] == {"date": "2026-10-20", "score": 66}
    assert points[-2]["score"] == 60


def test_the_first_day_of_the_window_is_included():
    points = trend.build_trend(60, {date(2026, 9, 21): 61}, TODAY)
    assert points[0] == {"date": "2026-09-21", "score": 61}


def test_a_day_outside_the_window_is_ignored():
    points = trend.build_trend(60, {date(2026, 9, 20): 99, date(2026, 10, 21): 99}, TODAY)
    assert {p["score"] for p in points} == {60}


def test_the_window_opens_at_the_utc_midnight_of_the_first_day():
    assert trend.window_start(TODAY) == datetime(2026, 9, 21, tzinfo=UTC)
    assert trend.window_start(TODAY + timedelta(days=1)) == datetime(2026, 9, 22, tzinfo=UTC)
