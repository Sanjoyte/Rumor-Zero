import time
from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.accounts.tests.conftest import run_together
from apps.posts import services
from apps.posts.models import Post, PostStatus, PostType
from apps.posts.services import (
    FactPostsPaused,
    FactQuotaExceeded,
    create_post,
    fact_quota,
)
from apps.posts.tests.factories import PostFactory, VerifiedUserFactory

pytestmark = pytest.mark.django_db

DAY = timedelta(hours=24)


@pytest.fixture
def author(fact_limit):
    return VerifiedUserFactory()


def fact_posts(author, count, *, age=timedelta(hours=1), **traits):
    """`count` fact posts, each made a little earlier than the one before, all within `age`+."""
    now = timezone.now()
    return [
        PostFactory(author=author, fact=True, created_at=now - age - timedelta(seconds=i), **traits)
        for i in range(count)
    ]


# ---------- creating ----------


def test_an_opinion_is_published_at_once(author):
    now = timezone.now()
    post = create_post(author=author, content="I like rain", post_type=PostType.OPINION, now=now)
    assert post.status == PostStatus.PUBLISHED
    assert post.post_type == PostType.OPINION
    assert post.created_at == now
    assert post.sources == []


def test_a_fact_waits_for_the_pipeline(author):
    post = create_post(author=author, content="Water boils at 100C", post_type=PostType.FACT)
    assert post.status == PostStatus.PENDING


def test_sources_are_stored_in_the_order_given(author):
    sources = ["https://z.example/", "10.1000/a", "https://a.example/"]
    post = create_post(author=author, content="Claim", post_type=PostType.FACT, sources=sources)
    assert Post.objects.get(pk=post.pk).sources == sources


def test_a_fact_without_sources_is_fine(author):
    post = create_post(author=author, content="Claim", post_type=PostType.FACT, sources=())
    assert post.sources == []


def test_an_opinion_with_sources_is_refused(author):
    with pytest.raises(ValidationError):
        create_post(author=author, content="x", post_type=PostType.OPINION, sources=["10.1/x"])
    assert not Post.objects.exists()


def test_an_emergency_opinion_is_refused_before_anything_is_written(author):
    with pytest.raises(ValidationError) as exc:
        create_post(author=author, content="x", post_type=PostType.OPINION, is_emergency=True)
    assert exc.value.message_dict == {"is_emergency": ["Only fact posts can be emergencies."]}
    assert not Post.objects.exists()


# ---------- the rolling 24-hour fact quota ----------


def test_the_tenth_fact_post_passes_and_the_eleventh_is_refused(author):
    now = timezone.now()
    for i in range(10):
        create_post(
            author=author,
            content=f"Claim {i}",
            post_type=PostType.FACT,
            now=now - timedelta(hours=5) + timedelta(minutes=i),
        )
    with pytest.raises(FactQuotaExceeded) as exc:
        create_post(author=author, content="One too many", post_type=PostType.FACT, now=now)
    assert exc.value.limit == 10
    # The oldest of the ten frees the first slot, 24 h after it was made.
    assert exc.value.next_slot_at == now - timedelta(hours=5) + DAY
    assert Post.objects.count() == 10


def test_opinions_never_use_the_quota(author):
    for i in range(12):
        create_post(author=author, content=f"Opinion {i}", post_type=PostType.OPINION)
    assert create_post(author=author, content="Claim", post_type=PostType.FACT)


def test_a_post_exactly_24_hours_old_no_longer_counts(author):
    now = timezone.now()
    PostFactory(author=author, fact=True, created_at=now - DAY)
    quota = fact_quota(author, now=now)
    assert (quota.used, quota.remaining) == (0, 10)


def test_a_post_a_microsecond_younger_than_24_hours_counts(author):
    now = timezone.now()
    PostFactory(author=author, fact=True, created_at=now - DAY + timedelta(microseconds=1))
    assert fact_quota(author, now=now).used == 1


