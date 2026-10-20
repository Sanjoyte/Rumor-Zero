"""Part 11C through the real services (ARCHITECTURE §4, §4b, §8): Demote, what Mark FALSE does to
an emergency, the automatic block and its lift, and the manual Block / Unblock on an account.

Every test checks the account's column against `rules.standing_block_end` of its rows."""

from datetime import timedelta

import pytest
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.moderation import rules, services
from apps.moderation.models import ActionKind, ModerationAction
from apps.moderation.tests.factories import moderator_user, senior_user
from apps.posts.emergency import is_active_emergency
from apps.posts.models import FlaggedReason, PostStatus, PostType
from apps.posts.tests.factories import PostFactory, VerifiedUserFactory
from apps.reputation import services as reputation_services
from apps.reputation.models import EventKind
from apps.reputation.tests.factories import FALSE_95, label_by_pipeline, stored

pytestmark = pytest.mark.django_db

DAY = timedelta(days=1)
TICK = timedelta(microseconds=1)


def emergency(*, active=True, author=None, **fields):
    """A reported emergency fact under review (or `status=…`), active unless `active=False`."""
    now = timezone.now()
    expires = now + timedelta(hours=20) if active else now - timedelta(minutes=1)
    fields.setdefault("status", PostStatus.UNDER_REVIEW)
    if fields["status"] == PostStatus.UNDER_REVIEW:
        fields.setdefault("flagged_reason", FlaggedReason.REPORTS)
        fields.setdefault("pre_review_status", PostStatus.PENDING)
    return PostFactory(
        author=author or VerifiedUserFactory(),
        post_type=PostType.FACT,
        is_emergency=True,
        emergency_expires_at=expires,
        created_at=expires - timedelta(hours=24),
        **fields,
    )


def reload(obj):
    return type(obj).objects.get(pk=obj.pk)


def block_rows(user):
    return list(
        ModerationAction.objects.filter(
            subject_user=user,
            action__in=[ActionKind.EMERGENCY_BLOCKED, ActionKind.EMERGENCY_UNBLOCKED],
        ).order_by("created_at", "id")
    )


def column(user):
    return User.objects.values_list("emergency_blocked_until", flat=True).get(pk=user.pk)


def assert_column_follows_the_rows(user):
    rows = [rules.BlockRow(r.action, r.post_id, r.blocked_until) for r in block_rows(user)]
    assert column(user) == rules.standing_block_end(rows)


def history(post):
    return list(
        ModerationAction.objects.filter(post=post)
        .order_by("created_at", "id")
        .values_list("action", flat=True)
    )


# ---------- Mark FALSE on an emergency ----------


def test_mark_false_on_an_active_emergency_unpins_blocks_and_costs_three():
    post = emergency()
    moderator = moderator_user()
    now = timezone.now()
    entry = services.mark_false(post.pk, moderator=moderator, now=now)
    after = reload(post)
    assert after.status == PostStatus.VERIFIED_FALSE
    assert after.emergency_demoted_at == now
    assert not is_active_emergency(after, now)
    # Three rows, 1 µs apart, in the order they happened.
    rows = list(ModerationAction.objects.order_by("created_at"))
    assert [r.action for r in rows] == [
        ActionKind.MARKED_FALSE,
        ActionKind.EMERGENCY_DEMOTED,
        ActionKind.EMERGENCY_BLOCKED,
    ]
    assert [r.created_at for r in rows] == [now, now + TICK, now + 2 * TICK]
    assert rows[0] == entry
    demoted, block = rows[1], rows[2]
    assert (demoted.post, demoted.moderator, demoted.subject_user) == (after, moderator, None)
    assert (demoted.from_status, demoted.to_status) == (PostStatus.VERIFIED_FALSE,) * 2
    assert (block.post, block.moderator, block.subject_user) == (after, moderator, post.author)
    assert block.blocked_until == block.created_at + 30 * DAY
    assert block.notes == "Automatic: the emergency post was labelled FALSE."
    assert (block.from_status, block.to_status) == (None, None)
    assert column(post.author) == block.blocked_until
    # The −3 (N + 3), and the ledger links the Mark FALSE row, not the others.
    assert stored(post.author) == (38, 1)
    [event] = post.author.reputation_events.all()
    assert (event.kind, event.moderation_action_id) == (EventKind.EMERGENCY_FALSE, entry.pk)
    assert not reputation_services.pending_changes(after)


