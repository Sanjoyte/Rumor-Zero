# Rumor Zero: Build plan (task.md)

## How to use this file

1. Start Claude Code in the repo root (`claude`).
2. **Enter plan mode:** press **Shift+Tab** until the footer shows *plan mode*, or start your message with `/plan`.
3. **Set the part's PLAN model and effort.** For example `/model opus`, then `/effort xhigh`.
4. Type: **`Plan Part 4 from @task.md`**. The `@` attaches this file, and Claude reads `CLAUDE.md` and `docs/ARCHITECTURE.md` itself.
5. **Review the plan.** Ask for changes until you're happy, then approve it.
6. **Switch to the IMPLEMENT model**, if it's different. Press **Esc** as soon as implementation starts, run `/model …` and `/effort …`, then type *"Implement the approved plan."*
   - Shortcut: `/model opusplan` uses Opus while planning and switches to Sonnet for implementation automatically.
7. **Claude implements only that part.** It runs the part's tests, ticks its acceptance criteria below, sets its **Status**, and **stops**.
8. **You review** the diff and run the tests yourself, then do all git operations (commit/push) yourself. Start a fresh session (`/clear`) for the next part.

**Models and effort** (checked against the Claude Code docs on 2026-09-29):
- `/model` aliases: `opus` → Opus 5.5, `sonnet` → Sonnet 5.5, `haiku` → Haiku 4.5, `opusplan`.
- `/effort` levels: `low`, `medium`, `high`, `xhigh`, `max` on Opus 5.5 and Sonnet 5.5 (both default to `medium`). `max` is **session-only**. Haiku 4.5 has no effort setting.

**Status legend:** `[ ] Not started` · `[~] In progress` · `[x] Done (date)` · `[!] Blocked (reason)`

| Part | Title | Depends on | Status |
|---|---|---|---|
| 0A | Backend foundation | SETUP Part A | [ ] |
| 0B | Frontend foundation & design system | SETUP Part A | [ ] |
| 0C | App shell, API relay, API client, CI | 0A, 0B | [ ] |
| 1 | Auth core: sign up, log in, tokens, log out | 0C | [ ] |
| 2 | Email verification & password reset | 1 | [ ] |
| 3 | Continue with Google | 1 | [ ] |
| 4 | Posts: composer + Recent feed | 1 | [ ] |
| 5 | Post detail, sharing, deletion, status polling | 4 | [ ] |
| 6 | Profiles, follows, Following feed | 4 | [ ] |
| 7 | Likes & comments | 5 | [ ] |
| 8 | Reporting & threshold | 5 | [ ] |
| 9 | Fact-check pipeline stub + routing | 8 | [ ] |
| 10 | Human review panel (Django Admin) | 9 | [ ] |
| 11 | Appeals & removed-post tombstones | 10 | [ ] |
| 12 | Search | 6 | [ ] |
| 13 | Notifications | 7, 10, 11 | [ ] |
| 14 | Account settings, data export, deletion | 6, 7 | [ ] |
| 15 | Landing & static pages | 4 | [ ] |
| 16 | Security pass, load test, E2E hardening | 1–15 | [ ] |
| 17 | Deploy backend (Render, Neon, Upstash, Brevo, Sentry) | 16 | [ ] |
| 18 | Deploy frontend, keep-alive & monitoring | 17 | [ ] |

The order follows the guide's MVP roadmap (§18): setup → auth → posts/feed → follow/like/comment → reports → pipeline stub → review panel → search + notifications → security + load test → launch.

Adjustments for real dependencies:
- Part 0 is split into three.
- Auth and social are split into sessions of one sitting each.
- Appeals (guide §8.4) follow the review panel.
- Notifications come after every event source exists.
- Deployment is last.

---

## Part 0A: Backend foundation
**Status:** [ ] Not started
**Goal:** a running Django project with env-driven settings, the final custom User model (before the first migration), health endpoints, shared API plumbing, local Postgres/Redis, and a green test and lint setup.
**Depends on:** SETUP.md Part A (Python 3.13, Docker); ENV_GUIDE §1.1–1.4 done (`backend/.env` exists).
**Stitch files to convert:** none.

**Backend scope**
- Setup commands:
  - in `backend/`: `py -3.13 -m venv .venv`, then `django-admin startproject rumor_zero .`
  - apps `core`, `accounts` via `python manage.py startapp <name> apps/<name>`
- Files:
  - `requirements.txt` / `requirements-dev.txt` pinned per SETUP B1/B2 (re-check the latest patch versions)
  - `pyproject.toml` (ruff, pytest)
  - `conftest.py`, `.python-version` (3.13)
  - root `compose.yaml`: `postgres:18` (volume at `/var/lib/postgresql`) + `redis:8-alpine`, both with healthchecks
  - root `.gitattributes` (`* text=auto eol=lf`)
- `settings.py`:
  - reads env with django-environ (process env wins over `.env`)
  - `DATABASE_URL` with `CONN_MAX_AGE=60`, `CONN_HEALTH_CHECKS=True`
  - Redis cache when `REDIS_URL` is set (`protocol: 2`), else LocMem
  - Argon2 first in `PASSWORD_HASHERS`
  - WhiteNoise; admin at `ADMIN_URL_PATH`
  - production security settings when not DEBUG: `SECURE_PROXY_SSL_HEADER`, HSTS, secure cookies
  - Sentry initialised only if `SENTRY_DSN` is set (`send_default_pii=False`)
  - logging that never prints secrets
- `accounts.User`, exactly as in ARCHITECTURE §2: UUID, lowercase username validation plus reserved names, lowercase email, role → Groups/`is_staff` sync, `is_email_verified`, `display_name`, `bio`, `avatar_url` (unused). Plus the manager, an admin, and the initial migration.
- `core`:
  - `/api/health/`: no DB and no session, so **0 queries**
  - `/api/health/deep/`: needs `X-RZ-Cron-Secret`; runs `SELECT 1` and a cache set/get
  - `ClientIPMiddleware` (ARCHITECTURE §1)
  - DRF defaults: JSON only, the custom exception handler that adds `code`, a cursor pagination class returning `next_cursor`, and throttle scopes from ARCHITECTURE §3
  - `PlatformSettings` singleton, a data migration seeding it from env, and a cached accessor. Seniors-only admin permissions come in Part 10.

**Frontend scope:** none.
**API endpoints:** `GET /api/health/`, `GET /api/health/deep/`.

**Acceptance criteria**
- [ ] `docker compose up -d` shows both services healthy; `python manage.py migrate` works on an empty DB
- [ ] `AUTH_USER_MODEL = "accounts.User"` from the very first migration; `createsuperuser` works
- [ ] Changing `role` updates Group membership and `is_staff`
- [ ] `/api/health/` returns `{"status":"ok"}` with **0 queries**; `/api/health/deep/` returns 403 without the secret and 200 with it
- [ ] `X-RZ-Client-IP` is honoured only with the correct `X-RZ-Proxy-Secret`
- [ ] `python manage.py check --deploy` passes with production-like env values (DEBUG=False, secure cookies, HSTS)
- [ ] `ruff check .`, `ruff format --check .`, `pytest` and `makemigrations --check --dry-run` are all clean
- [ ] No secret appears in the repo; any new env var is added to `backend/.env.example` and ENV_GUIDE

