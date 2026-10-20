"""The moderator actions tell the post's author (Part 13) in the action's own transaction:
what each of the eight does, which items come together, and when nothing is said."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.moderation import services as moderation
from apps.moderation.models import Appeal, AppealStatus
from apps.moderation.tests.factories import AppealFactory, moderator_user
from apps.notifications.models import Notification, NotificationType
from apps.posts.models import FlaggedReason, Post, PostStatus, PostType
from apps.posts.tests.factories import PostFactory, VerifiedUserFactory
from apps.reports.tests.factories import ReportFactory

pytestmark = pytest.mark.django_db

TICK = timedelta(microseconds=1)


def reviewed(*, flag=FlaggedReason.REPORTS, pre=PostStatus.PENDING, **fields):
    """A fact under review (reports by default, as the threshold leaves it)."""
    fields.setdefault("post_type", PostType.FACT)
    post = PostFactory(
        status=PostStatus.UNDER_REVIEW,
        flagged_reason=flag,
        pre_review_status=pre,
        report_count=2,
        **fields,
    )
    ReportFactory.create_batch(2, post=post)
    return post


def emergency(**fields):
    now = timezone.now()
    return reviewed(
        is_emergency=True,
        emergency_expires_at=now + timedelta(hours=20),
        created_at=now - timedelta(hours=4),
        **fields,
    )


def sent(post=None):
    """`(type, outcome)` of every item, oldest first."""
    rows = Notification.objects.order_by("created_at", "id")
    if post is not None:
        rows = rows.filter(post=post)
    return [(row.type, row.outcome) for row in rows]


def only_for_the_author(post):
    assert set(Notification.objects.values_list("recipient_id", flat=True)) <= {post.author_id}
    assert set(Notification.objects.values_list("actor_id", flat=True)) <= {None}


# ---------- verdicts and removals ----------


def test_mark_verified_tells_the_author_it_is_true():
    post = reviewed()
    moderation.mark_verified(post.pk, moderator=moderator_user())
    assert sent() == [(NotificationType.VERDICT, "true")]
    only_for_the_author(post)


def test_mark_false_tells_the_author_it_is_false():
    post = reviewed()
    moderation.mark_false(post.pk, moderator=moderator_user())
    assert sent() == [(NotificationType.VERDICT, "false")]
    only_for_the_author(post)


def test_a_verdict_names_no_moderator():
    post = reviewed()
    moderation.mark_false(post.pk, moderator=moderator_user())
    assert Notification.objects.get().actor_id is None


def test_mark_verified_on_a_post_that_was_already_true_repeats_nothing():
    post = reviewed(pre=PostStatus.VERIFIED_TRUE)
    moderation.mark_verified(post.pk, moderator=moderator_user())
    assert Post.objects.get(pk=post.pk).status == PostStatus.VERIFIED_TRUE
    assert sent() == []


def test_mark_false_on_a_post_that_was_already_false_repeats_nothing():
    post = reviewed(pre=PostStatus.VERIFIED_FALSE, verdict_source="pipeline")
    moderation.mark_false(post.pk, moderator=moderator_user())
    assert sent() == []


def test_mark_verified_on_a_false_post_under_review_is_a_new_verdict():
    post = reviewed(pre=PostStatus.VERIFIED_FALSE, verdict_source="pipeline")
    moderation.mark_verified(post.pk, moderator=moderator_user())
    assert sent() == [(NotificationType.VERDICT, "true")]


@pytest.mark.parametrize("post_type", [PostType.FACT, PostType.OPINION])
def test_remove_tells_the_author(post_type):
    pre = PostStatus.PENDING if post_type == PostType.FACT else PostStatus.PUBLISHED
    post = reviewed(post_type=post_type, pre=pre)
    moderation.remove_post(post.pk, moderator=moderator_user(), public_note="Hateful")
    assert sent() == [(NotificationType.REMOVED, "")]
    only_for_the_author(post)


def test_the_public_note_is_not_copied_into_the_item():
    post = reviewed()
    moderation.remove_post(post.pk, moderator=moderator_user(), public_note="A reason")
    assert not hasattr(Notification.objects.get(), "public_note")


# ---------- silent actions ----------


def test_dismiss_reports_is_silent():
    post = reviewed()
    moderation.dismiss_reports(post.pk, moderator=moderator_user())
    assert sent() == []


def test_escalate_is_silent():
    post = reviewed()
    moderation.escalate(post.pk, moderator=moderator_user())
    assert sent() == []


def test_a_refused_action_writes_nothing():
    post = PostFactory()  # a published opinion is not under review
    with pytest.raises(moderation.ActionRefused):
        moderation.mark_verified(post.pk, moderator=moderator_user())
    assert sent() == []


def test_filing_an_appeal_tells_nobody():
    post = PostFactory(moderator_verdict=True)
    moderation.file_appeal(author=post.author, post_id=post.pk, reason="Wrong")
    assert sent() == []


def test_blocking_and_unblocking_emergency_posting_tell_nobody():
    account = VerifiedUserFactory()
    moderation.block_emergency_posting(account.pk, moderator=moderator_user())
    moderation.unblock_emergency_posting(account.pk, moderator=moderator_user())
    assert sent() == []


def test_a_superuser_moderating_their_own_post_notifies_nobody():
    boss = VerifiedUserFactory(is_superuser=True)
    post = reviewed(author=boss)
    moderation.mark_false(post.pk, moderator=boss)
    assert Post.objects.get(pk=post.pk).status == PostStatus.VERIFIED_FALSE
    assert sent() == []


# ---------- emergencies ----------


def test_mark_false_on_an_active_emergency_sends_the_verdict_and_the_demotion():
    post = emergency()
    moderation.mark_false(post.pk, moderator=moderator_user())
    assert sent() == [
        (NotificationType.VERDICT, "false"),
        (NotificationType.EMERGENCY_DEMOTED, ""),
    ]
    only_for_the_author(post)


def test_demote_sends_only_the_demotion():
    post = emergency()
    moderation.demote_emergency(post.pk, moderator=moderator_user())
    assert sent() == [(NotificationType.EMERGENCY_DEMOTED, "")]


def test_mark_verified_on_an_active_emergency_does_not_demote_it():
    post = emergency()
    moderation.mark_verified(post.pk, moderator=moderator_user())
    assert sent() == [(NotificationType.VERDICT, "true")]


def test_the_automatic_block_after_a_false_emergency_adds_no_item():
    post = emergency()
    moderation.mark_false(post.pk, moderator=moderator_user())
    post.author.refresh_from_db()
    assert post.author.emergency_blocked_until is not None
    assert len(sent()) == 2  # the verdict and the demotion; the block says nothing


def test_the_automatic_lift_after_an_overturned_false_adds_no_item():
    post = emergency()
    moderation.mark_false(post.pk, moderator=moderator_user())
    Notification.objects.all().delete()
    appeal = moderation.file_appeal(author=post.author, post_id=post.pk, reason="No")
    assert appeal.kind == "label"
    moderation.mark_verified(post.pk, moderator=moderator_user())
    # The verdict and the appeal; the lift of the block is silent.
    assert sent() == [
        (NotificationType.VERDICT, "true"),
        (NotificationType.APPEAL_RESOLVED, "overturned"),
    ]


# ---------- appeals ----------


def test_an_overturned_label_appeal_sends_the_new_verdict_then_the_appeal():
    appeal = AppealFactory()
    moderation.mark_verified(appeal.post_id, moderator=moderator_user())
    assert sent() == [
        (NotificationType.VERDICT, "true"),
        (NotificationType.APPEAL_RESOLVED, "overturned"),
    ]
    assert Appeal.objects.get().status == AppealStatus.OVERTURNED
    assert set(Notification.objects.values_list("recipient_id", flat=True)) == {appeal.author_id}


def test_an_upheld_label_appeal_by_mark_false_sends_the_appeal_only():
    appeal = AppealFactory()
    moderation.mark_false(appeal.post_id, moderator=moderator_user())
    assert sent() == [(NotificationType.APPEAL_RESOLVED, "upheld")]


def test_removing_a_post_under_a_label_appeal_sends_the_removal_then_the_appeal():
    appeal = AppealFactory()
    moderation.remove_post(appeal.post_id, moderator=moderator_user())
    assert sent() == [
        (NotificationType.REMOVED, ""),
        (NotificationType.APPEAL_RESOLVED, "upheld"),
    ]


def test_restoring_a_removed_post_sends_the_appeal_only():
    appeal = AppealFactory(removal=True)
    moderation.restore_post(appeal.post_id, moderator=moderator_user())
    assert sent() == [(NotificationType.APPEAL_RESOLVED, "overturned")]


def test_keeping_a_post_removed_sends_the_appeal_only():
    appeal = AppealFactory(removal=True)
    moderation.keep_removed(appeal.post_id, moderator=moderator_user())
    assert sent() == [(NotificationType.APPEAL_RESOLVED, "upheld")]


def test_the_items_of_one_action_are_stamped_one_microsecond_apart_in_order():
    appeal = AppealFactory()
    moderation.mark_verified(appeal.post_id, moderator=moderator_user())
    first, second = Notification.objects.order_by("created_at")
    assert (first.type, second.type) == (NotificationType.VERDICT, NotificationType.APPEAL_RESOLVED)
    assert second.created_at - first.created_at == TICK


def test_mark_false_on_a_pinned_emergency_under_a_label_appeal_sends_demotion_then_appeal():
    """The label was FALSE already, so no repeat verdict; the priority ends and the appeal is
    upheld: two items, in that order, one microsecond apart."""
    now = timezone.now()
    appeal = AppealFactory(
        post__is_emergency=True,
        post__emergency_expires_at=now + timedelta(hours=20),
        post__created_at=now - timedelta(hours=4),
    )
    moderation.mark_false(appeal.post_id, moderator=moderator_user())
    first, second = Notification.objects.order_by("created_at")
    assert (first.type, second.type) == (
        NotificationType.EMERGENCY_DEMOTED,
        NotificationType.APPEAL_RESOLVED,
    )
    assert second.outcome == "upheld"
    assert second.created_at - first.created_at == TICK


def test_each_item_is_unread():
    post = reviewed()
    moderation.mark_false(post.pk, moderator=moderator_user())
    assert not Notification.objects.get().is_read
