"""`ModerationAction`: the checks, the append-only guards, and what survives a deletion."""

import pytest
from django.db import DataError, IntegrityError, connection, transaction
from django.utils import timezone

from apps.moderation.models import ActionKind, ModerationAction
from apps.moderation.tests.factories import ModerationActionFactory
from apps.posts.models import Post, PostStatus
from apps.posts.tests.factories import PostFactory, VerifiedUserFactory

pytestmark = pytest.mark.django_db


def violated(constraint_name, **fields):
    with pytest.raises(IntegrityError) as exc, transaction.atomic():
        ModerationActionFactory(**fields)
    assert exc.value.__cause__.diag.constraint_name == constraint_name


def test_the_whole_list_of_twelve_kinds_exists():
    """Part 10 made ten; Part 11 added `kept_removed` ("Keep removed" had no kind) and Part 11C
    `emergency_unblocked` (an Unblock, or the lift when a FALSE label is overturned)."""
    assert [kind.value for kind in ActionKind] == [
        "verified",
        "marked_false",
        "dismissed_report",
        "removed",
        "escalated",
        "restored",
        "kept_removed",
        "emergency_demoted",
        "emergency_blocked",
        "emergency_unblocked",
        "avatar_removed",
        "avatar_blocked",
    ]


@pytest.mark.parametrize("kind", ActionKind.values)
def test_every_kind_can_be_stored(kind):
    until = timezone.now() if kind == ActionKind.EMERGENCY_BLOCKED else None
    ModerationActionFactory(
        action=kind, post=None, from_status=None, to_status=None, blocked_until=until
    )
    assert ModerationAction.objects.get().action == kind


def test_a_block_row_must_say_when_it_ends():
    violated(
        "moderation_action_blocked_until_kind",
        action=ActionKind.EMERGENCY_BLOCKED,
        post=None,
        blocked_until=None,
    )


@pytest.mark.parametrize(
    "kind", [kind for kind in ActionKind.values if kind != ActionKind.EMERGENCY_BLOCKED]
)
def test_no_other_row_has_a_block_end(kind):
    violated("moderation_action_blocked_until_kind", action=kind, blocked_until=timezone.now())


def test_an_unknown_kind_is_refused_by_the_database():
    violated("moderation_action_valid", action="burned")


@pytest.mark.parametrize(
    ("field", "name"),
    [
        ("from_status", "moderation_action_from_status_valid"),
        ("to_status", "moderation_action_to_status_valid"),
    ],
)
def test_an_unknown_status_is_refused_by_the_database(field, name):
    violated(name, **{field: "invented"})


def test_account_level_actions_have_no_statuses_and_no_post():
    target = VerifiedUserFactory()
    ModerationActionFactory(
        post=None,
        subject_user=target,
        action=ActionKind.EMERGENCY_BLOCKED,
        from_status=None,
        to_status=None,
        blocked_until=timezone.now(),
    )
    row = ModerationAction.objects.get()
    assert (row.post, row.from_status, row.to_status, row.subject_user) == (
        None,
        None,
        None,
        target,
    )


def test_a_public_note_can_have_500_characters_and_not_501():
    ModerationActionFactory(public_note="n" * 500)
    with pytest.raises(DataError), transaction.atomic():
        ModerationActionFactory(public_note="n" * 501)


def test_created_at_defaults_to_now_and_can_be_placed_in_time():
    from datetime import UTC, datetime

    then = datetime(2026, 1, 2, 3, 4, tzinfo=UTC)
    assert ModerationActionFactory(created_at=then).created_at == then


# ---------- append-only ----------


def test_a_saved_row_can_not_be_saved_again():
    row = ModerationActionFactory(notes="first")
    row.notes = "second"
    with pytest.raises(RuntimeError, match="append-only"):
        row.save()
    assert ModerationAction.objects.get().notes == "first"


def test_a_row_can_not_be_deleted():
    row = ModerationActionFactory()
    with pytest.raises(RuntimeError, match="append-only"):
        row.delete()
    assert ModerationAction.objects.count() == 1


def test_a_row_can_be_created_with_save_once():
    row = ModerationAction(action=ActionKind.ESCALATED, post=PostFactory(), post_snapshot="x")
    row.save()
    assert ModerationAction.objects.count() == 1


# ---------- what survives a deletion ----------


def test_deleting_the_post_keeps_the_row_with_its_snapshot_and_a_null_post():
    post = PostFactory(content="What it said")
    ModerationActionFactory(post=post, post_snapshot="What it said")
    post.delete()
    row = ModerationAction.objects.get()
    assert row.post is None and row.post_snapshot == "What it said"


def test_deleting_the_authors_account_keeps_the_rows_too():
    post = PostFactory()
    ModerationActionFactory(post=post, post_snapshot=post.content)
    post.author.delete()
    assert Post.objects.count() == 0
    row = ModerationAction.objects.get()
    assert row.post is None and row.post_snapshot


def test_deleting_the_moderator_keeps_the_row_with_a_null_moderator():
    row = ModerationActionFactory()
    row.moderator.delete()
    assert ModerationAction.objects.get().moderator is None


def test_the_post_page_can_list_its_history_through_the_related_name():
    post = PostFactory()
    ModerationActionFactory(post=post, action=ActionKind.ESCALATED)
    ModerationActionFactory(post=post, to_status=PostStatus.REMOVED)
    assert post.moderation_actions.count() == 2


def test_both_indexes_exist():
    with connection.cursor() as cursor:
        names = set(connection.introspection.get_constraints(cursor, "moderation_moderationaction"))
    assert {"modaction_post_created_idx", "modaction_created_idx"} <= names
