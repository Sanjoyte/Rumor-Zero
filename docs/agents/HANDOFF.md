# Rumor Zero: live handoff

Update this file at meaningful checkpoints and before switching between Claude Code and Codex.
Keep it concise and factual. The incoming agent must verify it against the current files and
read-only git output.

## Active work

- **Part:** 1 (Auth core: sign up, log in, tokens, log out). Parts 0A, 0B, 0D and 0C are done;
  0C was closed in `d92f070`.
- **Owner:** none (idle until the user starts implementation)
- **Phase:** plan approved by the user on 2026-10-02. No Part 1 code written, no setup command run.
  task.md is unchanged: Part 1 is still `[ ]` and goes to `[~]` when implementation starts (plan
  step 0).
- **Approved plan:** [`docs/agents/plans/part-1-auth-core.md`](plans/part-1-auth-core.md)
- **Previous plan:** [`docs/agents/plans/part-0C-app-shell-relay-ci.md`](plans/part-0C-app-shell-relay-ci.md)
  (done 2026-10-01)
- **Last updated:** 2026-10-02 by Claude (Opus 5.5), Part 1 plan approved and saved

## Completed checkpoints

- 2026-10-02 (Claude, Opus 5.5): **Part 1 planned and approved.**
  - Saved as `docs/agents/plans/part-1-auth-core.md`.
  - allauth 65.19.5 behaviour was read in the installed source, and Turnstile was checked against
    Cloudflare's docs. A separate adversarial review pass was folded in.
  - User decisions: CLI superusers count as verified (plus a backfill migration); Turnstile fails
    closed; a non-secret `rz_session` hint cookie.
  - The plan's deviations list is part of the approval.
  - Nothing else was changed.
- Dual-agent setup, the pre-0A correction pass, Parts 0A, 0B and 0D (0D = `b695f09`), the
  multi-source spec change (`bd05636`) and the 0C plan (`90857ec`), all committed by the user.
- 2026-10-01: **CI green, Part 0C done.** The run on `60cfffc` passed Backend, Frontend (including
  the OpenNext build) and E2E, as the user reported. The agent couldn't read it (`gh` not installed,
  private repo; MEMORY.md). The closing edits were committed by the user as `d92f070`: `task.md`
  (last criterion, both status spots, CI note), the plan's status line, `docs/test-command.md`
  (Part 0C step 11), `MEMORY.md` (CI results come from the user) and this file.
