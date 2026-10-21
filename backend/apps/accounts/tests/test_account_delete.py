"""DELETE /api/v1/me/ and the deletion routine behind it (ARCHITECTURE §2, §7; Part 14)."""

import pytest
from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount
from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.sessions.models import Session
from django.test import Client

from apps.accounts import deletion
from apps.accounts.models import Role, User
from apps.accounts.tests.conftest import (
    SITE_HEADERS,
    access_token_for,
    login,
    refresh,
    sign_in,
)
from apps.accounts.tests.factories import DEFAULT_PASSWORD, UserFactory
from apps.accounts.tests.populate import fill
from apps.moderation.models import Appeal, ModerationAction
from apps.moderation.tests.factories import moderator_user, senior_user
from apps.notifications.models import Notification, NotificationType
from apps.notifications.tests.factories import NotificationFactory, comment_item
from apps.posts.models import Post
from apps.posts.tests.factories import PostFactory, VerifiedUserFactory
from apps.reports.models import Report
from apps.reports.tests.factories import ReportFactory
from apps.reputation.models import EventKind, ReputationEvent
from apps.reputation.tests.factories import EventFactory
from apps.social.models import Bookmark, Comment, Follow, Like, Repost
from apps.social.tests.factories import CommentFactory, LikeFactory

pytestmark = pytest.mark.django_db

URL = "/api/v1/me/"


def delete(client, token, body=None):
    return client.delete(URL, body, format="json", HTTP_AUTHORIZATION=f"Bearer {token}")


def delete_as(client, user, body=None):
    return delete(client, access_token_for(user), body)


def with_password(user_password=DEFAULT_PASSWORD):
    return {"password": user_password}


# ---------- what goes ----------


def test_the_account_and_everything_it_owns_goes(api_client):
    user = VerifiedUserFactory(username="ada")
    posts = fill(user)
    EmailAddress.objects.create(user=user, email=user.email, verified=True, primary=True)

    response = delete_as(api_client, user, with_password())

    assert response.status_code == 204 and response.content == b""
    assert not User.objects.filter(pk=user.pk).exists()
    for model, field in (
        (Post, "author"),
        (Comment, "author"),
        (Like, "user"),
        (Bookmark, "user"),
        (Repost, "user"),
        (Report, "reporter"),
        (Appeal, "author"),
        (ReputationEvent, "user"),
        (EmailAddress, "user"),
        (SocialAccount, "user"),
        (Notification, "recipient"),
    ):
        assert not model.objects.filter(**{f"{field}_id": user.pk}).exists(), model
    assert not Follow.objects.filter(follower_id=user.pk).exists()
    assert not Follow.objects.filter(following_id=user.pk).exists()
    assert not Post.objects.filter(pk__in=[p.pk for p in posts.values()]).exists()


def test_what_belongs_to_other_people_stays(api_client):
    user = VerifiedUserFactory()
    other = VerifiedUserFactory()
    others_post = PostFactory(author=other, content="Theirs")
    others_comment = CommentFactory(author=other, post=others_post, content="Theirs too")
    others_item = NotificationFactory(
        recipient=other, actor=VerifiedUserFactory(), post=others_post
    )
    # The account's actions on other people's things go; their things stay.
    LikeFactory(user=user, post=others_post)
    CommentFactory(author=user, post=others_post)

    assert delete_as(api_client, user, with_password()).status_code == 204

    assert Post.objects.filter(pk=others_post.pk).exists()
    assert Comment.objects.filter(pk=others_comment.pk).exists()
    assert Notification.objects.filter(pk=others_item.pk).exists()
    assert not Like.objects.filter(post=others_post, user_id=user.pk).exists()
    assert Comment.objects.filter(post=others_post).count() == 1


def test_the_notifications_the_account_caused_go_with_it(api_client):
    """Without the discard the foreign key would leave "Someone liked your post" behind."""
    user = VerifiedUserFactory()
    other = VerifiedUserFactory()
    post = PostFactory(author=other)
    like = NotificationFactory(recipient=other, actor=user, post=post)
    follow = NotificationFactory(
        recipient=other, actor=user, type=NotificationType.FOLLOW, post=None
    )
    comment = comment_item(other, user, post=post)
    unrelated = NotificationFactory(recipient=other, actor=VerifiedUserFactory(), post=post)

    assert delete_as(api_client, user, with_password()).status_code == 204

    assert not Notification.objects.filter(pk__in=[like.pk, follow.pk, comment.pk]).exists()
    assert Notification.objects.filter(pk=unrelated.pk).exists()
    assert Notification.objects.filter(actor__isnull=True, recipient=other).count() == 0


