from django.conf import settings
from django.core.cache import cache
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction

from apps.core.platform_defaults import FIELDS

PLATFORM_SETTINGS_CACHE_KEY = "core:platform_settings:v1"


def _setting_field(name):
    _, default, minimum, maximum = FIELDS[name]
    return models.PositiveSmallIntegerField(
        default=default, validators=[MinValueValidator(minimum), MaxValueValidator(maximum)]
    )


class PlatformSettings(models.Model):
    """Singleton (id=1) holding the thresholds moderators can tune (ARCHITECTURE §2, §3)."""

    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)

    report_threshold = _setting_field("report_threshold")
    report_window_hours = _setting_field("report_window_hours")
    report_min_account_age_hours = _setting_field("report_min_account_age_hours")
    confidence_threshold = _setting_field("confidence_threshold")
    fact_posts_per_day = _setting_field("fact_posts_per_day")
    emergency_duration_hours = _setting_field("emergency_duration_hours")
    emergency_posts_per_day = _setting_field("emergency_posts_per_day")
    emergency_min_account_age_days = _setting_field("emergency_min_account_age_days")
    emergency_min_reputation = _setting_field("emergency_min_reputation")
    emergency_report_threshold = _setting_field("emergency_report_threshold")
    emergency_false_cooldown_days = _setting_field("emergency_false_cooldown_days")

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "platform settings"
        verbose_name_plural = "platform settings"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(id=1), name="core_platformsettings_singleton"
            ),
            *(
                models.CheckConstraint(
                    condition=models.Q(**{f"{field}__gte": minimum, f"{field}__lte": maximum}),
                    name=f"core_platformsettings_{field}_range",
                )
                for field, (_, _, minimum, maximum) in FIELDS.items()
            ),
        ]

    def __str__(self):
        return "Platform settings"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Now, and again after commit, so a reader that repopulates the cache mid-transaction
        # can't leave the old values behind.
        cache.delete(PLATFORM_SETTINGS_CACHE_KEY)
        transaction.on_commit(lambda: cache.delete(PLATFORM_SETTINGS_CACHE_KEY))