- 2026-10-01 (Claude, Opus 5.5): **fix for the first CI run**, committed by the user as `60cfffc`.
  - CI on `6e83866`: backend and e2e were green; the frontend job failed at "OpenNext build" with
    `ERR_MODULE_NOT_FOUND: Cannot find package 'esbuild' imported from
    …/@opennextjs/cloudflare/dist/cli/build/bundle-server.js`.
  - Cause: `@opennextjs/cloudflare` 1.20.7 imports `esbuild` without declaring it (upstream
    opennextjs-cloudflare#1339; fix PR #1353 unreleased). It relied on npm hoisting `@opennextjs/aws`'s
    nested 0.25.4, and `vite` 8.3.1's optional peer `esbuild ^0.27.0 || ^0.28.0` blocks that hoist, so
    no top-level `esbuild` existed. Windows has the same tree; it went unnoticed because the OpenNext
    build is Linux-only.
  - Fix: `esbuild` **0.28.1** as an exact devDependency.
    - It matches wrangler's own pin (one shared copy) and sits inside vite's peer range.
    - It's patched for GHSA-g7r4-m6w7-qqqr; 0.27.7, upstream's suggested line, was flagged by
      `npm audit`.
    - Lockfile: wrangler's nested `esbuild` + 26 `@esbuild/*` entries moved to the top level; nothing
      else changed. Git's default diff shows ~8.5k lines because of the move; `--diff-algorithm=histogram`
      shows ~485.
    - Docs: SETUP B3 `esbuild` row (why, and remove once OpenNext declares it), task.md deviation,
      MEMORY (Docker recipe for Linux-only CI steps).
- 2026-10-01 (Claude, Opus 5.5): **Part 0C implemented**, committed by the user as `6e83866`.
  - **Relay:** `src/lib/api/relay.ts` + `src/app/api/[...path]/route.ts`, per ARCHITECTURE §1.
    Bodies are buffered (≤ 6 MB). A backend `/api/` `Location` is rewritten as relative. Timeout: 70 s,
    for the headers only. `backend_waking` 503s.
  - **API client and auth skeleton:** `src/lib/api/{client,types}.ts`, and in `src/lib/auth/`:
    `token-store.ts`, `refresh-lock.ts`, `AuthProvider.tsx`. The provider stays anonymous until Part 1.
  - **Shell:** `src/components/shell/*` (AppShell, Sidebar, TopBar, MobileNav, AccountMenu, ShellLink,
    nav-items, AuthLayout, MarketingNav, MarketingFooter, Placeholder).
    - Route groups `(marketing)`, `(auth)`, `(app)` with placeholder pages.
    - `not-found`, `error`, `global-error`; `fonts.ts`.
    - `/dev/shell` preview (`features/dev/ShellPreview.tsx`).
    - The title template; the toast mobile offset.
  - **OpenNext and E2E:** `wrangler.jsonc`, `open-next.config.ts`, the `next.config.ts` phase function
    (`initOpenNextCloudflareForDev` runs in dev only, plus `skipTrailingSlashRedirect`, a page-slash
    redirect and `poweredByHeader: false`); `playwright.config.ts`, `e2e/smoke.spec.ts`.
  - **CI:** `.github/workflows/ci.yml`, with three jobs on `actions/*@v7`.
  - **Docs:**
    - `task.md`: criteria and deviations; status left `[~]` until CI is green.
    - `ARCHITECTURE.md`: §1 relay rules, §10 layouts, §11 CI.
    - `ANALYSIS.md`: a.3, c-35 and d.
    - `STRUCTURE.md`: ✅ markers.
    - `SETUP.md`: pins, OpenNext/Playwright notes, action majors.
    - `MEMORY.md`: an orphaned-dev-server entry, and the Edge minimum-width limit.
    - `docs/test-command.md`: Part 0C section.
    - The plan's status line.
  - No new env variable: `.env.example` files and ENV_GUIDE are unchanged.

## Current workspace state

- HEAD is `d92f070` (0C closed), on top of `60cfffc` (the CI fix) and `6e83866` (0C), all committed
  by the user.
- **Uncommitted:** only the new `docs/agents/plans/part-1-auth-core.md` and this file. No code,
  dependency, task.md or env-file change.
- `git status --short design` prints nothing.
- No nested `frontend/AGENTS.md`/`CLAUDE.md`.
- `frontend/playwright-report` and `frontend/test-results` exist locally; they are git-ignored.
- No real env file was read or edited. Checks that needed a secret used process-env test values
  (`echo-check-secret`) on a separate `next dev -p 3100`.
- **Nothing left running.** The Docker containers the agent started were stopped with
  `docker compose down`, which keeps the data. No dev server, `runserver` or workerd is running, and
  ports 3000/3100/8000/8765 are free. The Linux check container ran with `--rm` and is gone; the
  `node:24-bookworm-slim` image stays in Docker's local cache.

## Validation of the CI fix (2026-10-01)

- Passed (`frontend/`, Windows, each exit 0):
  - `npm ls esbuild` shows a top-level `esbuild@0.28.1`, also used by wrangler and vite
    (`deduped`); `@opennextjs/aws` keeps its nested 0.25.4.
  - `npm audit` → "found 0 vulnerabilities".
  - Loading `@opennextjs/cloudflare/dist/cli/build/bundle-server.js` (the module that failed in CI)
    works, and it resolves `esbuild` 0.28.1.
  - `npm run lint`, `lint:tokens`, `typecheck`, `format:check`; `npm test` → **51 files, 412 tests
    passed**.
- Passed (Linux): the whole CI frontend job in `node:24-bookworm-slim` (Node 24.21.0 / npm 11.19.0,
  the same as CI), with `CI=true`.
  - The source was the 288 files `git ls-files -co --exclude-standard` lists, so the only env files
    were the two `.env.example`s.
  - Steps: `npm ci` (736 packages), lint, typecheck, lint:tokens, format:check, test (**51 / 412
    passed**, including the 0D brand tests), then `npx opennextjs-cloudflare build` → "OpenNext build
    complete", `.open-next/worker.js` written. Exit 0.
- Not re-run: backend and e2e, which were green in CI and are untouched by this change.

## Validation of Part 0C (2026-10-01)

- `frontend/`, each exit 0:
  - Passed: `npm run lint` → no findings.
  - Passed: `npm run lint:tokens` → "lint:tokens OK".
  - Passed: `npm run typecheck`, also on a simulated clean checkout (without `next-env.d.ts` and
    `.next`).
  - Passed: `npm run format:check` → "All matched files use Prettier code style!".
  - Passed: `npm test` → **51 test files, 412 tests passed** (was 40 / 329 after 0D). New: the relay
    (24 unit + 8 real-HTTP), client (19), auth (9), shell (17 + 4 layouts), error pages (2).
  - Passed: `npm run build` → `/`, `/login`, `/signup` and the app placeholders `○` static;
    `/api/[...path]` and `/u/[username]` `ƒ`.
- Passed: `npm run test:e2e` → **8 passed**, run three ways:
  - reusing a running dev server
  - from PowerShell with nothing running (Playwright starts Django and `next dev`)
  - in CI mode (`$env:CI="1"`, after `npm run build`, against `next start`)
  Playwright cleaned up its servers each time.
- `backend/` (code unchanged), via the venv:
  - Passed: `ruff check .` → "All checks passed!"; `ruff format --check .` → "43 files already
    formatted".
  - Passed: `makemigrations --check --dry-run` → "No changes detected"; `pytest` → **200 passed**.
- Passed (real Django through `next dev`):
  - `curl -i http://localhost:3000/api/health/` → 200 `{"status":"ok"}`, no redirect.
  - `/api/health` → Django 301 with relative `location: /api/health/`.
  - `/api/a%2Fb/` → 400; `/api/nope/` → 404; `/home/` → 308 `/home`.
  - Django stopped → 503 `backend_waking` in 36 ms, with `retry-after: 30` and `cache-control: no-store`.
- Passed (scratchpad stand-in backend, in PowerShell):
  - Spoofed `X-RZ-Proxy-Secret`/`X-RZ-Client-IP`/`X-Forwarded-Host` are replaced or dropped
    (`secretMatches: true`, `clientIp: "::1"`).
  - A POST body arrives with `Content-Length: 11`, not chunked.
  - Two `Set-Cookie` headers reach curl.
  - `If-None-Match` → 304 with `etag` and `cache-control` unchanged.
- Passed (visual):
  - Headless Edge `/dev/shell` at 1280 next to Stitch b1 at 1280: same rail, header and item
    geometry. The only differences are the planned logo, Bookmarks, "New post", Moderation and no
    Ledger pill.
  - Edge at 1024 (icon dock).
  - Playwright at 390, 390 with the sheet open, 1280 with the user menu, the logged-out shell,
    `/login` and `/`: 0 px horizontal overflow everywhere.
  - Playwright interaction checks: Esc closes the menu and sheet, Tab shows the skip link, dock
    tooltips, titles follow the template.
- Passed: OpenNext's matcher honours `skipTrailingSlashRedirect` and exempts `/api/` (read in
  `node_modules/@opennextjs/aws/dist/core/routing/matcher.js`). `next dev` starts on Windows with
  `initOpenNextCloudflareForDev()` (workerd).
