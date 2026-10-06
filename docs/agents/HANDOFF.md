# Rumor Zero: live handoff

Update this file at meaningful checkpoints and before switching between Claude Code and Codex.
Keep it concise and factual. The incoming agent must verify it against the current files and
read-only git output.

## Active work

- **Part:** **2 (email verification & password reset)**, planned and approved, **not implemented**.
  Parts 0A, 0B, 0D, 0C and 1 are done; Part 1 CI green (user-reported 2026-10-06).
- **Machine:** the **Linux PC** (Ubuntu/Debian/Mint, bash) from 2026-10-06. `backend/.venv` and
  `frontend/node_modules` exist there.
- **Owner:** none (Claude stopped after saving the plan; implementation starts in a new session)
- **Phase:** plan approved; no code written, no setup commands run, `task.md` untouched.
- **Approved plan:**
  [`docs/agents/plans/part-2-email-verification-reset.md`](plans/part-2-email-verification-reset.md)
  (approved by the user 2026-10-07)
- **Previous plans:** [`chore-linux-machine-switch.md`](plans/chore-linux-machine-switch.md) (done
  2026-10-06), [`part-1-auth-core.md`](plans/part-1-auth-core.md) (done 2026-10-03)
- **Last updated:** 2026-10-07 by Claude (Opus 5.5), Part 2 planning

## Completed checkpoints

- 2026-10-07 (Claude, Opus 5.5): **Part 2 planned and approved** (plan linked above). Started from
  HEAD `353ee19` (the Linux chore, committed by the user), a clean tree in sync with `origin/main`.
  Read-only research only: allauth 65.19.5, Django 5.2 and Next 16.3.8 source, plus a review pass
  against the code. User decisions (2026-10-06):
  - sign-up lands on `/verify-email`;
  - New post is `aria-disabled` until the email is verified;
  - verification emails 1 per 60 s per address, plus 10 resends/day per address; reset requests keep
    allauth's per-minute limits, plus 10/day per address and 50/day per IP;
  - no email to unknown addresses (`ACCOUNT_EMAIL_UNKNOWN_ACCOUNTS = False`).

  Also recorded in the plan: the documented `auth/email/verify/resend` is code-mode only, so resend
  becomes our `POST /api/v1/me/verification-email/`; daily caps need separate allauth actions
  (rates sharing a "per" type share one history); reset links last 24 h.
- 2026-10-06 (Claude, Sonnet 5.5): **Linux machine-switch chore** (docs and comments only; no code,
  config, env or git change). Started from HEAD `d9d1358` (Part 1), a clean tree in sync with
  `origin/main`; CI green (user-reported).
  - **Dual docs, Linux first:** `docs/SETUP.md` (new "Part A (Linux)" with a clone-to-green-tests
    quick start, troubleshooting, A1–A7 for Ubuntu/Debian/Mint, and "Moving to another machine"),
    `docs/ENV_GUIDE.md` (Linux commands beside every PowerShell one, a one-command secret generator
    that prints nothing, new §1.9), `docs/test-command.md` (a bash block above each of the 51 original
    PowerShell blocks: 39 pairs plus 12 "same commands" blocks; the PowerShell blocks are unchanged),
    `AGENTS.md` (Commands block now bash-first, two-machine bullet), header comments of both
    `.env.example` files, and `.gitignore` (+`compose.override.yaml`, the local IPv6 workaround file
    in SETUP; one line beyond the plan).
  - **Left-behind audit:** everything git ignores is regenerable except `backend/.env` and
    `frontend/.env.local`, which hold only local values and are recreated from the examples (ENV_GUIDE
    §1.2 / §1.9). No CRLF in the index (28 tracked files have CRLF only in this Windows working copy),
    no case-only duplicate paths, no shell scripts, every generated brand asset tracked.
  - **Validation:** see "Validation of the Linux clean-room run (2026-10-06)".
