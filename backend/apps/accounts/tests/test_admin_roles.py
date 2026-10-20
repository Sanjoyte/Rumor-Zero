"""What seniors and moderators may do to accounts in Django Admin (Part 10): the change messages
with their values, suspension, Mark email verified, and deleting an account."""

import pytest
from allauth.account.models import EmailAddress
from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse

from apps.accounts import services
from apps.accounts.models import Role, User
from apps.accounts.tests.conftest import access_token_for, login, refresh
from apps.accounts.tests.factories import DEFAULT_PASSWORD, UserFactory
from apps.moderation.models import ModerationAction
from apps.moderation.tests.factories import ModerationActionFactory
from apps.notifications.models import Notification
from apps.notifications.tests.factories import NotificationFactory
from apps.posts.tests.factories import PostFactory
from apps.social.tests.factories import BookmarkFactory, CommentFactory

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("role_groups")]


def senior():
    return UserFactory(role=Role.SENIOR_MODERATOR)


def change_url(user, name="change"):
    return reverse(f"admin:accounts_user_{name}", args=[user.pk])


def form(user, **overrides):
    data = {
        "email": user.email,
        "username": user.username,
        "display_name": user.display_name,
        "bio": user.bio,
        "role": user.role,
        "is_active": "on" if user.is_active else "",
    }
    return {k: v for k, v in {**data, **overrides}.items() if v != ""}


def last_log(user):
    return LogEntry.objects.filter(
        content_type=ContentType.objects.get_for_model(User), object_id=str(user.pk)
    ).latest("action_time")


# ---------- change messages with values ----------


def test_a_role_change_is_logged_with_the_old_and_the_new_role(client):
    boss = senior()
    client.force_login(boss)
    target = UserFactory(role=Role.MODERATOR)
    client.post(change_url(target), form(target, role=Role.SENIOR_MODERATOR))
    entry = last_log(target)
    assert entry.get_change_message() == "Role: moderator → senior moderator."
    assert (entry.user, entry.action_flag) == (boss, CHANGE)


def test_a_suspension_is_logged_with_yes_and_no(client):
    client.force_login(senior())
    target = UserFactory()
    client.post(change_url(target), form(target, is_active=""))
    assert last_log(target).get_change_message() == "Active: yes → no."
    client.post(change_url(target), form(User.objects.get(pk=target.pk), is_active="on"))
    assert last_log(target).get_change_message() == "Active: no → yes."


def test_both_changes_at_once_are_one_message(client):
    client.force_login(senior())
    target = UserFactory(role=Role.MODERATOR)
    client.post(change_url(target), form(target, role=Role.USER, is_active=""))
    assert last_log(target).get_change_message() == "Role: moderator → user. Active: yes → no."


def test_a_superuser_changing_more_than_the_role_has_the_rest_named(client):
    client.force_login(UserFactory(is_superuser=True))
    target = UserFactory()
    client.post(change_url(target), form(target, role=Role.MODERATOR, bio="a bio"))
    assert last_log(target).get_change_message() == ("Role: user → moderator. Also changed: bio.")


def test_a_change_that_touches_neither_keeps_djangos_own_message(client):
    client.force_login(UserFactory(is_superuser=True))
    target = UserFactory()
    client.post(change_url(target), form(target, bio="only the bio"))
    assert "bio" in last_log(target).get_change_message().lower()
    assert "→" not in last_log(target).get_change_message()


def test_a_superusers_password_change_still_logs_djangos_message(client):
    client.force_login(UserFactory(is_superuser=True))
    target = UserFactory()
    response = client.post(
        reverse("admin:auth_user_password_change", args=[target.pk]),
        {"password1": "N3w-pass-phrase-here!", "password2": "N3w-pass-phrase-here!"},
    )
    assert response.status_code == 302
    assert last_log(target).get_change_message() == "Changed password."
    assert User.objects.get(pk=target.pk).check_password("N3w-pass-phrase-here!")


# ---------- suspension ----------


