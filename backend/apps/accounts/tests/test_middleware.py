"""AuthApiMiddleware: allow-list, CSRF guard, header stripping, Turnstile pre-check, bodies."""

import json

import pytest
from django.test import Client

from apps.accounts.models import User
from apps.accounts.tests.conftest import (
    DUMMY_TURNSTILE_TOKEN,
    LOGIN_URL,
    LOGOUT_URL,
    REFRESH_URL,
    SIGNUP_URL,
    SITE_HEADERS,
    access_token_for,
    assert_no_secrets,
    login,
    post_json,
    refresh_cookie,
    signup,
)
from apps.accounts.tests.factories import UserFactory
from apps.accounts.turnstile import TurnstileResult

pytestmark = pytest.mark.django_db

UNSAFE_ENDPOINTS = [LOGIN_URL, SIGNUP_URL, REFRESH_URL, LOGOUT_URL]


def body(response):
    return json.loads(response.content)


def first_error(response):
    return body(response)["errors"][0]


# ---------- allow-list ----------


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/auth/app/v1/account/email"),
        ("post", "/api/auth/app/v1/account/email"),
        ("get", "/api/auth/app/v1/auth/session"),
        ("delete", "/api/auth/app/v1/auth/session"),
        ("get", "/api/auth/app/v1/config"),
        ("post", "/api/auth/app/v1/auth/password/request"),
        ("post", "/api/auth/app/v1/auth/email/verify"),
        ("post", "/api/auth/app/v1/account/password/change"),
        ("get", LOGIN_URL),
        ("get", REFRESH_URL),
        ("post", LOGIN_URL + "/"),
        ("get", "/api/auth/"),
    ],
)
def test_only_the_allow_listed_endpoints_answer(site_client, method, path):
    response = getattr(site_client, method)(path)
    assert response.status_code == 404
    assert first_error(response)["code"] == "not_found"
    assert "no-store" in response["Cache-Control"]


def test_other_api_paths_are_untouched(client):
    response = client.get("/api/health/")
    assert response.status_code == 200
    assert response.cookies == {} or "rz_refresh" not in response.cookies


# ---------- CSRF guard ----------


@pytest.mark.parametrize("path", UNSAFE_ENDPOINTS)
@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"X-Requested-With": "rumor-zero"},
        {"Origin": "http://localhost:3000"},
        {"Origin": "https://evil.example", "X-Requested-With": "rumor-zero"},
        {"Origin": "null", "X-Requested-With": "rumor-zero"},
        {"Origin": "http://localhost:3001", "X-Requested-With": "rumor-zero"},
        {"Origin": "https://localhost:3000", "X-Requested-With": "rumor-zero"},
        {"Origin": "http://localhost:3000/", "X-Requested-With": "rumor-zero"},
        {"Origin": "http://localhost:3000", "X-Requested-With": "XMLHttpRequest"},
        {"Origin": "http://localhost:3000", "X-Requested-With": "Rumor-Zero"},
    ],
)
def test_unsafe_requests_need_the_frontend_origin_and_the_custom_header(path, headers, turnstile):
    client = Client(headers=headers)
    user = UserFactory()
    response = post_json(
        client,
        path,
        {"email": user.email, "password": "x", "turnstile_token": DUMMY_TURNSTILE_TOKEN},
    )
    assert response.status_code == 403
    assert first_error(response)["code"] == "csrf_failed"
    assert turnstile.calls == []


def test_a_cross_site_text_plain_form_cannot_log_in():
    """allauth parses any body as JSON, so a `<form enctype="text/plain">` could post JSON."""
    user = UserFactory()
    client = Client(headers={"Origin": "https://evil.example"})
    payload = json.dumps({"email": user.email, "password": "correct-horse-battery-staple"})
    response = client.post(LOGIN_URL, data=payload, content_type="text/plain")
    assert response.status_code == 403
    assert "rz_refresh" not in response.cookies


@pytest.mark.parametrize("path", [REFRESH_URL, LOGOUT_URL])
def test_two_refresh_cookies_are_refused(site_client, path):
    response = post_json(site_client, path, HTTP_COOKIE="rz_refresh=a; rz_refresh=b")
    assert response.status_code == 400
    assert first_error(response)["code"] == "invalid_cookie"
    assert response.cookies["rz_refresh"]["max-age"] == 0


# ---------- incoming credentials are ignored where tokens are issued ----------


def test_login_ignores_a_bearer_token_and_a_session_token(site_client):
    current = UserFactory()
    other = UserFactory()
    response = login(
        site_client,
        other.email,
        HTTP_AUTHORIZATION=f"Bearer {access_token_for(current)}",
        HTTP_X_SESSION_TOKEN="no-such-session",
    )
    # Not 409 (already authenticated) and not 410 (unknown session token).
    assert response.status_code == 200
    assert body(response)["data"]["user"]["email"] == other.email


