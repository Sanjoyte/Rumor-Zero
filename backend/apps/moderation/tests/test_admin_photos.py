"""Profile photos in Django Admin (Part 14B; ARCHITECTURE §8): the photo list, Remove photo, Block
photo uploads and Allow photo uploads, the account page's Photo field and the filter."""

from datetime import timedelta

import pytest
from django.contrib.auth.models import Group, Permission
from django.contrib.messages import get_messages
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import MODERATORS_GROUP, Avatar, User
from apps.accounts.tests import photo_fixtures as fx
from apps.moderation import services
from apps.moderation.models import ActionKind, ModerationAction
from apps.moderation.tests.factories import moderator_user, senior_user
from apps.posts.tests.factories import VerifiedUserFactory

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("role_groups")]

USERS = reverse("admin:accounts_user_changelist")
AVATARS = reverse("admin:accounts_avatar_changelist")


@pytest.fixture
def mod(client):
    user = moderator_user()
    client.force_login(user)
    return user


def person(username=None, *, photo=True, blocked=False):
    user = VerifiedUserFactory(**({"username": username} if username else {}))
    if photo:
        fx.give_photo(user, fx.jpeg(colour=(len(user.username) * 9 % 255, 40, 40)))
    if blocked:
        User.objects.filter(pk=user.pk).update(avatar_uploads_blocked=True)
    return User.objects.get(pk=user.pk)


def texts(response):
    return [str(message) for message in get_messages(response.wsgi_request)]


def act(client, url, name, *objects, apply=False, **extra):
    data = {"action": name, "_selected_action": [str(o.pk) for o in objects], **extra}
    if apply:
        data["apply"] = "1"
    else:
        data.update({"index": "0", "select_across": "0"})
    return client.post(url, data)


def rows():
    return list(ModerationAction.objects.order_by("created_at", "id"))


# ---------- Remove photo, from the account list ----------


@pytest.mark.parametrize("who", ["moderator", "senior", "superuser"])
def test_moderators_and_up_remove_a_photo_with_a_confirmation(client, who):
    actor = {
        "moderator": moderator_user,
        "senior": senior_user,
        "superuser": lambda: User.objects.create_superuser(
            "root@example.test", "root", "a-long-password-1"
        ),
    }[who]()
    client.force_login(actor)
    target = person("target_person")

    page = act(client, USERS, "remove_photo", target)
    body = page.content.decode()
    assert page.status_code == 200
    assert "Remove photo: are you sure?" in body
    assert "initials everywhere at once" in body and "target_person" in body
    assert "Photo now" in body and "Photo after this" in body
    assert "Has a photo, uploads allowed" in body and "No photo, uploads allowed" in body
    # Nothing happens until it is confirmed.
    assert Avatar.objects.filter(user=target).exists()

    done = act(client, USERS, "remove_photo", target, apply=True, notes="Not a face.")
    assert done.status_code == 302
    assert "Removed the photo of 1 account." in texts(done)
    (row,) = rows()
    assert (row.action, row.subject_user, row.moderator, row.post, row.notes) == (
        ActionKind.AVATAR_REMOVED,
        target,
        actor,
        None,
        "Not a face.",
    )
    assert User.objects.get(pk=target.pk).avatar_version is None
    assert not Avatar.objects.filter(user=target).exists()


def test_the_confirmation_page_has_internal_notes_and_no_public_note(client, mod):
    body = act(client, USERS, "block_photo_uploads", person()).content.decode()
    assert "Internal notes" in body and "public_note" not in body


def test_block_photo_uploads_removes_the_photo_and_logs_two_rows(client, mod):
    target = person("blocked_person")
    page = act(client, USERS, "block_photo_uploads", target).content.decode()
    assert "also removes the account&#x27;s current photo" in page
    assert "No photo, uploads blocked" in page

    done = act(client, USERS, "block_photo_uploads", target, apply=True, notes="Abuse.")
    assert "Blocked photo uploads on 1 account." in texts(done)
    removed, blocked = rows()
    assert (removed.action, blocked.action) == (
        ActionKind.AVATAR_REMOVED,
        ActionKind.AVATAR_BLOCKED,
    )
    after = User.objects.get(pk=target.pk)
    assert (after.avatar_version, after.avatar_uploads_blocked) == (None, True)


