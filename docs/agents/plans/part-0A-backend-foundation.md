# Plan: Part 0A, Backend foundation

- **Status:** IMPLEMENTED 2026-09-30 by Claude (Sonnet 5.5). Deviations are listed under Part 0A in
  `task.md`. The steps below are kept as the record of what was approved.
- **Drafted:** 2026-09-30 by Claude (Opus 5.5). **Approved:** 2026-09-30 by the user (Sanjoyte).
  **Implement with:** Sonnet 5.5 · medium (task.md).
- **Part:** 0A (task.md). **Depends on:** SETUP.md Part A + ENV_GUIDE §1.1–1.4. These aren't task.md
  parts, so there's no status to check. They were verified on this machine (read-only, 2026-09-30):
  Python 3.13.15 (`py -3.13`), Docker engine 29.7.2 running, Compose v5.4.0, `RemoteSigned`,
  `backend/.env` present (not read), and ports 5432/6379/8000 free. Every task.md part is `[ ]`;
  0A needs none of them. Git tree clean at `c25d479`.

## Context

Nothing is scaffolded yet. 0A creates the Django monolith the other backend parts build on. It is
the step that's hardest to change later: the custom User model must exist before the first
`migrate`, and the settings layout, error shape, pagination shape and client-IP trust are used by
every later part. Outcome: a running Django 5.2 project with env-driven settings, the final
`accounts.User`, health endpoints, shared DRF plumbing, the PlatformSettings singleton, local
Postgres 18 + Redis 8, and green ruff/pytest/migration checks.

Package pins re-checked on PyPI today. All are still the SETUP B1/B2 versions: Django 5.2.17,
DRF 3.18.1, django-allauth 65.19.5, argon2-cffi 25.1.0, psycopg 3.3.6, django-environ 0.14.0,
redis 8.1.0, whitenoise 6.12.0, gunicorn 26.2.0, django-anymail 15.2, sentry-sdk 2.71.0 (so the
MEMORY scrubbing facts still hold), pytest 9.1.1, pytest-django 4.14.0, pytest-cov 7.1.0,
factory-boy 3.3.3, ruff 0.16.9. Verified from source: Django 5.2.17's `RedisCache` passes `OPTIONS`
to `ConnectionPool.from_url`, and redis-py 8.1.0 accepts `protocol` and still has `DefaultParser`.
django-environ's missing-variable error names only the variable, and `read_env` never overwrites
process env.

## Decisions

**User decisions (2026-09-30):**
1. **Admin login by email.** `USERNAME_FIELD = "email"`, `REQUIRED_FIELDS = ["username"]`.
   `createsuperuser` asks for Email, then Username and Password. `get_by_natural_key` lowercases
   its input, so the admin login ignores case.
2. **Reserved usernames: exact match**, case-insensitive, after lowercasing. The list lives in
   `apps/accounts/validators.py` as `RESERVED_USERNAMES`:
   - Routes and system: admin administrator api auth login logout signin signout signup register
     settings account accounts home feed search explore notifications bookmarks messages profile
     user users post posts static media brand dev health internal privacy terms about help
     support contact status security abuse legal www mail email noreply no_reply postmaster
     webmaster hostmaster root system null undefined none anonymous unknown deleted removed
   - Staff and brand: mod mods moderator moderators moderation senior_moderator staff team
     official rumorzero rumor_zero factcheck fact_check factchecker fact_checker
   - Labels: verified false true emergency pipeline fact facts opinion

**Planner decisions** (conventional defaults, recorded in the docs during implementation):
- Physical table names stay Django's defaults (`accounts_user`, `core_platformsettings`). The
  ARCHITECTURE §2 headings (`users`, `platform_settings`) are logical names.
- Role → groups is cumulative: `moderator` joins "Moderators"; `senior_moderator` joins
  **both** "Moderators" and "Senior moderators". Part 10 then gives the senior group only the extra
  permissions.