def test_moderation_records_keep_a_copy_of_the_removed_post(api_client):
    user = VerifiedUserFactory()
    fill(user)

    assert delete_as(api_client, user, with_password()).status_code == 204

    action = ModerationAction.objects.get(post_snapshot="Bad")
    assert action.post is None and action.moderator is not None
    assert action.created_at is not None


def test_the_audit_rows_of_a_deleted_moderator_keep_their_text():
    """The moderator becomes NULL (SET_NULL); the admin path itself is in test_admin_roles."""
    target = moderator_user()
    post = PostFactory(content="audited")
    row = ModerationAction.objects.create(
        post=post,
        post_snapshot="audited",
        moderator=target,
        action="removed",
        from_status="published",
        to_status="removed",
    )
    deletion.delete_account(target)
    row.refresh_from_db()
    assert row.moderator is None and row.post_snapshot == "audited"


def test_the_photo_goes_with_the_account_and_its_url_stops_working(api_client):
    from apps.accounts.models import Avatar
    from apps.accounts.tests import photo_fixtures as fx

    user = VerifiedUserFactory()
    version = fx.give_photo(user)
    other = VerifiedUserFactory()
    fx.give_photo(other, fx.jpeg(colour=fx.BLUE))
    url = f"/api/v1/avatars/{user.pk}/{version}-256.webp"
    assert api_client.get(url).status_code == 200

    assert delete_as(api_client, user, with_password()).status_code == 204

    assert not Avatar.objects.filter(user_id=user.pk).exists()
    assert Avatar.objects.filter(user=other).exists()  # nobody else's
    assert api_client.get(url).status_code == 404


def test_the_photo_audit_rows_stay_with_the_account_nulled(api_client):
    """Photo actions are about an account (`subject_user`), not a post: the rows are kept for the
    record when the account goes, as the emergency block rows are."""
    from apps.accounts.tests import photo_fixtures as fx
    from apps.moderation import services

    user = VerifiedUserFactory()
    fx.give_photo(user)
    services.block_photo_uploads(user.pk, moderator=moderator_user(), notes="Abuse.")
    assert ModerationAction.objects.filter(subject_user=user).count() == 2

    assert delete_as(api_client, user, with_password()).status_code == 204

    rows = ModerationAction.objects.filter(action__startswith="avatar_").order_by("created_at")
    assert [row.action for row in rows] == ["avatar_removed", "avatar_blocked"]
    assert all(row.subject_user is None and row.notes == "Abuse." for row in rows)


def test_report_counts_are_never_taken_back(api_client):
    user = VerifiedUserFactory()
    reported = PostFactory(author=VerifiedUserFactory(), report_count=2)
    ReportFactory(reporter=user, post=reported)

    assert delete_as(api_client, user, with_password()).status_code == 204

    reported.refresh_from_db()
    assert reported.report_count == 2
    assert not Report.objects.filter(post=reported).exists()


def test_other_peoples_ledger_rows_about_the_posts_lose_only_the_link(api_client):
    user = VerifiedUserFactory()
    post = PostFactory(author=user)
    row = EventFactory(user=VerifiedUserFactory(), kind=EventKind.REPOST_FALSE, post=post)

    assert delete_as(api_client, user, with_password()).status_code == 204

    row.refresh_from_db()
    assert row.post is None and row.kind == EventKind.REPOST_FALSE


# ---------- sessions and cookies ----------


def test_the_response_expires_both_cookies(api_client):
    user = VerifiedUserFactory()
    response = delete_as(api_client, user, with_password())
    for name in ("rz_refresh", "rz_session"):
        cookie = response.cookies[name]
        assert cookie.value == "" and cookie["max-age"] == 0
    assert response.cookies["rz_refresh"]["path"] == "/api/auth/"
    assert response.cookies["rz_session"]["path"] == "/"


def test_every_session_of_the_account_is_dead_afterwards(api_client):
    user = VerifiedUserFactory()
    here, token = sign_in(user)
    elsewhere, _ = sign_in(user)
    assert refresh(here).status_code == 200 and refresh(elsewhere).status_code == 200
    sessions_before = Session.objects.count()

    assert delete(api_client, token, with_password()).status_code == 204

    # This device's session row is deleted; the other's is left for `clearsessions`, but its
    # refresh fails because the user row is gone.
    assert Session.objects.count() == sessions_before - 1
    assert refresh(here).status_code == 400
    assert refresh(elsewhere).status_code == 400
    assert api_client.get(URL, HTTP_AUTHORIZATION=f"Bearer {token}").status_code == 401


