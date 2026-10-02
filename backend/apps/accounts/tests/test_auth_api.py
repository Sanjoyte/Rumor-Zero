"""Sign-up, log-in, refresh and log-out through the real allauth views (ARCHITECTURE §7)."""

import json
import logging
import time
from smtplib import SMTPException

import pytest
from allauth.account.models import EmailAddress
from django.contrib.sessions.models import Session
from django.core import mail
from django.utils import timezone

import rumor_zero.settings as project_settings
from apps.accounts.models import User
from apps.accounts.tests.conftest import (
    LOGOUT_URL,
    STRONG_PASSWORD,
    access_token_for,
    assert_no_secrets,
    login,
    post_json,
    refresh,
    refresh_cookie,
    signup,
    use_refresh_cookie,
)
from apps.accounts.tests.factories import UserFactory
from apps.accounts.tokens import ROTATION_GRACE_SECONDS

pytestmark = pytest.mark.django_db


def body(response):
    return json.loads(response.content)


def error_params(response):
    return {(error.get("param"), error["code"]) for error in body(response)["errors"]}


def assert_auth_cookies_set(response):
    refresh_morsel = response.cookies["rz_refresh"]
    hint = response.cookies["rz_session"]
    assert refresh_morsel.value and refresh_morsel["httponly"] is True
    assert refresh_morsel["path"] == "/api/auth/" and refresh_morsel["samesite"] == "Lax"
    assert hint.value == "1" and hint["path"] == "/"
    return refresh_morsel.value


def assert_auth_cookies_deleted(response):
    for name in ("rz_refresh", "rz_session"):
        assert response.cookies[name].value == ""
        assert response.cookies[name]["max-age"] == 0


def assert_no_session_cookie(response):
    assert "sessionid" not in response.cookies
    assert "csrftoken" not in response.cookies


# ---------- sign-up ----------


def test_signup_logs_in_sets_both_cookies_and_returns_no_secret(site_client, turnstile):
    response = signup(site_client, email="Ada@Example.test", username="Ada")

    assert response.status_code == 200
    data = body(response)
    assert data["meta"]["is_authenticated"] is True
    assert data["meta"]["access_token"]
    assert data["data"]["user"]["username"] == "ada"
    refresh_token = assert_auth_cookies_set(response)
    assert_no_secrets(response, refresh_token)
    assert_no_session_cookie(response)
    assert "no-store" in response["Cache-Control"]

    user = User.objects.get(username="ada")
    assert user.email == "ada@example.test"
    assert user.is_email_verified is False
    assert EmailAddress.objects.get(user=user).verified is False
    # The session key never leaves the server.
    session_key = Session.objects.get().session_key
    assert session_key not in response.content.decode()


def test_signup_sends_the_verification_email_with_a_frontend_link(site_client, turnstile):
    assert signup(site_client).status_code == 200

    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.to == ["ada@example.test"]
    assert message.subject.startswith("[Rumor Zero] ")
    # The only link goes to the frontend. (allauth's default wording names the backend host;
    # Part 2 replaces the templates.)
    links = [word for word in message.body.split() if "://" in word]
    assert len(links) == 1
    assert links[0].startswith("http://localhost:3000/verify-email/")


def test_signup_succeeds_when_the_email_cannot_be_sent(site_client, turnstile, monkeypatch, caplog):
    def broken_send(self, messages):
        raise SMTPException("relay refused ada@example.test")

    monkeypatch.setattr("django.core.mail.backends.locmem.EmailBackend.send_messages", broken_send)
    with caplog.at_level(logging.ERROR, logger="apps.accounts.adapter"):
        response = signup(site_client)

    assert response.status_code == 200
    assert User.objects.filter(username="ada").exists()
    assert "Could not send the email_confirmation_signup email (SMTPException)" in caplog.text
    assert "ada@example.test" not in caplog.text


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"email": "taken@example.test"}, ("email", "email_taken")),
        ({"username": "taken_name"}, ("username", "username_taken")),
        ({"username": "ＴＡＫＥＮ_ｎａｍｅ"}, ("username", "username_taken")),
        ({"username": "ab"}, ("username", "invalid_username")),
        ({"username": "ada-lovelace"}, ("username", "invalid_username")),
        ({"username": "Admin"}, ("username", "reserved_username")),
        ({"password": "short1"}, ("password", "password_too_short")),
        ({"password": "password123"}, ("password", "password_too_common")),
        ({"password": "83920174"}, ("password", "password_entirely_numeric")),
    ],
)
def test_signup_field_errors_use_the_real_param_names(site_client, turnstile, overrides, expected):
    UserFactory(email="taken@example.test", username="taken_name")
    response = signup(site_client, **overrides)

    assert response.status_code == 400
    assert expected in error_params(response)
    assert_no_secrets(response)
    assert "rz_refresh" not in response.cookies


def test_a_bearer_token_on_signup_is_ignored_so_there_is_no_409(site_client, turnstile):
    other = UserFactory()
    response = signup(
        site_client,
        HTTP_AUTHORIZATION=f"Bearer {access_token_for(other)}",
        HTTP_X_SESSION_TOKEN="made-up-session-key",
    )
    assert response.status_code == 200
    assert body(response)["data"]["user"]["username"] == "ada"


def test_stored_passwords_are_argon2id(site_client, turnstile, settings):
    settings.PASSWORD_HASHERS = project_settings.PASSWORD_HASHERS
    assert signup(site_client).status_code == 200
    assert User.objects.get(username="ada").password.startswith("argon2$argon2id$")


# ---------- log in ----------


