import pytest

from apps.posts.tests.conftest import auth_client, verified_user  # noqa: F401  (fixtures)


@pytest.fixture(autouse=True)
def _feed_cache_on(settings):
    """The developer's own backend/.env may set FEED_CACHE_SECONDS; tests pin it."""
    settings.FEED_CACHE_SECONDS = 30