def test_mark_false_on_an_expired_emergency_blocks_but_has_no_priority_to_end():
    post = emergency(active=False)
    services.mark_false(post.pk, moderator=moderator_user())
    after = reload(post)
    assert after.emergency_demoted_at is None
    assert history(post) == [ActionKind.MARKED_FALSE, ActionKind.EMERGENCY_BLOCKED]
    assert column(post.author) is not None
    assert_column_follows_the_rows(post.author)


def test_mark_false_on_an_ordinary_fact_blocks_nothing():
    post = PostFactory(
        post_type=PostType.FACT,
        status=PostStatus.UNDER_REVIEW,
        flagged_reason=FlaggedReason.REPORTS,
        pre_review_status=PostStatus.PENDING,
    )
    services.mark_false(post.pk, moderator=moderator_user())
    assert history(post) == [ActionKind.MARKED_FALSE]
    assert column(post.author) is None


def test_a_block_length_of_zero_blocks_nothing(emergency_settings):
    emergency_settings(emergency_false_cooldown_days=0)
    post = emergency()
    services.mark_false(post.pk, moderator=moderator_user())
    assert history(post) == [ActionKind.MARKED_FALSE, ActionKind.EMERGENCY_DEMOTED]
    assert column(post.author) is None
    assert stored(post.author) == (38, 1)  # the score still moves


def test_the_block_length_comes_from_the_settings(emergency_settings):
    emergency_settings(emergency_false_cooldown_days=7)
    post = emergency()
    services.mark_false(post.pk, moderator=moderator_user())
    [block] = block_rows(post.author)
    assert block.blocked_until == block.created_at + 7 * DAY


@pytest.mark.parametrize("act", ["mark_verified", "dismiss_reports", "remove_post", "escalate"])
def test_the_other_actions_on_an_active_emergency_block_nobody_and_keep_the_priority(act):
    post = emergency()
    getattr(services, act)(post.pk, moderator=moderator_user())
    assert reload(post).emergency_demoted_at is None
    assert column(post.author) is None


# ---------- the pipeline's FALSE ----------


def test_the_pipeline_false_after_expiry_blocks_with_a_row_that_has_no_moderator():
    post = emergency(active=False, status=PostStatus.PENDING)
    now = timezone.now()
    assert label_by_pipeline(post, FALSE_95, now=now) == "labelled"
    [block] = block_rows(post.author)
    assert (block.moderator, block.post_id, block.created_at) == (None, post.pk, now)
    assert block.blocked_until == now + 30 * DAY
    assert column(post.author) == block.blocked_until
    assert stored(post.author) == (38, 1)


def test_the_pipeline_false_on_an_active_emergency_goes_to_review_and_blocks_nobody():
    post = emergency(status=PostStatus.PENDING)
    assert label_by_pipeline(post, FALSE_95) == "entered_review"
    after = reload(post)
    assert (after.status, after.flagged_reason) == (PostStatus.UNDER_REVIEW, FlaggedReason.PIPELINE)
    assert after.emergency_demoted_at is None
    assert block_rows(post.author) == [] and column(post.author) is None
    assert stored(post.author) == (50, 0)


# ---------- appeals: an upheld FALSE blocks once, an overturned one is lifted ----------


def false_by_a_moderator(post=None):
    post = post or emergency()
    services.mark_false(post.pk, moderator=moderator_user())
    return reload(post)


def test_an_upheld_label_appeal_does_not_block_twice():
    post = false_by_a_moderator()
    services.file_appeal(author=post.author, post_id=post.pk)
    services.mark_false(post.pk, moderator=moderator_user())
    assert len(block_rows(post.author)) == 1
    assert_column_follows_the_rows(post.author)


