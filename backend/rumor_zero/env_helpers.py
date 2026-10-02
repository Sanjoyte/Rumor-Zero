"""Small helpers for reading settings from the environment (django-environ)."""

from pathlib import Path
from urllib.parse import urlsplit

import environ
from django.core.exceptions import ImproperlyConfigured

# PyJWT warns below 32 bytes for HS256 (RFC 7518 §3.2).
MIN_JWT_KEY_LENGTH = 32
EMAIL_PROVIDERS = ("console", "brevo", "file")


def load_env_file(path):
    """Load a `.env` file if it exists. Variables already in the process env always win."""
    if Path(path).is_file():
        environ.Env.read_env(str(path), overwrite=False)


def require(env, name):
    """Return a non-empty variable, or fail naming the variable (never its value)."""
    value = env.str(name, default="")
    if not value.strip():
        raise ImproperlyConfigured(
            f"Set the {name} environment variable (see backend/.env.example)"
        )
    return value


def int_in_range(env, name, default, minimum, maximum):
    """An integer variable within [minimum, maximum]. Missing or empty → default."""
    raw = env.str(name, default="").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        value = None
    if value is None or not minimum <= value <= maximum:
        raise ImproperlyConfigured(f"{name} must be an integer between {minimum} and {maximum}")
    return value


def bare_origin(name, value, *, https_only):
    """`scheme://host[:port]`, lowercased, without a trailing slash. Anything else fails by name."""
    error = ImproperlyConfigured(
        f"{name} must be a bare origin such as https://example.com (no path, query or user info)"
    )
    try:
        parts = urlsplit(value.strip())
        port = parts.port
    except ValueError:
        raise error from None
    if (
        parts.scheme not in ("http", "https")
        or not parts.hostname
        or parts.username is not None
        or parts.password is not None
        or parts.path not in ("", "/")
        or parts.query
        or parts.fragment
    ):
        raise error
    if https_only and parts.scheme != "https":
        raise ImproperlyConfigured(f"{name} must use https when DJANGO_DEBUG is False")
    host = parts.hostname
    if ":" in host:  # IPv6 literal
        host = f"[{host}]"
    return f"{parts.scheme}://{host}" + (f":{port}" if port is not None else "")


def check_jwt_signing_key(key, secret_key):
    """The HS256 key must be long enough and must not double as DJANGO_SECRET_KEY."""
    if len(key) < MIN_JWT_KEY_LENGTH:
        raise ImproperlyConfigured(
            f"JWT_SIGNING_KEY must be at least {MIN_JWT_KEY_LENGTH} characters "
            "(see docs/ENV_GUIDE.md §1.2)"
        )
    if key == secret_key:
        raise ImproperlyConfigured("JWT_SIGNING_KEY must be different from DJANGO_SECRET_KEY")


def email_config(provider, *, base_dir, brevo_api_key):
    """(EMAIL_BACKEND, EMAIL_FILE_PATH, ANYMAIL) for EMAIL_PROVIDER (console | brevo | file)."""
    if provider == "console":
        return "django.core.mail.backends.console.EmailBackend", None, {}
    if provider == "file":
        # git-ignored; Part 2's E2E test reads the emails from here.
        mail_dir = str(Path(base_dir) / "tmp" / "mail")
        return "django.core.mail.backends.filebased.EmailBackend", mail_dir, {}
    if provider == "brevo":
        if not brevo_api_key.strip():
            raise ImproperlyConfigured(
                "Set the BREVO_API_KEY environment variable when EMAIL_PROVIDER is brevo"
            )
        return "anymail.backends.brevo.EmailBackend", None, {"BREVO_API_KEY": brevo_api_key}
    raise ImproperlyConfigured(f"EMAIL_PROVIDER must be one of: {', '.join(EMAIL_PROVIDERS)}")


def cache_config(redis_url):
    """Redis cache when a URL is set (protocol 2 for Upstash), else an in-process cache."""
    if redis_url:
        return {
            "default": {
                "BACKEND": "django.core.cache.backends.redis.RedisCache",
                "LOCATION": redis_url,
                "OPTIONS": {
                    "protocol": 2,
                    "socket_connect_timeout": 5,
                    "socket_timeout": 5,
                },
            }
        }
    return {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