def test_the_old_credentials_no_longer_log_in(api_client):

    user = VerifiedUserFactory()
    email = user.email
    assert delete_as(api_client, user, with_password()).status_code == 204
    assert login(Client(headers=SITE_HEADERS), email, DEFAULT_PASSWORD).status_code == 400


# ---------- the confirmation ----------


def test_a_wrong_password_is_a_400_and_deletes_nothing(api_client):
    user = VerifiedUserFactory()
    response = delete_as(api_client, user, {"password": "wrong-password-here"})
    assert response.status_code == 400
    assert list(response.json()) == ["password"]
    assert User.objects.filter(pk=user.pk).exists()


@pytest.mark.parametrize("body", [None, {}, {"password": ""}, {"password": 5}, {"username": "x"}])
def test_a_missing_or_malformed_password_is_a_400(api_client, body):
    user = VerifiedUserFactory()
    response = delete_as(api_client, user, body)
    assert response.status_code == 400
    assert User.objects.filter(pk=user.pk).exists()


def test_a_list_body_is_a_400_not_a_crash(api_client):
    user = VerifiedUserFactory()
    assert delete_as(api_client, user, ["password"]).status_code == 400


def test_a_google_only_account_confirms_with_its_username(api_client):
    user = VerifiedUserFactory(password=None, username="ada_g")
    assert delete_as(api_client, user, {"password": "anything"}).status_code == 400
    assert delete_as(api_client, user, {"username": "someone_else"}).status_code == 400
    assert delete_as(api_client, user, None).status_code == 400
    assert User.objects.filter(pk=user.pk).exists()
    assert delete_as(api_client, user, {"username": "  ADA_G "}).status_code == 204
    assert not User.objects.filter(pk=user.pk).exists()


# ---------- staff ----------


@pytest.mark.parametrize(
    "make",
    [
        lambda: moderator_user(),
        lambda: senior_user(),
        lambda: VerifiedUserFactory(is_superuser=True),
    ],
    ids=["moderator", "senior", "superuser"],
)
def test_staff_get_403_staff_account(api_client, make):
    user = make()
    response = delete_as(api_client, user, with_password())
    assert response.status_code == 403
    assert response.json()["code"] == "staff_account"
    assert "admin" in response.json()["detail"].lower()
    assert User.objects.filter(pk=user.pk).exists()


def test_a_former_moderator_who_wrote_admin_log_entries_is_refused_too(api_client):
    former = VerifiedUserFactory(role=Role.USER)
    LogEntry.objects.log_actions(former.pk, [UserFactory()], CHANGE, change_message="did a thing")
    response = delete_as(api_client, former, with_password())
    assert response.status_code == 403 and response.json()["code"] == "staff_account"
    assert User.objects.filter(pk=former.pk).exists()


def test_the_staff_answer_comes_before_the_password_is_hashed(api_client):
    user = moderator_user()
    response = delete_as(api_client, user, {"password": "wrong"})
    assert response.status_code == 403


# ---------- the rest of the contract ----------


def test_anonymous_is_401(api_client):
    assert api_client.delete(URL, with_password(), format="json").status_code == 401


def test_an_unverified_account_may_delete_itself(api_client):
    user = UserFactory()
    assert delete_as(api_client, user, with_password()).status_code == 204


def test_ten_attempts_an_hour_then_429(api_client):
    user = VerifiedUserFactory()
    token = access_token_for(user)
    codes = [delete(api_client, token, {"password": "wrong"}).status_code for _ in range(11)]
    assert codes[:10] == [400] * 10
    assert codes[10] == 429
    assert User.objects.filter(pk=user.pk).exists()


def test_the_routine_is_idempotent():
    user = VerifiedUserFactory()
    PostFactory(author=user)
    assert deletion.delete_account(user) is True
    assert deletion.delete_account(user) is False
    assert not User.objects.filter(pk=user.pk).exists()


def test_a_second_request_with_the_same_token_after_the_delete_is_a_401(api_client):
    user = VerifiedUserFactory()
    token = access_token_for(user)
    assert delete(api_client, token, with_password()).status_code == 204
    assert delete(api_client, token, with_password()).status_code == 401


def test_a_get_does_not_use_the_delete_allowance(api_client):
    user = VerifiedUserFactory()
    token = access_token_for(user)
    for _ in range(12):
        assert api_client.get(URL, HTTP_AUTHORIZATION=f"Bearer {token}").status_code == 200
    assert delete(api_client, token, with_password()).status_code == 204