**Required tests:** user model (email/username normalisation, reserved names, role sync), health endpoints (query count 0, secret check), ClientIPMiddleware (secret ok / wrong / missing), PlatformSettings accessor (seed, caching), pagination output shape, exception handler `code`.

**Recommended models**
- **Plan:** Opus 5.5 · high. The custom user model and settings layout are painful to change after the first migration.
- **Implement:** Sonnet 5.5 · medium. Well-trodden Django scaffolding once the plan is fixed.

---

## Part 0B: Frontend foundation & design system
**Status:** [ ] Not started
**Goal:** a Next.js app whose Tailwind v4 theme **is** the Stitch design system, plus the tested UI primitive kit every later screen is built from.
**Depends on:** SETUP.md Part A (Node 24). Can run in parallel with 0A.

**Stitch files to convert**
- `design/stitch/DESIGN.md` (all tokens)
- Component sources:
  - `b1_home_feed`: PostCard, StatusBadge, CategoryChip, Tabs
  - `b2_post_composer_modal`: Modal, SegmentedControl, Textarea + counter, Toggle
  - `a2_sign_up`, `a3_log_in`, `a6_reset_password`: TextField, PasswordField, PasswordStrengthMeter, Alert, Button, Divider
  - `d1_report_post_modal`: RadioCard list
  - `b4_search_results`: FilterChips, LoadMore
  - `c2_account_settings`: Checkbox, DangerZone
  - `d2_moderator_peer_review_queue`: Select
  - `design/stitch/code.html`: the full status taxonomy for StatusBadge

**Frontend scope**
- **Scaffold:**
  - Move `frontend/.env.example` out of `frontend/`.
  - From the repo root: `npx create-next-app@16.3 frontend --ts --tailwind --eslint --app --src-dir --import-alias "@/*" --use-npm --turbopack --no-agents-md --disable-git --yes`. Use the latest 16.3.x, **≥ 16.3.7**.
  - Put `.env.example` back, append `!.env.example` to `frontend/.gitignore`, and confirm no `frontend/CLAUDE.md` or `AGENTS.md` exists.
  - package name `rumor-zero-frontend`; `.nvmrc` = `24`; `@types/node` ^24
  - scripts: `lint` (eslint), `typecheck`, `test` (vitest run), `lint:tokens` (fails on default-palette classes or raw hex in `src/`)
- **Theme:** `src/app/globals.css` `@theme` holds every DESIGN.md token.
  - colours → `--color-*`, with the default palette reset
  - `--text-*` with line height, letter spacing and weight
  - `--radius-lg: 0.25rem`
  - `--spacing-space-*`, `--container-reading/wide/form/modal`
  - base body styles, a focus-visible ring in `secondary`, `prefers-reduced-motion`
  - Do **not** port the scrollbar-hiding CSS.
- **Fonts:** Inter, JetBrains Mono and Newsreader (roman + italic, opsz) via `next/font/google`, as CSS variables. Material Symbols Outlined via the `material-symbols` package, plus an `<Icon>` component.
- **UI primitives** (`src/components/ui/`), each with variants that match Stitch:
  - Button (primary / secondary / ghost / destructive / icon)
  - TextField, PasswordField, Textarea (counter), Checkbox, RadioCard, Select, Toggle
  - Tabs, SegmentedControl, FilterChips
  - Card, VerdictStripe, StatusBadge (the ARCHITECTURE §4 badge table), CategoryChip
  - Avatar (initials only)
  - Modal (native `<dialog>`: focus trap, Esc, `aria-modal`)
  - Alert, Toast, Skeleton, EmptyState, LoadMore, ProgressBar, PasswordStrengthMeter
- Helpers: `lib/cn.ts`, `lib/format.ts` (relative time, compact numbers).
- A **dev-only** gallery at `/dev/ui` showing every component and state. It 404s in production builds.
- Vitest + RTL + jest-dom setup; Prettier with the Tailwind plugin.

**Backend scope:** none. **API endpoints:** none.

**Acceptance criteria**
- [ ] `/dev/ui` shows every primitive in every state. PostCard, the sign-up form fields, the d1 radio list and the b2 modal visually match Stitch side by side at 1280 px.
- [ ] Every Stitch class name used in the components resolves: no missing tokens, no default palette (`npm run lint:tokens` passes)
- [ ] StatusBadge renders glyph + label (+ % where applicable) for all 8 rows of the ARCHITECTURE §4 badge table
- [ ] `npm run lint`, `npm run typecheck`, `npm test` and `npm run build` pass
- [ ] `git check-ignore frontend/.env.example` prints nothing (the file is tracked); no frontend CLAUDE.md or AGENTS.md

**Required tests:** a render and variant test per primitive; Modal a11y (role, focus return, Esc); Tabs and SegmentedControl keyboard navigation; PasswordField show/hide; StatusBadge table-driven test; `cn`/`format` unit tests.

**Recommended models**
- **Plan:** Opus 5.5 · medium. The token mapping to Tailwind v4 needs care, but it's mechanical.
- **Implement:** Sonnet 5.5 · high. About 25 components converted with pixel-level fidelity and tests.

---

## Part 0C: App shell, API relay, API client, CI
**Status:** [ ] Not started
**Goal:** the three page layouts; the single-origin API relay (the core of the free topology); the base API client; and a CI pipeline that also proves the Cloudflare build works on Linux.
**Depends on:** 0A, 0B.
**Stitch files to convert:** app shell (sidebar + top bar) from `b1_home_feed`; `MarketingNav`/`MarketingFooter` from `a1_logged_out_home`; auth card layout from `a2_sign_up`.

**Frontend scope**
- **API relay** `src/app/api/[...path]/route.ts`, per ANALYSIS d / ARCHITECTURE §1:
  - handles all methods; allow-lists request headers; sets `X-RZ-Proxy-Secret` and `X-RZ-Client-IP`
  - streams bodies (`duplex:'half'`), `redirect:'manual'`
  - copies back every `Set-Cookie` via `getSetCookie()`
  - ~70 s timeout, returning `503 backend_waking`
  - never forwards `Host` or hop-by-hop headers