def test_a_suspended_account_cannot_log_in_use_its_token_or_refresh(
    client, site_client, api_client
):
    target = UserFactory(email="suspect@example.test")
    assert login(site_client, target.email).status_code == 200
    token = access_token_for(target)
    assert api_client.get("/api/v1/me/", HTTP_AUTHORIZATION=f"Bearer {token}").status_code == 200

    client.force_login(senior())
    assert client.post(change_url(target), form(target, is_active="")).status_code == 302
    assert User.objects.get(pk=target.pk).is_active is False

    assert refresh(site_client).status_code == 400  # the cookie's session no longer works
    assert api_client.get("/api/v1/me/", HTTP_AUTHORIZATION=f"Bearer {token}").status_code == 401
    fresh = login(site_client, target.email, DEFAULT_PASSWORD)
    assert fresh.status_code in (400, 401)
    assert api_client.get("/api/v1/me/").status_code in (401, 403)


def test_a_suspended_accounts_content_stays_up(client):
    target = UserFactory()
    post = PostFactory(author=target, content="still readable")
    client.force_login(senior())
    client.post(change_url(target), form(target, is_active=""))
    from apps.posts.models import Post

    assert Post.objects.visible().filter(pk=post.pk).exists()


# ---------- Mark email verified ----------


def verify(client, *users):
    return client.post(
        reverse("admin:accounts_user_changelist"),
        {"action": "verify_email", "index": "0", "_selected_action": [str(u.pk) for u in users]},
        follow=True,
    )


def test_marking_the_email_verified_sets_both_flags_and_creates_the_address(client):
    client.force_login(senior())
    target = UserFactory(email="stuck@example.test")
    assert target.is_email_verified is False and not EmailAddress.objects.filter(user=target)
    response = verify(client, target)
    assert "Marked the email verified on 1 account." in [
        str(m) for m in response.context["messages"]
    ]
    target.refresh_from_db()
    assert target.is_email_verified is True
    address = EmailAddress.objects.get(user=target)
    assert (address.email, address.verified, address.primary) == ("stuck@example.test", True, True)
    assert last_log(target).get_change_message() == "Marked email verified"


def test_it_verifies_an_address_that_exists_but_was_never_confirmed(client):
    client.force_login(senior())
    target = UserFactory(email="pending@example.test")
    EmailAddress.objects.create(user=target, email=target.email, verified=False, primary=True)
    verify(client, target)
    assert EmailAddress.objects.get(user=target).verified is True
    assert EmailAddress.objects.filter(user=target).count() == 1


def test_an_account_that_is_already_verified_is_skipped_and_not_logged(client):
    client.force_login(senior())
    target = UserFactory(is_email_verified=True)
    before = LogEntry.objects.count()
    response = verify(client, target)
    assert any("Skipped 1" in str(m) for m in response.context["messages"])
    assert LogEntry.objects.count() == before
    assert not EmailAddress.objects.filter(user=target).exists()


def test_a_senior_cannot_verify_a_superuser_or_themselves_this_way(client):
    boss = senior()
    client.force_login(boss)
    root = UserFactory(is_superuser=True)
    verify(client, root, boss)
    for account in (root, boss):
        account.refresh_from_db()
        assert account.is_email_verified is False


def test_a_moderator_cannot_run_the_action(client):
    client.force_login(UserFactory(role=Role.MODERATOR))
    target = UserFactory()
    verify(client, target)
    target.refresh_from_db()
    assert target.is_email_verified is False


def test_verify_email_by_staff_returns_what_it_did():
    user = UserFactory()
    assert services.verify_email_by_staff(user) is True
    assert services.verify_email_by_staff(user) is False
    assert User.objects.get(pk=user.pk).is_email_verified is True


def test_the_google_helper_behaves_as_before_after_the_move():
    user = UserFactory(email="gus@gmail.com")
    address = services.mark_email_verified_by_google(user, "  Gus@Gmail.com ")
    assert (address.email, address.verified, address.primary) == ("gus@gmail.com", True, True)
    assert user.is_email_verified is True and User.objects.get(pk=user.pk).is_email_verified


