"""Settings tests. Deployment checks run in a subprocess with a fully explicit environment."""

import json
import os
import secrets
import subprocess
import sys
from pathlib import Path

import environ
import pytest
from django.contrib.auth.hashers import Argon2PasswordHasher
from django.core.exceptions import ImproperlyConfigured
from rest_framework.throttling import SimpleRateThrottle

import rumor_zero.settings as project_settings
from apps.core.platform_defaults import FIELDS
from rumor_zero.env_helpers import (
    bare_origin,
    cache_config,
    check_jwt_signing_key,
    email_config,
    flag,
    google_client_id,
    int_in_range,
    pipeline_config,
)

BACKEND_DIR = Path(__file__).resolve().parents[3]

FAKE_DB_PASSWORD = "fake-db-pass-9f3"
# Every secret production_env() sets; none may ever appear in output.
SECRET_VARIABLES = (
    "DJANGO_SECRET_KEY",
    "PROXY_SHARED_SECRET",
    "INTERNAL_CRON_SECRET",
    "JWT_SIGNING_KEY",
    "TURNSTILE_SECRET_KEY",
    "BREVO_API_KEY",
    "PIPELINE_API_KEY",
)


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
            "FRONTEND_ORIGIN": "https://app.example.test",
            "AUTH_COOKIE_SECURE": "True",
            "JWT_SIGNING_KEY": secrets.token_urlsafe(48),
            "JWT_ACCESS_TOKEN_MINUTES": "15",
            "JWT_REFRESH_TOKEN_DAYS": "14",
            "TURNSTILE_SECRET_KEY": secrets.token_urlsafe(24),
            "GOOGLE_OAUTH_CLIENT_ID": "",
            "EMAIL_PROVIDER": "brevo",
            "BREVO_API_KEY": "xkeysib-" + secrets.token_hex(16),
            "DEFAULT_FROM_EMAIL": "Rumor Zero <no-reply@example.test>",
            "SENTRY_DSN": "",
            "SENTRY_ENVIRONMENT": "production",
            "SENTRY_TRACES_SAMPLE_RATE": "0.0",
            "PIPELINE_BACKEND": "stub",
            "PIPELINE_INLINE_KICK": "True",
            "PIPELINE_URL": "",
            "PIPELINE_API_KEY": "",
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


def assert_no_secret_in(output, env):
    for name in SECRET_VARIABLES:
        if env[name]:
            assert env[name] not in output, name
    assert FAKE_DB_PASSWORD not in output


@pytest.mark.parametrize(
    "name",
    [
        "DJANGO_SECRET_KEY",
        "DATABASE_URL",
        "PROXY_SHARED_SECRET",
        "INTERNAL_CRON_SECRET",
        "FRONTEND_ORIGIN",
        "JWT_SIGNING_KEY",
        "TURNSTILE_SECRET_KEY",
        "BREVO_API_KEY",
    ],
)
def test_a_missing_required_variable_fails_by_name_without_leaking_values(name):
    env = production_env(**{name: ""})
    result = run_python(["manage.py", "check"], env)

    assert result.returncode != 0
    assert f"Set the {name} environment variable" in result.stderr
    assert_no_secret_in(result.stdout + result.stderr, env)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"JWT_SIGNING_KEY": "k" * 31}, "JWT_SIGNING_KEY must be at least 32 characters"),
        ({"FRONTEND_ORIGIN": "http://app.example.test"}, "FRONTEND_ORIGIN must use https"),
        ({"FRONTEND_ORIGIN": "https://app.example.test/home"}, "FRONTEND_ORIGIN must be a bare"),
        ({"AUTH_COOKIE_SECURE": "False"}, "AUTH_COOKIE_SECURE must be True"),
        ({"EMAIL_PROVIDER": "console"}, "EMAIL_PROVIDER must be brevo"),
        ({"EMAIL_PROVIDER": "file"}, "EMAIL_PROVIDER must be brevo"),
        ({"JWT_ACCESS_TOKEN_MINUTES": "61"}, "JWT_ACCESS_TOKEN_MINUTES must be an integer"),
        ({"JWT_REFRESH_TOKEN_DAYS": "0"}, "JWT_REFRESH_TOKEN_DAYS must be an integer"),
        ({"FEED_CACHE_SECONDS": "301"}, "FEED_CACHE_SECONDS must be an integer"),
        ({"FEED_CACHE_SECONDS": "-1"}, "FEED_CACHE_SECONDS must be an integer"),
        ({"FEED_CACHE_SECONDS": "soon"}, "FEED_CACHE_SECONDS must be an integer"),
    ],
)
def test_production_auth_guards_fail_by_name_without_leaking_values(overrides, message):
    env = production_env(**overrides)
    result = run_python(["manage.py", "check"], env)

    assert result.returncode != 0
    assert message in result.stderr
    assert_no_secret_in(result.stdout + result.stderr, env)