- Username input is lowercased before validation, so "Ada" is stored as "ada" and "ADMIN" is
  rejected as reserved. Email is stripped and fully lowercased. DB checks enforce both.
- Production HSTS: 1 year + `includeSubDomains`, preload off. `security.W021` is silenced with a
  comment: preload needs the registrable domain (`onrender.com`), which we don't own.
  `SECURE_SSL_REDIRECT=True`, with `^api/health/$` exempt so Render/UptimeRobot checks never get a
  301.
- Tests use LocMem cache, plain static storage and the MD5 hasher through an autouse fixture. This
  keeps them hermetic and fast, and they never flush the dev Redis. The Redis config is
  unit-tested as data; real Redis is checked manually through `/api/health/deep/`.
- `requirements.txt` holds everything in SETUP B1 except Pillow (14B). allauth and anymail are
  installed but only configured in Parts 1–2.
- 0A settings read only the variables 0A uses (below). Later parts add their own.

## Files

New, in the repo root: `compose.yaml`.

New, in `backend/`:
- `.python-version`, `requirements.txt`, `requirements-dev.txt`, `pyproject.toml`, `conftest.py`,
  `manage.py`
- `rumor_zero/`: `__init__.py`, `settings.py` (fully rewritten), `urls.py`, `asgi.py`, `wsgi.py`,
  `env_helpers.py`, `sentry.py`
- `apps/__init__.py`
- `apps/accounts/`: `apps.py`, `models.py`, `validators.py`, `admin.py`, `migrations/0001_initial.py`,
  `tests/{__init__,factories,test_models,test_admin}.py`
- `apps/core/`: `apps.py`, `models.py`, `platform_defaults.py`, `services.py`, `middleware.py`,
  `pagination.py`, `exceptions.py`, `views.py`, `urls.py`, `admin.py`,
  `migrations/{0001_initial,0002_seed_platform_settings}.py`,
  `tests/{__init__,test_health,test_middleware,test_platform_settings,test_pagination,test_exceptions,test_sentry,test_settings}.py`
- Delete the unused `startapp` stubs (`views.py`/`tests.py`) where they aren't needed.

Docs changed at the end: `docs/ARCHITECTURE.md` (§1 note, §2 users/conventions/platform_settings),
`docs/STRUCTURE.md` (the new `rumor_zero/` modules), `task.md`, `docs/agents/HANDOFF.md`, and
`docs/agents/MEMORY.md` only for durable discoveries. **No new env vars** are expected, so
`backend/.env.example` and ENV_GUIDE stay unchanged unless implementation adds one (then update both).

## Ordered steps

0. **Pre-flight:** confirm `git status` shows only this plan and HANDOFF (or is clean, if the user
   has committed them). Set the owner to the implementing agent and phase "implementing 0A" in
   HANDOFF. (This plan is already saved here.)
   Optional user check that prints key **names only**, never values:
   `Compare-Object (Select-String backend\.env.example '^([A-Z_]+)=' | % {$_.Matches.Groups[1].Value}) (Select-String backend\.env '^([A-Z_]+)=' | % {$_.Matches.Groups[1].Value})`
1. **compose.yaml** (`name: rumor-zero`):
   - `postgres:18` with user, password and db `rumor_zero`, volume `pgdata:/var/lib/postgresql`,
     port `127.0.0.1:5432:5432`, healthcheck `pg_isready -U rumor_zero -d rumor_zero`
   - `redis:8-alpine` on `127.0.0.1:6379:6379`, healthcheck `redis-cli ping`
   - Ports are bound to localhost, so the weak local password isn't exposed on the LAN.
   - Then `docker compose up -d` and `docker compose ps`: both healthy.
