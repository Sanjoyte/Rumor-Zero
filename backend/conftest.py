import threading

import pytest
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.core.cache import cache
from rest_framework.test import APIClient

# pytest-django loads the settings module before this file, so tests change settings through the
# `settings` fixture or `monkeypatch`, never by injecting environment variables here.

TEST_FRONTEND_ORIGIN = "http://localhost:3000"
TEST_JWT_SIGNING_KEY = "test-only-jwt-signing-key-0123456789abcdef"
# Cloudflare's official "always passes" test secret (the backend/.env.example value).
TEST_TURNSTILE_SECRET = "1x0000000000000000000000000000000AA"
# A made-up Google client ID: tests never use the developer's real one.
TEST_GOOGLE_CLIENT_ID = "rz-test-client.apps.googleusercontent.com"


def _no_network(*args, **kwargs):
    raise AssertionError("Tests must not call Cloudflare: mock verify_turnstile or urlopen")


def _no_google_network(self, *args, **kwargs):
    raise AssertionError("Tests must not call Google: use the `google` fixture")


def _no_pipeline_network():
    raise AssertionError("Tests must not call a real pipeline: give HttpPipelineClient an opener")


@pytest.fixture(autouse=True)
def _hermetic(settings, monkeypatch):
    """Keep tests independent of the developer's .env: no real Redis, static build or hashing,
    fixed auth values, and no network."""
    settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    settings.STORAGES = {
        **settings.STORAGES,
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
    # Production-only security settings must not turn every test request into a redirect.
    settings.SECURE_SSL_REDIRECT = False
    settings.SESSION_COOKIE_SECURE = False
    settings.CSRF_COOKIE_SECURE = False

    settings.FRONTEND_ORIGIN = TEST_FRONTEND_ORIGIN
    settings.HEADLESS_FRONTEND_URLS = {
        "account_confirm_email": f"{TEST_FRONTEND_ORIGIN}/verify-email/{{key}}",
        "account_reset_password_from_key": f"{TEST_FRONTEND_ORIGIN}/reset-password/{{key}}",
        "account_reset_password": f"{TEST_FRONTEND_ORIGIN}/forgot-password",
        "account_signup": f"{TEST_FRONTEND_ORIGIN}/signup",
    }
    settings.AUTH_COOKIE_SECURE = False
    settings.JWT_SIGNING_KEY = TEST_JWT_SIGNING_KEY
    settings.HEADLESS_JWT_PRIVATE_KEY = TEST_JWT_SIGNING_KEY
    settings.HEADLESS_JWT_ACCESS_TOKEN_EXPIRES_IN = 15 * 60
    settings.REFRESH_TOKEN_SECONDS = 14 * 86400
    settings.HEADLESS_JWT_REFRESH_TOKEN_EXPIRES_IN = 14 * 86400
    settings.TURNSTILE_SECRET_KEY = TEST_TURNSTILE_SECRET
    monkeypatch.setattr("apps.accounts.turnstile.urlopen", _no_network)
    # Google sign-in is on with a test client ID, whatever backend/.env says; the signing
    # certificates come from the `google` fixture, never the network.
    settings.GOOGLE_OAUTH_CLIENT_ID = TEST_GOOGLE_CLIENT_ID
    settings.SOCIALACCOUNT_PROVIDERS = {
        "google": {
            "APPS": [{"client_id": TEST_GOOGLE_CLIENT_ID, "secret": "", "key": ""}],
            "VERIFIED_EMAIL": False,
        }
    }
    monkeypatch.setattr(DefaultSocialAccountAdapter, "get_requests_session", _no_google_network)
    # The fact-check pipeline is the deterministic stub and nothing is checked in a background
    # thread unless a test asks for it (`settings.PIPELINE_INLINE_KICK = True`).
    settings.PIPELINE_BACKEND = "stub"
    settings.PIPELINE_INLINE_KICK = False
    settings.PIPELINE_URL = ""
    settings.PIPELINE_API_KEY = ""
    monkeypatch.setattr("apps.pipeline.clients._default_opener", _no_pipeline_network)
    cache.clear()


@pytest.fixture(autouse=True)
def _no_kick_thread_left_behind():
    """A kick thread that outlives its test would keep a connection to the test database open (and
    could write into the next test). Tests that start one join it; this catches those that don't."""
    yield
    left = [t for t in threading.enumerate() if t.name == "pipeline-kick"]
    for thread in left:
        thread.join(timeout=10)
    assert [t for t in left if t.is_alive()] == [], "a pipeline-kick thread outlived its test"


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user(db):
    from apps.accounts.tests.factories import UserFactory

    return UserFactory()


@pytest.fixture
def role_groups(db):
    """Both moderator groups with exactly their permissions (`apps/moderation/roles.py`). The test
    database gets them from migration 0002, but a `transaction=True` test flushes the database:
    `post_migrate` brings the permission rows back and not the groups' assignments, so a test that
    depends on them calls this. It also works in an ordinary `db` test."""
    from apps.moderation.roles import sync_role_groups

    sync_role_groups()