- Passed: `ci.yml` parses (the `yaml` package): 3 jobs, all actions `@v7`; triggers are push to
  `main`, PR and dispatch.
- Not run at the time (Linux/GitHub only): `npx opennextjs-cloudflare build` (it has since run, in
  the CI fix above), the CI workflow itself, `wrangler preview`/`deploy`.

## Next exact action

**Implement Part 1 from the approved plan** ([`plans/part-1-auth-core.md`](plans/part-1-auth-core.md)).

- Model: Opus 5.5 · high (task.md Part 1).
- Start with the plan's step 0: set Part 1 to `[~]` in both task.md places and update "Active
  work". The 0C dependency is already satisfied.
- Then follow steps 1–12 in order, and check the plan's stop conditions at each step.
- The Part 1 follow-ups listed below (0A, 0B, 0C) are covered by the plan.
- CI results come from the user (MEMORY.md). Reproduce any Linux-only failure in Docker before
  asking for another push.

## Blockers or user decisions

- None open.
- User decisions for Part 1 (2026-10-02), in the plan and written into ARCHITECTURE during
  implementation:
  - `createsuperuser` and a backfill migration mark superusers' email verified.
  - Turnstile fails closed when siteverify is unreachable or rejects the secret.
  - A non-secret `rz_session=1` hint cookie lets anonymous page loads skip the refresh call.
