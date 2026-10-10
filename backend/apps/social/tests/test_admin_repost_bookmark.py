"""Django Admin for reposts (read-only) and bookmarks (read-only and superusers only, because
bookmarks are private: user decision 2026-10-10)."""

import pytest
from django.contrib import admin
from django.contrib.auth.models import Permission
from django.urls import reverse

from apps.accounts.models import Role, User
from apps.accounts.tests.factories import UserFactory
from apps.social.models import Bookmark, Repost
from apps.social.tests.factories import BookmarkFactory, RepostFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def superuser(client):
    user = User.objects.create_superuser(
        email="root@example.test", username="root_user", password="S3cure-pass-phrase!"
    )
    client.force_login(user)
    return user


def moderator_with(client, *codenames):
    """A moderator (so `is_staff`; `User.save` derives it from the role) holding exactly these
    permissions."""
    user = UserFactory(role=Role.MODERATOR)
    user.user_permissions.set(Permission.objects.filter(codename__in=codenames))
    client.force_login(user)
    return user


def test_both_models_are_registered_in_the_admin():
    assert Repost in admin.site._registry
    assert Bookmark in admin.site._registry


def test_the_repost_changelist_renders_filters_searches_and_is_read_only(client, superuser):
    repost = RepostFactory(user__username="needle_fan", status_at_repost="pending")
    RepostFactory(user__username="other_fan")
    url = reverse("admin:social_repost_changelist")
    page = client.get(url, {"q": "needle_fan"})
    assert page.status_code == 200
    assert b"needle_fan" in page.content and b"other_fan" not in page.content
    assert client.get(url, {"status_at_repost": "pending"}).status_code == 200
    assert client.get(reverse("admin:social_repost_add")).status_code == 403
    assert client.post(reverse("admin:social_repost_change", args=[repost.pk])).status_code == 403
    assert client.post(reverse("admin:social_repost_delete", args=[repost.pk])).status_code == 403


def test_a_superuser_sees_the_bookmarks_read_only(client, superuser):
    bookmark = BookmarkFactory(user__username="needle_saver")
    BookmarkFactory(user__username="other_saver")
    url = reverse("admin:social_bookmark_changelist")
    page = client.get(url, {"q": "needle_saver"})
    assert page.status_code == 200
    assert b"needle_saver" in page.content and b"other_saver" not in page.content
    assert client.get(reverse("admin:social_bookmark_add")).status_code == 403
    assert (
        client.post(reverse("admin:social_bookmark_change", args=[bookmark.pk])).status_code == 403
    )
    assert (
        client.post(reverse("admin:social_bookmark_delete", args=[bookmark.pk])).status_code == 403
    )
    assert b"Bookmarks" in client.get(reverse("admin:index")).content


def test_a_moderator_cannot_open_bookmarks_even_with_every_bookmark_permission(client):
    moderator_with(
        client, "view_bookmark", "change_bookmark", "delete_bookmark", "add_bookmark", "view_repost"
    )
    BookmarkFactory()
    assert client.get(reverse("admin:social_bookmark_changelist")).status_code == 403
    assert client.get(reverse("admin:social_bookmark_add")).status_code == 403
    index = client.get(reverse("admin:index")).content
    assert b"Bookmarks" not in index  # not even listed on the admin home
    assert b"Reposts" in index  # reposts are an ordinary read-only model


def test_a_moderator_with_the_repost_permission_can_view_reposts(client):
    moderator_with(client, "view_repost")
    RepostFactory()
    assert client.get(reverse("admin:social_repost_changelist")).status_code == 200


def test_a_bookmark_never_appears_in_any_other_admin_page(client, superuser):
    bookmark = BookmarkFactory(user__username="private_person")
    assert b"private_person" not in client.get(reverse("admin:social_repost_changelist")).content
    assert b"private_person" not in client.get(reverse("admin:social_like_changelist")).content
    assert bookmark.pk