def test_allow_photo_uploads_lifts_the_block(client, mod):
    target = person(photo=False, blocked=True)
    page = act(client, USERS, "allow_photo_uploads", target).content.decode()
    assert "A photo that was removed stays removed" in page
    done = act(client, USERS, "allow_photo_uploads", target, apply=True)
    assert "Allowed photo uploads on 1 account." in texts(done)
    assert [row.action for row in rows()] == [ActionKind.AVATAR_UNBLOCKED]
    assert User.objects.get(pk=target.pk).avatar_uploads_blocked is False


def test_an_account_with_no_photo_can_still_be_blocked_and_allowed_from_the_user_list(client, mod):
    target = person(photo=False)
    act(client, USERS, "block_photo_uploads", target, apply=True)
    assert User.objects.get(pk=target.pk).avatar_uploads_blocked is True
    act(client, USERS, "allow_photo_uploads", target, apply=True)
    assert User.objects.get(pk=target.pk).avatar_uploads_blocked is False


def test_refused_accounts_are_listed_as_skipped_and_not_touched(client, mod):
    no_photo = person("nobody_here", photo=False)
    blocked = person("already_blocked", photo=False, blocked=True)
    page = act(client, USERS, "remove_photo", no_photo).content.decode()
    assert "no profile photo" in page and "None of the selected accounts" in page
    page = act(client, USERS, "block_photo_uploads", blocked).content.decode()
    assert "photo uploads already blocked" in page
    page = act(client, USERS, "allow_photo_uploads", no_photo).content.decode()
    assert "photo uploads not blocked" in page

    response = act(client, USERS, "remove_photo", no_photo, apply=True)
    assert "Skipped 1: 1 no profile photo." in texts(response)
    assert not ModerationAction.objects.exists()


def test_a_superuser_account_and_your_own_are_skipped(client, mod):
    root = User.objects.create_superuser("root@example.test", "root", "a-long-password-1")
    fx.give_photo(root)
    fx.give_photo(mod)
    body = act(client, USERS, "remove_photo", root, mod).content.decode()
    assert "a superuser&#x27;s account" in body and "your own account" in body
    act(client, USERS, "remove_photo", root, mod, apply=True)
    assert not ModerationAction.objects.exists()
    assert Avatar.objects.count() == 2


def test_the_apply_step_acts_on_the_shown_ids_never_select_across(client, mod):
    shown, other = person(), person()
    response = client.post(
        USERS,
        {
            "action": "remove_photo",
            "apply": "1",
            "select_across": "1",
            "_selected_action": [str(shown.pk), "not-a-uuid"],
        },
    )
    assert response.status_code == 302
    assert list(ModerationAction.objects.values_list("subject_user", flat=True)) == [shown.pk]
    assert Avatar.objects.filter(user=other).exists()


def test_a_batch_over_100_accounts_is_refused(client, mod):
    accounts = [VerifiedUserFactory() for _ in range(101)]
    response = act(client, USERS, "block_photo_uploads", *accounts)
    assert "Select at most 100 accounts at a time." in texts(response)
    assert not ModerationAction.objects.exists()


def test_the_account_list_offers_the_three_photo_actions_to_a_moderator(client, mod):
    person()
    page = client.get(USERS).content.decode()
    for name in ("remove_photo", "block_photo_uploads", "allow_photo_uploads"):
        assert f'value="{name}"' in page


def test_without_the_permission_there_are_no_photo_actions_and_nothing_happens(client):
    group = Group.objects.get(name=MODERATORS_GROUP)
    group.permissions.remove(Permission.objects.get(codename="moderate_profile_photos"))
    client.force_login(moderator_user())
    target = person()
    page = client.get(USERS).content.decode()
    assert "remove_photo" not in page and "block_photo_uploads" not in page
    act(client, USERS, "remove_photo", target, apply=True)
    assert not ModerationAction.objects.exists() and Avatar.objects.filter(user=target).exists()

    client.force_login(VerifiedUserFactory())  # not staff
    response = act(client, USERS, "remove_photo", target, apply=True)
    assert response.status_code == 302 and "/login/" in response["Location"]
    assert not ModerationAction.objects.exists()