def test_the_jwt_key_must_not_be_the_django_secret_key():
    env = production_env()
    env["JWT_SIGNING_KEY"] = env["DJANGO_SECRET_KEY"]
    result = run_python(["manage.py", "check"], env)

    assert result.returncode != 0
    assert "JWT_SIGNING_KEY must be different from DJANGO_SECRET_KEY" in result.stderr
    assert_no_secret_in(result.stdout + result.stderr, env)


AUTH_PROBE = """
import json
from django.conf import settings
print(json.dumps({
    "frontend_origin": settings.FRONTEND_ORIGIN,
    "frontend_urls": settings.HEADLESS_FRONTEND_URLS,
    "email_backend": settings.EMAIL_BACKEND,
    "anymail_has_key": bool(settings.ANYMAIL.get("BREVO_API_KEY")),
    "jwt_key_is_env": settings.HEADLESS_JWT_PRIVATE_KEY == settings.JWT_SIGNING_KEY,
    "access_seconds": settings.HEADLESS_JWT_ACCESS_TOKEN_EXPIRES_IN,
    "refresh_seconds": settings.HEADLESS_JWT_REFRESH_TOKEN_EXPIRES_IN,
    "cookie_seconds": settings.REFRESH_TOKEN_SECONDS,
    "cookie_secure": settings.AUTH_COOKIE_SECURE,
}))
"""


def test_production_auth_settings_come_from_the_environment():
    env = production_env(FRONTEND_ORIGIN="HTTPS://App.Example.test/", JWT_ACCESS_TOKEN_MINUTES="10")
    env["DJANGO_SETTINGS_MODULE"] = "rumor_zero.settings"
    result = run_python(["-c", "import django; django.setup()\n" + AUTH_PROBE], env)
    assert result.returncode == 0, result.stderr
    probe = json.loads(result.stdout.strip().splitlines()[-1])
    assert probe["frontend_origin"] == "https://app.example.test"
    assert probe["frontend_urls"] == {
        "account_confirm_email": "https://app.example.test/verify-email/{key}",
        "account_reset_password_from_key": "https://app.example.test/reset-password/{key}",
        "account_reset_password": "https://app.example.test/forgot-password",
        "account_signup": "https://app.example.test/signup",
    }
    assert probe["email_backend"] == "anymail.backends.brevo.EmailBackend"
    assert probe["anymail_has_key"] is True
    assert probe["jwt_key_is_env"] is True
    assert probe["access_seconds"] == 600
    assert probe["refresh_seconds"] == probe["cookie_seconds"] == 14 * 86400
    assert probe["cookie_secure"] is True
    assert_no_secret_in(result.stdout + result.stderr, env)


FEED_PROBE = """
import json
from django.conf import settings
print(json.dumps({"seconds": settings.FEED_CACHE_SECONDS}))
"""


def feed_cache_seconds(**overrides):
    env = production_env(**overrides)
    env["DJANGO_SETTINGS_MODULE"] = "rumor_zero.settings"
    result = run_python(["-c", "import django; django.setup()\n" + FEED_PROBE], env)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout.strip().splitlines()[-1])["seconds"]