- `src/lib/api/client.ts`: relative `/api` base, JSON helpers, error normalisation for both the DRF and allauth shapes, and a 401 hook (refresh is wired in Part 1). `types.ts` holds the Post and User shapes from ARCHITECTURE §9.
- `src/lib/auth/AuthProvider.tsx` skeleton: in-memory token store, plus a refresh-lock helper built on the Web Locks API.
- **Shell components:**
  - `AppShell`: ≥1280 px full rail; 768–1279 px icon dock; <768 px top bar + bottom nav
  - `Sidebar`: Home, Search, Notifications, Profile, **New post**, a Moderation link placeholder, Settings, user card
  - `TopBar`: search input → `/search?q=`
  - `MobileNav`, `AuthLayout`, `MarketingNav`, `MarketingFooter`
- Route groups `(marketing)`, `(auth)`, `(app)` with placeholder pages; a basic `not-found`.
- OpenNext setup:
  - `wrangler.jsonc`: `name: "rumor-zero"`, `nodejs_compat`, assets binding, `vars.BACKEND_ORIGIN` placeholder
  - `open-next.config.ts` (default cache, **no R2**)
  - `initOpenNextCloudflareForDev()`
  - scripts `preview`/`deploy`/`upload`/`cf-typegen`. They run on Linux only; don't run them on Windows.
- `playwright.config.ts` (webServer starts Django + Next) and `e2e/smoke.spec.ts`.

**Backend scope:** none beyond what E2E needs (e.g. a CI env file built from `.env.example`).

**CI** `.github/workflows/ci.yml`, on push and PR:
- **backend:** ubuntu, Python 3.13, `postgres:18` + `redis` services; ruff, pytest, makemigrations check
- **frontend:** Node 24, `npm ci`, lint, typecheck, lint:tokens, vitest, `next build`, `npx @opennextjs/cloudflare build`
- **e2e:** Playwright chromium against both servers

All three jobs run on test values only; no secrets.

**API endpoints:** none new (the relay forwards `/api/health/`).

**Acceptance criteria**
- [ ] With Django running, `http://localhost:3000/api/health/` returns Django's JSON through the relay
- [ ] The backend receives the correct `X-RZ-Client-IP` and secret; spoofed client headers from the browser are dropped
- [ ] Multiple `Set-Cookie` headers survive the relay; with the backend stopped, the relay returns `503 {"code":"backend_waking"}`
- [ ] The shell matches Stitch b1 at 1280 px and is usable at 1024 px (icon dock) and 390 px (bottom nav); the current page has `aria-current="page"`
- [ ] The Playwright smoke test passes locally
- [ ] After you push, all CI jobs are green on GitHub, including the OpenNext build on Linux

**Required tests:** relay unit tests with mocked `fetch` (header allow-list, secret and IP injection, cookie passthrough, timeout → 503, method and body passthrough); API client error normalisation; shell render tests (nav items, active state, responsive variants); E2E smoke.

**Recommended models**
- **Plan:** Opus 5.5 · high. The relay, cookies and client-IP trust are subtle and security-relevant.
- **Implement:** Sonnet 5.5 · high. Many moving parts, but each is well specified.

---

## Part 1: Auth core (sign up, log in, tokens, log out)
**Status:** [ ] Not started
**Goal:** email + username + password sign-up with Turnstile; login; a 15-min access token in memory; a 14-day refresh token in an httpOnly cookie; logout; and unverified accounts treated as read-only.
**Depends on:** 0C.
**Stitch files to convert:** `a2_sign_up`, `a3_log_in` (plus the app-shell unverified banner). The Google button is visually present but hidden until Part 3.

**Backend scope**
- django-allauth **headless** configured per ARCHITECTURE §7: `app` client, JWT strategy with HS256 from `JWT_SIGNING_KEY`, headless-only. Mount it under `/api/auth/`, confirm the exact paths, and update ARCHITECTURE §7 and §9.
- Signup fields email/username/password; login by email.
- **Turnstile** server-side verification on signup, with the fallback described in ARCHITECTURE §7.
- **Refresh-cookie adapter** `apps/accounts/cookies.py`: strips `refresh_token` from responses, sets the `rz_refresh` cookie, injects it on refresh, and checks Origin + `X-Requested-With`. Plus our `POST /api/auth/logout/`.
- `GET /api/v1/auth/username-available/?u=` (throttled, validates format and reserved words).
- `GET /api/v1/me/` returning id, username, display_name, email, is_email_verified, role, has_usable_password, google_connected, and `admin_url` for staff only.
- `IsEmailVerified` permission (403 `email_unverified`).
- `ACCOUNT_RATE_LIMITS` on the real client IP.
- `EMAIL_PROVIDER` switch (console / brevo via anymail / file for E2E). Allauth sends the verification email on signup; its template is branded in Part 2.

**Frontend scope**
- `/signup` (a2):
  - debounced username availability check
  - PasswordStrengthMeter (one consistent scale)
  - Turnstile widget (explicit render; test key locally)
  - field errors, submit loading state
- `/login` (a3): error banner; no "remember me" and no attempt counter.
- `AuthProvider` completed:
  - refresh on load, scheduled refresh 60 s before expiry
  - Web Locks serialisation across tabs
  - one retry on 401
  - logout
- Route guard: `(app)` pages that need a user redirect to `/login?next=…`.
- `UnverifiedBanner` in AppShell.
- The user menu has **Log out**.

**API endpoints:** allauth `…/auth/signup`, `…/auth/login`, `…/tokens/refresh` · `POST /api/auth/logout/` · `GET /api/v1/auth/username-available/` · `GET /api/v1/me/`.

**Acceptance criteria**
- [ ] Sign-up (test Turnstile key) logs you in; the "Verify your email" banner shows; the verification email appears in the `runserver` console
- [ ] `refresh_token` never appears in any JSON body, JS-readable cookie, or local/session storage. `rz_refresh` is HttpOnly, SameSite=Lax, `Path=/api/auth/`, has no Domain, and is Secure when `AUTH_COOKIE_SECURE=True`.
- [ ] A page reload keeps you logged in; logout clears memory and the cookie; the old refresh token then fails
- [ ] Refresh and logout return 403 without the correct `Origin` or `X-Requested-With`
- [ ] Stored password hashes start with `argon2$argon2id$`
- [ ] Duplicate email, taken or invalid username, weak password and a failed Turnstile each show the right field error
- [ ] Repeated failed logins are rate-limited per real client IP (through the relay)
- [ ] Unverified users get 403 `email_unverified` on a verified-only endpoint
- [ ] Two tabs open at token expiry both stay logged in (no rotation race)

**Required tests**
- Backend: signup, login, refresh and logout API; cookie attributes; the CSRF checks; username availability (case, reserved words, format); Turnstile verification mocked (pass/fail/missing); Argon2; rate limiting; `/me` fields including staff-only `admin_url`; `IsEmailVerified`.
- Frontend: SignupForm/LoginForm validation and error rendering; AuthProvider timers and the lock (fake timers); username-check debounce.
- E2E: sign up → banner → reload still logged in → log out.

**Recommended models**
- **Plan:** Opus 5.5 · xhigh. Security-critical, and it integrates allauth headless JWT with a custom cookie adapter.
- **Implement:** Opus 5.5 · high. Correctness matters more than speed in auth code.

