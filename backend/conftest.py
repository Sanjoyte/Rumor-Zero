import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

# pytest-django loads the settings module before this file, so tests change settings through the
# `settings` fixture or `monkeypatch`, never by injecting environment variables here.


@pytest.fixture(autouse=True)
def _hermetic(settings):
    """Keep tests independent of the developer's .env: no real Redis, static build or hashing."""
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
    cache.clear()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user(db):
    from apps.accounts.tests.factories import UserFactory

    return UserFactory()
