"""A full `User.save()` never writes the credibility score (Part 11B, ARCHITECTURE §2).

The score is written only by the reputation service (`bulk_update`) and `recompute_reputation`. A
save of a loaded account without `update_fields` (allauth's `set_password`, the admin form) would
otherwise write back the score it read earlier in the request and undo a ledger write that
committed meanwhile."""

import pytest
from allauth.account.adapter import get_adapter
from django.contrib.auth.models import Group
from django.urls import reverse

from apps.accounts.admin import UserAdmin
from apps.accounts.models import MODERATORS_GROUP, Role, User
from apps.accounts.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def score_meanwhile(user, score=62, sample=3):
    """As if a ledger write had committed after `user` was loaded."""
    User.objects.filter(pk=user.pk).update(reputation_score=score, reputation_sample=sample)


def stored(user):
    return tuple(
        User.objects.filter(pk=user.pk).values_list("reputation_score", "reputation_sample").get()
    )


def test_a_full_save_of_a_stale_instance_leaves_the_score_alone():
    stale = User.objects.get(pk=UserFactory().pk)
    score_meanwhile(stale)
    stale.bio = "A new bio"
    stale.save()
    assert stored(stale) == (62, 3)
    assert User.objects.get(pk=stale.pk).bio == "A new bio"


def test_even_a_score_set_on_the_instance_is_not_written_by_save():
    user = UserFactory()
    user.reputation_score = 99
    user.reputation_sample = 40
    user.save()
    assert stored(user) == (50, 0)


def test_allauths_set_password_leaves_the_score_alone():
    stale = User.objects.get(pk=UserFactory().pk)
    score_meanwhile(stale)
    get_adapter().set_password(stale, "another-long-password-42")
    assert stored(stale) == (62, 3)
    assert User.objects.get(pk=stale.pk).check_password("another-long-password-42")


def test_the_admin_form_leaves_the_score_alone(client, monkeypatch):
    root = User.objects.create_superuser("root@example.test", "root", "a-long-password-1")
    client.force_login(root)
    target = UserFactory(display_name="Old")
    url = reverse("admin:accounts_user_change", args=[target.pk])
    save_model = UserAdmin.save_model

    def ledger_write_commits_while_the_form_is_saved(self, request, obj, form, change):
        score_meanwhile(obj)  # after the admin loaded the account, before it saves it
        save_model(self, request, obj, form, change)

    monkeypatch.setattr(UserAdmin, "save_model", ledger_write_commits_while_the_form_is_saved)
    response = client.post(
        url,
        {
            "email": target.email,
            "username": target.username,
            "display_name": "New",
            "bio": "",
            "role": Role.USER,
            "is_active": "on",
        },
    )
    assert response.status_code == 302
    assert User.objects.get(pk=target.pk).display_name == "New"
    assert stored(target) == (62, 3)


def test_a_role_change_by_a_full_save_still_syncs_the_groups():
    user = User.objects.get(pk=UserFactory().pk)
    user.role = Role.MODERATOR
    user.save()
    fresh = User.objects.get(pk=user.pk)
    assert fresh.role == Role.MODERATOR
    assert fresh.is_staff is True
    assert list(fresh.groups.values_list("name", flat=True)) == [MODERATORS_GROUP]
    assert Group.objects.filter(name=MODERATORS_GROUP).exists()


def test_a_create_writes_the_starting_score():
    user = User(email="new@example.test", username="newcomer")
    user.set_password("a-long-password-1")
    user.save()
    assert stored(user) == (50, 0)


def test_update_fields_naming_the_score_still_writes_it():
    """Only the full save is narrowed: the service writes the two columns with `bulk_update`,
    and an explicit `update_fields` (a test, a shell) is taken at its word."""
    user = UserFactory()
    user.reputation_score = 70
    user.save(update_fields=["reputation_score"])
    assert stored(user) == (70, 0)