2. **Tooling files:**
   - `.python-version` = `3.13`
   - `requirements.txt`: exact `==` pins, with extras `django-allauth[headless,socialaccount]`,
     `psycopg[binary]`, `django-anymail[brevo]` and `sentry-sdk[django]`
   - `requirements-dev.txt`: `-r requirements.txt` + the B2 tools
   - `pyproject.toml`:
     - ruff: `line-length=100`, `target-version="py313"`, lint `select=["E","W","F","I","B","UP","DJ","C4","SIM"]`,
       isort `known-first-party=["apps","rumor_zero"]`, `per-file-ignores` `"**/migrations/*.py"=["E501"]`
       (pre-0A follow-up)
     - pytest: `DJANGO_SETTINGS_MODULE="rumor_zero.settings"`, `testpaths=["apps"]`, `addopts="-ra --strict-markers"`
     - coverage: source `apps`, `rumor_zero`; omit migrations and tests
3. **venv + install:** `py -3.13 -m venv .venv`, then `.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt`.
   Call `.venv\Scripts\python.exe` / `ruff.exe` directly; activation doesn't persist between tool calls.
4. **Scaffold** (in `backend/`):
   - `python -m django startproject rumor_zero .`
   - create `apps/__init__.py` and the empty `apps\core` and `apps\accounts` folders
   - `python manage.py startapp core apps/core` and `… accounts apps/accounts`
   - set `name = "apps.<name>"` in each `apps.py`
   - `ruff check --fix . ; ruff format .`
   - ⚠ **Do not run `migrate` until step 8.**
5. **Settings** (`rumor_zero/settings.py`, full rewrite; the generated `django-insecure-…` key
   disappears):
   - Env:
     - `env_helpers.load_env_file(BASE_DIR / ".env")` reads the file only if it exists; process env wins.
     - `require(env, name)` raises `ImproperlyConfigured("Set the <NAME> environment variable (see backend/.env.example)")`
       when a variable is missing **or empty**, and never includes its value.
     - Required: `DJANGO_SECRET_KEY`, `DATABASE_URL`, `PROXY_SHARED_SECRET`, `INTERNAL_CRON_SECRET`.
     - Optional, with defaults:
       - `DJANGO_DEBUG=False`, `DJANGO_ALLOWED_HOSTS=[]`, `DJANGO_CSRF_TRUSTED_ORIGINS=[]`
       - `ADMIN_URL_PATH="admin/"`, validated: must end with `/`, must not start with `/`
       - `REDIS_URL=""`, `SENTRY_DSN=""`, `SENTRY_ENVIRONMENT="local"`, `SENTRY_TRACES_SAMPLE_RATE=0.0`
       - the 11 PlatformSettings seed variables
   - Database: `DATABASES` from `DATABASE_URL`, plus `CONN_MAX_AGE=60` and `CONN_HEALTH_CHECKS=True`.
     `DEFAULT_AUTO_FIELD` = BigAutoField (for later bigint tables).
   - Cache: `env_helpers.cache_config(redis_url)` gives `RedisCache` with
     `OPTIONS={"protocol": 2, "socket_connect_timeout": 5, "socket_timeout": 5}`, or `LocMemCache`
     when the URL is empty.
   - Passwords: `PASSWORD_HASHERS` = Argon2, PBKDF2, PBKDF2SHA1. Django's default validators.
   - Apps and middleware:
     - `INSTALLED_APPS`: `whitenoise.runserver_nostatic` before `staticfiles`, `rest_framework`,
       `apps.core`, `apps.accounts`. `AUTH_USER_MODEL="accounts.User"`.
     - `MIDDLEWARE`: `apps.core.middleware.ClientIPMiddleware` **first**, then Security, WhiteNoise,
       Session, Common, Csrf, Auth, Messages, XFrame.
   - Static files: `STATIC_ROOT=BASE_DIR/"staticfiles"`; `STORAGES["staticfiles"]` =
     `whitenoise.storage.CompressedManifestStaticFilesStorage`.
   - Templates: `DIRS=[BASE_DIR/"templates"]` (used from Parts 2/10). UTC, `USE_TZ=True`.
   - `REST_FRAMEWORK`:
     - JSON-only renderer and parser; `TEST_REQUEST_DEFAULT_FORMAT="json"`
     - `DEFAULT_AUTHENTICATION_CLASSES=[]` (Part 1 adds allauth JWT);
       `DEFAULT_PERMISSION_CLASSES=[IsAuthenticatedOrReadOnly]`
     - `EXCEPTION_HANDLER="apps.core.exceptions.api_exception_handler"`
     - `DEFAULT_PAGINATION_CLASS="apps.core.pagination.CursorPagination"`, `PAGE_SIZE=20`
     - `NUM_PROXIES=0`
     - `DEFAULT_THROTTLE_RATES` with all 10 scopes from ARCHITECTURE §3 (`post_create` "30/hour" …
       `username_check` "30/min"). No default throttle classes.
   - When not DEBUG:
     - `SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO","https")`, `SECURE_SSL_REDIRECT=True`
       (+ exempt `^api/health/$`)
     - HSTS 31536000 + `includeSubDomains`
     - `SESSION_COOKIE_SECURE` and `CSRF_COOKIE_SECURE`
     - `SILENCED_SYSTEM_CHECKS=["security.W021"]` with a comment
   - `LOGGING`: console → stdout, INFO. `django.db.backends` at WARNING, so SQL params are never
     logged. No request headers or bodies are logged.
   - Custom settings: `PROXY_SHARED_SECRET`, `INTERNAL_CRON_SECRET`,
     `PLATFORM_SETTINGS_SEED = platform_defaults.read_seed(env)`.
   - Sentry: `rumor_zero/sentry.py` defines `sentry_options(dsn, environment, traces_sample_rate)`
     and `init_sentry(...)`, called only if `SENTRY_DSN` is set. The options are:
     - `integrations=[DjangoIntegration()]`
     - `send_default_pii=False`, `max_request_body_size="never"`, `include_local_variables=False`
     - `event_scrubber=EventScrubber(denylist=DEFAULT_DENYLIST + ["x-rz-proxy-secret","x-rz-cron-secret","x-rz-client-ip"])`
     - `environment`, `traces_sample_rate`
   - Variables holding secrets are named `secret`/`token` (exact DEFAULT_DENYLIST keys) where
     practical (pre-0A follow-up).
   - `urls.py`: `path("api/", include("apps.core.urls"))` and `path(settings.ADMIN_URL_PATH, admin.site.urls)`.
