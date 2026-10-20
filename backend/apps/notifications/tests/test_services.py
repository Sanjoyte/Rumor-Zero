"""`notify()` and the helpers (ARCHITECTURE §2, §9)."""

from datetime import timedelta

import pytest
from django.db import IntegrityError, connection, transaction
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.notifications import services
from apps.notifications.models import Notification, NotificationOutcome, NotificationType
from apps.notifications.tests.factories import NotificationFactory
from apps.posts.models import PostStatus
from apps.posts.tests.factories import PostFactory, VerifiedUserFactory

pytestmark = pytest.mark.django_db


def test_notify_writes_the_item():
    post = PostFactory()
    fan = VerifiedUserFactory()
    now = timezone.now()
    services.liked(user=fan, post=post, now=now)
    item = Notification.objects.get()
    assert (item.type, item.recipient_id, item.actor_id, item.post_id) == (
        NotificationType.LIKE,
        post.author_id,
        fan.pk,
        post.pk,
    )
    assert item.comment_id is None
    assert item.outcome == ""
    assert item.is_read is False
    assert item.created_at == now


def test_notify_to_yourself_writes_nothing():
    post = PostFactory()
    assert services.liked(user=post.author, post=post) is None
    assert Notification.objects.count() == 0


def test_the_same_like_twice_is_one_item():
    post = PostFactory()
    fan = VerifiedUserFactory()
    services.liked(user=fan, post=post)
    services.liked(user=fan, post=post)
    assert Notification.objects.count() == 1


def test_a_like_and_a_repost_of_one_post_are_two_items():
    post = PostFactory()
    fan = VerifiedUserFactory()
    services.liked(user=fan, post=post)
    services.reposted(user=fan, post=post)
    assert sorted(Notification.objects.values_list("type", flat=True)) == ["like", "repost"]


def test_the_same_follow_twice_is_one_item():
    me, fan = VerifiedUserFactory(), VerifiedUserFactory()
    services.followed(follower=fan, target=me)
    services.followed(follower=fan, target=me)
    assert Notification.objects.count() == 1


def test_a_check_violation_still_raises_through_the_quiet_insert():
    """`ON CONFLICT DO NOTHING` swallows only unique conflicts: a wrong shape is a bug."""
    with pytest.raises(IntegrityError), transaction.atomic():
        services.notify(
            type=NotificationType.FOLLOW,
            recipient_id=VerifiedUserFactory().pk,
            actor_id=VerifiedUserFactory().pk,
            post_id=PostFactory().pk,
        )


@pytest.mark.django_db(transaction=True)
def test_notify_refuses_to_run_outside_a_transaction():
    recipient, actor = VerifiedUserFactory(), VerifiedUserFactory()
    with pytest.raises(RuntimeError, match="inside the caller's transaction"):
        services.notify(type=NotificationType.FOLLOW, recipient_id=recipient.pk, actor_id=actor.pk)
    assert Notification.objects.count() == 0
    with transaction.atomic():
        services.notify(type=NotificationType.FOLLOW, recipient_id=recipient.pk, actor_id=actor.pk)
    assert Notification.objects.count() == 1


@pytest.mark.django_db(transaction=True)
def test_notify_works_inside_a_durable_block():
    recipient, actor = VerifiedUserFactory(), VerifiedUserFactory()
    with transaction.atomic(durable=True):
        services.followed(follower=actor, target=recipient)
    assert Notification.objects.count() == 1


def test_a_verdict_stores_true_or_false():
    post = PostFactory(fact=True)
    services.verdict_reached(post=post, label=PostStatus.VERIFIED_TRUE)
    services.verdict_reached(post=post, label=PostStatus.VERIFIED_FALSE)
    assert sorted(Notification.objects.values_list("outcome", flat=True)) == ["false", "true"]
    assert set(Notification.objects.values_list("actor_id", flat=True)) == {None}