@pytest.mark.parametrize(
    ("value", "expected"), [("", 30), ("45", 45), ("0", 0), ("300", 300), (" 20 ", 20)]
)
def test_feed_cache_seconds_defaults_to_30_and_accepts_0_to_300(value, expected):
    assert feed_cache_seconds(FEED_CACHE_SECONDS=value) == expected


def test_the_feed_cache_setting_is_not_a_platform_setting():
    assert "FEED_CACHE_SECONDS" not in {name.upper() for name in FIELDS}
    assert "feed_cache_seconds" not in FIELDS


GOOGLE_CLIENT_ID = "123456789012-abcdefghijklmnop.apps.googleusercontent.com"
GOOGLE_PROBE = """
import json
from django.conf import settings
print(json.dumps({
    "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
    "apps": settings.SOCIALACCOUNT_PROVIDERS["google"]["APPS"],
    "installed": [a for a in settings.INSTALLED_APPS if "socialaccount" in a],
}))
"""


def google_probe(**overrides):
    env = production_env(**overrides)
    env["DJANGO_SETTINGS_MODULE"] = "rumor_zero.settings"
    result = run_python(["-c", "import django; django.setup()\n" + GOOGLE_PROBE], env)
    return result, env


def test_google_sign_in_is_configured_from_the_client_id_alone():
    result, env = google_probe(GOOGLE_OAUTH_CLIENT_ID=f"  {GOOGLE_CLIENT_ID} ")
    assert result.returncode == 0, result.stderr
    probe = json.loads(result.stdout.strip().splitlines()[-1])
    assert probe["client_id"] == GOOGLE_CLIENT_ID
    # No client secret: the ID-token flow doesn't use one.
    assert probe["apps"] == [{"client_id": GOOGLE_CLIENT_ID, "secret": "", "key": ""}]
    assert probe["installed"] == [
        "allauth.socialaccount",
        "allauth.socialaccount.providers.google",
    ]
    assert_no_secret_in(result.stdout + result.stderr, env)


def test_a_blank_client_id_disables_google_and_is_not_an_error():
    result, _ = google_probe(GOOGLE_OAUTH_CLIENT_ID="")
    assert result.returncode == 0, result.stderr
    probe = json.loads(result.stdout.strip().splitlines()[-1])
    assert probe["client_id"] == ""
    assert probe["apps"] == []


@pytest.mark.parametrize(
    "value",
    [
        "not-a-client-id",
        "123.apps.googleusercontent.com.evil.example",
        "123 456.apps.googleusercontent.com",
        "1" * 200 + ".apps.googleusercontent.com",
    ],
)
def test_a_malformed_client_id_fails_by_name_without_quoting_the_value(value):
    result, env = google_probe(GOOGLE_OAUTH_CLIENT_ID=value)
    assert result.returncode != 0
    assert "GOOGLE_OAUTH_CLIENT_ID must be a Google OAuth client ID" in result.stderr
    assert value not in result.stdout + result.stderr
    assert_no_secret_in(result.stdout + result.stderr, env)


def test_google_client_id_helper(monkeypatch):
    env = environ.Env()
    monkeypatch.delenv("GOOGLE_OAUTH_CLIENT_ID", raising=False)
    assert google_client_id(env) == ""
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "   ")
    assert google_client_id(env) == ""
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", GOOGLE_CLIENT_ID)
    assert google_client_id(env) == GOOGLE_CLIENT_ID
    for bad in ("x", ".apps.googleusercontent.com"):  # the suffix alone is not an ID
        monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", bad)
        with pytest.raises(ImproperlyConfigured, match="GOOGLE_OAUTH_CLIENT_ID"):
            google_client_id(env)