6. **accounts:**
   - `validators.py`:
     - `normalize_username` (NFKC, strip, lower); `normalize_email` (strip, lower)
     - `validate_username`: lowercases, then checks the regex `^[a-z0-9_]{3,30}$` and
       `RESERVED_USERNAMES` ("This username is reserved.")
     - Reused by Part 1's availability endpoint.
   - `models.py`:
     - `Role(TextChoices)` = user / moderator / senior_moderator, plus `ROLE_GROUPS`.
     - `UserManager(BaseUserManager)`: `create_user(email, username, password=None, **extra)`,
       `create_superuser` (sets `is_superuser=True` and leaves `role=user`), and
       `get_by_natural_key` (lowercased).
     - `User(AbstractBaseUser, PermissionsMixin)` with exactly the ARCHITECTURE §2 fields:
       - `id` UUID4 PK
       - `username` CharField(30, unique, `validators=[validate_username]`)
       - `email` EmailField(254, unique)
       - `display_name` (50, blank), `bio` (280, blank)
       - `role` (default user), `is_email_verified`, `is_active`, `is_staff`
       - `avatar_version` CharField(16, null) with `# noqa: DJ001` (null means no photo, per §2)
       - `avatar_uploads_blocked`
       - `reputation_score` SmallIntegerField, default 50
       - `reputation_sample` IntegerField, default 0
       - `emergency_blocked_until` (null)
       - `created_at` (default `timezone.now`, db_index)
     - Settings on `User`: `USERNAME_FIELD="email"`, `EMAIL_FIELD="email"`,
       `REQUIRED_FIELDS=["username"]`, `__str__`→username.
     - `Meta.constraints` (Django 5.2 `condition=`):
       - role in values
       - `reputation_score` 0–100
       - `reputation_sample >= 0`
       - `username ~ '^[a-z0-9_]{3,30}$'`
       - `email = LOWER(email)`
     - `clean()` and `save()` normalise username and email.
     - `save()` sets `is_staff = is_superuser or role != user` on every save, and then (after
       `super().save()`) syncs the groups (`get_or_create` by name, `groups.set`). The group sync
       runs only on create or when `role`/`is_superuser` changed since load (the original values are
       tracked in `from_db`). If `update_fields` is given without those fields, it's skipped, so
       login's `last_login` save stays a single query. If `update_fields` includes `role`, add
       `is_staff`.
   - `admin.py`: `UserAdmin(BaseUserAdmin)` with custom change and creation forms
     (email, username, password):
     - list columns: username, email, role, is_staff, is_superuser, is_email_verified, is_active,
       created_at; filters, search on username/email, ordering `-created_at`,
       `filter_horizontal=()`
     - **Neither `groups` nor `is_staff` is an editable form field**, otherwise the admin's
       `save_related` would overwrite the role sync. They're read-only, and so are
       `is_email_verified`, `reputation_*`, `avatar_*`, `emergency_blocked_until`, `last_login` and
       `created_at` (their dedicated, logged actions arrive in 2/10/11C/14B).
     - Editable: email, username, display_name, bio, role, is_active, is_superuser.
       Seniors-only editing comes in Part 10.
   - `makemigrations accounts`, then ruff fix + format.
