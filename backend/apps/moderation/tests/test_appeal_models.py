"""`Appeal`: the checks, one per post for life, what a deletion takes with it, and the audit row's
link (ARCHITECTURE §2)."""

from datetime import timedelta

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.moderation.models import ActionKind, Appeal, AppealKind, AppealStatus, ModerationAction
from apps.moderation.tests.factories import (
    AppealFactory,
    ModerationActionFactory,
    moderator_user,
)
from apps.posts.models import Post, PostStatus
from apps.posts.tests.factories import PostFactory, VerifiedUserFactory

pytestmark = pytest.mark.django_db


def violated(constraint_name, **fields):
    with pytest.raises(IntegrityError) as exc, transaction.atomic():
        AppealFactory(**fields)
    assert exc.value.__cause__.diag.constraint_name == constraint_name


def test_a_new_appeal_is_open_with_no_resolution():
    appeal = AppealFactory()
    appeal.refresh_from_db()
    assert appeal.status == AppealStatus.OPEN
    assert appeal.resolved_at is None and appeal.resolved_by is None
    assert appeal.kind == AppealKind.LABEL


@pytest.mark.parametrize("kind", AppealKind.values)
def test_both_kinds_can_be_stored(kind):
    assert AppealFactory(kind=kind).kind == kind


def test_an_unknown_kind_is_refused_by_the_database():
    violated("appeals_kind_valid", kind="complaint")


def test_an_unknown_status_is_refused_by_the_database():
    violated("appeals_status_valid", status="maybe", resolved_at=timezone.now())


def test_an_open_appeal_with_a_resolution_time_is_refused():
    violated("appeals_resolution_consistent", resolved_at=timezone.now())


@pytest.mark.parametrize("status", [AppealStatus.UPHELD, AppealStatus.OVERTURNED])
def test_a_resolved_appeal_without_a_resolution_time_is_refused(status):
    violated("appeals_resolution_consistent", status=status, resolved_at=None)


@pytest.mark.parametrize("status", [AppealStatus.UPHELD, AppealStatus.OVERTURNED])
def test_a_resolved_appeal_with_a_resolution_time_is_stored(status):
    appeal = AppealFactory(status=status, resolved_at=timezone.now(), resolved_by=moderator_user())
    assert appeal.status == status


def test_a_post_has_at_most_one_appeal_for_life():
    appeal = AppealFactory()
    with pytest.raises(IntegrityError), transaction.atomic():
        Appeal.objects.create(post=appeal.post, author=appeal.author, kind=AppealKind.LABEL)
    # Even after it is resolved.
    Appeal.objects.filter(pk=appeal.pk).update(
        status=AppealStatus.UPHELD, resolved_at=timezone.now()
    )
    with pytest.raises(IntegrityError), transaction.atomic():
        Appeal.objects.create(post=appeal.post, author=appeal.author, kind=AppealKind.LABEL)


def test_the_reason_may_be_blank_and_is_at_most_500_characters():
    assert AppealFactory(reason="").reason == ""
    assert len(AppealFactory(reason="é" * 500).reason) == 500


def test_str_names_the_kind_and_the_post_but_never_the_authors_words():
    appeal = AppealFactory(reason="This was a joke, please read it again")
    text = str(appeal)
    assert "FALSE label" in text and str(appeal.post_id) in text
    assert "joke" not in text


def test_deleting_the_post_deletes_its_appeal():
    appeal = AppealFactory()
    appeal.post.delete()
    assert not Appeal.objects.filter(pk=appeal.pk).exists()


def test_deleting_the_author_deletes_their_appeal():
    appeal = AppealFactory()
    User.objects.filter(pk=appeal.author_id).delete()
    assert not Appeal.objects.filter(pk=appeal.pk).exists()


def test_deleting_a_moderators_account_keeps_the_appeal_and_forgets_who():
    original, resolver = moderator_user(), moderator_user()
    appeal = AppealFactory(
        original_moderator=original,
        status=AppealStatus.UPHELD,
        resolved_by=resolver,
        resolved_at=timezone.now(),
    )
    User.objects.filter(pk__in=[original.pk, resolver.pk]).delete()
    appeal.refresh_from_db()
    assert appeal.original_moderator_id is None and appeal.resolved_by_id is None
    assert appeal.status == AppealStatus.UPHELD


def test_the_audit_row_links_to_the_appeal_it_resolved_and_survives_its_deletion():
    appeal = AppealFactory()
    row = ModerationActionFactory(
        post=appeal.post, action=ActionKind.RESTORED, from_status=PostStatus.REMOVED, appeal=appeal
    )
    assert list(appeal.moderation_actions.all()) == [row]
    appeal.post.delete()  # CASCADE takes the appeal; the log keeps its row with the link nulled
    row = ModerationAction.objects.get(pk=row.pk)
    assert row.appeal_id is None
    assert Post.objects.count() == 0


def test_an_action_without_an_appeal_has_none():
    assert ModerationActionFactory().appeal is None


def test_created_at_is_given_by_the_caller_so_tests_can_place_appeals_in_time():
    then = timezone.now() - timedelta(days=3)
    assert AppealFactory(created_at=then).created_at == then


def test_the_author_has_a_related_name_for_their_appeals():
    appeal = AppealFactory()
    assert list(appeal.author.appeals.all()) == [appeal]
    assert PostFactory().pk != appeal.post_id  # a second post has none
    assert VerifiedUserFactory().appeals.count() == 0
