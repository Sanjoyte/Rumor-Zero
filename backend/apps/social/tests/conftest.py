import pytest

from apps.posts.tests.conftest import auth_client, verified_user  # noqa: F401  (fixtures)
from conftest import pin_emergency_settings


@pytest.fixture(autouse=True)
def _feed_cache_on(settings):
    """The developer's own backend/.env may set FEED_CACHE_SECONDS; tests pin it."""
    settings.FEED_CACHE_SECONDS = 30


@pytest.fixture(autouse=True)
def _pinned_emergency_settings(request):
    """The six emergency settings at their defaults in every database test (Part 11C): the seed
    comes from the developer's own `backend/.env`."""
    pin_emergency_settings(request)