- User decisions for 0C (2026-10-01), recorded in ARCHITECTURE §10:
  - The logged-out shell has a reduced nav: Home, Search, Log in / Sign up.
  - Phones get a top bar plus a 5-tab bottom bar (Home, Search, New post, Notifications, Profile);
    the avatar opens a sheet with Bookmarks, Settings and Moderation.
  - Marketing links go only to existing pages; About, Community Guidelines, Press and Contact are
    dropped.

## Follow-ups noted during 0C (not done, per the part's scope)

- **Part 1:**
  - Through the relay, Django sees `Host` = the backend and `Origin` = the frontend. Any unsafe view
    that isn't CSRF-exempt would fail Django's Origin check. Refresh/logout must be `csrf_exempt` with
    the c-18 checks (Origin + `X-Requested-With`), and allauth headless views need checking the same
    way.
  - `GET /api/v1/me/` should also return `avatar_url` (null until 14B): the shell's `Me` type uses it.
  - Wire `setUnauthorizedHandler` (refresh with `withRefreshLock`, then retry) and the `loading` state in
    `AuthProvider`. Add the user-menu "Log out".
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
  - `npm ci` on Linux warns that `eslint@9.39.5` is deprecated ("no longer supported"). Our
    `"eslint": "^9"` range (from create-next-app) holds it there; `eslint-config-next` 16.3.8 accepts
    `>=9.0.0`. Moving to a supported ESLint major is a separate, deliberate upgrade: check the flat
    config and `npm run lint`.
- **Minor:**
  - `<Logo/>` renders 47.86 px instead of 48 px tall at `lg`, because preflight sets
    `img { height: auto }`, so the rounded width decides the height. Invisible in practice; the E2E
    test allows ±0.5 px.
  - The toast offset (`bottom-20` below 768 px) also applies on marketing pages, where there is no
    bottom bar.

## Follow-ups noted during 0D (still open)

- Part 2: email templates use `FRONTEND_ORIGIN/brand/email-logo.png` (320 px wide, shown at 160).
- Part 10: `templates/admin/base_site.html` uses the static `core/brand/logo-admin.png` (158x64). `collectstatic`
  must pick it up (Part 17 already lists collectstatic in the build).
- The `theme_color` of the web manifest is the dark plate colour; revisit if a light toolbar is preferred.
- If the logo is re-exported, check `markSelector` in `scripts/brand/brand.config.json` (the build fails when
  it does not match exactly one shape) and compare the printed contrast table with ARCHITECTURE §14.

## Follow-ups noted during 0B (still open)

- Part 16: subset the 4 MB Material Symbols font to the glyphs actually used.
- Toasts render below an open `<dialog>` (top layer). If a toast must appear over a modal, move the
  toast region into a popover. Background scroll is also not locked while a modal is open.
- Part 1: revisit `scorePassword` against the final allauth/Django validators.
- `PostCard` has no action bar or source line yet (Parts 4, 7, 7B) and no skeleton variant.

## Follow-ups noted during 0A (still open)

- Part 10: log old → new values for every PlatformSettings change; seniors-only editing; the senior
  group's extra permissions (the role → groups mapping is cumulative).
- Part 1/2: a CLI superuser has `is_email_verified=False` and no allauth `EmailAddress`; decide
  whether it needs app writes. `DEFAULT_AUTHENTICATION_CLASSES` is `[]` until Part 1, so an
  unauthenticated request currently returns 403 rather than 401.
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
