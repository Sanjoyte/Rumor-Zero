"""Settings tests. Deployment checks run in a subprocess with a fully explicit environment."""

import json
import os
import secrets
import subprocess
import sys
from pathlib import Path

import pytest
from django.contrib.auth.hashers import Argon2PasswordHasher
from rest_framework.throttling import SimpleRateThrottle

import rumor_zero.settings as project_settings
from apps.core.platform_defaults import FIELDS
from rumor_zero.env_helpers import cache_config

BACKEND_DIR = Path(__file__).resolve().parents[3]

FAKE_DB_PASSWORD = "fake-db-pass-9f3"


def production_env(**overrides):
    """A production-like environment. Every variable the settings read is set explicitly (an
    empty string still counts as set), so backend/.env can never influence the result."""
    env = os.environ.copy()
    env.update(
        {
            "DJANGO_SECRET_KEY": secrets.token_urlsafe(50),
            "DJANGO_DEBUG": "False",
            "DJANGO_ALLOWED_HOSTS": "api.example.test",
            "DJANGO_CSRF_TRUSTED_ORIGINS": "https://api.example.test",
            "ADMIN_URL_PATH": "control-room-4711/",
            "DATABASE_URL": f"postgres://fake_user:{FAKE_DB_PASSWORD}@db.example.invalid:5432/fake",
            "REDIS_URL": "",
            "PROXY_SHARED_SECRET": secrets.token_urlsafe(24),
            "INTERNAL_CRON_SECRET": secrets.token_urlsafe(24),
            "SENTRY_DSN": "",
            "SENTRY_ENVIRONMENT": "production",
            "SENTRY_TRACES_SAMPLE_RATE": "0.0",
            **{name: str(default) for name, default, _, _ in FIELDS.values()},
        }
    )
    env.update(overrides)
    return env


def run_python(args, env):
    return subprocess.run(
        [sys.executable, *args],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


PROBE = """
import json
from django.conf import settings
print(json.dumps({
    "debug": settings.DEBUG,
    "proxy_ssl_header": list(settings.SECURE_PROXY_SSL_HEADER),
    "ssl_redirect": settings.SECURE_SSL_REDIRECT,
    "redirect_exempt": settings.SECURE_REDIRECT_EXEMPT,
    "hsts_seconds": settings.SECURE_HSTS_SECONDS,
    "hsts_subdomains": settings.SECURE_HSTS_INCLUDE_SUBDOMAINS,
    "session_cookie_secure": settings.SESSION_COOKIE_SECURE,
    "csrf_cookie_secure": settings.CSRF_COOKIE_SECURE,
}))
"""


def test_check_deploy_passes_with_production_like_env():
    result = run_python(
        ["manage.py", "check", "--deploy", "--fail-level", "WARNING"], production_env()
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_production_security_flags_are_on():
    env = production_env()
    env["DJANGO_SETTINGS_MODULE"] = "rumor_zero.settings"
    result = run_python(["-c", "import django; django.setup()\n" + PROBE], env)
    assert result.returncode == 0, result.stderr
    flags = json.loads(result.stdout.strip().splitlines()[-1])
    assert flags["debug"] is False
    assert flags["proxy_ssl_header"] == ["HTTP_X_FORWARDED_PROTO", "https"]
    assert flags["ssl_redirect"] is True
    assert flags["redirect_exempt"] == [r"^api/health/$"]
    assert flags["hsts_seconds"] >= 31536000
    assert flags["hsts_subdomains"] is True
    assert flags["session_cookie_secure"] is True
    assert flags["csrf_cookie_secure"] is True


@pytest.mark.parametrize(
    "name", ["DJANGO_SECRET_KEY", "DATABASE_URL", "PROXY_SHARED_SECRET", "INTERNAL_CRON_SECRET"]
)
def test_a_missing_required_variable_fails_by_name_without_leaking_values(name):
    env = production_env(**{name: ""})
    result = run_python(["manage.py", "check"], env)

    assert result.returncode != 0
    assert f"Set the {name} environment variable" in result.stderr
    output = result.stdout + result.stderr
    for other in ("DJANGO_SECRET_KEY", "PROXY_SHARED_SECRET", "INTERNAL_CRON_SECRET"):
        if other != name:
            assert env[other] not in output
    assert FAKE_DB_PASSWORD not in output


@pytest.mark.parametrize("path", ["/admin/", "admin", ""])
def test_admin_url_path_must_end_with_a_slash_and_not_start_with_one(path):
    result = run_python(["manage.py", "check"], production_env(ADMIN_URL_PATH=path))
    assert result.returncode != 0
    assert "ADMIN_URL_PATH" in result.stderr


def test_health_is_exempt_from_the_https_redirect_but_other_paths_are_not(client, settings):
    settings.SECURE_SSL_REDIRECT = True
    settings.SECURE_REDIRECT_EXEMPT = project_settings.SECURE_REDIRECT_EXEMPT
    assert client.get("/api/health/").status_code == 200
    assert client.get("/api/health/deep/").status_code == 301


# ---------- pure settings data ----------


def test_cache_config_uses_redis_protocol_2_when_a_url_is_set():
    config = cache_config("rediss://default:pw@example.invalid:6379/0")["default"]
    assert config["BACKEND"] == "django.core.cache.backends.redis.RedisCache"
    assert config["LOCATION"] == "rediss://default:pw@example.invalid:6379/0"
    assert config["OPTIONS"]["protocol"] == 2
    assert config["OPTIONS"]["socket_connect_timeout"] == 5
    assert config["OPTIONS"]["socket_timeout"] == 5


def test_cache_config_falls_back_to_local_memory_without_a_url():
    config = cache_config("")["default"]
    assert config == {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}


def test_argon2_is_the_first_password_hasher():
    # The project module, not django.conf.settings: the test fixture swaps in a fast hasher.
    assert project_settings.PASSWORD_HASHERS[0].endswith("Argon2PasswordHasher")
    hasher = Argon2PasswordHasher()
    assert hasher.encode("pw", hasher.salt()).startswith("argon2$argon2id$")


def test_drf_defaults():
    rest = project_settings.REST_FRAMEWORK
    assert rest["DEFAULT_RENDERER_CLASSES"] == ["rest_framework.renderers.JSONRenderer"]
    assert rest["DEFAULT_PARSER_CLASSES"] == ["rest_framework.parsers.JSONParser"]
    assert rest["NUM_PROXIES"] == 0
    assert rest["PAGE_SIZE"] == 20
    assert rest["DEFAULT_PAGINATION_CLASS"] == "apps.core.pagination.CursorPagination"
    assert rest["EXCEPTION_HANDLER"] == "apps.core.exceptions.api_exception_handler"
    assert "DEFAULT_THROTTLE_CLASSES" not in rest  # views opt in per scope


def test_all_ten_throttle_scopes_parse_to_the_documented_rates():
    rates = project_settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
    hour, day, minute = 3600, 86400, 60
    expected = {
        "post_create": (30, hour),
        "comment": (60, hour),
        "like": (300, hour),
        "follow": (100, hour),
        "report": (10, hour),
        "appeal": (5, day),
        "repost": (100, hour),
        "bookmark": (300, hour),
        "avatar_upload": (5, day),
        "username_check": (30, minute),
    }
    assert {
        scope: SimpleRateThrottle.parse_rate(object(), rate) for scope, rate in rates.items()
    } == (expected)
