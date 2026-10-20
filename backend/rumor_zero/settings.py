"""Django settings for Rumor Zero. Everything comes from the environment (django-environ)."""

from pathlib import Path

import environ
from django.core.exceptions import ImproperlyConfigured

from apps.core import platform_defaults
from rumor_zero.env_helpers import (
    bare_origin,
    cache_config,
    check_jwt_signing_key,
    email_config,
    flag,
    google_client_id,
    int_in_range,
    load_env_file,
    pipeline_config,
    require,
)
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

# ---------- Frontend origin and auth cookies (ARCHITECTURE §7) ----------
# Email links, the Origin check on /api/auth/ and HEADLESS_FRONTEND_URLS all use it.
FRONTEND_ORIGIN = bare_origin(
    "FRONTEND_ORIGIN", require(env, "FRONTEND_ORIGIN"), https_only=not DEBUG
)
AUTH_COOKIE_SECURE = env.bool("AUTH_COOKIE_SECURE", default=True)
if not DEBUG and not AUTH_COOKIE_SECURE:
    raise ImproperlyConfigured("AUTH_COOKIE_SECURE must be True when DJANGO_DEBUG is False")

JWT_SIGNING_KEY = require(env, "JWT_SIGNING_KEY")
check_jwt_signing_key(JWT_SIGNING_KEY, SECRET_KEY)
JWT_ACCESS_TOKEN_MINUTES = int_in_range(env, "JWT_ACCESS_TOKEN_MINUTES", 15, 1, 60)
JWT_REFRESH_TOKEN_DAYS = int_in_range(env, "JWT_REFRESH_TOKEN_DAYS", 14, 1, 90)
# The rz_refresh cookie's Max-Age and the token session's lifetime.
REFRESH_TOKEN_SECONDS = JWT_REFRESH_TOKEN_DAYS * 86400

TURNSTILE_SECRET_KEY = require(env, "TURNSTILE_SECRET_KEY")

# ---------- Apps and middleware ----------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "rest_framework",
    "allauth",
    "allauth.account",
    "allauth.headless",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "anymail",
    "apps.core",
    "apps.accounts",
    "apps.posts",
    "apps.social",
    "apps.reports",
    "apps.pipeline",
    "apps.moderation",
    "apps.reputation",
    "apps.notifications",
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
    "allauth.account.middleware.AccountMiddleware",
    # CSRF guard, endpoint allow-list, Turnstile and the refresh cookie for /api/auth/ only.
    "apps.accounts.middleware.AuthApiMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# allauth's backend alone: it also serves the Django Admin login (by email). Adding ModelBackend
# would hash a wrong password twice (Argon2 uses 100 MiB per hash).
AUTHENTICATION_BACKENDS = ["allauth.account.auth_backends.AuthenticationBackend"]

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

# Seconds the first page of a user's Following feed stays cached (ARCHITECTURE §3, §9). 0 turns the
# cache off. Not a PlatformSettings value: it is read here, not edited in Django Admin.
FEED_CACHE_SECONDS = int_in_range(env, "FEED_CACHE_SECONDS", 30, 0, 300)

# ---------- Fact-check pipeline (ARCHITECTURE §6; Part 9) ----------
# stub = the built-in deterministic fake; http = a real pipeline at PIPELINE_URL (Bearer
# PIPELINE_API_KEY). Running the stub in production is a launch decision for Part 17 (§6).
PIPELINE_BACKEND, PIPELINE_URL, PIPELINE_API_KEY = pipeline_config(env)
# Check a new fact post in a background thread right after it commits (the fast path). The hourly
# tick and `manage.py process_pending` pick up anything it misses. Tests turn it off.
PIPELINE_INLINE_KICK = flag(env, "PIPELINE_INLINE_KICK", default=True)

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
    # Bearer access tokens from allauth's JWT strategy; a deleted or inactive user gets 401.
    "DEFAULT_AUTHENTICATION_CLASSES": ["apps.accounts.authentication.JWTAuthentication"],
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
        "status_poll": "120/min",
        # Counted per client IP, signed in or not (apps.core.throttles).
        "search": "60/min",
        # The list, the unread count and mark-read, per signed-in user (a tab polls 2 a minute).
        "notifications": "120/min",
        # Settings (Part 14), per signed-in user. An Argon2 hash costs about 100 MiB, so the paths
        # that verify or set a password stay throttled.
        "profile_update": "30/hour",
        "password_change": "10/hour",
        "data_export": "10/hour",
        "account_delete": "10/hour",
    },
}

