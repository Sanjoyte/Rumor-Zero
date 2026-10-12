"""The two seniors-only logs: the moderation log and Django's admin log (both read-only)."""

import pytest
from django.contrib.admin.models import CHANGE, LogEntry
from django.urls import reverse

from apps.accounts.models import Role
from apps.accounts.tests.factories import UserFactory
from apps.moderation.models import ActionKind
from apps.moderation.tests.factories import ModerationActionFactory, moderator_user, senior_user
from apps.posts.tests.factories import PostFactory

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("role_groups")]

LOG = reverse("admin:moderation_moderationaction_changelist")


@pytest.fixture
def boss(client):
    user = senior_user()
    client.force_login(user)
    return user


def test_the_moderation_log_lists_what_moderators_did(client, boss):
    post = PostFactory(content="a post that was acted on")
    ModerationActionFactory(
        post=post,
        post_snapshot=post.content,
        moderator=moderator_user(username="the_mod"),
        action=ActionKind.MARKED_FALSE,
        from_status="under_review",
        to_status="verified_false",
    )
    body = client.get(LOG).content.decode()
    assert "the_mod" in body and "Marked FALSE" in body
    assert "under_review → verified_false" in body
    assert "a post that was acted on" in body
    assert f'href="{reverse("admin:posts_post_change", args=[post.pk])}"' in body


def test_a_row_whose_post_is_gone_still_shows_its_snapshot_without_a_link(client, boss):
    post = PostFactory(content="the text it had")
    ModerationActionFactory(post=post, post_snapshot=post.content)
    post.delete()
    body = client.get(LOG).content.decode()
    assert "the text it had" in body and "/admin/posts/post/" not in body.split("<tbody>")[1]


def test_the_log_filters_and_searches(client, boss):
    ModerationActionFactory(post_snapshot="alpha claim", action=ActionKind.REMOVED)
    ModerationActionFactory(
        post_snapshot="beta claim", action=ActionKind.ESCALATED, from_status=None, to_status=None
    )
    body = client.get(LOG, {"action__exact": "escalated"}).content.decode()
    assert "beta claim" in body and "alpha claim" not in body
    body = client.get(LOG, {"q": "alpha"}).content.decode()
    assert "alpha claim" in body and "beta claim" not in body
    by_moderator = moderator_user(username="needle_mod")
    ModerationActionFactory(post_snapshot="gamma claim", moderator=by_moderator)
    body = client.get(LOG, {"q": "needle_mod"}).content.decode()
    assert "gamma claim" in body and "alpha claim" not in body


def test_nobody_edits_or_deletes_a_log_row_even_a_superuser(client):
    client.force_login(UserFactory(is_superuser=True))
    row = ModerationActionFactory()
    change = reverse("admin:moderation_moderationaction_change", args=[row.pk])
    page = client.get(change)
    assert page.status_code == 200 and b'name="_save"' not in page.content
    assert client.post(change, {"notes": "edited"}).status_code == 403
    assert client.get(reverse("admin:moderation_moderationaction_add")).status_code == 403
    delete = reverse("admin:moderation_moderationaction_delete", args=[row.pk])
    assert client.get(delete).status_code == 403
    assert client.post(delete, {"post": "yes"}).status_code == 403
    assert type(row).objects.filter(pk=row.pk).exists()


def test_the_admin_log_shows_account_and_comment_changes_with_their_values(client, boss):
    target = UserFactory(role=Role.MODERATOR)
    client.post(
        reverse("admin:accounts_user_change", args=[target.pk]),
        {
            "email": target.email,
            "username": target.username,
            "display_name": "",
            "bio": "",
            "role": Role.USER,
            "is_active": "on",
        },
    )
    body = client.get(reverse("admin:admin_logentry_changelist")).content.decode()
    assert "Role: moderator → user." in body
    assert boss.username in body


def test_the_admin_log_is_read_only_and_filterable(client, boss):
    target = UserFactory()
    LogEntry.objects.log_actions(boss.pk, [target], CHANGE, change_message="Hidden")
    url = reverse("admin:admin_logentry_changelist")
    assert client.get(url, {"action_flag__exact": str(CHANGE)}).status_code == 200
    assert client.get(url, {"q": target.username}).status_code == 200
    entry = LogEntry.objects.get()
    change = reverse("admin:admin_logentry_change", args=[entry.pk])
    assert client.get(change).status_code == 200
    assert client.post(change, {"object_repr": "x"}).status_code == 403
    assert client.get(reverse("admin:admin_logentry_add")).status_code == 403
    assert (
        client.post(
            reverse("admin:admin_logentry_delete", args=[entry.pk]), {"post": "yes"}
        ).status_code
        == 403
    )
    assert LogEntry.objects.filter(pk=entry.pk).exists()


def test_a_moderator_gets_neither_log(client):
    client.force_login(moderator_user())
    assert client.get(LOG).status_code == 403
    assert client.get(reverse("admin:admin_logentry_changelist")).status_code == 403
