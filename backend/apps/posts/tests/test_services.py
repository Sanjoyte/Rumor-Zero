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
    EmergencyUnavailable,
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


@pytest.mark.parametrize("post_type", [PostType.OPINION, PostType.FACT])
def test_an_emergency_is_refused_before_anything_is_written(author, post_type):
    with pytest.raises(EmergencyUnavailable):
        create_post(author=author, content="x", post_type=post_type, is_emergency=True)
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
    with CaptureQueriesContext(connection) as queries:
        create_post(author=author, content="Claim", post_type=PostType.FACT)
    assert any("FOR UPDATE" in q and "accounts_user" in q for q in sql(queries))


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
    monkeypatch.setattr(services, "_lock_author", lambda author: None)
    author = VerifiedUserFactory()
    fact_posts(author, 9)
    results = run_together(try_post(author), try_post(author))
    assert results == ["created", "created"]
    assert Post.objects.filter(author=author, post_type=PostType.FACT).count() == 11