---

## Part 2: Email verification & password reset
**Status:** [ ] Not started
**Goal:** the complete email flows from guide §4.3: verification (24-hour links), resend, and forgot/reset password with no account enumeration.
**Depends on:** 1.
**Stitch files to convert:** `a4_verify_email`, `a5_forgot_password`, `a6_reset_password`.

**Backend scope**
- `HEADLESS_FRONTEND_URLS` pointing at `FRONTEND_ORIGIN`.
- Branded plain-text + HTML templates: "Rumor Zero", no fabricated org names.
- `email_confirmed` signal → `is_email_verified=True`.
- Resend throttled.
- Password reset with login-on-reset, revoking other sessions.
- An anymail Brevo configuration test using anymail's test backend.
- `EMAIL_PROVIDER=file` for E2E, writing emails to a git-ignored temp folder.

**Frontend scope**
- `/verify-email`: check your inbox, resend with a 60 s countdown, "Continue browsing read-only".
- `/verify-email/[key]`: verifying / verified ("Start posting") / expired-invalid ("Send a new link").
- `/forgot-password`: idle and sent states are separate, and the sent message is identical whether or not the account exists.
- `/reset-password/[key]`: form; mismatch, weak and expired states; success leads to a logged-in session.
- Resend action in the UnverifiedBanner.

**API endpoints:** allauth `…/auth/email/verify`, `…/auth/email/verify/resend`, `…/auth/password/request`, `…/auth/password/reset`.

**Acceptance criteria**
- [ ] The console link verifies the account; the banner disappears; verified-only actions work
- [ ] A link older than 24 h, or one already used, shows the expired state with a working resend
- [ ] Forgot-password responses are identical for existing and non-existing emails (status and body)
- [ ] Reset logs you in, and previously issued refresh tokens stop working
- [ ] Emails come from `DEFAULT_FROM_EMAIL` and link to `FRONTEND_ORIGIN` only

**Required tests:** verify flow; expiry with time control; resend throttle; reset flow, token revocation and enumeration-safe responses; email subject, from and link host; frontend state components; E2E: sign up → read the email file → open the link → verified → post button enabled.

**Recommended models**
- **Plan:** Opus 5.5 · high. The enumeration-safety and session-revocation edge cases need careful design.
- **Implement:** Sonnet 5.5 · high. It follows the patterns set in Part 1.

---

## Part 3: Continue with Google
**Status:** [ ] Not started
**Goal:** one-click Google sign-in and sign-up (guide §4.4) via Google Identity Services ID tokens, verified by allauth.
**Depends on:** 1. You need a Google OAuth client ID (ENV_GUIDE §1.6).
**Stitch files to convert:** the Google button and "or" divider in `a2_sign_up` and `a3_log_in`.

**Backend scope**
- allauth Google provider configured from settings (client ID only, no secret); the `…/auth/provider/token` flow.
- Auto-connect to an existing account by verified email.
- An adapter that generates a unique username for new Google users (c-29) and sets `is_email_verified=True`.
- Disabled cleanly when `GOOGLE_OAUTH_CLIENT_ID` is empty.
- `/me.google_connected`.