7. **core:**
   - `platform_defaults.py`: `FIELDS` maps field → (ENV_NAME, default, min, max) for the 11 values
     in ARCHITECTURE §3. `read_seed(env)` returns a dict: a missing variable → its default; an
     invalid or out-of-range value → `ImproperlyConfigured` naming the variable. Model defaults
     come from the same table.
   - `models.py`: `PlatformSettings`:
     - `id` PositiveSmallIntegerField PK, default 1, with a check `id=1`
     - the 11 fields (PositiveSmallIntegerField): `report_threshold`, `report_window_hours`,
       `report_min_account_age_hours`, `confidence_threshold`, `fact_posts_per_day`,
       `emergency_duration_hours`, `emergency_posts_per_day`, `emergency_min_account_age_days`,
       `emergency_min_reputation`, `emergency_report_threshold`, `emergency_false_cooldown_days`
     - `updated_by` FK SET_NULL null `related_name="+"`, `updated_at` auto_now
     - Checks:
       - ≥ 1 for `report_threshold`, `report_window_hours`, `emergency_duration_hours`,
         `emergency_report_threshold`
       - 0–100 for `confidence_threshold`, `emergency_min_reputation`
       - the others ≥ 0 (a per-day value of 0 works as a kill switch)
     - Min/Max validators mirror the checks.
     - `save()` deletes the cache key now and again on commit.
   - `services.py`: `get_platform_settings()` uses a 60 s cache (`core:platform_settings:v1`).
     On a miss it runs `get_or_create(pk=1, defaults=settings.PLATFORM_SETTINGS_SEED)`, which also
     heals the row after a transactional-test flush.
   - `middleware.py`: `ClientIPMiddleware`:
     - pops `HTTP_X_RZ_PROXY_SECRET` and `HTTP_X_RZ_CLIENT_IP` from `request.META`, so no later code,
       log or error report can see them
     - if the popped secret `hmac.compare_digest`-matches `settings.PROXY_SHARED_SECRET` and the
       client IP parses with `ipaddress`, sets `REMOTE_ADDR` to it
     - otherwise uses the right-most valid `X-Forwarded-For` entry; otherwise leaves `REMOTE_ADDR`
   - `pagination.py`: `CursorPagination`:
     - page_size 20, `page_size_query_param="page_size"`, `max_page_size=50`, ordering `-created_at`
     - `encode_cursor` returns the bare token, not a URL
     - response `{"results": [...], "next_cursor": token|null}`
   - `exceptions.py`: `api_exception_handler` wraps DRF's handler:
     - validation errors keep `{"field": ["msg"]}` (a bare list becomes `{"non_field_errors": [...]}`)
     - other errors become `{"detail": str, "code": exc.detail.code or exc.default_code}`
     - 429 keeps DRF's `Retry-After`
     - unhandled exceptions stay None (Django's 500)
   - `views.py` + `urls.py`:
     - `health/`: DRF APIView, no authentication, permission or throttle classes, `never_cache`,
       returns `{"status":"ok"}`, touches neither the DB nor the session
     - `health/deep/`:
       - 403 (`permission_denied`) unless `X-RZ-Cron-Secret` matches `INTERNAL_CRON_SECRET`
         (constant time)
       - runs `SELECT 1` and a set/get/delete of a unique cache key
       - 200 `{"status":"ok","database":"ok","cache":"ok"}`, or 503 with per-component
         `"error"`, logging only the exception class name
   - `admin.py`: `PlatformSettingsAdmin`: no add once the row exists, no delete, `updated_by`
     set in `save_model`, audit fields read-only. Seniors-only and change auditing come in Part 10.
   - Migrations: `makemigrations core` → `0001_initial`, then `makemigrations core --empty -n seed_platform_settings`.
     The RunPython `get_or_create(pk=1, …)` uses the historical model and filters the seed keys to
     that model's fields, so a future field can't break a fresh migrate. Reverse is a no-op.
     Then ruff fix + format.
8. **Migrate on the empty DB:** `python manage.py migrate` (first ever run), then `makemigrations --check --dry-run`.
9. **Tests** (below). Root `conftest.py`:
   - an autouse `_hermetic` fixture (via `settings`): LocMem cache + `cache.clear()`,
     `StaticFilesStorage`, MD5 hasher
   - `api_client` and `user` fixtures; `UserFactory` in `apps/accounts/tests/factories.py`
   - Every test folder gets an `__init__.py` (pre-0A follow-up).
   - Note: pytest-django loads settings **before** `conftest.py`, so tests set values through
     `settings`/`monkeypatch`, never by injecting env in conftest.
10. **Validate** (commands below). Then update the docs: ARCHITECTURE §2 (USERNAME_FIELD, the
    reserved rule, the cumulative groups, the DB checks, physical table names, PlatformSettings
    ranges) and §1 (the middleware strips the X-RZ headers); STRUCTURE; task.md (tick the criteria,
    `[x] Done (date)` in both places, deviations); HANDOFF (commands and results, next action);
    MEMORY (only new durable facts). Then stop.

## Required tests (pytest, real Postgres)

- **accounts/test_models:**
  - email/username normalisation, including NFKC
  - format rejections: short, long, hyphen, space, non-ASCII
  - every reserved word rejected in any case, while "ada_admin" is allowed
  - role sync: user → moderator → senior → user, checking the groups and `is_staff`
  - the superuser keeps `is_staff` with `role=user` and across role changes
  - a `last_login`-only save is 1 query
  - DB checks: `reputation_score` −1/101, uppercase username/email via `.update()` →
    `IntegrityError`; the default score is 50
  - `get_by_natural_key` ignores case
- **accounts/test_admin:**
  - `call_command("createsuperuser", interactive=False, email=…, username=…)` with
    `DJANGO_SUPERUSER_PASSWORD` monkeypatched, then `client.login(username=<email>, …)`, then
    `GET reverse("admin:index")` returns 200
  - changing the role through the admin change form keeps the groups synced
- **core/test_health:**
  - `/api/health/` returns `{"status":"ok"}` with `django_assert_num_queries(0)`, also with a
    logged-in session cookie
  - deep: missing or wrong secret → 403 with `code`; correct → 200 and exactly 1 query; a broken
    cache → 503
- **core/test_middleware:** secret ok → IP used; wrong or missing → right-most XFF, or else
  `REMOTE_ADDR`; ok secret + invalid IP → fallback; both headers removed from `META`.
- **core/test_platform_settings:**
  - the migrated row exists
  - `read_seed` with a monkeypatched env: overrides applied, missing `EMERGENCY_*` → defaults,
    invalid value → error naming the variable
  - the accessor: second call 0 queries, `save()` invalidates, a deleted row is recreated
  - DB range checks
- **core/test_pagination:** 25 users → 20 + a `next_cursor` token (no `http`, no `?`) → 5 + `null`;
  `page_size` capped at 50.
- **core/test_exceptions:** `NotFound`, `PermissionDenied(code="email_unverified")`, `Throttled`
  (+ `Retry-After`), field `ValidationError` unchanged, bare → `non_field_errors`.
- **core/test_sentry:** monkeypatch `sentry_sdk.init` and call `init_sentry(dsn="https://public@example.invalid/1", …)`.
  Assert the options (pii off, body `never`, locals off, the denylist includes the three headers).
  Then run the captured `event_scrubber` on a Sentry-shaped event with `X-Rz-Proxy-Secret`,
  `X-Rz-Cron-Secret`, `X-Rz-Client-Ip` and `Accept` headers: the first three are filtered and
  `Accept` is kept. No network.
- **core/test_settings:**
  - Subprocess: with production-like fake env (DEBUG False, a random 50-char key, allowed hosts,
    https CSRF origins), `manage.py check --deploy --fail-level WARNING` exits 0. With the same env,
    a probe prints the security flags: proxy SSL header, HSTS ≥ 1 y, secure cookies, SSL redirect.
    Every variable the settings read is passed explicitly, so `.env` can't influence the result.
  - `DJANGO_SECRET_KEY=""` → non-zero exit; stderr names the variable and contains none of the
    other fake secret values.
  - Pure: `cache_config` (Redis + protocol 2 / LocMem); Argon2 first in the project settings
    module and its hash starts with `argon2$argon2id$`; DRF defaults (JSON-only, `NUM_PROXIES=0`,
    all 10 throttle scopes parse).

## Validation (in `backend/`, PowerShell, `.venv\Scripts\…` executables)

```powershell
docker compose up -d ; docker compose ps          # repo root: both "healthy"
.\.venv\Scripts\python.exe manage.py migrate      # empty DB, first run
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\ruff.exe check . ; .\.venv\Scripts\ruff.exe format --check .
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m pytest --cov=apps --cov=rumor_zero
.\.venv\Scripts\python.exe manage.py check
git grep -n "django-insecure" ; git check-ignore backend/.env   # expect: no match ; path printed
```

Manual (user; optional agent smoke with `runserver`):
- `createsuperuser` → log in at http://localhost:8000/admin/ with the email
- `/api/health/` → 200
- `/api/health/deep/` with the header → 200, which proves Postgres and the real Redis

## Non-goals

- allauth, JWT, email or Turnstile settings (Parts 1–3)
- the seniors-only admin, Groups permissions and settings-change auditing (Part 10)
- any frontend or CI (0B/0C)
- `render.yaml` (17)
- no other `apps/*`

## Stop conditions

- Never read or print `backend/.env`. If Django reports "Set the X environment variable", stop and
  tell the user the **name**.
- If `migrate` ran before `accounts.User` existed, stop and ask the user before
  `docker compose down -v` (it destroys the local DB volume).
- If a pinned package fails to install on Windows/Python 3.13, or a container isn't healthy, stop
  and report it.
- No git state changes; `design/` untouched; nothing outside 0A beyond the doc updates above.

## Follow-ups (not in 0A)

- Part 10: log old → new values for every PlatformSettings change ("every change is logged",
  §2); the Groups permission data migration can rely on the cumulative mapping.
- Part 1/2: a CLI superuser has `is_email_verified=False` and no allauth `EmailAddress`, so the
  app treats it as unverified; decide whether it needs app writes.
- Part 17:
  - a deploy check that fails when `PROXY_SHARED_SECRET`/`INTERNAL_CRON_SECRET` is short or a
    `local-dev-only` placeholder
  - verify the Host header of Render's health check against `ALLOWED_HOSTS`
