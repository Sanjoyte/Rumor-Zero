import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

# pytest-django loads the settings module before this file, so tests change settings through the
# `settings` fixture or `monkeypatch`, never by injecting environment variables here.

TEST_FRONTEND_ORIGIN = "http://localhost:3000"
TEST_JWT_SIGNING_KEY = "test-only-jwt-signing-key-0123456789abcdef"
# Cloudflare's official "always passes" test secret (the backend/.env.example value).
TEST_TURNSTILE_SECRET = "1x0000000000000000000000000000000AA"


def _no_network(*args, **kwargs):
    raise AssertionError("Tests must not call Cloudflare: mock verify_turnstile or urlopen")


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
    cache.clear()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user(db):
    from apps.accounts.tests.factories import UserFactory

    return UserFactory()