def test_deleted_and_removed_fact_posts_still_count(author):
    fact_posts(author, 5, deleted=True)
    fact_posts(author, 5, age=timedelta(hours=2), removed=True)
    quota = fact_quota(author, now=timezone.now())
    assert (quota.used, quota.remaining) == (10, 0)
    with pytest.raises(FactQuotaExceeded):
        create_post(author=author, content="Again", post_type=PostType.FACT)


def test_other_people_and_other_kinds_do_not_count(author):
    PostFactory.create_batch(3, author=author)  # opinions
    PostFactory.create_batch(4, fact=True)  # someone else's facts
    assert fact_quota(author, now=timezone.now()).used == 0


def test_the_quota_frees_up_as_posts_age_out(author):
    now = timezone.now()
    fact_posts(author, 10, age=timedelta(hours=23, minutes=59))
    assert fact_quota(author, now=now).remaining == 0
    assert fact_quota(author, now=now + timedelta(minutes=2)).remaining >= 1


def test_the_quota_shape(author):
    now = timezone.now()
    oldest = now - timedelta(hours=3)
    PostFactory(author=author, fact=True, created_at=oldest)
    PostFactory(author=author, fact=True, created_at=now - timedelta(hours=1))
    quota = fact_quota(author, now=now)
    assert (quota.limit, quota.used, quota.remaining, quota.next_slot_at) == (10, 2, 8, None)


def test_next_slot_is_when_the_oldest_post_ages_out(author):
    now = timezone.now()
    times = [now - timedelta(hours=h) for h in (10, 8, 6, 4, 2, 1, 1, 1, 1, 1)]
    for created in times:
        PostFactory(author=author, fact=True, created_at=created)
    quota = fact_quota(author, now=now)
    assert quota.remaining == 0
    assert quota.next_slot_at == times[0] + DAY


def test_a_lowered_limit_waits_for_enough_posts_to_age_out(author, fact_limit):
    now = timezone.now()
    times = [now - timedelta(hours=h) for h in (20, 18, 16, 14, 12, 10, 8, 6)]  # eight posts
    for created in times:
        PostFactory(author=author, fact=True, created_at=created)
    fact_limit(5)
    quota = fact_quota(author, now=now)
    assert (quota.used, quota.remaining) == (8, 0)
    # Back under the limit needs 4 of them gone: the 4th oldest, plus 24 h.
    assert quota.next_slot_at == times[3] + DAY


def test_a_limit_of_zero_pauses_fact_posts(author, fact_limit):
    fact_limit(0)
    quota = fact_quota(author, now=timezone.now())
    assert (quota.limit, quota.remaining, quota.next_slot_at) == (0, 0, None)
    with pytest.raises(FactPostsPaused):
        create_post(author=author, content="Claim", post_type=PostType.FACT)
    # Opinions are unaffected.
    assert create_post(author=author, content="Opinion", post_type=PostType.OPINION)


def test_a_failed_create_leaves_no_row(author):
    fact_posts(author, 10)
    before = Post.objects.count()
    with pytest.raises(FactQuotaExceeded):
        create_post(author=author, content="x", post_type=PostType.FACT)
    assert Post.objects.count() == before


def test_the_quota_is_one_query_once_the_settings_are_cached(author, django_assert_num_queries):
    fact_quota(author, now=timezone.now())  # warms the platform-settings cache
    with django_assert_num_queries(1):
        fact_quota(author, now=timezone.now())


# ---------- locking ----------


def sql(queries):
    return [query["sql"] for query in queries]


def test_a_fact_post_locks_the_author_row(author):
    """`FOR NO KEY UPDATE` since Part 11C (Part 11B's rule for every user lock): it still
    serialises two posts, a block and the ledger, not every insert that points at the author."""
    with CaptureQueriesContext(connection) as queries:
        create_post(author=author, content="Claim", post_type=PostType.FACT)
    locks = [q for q in sql(queries) if "FOR" in q and "accounts_user" in q]
    assert len(locks) == 1 and "FOR NO KEY UPDATE" in locks[0]


def test_an_opinion_takes_no_lock(author):
    with CaptureQueriesContext(connection) as queries:
        create_post(author=author, content="Opinion", post_type=PostType.OPINION)
    assert not any("FOR UPDATE" in q for q in sql(queries))


