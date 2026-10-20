"""Notifications in Django Admin: read-only, for support (ARCHITECTURE §8)."""

import pytest
from django.contrib import admin
from django.urls import reverse

from apps.accounts.models import User
from apps.notifications.models import Notification
from apps.notifications.tests.factories import NotificationFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def superuser(client):
    user = User.objects.create_superuser(
        email="root@example.test", username="root_user", password="S3cure-pass-phrase!"
    )
    client.force_login(user)
    return user


def test_notifications_are_registered():
    assert Notification in admin.site._registry


def test_the_changelist_shows_each_item_and_filters(client, superuser):
    NotificationFactory(recipient__username="recipient_one", actor__username="actor_one")
    url = reverse("admin:notifications_notification_changelist")
    page = client.get(url)
    assert page.status_code == 200
    assert b"recipient_one" in page.content
    assert b"actor_one" in page.content
    assert b"recipient_one" in client.get(url, {"type": "like"}).content
    assert b"recipient_one" not in client.get(url, {"type": "follow"}).content
    assert b"recipient_one" in client.get(url, {"q": "actor_one"}).content


def test_one_item_opens_read_only(client, superuser):
    item = NotificationFactory()
    url = reverse("admin:notifications_notification_change", args=[item.pk])
    page = client.get(url)
    assert page.status_code == 200
    assert b'name="_save"' not in page.content
    assert client.post(url, {"is_read": "on"}).status_code in (403, 302)
    item.refresh_from_db()
    assert not item.is_read


def test_nobody_can_add_or_delete_an_item(client, superuser):
    item = NotificationFactory()
    assert client.get(reverse("admin:notifications_notification_add")).status_code == 403
    delete = reverse("admin:notifications_notification_delete", args=[item.pk])
    assert client.get(delete).status_code == 403
    assert Notification.objects.count() == 1