def test_an_overturned_label_appeal_lifts_the_block():
    post = false_by_a_moderator()
    services.file_appeal(author=post.author, post_id=post.pk)
    other = moderator_user()
    services.mark_verified(post.pk, moderator=other)
    blocked, lifted = block_rows(post.author)
    assert lifted.action == ActionKind.EMERGENCY_UNBLOCKED
    assert (lifted.post_id, lifted.moderator, lifted.blocked_until) == (post.pk, other, None)
    assert lifted.notes == "Automatic: the FALSE label was overturned."
    assert lifted.created_at > blocked.created_at
    assert column(post.author) is None
    assert stored(post.author) == (55, 1)


def test_an_overturned_appeal_keeps_a_manual_block_that_still_stands():
    post = false_by_a_moderator()
    later = timezone.now() + timedelta(days=5)
    # The manual block must reach past the automatic one to be worth writing.
    services.block_emergency_posting(post.author.pk, moderator=senior_user(), now=later)
    manual_end = column(post.author)
    services.file_appeal(author=post.author, post_id=post.pk)
    services.mark_verified(post.pk, moderator=moderator_user())
    assert column(post.author) == manual_end
    assert_column_follows_the_rows(post.author)


def test_an_overturned_appeal_keeps_another_false_emergencys_block():
    author = VerifiedUserFactory()
    first = false_by_a_moderator(emergency(author=author))
    second = false_by_a_moderator(emergency(author=author))
    second_end = block_rows(author)[-1].blocked_until
    services.file_appeal(author=author, post_id=first.pk)
    services.mark_verified(first.pk, moderator=moderator_user())
    assert column(author) == second_end
    assert_column_follows_the_rows(author)
    # Overturning the second one too frees the account.
    services.file_appeal(author=author, post_id=second.pk)
    services.mark_verified(second.pk, moderator=moderator_user())
    assert column(author) is None


def test_a_restore_of_a_removed_false_emergency_lifts_nothing():
    """A Restore reverses the removal's rows, never the label's (`post_removed`, not
    `emergency_false`): the FALSE and its block stand."""
    post = false_by_a_moderator()
    services.remove_post(post.pk, moderator=moderator_user())
    services.file_appeal(author=post.author, post_id=post.pk)
    services.restore_post(post.pk, moderator=moderator_user())
    after = reload(post)
    assert after.status == PostStatus.VERIFIED_FALSE
    assert [r.action for r in block_rows(post.author)] == [ActionKind.EMERGENCY_BLOCKED]
    assert column(post.author) is not None


def test_a_lift_comes_after_an_unblock_lifted_everything_and_writes_nothing():
    post = false_by_a_moderator()
    services.unblock_emergency_posting(post.author.pk, moderator=senior_user())
    services.file_appeal(author=post.author, post_id=post.pk)
    services.mark_verified(post.pk, moderator=moderator_user())
    assert [r.action for r in block_rows(post.author)] == [
        ActionKind.EMERGENCY_BLOCKED,
        ActionKind.EMERGENCY_UNBLOCKED,
    ]
    assert column(post.author) is None


# ---------- Demote emergency ----------


def test_demote_ends_the_priority_and_changes_nothing_else():
    post = emergency()
    moderator = moderator_user()
    now = timezone.now()
    entry = services.demote_emergency(post.pk, moderator=moderator, notes="Not urgent.", now=now)
    after = reload(post)
    assert after.emergency_demoted_at == now
    assert (after.status, after.flagged_reason) == (PostStatus.UNDER_REVIEW, FlaggedReason.REPORTS)
    assert entry.action == ActionKind.EMERGENCY_DEMOTED
    assert (entry.from_status, entry.to_status) == (PostStatus.UNDER_REVIEW,) * 2
    assert (entry.notes, entry.public_note, entry.moderator) == ("Not urgent.", "", moderator)
    assert history(post) == [ActionKind.EMERGENCY_DEMOTED]
    assert column(post.author) is None
    assert stored(post.author) == (50, 0)
    assert not reputation_services.pending_changes(after)


@pytest.mark.parametrize(
    "status", [PostStatus.PENDING, PostStatus.VERIFIED_TRUE, PostStatus.UNDER_REVIEW]
)
def test_demote_works_in_any_status(status):
    post = emergency(status=status)
    services.demote_emergency(post.pk, moderator=moderator_user())
    assert reload(post).emergency_demoted_at is not None