def test_login_sets_both_cookies_and_returns_only_the_access_token(site_client):
    user = UserFactory(email="bo@example.test")
    response = login(site_client, "BO@example.test")

    assert response.status_code == 200
    data = body(response)
    assert set(data["meta"]) == {"is_authenticated", "access_token"}
    assert data["data"]["user"]["email"] == user.email
    refresh_token = assert_auth_cookies_set(response)
    assert_no_secrets(response, refresh_token)
    assert_no_session_cookie(response)


def test_a_wrong_password_is_a_password_error_without_cookies(site_client):
    user = UserFactory()
    response = login(site_client, user.email, "wrong-password")

    assert response.status_code == 400
    assert error_params(response) == {("password", "email_password_mismatch")}
    assert "rz_refresh" not in response.cookies
    assert_no_secrets(response)


def test_the_access_token_authenticates_the_api(site_client):
    user = UserFactory()
    access = body(login(site_client, user.email))["meta"]["access_token"]
    response = site_client.get("/api/v1/me/", HTTP_AUTHORIZATION=f"Bearer {access}")
    assert response.status_code == 200
    assert body(response)["id"] == str(user.pk)


def test_login_again_revokes_the_session_behind_the_old_cookie(site_client):
    user = UserFactory()
    login(site_client, user.email)
    first = refresh_cookie(site_client)
    login(site_client, user.email)
    second = refresh_cookie(site_client)

    assert first != second
    assert Session.objects.count() == 1
    use_refresh_cookie(site_client, first)
    assert refresh(site_client).status_code == 400
    use_refresh_cookie(site_client, second)
    assert refresh(site_client).status_code == 200


# ---------- refresh ----------


def test_refresh_rotates_the_cookie_and_returns_a_new_access_token(site_client):
    user = UserFactory()
    first_access = body(login(site_client, user.email))["meta"]["access_token"]
    first = refresh_cookie(site_client)

    response = refresh(site_client)
    assert response.status_code == 200
    data = body(response)
    assert set(data["data"]) == {"access_token"}
    assert data["data"]["access_token"] != first_access
    second = assert_auth_cookies_set(response)
    assert second != first
    assert_no_secrets(response, first, second)
    assert_no_session_cookie(response)
    assert "no-store" in response["Cache-Control"]


def test_a_rotated_token_works_during_the_grace_period_only(site_client, monkeypatch):
    user = UserFactory()
    login(site_client, user.email)
    old = refresh_cookie(site_client)
    assert refresh(site_client).status_code == 200

    # A retry after a lost response: the old cookie still works for a minute.
    use_refresh_cookie(site_client, old)
    assert refresh(site_client).status_code == 200

    real_time = time.time
    monkeypatch.setattr(time, "time", lambda: real_time() + ROTATION_GRACE_SECONDS + 1)
    use_refresh_cookie(site_client, old)
    response = refresh(site_client)
    assert response.status_code == 400
    assert_auth_cookies_deleted(response)


def test_refresh_without_a_cookie_is_401_and_clears_the_hint(site_client):
    response = refresh(site_client)
    assert response.status_code == 401
    assert_auth_cookies_deleted(response)
    assert_no_secrets(response)


def test_refresh_ignores_a_token_sent_in_the_body(site_client):
    user = UserFactory()
    login(site_client, user.email)
    token = refresh_cookie(site_client)
    site_client.cookies.clear()

    response = post_json(site_client, "/api/auth/app/v1/tokens/refresh", {"refresh_token": token})
    assert response.status_code == 401


def test_a_garbage_cookie_is_400_and_deletes_both_cookies(site_client):
    use_refresh_cookie(site_client, "not-a-token")
    response = refresh(site_client)
    assert response.status_code == 400
    assert_auth_cookies_deleted(response)


def test_refresh_fails_once_the_password_changes(site_client):
    user = UserFactory()
    login(site_client, user.email)
    user.set_password(STRONG_PASSWORD)
    user.save()
    assert refresh(site_client).status_code == 400


def test_refresh_fails_for_an_inactive_user(site_client):
    user = UserFactory()
    login(site_client, user.email)
    User.objects.filter(pk=user.pk).update(is_active=False)
    assert refresh(site_client).status_code == 400


def test_the_token_session_slides_with_each_refresh(site_client, settings):
    user = UserFactory()
    login(site_client, user.email)
    session = Session.objects.get()
    Session.objects.filter(pk=session.pk).update(expire_date=session.expire_date.replace(year=2000))
    # An expired session is gone for good...
    assert refresh(site_client).status_code == 400

    login(site_client, user.email)
    live = Session.objects.filter(expire_date__gt=timezone.now())
    before = live.get().expire_date
    time.sleep(1.1)
    assert refresh(site_client).status_code == 200
    # ...and a live one is pushed forward by REFRESH_TOKEN_SECONDS on every refresh.
    after = live.get().expire_date
    assert after > before
    assert abs((after - timezone.now()).total_seconds() - settings.REFRESH_TOKEN_SECONDS) < 5


# ---------- log out ----------


def test_logout_deletes_the_session_and_both_cookies(site_client):
    user = UserFactory()
    login(site_client, user.email)
    token = refresh_cookie(site_client)

    response = post_json(site_client, LOGOUT_URL)
    assert response.status_code == 204
    assert response.content == b""
    assert_auth_cookies_deleted(response)
    assert Session.objects.count() == 0
    assert "no-store" in response["Cache-Control"]

    use_refresh_cookie(site_client, token)
    assert refresh(site_client).status_code == 400


def test_logout_is_idempotent(site_client):
    assert post_json(site_client, LOGOUT_URL).status_code == 204
    use_refresh_cookie(site_client, "not-a-token")
    assert post_json(site_client, LOGOUT_URL).status_code == 204


def test_logout_only_accepts_post(site_client):
    response = site_client.get(LOGOUT_URL)
    assert response.status_code == 405
    assert body(response) == {"status": 405}