# ---------- deleting an account ----------


def test_deleting_an_account_with_posts_works_for_a_senior_and_keeps_the_log_rows(client):
    client.force_login(senior())
    target = UserFactory(role=Role.MODERATOR)
    post = PostFactory(author=target, content="their post")
    other_post = PostFactory(content="someone else's post")
    by_them = ModerationActionFactory(moderator=target, post=other_post)
    on_them = ModerationActionFactory(moderator=UserFactory(role=Role.MODERATOR), post=post)
    response = client.post(change_url(target, "delete"), {"post": "yes"})
    assert response.status_code == 302
    assert not User.objects.filter(pk=target.pk).exists()
    assert ModerationAction.objects.get(pk=by_them.pk).moderator is None
    kept = ModerationAction.objects.get(pk=on_them.pk)
    assert kept.post is None and kept.post_snapshot == "their post"


def test_the_delete_page_is_a_summary_with_no_bookmark_or_comment_text(client):
    client.force_login(senior())
    target = UserFactory()
    BookmarkFactory(user=target, post__content="a very private bookmark target")
    CommentFactory(author=target, content="a comment that must not be printed")
    PostFactory(author=target, content="a post that must not be printed")
    body = client.get(change_url(target, "delete")).content.decode()
    for secret in ("private bookmark target", "must not be printed", "bookmarked"):
        assert secret not in body
    assert "Posts: 1" in body and "Comments: 1" in body and "Bookmarks: 1" in body


def test_an_account_that_wrote_admin_log_entries_cannot_be_deleted_only_suspended(client):
    former_senior = UserFactory(role=Role.USER, username="former_boss")
    other = UserFactory()
    # The log entry that account wrote while it was a senior.
    LogEntry.objects.log_actions(
        former_senior.pk,
        [other],
        CHANGE,
        change_message="Role: user → moderator.",
    )
    for kind in ("senior", "superuser"):
        client.force_login(senior() if kind == "senior" else UserFactory(is_superuser=True))
        page = client.get(change_url(former_senior, "delete"))
        assert "former_boss wrote admin log entries" in page.content.decode()
        assert "Suspend the account instead" in page.content.decode()
        assert client.post(change_url(former_senior, "delete"), {"post": "yes"}).status_code == 200
        assert User.objects.filter(pk=former_senior.pk).exists()
    assert LogEntry.objects.filter(user=former_senior).exists()


def test_the_admin_delete_uses_the_owners_routine_and_discards_the_notifications_it_caused(client):
    """Part 14: Django's own delete would leave "Someone liked your post" behind (SET_NULL)."""
    client.force_login(senior())
    target = UserFactory()
    other = UserFactory()
    post = PostFactory(author=other)
    caused = NotificationFactory(recipient=other, actor=target, post=post)
    unrelated = NotificationFactory(recipient=other, actor=UserFactory(), post=post)

    assert client.post(change_url(target, "delete"), {"post": "yes"}).status_code == 302

    assert not User.objects.filter(pk=target.pk).exists()
    assert not Notification.objects.filter(pk=caused.pk).exists()
    assert Notification.objects.filter(pk=unrelated.pk).exists()


def test_a_superusers_bulk_delete_goes_through_the_same_routine(client):
    admin = UserFactory(is_superuser=True)
    client.force_login(admin)
    first, second, other = UserFactory(), UserFactory(), UserFactory()
    post = PostFactory(author=other)
    items = [
        NotificationFactory(recipient=other, actor=user, post=post) for user in (first, second)
    ]
    data = {
        "action": "delete_selected",
        "_selected_action": [str(first.pk), str(second.pk)],
        "post": "yes",
    }

    response = client.post(reverse("admin:accounts_user_changelist"), data)

    assert response.status_code == 302
    assert not User.objects.filter(pk__in=[first.pk, second.pk]).exists()
    assert not Notification.objects.filter(pk__in=[item.pk for item in items]).exists()
    assert User.objects.filter(pk=other.pk).exists()