def test_demote_is_refused_on_a_post_that_is_not_an_active_emergency():
    for post in (
        emergency(active=False),
        emergency(emergency_demoted_at=timezone.now()),
        PostFactory(post_type=PostType.FACT, status=PostStatus.PENDING),
    ):
        with pytest.raises(services.ActionRefused) as refused:
            services.demote_emergency(post.pk, moderator=moderator_user())
        assert refused.value.refusal is rules.NOT_ACTIVE_EMERGENCY
    assert not ModerationAction.objects.exists()


def test_demote_twice_is_refused_the_second_time():
    post = emergency()
    services.demote_emergency(post.pk, moderator=moderator_user())
    with pytest.raises(services.ActionRefused):
        services.demote_emergency(post.pk, moderator=moderator_user())
    assert history(post) == [ActionKind.EMERGENCY_DEMOTED]


def test_demote_is_refused_on_your_own_post():
    moderator = moderator_user()
    post = emergency(author=moderator)
    with pytest.raises(services.ActionRefused) as refused:
        services.demote_emergency(post.pk, moderator=moderator)
    assert refused.value.refusal is rules.OWN_POST


def test_a_demoted_emergency_marked_false_later_blocks_but_is_not_demoted_again():
    post = emergency()
    services.demote_emergency(post.pk, moderator=moderator_user())
    demoted_at = reload(post).emergency_demoted_at
    services.mark_false(post.pk, moderator=moderator_user())
    assert reload(post).emergency_demoted_at == demoted_at
    assert history(post) == [
        ActionKind.EMERGENCY_DEMOTED,
        ActionKind.MARKED_FALSE,
        ActionKind.EMERGENCY_BLOCKED,
    ]


def test_a_restore_inside_the_24_hours_pins_the_post_again():
    """Remove doesn't demote, so a Restore (the removal was the mistake) brings the priority
    back while the 24 hours last."""
    post = emergency(status=PostStatus.PENDING)
    services.remove_post(post.pk, moderator=moderator_user())
    assert not is_active_emergency(reload(post), timezone.now())
    services.file_appeal(author=post.author, post_id=post.pk)
    services.restore_post(post.pk, moderator=moderator_user())
    assert is_active_emergency(reload(post), timezone.now())


# ---------- the manual Block / Unblock (UserAdmin) ----------


def test_a_manual_block_lasts_as_long_as_an_automatic_one():
    target = VerifiedUserFactory()
    moderator = moderator_user()
    now = timezone.now()
    entry = services.block_emergency_posting(
        target.pk, moderator=moderator, notes="Spam emergencies.", now=now
    )
    assert entry.action == ActionKind.EMERGENCY_BLOCKED
    assert (entry.post, entry.subject_user, entry.moderator) == (None, target, moderator)
    assert (entry.post_snapshot, entry.notes) == ("", "Spam emergencies.")
    assert (entry.from_status, entry.to_status) == (None, None)
    assert entry.blocked_until == now + 30 * DAY
    assert column(target) == now + 30 * DAY


def test_the_column_is_the_latest_end_of_the_blocks_that_stand():
    """The max rule: a manual block shorter than an automatic one doesn't shorten it."""
    post = false_by_a_moderator()
    automatic_end = column(post.author)
    # At the automatic block's own time, 30 days reach no further: refused.
    [automatic] = block_rows(post.author)
    with pytest.raises(services.ActionRefused) as refused:
        services.block_emergency_posting(
            post.author.pk, moderator=senior_user(), now=automatic.created_at
        )
    assert refused.value.refusal is rules.ALREADY_BLOCKED
    # Ten days on, a manual block reaches further and becomes the end.
    later = timezone.now() + 10 * DAY
    services.block_emergency_posting(post.author.pk, moderator=senior_user(), now=later)
    assert column(post.author) == later + 30 * DAY > automatic_end
    assert_column_follows_the_rows(post.author)


