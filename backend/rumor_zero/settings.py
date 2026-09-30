"""Django settings for Rumor Zero. Everything comes from the environment (django-environ)."""

from pathlib import Path

import environ
from django.core.exceptions import ImproperlyConfigured

from apps.core import platform_defaults
from rumor_zero.env_helpers import cache_config, load_env_file, require
from rumor_zero.sentry import init_sentry

BASE_DIR = Path(__file__).resolve().parent.parent

# backend/.env is optional and never overrides variables already in the process environment.
load_env_file(BASE_DIR / ".env")
env = environ.Env()

# ---------- Core ----------
SECRET_KEY = require(env, "DJANGO_SECRET_KEY")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=[])
CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])

ADMIN_URL_PATH = env.str("ADMIN_URL_PATH", default="admin/")
if not ADMIN_URL_PATH.endswith("/") or ADMIN_URL_PATH.startswith("/"):
    raise ImproperlyConfigured("ADMIN_URL_PATH must end with '/' and must not start with '/'")

# Shared with the frontend API relay (X-RZ-Proxy-Secret) and the cron/health callers
# (X-RZ-Cron-Secret).
PROXY_SHARED_SECRET = require(env, "PROXY_SHARED_SECRET")
INTERNAL_CRON_SECRET = require(env, "INTERNAL_CRON_SECRET")

# Initial PlatformSettings values, used by the seed migration and the model's get_or_create.
PLATFORM_SETTINGS_SEED = platform_defaults.read_seed(env)

# ---------- Apps and middleware ----------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    "rest_framework",
    "apps.core",
    "apps.accounts",
]

AUTH_USER_MODEL = "accounts.User"

MIDDLEWARE = [
    # First, so nothing else ever sees the X-RZ-* headers or an untrusted client address.
    "apps.core.middleware.ClientIPMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "rumor_zero.urls"
WSGI_APPLICATION = "rumor_zero.wsgi.application"
ASGI_APPLICATION = "rumor_zero.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ---------- Database and cache ----------
DATABASES = {"default": env.db_url_config(require(env, "DATABASE_URL"))}
DATABASES["default"]["CONN_MAX_AGE"] = 60
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CACHES = cache_config(env.str("REDIS_URL", default=""))

# ---------- Passwords ----------
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------- Time and static files ----------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# ---------- Django REST framework ----------
REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
    # Part 1 adds the allauth JWT authentication class.
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticatedOrReadOnly"],
    "EXCEPTION_HANDLER": "apps.core.exceptions.api_exception_handler",
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.CursorPagination",
    "PAGE_SIZE": 20,
    # ClientIPMiddleware already put the real client address in REMOTE_ADDR.
    "NUM_PROXIES": 0,
    # Views opt in with throttle_classes + throttle_scope (ARCHITECTURE §3).
    "DEFAULT_THROTTLE_RATES": {
        "post_create": "30/hour",
        "comment": "60/hour",
        "like": "300/hour",
        "follow": "100/hour",
        "report": "10/hour",
        "appeal": "5/day",
        "repost": "100/hour",
        "bookmark": "300/hour",
        "avatar_upload": "5/day",
        "username_check": "30/min",
    },
}

# ---------- Production security (HTTPS is terminated by Render's proxy) ----------
# Render's health check uses plain HTTP, so the shallow endpoint is exempt from the redirect.
SECURE_REDIRECT_EXEMPT = [r"^api/health/$"]
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    # W021 (HSTS preload) is silenced on purpose: preload needs the registrable domain
    # (onrender.com), which we don't own.
    SILENCED_SYSTEM_CHECKS = ["security.W021"]

# ---------- Logging: stdout only; never request headers or bodies, never SQL parameters ----------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"plain": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"}},
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
            "formatter": "plain",
        }
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {"django.db.backends": {"level": "WARNING"}},
}

# ---------- Sentry (only when a DSN is set) ----------
SENTRY_DSN = env.str("SENTRY_DSN", default="")
if SENTRY_DSN:
    init_sentry(
        dsn=SENTRY_DSN,
        environment=env.str("SENTRY_ENVIRONMENT", default="local"),
        traces_sample_rate=env.float("SENTRY_TRACES_SAMPLE_RATE", default=0.0),
    )
