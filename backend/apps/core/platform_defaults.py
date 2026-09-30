"""Initial PlatformSettings values (ARCHITECTURE §3): env names, defaults and allowed ranges.

Kept free of Django model imports so `rumor_zero/settings.py` can use it.
"""

from django.core.exceptions import ImproperlyConfigured

SMALLINT_MAX = 32767

# field name -> (env variable, default, minimum, maximum)
FIELDS = {
    "report_threshold": ("REPORT_THRESHOLD", 5, 1, SMALLINT_MAX),
    "report_window_hours": ("REPORT_WINDOW_HOURS", 24, 1, SMALLINT_MAX),
    "report_min_account_age_hours": ("REPORT_MIN_ACCOUNT_AGE_HOURS", 24, 0, SMALLINT_MAX),
    "confidence_threshold": ("CONFIDENCE_THRESHOLD", 85, 0, 100),
    "fact_posts_per_day": ("FACT_POSTS_PER_DAY", 10, 0, SMALLINT_MAX),
    "emergency_duration_hours": ("EMERGENCY_DURATION_HOURS", 24, 1, SMALLINT_MAX),
    "emergency_posts_per_day": ("EMERGENCY_POSTS_PER_DAY", 1, 0, SMALLINT_MAX),
    "emergency_min_account_age_days": ("EMERGENCY_MIN_ACCOUNT_AGE_DAYS", 7, 0, SMALLINT_MAX),
    "emergency_min_reputation": ("EMERGENCY_MIN_REPUTATION", 40, 0, 100),
    "emergency_report_threshold": ("EMERGENCY_REPORT_THRESHOLD", 2, 1, SMALLINT_MAX),
    "emergency_false_cooldown_days": ("EMERGENCY_FALSE_COOLDOWN_DAYS", 30, 0, SMALLINT_MAX),
}


def read_seed(env):
    """Return {field: value} from the environment. Missing → default; invalid → error by name."""
    seed = {}
    for field, (name, default, minimum, maximum) in FIELDS.items():
        raw = env.str(name, default="").strip()
        if not raw:
            seed[field] = default
            continue
        try:
            value = int(raw)
        except ValueError:
            value = None
        if value is None or not minimum <= value <= maximum:
            raise ImproperlyConfigured(f"{name} must be an integer between {minimum} and {maximum}")
        seed[field] = value
    return seed