def test_a_full_save_of_a_partly_loaded_account_writes_only_what_was_loaded():
    user = UserFactory(display_name="Kept", bio="Kept too")
    partial = User.objects.only("id", "username", "email", "role", "is_superuser").get(pk=user.pk)
    User.objects.filter(pk=user.pk).update(display_name="Changed meanwhile")
    partial.save()
    fresh = User.objects.get(pk=user.pk)
    assert (fresh.display_name, fresh.bio) == ("Changed meanwhile", "Kept too")


# ---------- Part 11C: the emergency block is the moderation service's too ----------


def block_meanwhile(user, until):
    """As if a block (or a Mark FALSE) had committed after `user` was loaded."""
    User.objects.filter(pk=user.pk).update(emergency_blocked_until=until)


def stored_block(user):
    return User.objects.filter(pk=user.pk).values_list("emergency_blocked_until", flat=True).get()


def test_a_full_save_of_a_stale_instance_leaves_the_emergency_block_alone():
    from django.utils import timezone

    stale = User.objects.get(pk=UserFactory().pk)
    until = timezone.now().replace(microsecond=0)
    block_meanwhile(stale, until)
    stale.bio = "Another bio"
    stale.save()
    assert stored_block(stale) == until
    assert User.objects.get(pk=stale.pk).bio == "Another bio"


def test_allauths_set_password_leaves_the_emergency_block_alone():
    from django.utils import timezone

    stale = User.objects.get(pk=UserFactory().pk)
    until = timezone.now().replace(microsecond=0)
    block_meanwhile(stale, until)
    get_adapter().set_password(stale, "yet-another-long-password-7")
    assert stored_block(stale) == until


def test_a_block_set_on_the_instance_is_not_written_by_a_full_save():
    from django.utils import timezone

    user = UserFactory()
    user.emergency_blocked_until = timezone.now()
    user.save()
    assert stored_block(user) is None


# ---------- Part 14B: the photo is the avatar service's and the moderation service's ----------


def test_a_full_save_of_a_stale_instance_leaves_the_photo_version_alone():
    """A removed photo must not come back because a stale copy was saved (the admin form, allauth's
    `set_password`), and a new one must not be erased."""
    user = UserFactory(avatar_version="aaaaaaaaaaaaaaaa")
    stale = User.objects.get(pk=user.pk)
    User.objects.filter(pk=user.pk).update(avatar_version=None)  # removed meanwhile
    stale.bio = "Another bio"
    stale.save()
    fresh = User.objects.get(pk=user.pk)
    assert fresh.avatar_version is None and fresh.bio == "Another bio"

    other = User.objects.get(pk=user.pk)
    User.objects.filter(pk=user.pk).update(avatar_version="bbbbbbbbbbbbbbbb")  # replaced meanwhile
    other.save()
    assert User.objects.get(pk=user.pk).avatar_version == "bbbbbbbbbbbbbbbb"


def test_a_full_save_of_a_stale_instance_cannot_lift_a_photo_block():
    stale = User.objects.get(pk=UserFactory().pk)
    User.objects.filter(pk=stale.pk).update(avatar_uploads_blocked=True)
    stale.bio = "Another bio"
    stale.save()
    assert User.objects.get(pk=stale.pk).avatar_uploads_blocked is True


def test_allauths_set_password_leaves_the_photo_alone():
    user = UserFactory(avatar_version="aaaaaaaaaaaaaaaa")
    stale = User.objects.get(pk=user.pk)
    User.objects.filter(pk=user.pk).update(avatar_version=None, avatar_uploads_blocked=True)
    get_adapter().set_password(stale, "another-long-password-42")
    fresh = User.objects.get(pk=user.pk)
    assert (fresh.avatar_version, fresh.avatar_uploads_blocked) == (None, True)


def test_the_photo_fields_are_service_owned():
    from apps.accounts.models import SERVICE_OWNED_FIELDS

    assert {"avatar_version", "avatar_uploads_blocked"} <= SERVICE_OWNED_FIELDS


def test_update_fields_naming_the_photo_still_writes_it():
    """Only the full save is narrowed; the service writes with `.update()`."""
    user = UserFactory()
    user.avatar_version = "cccccccccccccccc"
    user.save(update_fields=["avatar_version"])
    assert User.objects.get(pk=user.pk).avatar_version == "cccccccccccccccc"