# ---------- the account page and the filter ----------


def test_the_account_page_shows_the_photo_the_block_and_the_photo_actions(client, mod):
    target = person("photo_subject")
    services.block_photo_uploads(
        target.pk, moderator=moderator_user(username="the_decider"), notes="Abuse."
    )
    page = client.get(reverse("admin:accounts_user_change", args=[target.pk])).content.decode()

    assert "Photo" in page and "Uploads blocked" in page
    assert "Photo removed" in page and "Photo uploads blocked" in page
    assert "the_decider" in page and "Abuse." in page


def test_the_account_page_shows_the_thumbnail_of_a_current_photo(client, mod):
    target = person()
    page = client.get(reverse("admin:accounts_user_change", args=[target.pk])).content.decode()
    version = Avatar.objects.get(user=target).version
    assert f"/api/v1/avatars/{target.pk}/{version}-96.webp" in page
    assert "Uploads allowed" in page


def test_the_account_page_says_no_photo_when_there_is_none(client, mod):
    target = person(photo=False)
    page = client.get(reverse("admin:accounts_user_change", args=[target.pk])).content.decode()
    assert "No photo" in page and "avatars/" not in page.split("Photo")[1][:300]


def test_the_account_page_hides_the_photo_without_the_permission(client):
    group = Group.objects.get(name=MODERATORS_GROUP)
    group.permissions.remove(Permission.objects.get(codename="moderate_profile_photos"))
    client.force_login(moderator_user())
    target = person()
    page = client.get(reverse("admin:accounts_user_change", args=[target.pk])).content.decode()
    assert "Uploads allowed" not in page and "-96.webp" not in page


def test_the_photo_uploads_filter(client, mod):
    person("is_blocked", photo=False, blocked=True)
    person("is_allowed", photo=False)
    assert "By photo uploads" in client.get(USERS).content.decode()
    page = client.get(USERS, {"photo_uploads": "blocked"}).content.decode()
    assert "is_blocked" in page and "is_allowed" not in page
    page = client.get(USERS, {"photo_uploads": "allowed"}).content.decode()
    assert "is_allowed" in page and "is_blocked" not in page


def test_the_account_form_still_saves_for_a_superuser_and_keeps_the_photo(client):
    """The Photo field is read-only text, so the form's own POST is unchanged and a stale full save
    can neither bring a removed photo back nor lift a block."""
    root = User.objects.create_superuser("root@example.test", "root", "a-long-password-1")
    client.force_login(root)
    target = person()
    response = client.post(
        reverse("admin:accounts_user_change", args=[target.pk]),
        {
            "email": target.email,
            "username": target.username,
            "display_name": "Renamed",
            "bio": "",
            "role": "user",
            "is_active": "on",
        },
    )
    assert response.status_code == 302
    after = User.objects.get(pk=target.pk)
    assert after.display_name == "Renamed" and after.avatar_version == target.avatar_version


# ---------- the photo list (AvatarAdmin) ----------


def test_the_photo_list_shows_thumbnails_newest_change_first(client, mod):
    older = person("older_photo")
    newer = person("newer_photo")
    Avatar.objects.filter(user=older).update(updated_at=timezone.now() - timedelta(days=2))
    page = client.get(AVATARS).content.decode()

    assert page.index("newer_photo") < page.index("older_photo")
    version = Avatar.objects.get(user=newer).version
    assert f"/api/v1/avatars/{newer.pk}/{version}-96.webp" in page
    assert reverse("admin:accounts_user_change", args=[newer.pk]) in page


def test_the_photo_list_never_loads_the_image_bytes(client, mod):
    for _ in range(3):
        person()
    with CaptureQueriesContext(connection) as queries:
        assert client.get(AVATARS).status_code == 200
    assert not [q for q in queries if "image_256" in q["sql"] or "image_96" in q["sql"]]


def test_the_photo_list_searches_by_username(client, mod):
    person("findable_ada")
    person("someone_else")
    page = client.get(AVATARS, {"q": "findable"}).content.decode()
    assert "findable_ada" in page and "someone_else" not in page