@pytest.fixture
def slow_count(monkeypatch):
    """Hold each fact post between counting and inserting, so a second one can collide."""
    original = services._fact_post_times

    def slow(author, since):
        result = original(author, since)
        time.sleep(0.3)
        return result

    monkeypatch.setattr(services, "_fact_post_times", slow)


def try_post(author):
    def attempt():
        try:
            create_post(author=author, content="Racing claim", post_type=PostType.FACT)
        except FactQuotaExceeded:
            return "refused"
        return "created"

    return attempt


@pytest.mark.django_db(transaction=True)
def test_two_simultaneous_fact_posts_at_nine_of_ten_let_exactly_one_through(fact_limit, slow_count):
    author = VerifiedUserFactory()
    fact_posts(author, 9)
    results = run_together(try_post(author), try_post(author))
    assert sorted(results) == ["created", "refused"]
    assert Post.objects.filter(author=author, post_type=PostType.FACT).count() == 10


@pytest.mark.django_db(transaction=True)
def test_without_the_lock_both_get_through_which_is_what_it_prevents(
    fact_limit, slow_count, monkeypatch
):
    monkeypatch.setattr(services, "_lock_author", lambda author: author)
    author = VerifiedUserFactory()
    fact_posts(author, 9)
    results = run_together(try_post(author), try_post(author))
    assert results == ["created", "created"]
    assert Post.objects.filter(author=author, post_type=PostType.FACT).count() == 11


# ---------- Part 11C: emergency posts (§4b) ----------


@pytest.fixture
def elder(fact_limit):
    """An author who may post an emergency: verified, 30 days old, the starting score."""
    return VerifiedUserFactory(created_at=timezone.now() - timedelta(days=30))


def emergency(author, content="Flood warning for the river district", **kwargs):
    return create_post(
        author=author, content=content, post_type=PostType.FACT, is_emergency=True, **kwargs
    )


def test_an_emergency_stores_its_expiry_24_hours_after_it_was_made(elder):
    now = timezone.now()
    post = emergency(elder, now=now)
    stored = Post.objects.get(pk=post.pk)
    assert stored.is_emergency is True
    assert stored.emergency_expires_at == now + timedelta(hours=24)
    assert stored.emergency_demoted_at is None
    assert stored.status == PostStatus.PENDING


def test_the_duration_comes_from_the_settings(elder, emergency_settings):
    emergency_settings(emergency_duration_hours=6)
    now = timezone.now()
    assert emergency(elder, now=now).emergency_expires_at == now + timedelta(hours=6)


def test_a_plain_fact_has_no_expiry(elder):
    post = create_post(author=elder, content="Claim", post_type=PostType.FACT)
    assert (post.is_emergency, post.emergency_expires_at) == (False, None)


def test_an_emergency_counts_toward_the_fact_quota(elder, fact_limit):
    fact_limit(2)
    emergency(elder)
    quota = fact_quota(elder)
    assert (quota.used, quota.remaining, len(quota.emergency_times)) == (1, 1, 1)


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"is_email_verified": False}, "unverified"),
        ({"created_at_days": 2}, "account_too_new"),
        ({"reputation_score": 39}, "score_too_low"),
        ({"blocked_days": 3}, "blocked"),
    ],
)
def test_each_account_rule_refuses_through_the_service_and_writes_nothing(elder, change, reason):
    from apps.accounts.models import User

    now = timezone.now()
    fields = {}
    if "is_email_verified" in change:
        fields["is_email_verified"] = False
    if "created_at_days" in change:
        fields["created_at"] = now - timedelta(days=change["created_at_days"])
    if "reputation_score" in change:
        fields["reputation_score"] = change["reputation_score"]
    if "blocked_days" in change:
        fields["emergency_blocked_until"] = now + timedelta(days=change["blocked_days"])
    User.objects.filter(pk=elder.pk).update(**fields)
    with pytest.raises(services.EmergencyNotAllowed) as exc:
        emergency(elder, now=now)
    assert exc.value.reason == reason
    assert not Post.objects.exists()


