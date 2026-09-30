from django.conf import settings
from django.core.cache import cache

from apps.core.models import PLATFORM_SETTINGS_CACHE_KEY, PlatformSettings

PLATFORM_SETTINGS_CACHE_SECONDS = 60


def get_platform_settings():
    """Return the PlatformSettings singleton through a 60 s cache."""
    platform_settings = cache.get(PLATFORM_SETTINGS_CACHE_KEY)
    if platform_settings is None:
        # get_or_create also heals a missing row (e.g. after a test flush).
        platform_settings, _ = PlatformSettings.objects.get_or_create(
            pk=1, defaults=settings.PLATFORM_SETTINGS_SEED
        )
        cache.set(PLATFORM_SETTINGS_CACHE_KEY, platform_settings, PLATFORM_SETTINGS_CACHE_SECONDS)
    return platform_settings
