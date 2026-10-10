import pytest
from django.conf import settings

from apps.core.models import PlatformSettings
from apps.core.services import get_platform_settings
from apps.posts.tests.conftest import auth_client, verified_user  # noqa: F401  (fixtures)


@pytest.fixture
def report_settings(db):
    """Pin the three report settings. The seed comes from the developer's own `backend/.env`, so
    tests must not rely on it. It saves the singleton (`.update()` would skip the cache
    invalidation); a `transaction=True` test flushes the row, so it is healed with
    `get_or_create`."""

    def set_values(*, threshold=5, window_hours=24, min_age_hours=24):
        row, _ = PlatformSettings.objects.get_or_create(
            pk=1, defaults=settings.PLATFORM_SETTINGS_SEED
        )
        row.report_threshold = threshold
        row.report_window_hours = window_hours
        row.report_min_account_age_hours = min_age_hours
        row.save()
        return get_platform_settings()

    set_values()
    return set_values


@pytest.fixture(autouse=True)
def _pinned_report_settings(report_settings):
    """Every test in this app starts from threshold 5, a 24 h window and a 24 h minimum age."""