def test_refresh_ignores_a_session_token_header(site_client):
    user = UserFactory()
    login(site_client, user.email)
    response = post_json(site_client, REFRESH_URL, HTTP_X_SESSION_TOKEN="no-such-session")
    assert response.status_code == 200


# ---------- bodies ----------


def test_an_unparsable_body_becomes_a_json_400(site_client):
    response = site_client.post(LOGIN_URL, data="{not json", content_type="application/json")
    assert response.status_code == 400
    assert response["Content-Type"] == "application/json"
    assert body(response) == {"status": 400}


def test_a_server_error_page_becomes_a_bare_json_500(monkeypatch):
    def explode(*args, **kwargs):
        raise RuntimeError("boom with secrets")

    monkeypatch.setattr("allauth.headless.account.views.LoginView.post", explode)
    user = UserFactory()
    client = Client(headers=SITE_HEADERS, raise_request_exception=False)
    response = login(client, user.email)
    assert response.status_code == 500
    assert response["Content-Type"] == "application/json"
    assert body(response) == {"status": 500}


def test_a_failed_refresh_with_a_5xx_keeps_the_cookies(site_client, monkeypatch):
    user = UserFactory()
    login(site_client, user.email)

    def explode(*args, **kwargs):
        raise RuntimeError("database went away")

    monkeypatch.setattr("apps.accounts.tokens.RumorZeroJWTTokenStrategy.refresh_token", explode)
    client = Client(headers=SITE_HEADERS, raise_request_exception=False)
    client.cookies = site_client.cookies
    response = post_json(client, REFRESH_URL)
    assert response.status_code == 500
    assert "rz_refresh" not in response.cookies


# ---------- Turnstile pre-check on sign-up ----------


def test_signup_sends_the_widget_token_and_the_client_ip_to_turnstile(turnstile, settings):
    settings.PROXY_SHARED_SECRET = "test-relay-secret"
    client = Client(
        headers={
            **SITE_HEADERS,
            "X-RZ-Proxy-Secret": "test-relay-secret",
            "X-RZ-Client-IP": "203.0.113.7",
        }
    )
    assert signup(client).status_code == 200
    assert turnstile.calls == [(DUMMY_TURNSTILE_TOKEN, "203.0.113.7")]


@pytest.mark.parametrize("token", [None, "", "   ", 42, ["XXXX"], {"t": 1}, "x" * 2049], ids=repr)
def test_a_missing_or_malformed_token_fails_without_calling_cloudflare(
    site_client, turnstile, token
):
    data = {"email": "ada@example.test", "username": "ada", "password": "correct-horse-1"}
    if token is not None:
        data["turnstile_token"] = token
    response = post_json(site_client, SIGNUP_URL, data)

    assert response.status_code == 400
    error = first_error(response)
    assert (error["code"], error["param"]) == ("turnstile_failed", "turnstile_token")
    assert turnstile.calls == []
    assert not User.objects.exists()


def test_a_2048_character_token_is_sent_to_cloudflare(site_client, turnstile):
    data = {
        "email": "ada@example.test",
        "username": "ada",
        "password": "correct-horse-battery-42",
        "turnstile_token": "x" * 2048,
    }
    assert post_json(site_client, SIGNUP_URL, data).status_code == 200
    assert len(turnstile.calls) == 1


@pytest.mark.parametrize(
    ("result", "code"),
    [
        (TurnstileResult.FAILED, "turnstile_failed"),
        (TurnstileResult.UNAVAILABLE, "turnstile_unavailable"),
    ],
)
def test_a_failed_or_unavailable_check_refuses_signup(site_client, turnstile, result, code):
    turnstile.result = result
    response = signup(site_client)

    assert response.status_code == 400
    error = first_error(response)
    assert (error["code"], error["param"]) == (code, "turnstile_token")
    assert not User.objects.exists()
    assert_no_secrets(response)


def test_unavailable_tells_the_user_to_try_again_in_a_minute(site_client, turnstile):
    turnstile.result = TurnstileResult.UNAVAILABLE
    message = first_error(signup(site_client))["message"]
    assert message == "We couldn't run the bot check. Try again in a minute."


def test_a_bad_token_hides_whether_the_email_is_taken(site_client, turnstile):
    UserFactory(email="taken@example.test")
    turnstile.result = TurnstileResult.FAILED
    response = signup(site_client, email="taken@example.test")

    errors = body(response)["errors"]
    assert [(e["code"], e.get("param")) for e in errors] == [
        ("turnstile_failed", "turnstile_token")
    ]


def test_the_refresh_cookie_from_signup_works(site_client, turnstile):
    signup(site_client)
    assert refresh_cookie(site_client)
    assert post_json(site_client, REFRESH_URL).status_code == 200