# ---------- Authentication: django-allauth headless, JWT strategy (ARCHITECTURE §7) ----------
ACCOUNT_ADAPTER = "apps.accounts.adapter.AccountAdapter"
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "username*", "password1*"]
ACCOUNT_EMAIL_VERIFICATION = "optional"
ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS = 1
ACCOUNT_LOGIN_ON_PASSWORD_RESET = True
ACCOUNT_PRESERVE_USERNAME_CASING = False
ACCOUNT_EMAIL_SUBJECT_PREFIX = "[Rumor Zero] "
# Keyed on REMOTE_ADDR, which ClientIPMiddleware sets; a "key" is the email, so it is also per
# account. allauth keeps one history per action and "per" type, so a rate list must never repeat a
# "per" type: "1/60s/key,10/1d/key" would let the minute rate prune what the day rate needs. The
# daily caps are therefore separate actions (`*_daily`) that our own code consumes.
ACCOUNT_RATE_LIMITS = {
    "login": "30/m/ip",
    "login_failed": "10/m/ip,5/300s/key",
    "signup": "20/m/ip",
    # Verification emails: 1 per 60 s per address, plus a daily cap (resend service).
    "confirm_email": "1/60s/key",
    "confirm_email_daily": "10/1d/key",
    # Reset requests: allauth's own per-minute limits, plus daily caps (AuthApiMiddleware).
    "reset_password": "20/m/ip,5/m/key",
    "reset_password_daily": "50/1d/ip,10/1d/key",
    "reset_password_from_key": "20/m/ip",
}
# No email to unknown addresses, and every answer stays identical (no account enumeration).
ACCOUNT_EMAIL_UNKNOWN_ACCOUNTS = False
ACCOUNT_PREVENT_ENUMERATION = True
# Django's default is 3 days; the reset page says "Links expire in 24 hours".
PASSWORD_RESET_TIMEOUT = 24 * 3600
ALLAUTH_TRUSTED_PROXY_COUNT = 0

HEADLESS_ONLY = True
HEADLESS_CLIENTS = ("app",)
HEADLESS_TOKEN_STRATEGY = "apps.accounts.tokens.RumorZeroJWTTokenStrategy"
HEADLESS_JWT_ALGORITHM = "HS256"
HEADLESS_JWT_PRIVATE_KEY = JWT_SIGNING_KEY
HEADLESS_JWT_ACCESS_TOKEN_EXPIRES_IN = JWT_ACCESS_TOKEN_MINUTES * 60
HEADLESS_JWT_REFRESH_TOKEN_EXPIRES_IN = REFRESH_TOKEN_SECONDS
HEADLESS_JWT_ROTATE_REFRESH_TOKEN = True
# Access tokens are checked by signature and expiry only, so they outlive a logout by ≤ 15 min.
HEADLESS_JWT_STATEFUL_VALIDATION_ENABLED = False
# Headless-only mode refuses to send the verification email without these. The pages are
# /verify-email/<key>, /reset-password/<key> and /forgot-password (Part 2).
HEADLESS_FRONTEND_URLS = {
    "account_confirm_email": f"{FRONTEND_ORIGIN}/verify-email/{{key}}",
    "account_reset_password_from_key": f"{FRONTEND_ORIGIN}/reset-password/{{key}}",
    "account_reset_password": f"{FRONTEND_ORIGIN}/forgot-password",
    "account_signup": f"{FRONTEND_ORIGIN}/signup",
}
# ---------- Continue with Google (ARCHITECTURE §7; Part 3) ----------
# Blank disables it: the provider-token endpoint answers 404 and the frontend hides the button.
# A client ID is public, and the ID-token flow needs no secret, so none is configured.
GOOGLE_OAUTH_CLIENT_ID = google_client_id(env)
SOCIALACCOUNT_ADAPTER = "apps.accounts.adapter.SocialAccountAdapter"
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "APPS": (
            [{"client_id": GOOGLE_OAUTH_CLIENT_ID, "secret": "", "key": ""}]
            if GOOGLE_OAUTH_CLIENT_ID
            else []
        ),
        # Use Google's own `email_verified` claim; never force it on.
        "VERIFIED_EMAIL": False,
    }
}
# A Google sign-in with an address that matches an existing account links to it, after our
# SocialAccountAdapter.pre_social_login refuses staff, inactive and non-authoritative matches.
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True
# A pending social sign-up needs X-Session-Token, which AuthApiMiddleware strips: never pend.
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_STORE_TOKENS = False
# Each sign-in fetches Google's signing certificates (allauth has no cache for them).
SOCIALACCOUNT_REQUESTS_TIMEOUT = 5

# The database session engine (Django's default) stays: refresh locks the session row, and logout
# deletes it.
SESSION_ENGINE = "django.contrib.sessions.backends.db"

# ---------- Email (console | brevo | file) ----------
EMAIL_PROVIDER = env.str("EMAIL_PROVIDER", default="console").strip()
if not DEBUG and EMAIL_PROVIDER != "brevo":
    # console and file would put verification links in the logs or on disk.
    raise ImproperlyConfigured("EMAIL_PROVIDER must be brevo when DJANGO_DEBUG is False")
DEFAULT_FROM_EMAIL = env.str("DEFAULT_FROM_EMAIL", default="Rumor Zero <no-reply@example.com>")
EMAIL_BACKEND, EMAIL_FILE_PATH, ANYMAIL = email_config(
    EMAIL_PROVIDER, base_dir=BASE_DIR, brevo_api_key=env.str("BREVO_API_KEY", default="")
)

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
