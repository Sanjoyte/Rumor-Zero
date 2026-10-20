"""POST /api/v1/me/password/ (ARCHITECTURE §7, §9; Part 14)."""

import pytest
from django.contrib.sessions.models import Session
from django.core import mail
from django.test import Client

from apps.accounts.tests.conftest import (
    SITE_HEADERS,
    STRONG_PASSWORD,
    access_token_for,
    login,
    refresh,
    run_together,
    sign_in,
)
from apps.accounts.tests.factories import DEFAULT_PASSWORD, UserFactory

pytestmark = pytest.mark.django_db

URL = "/api/v1/me/password/"


def change(api_client, token, current=DEFAULT_PASSWORD, new=STRONG_PASSWORD, **extra):
    body = {"current_password": current, "new_password": new, **extra}
    return api_client.post(URL, body, format="json", HTTP_AUTHORIZATION=f"Bearer {token}")


def test_it_changes_the_password(api_client, django_capture_on_commit_callbacks):
    user = UserFactory()
    _, token = sign_in(user)

    with django_capture_on_commit_callbacks(execute=True):
        response = change(api_client, token)

    assert response.status_code == 204 and response.content == b""
    user.refresh_from_db()
    assert user.check_password(STRONG_PASSWORD)
    assert not user.check_password(DEFAULT_PASSWORD)
    assert login(Client(headers=SITE_HEADERS), user.email, DEFAULT_PASSWORD).status_code == 400
    assert login(Client(headers=SITE_HEADERS), user.email, STRONG_PASSWORD).status_code == 200


def test_this_device_stays_signed_in_and_every_other_one_ends(api_client):
    user = UserFactory()
    here, here_token = sign_in(user)
    elsewhere, _ = sign_in(user)
    assert refresh(here).status_code == 200  # both work before the change
    here_sessions = Session.objects.count()

    assert change(api_client, here_token).status_code == 204

    assert Session.objects.count() == here_sessions  # nothing was deleted: the other just fails
    assert refresh(here).status_code == 200
    assert refresh(here).status_code == 200  # and keeps working
    assert refresh(elsewhere).status_code == 400
    me = api_client.get("/api/v1/me/", HTTP_AUTHORIZATION=f"Bearer {here_token}")
    assert me.status_code == 200


def test_the_email_goes_out_after_the_commit_with_a_reset_link(
    api_client, django_capture_on_commit_callbacks, settings
):
    user = UserFactory(email="ada@example.test")
    _, token = sign_in(user)
    mail.outbox.clear()

    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        change(api_client, token)
    assert mail.outbox == []  # nothing before the commit
    for callback in callbacks:
        callback()

    (message,) = mail.outbox
    assert message.to == ["ada@example.test"]
    assert message.subject == "[Rumor Zero] Your password was changed"
    assert "was just changed" in message.body
    assert f"{settings.FRONTEND_ORIGIN}/forgot-password" in message.body
    assert STRONG_PASSWORD not in message.body and DEFAULT_PASSWORD not in message.body
    assert message.alternatives


def test_a_wrong_current_password_is_a_400_and_changes_nothing(
    api_client, django_capture_on_commit_callbacks
):
    user = UserFactory()
    _, token = sign_in(user)
    mail.outbox.clear()
    with django_capture_on_commit_callbacks(execute=True):
        response = change(api_client, token, current="not-the-password")
    assert response.status_code == 400
    assert list(response.json()) == ["current_password"]
    user.refresh_from_db()
    assert user.check_password(DEFAULT_PASSWORD)
    assert mail.outbox == []


@pytest.mark.parametrize(
    "new", ["short", "12345678901234", "password1234", "correct-horse-battery-staple"]
)
def test_a_weak_new_password_is_a_400_on_new_password(api_client, new):
    user = UserFactory(username="correcthorse")
    _, token = sign_in(user)
    response = change(api_client, token, new=new)
    assert response.status_code == 400
    assert "new_password" in response.json()
    user.refresh_from_db()
    assert user.check_password(DEFAULT_PASSWORD)


def test_a_password_that_resembles_the_username_is_refused(api_client):
    user = UserFactory(username="ada_lovelace_99", email="someone@example.test")
    _, token = sign_in(user)
    assert change(api_client, token, new="ada_lovelace_99").status_code == 400


def test_missing_and_blank_fields_are_400(api_client):
    user = UserFactory()
    _, token = sign_in(user)
    assert (
        api_client.post(URL, {}, format="json", HTTP_AUTHORIZATION=f"Bearer {token}").status_code
        == 400
    )
    assert change(api_client, token, current="").status_code == 400
    assert change(api_client, token, new="").status_code == 400


def test_passwords_are_not_trimmed(api_client):
    user = UserFactory()
    _, token = sign_in(user)
    assert change(api_client, token, current=f" {DEFAULT_PASSWORD} ").status_code == 400
    assert change(api_client, token, new=f"  {STRONG_PASSWORD}  ").status_code == 204
    user.refresh_from_db()
    assert user.check_password(f"  {STRONG_PASSWORD}  ")


def test_a_google_only_account_gets_409_password_not_set(api_client):
    user = UserFactory(password=None)
    token = access_token_for(user)
    response = change(api_client, token, current="anything")
    assert response.status_code == 409
    assert response.json()["code"] == "password_not_set"
    assert "Forgot password" in response.json()["detail"]
    user.refresh_from_db()
    assert not user.has_usable_password()


def test_a_session_that_is_already_gone_does_not_stop_the_change(api_client):
    user = UserFactory()
    browser, token = sign_in(user)
    Session.objects.all().delete()  # the access token still validates for its 15 minutes
    assert change(api_client, token).status_code == 204
    user.refresh_from_db()
    assert user.check_password(STRONG_PASSWORD)
    assert refresh(browser).status_code == 400


def test_a_token_without_a_real_session_still_changes_the_password(api_client):
    user = UserFactory()
    assert change(api_client, access_token_for(user)).status_code == 204


def test_anonymous_is_401(api_client):
    response = api_client.post(URL, {"current_password": "x", "new_password": "y"}, format="json")
    assert response.status_code == 401


def test_ten_attempts_an_hour_then_429(api_client):
    user = UserFactory()
    token = access_token_for(user)
    codes = [change(api_client, token, current="wrong").status_code for _ in range(11)]
    assert codes[:10] == [400] * 10
    assert codes[10] == 429


def test_an_unusable_password_is_not_throttled_before_the_login_check(api_client):
    user = UserFactory(password=None)
    response = api_client.post(
        URL, {}, format="json", HTTP_AUTHORIZATION=f"Bearer {access_token_for(user)}"
    )
    assert response.status_code == 409


@pytest.mark.django_db(transaction=True)
def test_a_refresh_at_the_same_moment_cannot_write_the_old_hash_back(api_client):
    """The change takes the session row's lock, as a refresh does, so the two run one after the
    other and this device's next refresh still works."""
    user = UserFactory()
    here, token = sign_in(user)

    def a_refresh():
        return refresh(here).status_code

    def the_change():
        from rest_framework.test import APIClient

        return change(APIClient(), token).status_code

    results = run_together(a_refresh, the_change)

    assert results[1] == 204
    assert results[0] in (200, 400)
    assert refresh(here).status_code == 200