def test_an_unblock_lifts_every_block_automatic_ones_included():
    post = false_by_a_moderator()
    services.block_emergency_posting(
        post.author.pk, moderator=senior_user(), now=timezone.now() + 3 * DAY
    )
    moderator = moderator_user()
    entry = services.unblock_emergency_posting(post.author.pk, moderator=moderator, notes="Ok.")
    assert entry.action == ActionKind.EMERGENCY_UNBLOCKED
    assert (entry.post, entry.subject_user, entry.blocked_until) == (None, post.author, None)
    assert column(post.author) is None
    # A FALSE emergency after the unblock blocks again.
    false_by_a_moderator(emergency(author=post.author))
    assert column(post.author) is not None
    assert_column_follows_the_rows(post.author)


@pytest.mark.parametrize(
    ("who", "target_kind", "code"),
    [
        ("moderator", "superuser", "superuser_account"),
        ("senior", "superuser", "superuser_account"),
        ("moderator", "self", "own_account"),
        ("senior", "self", "own_account"),
    ],
)
def test_the_account_refusals(who, target_kind, code):
    actor = moderator_user() if who == "moderator" else senior_user()
    if target_kind == "superuser":
        target = User.objects.create_superuser("root2@example.test", "root_two", "a-long-pass-1")
    else:
        target = actor
    with pytest.raises(services.ActionRefused) as refused:
        services.block_emergency_posting(target.pk, moderator=actor)
    assert refused.value.refusal.code == code
    assert not ModerationAction.objects.exists()


def test_a_superuser_may_block_a_superuser_and_themselves():
    root = User.objects.create_superuser("root@example.test", "root", "a-long-password-1")
    other = User.objects.create_superuser("root2@example.test", "root_two", "a-long-pass-1")
    services.block_emergency_posting(other.pk, moderator=root)
    services.block_emergency_posting(root.pk, moderator=root)
    assert column(other) and column(root)


def test_unblocking_an_account_that_is_not_blocked_is_refused():
    target = VerifiedUserFactory()
    with pytest.raises(services.ActionRefused) as refused:
        services.unblock_emergency_posting(target.pk, moderator=moderator_user())
    assert refused.value.refusal is rules.NOT_BLOCKED


def test_a_block_with_a_length_of_zero_is_refused(emergency_settings):
    emergency_settings(emergency_false_cooldown_days=0)
    with pytest.raises(services.ActionRefused) as refused:
        services.block_emergency_posting(VerifiedUserFactory().pk, moderator=moderator_user())
    assert refused.value.refusal is rules.NO_BLOCK_LENGTH


def test_an_account_that_is_gone_is_refused():
    import uuid

    with pytest.raises(services.ActionRefused) as refused:
        services.block_emergency_posting(uuid.uuid4(), moderator=moderator_user())
    assert refused.value.refusal is rules.NO_ACCOUNT


def test_an_accounts_block_rows_are_strictly_increasing_even_with_an_older_clock():
    """A writer whose `now` is older than the account's last row (it waited for the lock) still
    comes after it, so `standing_block_end` reads the rows in the order they happened."""
    target = VerifiedUserFactory()
    now = timezone.now()
    services.block_emergency_posting(target.pk, moderator=moderator_user(), now=now)
    unblock = services.unblock_emergency_posting(
        target.pk, moderator=moderator_user(), now=now - timedelta(seconds=5)
    )
    assert unblock.created_at == now + TICK
    assert column(target) is None


def test_the_block_functions_refuse_to_run_outside_a_transaction():
    """`block_after_emergency_false` runs inside the caller's transaction, after `settle_post`
    locked the post and the author; called alone it raises (it never opens one of its own)."""
    post = emergency()
    row = reputation_services.ReputationEvent(kind=EventKind.EMERGENCY_FALSE, user=post.author)
    connection = transaction.get_connection()
    in_block = connection.in_atomic_block
    try:
        # pytest-django's own transaction counts as one; pretend it isn't there.
        connection.in_atomic_block = False
        with pytest.raises(RuntimeError, match="caller's transaction"):
            services.block_after_emergency_false(post, [row], now=timezone.now(), moderator=None)
    finally:
        connection.in_atomic_block = in_block
