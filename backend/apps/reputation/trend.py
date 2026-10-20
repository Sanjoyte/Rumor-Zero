"""The 30-day credibility trend on `GET /api/v1/users/{username}/reputation/` (Part 11D).

Pure: `build_trend` takes the score before the window, the last `score_after` of each UTC day that
had a row, and today's date, so the midnight edges and the carry-forward are tested with a given
`today` (the view reads the clock once).
"""

from datetime import UTC, datetime, time, timedelta

from apps.reputation.scoring import START_SCORE

DAYS = 30


def window_start(today):
    """The UTC midnight that opens the first of the `DAYS` days ending on `today`."""
    return datetime.combine(today - timedelta(days=DAYS - 1), time.min, tzinfo=UTC)


def build_trend(base, last_by_day, today):
    """`DAYS` points `{date, score}` for `today - 29 … today`. Each day shows the last row's
    `score_after` of that day, and a quiet day carries the previous one forward. `base` is the
    score right before the window (None when the account had no row yet: it starts at 50)."""
    score = START_SCORE if base is None else base
    points = []
    for offset in range(DAYS - 1, -1, -1):
        day = today - timedelta(days=offset)
        score = last_by_day.get(day, score)
        points.append({"date": day.isoformat(), "score": score})
    return points