def test_the_social_account_settings_are_pinned():
    assert project_settings.SOCIALACCOUNT_ADAPTER == "apps.accounts.adapter.SocialAccountAdapter"
    assert project_settings.SOCIALACCOUNT_EMAIL_AUTHENTICATION is True
    assert project_settings.SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT is True
    # A pending social sign-up can't be finished (the middleware strips X-Session-Token).
    assert project_settings.SOCIALACCOUNT_AUTO_SIGNUP is True
    assert project_settings.SOCIALACCOUNT_STORE_TOKENS is False
    assert project_settings.SOCIALACCOUNT_REQUESTS_TIMEOUT == 5
    assert project_settings.SOCIALACCOUNT_PROVIDERS["google"]["VERIFIED_EMAIL"] is False
    # No "account connected" email until Part 14.
    assert getattr(project_settings, "ACCOUNT_EMAIL_NOTIFICATIONS", False) is False


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


def test_all_twelve_throttle_scopes_parse_to_the_documented_rates():
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
        "status_poll": (120, minute),
        "search": (60, minute),
    }
    assert {
        scope: SimpleRateThrottle.parse_rate(object(), rate) for scope, rate in rates.items()
    } == (expected)


def test_drf_authenticates_with_the_project_jwt_class():
    assert project_settings.REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"] == [
        "apps.accounts.authentication.JWTAuthentication"
    ]
    assert project_settings.AUTHENTICATION_BACKENDS == [
        "allauth.account.auth_backends.AuthenticationBackend"
    ]
    assert project_settings.SESSION_ENGINE == "django.contrib.sessions.backends.db"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("http://localhost:3000", "http://localhost:3000"),
        ("http://localhost:3000/", "http://localhost:3000"),
        ("HTTPS://Rumor-Zero.Example.dev", "https://rumor-zero.example.dev"),
        ("https://[::1]:8443", "https://[::1]:8443"),
    ],
)
def test_bare_origin_normalises(value, expected):
    assert bare_origin("FRONTEND_ORIGIN", value, https_only=False) == expected


@pytest.mark.parametrize(
    "value",
    [
        "localhost:3000",
        "ftp://example.com",
        "https://",
        "https://example.com/app",
        "https://example.com?x=1",
        "https://example.com#top",
        "https://user:pw@example.com",
        "https://example.com:99999",
    ],
)
def test_bare_origin_rejects_anything_but_an_origin(value):
    with pytest.raises(ImproperlyConfigured, match="FRONTEND_ORIGIN must be a bare origin"):
        bare_origin("FRONTEND_ORIGIN", value, https_only=False)


def test_bare_origin_requires_https_when_asked():
    with pytest.raises(ImproperlyConfigured, match="must use https"):
        bare_origin("FRONTEND_ORIGIN", "http://example.com", https_only=True)


def test_int_in_range_reads_defaults_and_rejects_out_of_range(monkeypatch):
    env = environ.Env()
    monkeypatch.delenv("RZ_TEST_NUMBER", raising=False)
    assert int_in_range(env, "RZ_TEST_NUMBER", 15, 1, 60) == 15
    monkeypatch.setenv("RZ_TEST_NUMBER", "60")
    assert int_in_range(env, "RZ_TEST_NUMBER", 15, 1, 60) == 60
    for bad in ("0", "61", "ten", "1.5"):
        monkeypatch.setenv("RZ_TEST_NUMBER", bad)
        with pytest.raises(ImproperlyConfigured, match="RZ_TEST_NUMBER must be an integer"):
            int_in_range(env, "RZ_TEST_NUMBER", 15, 1, 60)


def test_jwt_signing_key_check():
    check_jwt_signing_key("k" * 32, "other")
    with pytest.raises(ImproperlyConfigured, match="at least 32"):
        check_jwt_signing_key("k" * 31, "other")
    with pytest.raises(ImproperlyConfigured, match="different from DJANGO_SECRET_KEY"):
        check_jwt_signing_key("k" * 40, "k" * 40)


