"""DELETE /api/v1/me/avatar/ (ARCHITECTURE §4e): take the photo down, back to initials."""

import threading

import pytest
from django.db import connection

from apps.accounts import avatars
from apps.accounts.models import Avatar, User
from apps.accounts.tests import photo_fixtures as fx
from apps.accounts.tests.conftest import access_token_for, run_together
from apps.accounts.tests.factories import UserFactory

pytestmark = pytest.mark.django_db

URL = "/api/v1/me/avatar/"


def delete(client, user):
    return client.delete(URL, HTTP_AUTHORIZATION=f"Bearer {access_token_for(user)}")


def with_photo(**kwargs):
    user = UserFactory(is_email_verified=True, **kwargs)
    fx.give_photo(user)
    return user


def test_it_removes_the_photo_at_once_and_answers_204(api_client):
    user = with_photo()
    response = delete(api_client, user)

    assert response.status_code == 204 and response.content == b""
    assert not Avatar.objects.filter(user=user).exists()
    user.refresh_from_db()
    assert user.avatar_version is None


def test_me_shows_initials_afterwards(api_client):
    user = with_photo()
    delete(api_client, user)
    me = api_client.get("/api/v1/me/", HTTP_AUTHORIZATION=f"Bearer {access_token_for(user)}")
    assert me.json()["avatar_url"] is None


def test_it_is_safe_to_repeat_and_works_with_no_photo_at_all(api_client):
    user = with_photo()
    assert [delete(api_client, user).status_code for _ in range(3)] == [204, 204, 204]
    assert delete(api_client, UserFactory()).status_code == 204


def test_anonymous_gets_401(api_client):
    assert api_client.delete(URL).status_code == 401


def test_an_unverified_or_blocked_account_can_still_take_its_photo_down(api_client):
    """Only putting a photo up needs a verified email and uploads that aren't blocked."""
    unverified = UserFactory()
    Avatar.objects.create(
        user=unverified,
        image_256=b"x",
        image_96=b"x",
        version="0123456789abcdef",
        bytes_total=2,
    )
    User.objects.filter(pk=unverified.pk).update(avatar_version="0123456789abcdef")
    assert delete(api_client, unverified).status_code == 204
    assert not Avatar.objects.exists()

    blocked = with_photo()
    User.objects.filter(pk=blocked.pk).update(avatar_uploads_blocked=True)
    assert delete(api_client, blocked).status_code == 204
    assert not Avatar.objects.exists()


def test_it_has_no_throttle(api_client):
    user = with_photo()
    assert all(delete(api_client, user).status_code == 204 for _ in range(12))


def test_it_never_touches_another_users_photo(api_client):
    ada, bo = with_photo(), with_photo()
    before = Avatar.objects.get(user=bo).version
    delete(api_client, ada)

    assert Avatar.objects.get(user=bo).version == before
    bo.refresh_from_db()
    assert bo.avatar_version == before


def test_the_photo_can_be_put_up_again_after_it_was_taken_down(api_client):
    user = with_photo()
    delete(api_client, user)
    response = api_client.put(
        URL,
        {"file": fx.upload(fx.jpeg(colour=fx.BLUE))},
        format="multipart",
        HTTP_AUTHORIZATION=f"Bearer {access_token_for(user)}",
    )
    assert response.status_code == 200 and response.json()["avatar_url"]


def test_delete_photo_reports_whether_there_was_one():
    user = UserFactory(is_email_verified=True)
    assert avatars.delete_photo(user.pk) is False
    fx.give_photo(user)
    assert avatars.delete_photo(user.pk) is True
    assert avatars.delete_photo(user.pk) is False
    assert avatars.delete_photo(UserFactory().pk) is False


@pytest.mark.django_db(transaction=True)
def test_a_delete_and_an_upload_at_the_same_moment_leave_the_two_rows_agreeing(api_client):
    """Whichever wins, `users.avatar_version` and the Avatar row describe the same photo."""
    for _ in range(5):
        user = with_photo()
        client = api_client.__class__()

        def upload(user=user, client=client):
            return client.put(
                URL,
                {"file": fx.upload(fx.jpeg(colour=fx.GREEN))},
                format="multipart",
                HTTP_AUTHORIZATION=f"Bearer {access_token_for(user)}",
            ).status_code

        def remove(user=user):
            return delete(api_client.__class__(), user).status_code

        statuses = run_together(upload, remove)
        assert statuses[1] == 204
        user.refresh_from_db()
        row = Avatar.objects.filter(user=user).first()
        assert (row.version if row else None) == user.avatar_version


@pytest.mark.django_db(transaction=True)
def test_deleting_the_account_while_a_photo_is_uploading_does_not_deadlock():
    from apps.accounts import deletion

    user = UserFactory(is_email_verified=True)
    blob = fx.jpeg()

    def save():
        try:
            return avatars.save_photo(user.pk, blob)
        except Exception as error:  # the account may be gone by then
            return type(error).__name__

    def remove():
        return deletion.delete_account(User.objects.get(pk=user.pk))

    results = run_together(save, remove)
    assert results[1] is True
    assert not User.objects.filter(pk=user.pk).exists()
    assert not Avatar.objects.exists()
    connection.close()
    assert threading.active_count() >= 1