def test_a_photo_page_is_view_only_and_shows_no_bytes(client, mod):
    target = person()
    row = Avatar.objects.get(user=target)
    page = client.get(reverse("admin:accounts_avatar_change", args=[target.pk]))
    body = page.content.decode()
    assert page.status_code == 200
    assert row.version in body and str(row.bytes_total) in body
    assert 'name="_save"' not in body and "deletelink" not in body


def test_nobody_adds_changes_or_deletes_a_photo_through_the_admin(client):
    root = User.objects.create_superuser("root@example.test", "root", "a-long-password-1")
    client.force_login(root)
    target = person()
    assert client.get(reverse("admin:accounts_avatar_add")).status_code == 403
    change = reverse("admin:accounts_avatar_change", args=[target.pk])
    assert client.post(change, {"version": "0123456789abcdef"}).status_code == 403
    assert client.post(reverse("admin:accounts_avatar_delete", args=[target.pk])).status_code == 403
    page = client.get(AVATARS).content.decode()
    assert "delete_selected" not in page
    assert Avatar.objects.get(user=target).version != "0123456789abcdef"


def test_the_photo_list_has_remove_and_block_but_not_allow(client, mod):
    person()
    page = client.get(AVATARS).content.decode()
    assert 'value="remove_photo"' in page and 'value="block_photo_uploads"' in page
    assert 'value="allow_photo_uploads"' not in page


def test_remove_photo_from_the_photo_list(client, mod):
    target = person("listed_person")
    page = act(client, AVATARS, "remove_photo", target)
    body = page.content.decode()
    assert page.status_code == 200 and "listed_person" in body
    assert f'href="{AVATARS}"' in body  # the breadcrumb goes back to the photo list

    done = act(client, AVATARS, "remove_photo", target, apply=True, notes="From the list.")
    assert "Removed the photo of 1 account." in texts(done)
    (row,) = rows()
    assert (row.action, row.subject_user, row.notes) == (
        ActionKind.AVATAR_REMOVED,
        target,
        "From the list.",
    )
    assert not Avatar.objects.filter(user=target).exists()


def test_block_photo_uploads_from_the_photo_list_logs_two_rows(client, mod):
    target = person()
    act(client, AVATARS, "block_photo_uploads", target, apply=True)
    assert [row.action for row in rows()] == [ActionKind.AVATAR_REMOVED, ActionKind.AVATAR_BLOCKED]
    assert User.objects.get(pk=target.pk).avatar_uploads_blocked is True


def test_the_photo_list_apply_step_ignores_select_across_and_bad_ids(client, mod):
    shown, other = person(), person()
    response = client.post(
        AVATARS,
        {
            "action": "remove_photo",
            "apply": "1",
            "select_across": "1",
            "_selected_action": [str(shown.pk), "../etc/passwd"],
        },
    )
    assert response.status_code == 302
    assert (
        Avatar.objects.filter(user=other).exists()
        and not Avatar.objects.filter(user=shown).exists()
    )


def test_the_photo_list_needs_the_view_permission(client):
    group = Group.objects.get(name=MODERATORS_GROUP)
    group.permissions.remove(Permission.objects.get(codename="view_avatar"))
    client.force_login(moderator_user())
    assert client.get(AVATARS).status_code == 403
    client.force_login(VerifiedUserFactory())
    assert client.get(AVATARS).status_code == 302  # not staff: the login page


def test_a_senior_moderator_reaches_the_photo_list_through_the_moderators_group(client):
    client.force_login(senior_user())
    person()
    assert client.get(AVATARS).status_code == 200


def test_a_photo_page_history_is_for_those_who_may_read_the_admin_log(client, mod):
    target = person()
    history = reverse("admin:accounts_avatar_history", args=[target.pk])
    assert client.get(history).status_code == 403
    client.force_login(senior_user())
    assert client.get(history).status_code == 200


def test_a_deleted_account_leaves_the_photo_list_and_its_audit_rows_lose_the_account(client, mod):
    from apps.accounts import deletion

    target = person()
    services.remove_photo(target.pk, moderator=moderator_user())
    deletion.delete_account(target)
    assert not Avatar.objects.exists()
    (row,) = rows()
    assert row.subject_user is None and row.action == ActionKind.AVATAR_REMOVED
    assert client.get(AVATARS).status_code == 200
