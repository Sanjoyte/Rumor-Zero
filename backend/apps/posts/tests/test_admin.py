import pytest
from django.contrib import admin
from django.urls import reverse

from apps.accounts.models import User
from apps.posts.models import Post
from apps.posts.tests.factories import PostFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def superuser(client):
    user = User.objects.create_superuser(
        email="root@example.test", username="root_user", password="S3cure-pass-phrase!"
    )
    client.force_login(user)
    return user


def test_post_is_registered_in_the_admin():
    assert Post in admin.site._registry


def test_the_changelist_renders_with_filters_and_search(client, superuser):
    PostFactory(content="A claim about trains", fact=True)
    PostFactory(content="An opinion about buses")
    url = reverse("admin:posts_post_changelist")
    assert client.get(url).status_code == 200
    page = client.get(url, {"q": "trains"})
    assert page.status_code == 200
    assert b"A claim about trains" in page.content
    assert b"An opinion about buses" not in page.content
    assert client.get(url, {"post_type": "fact", "status": "pending"}).status_code == 200


def test_nobody_can_add_change_or_delete_a_post_from_the_admin(client, superuser):
    post = PostFactory()
    assert client.get(reverse("admin:posts_post_add")).status_code == 403
    assert client.post(reverse("admin:posts_post_add"), {"content": "x"}).status_code == 403
    change = reverse("admin:posts_post_change", args=[post.pk])
    assert client.post(change, {"content": "edited", "post_type": "opinion"}).status_code == 403
    assert client.get(reverse("admin:posts_post_delete", args=[post.pk])).status_code == 403
    post.refresh_from_db()
    assert post.content != "edited"


def test_the_detail_page_is_view_only(client, superuser):
    post = PostFactory(content="Look but do not touch")
    page = client.get(reverse("admin:posts_post_change", args=[post.pk]))
    assert page.status_code == 200
    assert b"Look but do not touch" in page.content
    assert b'name="_save"' not in page.content
    assert b"deletelink" not in page.content
