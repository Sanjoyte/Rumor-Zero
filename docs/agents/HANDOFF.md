# Rumor Zero: live handoff

Update this file at meaningful checkpoints and before switching between Claude Code and Codex.
Keep it concise and factual. The incoming agent must verify it against the current files and
read-only git output.

## Active work

- **Part:** 0B (Frontend foundation & design system). Part 0A is done (2026-09-30).
- **Owner:** Claude (Sonnet 5.5)
- **Phase:** plan approved by the user 2026-10-01; implementation starting
- **Approved plan:** `docs/agents/plans/part-0B-frontend-foundation.md`
- **Last updated:** 2026-10-01 by Claude (Sonnet 5.5), Part 0B start

## Completed checkpoints

- Dual-agent setup (`dbe02e6`) and the pre-0A correction pass (`c25d479`), both committed by the user.
- 2026-09-30 (Claude, Opus 5.5): Part 0A planning; the plan was committed by the user.
- 2026-09-30 (Claude, Sonnet 5.5): **Part 0A implemented.**
  - Local services: root `compose.yaml` (Postgres 18 + Redis 8, healthchecks, loopback ports).
  - `backend/`: venv, pinned `requirements*.txt`, `pyproject.toml`, `conftest.py`, the `rumor_zero`
    project (env-driven `settings.py`, `env_helpers.py`, `sentry.py`, `urls.py`) and two apps:
    - `accounts`: custom `User` (email login, UUID, role → groups/`is_staff` sync, DB checks),
      `validators.py`, admin, `0001_initial`.
    - `core`: `PlatformSettings` singleton + cached accessor, `ClientIPMiddleware`, cursor
      pagination, exception handler with `code`, health + deep health, admin, `0001_initial`,
      `0002_seed_platform_settings`.
  - Docs updated: ARCHITECTURE §1/§2, STRUCTURE, `task.md` (both status locations + deviations),
    MEMORY (the `localhost`/IPv6 stall).
  - No new env variables were needed, so `backend/.env.example` and ENV_GUIDE are unchanged.

## Current workspace state

- The tree was clean at the start (the user had committed the plan). Everything below is new and
  uncommitted; nothing pre-existing was modified except the docs listed.
- `backend/.env` was **not read or edited**. Its `DATABASE_URL` host, port and name were checked as
  booleans only (local, 5432, `rumor_zero`); no value was printed.
- The local DB was migrated for the first time (empty DB → `accounts.0001` first). The Docker volume
  `rumor-zero_pgdata` now holds that schema; the containers are running.
- 25 tracked text files may still be CRLF in the working tree (see the earlier note); harmless.

## Validation (all in `backend/`, `.venv\Scripts\…` executables, 2026-09-30)

- Passed: `docker compose up -d` → `docker compose ps`: postgres and redis both `(healthy)`.
- Passed: `python manage.py migrate` on the empty DB (21 migrations, `accounts.0001` before `admin`/`core`);
  a second `migrate` reports "No migrations to apply".
- Passed: `python manage.py makemigrations --check --dry-run` → "No changes detected" (exit 0).
- Passed: `ruff check .` → "All checks passed!"; `ruff format --check .` → "43 files already formatted".
- Passed: `python manage.py check` → no issues.
- Passed: `python -m pytest` → **200 passed** (~5 s, real Postgres, hermetic cache/hasher/static).
- Passed: `python -m pytest --cov=apps --cov=rumor_zero` → 200 passed, total coverage 93%.
- Passed (inside pytest, subprocess with an explicit production-like env): `manage.py check --deploy
  --fail-level WARNING` exits 0; the probe shows the proxy SSL header, SSL redirect with
  `^api/health/$` exempt, HSTS ≥ 1 year with subdomains, and secure session/CSRF cookies.
- Passed (in-process against the real `.env` config, statuses only): `/api/health/` → 200; deep health
  without the secret → 403; with it → 200 `{"status":"ok","database":"ok","cache":"ok"}`, which
  exercised real Postgres and the real Redis (`RedisCache`, protocol 2); the seeded PlatformSettings
  row is present; the admin login page → 200.
- Passed: `git grep "django-insecure"` (outside docs) → no match; `git check-ignore backend/.env` →
  prints the path.
- Not run: a manual interactive `createsuperuser` + browser login (covered by
  `test_createsuperuser_account_can_log_into_the_admin`), and gunicorn (not runnable on Windows).

## Next exact action

1. The user reviews the diff and commits (all git operations are theirs). Optional manual check:
   `cd backend ; .\.venv\Scripts\Activate.ps1 ; python manage.py createsuperuser`, then
   `python manage.py runserver` and log in at http://localhost:8000/admin/ with the **email**.
2. Start a fresh session for the next part in `task.md`'s order. Per the table, Part 0B (frontend)
   depends only on SETUP Part A and has no backend dependency; 0C needs 0A, 0B and 0D.
3. Prompt for planning: `Plan Part 0B from task.md. Do not implement yet.`

## Blockers or user decisions

- None open.

## Follow-ups noted during 0A (not done, per the part's scope)

- Part 10: log old → new values for every PlatformSettings change; seniors-only editing; the senior
  group's extra permissions (the role → groups mapping is cumulative).
- Part 1/2: a CLI superuser has `is_email_verified=False` and no allauth `EmailAddress`; decide
  whether it needs app writes. `DEFAULT_AUTHENTICATION_CLASSES` is `[]` until Part 1, so an
  unauthenticated request currently returns 403 rather than 401.
- Part 17: fail deploys when `PROXY_SHARED_SECRET`/`INTERNAL_CRON_SECRET` is short or a
  `local-dev-only` placeholder; verify Render's health-check Host header against `ALLOWED_HOSTS`;
  `collectstatic` must run in the build (the manifest storage needs it when DEBUG is False).
- Part 0C: CI builds its env file from `backend/.env.example`; the tests read it only through
  process env/`.env`, and `test_settings.py` passes every variable explicitly to its subprocesses.

## Files changed for the current work (uncommitted)

- New: `compose.yaml`; `backend/{.python-version,manage.py,conftest.py,pyproject.toml,requirements.txt,requirements-dev.txt}`;
  `backend/rumor_zero/*` (7 files); `backend/apps/**` (`accounts`, `core`, with migrations and tests).
- Edited docs: `docs/ARCHITECTURE.md`, `docs/STRUCTURE.md`, `docs/agents/HANDOFF.md`,
  `docs/agents/MEMORY.md`, `docs/agents/plans/part-0A-backend-foundation.md`, `task.md`.
- Untracked and ignored (not for commit): `backend/.venv/`, caches, `backend/.coverage`.

## Handoff checklist (outgoing agent)

- [x] Stop editing before the incoming agent starts.
- [x] Record current owner, phase and approved plan.
- [x] Record files changed and any unrelated pre-existing modifications.
- [x] Record every validation command and its exact pass/fail result.
- [x] Record blockers, user decisions and the next exact action.
- [x] Promote only durable, non-duplicated knowledge to `MEMORY.md`.