- 2026-10-03 (Claude, Opus 5.5): **Part 1 implemented** (committed by the user as `d9d1358`).
  Started from HEAD `349dc96` (the plan + this file, committed by the user), whose workspace matched
  this file's previous state.
  - **Backend** (`backend/apps/accounts/`): `middleware.py` (AuthApiMiddleware: allow-list, CSRF
    guard on every unsafe `/api/auth/` request, header stripping, Turnstile pre-check, refresh-cookie
    injection, secret stripping, JSON bodies, `no-store`), `tokens.py` (row lock + 60 s grace),
    `cookies.py`, `turnstile.py` (stdlib, fails closed), `adapter.py`, `authentication.py`,
    `permissions.py`, `serializers.py`, `views.py` (logout, `/me`, username check), `urls.py`,
    `migrations/0002_verify_superuser_emails.py`, `models.py` (`create_superuser` verified);
    `rumor_zero/{settings,urls,env_helpers}.py` (allauth/headless/email settings, startup guards);
    `conftest.py` (fixed auth values, no network); 11 new test files + `tests/conftest.py`;
    `apps/core/tests/test_settings.py` (new variables, guards, helpers).
  - **Frontend:** `src/lib/auth/{session,auth-api,jwt,session-hint,next-path,route-guard}.ts`,
    `AuthProvider.tsx` (rewritten), `src/lib/turnstile.ts`, `src/lib/api/client.ts` (`token: false`),
    `src/features/auth/` (SignupForm, LoginForm, Turnstile, useUsernameAvailability,
    useRedirectWhenLoggedIn, messages, test-helpers), `src/components/shell/` (UnverifiedBanner,
    loading skeletons, Log out in AccountMenu), `src/app/(app)/layout.tsx` (guard + logout),
    `src/app/(auth)/{login,signup}/page.tsx`, `ui/Avatar.tsx` (initials skip a leading "@"),
    `features/dev/ShellPreview.tsx`, `e2e/auth.spec.ts`, `playwright.config.ts` (`REDIS_URL: ""`),
    `e2e/smoke.spec.ts` (comment), tests next to each file.
  - **Docs and config:** `task.md` (criteria, deviations, both status spots), ARCHITECTURE §0/§2/§3/
    §7 (rewritten)/§9/§10/§12, ANALYSIS c-18 and d, ENV_GUIDE §1.2/§1.3/§1.5/§2.13, STRUCTURE
    markers, MEMORY (allauth gotchas, PowerShell 5.1 JSON quoting, Docker-restart note),
    `docs/test-command.md` (Part 1 section, commands run by the agent), the plan's status line,
    `backend/.env.example` (JWT placeholder 30 → 40 characters, comments), root `.gitignore`
    (`backend/tmp/`).
  - No new dependency and no new env variable. No real env file was edited. `backend/.env` was
    read only through commands that print lengths or a yes/no, never values (it has a 67-character
    `JWT_SIGNING_KEY` different from `DJANGO_SECRET_KEY`, and Cloudflare's always-pass test secret).
  - The local database was migrated (allauth's `account` 0001–0009 and `accounts.0002`), which
    marked the local superuser verified. Test accounts from the checks remain (see test-command
    step 12).
- 2026-10-02 (Claude, Opus 5.5): **Part 1 planned and approved** (`349dc96`). allauth 65.19.5
  behaviour read in the installed source; Turnstile checked against Cloudflare's docs. User
  decisions: CLI superusers count as verified (plus a backfill migration); Turnstile fails closed; a
  non-secret `rz_session` hint cookie.
- 2026-10-01: **CI green, Part 0C done** (`d92f070`; run on `60cfffc`, user-reported). The 0C
  implementation is `6e83866` and the esbuild CI fix `60cfffc`; their validation details are in
  this file's history at `d92f070`.
- Dual-agent setup, the pre-0A correction pass, Parts 0A, 0B and 0D (0D = `b695f09`), the
  multi-source spec change (`bd05636`) and the 0C plan (`90857ec`), all committed by the user.

## Current workspace state

- HEAD is `353ee19` (Linux chore), in sync with `origin/main`, tree clean at the start of planning.
  **Uncommitted** after planning: modified `docs/agents/HANDOFF.md` (this file); new
  `docs/agents/plans/part-2-email-verification-reset.md`. Nothing else.
- No code, config, env file or `task.md` changed. Nothing was started (no servers, no containers).

## Validation of Part 1 (2026-10-03)

- **Backend** (`backend/`, venv, Postgres + Redis up), each exit 0:
  - `python -m pytest` → **440 passed** (was 200); `pytest apps/accounts` → 327 passed; no warnings.
    The same suite also passes with only `backend/.env.example`'s values in the process env (what
    CI uses), as does `manage.py check`.
  - `ruff check .` → "All checks passed!"; `ruff format --check .` → "66 files already formatted".
  - `makemigrations --check --dry-run` → "No changes detected"; `manage.py check` → no issues;
    `check --deploy` passes with a production-like env (`test_settings.py`).
  - The four concurrency tests (threads, separate connections) passed 5 runs in a row.
- **Frontend** (`frontend/`), each exit 0: `npm run lint`, `lint:tokens`, `typecheck`,
  `format:check`; `npm test` → **59 files, 562 tests passed** (was 51 / 412); `npm run build` →
  `/login` and `/signup` still `○`, `/api/[...path]` `ƒ`.
- **E2E:** `npm run test:e2e` → **11 passed** (8 smoke + 3 auth), with Playwright starting Django
  and `next dev`, and again in CI mode (`$env:CI="1"` after `npm run build`, against `next start`).
  Also passed reusing running servers.
- **Manual** (all recorded in `docs/test-command.md` Part 1):
  - curl against `runserver`: signup sets both cookies with the right flags, the body has only
    `access_token`; the console email links to `http://localhost:3000/verify-email/<key>`;
    refresh rotates, the old cookie works at once and fails after 61 s; 403 `csrf_failed` without
    `Origin` or `X-Requested-With` (refresh and logout); logout → 204 + both cookies deleted, the old
    cookie → 400, no cookie → 401; the access token still works until expiry (by design); an
    unlisted allauth endpoint → 404.
  - Through the relay: 10 failed logins → the 11th `too_many_login_attempts`; a direct call from
    `127.0.0.1` isn't blocked (per-address).
  - Browser (Playwright/Chromium scripts): screenshots of `/signup` and `/login` next to Stitch a2/a3
    at 1280 px (same card width; differences are the planned ones), 390 px with 0 px overflow; real
    sign-up with the test widget → `/home` + banner; cookies (`rz_refresh` host-only, HttpOnly, Lax,
    `/api/auth/`; `rz_session` readable), empty local/session storage, `document.cookie` =
    `rz_session=1`; field errors (email taken, username taken/reserved/invalid, common password);
    the always-fail Turnstile secret → the message under the widget and a reset; the rate-limit
    banner; `/settings` → `/login?next=%2Fsettings`; logout in one tab logs out the other; the
    loading placeholder; Log out at the end of the phone sheet.
- **CI on GitHub:** green for Part 1 (user-reported 2026-10-06), including the E2E job's Turnstile
  test-key sign-up.

## Validation of the Linux clean-room run (2026-10-06)

Goal: prove that a fresh Linux checkout plus the guides works. Method: pack
`git ls-files -co --exclude-standard` (what `git pull` brings, plus the uncommitted doc edits; no
real env file) into a tar, extract it into a fresh **Ubuntu 24.04 container** that shares its network
namespace with throwaway `postgres:18` and `redis:8-alpine` containers (so `localhost:5432/6379` is as
in the guide), then run the guides' Linux commands. Docker Desktop's Linux engine; all exit codes 0.

- **SETUP Part A (Linux):** A1 `apt install git`; A2 `apt-cache policy python3.13` (none on Ubuntu
  24.04), deadsnakes PPA, `python3.13` = **3.13.16**, `venv` works; A3 nvm **v0.40.8** →
  `nvm install 24` = **Node v24.21.0**, npm 11.19.0; A7 `jq`, `npx playwright install --with-deps
  chromium` (Chrome Headless Shell 153); A4: the Docker apt-repository block extracted verbatim from
  SETUP resolved (`docker-ce` 5:29.8.2, `docker-compose-plugin` 5.6.0 candidates); not installed.
- **ENV_GUIDE §1.2 one-command generator** (extracted verbatim from the doc): writes four 67-character
  values, `PROXY_SHARED_SECRET` identical in both files, `JWT_SIGNING_KEY` ≠ `DJANGO_SECRET_KEY`;
  nothing printed.
- **Backend:** `pip install -r requirements-dev.txt`, `migrate`, `createsuperuser --noinput`,
  `python -m pytest` → **440 passed**; `ruff check .` → "All checks passed!"; `ruff format --check .`
  → "66 files already formatted"; `makemigrations --check --dry-run` → "No changes detected";
  `manage.py check` → no issues.
- **Frontend:** `npm ci`; `lint`, `typecheck`, `lint:tokens`, `format:check` clean; `npm test` →
  **562 passed**; `npm run build` OK (route list as before, `/api/[...path]` `ƒ`).
- **E2E:** `npm run test:e2e` → **11 passed** (Django + `next dev` started by Playwright).
- **docs/test-command.md, Linux blocks run verbatim** (extracted by script) against live Django +
  `next dev`: Part 0A steps 3 and 4, Part 1 steps 1, 3, 4, 5 (including the 61 s refresh grace, the
  CSRF 403s, logout, 11 relay logins with the 11th `too_many_login_attempts`, and the final direct
  request from `--interface 127.0.0.2` → `email_password_mismatch`); Part 0B step 3; Part 0D steps 1, 3,
  4, 6, 7, 10, 11. Output matched the shared expected text each time. `npm run brand:build` on Linux
  reproduced every committed brand asset byte for byte (`git status` clean).
- **Syntax:** `bash -n` passes on all 51 bash blocks of `test-command.md`, all 14 of `SETUP.md`, all
  5 of `ENV_GUIDE.md` and the one in `AGENTS.md`. A script confirmed all 51 original PowerShell
  blocks survive unchanged (39 as the Windows twin, 12 as "same commands" bash blocks) and all 15
  expected-output blocks are identical.
- **Not provable here (listed in the guides as "if X fails, do Y"):** installing Docker Engine and the
  `docker` group on the real PC, `docker compose up -d` itself (sibling containers stood in for it;
  only the override file's syntax was checked with `docker compose config`), IPv6 `[::1]` publishing,
  GitHub SSH auth, Linux Mint and Debian specifics (Playwright, Python 3.13 packaging), and Windows
  Docker Desktop behaviour is unchanged.
- **FYI, not caused by this chore:** `npm audit` reports 5 high-severity advisories, all in one
  **dev-only** chain (`braces` → `micromatch` → `fast-glob` → `@next/eslint-plugin-next` →
  `eslint-config-next`); production dependencies: 0. The "449 packages / 0 vulnerabilities" text in
  `test-command.md` Part 0B/0D step 1 dates from Part 0B (the tree is 737 packages now).

## Next exact action

1. **User:** review and commit the plan and this file.
2. **Implement Part 2 from the approved plan**
   ([`part-2-email-verification-reset.md`](plans/part-2-email-verification-reset.md)), starting at its
   "Ordered steps" step 2 (step 1, saving the plan, is done). Fresh session, task.md's implement
   model (Sonnet 5.5 · high); first `git status` and `docker compose up -d`.

## Blockers or user decisions

- None open.
- User decisions for Part 1 (2026-10-02), now in ARCHITECTURE §2/§7: superusers are verified
  (createsuperuser + backfill migration); Turnstile fails closed; the `rz_session=1` hint cookie.
- User decisions for 0C (2026-10-01), in ARCHITECTURE §10: the reduced logged-out shell; phones get a
  top bar plus five bottom tabs with an account sheet; marketing links only to existing pages.

## Follow-ups noted during Part 1 (not done, per the part's scope)

- **Part 2:**
  - Add `auth/email/verify`, `auth/password/request`, `auth/password/reset` and the chosen resend
    endpoint to `ALLAUTH_ENDPOINTS` in `apps/accounts/middleware.py` (`auth/email/verify/resend` is
    allauth's code-flow resend).
  - Replace the email templates: allauth's default text says "Hello from <backend host>!" (the only
    link already uses `FRONTEND_ORIGIN`). Add "Forgot password?" on `/login`; Resend in
    `UnverifiedBanner`.
  - `EMAIL_PROVIDER=file` writes to `backend/tmp/mail/` (git-ignored) for the E2E mailbox.
  - A password reset must end other sessions; refresh already fails after a password change
    (session auth hash, `test_refresh_fails_once_the_password_changes`).
- **Part 3:** add `allauth.socialaccount` and `auth/provider/token` to the allow-list; make
  `google_connected` real. A *pending* social signup needs `X-Session-Token`, which the middleware
  strips and the relay doesn't forward: auto-signup must never pend, or add a short-lived flow cookie.
- **Part 4:** the first real users of `IsEmailVerified` (posts). `RequestOptions.token: false` must
  not be used for app calls that should refresh on 401.
- **Part 6/14:** sign-up sets no display name, so the rail's user card shows `@username` twice (name
  fallback + handle). Consider showing the handle once when the display name is blank.
- **Part 9/17:** run `clearsessions` periodically (expired token sessions pile up in Neon).
- **Part 10:** as defence in depth, make the admin refuse sessions created by headless login.
- **Part 14:** deleting an account must also delete its sessions.
- **Part 16:**
  - CSP for Turnstile (`challenges.cloudflare.com` script and frame).
  - Check what siteverify returns for `action`/`hostname` with the test keys, and add those checks if
    possible.
  - Brute-force protection for the Django Admin login; Argon2's 100 MiB per hash against Render's
    512 MB (worker count or `memory_cost`).
  - Two `rz_refresh` cookies make refresh **and logout** answer 400 (by plan). A stale duplicate
    with another path would block logout until it expires; revisit if it is ever seen.
  - E2E tests write accounts into the local dev database; consider a separate E2E database.
- **Part 17:** fail a deploy that uses a Turnstile test secret.
- **Visual (minor):** the shared `AuthLayout` card (0C) is `p-space-xl sm:p-11` with 44 px inputs;
  a3 used `px-space-xl pt-10 pb-9` and 40 px inputs. Accepted.

## Follow-ups noted during 0C (still open)

- (Part 1 items done: CSRF for refresh/logout and allauth views, `avatar_url` in `/me`, the 401
  refresh hook, `loading`, Log out.)
- **Part 4:** wire `onNewPost` (the AppShell prop, used by the rail button and the bottom tab) to the
  composer modal. At 390 px, `PostCard`'s header wraps the author name onto two lines.
- **Part 14B:** photo uploads rely on the relay's 6 MB body cap (`MAX_BODY_BYTES` in `relay.ts`).
- **Part 15:** polish `not-found`/`error`/`global-error` and the placeholder pages; `/how-it-works`,
  `/privacy` and `/terms` are placeholders.
- **Part 18:**
  - On Workers, confirm `/api/health/` through the relay (already in the production smoke test) and
    that `request.signal` doesn't abort early.
  - Never build the Worker from a checkout with a real `.env.local` (SETUP B3 note).
  - Replace `vars.BACKEND_ORIGIN` in `wrangler.jsonc`.
- **Dependency upkeep (Part 16 Dependabot, or any OpenNext upgrade):**
  - Remove the `esbuild` devDependency once an `@opennextjs/cloudflare` release declares `esbuild`
    itself (upstream #1339 / PR #1353). Then re-run the OpenNext build: in Docker first, then CI.
  - When bumping `wrangler`, keep `esbuild` on wrangler's own pin, so one copy is shared and it stays
    inside vite's peer range.
  - `npm audit` (2026-10-06): 5 high advisories in the dev-only `braces` → `micromatch` →
    `fast-glob` → `@next/eslint-plugin-next` → `eslint-config-next` chain; production dependencies
    clean. Let Dependabot (Part 16) or a deliberate `eslint-config-next` bump resolve it; don't run
    `npm audit fix --force` blindly.
  - `npm ci` on Linux warns that `eslint@9.39.5` is deprecated. Moving to a supported ESLint major is
    a separate, deliberate upgrade: check the flat config and `npm run lint`.
  - Any django-allauth upgrade: re-check the internals Part 1 depends on (MEMORY entry, 2026-10-03).
- **Minor:**
  - `<Logo/>` renders 47.86 px instead of 48 px tall at `lg` (preflight `img { height: auto }`).
  - The toast offset (`bottom-20` below 768 px) also applies on marketing pages, where there is no
    bottom bar.

## Follow-ups noted during 0D (still open)

- Part 2: email templates use `FRONTEND_ORIGIN/brand/email-logo.png` (320 px wide, shown at 160).
- Part 10: `templates/admin/base_site.html` uses the static `core/brand/logo-admin.png` (158x64).
  `collectstatic` must pick it up (Part 17 already lists collectstatic in the build).
- The `theme_color` of the web manifest is the dark plate colour; revisit if a light toolbar is
  preferred.
- If the logo is re-exported, check `markSelector` in `scripts/brand/brand.config.json` and compare
  the printed contrast table with ARCHITECTURE §14.

## Follow-ups noted during 0B (still open)

- Part 16: subset the 4 MB Material Symbols font to the glyphs actually used.
- Toasts render below an open `<dialog>` (top layer). If a toast must appear over a modal, move the
  toast region into a popover. Background scroll is also not locked while a modal is open.
- (Done in Part 1: `scorePassword` already rates anything under 8 characters as Weak, matching
  Django's minimum; the sign-up form also checks the 8-character minimum.)
- `PostCard` has no action bar or source line yet (Parts 4, 7, 7B) and no skeleton variant.

## Follow-ups noted during 0A (still open)

- Part 10: log old → new values for every PlatformSettings change; seniors-only editing; the senior
  group's extra permissions (the role → groups mapping is cumulative).
- (Done in Part 1: CLI superusers are verified with an allauth `EmailAddress`; the default
  authentication class is set, so an unauthenticated request now gets 401.)
- Part 17: fail deploys when `PROXY_SHARED_SECRET`/`INTERNAL_CRON_SECRET` is short or a
  `local-dev-only` placeholder; verify Render's health-check Host header against `ALLOWED_HOSTS`;
  `collectstatic` must run in the build (the manifest storage needs it when DEBUG is False).

## Handoff checklist (outgoing agent)

- [x] Stop editing before the incoming agent starts.
- [x] Record current owner, phase and approved plan.
- [x] Record files changed and any unrelated pre-existing modifications.
- [x] Record every validation command and its exact pass/fail result.
- [x] Record blockers, user decisions and the next exact action.
- [x] Promote only durable, non-duplicated knowledge to `MEMORY.md`.