def test_the_moderation_helpers_have_no_actor_and_the_posts_author_as_recipient():
    post = PostFactory(fact=True)
    services.entered_review(post=post)
    services.removed(post=post)
    services.emergency_demoted(post=post)
    assert set(Notification.objects.values_list("recipient_id", flat=True)) == {post.author_id}
    assert set(Notification.objects.values_list("actor_id", flat=True)) == {None}
    assert sorted(Notification.objects.values_list("type", flat=True)) == [
        "emergency_demoted",
        "removed",
        "under_review",
    ]


def test_appeal_resolved_goes_to_the_appeals_author_with_its_status():
    from apps.moderation.models import AppealStatus
    from apps.moderation.tests.factories import AppealFactory

    appeal = AppealFactory(status=AppealStatus.OPEN)
    appeal.status = AppealStatus.OVERTURNED
    services.appeal_resolved(post=appeal.post, appeal=appeal)
    item = Notification.objects.get()
    assert item.recipient_id == appeal.author_id
    assert item.outcome == NotificationOutcome.OVERTURNED


def test_discard_for_post_deletes_only_that_posts_items():
    one, other = NotificationFactory(), NotificationFactory()
    services.discard_for_post(one.post_id)
    assert list(Notification.objects.values_list("pk", flat=True)) == [other.pk]


def test_discard_for_comment_deletes_only_that_comments_item():
    from apps.notifications.tests.factories import comment_item

    one = comment_item(VerifiedUserFactory(), VerifiedUserFactory())
    other = comment_item(VerifiedUserFactory(), VerifiedUserFactory())
    services.discard_for_comment(one.comment_id)
    assert list(Notification.objects.values_list("pk", flat=True)) == [other.pk]


def test_unread_count_counts_only_your_unread_items():
    me = VerifiedUserFactory()
    NotificationFactory.create_batch(3, recipient=me)
    NotificationFactory(recipient=me, is_read=True)
    NotificationFactory()
    assert services.unread_count(me) == 3


def test_unread_count_is_one_query_on_the_partial_index():
    me = VerifiedUserFactory()
    NotificationFactory.create_batch(3, recipient=me)
    with CaptureQueriesContext(connection) as queries:
        services.unread_count(me)
    assert len(queries) == 1
    # The predicate is the index's own (`is_read = false`), which is what lets Postgres use it.
    assert 'NOT "notifications_notification"."is_read"' in queries[0]["sql"]


def test_mark_read_with_ids_changes_only_those():
    me = VerifiedUserFactory()
    a, b, c = NotificationFactory.create_batch(3, recipient=me)
    assert services.mark_read(me, ids=[a.pk, b.pk]) == 1
    assert list(
        Notification.objects.filter(is_read=True).order_by("id").values_list("pk", flat=True)
    ) == sorted([a.pk, b.pk])
    c.refresh_from_db()
    assert not c.is_read


def test_mark_read_all_changes_everything_of_yours_and_nothing_of_theirs():
    me, them = VerifiedUserFactory(), VerifiedUserFactory()
    NotificationFactory.create_batch(3, recipient=me)
    theirs = NotificationFactory(recipient=them)
    assert services.mark_read(me) == 0
    assert Notification.objects.filter(recipient=me, is_read=False).count() == 0
    theirs.refresh_from_db()
    assert not theirs.is_read


def test_mark_read_ignores_other_peoples_and_unknown_ids():
    import uuid

    me, them = VerifiedUserFactory(), VerifiedUserFactory()
    mine = NotificationFactory(recipient=me)
    theirs = NotificationFactory(recipient=them)
    assert services.mark_read(me, ids=[theirs.pk, uuid.uuid4()]) == 1
    theirs.refresh_from_db()
    mine.refresh_from_db()
    assert not theirs.is_read
    assert not mine.is_read


def test_an_action_s_items_can_be_stamped_one_microsecond_apart():
    post = PostFactory(fact=True)
    now = timezone.now()
    services.removed(post=post, now=now)
    services.emergency_demoted(post=post, now=now + services.TICK)
    times = list(Notification.objects.order_by("created_at").values_list("created_at", flat=True))
    assert times[1] - times[0] == timedelta(microseconds=1)
