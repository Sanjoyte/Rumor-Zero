# Rumor Zero: live handoff

Update this file at meaningful checkpoints and before switching between Claude Code and Codex.
Keep it concise and factual. The incoming agent must verify it against the current files and
read-only git output.

## Active work

- **Part:** 0C (App shell, API relay, API client, CI). Parts 0A (2026-09-30), 0B and 0D (2026-10-01)
  are done and committed.
- **Owner:** none (implementation finished; idle until the user reviews, commits and pushes)
- **Phase:** implemented and validated locally. task.md shows `[~] In progress (awaiting first CI
  run)` in both places, with 7 of 8 criteria ticked. The open one is "all CI jobs green on GitHub",
  which needs the user's push.
- **Last approved plan:** [`docs/agents/plans/part-0C-app-shell-relay-ci.md`](plans/part-0C-app-shell-relay-ci.md)
  (status: implemented 2026-10-01; awaiting CI)
- **Last updated:** 2026-10-01 by Claude (Opus 5.5), end of Part 0C implementation

## Completed checkpoints

- Dual-agent setup, the pre-0A correction pass, Parts 0A, 0B and 0D (0D = `b695f09`), the
  multi-source spec change (`bd05636`) and the 0C plan (`90857ec`), all committed by the user.
- 2026-10-01 (Claude, Opus 5.5): **Part 0C implemented** (uncommitted, see the file list below).
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

- **Modified:**
  - `task.md`, `docs/{ARCHITECTURE,ANALYSIS,STRUCTURE,SETUP,test-command}.md`
  - `docs/agents/{HANDOFF,MEMORY}.md`, `docs/agents/plans/part-0C-app-shell-relay-ci.md`
  - in `frontend/`: `package.json`, `package-lock.json`, `next.config.ts`, `tsconfig.json`,
    `eslint.config.mjs`, `.prettierignore`
  - in `frontend/src/`: `app/layout.tsx`, `app/providers.tsx`, `components/ui/Toast.tsx`,
    `features/dev/UiGallery.tsx`
- **Deleted:** `frontend/src/app/page.tsx`. It moved to `(marketing)/page.tsx`; two pages for `/` would
  fail the build.
- **New:**
  - `.github/workflows/ci.yml`
  - in `frontend/`: `wrangler.jsonc`, `open-next.config.ts`, `playwright.config.ts`, `e2e/`
  - in `frontend/src/app/`: `(app)/`, `(auth)/`, `(marketing)/`, `api/`, `dev/shell/`, `fonts.ts`,
    `not-found.tsx`, `error.tsx`, `global-error.tsx`, `error-pages.test.tsx`
  - in `frontend/src/`: `components/shell/`, `lib/api/`, `lib/auth/`, `features/dev/ShellPreview.tsx`
- `git status --short design` prints nothing.
- No nested `frontend/AGENTS.md`/`CLAUDE.md`.
- `frontend/playwright-report` and `frontend/test-results` exist locally; they are git-ignored.
- No real env file was read or edited. Checks that needed a secret used process-env test values
  (`echo-check-secret`) on a separate `next dev -p 3100`.
- **Nothing left running.** The Docker containers the agent started were stopped with
  `docker compose down`, which keeps the data. No dev server, `runserver` or workerd is running, and
  ports 3000/3100/8000/8765 are free.

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
- Not run (Linux/GitHub only):
  - `npx opennextjs-cloudflare build`
  - the CI workflow itself
  - `wrangler preview`/`deploy`

## Next exact action

1. The user reviews the diff, commits and pushes (all git operations are theirs). `docs/test-command.md`
   Part 0C has the hands-on checks.
2. Check the first CI run, either in GitHub's Actions tab or with `gh run list --workflow ci.yml --limit 1`
   and `gh run view <id> --log-failed` (read-only; `gh api` is denied).
   - **If all three jobs are green:** tick the last 0C criterion in task.md, set
     `**Status:** [x] Done (YYYY-MM-DD)` and the summary row to `[x] Done (YYYY-MM-DD)`, then update
     this file. The next part is **Part 1** (Auth core). Prompt: `Plan Part 1 from task.md. Do not
     implement yet.`
   - **If a job fails:** investigate and report before changing anything. Known risks:
     - 0D's `build.test.ts` may report stale brand SVGs on Linux (librsvg measurement). Fix the
       measurement; never loosen the test.
     - An import-case mismatch could fail the Linux build.
     - A Linux-only OpenNext build problem.

## Blockers or user decisions

- None open.
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
