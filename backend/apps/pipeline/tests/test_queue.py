"""The queue (ARCHITECTURE §6): which posts are owed a check, when they are due, in what order,
and that a reported post leaves the queue whatever its check ends with."""

import itertools
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.tests.factories import UserFactory
from apps.pipeline import processor
from apps.pipeline.routing import awaiting_check_q, is_awaiting_check
from apps.pipeline.tests.conftest import answering, fact, failing, reported_fact
from apps.posts.models import FlaggedReason, Post, PostStatus, PostType, VerdictSource

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("pipeline_cfg")]


def test_the_query_and_the_python_guard_agree_on_every_state_the_database_allows():
    """Every combination of type, status, reason, pre-review status, source and deletion that the
    checks accept: the queue's `Q` and the apply guard must pick exactly the same posts."""
    author = UserFactory()
    now = timezone.now()
    rows = []
    for post_type, status, flag, pre, source, deleted in itertools.product(
        PostType.values,
        PostStatus.values,
        [None, *FlaggedReason.values],
        [None, *PostStatus.values],
        [None, *VerdictSource.values],
        [False, True],
    ):
        if post_type == PostType.OPINION and status not in ("published", "under_review", "removed"):
            continue
        if post_type == PostType.FACT and status == PostStatus.PUBLISHED:
            continue
        rows.append(
            Post(
                author=author,
                content="x",
                post_type=post_type,
                status=status,
                flagged_reason=flag,
                pre_review_status=pre,
                verdict_source=source,
                deleted_at=now if deleted else None,
                # The database holds this to "set exactly while under review".
                review_started_at=now if status == PostStatus.UNDER_REVIEW else None,
                created_at=now,
            )
        )
    Post.objects.bulk_create(rows)
    in_query = set(Post.objects.filter(awaiting_check_q()).values_list("id", flat=True))
    in_python = {post.id for post in Post.objects.all() if is_awaiting_check(post)}
    assert in_query == in_python
    # Only the two documented shapes are owed a check.
    shapes = {
        (p.status, p.flagged_reason, p.pre_review_status)
        for p in Post.objects.filter(id__in=in_query)
    }
    assert shapes == {
        (PostStatus.PENDING, flag, pre)
        for flag in [None, *FlaggedReason.values]
        for pre in [None, *PostStatus.values]
    } | {(PostStatus.UNDER_REVIEW, FlaggedReason.REPORTS, PostStatus.PENDING)}


def test_a_post_is_due_with_no_next_try_or_once_its_time_has_come():
    now = timezone.now()
    never = fact("never tried", age_seconds=50)
    past = fact("past", age_seconds=40, pipeline_next_attempt_at=now - timedelta(seconds=1))
    exact = fact("exact", age_seconds=30, pipeline_next_attempt_at=now)
    future = fact("future", age_seconds=20, pipeline_next_attempt_at=now + timedelta(seconds=1))
    assert list(processor.due_posts(now)) == [never, past, exact]
    assert future not in processor.due_posts(now)


def test_active_emergencies_come_first_then_the_oldest():
    """Part 11C: only an *active* emergency jumps the queue; an expired or demoted one waits its
    turn by age like any other post."""
    now = timezone.now()
    old = fact("old", age_seconds=300)
    new = fact("new", age_seconds=10)
    active = fact(
        "active", age_seconds=5, is_emergency=True, emergency_expires_at=now + timedelta(hours=24)
    )
    newer_active = fact(
        "newer active",
        age_seconds=2,
        is_emergency=True,
        emergency_expires_at=now + timedelta(hours=24),
    )
    expired = fact(
        "expired", age_seconds=400, is_emergency=True, emergency_expires_at=now - timedelta(1)
    )
    demoted = fact(
        "demoted",
        age_seconds=250,
        is_emergency=True,
        emergency_expires_at=now + timedelta(hours=24),
        emergency_demoted_at=now - timedelta(minutes=1),
    )
    reported = reported_fact("reported", created_at=now - timedelta(seconds=200))
    assert list(processor.due_posts(now)) == [
        active,
        newer_active,
        expired,
        old,
        demoted,
        reported,
        new,
    ]


def test_an_emergency_leaves_the_front_of_the_queue_when_its_time_is_up():
    now = timezone.now()
    old = fact("old", age_seconds=300)
    expires = now + timedelta(hours=1)
    emergency = fact("emergency", age_seconds=5, is_emergency=True, emergency_expires_at=expires)
    assert list(processor.due_posts(expires - timedelta(microseconds=1))) == [emergency, old]
    assert list(processor.due_posts(expires)) == [old, emergency]


def test_the_processor_checks_an_active_emergency_before_older_posts():
    now = timezone.now()
    old = fact("old", age_seconds=300)
    emergency = fact(
        "emergency", age_seconds=5, is_emergency=True, emergency_expires_at=now + timedelta(1)
    )
    client = answering("true", 95)
    assert processor.process_pending(limit=1, client=client, now=now) == 1
    assert client.post_ids == [emergency.pk]
    assert processor.process_pending(limit=1, client=client, now=now) == 1
    assert client.post_ids == [emergency.pk, old.pk]


def test_ties_on_the_time_are_ordered_by_id():
    when = timezone.now() - timedelta(minutes=1)
    posts = [fact(f"tie {n}", created_at=when) for n in range(4)]
    assert list(processor.due_posts(timezone.now())) == sorted(posts, key=lambda p: p.pk)


LATE_ENDINGS = {
    "late true": answering("true", 95),
    "late false": answering("false", 92),
    "late weak": answering("inconclusive", 99),
}


@pytest.mark.parametrize("client", LATE_ENDINGS.values(), ids=LATE_ENDINGS.keys())
def test_a_reported_post_leaves_the_queue_whatever_its_check_ends_with(client):
    post = reported_fact()
    assert processor.process_pending(client=client) == 1
    later = timezone.now() + timedelta(days=1)
    assert processor.process_pending(client=client, now=later) == 0
    assert client.post_ids == [post.pk]


def test_a_reported_post_leaves_the_queue_when_the_pipeline_gives_up():
    post = reported_fact()
    client = failing()
    when = timezone.now()
    for _ in range(5):
        when += timedelta(hours=1)  # past every backoff
        assert processor.process_pending(client=client, now=when) == 1
    after = Post.objects.get(pk=post.pk)
    assert after.flagged_reason == FlaggedReason.BOTH
    assert processor.process_pending(client=client, now=when + timedelta(days=1)) == 0
    assert len(client.requests) == 5
