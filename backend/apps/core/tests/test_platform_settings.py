import environ
import pytest
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import IntegrityError, transaction

from apps.core.models import PLATFORM_SETTINGS_CACHE_KEY, PlatformSettings
from apps.core.platform_defaults import FIELDS, read_seed
from apps.core.services import get_platform_settings

pytestmark = pytest.mark.django_db

ENV_NAMES = [name for name, *_ in FIELDS.values()]
DEFAULTS = {field: default for field, (_, default, _, _) in FIELDS.items()}


@pytest.fixture
def clean_env(monkeypatch):
    for name in ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


# ---------- seed ----------


def test_the_migration_created_the_singleton_row(settings):
    row = PlatformSettings.objects.get()
    assert row.pk == 1
    for field, value in settings.PLATFORM_SETTINGS_SEED.items():
        assert getattr(row, field) == value


def test_documented_defaults():
    assert DEFAULTS == {
        "report_threshold": 5,
        "report_window_hours": 24,
        "report_min_account_age_hours": 24,
        "confidence_threshold": 85,
        "fact_posts_per_day": 10,
        "emergency_duration_hours": 24,
        "emergency_posts_per_day": 1,
        "emergency_min_account_age_days": 7,
        "emergency_min_reputation": 40,
        "emergency_report_threshold": 2,
        "emergency_false_cooldown_days": 30,
    }


def test_read_seed_uses_defaults_when_nothing_is_set(clean_env):
    assert read_seed(environ.Env()) == DEFAULTS


def test_read_seed_applies_overrides(clean_env):
    clean_env.setenv("REPORT_THRESHOLD", "7")
    clean_env.setenv("EMERGENCY_DURATION_HOURS", "48")
    seed = read_seed(environ.Env())
    assert seed["report_threshold"] == 7
    assert seed["emergency_duration_hours"] == 48
    assert seed["confidence_threshold"] == 85


def test_missing_emergency_variables_fall_back_to_their_defaults(clean_env):
    clean_env.setenv("REPORT_THRESHOLD", "9")
    clean_env.setenv("EMERGENCY_MIN_REPUTATION", "")  # empty counts as missing
    seed = read_seed(environ.Env())
    assert seed["report_threshold"] == 9
    for field in DEFAULTS:
        if field.startswith("emergency_"):
            assert seed[field] == DEFAULTS[field]


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("REPORT_THRESHOLD", "12x34"),
        ("REPORT_THRESHOLD", "0"),
        ("CONFIDENCE_THRESHOLD", "101"),
        ("EMERGENCY_MIN_REPUTATION", "-1"),
        ("EMERGENCY_DURATION_HOURS", "0"),
        ("FACT_POSTS_PER_DAY", "99999"),
    ],
)
def test_read_seed_rejects_invalid_values_naming_the_variable(clean_env, name, value):
    clean_env.setenv(name, value)
    with pytest.raises(ImproperlyConfigured) as excinfo:
        read_seed(environ.Env())
    assert name in str(excinfo.value)
    if not value.lstrip("-").isdigit():
        assert value not in str(excinfo.value)  # the raw value is never echoed


def test_a_per_day_limit_of_zero_is_a_valid_kill_switch(clean_env):
    clean_env.setenv("FACT_POSTS_PER_DAY", "0")
    clean_env.setenv("EMERGENCY_POSTS_PER_DAY", "0")
    seed = read_seed(environ.Env())
    assert seed["fact_posts_per_day"] == 0
    assert seed["emergency_posts_per_day"] == 0


# ---------- cached accessor ----------


def test_accessor_reads_the_database_once_then_the_cache(django_assert_num_queries):
    with django_assert_num_queries(1):
        first = get_platform_settings()
    with django_assert_num_queries(0):
        second = get_platform_settings()
    assert first.pk == second.pk == 1


def test_save_invalidates_the_cache():
    row = get_platform_settings()
    row.report_threshold = 9
    row.save()
    assert cache.get(PLATFORM_SETTINGS_CACHE_KEY) is None
    assert get_platform_settings().report_threshold == 9


def test_save_clears_the_cache_again_on_commit(django_capture_on_commit_callbacks):
    row = get_platform_settings()
    with django_capture_on_commit_callbacks(execute=True):
        row.save()
        # A concurrent reader repopulating the cache mid-transaction with the old values...
        cache.set(PLATFORM_SETTINGS_CACHE_KEY, row, 60)
    # ...must not survive the commit.
    assert cache.get(PLATFORM_SETTINGS_CACHE_KEY) is None


def test_a_deleted_row_is_recreated_from_the_seed(settings):
    PlatformSettings.objects.all().delete()
    cache.clear()
    row = get_platform_settings()
    assert PlatformSettings.objects.count() == 1
    assert row.report_threshold == settings.PLATFORM_SETTINGS_SEED["report_threshold"]


# ---------- constraints ----------


@pytest.mark.parametrize(
    ("field", "bad_value"),
    [
        ("report_threshold", 0),
        ("report_window_hours", 0),
        ("emergency_duration_hours", 0),
        ("emergency_report_threshold", 0),
        ("confidence_threshold", 101),
        ("emergency_min_reputation", 101),
        ("fact_posts_per_day", -1),
    ],
)
def test_database_rejects_out_of_range_values(field, bad_value):
    with pytest.raises(IntegrityError), transaction.atomic():
        PlatformSettings.objects.filter(pk=1).update(**{field: bad_value})


@pytest.mark.parametrize("field", ["fact_posts_per_day", "emergency_posts_per_day"])
def test_database_accepts_zero_for_per_day_limits(field):
    PlatformSettings.objects.filter(pk=1).update(**{field: 0})
    assert getattr(PlatformSettings.objects.get(pk=1), field) == 0


def test_only_one_row_can_exist():
    with pytest.raises(IntegrityError), transaction.atomic():
        PlatformSettings.objects.create(pk=2)


def test_model_validators_mirror_the_database_ranges():
    row = PlatformSettings.objects.get(pk=1)
    row.report_threshold = 0
    with pytest.raises(ValidationError) as excinfo:
        row.full_clean()
    assert "report_threshold" in excinfo.value.message_dict
