import itertools
from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.utils import timezone

from apps.posts.emergency import is_active_emergency
from apps.posts.models import PostStatus

NOW = timezone.now()


def post(**overrides):
    fields = {
        "is_emergency": True,
        "emergency_demoted_at": None,
        "emergency_expires_at": NOW + timedelta(hours=1),
        "status": PostStatus.PENDING,
        "deleted_at": None,
    }
    return SimpleNamespace(**{**fields, **overrides})


def test_a_live_emergency_is_active():
    assert is_active_emergency(post(), NOW)


@pytest.mark.parametrize(
    "status", ["pending", "verified_true", "verified_false", "under_review", "published"]
)
def test_every_status_but_removed_keeps_the_priority(status):
    assert is_active_emergency(post(status=status), NOW)


@pytest.mark.parametrize(
    "overrides",
    [
        {"is_emergency": False},
        {"emergency_demoted_at": NOW - timedelta(minutes=1)},
        {"emergency_expires_at": NOW - timedelta(seconds=1)},
        {"emergency_expires_at": NOW},
        {"emergency_expires_at": None},
        {"status": PostStatus.REMOVED},
        {"deleted_at": NOW - timedelta(minutes=1)},
    ],
    ids=[
        "not_emergency",
        "demoted",
        "expired",
        "expires_this_instant",
        "no_expiry",
        "removed",
        "deleted",
    ],
)
def test_it_is_not_active(overrides):
    assert not is_active_emergency(post(**overrides), NOW)


def test_it_expires_at_the_exact_second():
    expires = NOW + timedelta(hours=24)
    assert is_active_emergency(
        post(emergency_expires_at=expires), expires - timedelta(microseconds=1)
    )
    assert not is_active_emergency(post(emergency_expires_at=expires), expires)


# ---------- Part 11C: the query twin (one rule in two forms) ----------


@pytest.mark.django_db
def test_the_query_and_the_python_rule_agree_on_every_state_the_database_allows():
    """Every emergency shape the checks accept, crossed with every status, deletion and both sides
    of the expiry: `active_emergency_q` and `is_active_emergency` must pick the same posts."""
    from apps.accounts.tests.factories import UserFactory
    from apps.posts.emergency import active_emergency_q
    from apps.posts.models import Post, PostType

    author = UserFactory()
    now = timezone.now()
    rows = []
    shapes = [
        (False, None, None),
        (True, now + timedelta(hours=1), None),  # active (unless removed or deleted)
        (True, now + timedelta(microseconds=1), None),
        (True, now, None),  # expires this very instant
        (True, now - timedelta(seconds=1), None),
        (True, now + timedelta(hours=1), now - timedelta(minutes=1)),  # demoted
        (True, now - timedelta(hours=1), now - timedelta(hours=2)),
    ]
    for post_type, status, shape, deleted in itertools.product(
        PostType.values, PostStatus.values, shapes, [False, True]
    ):
        is_emergency, expires, demoted = shape
        if post_type == PostType.OPINION and (
            is_emergency or status not in ("published", "under_review", "removed")
        ):
            continue
        if post_type == PostType.FACT and status == PostStatus.PUBLISHED:
            continue
        rows.append(
            Post(
                author=author,
                content="x",
                post_type=post_type,
                status=status,
                is_emergency=is_emergency,
                emergency_expires_at=expires,
                emergency_demoted_at=demoted,
                deleted_at=now if deleted else None,
                review_started_at=now if status == PostStatus.UNDER_REVIEW else None,
                created_at=now,
            )
        )
    Post.objects.bulk_create(rows)
    in_query = set(Post.objects.filter(active_emergency_q(now)).values_list("id", flat=True))
    in_python = {post.id for post in Post.objects.all() if is_active_emergency(post, now)}
    assert in_query == in_python
    # Two of the shapes are active, on every fact status but removed, when not deleted.
    assert len(in_query) == 2 * 4
    # `exclude` is the exact complement (the nullable columns don't leak through a NOT).
    outside = set(Post.objects.exclude(active_emergency_q(now)).values_list("id", flat=True))
    assert outside == set(Post.objects.values_list("id", flat=True)) - in_query


