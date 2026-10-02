# Rumor Zero: live handoff

Update this file at meaningful checkpoints and before switching between Claude Code and Codex.
Keep it concise and factual. The incoming agent must verify it against the current files and
read-only git output.

## Active work

- **Part:** 1 (Auth core: sign up, log in, tokens, log out): **done locally on 2026-10-03**, not
  committed yet. Parts 0A, 0B, 0D and 0C are done; 0C was closed in `d92f070`.
- **Owner:** none (Claude stopped after Part 1; the user reviews, commits and pushes)
- **Phase:** all plan steps 0–12 done; task.md shows Part 1 `[x] Done (2026-10-03)` in both places.
  CI has not run on this code yet (only the user pushes).
- **Approved plan:** [`docs/agents/plans/part-1-auth-core.md`](plans/part-1-auth-core.md)
  (status line: implemented and validated 2026-10-03)
- **Previous plan:** [`docs/agents/plans/part-0C-app-shell-relay-ci.md`](plans/part-0C-app-shell-relay-ci.md)
  (done 2026-10-01)
- **Last updated:** 2026-10-03 by Claude (Opus 5.5), Part 1 implemented, validated and documented

## Completed checkpoints

- 2026-10-03 (Claude, Opus 5.5): **Part 1 implemented** (uncommitted; see "Current workspace
  state"). Started from HEAD `349dc96` (the plan + this file, committed by the user), whose
  workspace matched this file's previous state.
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

- HEAD is `349dc96` (Part 1 plan). Everything listed under the 2026-10-03 checkpoint is
  **uncommitted**: 38 modified tracked files and 47 new files (`git diff --name-only`,
  `git ls-files --others --exclude-standard`).
- All changed files use LF, like the repository (`* text=auto eol=lf`); a CRLF slip from Python
  edits was found and converted back.
- `git status --short design` prints nothing; no nested `frontend/AGENTS.md`/`CLAUDE.md`.
- **Nothing left running.** The dev servers were stopped and their orphaned `next dev`/`workerd`
  processes ended (MEMORY entry); ports 3000 and 8000 are free. The Docker containers (restarted by
  the agent after Docker Desktop had stopped them) were stopped with `docker compose down`, which
  keeps the data.
- Scratchpad files (screenshots, Playwright scripts) are outside the repo. The `%TEMP%\rz-*`
  helper files from the manual checks were deleted; older `%TEMP%\rz-edge-*`, `rz-dev*.log` and
  similar files predate this session and were left alone.

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
- **Not run:** CI on GitHub (the user pushes). New risk there: the E2E job's browser and Django must
  reach `challenges.cloudflare.com` for the test-key sign-up.

## Next exact action

1. **User:** review the diff, commit Part 1 and push. Report the CI result (MEMORY: the agent can't
   read it). If the E2E job fails at the Turnstile widget or siteverify, that is one of the plan's
   stop conditions: reproduce it from the "playwright-report" artifact before changing anything.
2. Then start a fresh session for **Part 2** (email verification & password reset): plan it first
   (`Plan Part 2 from task.md. Do not implement yet.`). Read "Follow-ups noted during Part 1" below.

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
