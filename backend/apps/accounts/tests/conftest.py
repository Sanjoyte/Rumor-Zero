"""Helpers for the auth API tests: a same-site client, a fake Turnstile and token helpers."""

import json

import pytest
from allauth.headless.tokens.strategies.jwt import internal
from django.contrib.sessions.backends.db import SessionStore
from django.test import Client

from apps.accounts import middleware
from apps.accounts.tests.factories import DEFAULT_PASSWORD
from apps.accounts.turnstile import TurnstileResult

# The root conftest fixes settings.FRONTEND_ORIGIN to this value.
TEST_FRONTEND_ORIGIN = "http://localhost:3000"
LOGIN_URL = middleware.LOGIN_PATH
SIGNUP_URL = middleware.SIGNUP_PATH
REFRESH_URL = middleware.REFRESH_PATH
LOGOUT_URL = middleware.LOGOUT_PATH
SITE_HEADERS = {"Origin": TEST_FRONTEND_ORIGIN, "X-Requested-With": "rumor-zero"}
DUMMY_TURNSTILE_TOKEN = "XXXX.DUMMY.TOKEN.XXXX"
STRONG_PASSWORD = "correct-horse-battery-staple-42"


class FakeTurnstile:
    """Stands in for verify_turnstile: records each call and returns `result`."""

    def __init__(self):
        self.result = TurnstileResult.OK
        self.calls = []

    def __call__(self, token, remote_ip):
        self.calls.append((token, remote_ip))
        return self.result


@pytest.fixture
def turnstile(monkeypatch):
    fake = FakeTurnstile()
    monkeypatch.setattr("apps.accounts.middleware.verify_turnstile", fake)
    return fake


@pytest.fixture
def site_client():
    """A browser on the frontend origin, as the relay forwards it."""
    return Client(headers=SITE_HEADERS)


def post_json(client, url, data=None, **extra):
    return client.post(url, data=json.dumps(data or {}), content_type="application/json", **extra)


def signup(client, *, email="ada@example.test", username="ada", password=STRONG_PASSWORD, **extra):
    data = {
        "email": email,
        "username": username,
        "password": password,
        "turnstile_token": DUMMY_TURNSTILE_TOKEN,
    }
    return post_json(client, SIGNUP_URL, data, **extra)


def login(client, email, password=DEFAULT_PASSWORD, **extra):
    return post_json(client, LOGIN_URL, {"email": email, "password": password}, **extra)


def refresh(client, **extra):
    return post_json(client, REFRESH_URL, **extra)


def refresh_cookie(client):
    morsel = client.cookies.get("rz_refresh")
    return morsel.value if morsel else ""


def use_refresh_cookie(client, token):
    client.cookies["rz_refresh"] = token


def access_token_for(user):
    """A valid access token without going through login (they are validated statelessly)."""
    session = SessionStore()
    session.create()
    return internal.create_access_token(user, session, {})


def walk_strings(value):
    """Every key and string value in a JSON body, however deeply nested."""
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from walk_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from walk_strings(item)
    elif isinstance(value, str):
        yield value


def assert_no_secrets(response, *secrets):
    """No refresh/session token field, and none of `secrets`, anywhere in the body."""
    assert response["Content-Type"].startswith("application/json")
    strings = list(walk_strings(json.loads(response.content)))
    assert "refresh_token" not in strings
    assert "session_token" not in strings
    for secret in secrets:
        if secret:
            assert secret not in response.content.decode()