# ---------- Part 11C: who may post an emergency (§4b) ----------

CFG = SimpleNamespace(
    emergency_min_account_age_days=7,
    emergency_min_reputation=40,
    emergency_posts_per_day=1,
)
CREATED = NOW - timedelta(days=30)


def person(**overrides):
    fields = {
        "is_email_verified": True,
        "created_at": CREATED,
        "reputation_score": 50,
        "emergency_blocked_until": None,
    }
    return SimpleNamespace(**{**fields, **overrides})


def quota(*, emergency_times=(), remaining=5, next_slot_at=None):
    return SimpleNamespace(
        emergency_times=list(emergency_times), remaining=remaining, next_slot_at=next_slot_at
    )


def why(user=None, *, q=None, cfg=CFG, now=NOW):
    from apps.posts.emergency import refusal

    return refusal(user or person(), quota=q or quota(), cfg=cfg, now=now)


def test_an_eligible_person_may_post_an_emergency():
    assert why() is None


def test_each_reason_with_its_next_allowed_time():
    from apps.posts.emergency import EmergencyReason as R
    from apps.posts.emergency import EmergencyRefusal

    young = NOW - timedelta(days=2)
    blocked = NOW + timedelta(days=10)
    used = NOW - timedelta(hours=3)
    slot = NOW + timedelta(hours=4)
    assert why(person(is_email_verified=False)) == EmergencyRefusal(R.UNVERIFIED, None)
    assert why(person(created_at=young)) == EmergencyRefusal(
        R.ACCOUNT_TOO_NEW, young + timedelta(days=7)
    )
    assert why(person(reputation_score=39)) == EmergencyRefusal(R.SCORE_TOO_LOW, None)
    assert why(person(emergency_blocked_until=blocked)) == EmergencyRefusal(R.BLOCKED, blocked)
    assert why(q=quota(emergency_times=[used])) == EmergencyRefusal(
        R.DAILY_LIMIT, used + timedelta(hours=24)
    )
    assert why(q=quota(remaining=0, next_slot_at=slot)) == EmergencyRefusal(R.FACT_QUOTA, slot)


def test_the_first_failing_rule_wins_in_the_order_of_the_table():
    from apps.posts.emergency import EmergencyReason as R

    everything = person(
        is_email_verified=False,
        created_at=NOW,
        reputation_score=0,
        emergency_blocked_until=NOW + timedelta(days=1),
    )
    full = quota(emergency_times=[NOW - timedelta(hours=1)], remaining=0, next_slot_at=NOW)
    order = []
    user, q = everything, full
    for reason, fix in [
        (R.UNVERIFIED, {"is_email_verified": True}),
        (R.ACCOUNT_TOO_NEW, {"created_at": CREATED}),
        (R.SCORE_TOO_LOW, {"reputation_score": 40}),
        (R.BLOCKED, {"emergency_blocked_until": None}),
    ]:
        got = why(user, q=q)
        order.append(got.reason)
        assert got.reason == reason
        user = SimpleNamespace(**{**vars(user), **fix})
    assert why(user, q=q).reason == R.DAILY_LIMIT
    q = quota(remaining=0, next_slot_at=NOW)
    assert why(user, q=q).reason == R.FACT_QUOTA
    assert why(user, q=quota()) is None
    assert order == [R.UNVERIFIED, R.ACCOUNT_TOO_NEW, R.SCORE_TOO_LOW, R.BLOCKED]


