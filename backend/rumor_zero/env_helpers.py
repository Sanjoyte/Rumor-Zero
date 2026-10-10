"""Small helpers for reading settings from the environment (django-environ)."""

import ipaddress
from pathlib import Path
from urllib.parse import urlsplit

import environ
from django.core.exceptions import ImproperlyConfigured

# PyJWT warns below 32 bytes for HS256 (RFC 7518 §3.2).
MIN_JWT_KEY_LENGTH = 32
EMAIL_PROVIDERS = ("console", "brevo", "file")
PIPELINE_BACKENDS = ("stub", "http")


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


def flag(env, name, default):
    """A True/False variable. Missing or empty → default (django-environ alone reads "" as
    False, which would make `NAME=` in .env turn a feature off)."""
    if not env.str(name, default="").strip():
        return default
    return env.bool(name)


def _is_loopback(host):
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def pipeline_url(name, value):
    """The real pipeline's endpoint: an https:// URL, or plain http:// to a loopback host only
    (the relay's rule: the API key never travels in clear). Errors name the variable only."""
    value = value.strip()
    if not value:
        raise ImproperlyConfigured(
            f"Set the {name} environment variable when PIPELINE_BACKEND is http"
        )
    error = ImproperlyConfigured(
        f"{name} must be an https:// URL (plain http:// only to a loopback host), "
        "with no user info or fragment"
    )
    try:
        parts = urlsplit(value)
        parts.port  # noqa: B018 (raises ValueError for a bad port)
    except ValueError:
        raise error from None
    if (
        parts.scheme not in ("http", "https")
        or not parts.hostname
        or parts.username is not None
        or parts.password is not None
        or parts.fragment
        or any(ch.isspace() or ord(ch) < 32 for ch in value)
    ):
        raise error
    if parts.scheme == "http" and not _is_loopback(parts.hostname):
        raise error
    return value


def pipeline_config(env):
    """(PIPELINE_BACKEND, PIPELINE_URL, PIPELINE_API_KEY) (ARCHITECTURE §6).

    `stub` (the default) needs nothing else and ignores the other two; `http` needs both. A wrong
    value fails at startup naming the variable, never quoting it.
    """
    backend = env.str("PIPELINE_BACKEND", default="").strip() or "stub"
    if backend not in PIPELINE_BACKENDS:
        raise ImproperlyConfigured(
            f"PIPELINE_BACKEND must be one of: {', '.join(PIPELINE_BACKENDS)}"
        )
    if backend == "stub":
        return backend, "", ""
    url = pipeline_url("PIPELINE_URL", env.str("PIPELINE_URL", default=""))
    api_key = env.str("PIPELINE_API_KEY", default="").strip()
    if not api_key:
        raise ImproperlyConfigured(
            "Set the PIPELINE_API_KEY environment variable when PIPELINE_BACKEND is http"
        )
    return backend, url, api_key


GOOGLE_CLIENT_ID_SUFFIX = ".apps.googleusercontent.com"
MAX_GOOGLE_CLIENT_ID_LENGTH = 200


def google_client_id(env, name="GOOGLE_OAUTH_CLIENT_ID"):
    """The Google OAuth web client ID, or "" when Google sign-in is disabled.

    A client ID is public, but a malformed one is a typo that would make every sign-in fail, so it
    is refused at startup. The error names the variable and never quotes the value.
    """
    value = env.str(name, default="").strip()
    if not value:
        return ""
    if (
        len(value) > MAX_GOOGLE_CLIENT_ID_LENGTH
        or not value.endswith(GOOGLE_CLIENT_ID_SUFFIX)
        or len(value) == len(GOOGLE_CLIENT_ID_SUFFIX)
        or any(ch.isspace() for ch in value)
    ):
        raise ImproperlyConfigured(
            f"{name} must be a Google OAuth client ID ending in {GOOGLE_CLIENT_ID_SUFFIX} "
            "(see docs/ENV_GUIDE.md §1.6), or empty to disable Google sign-in"
        )
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