**Frontend scope:** `GoogleButton` (loads the GIS script only on auth pages, renders Google's button, sends the credential to the API); hidden when `NEXT_PUBLIC_GOOGLE_CLIENT_ID` is empty; errors for a closed popup, a failed sign-in, or rejected account linking.

**API endpoints:** allauth `…/auth/provider/token`.

**Acceptance criteria**
- [ ] A new Google user is created with a generated username, verified, and logged in (refresh cookie set)
- [ ] An existing email/password user signing in with the same Google email ends up in the **same** account
- [ ] Wrong-audience, expired or forged ID tokens are rejected with 400
- [ ] It works end to end on `http://localhost:3000` with your client ID (manual check)

**Required tests:** backend with Google token verification mocked (new user, link, wrong `aud`, `email_verified=false`, expired); username generation uniqueness; frontend button visibility and callback. E2E isn't feasible for real Google, so use the manual checklist above.

**Recommended models**
- **Plan:** Opus 5.5 · high. Account linking and takeover edge cases need careful thought.
- **Implement:** Sonnet 5.5 · medium. Small surface area once the plan exists.

---

## Part 4: Posts (composer + Recent feed)
**Status:** [ ] Not started
**Goal:** create opinion/fact posts with the selector and see them in a reverse-chronological public feed (guide roadmap step 3). Fact posts stay `pending`; the pipeline comes in Part 9.
**Depends on:** 1.
**Stitch files to convert:**
- `b2_post_composer_modal`: minus emergency mode and the source field.
- `b1_home_feed`: the page layout, PostCard, and the **Recent** tab. The inline composer is replaced by a trigger that opens the modal.

**Backend scope**
- `posts.Post` with **every** column from ARCHITECTURE §2 except `search_vector` (Part 12). Check constraints and indexes as listed.
- `posts.services.create_post`: opinion → `published`, fact → `pending`; `fact_posts_per_day` quota from PlatformSettings; throttle `post_create`.
- Post serializer (ARCHITECTURE §9 shape).
- `GET/POST /api/v1/posts/`: global Recent feed, cursor pagination, excluding removed and deleted posts.
- `GET /api/v1/me/fact-quota/`.
- Basic admin registration.

**Frontend scope**
- `/home` with Tabs: Recent now; Following arrives in Part 6.
- `FeedList`: cursor LoadMore, skeletons, empty and error states.
- `PostCard`: every status variant via StatusBadge/VerdictStripe; fact vs opinion typography.
- `ComposerModal`:
  - text with a 500-char counter
  - required Opinion/Fact segmented control
  - quota line "n/10 fact posts left today"
  - disabled with a verify prompt for unverified users
  - submitting and error states
- The shell's "New post" button opens the composer.
- Optimistic insert at the top of the feed.

**API endpoints:** `POST /api/v1/posts/`, `GET /api/v1/posts/?cursor=`, `GET /api/v1/me/fact-quota/`.

**Acceptance criteria**
- [ ] An opinion appears as OPINION in italic serif; a fact appears with CHECKING FACTS… and a neutral stripe
- [ ] Unverified users can't post: the UI explains why and the API returns 403
- [ ] Posting without a type, empty, or over 500 chars is blocked on both client and server
- [ ] The 11th fact post of the day is refused with a clear message; the quota line updates
- [ ] Load more never duplicates or skips posts when new ones arrive meanwhile
- [ ] DB constraints reject an opinion with `verified_*` or a fact with `published`

**Required tests:** model constraints; `create_post` (status by type, quota, throttle); feed ordering, exclusion and cursor stability; query count constant for 20 posts; frontend Composer validation and states, PostCard variants, FeedList pagination; E2E: log in → post a fact → CHECKING FACTS… in the feed.

**Recommended models**
- **Plan:** Opus 5.5 · high. The central schema (status constraints, indexes, future fields) is decided here.
- **Implement:** Sonnet 5.5 · high. Substantial but well specified UI and API work.

---

## Part 5: Post detail, sharing, deletion, status polling
**Status:** [ ] Not started
**Goal:** a shareable, indexable post page (guide §1.1), author soft-delete (D6), and live badge updates by polling (guide §5.1 step 5).
**Depends on:** 4.
**Stitch files to convert:** `b3_post_detail_forensic_proof`. Only the claim header, author row, verdict block and action bar; the comments area is Part 7. Drop the chart, ledger, sources and hashes.

**Backend scope**
- `GET /api/v1/posts/{id}/`:
  - deleted → 404
  - removed → tombstone payload, content hidden except to the author
- `DELETE /api/v1/posts/{id}/`: author only; sets `deleted_at`.
- `GET /api/v1/posts/status/?ids=`: at most 50 ids; uncached; returns status, confidence and verdict_source only.

**Frontend scope**
- `/p/[id]` with **light SSR**: `generateMetadata` (title = excerpt + " · Rumor Zero", description = status label, OG tags) plus the claim text.
- `PostDetail`: big claim; verdict explanation per status ("Checked automatically · 94% confidence" / "Reviewed by a moderator" + `verdict_note`).
- "Copy link"; Delete (own post, confirmation modal).
- `useStatusPolling`: visible tab only, 10 s backing off to 60 s, stops after 10 min. Used by the feed and the detail page.
- PostCards link to the detail page.

**API endpoints:** `GET/DELETE /api/v1/posts/{id}/`, `GET /api/v1/posts/status/`.

**Acceptance criteria**
- [ ] `curl` of `/p/<id>` returns HTML containing the claim text and the correct `<title>`/OG tags
- [ ] Changing a post's status in the Django shell updates the badge in an open tab without a reload
- [ ] Polling pauses on a hidden tab and stops after 10 min
- [ ] After the author deletes a post it's gone from feeds and detail (404) but still visible in the admin
- [ ] A removed post shows the tombstone to the public

**Required tests:** detail visibility matrix (anonymous / author / other × each status and deleted); delete permissions; status endpoint (limits, exclusions, query count); `useStatusPolling` with fake timers and visibility changes; PostDetail states; E2E: create → open detail → copy link.

**Recommended models**
- **Plan:** Sonnet 5.5 · high. Standard work, but the SSR-vs-CPU-limit trade-off needs attention.
- **Implement:** Sonnet 5.5 · medium. Straightforward once planned.

---

## Part 6: Profiles, follows, Following feed
**Status:** [ ] Not started
**Goal:** public profiles, follow/unfollow, follower and following lists, and the fan-out-on-read Following feed with a short cache (guide §9.2).
**Depends on:** 4.
**Stitch files to convert:**
- `c1_user_profile`: header, counts, post list. Drop the side widgets and trust metrics.
- `c3_following_list`: tabs and user rows. Drop the chips and metrics.
- `b1_home_feed`: the Following tab.

**Backend scope**
- `social.Follow`: unique pair, no self-follow check.
- `POST/DELETE /api/v1/users/{u}/follow/`: idempotent.
- `GET /api/v1/users/{u}/`: display name, bio, joined date, counts (followers / following / posts / verified / false), `is_following`, `is_me`.
- `…/posts/`: cursor; excludes removed and deleted.
- `…/followers/`, `…/following/`.
- `GET /api/v1/feed/`: followed + own posts; first page cached per user for `FEED_CACHE_SECONDS`; cache busted when you post or change a follow.

**Frontend scope**
- `/u/[username]` (light SSR header): ProfileHeader with Follow button or "Edit profile" (→ `/settings`, Part 14); post list with filter chips All / Facts / Opinions.
- `/u/[username]/followers` and `/following` with Tabs; `UserRow` + `FollowButton` (optimistic, with rollback).
- The Following tab on `/home`, with the empty state "Follow people to see their posts here" → Recent.

**API endpoints:** the users/follow endpoints above, plus `GET /api/v1/feed/`.

**Acceptance criteria**
- [ ] Follow and unfollow are idempotent; self-follow returns 400; counts update
- [ ] The Following feed shows only followed accounts + your own posts, newest first; your new post shows immediately despite the cache
- [ ] An unknown username returns 404; lookup is case-insensitive
- [ ] List endpoints use a constant number of queries

**Required tests:** constraints; follow API idempotency; feed composition, caching and invalidation; profile counts; query counts; FollowButton optimistic and rollback; E2E: A follows B → B posts → A sees it under Following.

**Recommended models**
- **Plan:** Sonnet 5.5 · high. The feed caching and invalidation details matter.
- **Implement:** Sonnet 5.5 · medium. Standard social-graph CRUD.

---

## Part 7: Likes & comments
**Status:** [ ] Not started
**Goal:** likes with DB-enforced uniqueness and flat comments (guide §3.3, §9).
**Depends on:** 5.
**Stitch files to convert:** `b3_post_detail_forensic_proof` (discussion section: composer + list; no Reply, no comment IDs or likes); action bars in `b1_home_feed` and `a1_logged_out_home`.

**Backend scope**
- `social.Like` + `POST/DELETE /api/v1/posts/{id}/like/`.
- `social.Comment`:
  - `GET` (oldest first, cursor) and `POST` (verified only, ≤500 chars, throttle `comment`) on `/api/v1/posts/{id}/comments/`
  - `DELETE /api/v1/comments/{id}/` for your own comments
  - `is_hidden` excluded from lists
- `like_count`, `comment_count` and `liked_by_me` annotated into the Post serializer.
- CommentAdmin with a "Hide" action.

**Frontend scope:** `LikeButton` (optimistic; filled glyph in `secondary`), comment count on cards; `CommentList` + `CommentComposer` on `/p/[id]` (counter, Ctrl+Enter to submit, delete own, empty state).

**API endpoints:** the like and comment endpoints above.

**Acceptance criteria**
- [ ] Like toggling is idempotent and counts stay correct under concurrent requests
- [ ] Unverified users get 403; comments over 500 chars are rejected
- [ ] Hidden comments disappear for everyone but staff
- [ ] Feed queries stay constant with annotations

**Required tests:** constraint and race tests, API permissions, query counts, frontend components; E2E: like + comment on a post.

**Recommended models**
- **Plan:** Sonnet 5.5 · medium. Well-understood CRUD.
- **Implement:** Sonnet 5.5 · medium. Well-understood CRUD.

---

## Part 8: Reporting & threshold
**Status:** [ ] Not started
**Goal:** one report per user per post; a windowed, brigading-resistant threshold that sends posts to review while keeping them visible (guide §6; ARCHITECTURE §5).
**Depends on:** 5.
**Stitch files to convert:** `d1_report_post_modal`, with plain-language reasons (ANALYSIS b-5).

**Backend scope**
- `reports.Report` exactly per ARCHITECTURE §2.
- `POST /api/v1/posts/{id}/report/` implementing ARCHITECTURE §5: `select_for_update`, `report_count`, `counts_toward_threshold`, window count.
- Create `apps/pipeline/routing.py` with `merge_flag`, `enter_review` and `apply_report_threshold` (the pipeline part is added in Part 9).
- `posts.services` owns the status write.
- `reported_by_me` in the serializer.
- Read-only ReportAdmin.

**Frontend scope:** `ReportModal`:
- 5 reasons; the details textarea is required for "Something else"
- states: submitting, success toast, **"You reported this"** (disabled), "Verify your email to report", own post (no report action)

The Report action sits in the PostCard overflow menu and on the detail page.

**API endpoints:** `POST /api/v1/posts/{id}/report/`.

**Acceptance criteria**
- [ ] 5 counting reports within 24 h move the post to UNDER REVIEW (`flagged_reason=reports`); it stays visible
- [ ] Reports outside the window, from new inactive accounts, or dismissed don't count
- [ ] Reporting twice returns 409 and shows "You reported this"; reporting your own post → 403; a removed or deleted post → 404
- [ ] The 11th report in an hour → 429
- [ ] Concurrent reports can't skip the threshold (a threaded transaction test)

**Required tests:** window boundaries (time-controlled), account-weighting rules, `merge_flag`/`enter_review` unit tests, concurrency, API errors, ReportModal states; E2E: report flow.

**Recommended models**
- **Plan:** Opus 5.5 · high. Concurrency, the time window and anti-brigading rules are easy to get subtly wrong.
- **Implement:** Sonnet 5.5 · high. The plan pins down the tricky parts.

---

## Part 9: Fact-check pipeline stub + routing
**Status:** [ ] Not started
**Goal:** the fixed pipeline contract (guide §7.1), a deterministic stub, the corrected routing logic (c-3), and a DB-backed queue processed without Celery or workers (c-21), so verdict badges go live.
**Depends on:** 8.
**Stitch files to convert:** none new. Verify the verified, false and under-review badge and card states from `b1_home_feed` and `b3_post_detail_forensic_proof` against real data.

**Backend scope**
- `apps/pipeline/contract.py`: validated dataclasses.
- `clients.py`: `StubPipelineClient` (rules in ARCHITECTURE §6) and `HttpPipelineClient` (tested with a mocked HTTP layer).
- `routing.apply_pipeline_result`.
- `processor.process_pending` with `FOR UPDATE SKIP LOCKED`, retries, backoff and max attempts.
- Inline kick on commit (daemon thread, closes its DB connection).
- `manage.py process_pending [--loop --interval N]`.
- `POST /api/internal/tick/` (secret; small batch; returns `{"processed": n}`).
- Confidence threshold read from PlatformSettings.

**Frontend scope:** verdict explanation copy per `verdict_source`; confirm the polling from Part 5 picks up changes.

**API endpoints:** `POST /api/internal/tick/`.

**Acceptance criteria**
- [ ] Locally, a fact containing `#true` becomes VERIFIED 95% within seconds; `#false` becomes FALSE 92%; `#unsure` becomes UNDER REVIEW (pipeline)
- [ ] With the inline kick off, `process_pending` or the tick clears the backlog
- [ ] **Every pipeline-related row of the ARCHITECTURE §4 table has a passing test**, including a late result on a reported post, moderator-decided posts ignored, removed posts ignored, and inconclusive-with-high-confidence → review
- [ ] Client errors are retried with backoff; after 5 attempts the post goes to review
- [ ] The tick needs the secret (403 otherwise) and finishes in under 30 s for 10 posts
- [ ] Two concurrent processors never handle the same post

**Required tests:** contract validation; stub determinism; exhaustive routing table tests; processor retries and backoff (time-controlled); SKIP LOCKED concurrency; tick auth; frontend badge copy per status and source; E2E: post a `#true` fact → badge becomes VERIFIED.

**Recommended models**
- **Plan:** Opus 5.5 · xhigh. The status state machine is the product's core logic, and the guide's version had bugs.
- **Implement:** Opus 5.5 · high. Concurrency and state-transition correctness justify the stronger model.

---

## Part 10: Human review panel (Django Admin)
**Status:** [ ] Not started
**Goal:** the moderation panel from guide §8 with two roles, the review queue, bulk actions, a complete audit trail, and runtime-editable thresholds (c-13).
**Depends on:** 9.
**Stitch files to convert:** none. `d2_moderator_peer_review_queue` is **reference only** for filters, sorting and actions.

**Backend scope**
- `moderation.ModerationAction` (append-only, from/to status, post snapshot).
- `moderation.services`: `mark_verified`, `mark_false`, `dismiss_reports`, `remove`, `escalate`. Each is transactional, applies ARCHITECTURE §4, and logs.
- `PostAdmin` review queue per ARCHITECTURE §8: list columns, filters, search, inlines, bulk actions with a confirmation form for `verdict_note`/notes; verdict actions for facts only.
- Also: ReportAdmin; ModerationActionAdmin (read-only, full access seniors only); CommentAdmin hide; UserAdmin (role editable by seniors only); PlatformSettings admin (seniors only).
- A Groups and permissions data migration.
- Site header "Rumor Zero moderation".

**Frontend scope:** a "Moderation" sidebar link for staff (from `/me.admin_url`, opens in a new tab); hidden for everyone else.

**API endpoints:** none new (the admin is server-rendered).

**Acceptance criteria**
- [ ] Moderators can review and act, but can't edit roles or PlatformSettings, delete users, or see the full audit log. Seniors can do all of that.
- [ ] Every bulk action produces the ARCHITECTURE §4 result and exactly one `moderation_actions` row per post, with correct from/to status
- [ ] Verified/false actions aren't offered for opinion posts
- [ ] Dismiss reports restores `pre_review_status` (or leaves `pipeline` when the flag was `both`), and those reports stop counting
- [ ] The queue page with 100 flagged posts uses a bounded number of queries

**Required tests:** each service × each starting state; the permission matrix per role through the admin test client; audit rows; query counts; sidebar link visibility.

**Recommended models**
- **Plan:** Opus 5.5 · high. Permissions and audit correctness have legal weight (guide §16).
- **Implement:** Sonnet 5.5 · high. Django Admin configuration, well specified.

---

## Part 11: Appeals & removed-post tombstones
**Status:** [ ] Not started
**Goal:** the "Request another look" path for authors of false-labelled posts (guide §8.4, c-7) and proper tombstones for removed posts.
**Depends on:** 10.
**Stitch files to convert:** the "Request another look / appeal" button in `b3_post_detail_forensic_proof`; the removed tombstone card in `c1_user_profile` (with no appeal on removals in the MVP).

**Backend scope**
- `moderation.Appeal`.
- `POST /api/v1/posts/{id}/appeal/`: author only, `verified_false` only, one per post, throttle `appeal` → `enter_review(APPEAL)`.
- Admin appeal inline and filter; resolution through the Part 10 actions sets the appeal status and links the `ModerationAction`.
- The different-moderator rule (seniors exempt).
- `can_appeal` / `appeal_status` for the author only.

**Frontend scope:** `AppealModal` (optional reason ≤500 chars, states); an APPEAL PENDING chip for the author; the outcome shown on the detail page; `RemovedPostCard` (public and author variants) on the profile and detail pages.

**API endpoints:** `POST /api/v1/posts/{id}/appeal/`.

**Acceptance criteria**
- [ ] Only the author of a `verified_false` post can appeal, once (others 403, a second appeal 409)
- [ ] The appealed post appears in the admin queue as `appeal`; the moderator who made the original call can't resolve it unless senior
- [ ] Overturning gives VERIFIED, upholding keeps FALSE; the author sees the outcome

**Required tests:** API rules, service transitions, the moderator rule, serializer fields per viewer, AppealModal and chip; E2E: the author files an appeal (resolved through a service fixture).

**Recommended models**
- **Plan:** Sonnet 5.5 · high. Builds directly on the Part 10 services.
- **Implement:** Sonnet 5.5 · medium. Small, well-bounded feature.

---

## Part 12: Search
**Status:** [ ] Not started
**Goal:** Postgres full-text search over posts, plus people search (guide §10), with no new service.
**Depends on:** 6.
**Stitch files to convert:** `b4_search_results`: query box, Posts/People tabs, filter chips, result cards, load more. Drop Primary Sources, certainty sort and the contributor spotlight.

**Backend scope**
- `search_vector` `GeneratedField` + GIN index migration.
- `GET /api/v1/search/`:
  - `type=posts`: `websearch` query, `SearchRank`, filters `post_type` and `status`, excludes removed and deleted
  - `type=users`: prefix match on username and display name
  - Pagination: bounded offset (max 5 pages), because rank order can't use a cursor. Documented deviation.
  - Throttled per IP.

**Frontend scope:** `/search` (from the top bar): tabs; chips All / Facts / Opinions / Verified / False / Under review; results with query terms highlighted using a safe text-splitting util (no HTML); UserRows; empty and no-results states; load more.

**API endpoints:** `GET /api/v1/search/`.

**Acceptance criteria**
- [ ] "running" finds "run" (stemming); `EXPLAIN` shows the GIN index being used
- [ ] Removed and deleted posts never appear; filters combine correctly
- [ ] An empty query shows the empty state (API 400)

**Required tests:** search API (stemming, ranking, filters, exclusions); an EXPLAIN index-usage test; user prefix search; the highlight util (escaping, no injection); SearchResults component; E2E: find a known post.

**Recommended models**
- **Plan:** Sonnet 5.5 · high. The FTS details (GeneratedField, ranking, index usage) need care.
- **Implement:** Sonnet 5.5 · medium. Contained scope.

---

## Part 13: Notifications
**Status:** [ ] Not started
**Goal:** the DB-backed notifications from guide §11, polled every 30 s while the tab is visible.
**Depends on:** 7, 10, 11 (all the event sources).
**Stitch files to convert:** `c4_notifications`. The item types are rebuilt for the MVP and there are no filter tabs.

**Backend scope**
- `notifications.Notification`.
- `notifications.services.notify()`, called explicitly (no signals) from: follow, like, comment, pipeline verdict and under-review, moderator remove and verdict, appeal resolved.
- Dedupe follow and like; no self-notifications.
- `GET /api/v1/notifications/` (cursor), `GET …/unread-count/` (indexed, ≤2 queries, uncached), `POST …/mark-read/` (`ids` or `all`).

**Frontend scope:** `/notifications`: items with a glyph, actor initials, post excerpt, relative time and unread dot; mark all as read; mark read on click. A sidebar unread badge via `useUnreadCount` (30 s, visible-only). Empty state.

**API endpoints:** the three notification endpoints above.

**Acceptance criteria**
- [ ] Each event creates exactly one notification for the right recipient; none for your own actions; repeated like/unlike doesn't spam
- [ ] The unread count uses ≤2 queries and polling stops on a hidden tab

**Required tests:** one creation test per event type, dedupe, API, NotificationItem variants, hook timers; E2E: B likes A's post → A sees the badge and the item.

**Recommended models**
- **Plan:** Sonnet 5.5 · medium. The hooks into existing services are straightforward.
- **Implement:** Sonnet 5.5 · medium. Straightforward.

---

## Part 14: Account settings, data export, account deletion
**Status:** [ ] Not started
**Goal:** users can edit their profile, manage their password, download their data, and delete their account (guide §16 GDPR/CCPA note).
**Depends on:** 6, 7.
**Stitch files to convert:** `c2_account_settings`, subset only (ANALYSIS b-1).

**Backend scope**
- `PATCH /api/v1/me/`: display_name, username (validated, unique), bio ≤280.
- `POST /api/v1/me/password/`: only if the password is usable.
- `GET /api/v1/me/export/`: JSON of your own profile, posts, comments, likes, follows, reports and appeals.
- `DELETE /api/v1/me/`:
  - confirmed by password, or by typing your username for Google-only accounts
  - cascades your content
  - moderation logs keep their snapshots
  - logs you out

**Frontend scope:** `/settings` with sections:
- Profile (display name, username, bio with counter)
- Account (email read-only with a verified chip; change password, or "Signed in with Google")
- Your data (Download JSON)
- Danger zone (delete modal with typed confirmation)

Plus toasts and field errors.

**API endpoints:** the four `/me` endpoints above.

**Acceptance criteria**
- [ ] Profile edits show up everywhere; a taken username gives a field error
- [ ] The export contains all of your own data and nothing private about anyone else
- [ ] Deletion removes the user and their content, logs them out, and the audit trail keeps its post snapshots

**Required tests:** API validation, export contents and privacy, deletion cascade and audit retention, forms; E2E: edit profile → export → delete account.

**Recommended models**
- **Plan:** Opus 5.5 · medium. Deletion cascades and privacy correctness deserve the stronger model.
- **Implement:** Sonnet 5.5 · medium. Standard forms and endpoints.

---

## Part 15: Landing & static pages
**Status:** [ ] Not started
**Goal:** the public face: a landing page, "How verification works", Privacy and Terms (required by Google OAuth and guide §16), error pages, and proper titles everywhere.
**Depends on:** 4 (the landing preview uses the Recent feed).
**Stitch files to convert:** `a1_logged_out_home`; `design/stitch/code.html` (layout for the taxonomy table and FAQ only, with copy rewritten); marketing footer.

**Backend scope:** none.

**Frontend scope**
- `/`: prerendered. Hero, 3 feature cards in plain language, a live preview of 4 recent posts fetched client-side, "© 2026 Rumor Zero", no fabricated organisations or people. Logged-in visitors see "Go to your feed".
- `/how-it-works`: the status table rendered with the real StatusBadges, the lifecycle, and an FAQ with real answers (why opinions aren't checked, reports, appeals, the pipeline).
- `/privacy`, `/terms`: placeholder text clearly marked **"needs legal review"**.
- `not-found` and `error` pages.
- `<title>` = "<Page> · Rumor Zero" on every route; favicon (text-based until D9 is decided).

**API endpoints:** none new.

**Acceptance criteria**
- [ ] The landing page matches the a1 layout, and none of the Stitch sample names or organisations appear anywhere
- [ ] `next build` output marks these pages as static
- [ ] Every route has a proper title; Lighthouse accessibility ≥ 95 on `/`

**Required tests:** render tests for each page; E2E: landing → how it works → sign up navigation.

**Recommended models**
- **Plan:** Sonnet 5.5 · low. Content and layout only; the decisions are already made.
- **Implement:** Haiku 4.5 (no effort setting). Static markup built from existing components, where a fast model is enough.

---

## Part 16: Security pass, load test, E2E hardening
**Status:** [ ] Not started
**Goal:** guide roadmap step 9. Verify the security checklist, find slow endpoints before users do, and make the full E2E suite a gate.
**Depends on:** 1–15. Needs k6 (SETUP A6).
**Stitch files to convert:** none.

**Backend scope**
- Go through ARCHITECTURE §12 point by point.
- `check --deploy` clean.
- Security headers and cookie flags verified by tests; admin path confirmed.
- Throttle review; secret-leak scan of the repo (patterns); logging review (no tokens or PII).
- `seed_demo` command (dev-only; refuses when DEBUG=False) creating around 10k posts.
- `.github/dependabot.yml` (pip, npm, github-actions, weekly).
- `pip-audit`/`npm audit`, triaged.

**Frontend scope:** a Content-Security-Policy in `next.config.ts` headers that allows only self, Turnstile and Google Identity Services; verify there are no violations and no `dangerouslySetInnerHTML`; the full E2E journey suite.

**Load test:** `loadtest/*.js` k6 scripts (feed read 50 VUs, post create, report burst) against the local stack with seeded data; `EXPLAIN` on the hot queries.

**Acceptance criteria**
- [ ] Every ARCHITECTURE §12 row has evidence (a test or a documented check)
- [ ] CSP is active, and Turnstile + Google still work under it
- [ ] Locally, with 10k posts: feed and detail p95 < 300 ms, 0 errors; hot queries use indexes
- [ ] Dependabot is configured; no unresolved high or critical advisories (or they're documented)
- [ ] The full E2E suite is green in CI

**Required tests:** security header and cookie tests, the CSP test, the E2E suite, k6 thresholds codified in the scripts.

**Recommended models**
- **Plan:** Opus 5.5 · **max** (session-only). The docs recommend `max` for finding security vulnerabilities, and this is the dedicated audit.
- **Implement:** Opus 5.5 · high. Fixes may touch sensitive code across parts.

---

## Part 17: Deploy backend (Render, Neon, Upstash, Brevo, Sentry)
**Status:** [ ] Not started
**Goal:** the Django API live on free tiers, deployed only after CI passes.
**Depends on:** 16. You do the account and dashboard steps in ENV_GUIDE §2.0–2.6; Claude prepares the config and checklists and **never handles secret values**.
**Stitch files to convert:** none.

**Backend scope**
- `render.yaml` Blueprint: rootDir `backend`, build and start commands from ENV_GUIDE §2.6, health check path, auto-deploy after checks; env var **keys** only, with secrets marked `sync: false`.
- A production settings review.
- Anymail Brevo backend; Sentry.
- A staff-only "send test error" management command.
- Deploy runbook notes in `docs/`.

**Frontend scope:** none.

**Acceptance criteria**
- [ ] `<BACKEND>/api/health/` returns 200; `/api/health/deep/` with the secret returns 200 (Neon + Upstash reachable)
- [ ] Admin login works at `<BACKEND>/<ADMIN_URL_PATH>` with the superuser created as in ENV_GUIDE §2.6
- [ ] A verification email arrives via Brevo at a Gmail **and** an Outlook test inbox (check spam; note the result)
- [ ] A Sentry test error shows up in the `rumor-zero-api` project
- [ ] Render Auto-Deploy is set to "After CI Checks Pass"
- [ ] The BACKEND URL is filled in ARCHITECTURE §0

**Required tests:** CI stays green; a settings test asserting production flags when DEBUG=False; a smoke script (`curl` checks) documented in the runbook.

**Recommended models**
- **Plan:** Opus 5.5 · high. Free-tier gotchas (SMTP block, no shell, sleep, build limits) must all be handled.
- **Implement:** Sonnet 5.5 · medium. Mostly configuration and documentation.

---

## Part 18: Deploy frontend, keep-alive & monitoring
**Status:** [ ] Not started
**Goal:** the site live on Cloudflare Workers with real Turnstile and Google keys, keep-alive and monitoring in place (guide roadmap step 10, §15.3), and a verified production smoke test.
**Depends on:** 17. You do ENV_GUIDE §2.7–2.12.
**Stitch files to convert:** none.

**Frontend scope**
- `wrangler.jsonc` final (`vars.BACKEND_ORIGIN = <BACKEND>`); the Workers Builds settings documented.
- A Playwright production smoke test (`PLAYWRIGHT_BASE_URL=<FRONTEND>`): landing loads, the signup page shows the Turnstile widget, `/api/health/` through the relay works.
- Check Workers observability for CPU-limit (1102) errors on `/p/[id]`.

**Backend and ops scope**
- `.github/workflows/keepalive.yml`: runs daily plus `workflow_dispatch`; calls `/api/health/deep/` with the secret header; fails on non-200.
- UptimeRobot monitor; cron-job.org tick job.
- A very light k6 smoke run against production.

**Acceptance criteria**
- [ ] `<FRONTEND>` loads; signup with the real Turnstile widget and email login both work; Google sign-in works on the production origin
- [ ] Browser devtools show `rz_refresh` as a host-only HttpOnly Secure cookie on the `<FRONTEND>` host, and it survives a reload
- [ ] UptimeRobot is green for 24 h with no Render cold start in that window; cron-job.org returns 200 hourly; the keepalive workflow is green
- [ ] No Worker 1102 CPU-limit errors over 24 h of normal use
- [ ] The FRONTEND URL is filled in ARCHITECTURE §0; the ENV_GUIDE master table matches reality

**Required tests:** the production smoke suite, the keepalive workflow run, the k6 smoke run.

**Recommended models**
- **Plan:** Opus 5.5 · high. Cross-service wiring (origins, keys, cookies, build vs runtime variables) is where deployments fail.
- **Implement:** Sonnet 5.5 · medium. Configuration plus a small workflow and tests.