def test_the_edges_are_inclusive_where_the_table_says_so():
    from apps.posts.emergency import EmergencyReason as R

    # Exactly 7 days old passes; a microsecond younger doesn't.
    assert why(person(created_at=NOW - timedelta(days=7))) is None
    too_new = why(person(created_at=NOW - timedelta(days=7) + timedelta(microseconds=1)))
    assert too_new.reason == R.ACCOUNT_TOO_NEW
    # A score exactly at the minimum passes.
    assert why(person(reputation_score=40)) is None
    # A block ending now is over; one ending a microsecond later still holds.
    assert why(person(emergency_blocked_until=NOW)) is None
    assert why(person(emergency_blocked_until=NOW - timedelta(days=1))) is None
    later = NOW + timedelta(microseconds=1)
    assert why(person(emergency_blocked_until=later)).reason == R.BLOCKED


def test_the_account_age_and_the_score_come_from_the_settings():
    from apps.posts.emergency import EmergencyReason as R

    strict = SimpleNamespace(**{**vars(CFG), "emergency_min_account_age_days": 60})
    assert why(cfg=strict).reason == R.ACCOUNT_TOO_NEW
    open_door = SimpleNamespace(
        **{**vars(CFG), "emergency_min_account_age_days": 0, "emergency_min_reputation": 0}
    )
    assert why(person(created_at=NOW, reputation_score=0), cfg=open_door) is None
    picky = SimpleNamespace(**{**vars(CFG), "emergency_min_reputation": 51})
    assert why(cfg=picky).reason == R.SCORE_TOO_LOW


def test_the_daily_limit_counts_the_emergencies_it_is_given_and_frees_the_oldest_needed():
    from apps.posts.emergency import EmergencyReason as R

    times = [NOW - timedelta(hours=h) for h in (20, 10, 2)]  # oldest first
    two = SimpleNamespace(**{**vars(CFG), "emergency_posts_per_day": 2})
    got = why(q=quota(emergency_times=times[1:]), cfg=two)
    assert (got.reason, got.next_allowed_at) == (R.DAILY_LIMIT, times[1] + timedelta(hours=24))
    assert why(q=quota(emergency_times=times[2:]), cfg=two) is None
    # A lowered limit: three used, a limit of one: the newest must age out (3 - 1 + 1 = the 3rd).
    got = why(q=quota(emergency_times=times))
    assert got.next_allowed_at == times[2] + timedelta(hours=24)


def test_a_limit_of_zero_pauses_emergencies_with_no_time_to_wait_for():
    from apps.posts.emergency import EmergencyReason as R
    from apps.posts.emergency import EmergencyRefusal

    paused = SimpleNamespace(**{**vars(CFG), "emergency_posts_per_day": 0})
    assert why(cfg=paused) == EmergencyRefusal(R.DAILY_LIMIT, None)


def test_paused_fact_posts_refuse_an_emergency_with_no_time_to_wait_for():
    from apps.posts.emergency import EmergencyReason as R
    from apps.posts.emergency import EmergencyRefusal

    assert why(q=quota(remaining=0, next_slot_at=None)) == EmergencyRefusal(R.FACT_QUOTA, None)


@pytest.mark.parametrize(
    ("refused", "words"),
    [
        (("unverified", None), "Verify your email"),
        (("account_too_new", NOW), "too new"),
        (("score_too_low", None), "below 40"),
        (("blocked", NOW), "blocked on your account until"),
        (("daily_limit", NOW), "You've posted 1 emergency post in the last 24 hours"),
        (("daily_limit", None), "Emergency posts are paused right now."),
        (("fact_quota", NOW), "used all your fact posts"),
        (("fact_quota", None), "Fact posts are paused right now"),
    ],
)
def test_every_refusal_has_plain_words(refused, words):
    from apps.posts.emergency import EmergencyReason, EmergencyRefusal, refusal_text

    reason, at = refused
    text = refusal_text(EmergencyRefusal(EmergencyReason(reason), at), CFG)
    assert words in text
    assert "debunk" not in text.lower()
    if at is not None:
        assert "UTC" in text
