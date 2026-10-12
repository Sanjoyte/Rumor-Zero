"""Django Admin for likes and comments: read-only lists, plus Hide and Unhide on comments."""

import pytest
from django.contrib import admin
from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.auth.models import Permission
from django.urls import reverse

from apps.accounts.models import Role, User
from apps.accounts.tests.factories import UserFactory
from apps.social.models import Comment, Like
from apps.social.tests.factories import CommentFactory, LikeFactory

pytestmark = pytest.mark.django_db

CHANGELIST = "admin:social_comment_changelist"


@pytest.fixture
def superuser(client):
    user = User.objects.create_superuser(
        email="root@example.test", username="root_user", password="S3cure-pass-phrase!"
    )
    client.force_login(user)
    return user


def staff_with(client, *codenames):
    """A moderator (so `is_staff`; `User.save` derives it from the role) holding only these
    permissions: the Moderators group (Part 10) holds some of them already, so it is left."""
    user = UserFactory(role=Role.MODERATOR)
    user.groups.clear()
    user.user_permissions.set(Permission.objects.filter(codename__in=codenames))
    client.force_login(user)
    return user


def act(client, action, *comments):
    return client.post(
        reverse(CHANGELIST),
        {"action": action, "_selected_action": [str(c.pk) for c in comments]},
        follow=True,
    )


def test_like_and_comment_are_registered_in_the_admin():
    assert Like in admin.site._registry
    assert Comment in admin.site._registry


def test_the_like_changelist_renders_searches_and_is_read_only(client, superuser):
    like = LikeFactory(user__username="needle_fan")
    LikeFactory(user__username="other_fan")
    url = reverse("admin:social_like_changelist")
    page = client.get(url, {"q": "needle_fan"})
    assert page.status_code == 200
    assert b"needle_fan" in page.content
    assert b"other_fan" not in page.content
    assert client.get(reverse("admin:social_like_add")).status_code == 403
    assert client.post(reverse("admin:social_like_change", args=[like.pk])).status_code == 403
    assert client.post(reverse("admin:social_like_delete", args=[like.pk])).status_code == 403
    assert Like.objects.count() == 2


def test_the_comment_changelist_shows_every_comment_with_its_state(client, superuser):
    CommentFactory(content="a shown one")
    CommentFactory(content="a hidden one", hidden=True)
    CommentFactory(content="a deleted one", deleted=True)
    page = client.get(reverse(CHANGELIST))
    assert page.status_code == 200
    for text in (b"a shown one", b"a hidden one", b"a deleted one"):
        assert text in page.content


def test_the_comment_changelist_searches_and_filters(client, superuser):
    CommentFactory(content="needle text", author__username="somebody")
    CommentFactory(content="plain", author__username="needle_writer")
    CommentFactory(content="other", author__username="nobody", hidden=True)
    url = reverse(CHANGELIST)
    both = client.get(url, {"q": "needle"})
    assert b"needle text" in both.content and b"plain" in both.content
    assert b"other" not in both.content
    only_hidden = client.get(url, {"is_hidden__exact": "1"})
    assert b"other" in only_hidden.content and b"needle text" not in only_hidden.content
    only_deleted = client.get(url, {"deleted_at__isempty": "0"})
    assert only_deleted.status_code == 200


def test_nobody_can_add_change_or_delete_a_comment_from_the_admin(client, superuser):
    comment = CommentFactory(content="original")
    assert client.get(reverse("admin:social_comment_add")).status_code == 403
    change = reverse("admin:social_comment_change", args=[comment.pk])
    assert client.post(change, {"content": "edited"}).status_code == 403
    assert client.post(reverse("admin:social_comment_delete", args=[comment.pk])).status_code == 403
    comment.refresh_from_db()
    assert comment.content == "original"
    assert Comment.objects.count() == 1


def test_hide_hides_the_selected_comments_and_logs_each_one(client, superuser):
    one, two, untouched = CommentFactory(), CommentFactory(), CommentFactory()
    response = act(client, "hide_comments", one, two)
    assert b"Hidden: 2 comments." in response.content
    one.refresh_from_db(), two.refresh_from_db(), untouched.refresh_from_db()
    assert (one.is_hidden, two.is_hidden, untouched.is_hidden) == (True, True, False)
    log = LogEntry.objects.filter(action_flag=CHANGE, object_id=str(one.pk)).get()
    assert (log.user_id, log.change_message) == (superuser.pk, "Hidden")


def test_an_already_hidden_comment_is_not_changed_or_logged_again(client, superuser):
    comment = CommentFactory(hidden=True)
    response = act(client, "hide_comments", comment)
    assert b"Hidden: 0 comments." in response.content
    assert LogEntry.objects.count() == 0


def test_a_hidden_comment_disappears_from_the_public_list_and_count(client, api_client, superuser):
    comment = CommentFactory()
    post_url = f"/api/v1/posts/{comment.post_id}/"
    assert api_client.get(post_url).json()["comment_count"] == 1
    act(client, "hide_comments", comment)
    assert api_client.get(post_url).json()["comment_count"] == 0
    assert api_client.get(f"{post_url}comments/").json()["results"] == []


def test_unhide_brings_a_comment_back_and_logs_it(client, api_client, superuser):
    comment = CommentFactory(hidden=True)
    response = act(client, "unhide_comments", comment)
    assert b"Unhidden: 1 comment." in response.content
    comment.refresh_from_db()
    assert comment.is_hidden is False
    assert LogEntry.objects.get(object_id=str(comment.pk)).change_message == "Unhidden"
    assert len(api_client.get(f"/api/v1/posts/{comment.post_id}/comments/").json()["results"]) == 1


def test_unhide_does_not_undelete_what_the_author_deleted(client, api_client, superuser):
    comment = CommentFactory(hidden=True, deleted=True)
    act(client, "unhide_comments", comment)
    comment.refresh_from_db()
    assert comment.is_hidden is False
    assert comment.deleted_at is not None
    assert api_client.get(f"/api/v1/posts/{comment.post_id}/comments/").json()["results"] == []


def test_staff_without_the_change_permission_cannot_hide(client):
    staff_with(client, "view_comment")
    comment = CommentFactory()
    act(client, "hide_comments", comment)
    comment.refresh_from_db()
    assert comment.is_hidden is False
    page = client.get(reverse(CHANGELIST))
    assert page.status_code == 200  # they can look...
    assert b"hide_comments" not in page.content  # ...but the actions aren't offered


def test_staff_with_the_change_permission_can_hide_and_unhide(client):
    staff_with(client, "view_comment", "change_comment")
    comment = CommentFactory()
    act(client, "hide_comments", comment)
    comment.refresh_from_db()
    assert comment.is_hidden is True
    act(client, "unhide_comments", comment)
    comment.refresh_from_db()
    assert comment.is_hidden is False


def test_an_ordinary_user_cannot_reach_the_admin(client):
    client.force_login(UserFactory())
    assert client.get(reverse(CHANGELIST)).status_code == 302