def test_the_daily_limit_counts_deleted_and_removed_emergencies(elder):
    now = timezone.now()
    gone = emergency(elder, now=now - timedelta(hours=3))
    Post.objects.filter(pk=gone.pk).update(deleted_at=now - timedelta(hours=2))
    with pytest.raises(services.EmergencyNotAllowed) as exc:
        emergency(elder, content="Another warning", now=now)
    assert exc.value.reason == "daily_limit"
    assert exc.value.next_allowed_at == now - timedelta(hours=3) + timedelta(hours=24)
    Post.objects.filter(pk=gone.pk).update(deleted_at=None, status=PostStatus.REMOVED)
    with pytest.raises(services.EmergencyNotAllowed):
        emergency(elder, content="Another warning", now=now)


def test_an_emergency_24_hours_old_no_longer_counts(elder):
    now = timezone.now()
    emergency(elder, now=now - timedelta(hours=24))
    assert emergency(elder, content="The next day", now=now)


def test_a_full_fact_quota_refuses_an_emergency_with_its_own_reason(elder, fact_limit):
    fact_limit(1)
    now = timezone.now()
    create_post(author=elder, content="A plain claim", post_type=PostType.FACT, now=now)
    with pytest.raises(services.EmergencyNotAllowed) as exc:
        emergency(elder, now=now)
    assert exc.value.reason == "fact_quota"
    assert exc.value.next_allowed_at == now + timedelta(hours=24)


def test_paused_fact_posts_refuse_an_emergency_with_no_time(elder, fact_limit):
    fact_limit(0)
    with pytest.raises(services.EmergencyNotAllowed) as exc:
        emergency(elder)
    assert (exc.value.reason, exc.value.next_allowed_at) == ("fact_quota", None)


def test_paused_emergencies_refuse_with_no_time(elder, emergency_settings):
    emergency_settings(emergency_posts_per_day=0)
    with pytest.raises(services.EmergencyNotAllowed) as exc:
        emergency(elder)
    assert (exc.value.reason, exc.value.next_allowed_at) == ("daily_limit", None)
    assert exc.value.text == "Emergency posts are paused right now."


def test_the_lock_reads_a_block_committed_after_the_author_was_loaded(elder):
    """The view's `request.user` was loaded before a moderator's block (or a Mark FALSE)
    committed: the service decides on the locked, fresh row."""
    from apps.accounts.models import User

    stale = User.objects.get(pk=elder.pk)
    User.objects.filter(pk=elder.pk).update(
        emergency_blocked_until=timezone.now() + timedelta(days=30)
    )
    assert stale.emergency_blocked_until is None
    with pytest.raises(services.EmergencyNotAllowed) as exc:
        emergency(stale)
    assert exc.value.reason == "blocked"


def test_the_database_refuses_an_emergency_opinion_too():
    from django.db import IntegrityError, transaction

    with pytest.raises(IntegrityError) as exc, transaction.atomic():
        PostFactory(is_emergency=True, emergency_expires_at=timezone.now() + timedelta(hours=24))
    assert exc.value.__cause__.diag.constraint_name == "posts_post_emergency_fact_only"


def try_emergency(author):
    def attempt():
        try:
            emergency(author)
        except services.EmergencyNotAllowed as exc:
            return f"refused:{exc.reason}"
        return "created"

    return attempt


@pytest.mark.django_db(transaction=True)
def test_two_emergencies_at_once_let_exactly_one_through(
    fact_limit, emergency_settings, slow_count
):
    author = VerifiedUserFactory(created_at=timezone.now() - timedelta(days=30))
    results = run_together(try_emergency(author), try_emergency(author))
    assert sorted(results) == ["created", "refused:daily_limit"]
    assert Post.objects.filter(author=author, is_emergency=True).count() == 1


@pytest.mark.django_db(transaction=True)
def test_without_the_lock_two_emergencies_both_get_through(
    fact_limit, emergency_settings, slow_count, monkeypatch
):
    monkeypatch.setattr(services, "_lock_author", lambda author: author)
    author = VerifiedUserFactory(created_at=timezone.now() - timedelta(days=30))
    results = run_together(try_emergency(author), try_emergency(author))
    assert results == ["created", "created"]
