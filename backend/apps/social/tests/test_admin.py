import pytest
from django.contrib import admin
from django.urls import reverse

from apps.accounts.models import User
from apps.social.models import Follow
from apps.social.tests.factories import FollowFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def superuser(client):
    user = User.objects.create_superuser(
        email="root@example.test", username="root_user", password="S3cure-pass-phrase!"
    )
    client.force_login(user)
    return user


def test_follow_is_registered_in_the_admin():
    assert Follow in admin.site._registry


def test_the_changelist_renders_and_searches_by_username(client, superuser):
    FollowFactory(follower__username="needle_fan", following__username="haystack_star")
    FollowFactory(follower__username="other_fan", following__username="other_star")
    url = reverse("admin:social_follow_changelist")
    assert client.get(url).status_code == 200
    page = client.get(url, {"q": "needle_fan"})
    assert page.status_code == 200
    assert b"needle_fan" in page.content
    assert b"other_fan" not in page.content


def test_nobody_can_add_change_or_delete_a_follow_from_the_admin(client, superuser):
    follow = FollowFactory()
    assert client.get(reverse("admin:social_follow_add")).status_code == 403
    change = reverse("admin:social_follow_change", args=[follow.pk])
    assert client.post(change, {"follower": superuser.pk}).status_code == 403
    assert client.get(reverse("admin:social_follow_delete", args=[follow.pk])).status_code == 403
    assert Follow.objects.filter(pk=follow.pk).exists()


def test_the_detail_page_is_view_only(client, superuser):
    follow = FollowFactory()
    page = client.get(reverse("admin:social_follow_change", args=[follow.pk]))
    assert page.status_code == 200
    assert b'name="_save"' not in page.content