def test_email_config_for_each_provider(tmp_path):
    console = email_config("console", base_dir=tmp_path, brevo_api_key="")
    assert console == ("django.core.mail.backends.console.EmailBackend", None, {})
    backend, path, anymail = email_config("file", base_dir=tmp_path, brevo_api_key="")
    assert backend == "django.core.mail.backends.filebased.EmailBackend"
    assert Path(path) == tmp_path / "tmp" / "mail"
    assert anymail == {}
    brevo = email_config("brevo", base_dir=tmp_path, brevo_api_key="xkeysib-fake")
    assert brevo == ("anymail.backends.brevo.EmailBackend", None, {"BREVO_API_KEY": "xkeysib-fake"})
    with pytest.raises(ImproperlyConfigured, match="Set the BREVO_API_KEY"):
        email_config("brevo", base_dir=tmp_path, brevo_api_key=" ")
    with pytest.raises(ImproperlyConfigured, match="EMAIL_PROVIDER must be one of"):
        email_config("smtp", base_dir=tmp_path, brevo_api_key="")


def test_email_limits_and_enumeration_settings():
    from allauth.account import app_settings as account_settings
    from allauth.core.internal.ratelimit import Rate, parse_rates

    limits = account_settings.RATE_LIMITS
    day, minute = 86400, 60
    assert parse_rates(limits["confirm_email"]) == [Rate(1, 60, "key")]
    assert parse_rates(limits["confirm_email_daily"]) == [Rate(10, day, "key")]
    assert parse_rates(limits["reset_password"]) == [Rate(20, minute, "ip"), Rate(5, minute, "key")]
    assert parse_rates(limits["reset_password_daily"]) == [
        Rate(50, day, "ip"),
        Rate(10, day, "key"),
    ]
    assert parse_rates(limits["reset_password_from_key"]) == [Rate(20, minute, "ip")]
    # allauth keeps one history per action and "per" type, so a repeated type would let the
    # short rate prune what the long one needs.
    for action, rates in limits.items():
        pers = [rate.per for rate in parse_rates(rates)]
        assert len(pers) == len(set(pers)), action

    assert project_settings.ACCOUNT_EMAIL_UNKNOWN_ACCOUNTS is False
    assert project_settings.ACCOUNT_PREVENT_ENUMERATION is True
    assert project_settings.PASSWORD_RESET_TIMEOUT == 24 * 3600
    assert project_settings.ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS == 1


# ---------- Fact-check pipeline (Part 9) ----------

PIPELINE_KEY = secrets.token_urlsafe(24)
PIPELINE_PROBE = """
import json
from django.conf import settings
print(json.dumps({
    "backend": settings.PIPELINE_BACKEND,
    "kick": settings.PIPELINE_INLINE_KICK,
    "url": settings.PIPELINE_URL,
    "has_key": bool(settings.PIPELINE_API_KEY),
}))
"""


def pipeline_settings(**overrides):
    env = production_env(**overrides)
    env["DJANGO_SETTINGS_MODULE"] = "rumor_zero.settings"
    result = run_python(["-c", "import django; django.setup()\n" + PIPELINE_PROBE], env)
    assert result.returncode == 0, result.stderr
    assert_no_secret_in(result.stdout + result.stderr, env)
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_the_pipeline_defaults_to_the_stub_with_the_inline_kick_on():
    probe = pipeline_settings(PIPELINE_BACKEND="", PIPELINE_INLINE_KICK="")
    assert probe == {"backend": "stub", "kick": True, "url": "", "has_key": False}


def test_the_stub_ignores_a_url_and_a_key_and_the_kick_can_be_turned_off():
    probe = pipeline_settings(
        PIPELINE_INLINE_KICK="False",
        PIPELINE_URL="https://pipeline.example.test/check",
        PIPELINE_API_KEY=PIPELINE_KEY,
    )
    assert probe == {"backend": "stub", "kick": False, "url": "", "has_key": False}


