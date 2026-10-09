import pytest
from django.conf import settings
from rest_framework.test import APIClient

from apps.accounts.tests.conftest import access_token_for
from apps.core.models import PlatformSettings
from apps.core.services import get_platform_settings
from apps.posts.tests.factories import VerifiedUserFactory


@pytest.fixture
def verified_user(db):
    return VerifiedUserFactory()


@pytest.fixture
def auth_client():
    """A client that sends a valid access token for the given user."""

    def make(user):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token_for(user)}")
        return client

    return make


@pytest.fixture
def fact_limit(db):
    """Pin `fact_posts_per_day`. The seed comes from the developer's .env, so tests must not
    rely on it. It saves the singleton (`.update()` would skip the cache invalidation)."""

    def set_limit(value):
        # A transaction=True test flushes the seeded row; get_or_create heals it.
        row, _ = PlatformSettings.objects.get_or_create(
            pk=1, defaults=settings.PLATFORM_SETTINGS_SEED
        )
        row.fact_posts_per_day = value
        row.save()
        return get_platform_settings()

    set_limit(10)
    return set_limit