def test_the_http_pipeline_reads_its_url_and_key():
    probe = pipeline_settings(
        PIPELINE_BACKEND="http",
        PIPELINE_URL="https://pipeline.example.test/v1/check",
        PIPELINE_API_KEY=PIPELINE_KEY,
    )
    assert probe == {
        "backend": "http",
        "kick": True,
        "url": "https://pipeline.example.test/v1/check",
        "has_key": True,
    }


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"PIPELINE_BACKEND": "celery"}, "PIPELINE_BACKEND must be one of: stub, http"),
        (
            {"PIPELINE_BACKEND": "http", "PIPELINE_API_KEY": PIPELINE_KEY},
            "Set the PIPELINE_URL environment variable",
        ),
        (
            {"PIPELINE_BACKEND": "http", "PIPELINE_URL": "https://pipeline.example.test/check"},
            "Set the PIPELINE_API_KEY environment variable",
        ),
        (
            {
                "PIPELINE_BACKEND": "http",
                "PIPELINE_URL": "http://pipeline.example.test/check",
                "PIPELINE_API_KEY": PIPELINE_KEY,
            },
            "PIPELINE_URL must be an https:// URL",
        ),
    ],
)
def test_a_bad_pipeline_configuration_fails_by_name_without_leaking_values(overrides, message):
    env = production_env(**overrides)
    result = run_python(["manage.py", "check"], env)

    assert result.returncode != 0
    assert message in result.stderr
    assert_no_secret_in(result.stdout + result.stderr, env)


def pipeline_env(monkeypatch, **values):
    for name in ("PIPELINE_BACKEND", "PIPELINE_URL", "PIPELINE_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    return environ.Env()


@pytest.mark.parametrize(
    "url",
    [
        "https://pipeline.example.test/check",
        "https://pipeline.example.test:8443/v1/check?mode=full",
        "http://localhost:9000/check",
        "http://127.0.0.1:9000/check",
        "http://[::1]:9000/check",
    ],
)
def test_the_pipeline_url_can_be_https_or_plain_http_to_a_loopback_host(monkeypatch, url):
    env = pipeline_env(
        monkeypatch, PIPELINE_BACKEND="http", PIPELINE_URL=url, PIPELINE_API_KEY="key"
    )
    assert pipeline_config(env) == ("http", url, "key")


@pytest.mark.parametrize(
    "url",
    [
        "http://pipeline.example.test/check",
        "http://10.0.0.1/check",
        "ftp://pipeline.example.test/check",
        "pipeline.example.test/check",
        "https://user:pw@pipeline.example.test/check",
        "https://pipeline.example.test/check#part",
        "https:///check",
        "https://pipeline.example.test:99999/check",
        "https://pipeline.example.test/a b",
    ],
)
def test_any_other_pipeline_url_fails_by_name_without_quoting_it(monkeypatch, url):
    env = pipeline_env(
        monkeypatch, PIPELINE_BACKEND="http", PIPELINE_URL=url, PIPELINE_API_KEY="key"
    )
    with pytest.raises(ImproperlyConfigured, match="PIPELINE_URL must be an https:// URL") as exc:
        pipeline_config(env)
    assert url not in str(exc.value)


def test_the_stub_needs_no_url_or_key(monkeypatch):
    assert pipeline_config(pipeline_env(monkeypatch)) == ("stub", "", "")
    assert pipeline_config(pipeline_env(monkeypatch, PIPELINE_BACKEND=" stub ")) == ("stub", "", "")


def test_flag_reads_a_missing_or_empty_variable_as_its_default(monkeypatch):
    env = environ.Env()
    monkeypatch.delenv("RZ_TEST_FLAG", raising=False)
    assert flag(env, "RZ_TEST_FLAG", True) is True
    monkeypatch.setenv("RZ_TEST_FLAG", " ")
    assert flag(env, "RZ_TEST_FLAG", True) is True
    for value, expected in (("False", False), ("0", False), ("True", True), ("yes", True)):
        monkeypatch.setenv("RZ_TEST_FLAG", value)
        assert flag(env, "RZ_TEST_FLAG", not expected) is expected
