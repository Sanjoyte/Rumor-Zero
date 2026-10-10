# Rumor Zero: Build plan (task.md)

## How to use this file

1. Choose **one** active agent. Never run Claude Code and Codex concurrently in the same checkout.
2. Start it in the repo root. It must read `AGENTS.md`, `docs/agents/HANDOFF.md`,
   `docs/agents/MEMORY.md`, this part and the relevant architecture sections before planning.
3. Set the part's **PLAN** model and reasoning effort from the tables below, then enter plan mode:
   - Claude Code: `/model …`, `/effort …`, then `/plan` (or Shift+Tab).
   - Codex: `/model`, `/reasoning`, then `/plan`.
4. Prompt: **`Plan Part <ID> from task.md. Do not implement yet.`** Review and revise the plan.
   After you approve it, the agent saves it under `docs/agents/plans/` and links it from
   `docs/agents/HANDOFF.md`.
5. Switch to the **IMPLEMENT** model/effort if the table differs, then prompt:
   **`Implement only the approved Part <ID> plan, validate it, update task.md and HANDOFF.md, then stop.`**
6. If the active agent is near a usage/context limit, tell it:
   **`Checkpoint now for a handoff. Update HANDOFF.md and stop without starting another step.`**
7. Start the other agent and prompt:
   **`Continue Part <ID> from docs/agents/HANDOFF.md and the linked approved plan. Verify the current diff and test state first; continue only from the recorded next action.`**
8. When the part is done, the agent runs its required tests, ticks its acceptance criteria, updates
   both status locations in this file, records final validation in `HANDOFF.md`, and stops.
9. You review the diff and tests, then perform all git operations yourself. Start a fresh session
   for the next part (`/clear` in Claude; a new Codex chat/session in Codex).

**Models and effort** (checked against the Claude Code docs on 2026-09-29):
- `/model` aliases: `opus` → Opus 5.5, `sonnet` → Sonnet 5.5, `haiku` → Haiku 4.5, `opusplan`.
- `/effort` levels: `low`, `medium`, `high`, `xhigh`, `max` on Opus 5.5 and Sonnet 5.5 (both default to `medium`). `max` is **session-only**. Haiku 4.5 has no effort setting.

### Codex model choices for ChatGPT Plus

Checked against official OpenAI documentation on 2026-09-30. The project default in
`.codex/config.toml` is `gpt-6.1-sol` with `high` reasoning. Use `/model` and `/reasoning` to apply
the per-part choices below. The picker is authoritative for your account. If Astra is unavailable
or your Plus allowance is low, replace it with `gpt-6.1-sol` at the same effort (or one level
higher). If GPT-6.1 Sol has not reached your client, use `gpt-6-sol` at the same effort.

- **GPT-6.1 Sol (`gpt-6.1-sol`):** default for planning and implementation; best balance for long, coordinated
  engineering work.
- **GPT-6 Astra (`gpt-6-astra`):** reserve for the five highest-risk plans/audits. It uses the Plus allowance much
  faster, so do not use it for routine implementation.
- **GPT-6 Luna (`gpt-6-luna`):** use for bounded, mechanical implementation only after a stronger model has fixed
  the plan. Escalate to Sol if tests fail for a non-obvious reason.
- Avoid `ultra` on Plus for these parts. It delegates to subagents and spends allowance quickly;
  the explicit Claude↔Codex handoff already provides continuity.

| Part | Codex plan | Codex implement | Why |
|---|---|---|---|
| 0A | GPT-6.1 Sol · high | GPT-6.1 Sol · medium | Foundational schema/settings; implementation is standard once fixed |
| 0B | GPT-6.1 Sol · medium | GPT-6.1 Sol · high | Large coordinated design-system conversion |
| 0D | GPT-6.1 Sol · medium | GPT-6.1 Sol · medium | Bounded asset pipeline, but exactness matters |
| 0C | GPT-6.1 Sol · high | GPT-6.1 Sol · high | Relay, cookies, proxy trust and CI interact |
| 1 | GPT-6 Astra · high | GPT-6.1 Sol · xhigh | Security-critical auth design; long implementation |
| 2 | GPT-6.1 Sol · high | GPT-6.1 Sol · high | Enumeration safety and token/session edge cases |
| 3 | GPT-6.1 Sol · high | GPT-6.1 Sol · medium | Account-linking risks, small implementation surface |
| 4 | GPT-6.1 Sol · high | GPT-6.1 Sol · high | Central post schema plus substantial API/UI work |
| 5 | GPT-6.1 Sol · medium | GPT-6.1 Sol · medium | Standard detail/share/delete/polling flow |
| 6 | GPT-6.1 Sol · high | GPT-6.1 Sol · medium | Feed query and cache invalidation need care |
| 7 | GPT-6.1 Sol · medium | GPT-6 Luna · high | Well-bounded CRUD after the interfaces are fixed |
| 7B | GPT-6.1 Sol · high | GPT-6.1 Sol · high | Mixed-feed cursor stability is subtle |
| 8 | GPT-6.1 Sol · xhigh | GPT-6.1 Sol · high | Concurrency, windows and anti-brigading |
| 9 | GPT-6 Astra · xhigh | GPT-6.1 Sol · xhigh | Core state machine and concurrent transitions |
| 10 | GPT-6.1 Sol · high | GPT-6.1 Sol · high | Permissions and audit correctness |
| 11 | GPT-6.1 Sol · high | GPT-6.1 Sol · high | Restore path added to moderation state machine |
| 11B | GPT-6 Astra · xhigh | GPT-6.1 Sol · xhigh | Public, reversible and auditable reputation ledger |
| 11C | GPT-6 Astra · xhigh | GPT-6.1 Sol · xhigh | Highest-harm feature; time and abuse rules |
| 11D | GPT-6.1 Sol · medium | GPT-6 Luna · high | Mostly presentational work plus two read endpoints |
| 12 | GPT-6.1 Sol · high | GPT-6.1 Sol · medium | PostgreSQL FTS and index behavior |
| 13 | GPT-6.1 Sol · medium | GPT-6 Luna · high | Straightforward service hooks and UI |
| 14 | GPT-6.1 Sol · high | GPT-6.1 Sol · medium | Privacy and deletion cascades |
| 14B | GPT-6.1 Sol · high | GPT-6.1 Sol · high | Untrusted image processing and resource limits |
| 15 | GPT-6 Luna · medium | GPT-6 Luna · high | Static content built from established components |
| 16 | GPT-6 Astra · max | GPT-6.1 Sol · xhigh | Dedicated security/load/E2E audit and fixes |
| 17 | GPT-6.1 Sol · high | GPT-6.1 Sol · medium | Free-tier deployment constraints and configuration |
| 18 | GPT-6.1 Sol · high | GPT-6.1 Sol · medium | Cross-service origins, cookies, variables and monitoring |

If allowance permits, use **GPT-6 Astra · high** for a final read-only review of Parts 1, 9, 11B,
11C and 16 after their required tests pass. Put findings in the current approved plan/handoff; do
not let the review expand the part's scope without user approval.

**Status legend:** `[ ] Not started` · `[~] In progress` · `[x] Done (date)` · `[!] Blocked (reason)`

| Part | Title | Depends on | Status |
|---|---|---|---|
| 0A | Backend foundation | SETUP Part A | [x] Done (2026-09-30) |
| 0B | Frontend foundation & design system | SETUP Part A | [x] Done (2026-10-01) |
| 0D | Brand assets & Logo component | 0B | [x] Done (2026-10-01) |
| 0C | App shell, API relay, API client, CI | 0A, 0B, 0D | [x] Done (2026-10-01) |
| 1 | Auth core: sign up, log in, tokens, log out | 0C | [x] Done (2026-10-03) |
| 2 | Email verification & password reset | 1 | [x] Done (2026-10-07) |
| 3 | Continue with Google | 1 | [x] Done (2026-10-08) |
| 4 | Posts: composer + Recent feed | 1 | [x] Done (2026-10-09) |
| 5 | Post detail, sharing, deletion, status polling | 4 | [x] Done (2026-10-09) |
| 6 | Profiles, follows, Following feed | 4 | [x] Done (2026-10-09) |
| 7 | Likes & comments | 5 | [x] Done (2026-10-10) |
| 7B | Bookmarks & reposts | 6, 7 | [x] Done (2026-10-10) |
| 8 | Reporting & threshold | 5 | [x] Done (2026-10-10) |
| 9 | Fact-check pipeline stub + routing | 8 | [ ] |
| 10 | Human review panel (Django Admin) | 9 | [ ] |
| 11 | Appeals & removed-post tombstones | 10 | [ ] |
| 11B | Credibility score | 7B, 10, 11 | [ ] |
| 11C | Emergency posts | 9, 10, 11B | [ ] |
| 11D | Charts & stats | 7B, 11B | [ ] |
| 12 | Search | 6, 11B | [ ] |
| 13 | Notifications | 7, 7B, 10, 11, 11C | [ ] |
| 14 | Account settings, data export, deletion | 6, 7, 7B, 11B, 11D | [ ] |
| 14B | Photo avatars | 14 | [ ] |
| 15 | Landing & static pages | 4, 11B, 11C | [ ] |
| 16 | Security pass, load test, E2E hardening | every part above | [ ] |
| 17 | Deploy backend (Render, Neon, Upstash, Brevo, Sentry) | 16 | [ ] |
| 18 | Deploy frontend, keep-alive & monitoring | 17 | [ ] |

The order follows the guide's MVP roadmap (§18): setup → auth → posts/feed → follow/like/comment → reports → pipeline stub → review panel → search + notifications → security + load test → launch.

Adjustments for real dependencies:
- Part 0 is split into four. 0D (the logo) comes before the shell, so every brand mark uses the real logo from the start (D9).
- Auth and social are split into sessions of one sitting each.
- Appeals (guide §8.4) follow the review panel.
- The Stitch-only features (D5, changed 2026-09-29; ANALYSIS f) come right after what they depend on:
  - 7B after the social graph and the action bar;
  - 11B–11D after moderation and appeals, because the credibility score and the emergency rules react to verdicts, removals and appeals;
  - 14B after the settings page.
- Their columns are created early (posts in Part 4, users and PlatformSettings in 0A), so the later parts add logic, not risky schema changes.
- Notifications come after every event source exists.
- Deployment is last.
- Suffixed parts (0D, 7B, 11B–11D, 14B) keep the existing numbers unchanged. A planned "0E: swap in the SVG logo" was dropped because `design/logo.svg` arrived before 0D.

---

## Part 0A: Backend foundation
**Status:** [x] Done (2026-09-30)
**Goal:** a running Django project with env-driven settings, the final custom User model (before the first migration), health endpoints, shared API plumbing, local Postgres/Redis, and a green test and lint setup.
**Depends on:** SETUP.md Part A (Python 3.13, Docker); ENV_GUIDE §1.1–1.4 done (`backend/.env` exists).
**Stitch files to convert:** none.

**Backend scope**
- Setup commands:
  - in `backend/`: `py -3.13 -m venv .venv`, then `django-admin startproject rumor_zero .`
  - apps `core`, `accounts`: create `apps/__init__.py` and the empty target folder first (`New-Item -ItemType Directory apps\<name>`; `startapp` refuses a missing destination), run `python manage.py startapp <name> apps/<name>`, then change `name` in its `apps.py` from `"<name>"` to `"apps.<name>"`
  - straight after scaffolding, and after every `makemigrations`: `ruff check --fix . ; ruff format .`. Django writes single-quoted, unformatted code and only auto-runs black, which isn't installed. Migrations stay in ruff's scope.
- Files:
  - `requirements.txt` / `requirements-dev.txt` pinned per SETUP B1/B2 (re-check the latest patch versions)
  - `pyproject.toml` (ruff, pytest)
  - `conftest.py`, `.python-version` (3.13)
  - root `compose.yaml`: `postgres:18` (volume at `/var/lib/postgresql`) + `redis:8-alpine`, both with healthchecks
  - root `.gitattributes`: **already exists** (added 2026-09-30: `* text=auto eol=lf` plus `binary` for PDF, image and font types). Keep it, and add any new binary type to it.
- `settings.py`:
  - reads env with django-environ (process env wins over `.env`)
  - `backend/.env` is optional: it's loaded only if present, and a missing required variable fails by **name** (never its value). Tests never depend on the developer's real `.env`; they set what they need through the `settings` fixture or `monkeypatch`, and CI builds its env file from `.env.example` (Part 0C).
  - `DATABASE_URL` with `CONN_MAX_AGE=60`, `CONN_HEALTH_CHECKS=True`
  - Redis cache when `REDIS_URL` is set (`protocol: 2`), else LocMem
  - Argon2 first in `PASSWORD_HASHERS`
  - WhiteNoise; admin at `ADMIN_URL_PATH`
  - production security settings when not DEBUG: `SECURE_PROXY_SSL_HEADER`, HSTS, secure cookies
  - Sentry initialised only if `SENTRY_DSN` is set, with `send_default_pii=False`, `max_request_body_size="never"`, `include_local_variables=False` and `event_scrubber=EventScrubber(denylist=DEFAULT_DENYLIST + ["x-rz-proxy-secret", "x-rz-cron-secret", "x-rz-client-ip"])` (both from `sentry_sdk.scrubber`). `send_default_pii=False` alone would still send the three `X-RZ-*` headers, request bodies and frame locals (ARCHITECTURE §12).
  - logging that never prints secrets
- `accounts.User`, exactly as in ARCHITECTURE §2:
  - UUID, lowercase username validation plus reserved names, lowercase email, role → Groups/`is_staff` sync, `is_email_verified`, `display_name`, `bio`
  - the fields later parts use, created now so the user table never needs a risky change: `avatar_version` + `avatar_uploads_blocked` (14B), `reputation_score` (default 50, check 0–100) + `reputation_sample` (11B), `emergency_blocked_until` (11C)
  - plus the manager, an admin, and the initial migration
- `core`:
  - `/api/health/`: no DB and no session, so **0 queries**
  - `/api/health/deep/`: needs `X-RZ-Cron-Secret`; runs `SELECT 1` and a cache set/get
  - `ClientIPMiddleware` (ARCHITECTURE §1)
  - DRF defaults: JSON only, the custom exception handler that adds `code`, a cursor pagination class returning `next_cursor`, and throttle scopes from ARCHITECTURE §3
  - `PlatformSettings` singleton with every field in ARCHITECTURE §2 (including the six emergency limits used from 11C), a data migration seeding it from env (a missing `EMERGENCY_*` variable falls back to its default), and a cached accessor. Seniors-only admin permissions come in Part 10.

**Frontend scope:** none.
**API endpoints:** `GET /api/health/`, `GET /api/health/deep/`.

**Acceptance criteria**
- [x] `docker compose up -d` shows both services healthy; `python manage.py migrate` works on an empty DB
- [x] `AUTH_USER_MODEL = "accounts.User"` from the very first migration; `createsuperuser` works and that account can log into Django Admin
- [x] Changing `role` updates Group membership and `is_staff`; a superuser keeps `is_staff` whatever its role (`is_staff = is_superuser or role != user`)
- [x] A `reputation_score` outside 0–100 is rejected by the database; new users start at 50
- [x] `/api/health/` returns `{"status":"ok"}` with **0 queries**; `/api/health/deep/` returns 403 without the secret and 200 with it
- [x] `X-RZ-Client-IP` is honoured only with the correct `X-RZ-Proxy-Secret`
- [x] `python manage.py check --deploy` passes with production-like env values (DEBUG=False, secure cookies, HSTS)
- [x] `ruff check .`, `ruff format --check .`, `pytest` and `makemigrations --check --dry-run` are all clean
- [x] No secret appears in the repo; any new env var is added to `backend/.env.example` and ENV_GUIDE (no new variable was needed)

**Deviations and decisions (2026-09-30):**
- Admin login is by **email** (`USERNAME_FIELD="email"`), reserved usernames are an **exact-match** list, and groups are cumulative: both were user decisions, now in ARCHITECTURE §2.
- `compose.yaml` binds Postgres and Redis on `[::1]` as well as `127.0.0.1`. `localhost` resolves to `::1` first on Windows, and with nothing listening there libpq stalled for 8 s or more, so `makemigrations` appeared to hang. Ports stay loopback-only.
- `ClientIPMiddleware` trusts only the right-most `X-Forwarded-For` entry. An unparseable one leaves `REMOTE_ADDR` alone, because anything to its left is client-supplied (ARCHITECTURE §1).
- The role sync manages only the "Moderators" and "Senior moderators" groups and leaves other groups alone, instead of a blanket `groups.set()`.
- `PlatformSettings` fields carry an upper bound of 32767 (their column type), so the seed and the admin reject absurd values.
- `pytest` ignores WhiteNoise's "No directory at staticfiles" warning (`collectstatic` doesn't run in tests).

**Required tests:** user model (email/username normalisation, reserved names, role sync, a superuser keeping `is_staff` with `role = user` and after role changes, `reputation_score` range check), health endpoints (query count 0, secret check), ClientIPMiddleware (secret ok / wrong / missing), PlatformSettings accessor (seed including emergency defaults, caching), pagination output shape, exception handler `code`, Sentry scrubbing (a Sentry-shaped event with `X-Rz-Proxy-Secret`, `X-Rz-Cron-Secret` and `X-Rz-Client-Ip` headers comes out scrubbed, and the init options above are set; no DSN or network needed).

**Recommended models**
- **Plan:** Opus 5.5 · high. The custom user model and settings layout are painful to change after the first migration.
- **Implement:** Sonnet 5.5 · medium. Well-trodden Django scaffolding once the plan is fixed.

---

## Part 0B: Frontend foundation & design system
**Status:** [x] Done (2026-10-01)
**Goal:** a Next.js app whose Tailwind v4 theme **is** the Stitch design system, plus the tested UI primitive kit every later screen is built from.
**Depends on:** SETUP.md Part A (Node 24). Can run in parallel with 0A.

**Stitch files to convert**
- `design/stitch/DESIGN.md` (all tokens)
- Component sources:
  - `b1_home_feed`: PostCard (including the emergency card's violet stripe and EMERGENCY chip), StatusBadge, CategoryChip, Tabs
  - `b2_post_composer_modal`: Modal, SegmentedControl, Textarea + counter, Toggle (used by the emergency toggle in 11C)
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
  - Put `.env.example` back, append `!.env.example` to `frontend/.gitignore`, and confirm no nested `frontend/CLAUDE.md` or `AGENTS.md` exists.
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
  - Card, VerdictStripe (including the violet emergency stripe), StatusBadge (the ARCHITECTURE §4 badge table, including the EMERGENCY chip), CategoryChip
  - Avatar: an optional photo `src` (photos arrive in 14B), falling back to initials when there's no `src` or the image fails to load
  - Modal (native `<dialog>`: focus trap, Esc, `aria-modal`)
  - Alert, Toast, Skeleton, EmptyState, LoadMore, ProgressBar, PasswordStrengthMeter
- Helpers: `lib/cn.ts`, `lib/format.ts` (relative time, compact numbers).
- A **dev-only** gallery at `/dev/ui` showing every component and state. It 404s in production builds.
- Vitest + RTL + jest-dom setup; Prettier with the Tailwind plugin.

**Backend scope:** none. **API endpoints:** none.

**Acceptance criteria**
- [x] `/dev/ui` shows every primitive in every state. PostCard, the sign-up form fields, the d1 radio list and the b2 modal visually match Stitch side by side at 1280 px.
- [x] Every Stitch class name used in the components resolves: no missing tokens, no default palette (`npm run lint:tokens` passes)
- [x] StatusBadge renders glyph + label (+ % where applicable) for all 9 rows of the ARCHITECTURE §4 badge table, using the word FALSE (never "debunked")
- [x] PostCard shows the violet stripe and EMERGENCY chip for an active emergency, and the status colour otherwise
- [x] Avatar falls back to initials with no `src` and with a broken `src`
- [x] `npm run lint`, `npm run typecheck`, `npm test` and `npm run build` pass
- [x] `git check-ignore frontend/.env.example` prints nothing (the file is tracked); no nested frontend CLAUDE.md or AGENTS.md

**Deviations and decisions (2026-10-01):**
- **Scaffold in a temp folder.** `create-next-app` refuses a folder that holds `.env.example` *or* the real `.env.local`, so it ran with `--skip-install` in a scratch directory and the files were copied into `frontend/`. Neither env file was moved, read or edited. The flags differ from the plan text: `--turbopack` no longer exists (Turbopack is the default), and `--empty --no-react-compiler` were added.
- **Next 16.3.8 writes `frontend/AGENTS.md` and `CLAUDE.md` on every dev start**, even with `--no-agents-md`. `next.config.ts` sets `agentRules: false`; the generated files were deleted (hard rule 9).
- **Versions:** `next`/`eslint-config-next` 16.3.8, `vitest` 5.0.3 (SETUP said 5.0.2), `@testing-library/jest-dom` 7.0.1, `prettier` 3.9.9, `prettier-plugin-tailwindcss` 0.8.1, `jsdom` 30.1.1. Vite 8's own `@/` alias handling was not needed: `vitest.config.mts` aliases `@` directly, so `vite-tsconfig-paths` was **not** added.
- **`@tailwindcss/forms` 0.5.11, `strategy: "class"`** (decided by the user). Primitives add `form-input`, `form-checkbox`, `form-radio`, `form-select` and `form-textarea` themselves.
- **Password meter scale** (decided by the user): Weak / Fair / Good / Strong from a dependency-free `scorePassword()`; it is advisory and the Django validators stay authoritative.
- **PostCard** lives in `src/features/posts/PostCard.tsx` and is props-only (decided by the user). It has no action bar and no source line yet (Parts 4, 7, 7B). `DangerZone` and `Divider` are `ui/` primitives.
- **Tokens:** DESIGN.md has **49** colour tokens (ANALYSIS said 48). `--color-*`, `--font-*`, `--text-*`, `--radius-*` and `--shadow-*` are reset first. `shadow-sm` is overridden to Tailwind v3's lighter value because Stitch was built on v3.
- **Icon font:** `material-symbols/outlined.css` is imported into `@layer components` from `globals.css`. Its own rule is unlayered and would otherwise beat every `text-[1rem]` size utility.
- **Fixed while verifying in a real browser (headless Edge):** an `<img>` avatar that 404s before hydration never fired `onError` and showed a broken-image icon; the modal focused its Close button instead of the `data-autofocus` element (document order beat selector order).
- **Stitch vs docs:** where Stitch disagreed with itself the a2/d1 variant was used; FALSE claims are not struck through; labels say FALSE. Stitch's composer and report copy was rewritten per ANALYSIS b-5.
- **Not done (left for later parts):** the Material Symbols font is 4 MB (subset it in Part 16); toasts sit below an open `<dialog>` because the dialog uses the top layer (move the toast region to a popover if a toast must show over a modal); background scroll is not locked while a modal is open.

**Required tests:** a render and variant test per primitive; Modal a11y (role, focus return, Esc); Tabs and SegmentedControl keyboard navigation; PasswordField show/hide; StatusBadge table-driven test (including the emergency row); Avatar fallback; `cn`/`format` unit tests.

**Recommended models**
- **Plan:** Opus 5.5 · medium. The token mapping to Tailwind v4 needs care, but it's mechanical.
- **Implement:** Sonnet 5.5 · high. About 25 components converted with pixel-level fidelity and tests.

---

## Part 0D: Brand assets & Logo component
**Status:** [x] Done (2026-10-01)
**Goal:** one logo everywhere (D9). Every derived asset comes from one command and one master file, and one `<Logo/>` component is the only way the UI shows the brand. A later logo change is then: replace `design/logo.svg`, run one command.
**Depends on:** 0B. Runs before 0C, because the shell uses `<Logo/>`.
**Stitch files to convert:** none directly. The brand marks it replaces are applied in 0C and listed in ANALYSIS e.2:
- the sidebar wordmark in every app-shell file
- a1's "RUMOR ZERO" header/footer
- a3's `check` tile + wordmark + "Fact Social"
- the a4 `layers`, a5 `diamond` and a6 `lock` tiles

**Frontend scope**
- Add `sharp` 0.35.x as a devDependency (SETUP B3). Why: it renders the SVG master to PNG, with prebuilt Windows binaries. Only the brand script imports it, never app code or the Worker bundle.
- `frontend/scripts/brand/build-brand-assets.mjs` + `brand.config.json`, run as `npm run brand:build`, per ARCHITECTURE §14:
  - master `design/logo.svg`. The script **only reads** `design/`; it never writes, moves or deletes anything there. `design/logo.png` is not used.
  - **safety check first:** no `<script>`, `<foreignObject>`, `on*` attributes, external `href`/`xlink:href`, embedded bitmaps or `<text>`, and a `viewBox` must exist. Otherwise the build fails with a clear message.
  - wordmark: the SVG with its `viewBox` cropped to the artwork plus padding → `public/brand/logo.svg`
  - mark: the "0" in its own square `viewBox` → `public/brand/mark.svg`. The selector lives in the config (currently `path.cls-1`, the only path in the cyan class), and the build fails unless it matches exactly one `<path>`.
  - every asset in the ARCHITECTURE §14 table: `favicon.ico` (16/32/48, written by a small tested PNG-in-ICO helper), `icon.svg`, `apple-icon.png`, the three manifest icons, `opengraph-image.png` + `twitter-image.png` (+ `.alt.txt`), `email-logo.png`, `google-oauth-logo.png`, and `backend/apps/core/static/core/brand/logo-admin.png` (creating the folder if needed)
  - plates use `inverse-surface` `#283044`
  - `src/lib/brand-assets.json`: the generated list of assets, sizes and plate colour
  - prints the contrast table from ARCHITECTURE §14. It does not fail on the logo's own contrast (logotypes are exempt), but the numbers must match §14.
- `src/app/manifest.ts`: name and short name "Rumor Zero", theme/background colour from `brand-assets.json`, the three icons. The favicon, icon, apple-icon and Open Graph tags come from Next.js file conventions in `src/app/`.
- `src/components/ui/Logo.tsx`:
  - `variant="wordmark" | "mark"`, `size="sm" | "md" | "lg"` (24/36/48 px tall)
  - accessible name "Rumor Zero"; `decorative` gives `alt=""` when the name is written next to it
  - plain `<img>` with width and height (no layout shift, no `next/image` optimisation), never inlined SVG
- `lint:tokens` allowlist: only `src/lib/brand-assets.json` and `src/app/manifest.ts` may contain brand hex values.
- Guard test: nothing in `src/` except `Logo.tsx`, `brand-assets.json` and `manifest.ts` references `/brand/`, and nothing re-creates the old text wordmark.
- `/dev/ui` shows every Logo variant and size on `surface`, `surface-container-lowest` and `inverse-surface`.

**Backend scope:** none. The admin logo file is written here and used in Part 10.
**API endpoints:** none.

**Acceptance criteria**
- [x] `npm run brand:build` regenerates every asset in ARCHITECTURE §14 from `design/logo.svg`, and `git status` shows nothing changed under `design/`
- [x] A master with a `<script>`, an external link or a `<text>` element makes the build fail with a clear message
- [x] Sizes are exact:
  - favicon.ico holds 16/32/48
  - apple-icon is 180×180 and opaque
  - the manifest icons are 192, 512 and maskable 512, with the mark inside the 80 % safe zone
  - share images are 1200×630
  - the Google logo is 120×120 and under 1 MB
- [x] `next build` HTML contains the favicon, icon, apple-touch-icon, manifest and `og:image` tags
- [x] `<Logo/>` renders with the accessible name "Rumor Zero" (or `alt=""` when decorative) at every size, with no layout shift
- [x] The printed contrast table matches ARCHITECTURE §14
- [x] The guard test and `lint:tokens` pass; `npm run lint`, `typecheck`, `test` and `build` pass

**Deviations and decisions (2026-10-01):**
- **Icon plate shape** (decided by the user): `favicon.ico`, `icon.svg`, `icon-192.png` and `icon-512.png` use a rounded-square plate (22 % radius, transparent corners). `apple-icon.png`, `icon-maskable-512.png` and the wide plates are full-bleed squares/rectangles. ARCHITECTURE §14 records this.
- **`sharp` 0.35.5, exact pin.** SETUP said 0.35.4; 0.35.5 was already in `node_modules` as Next's optional dependency, so adding it as a devDependency only changed `package-lock.json` flags (`optional` → `devOptional` for sharp, `@img/colour`, `semver`). No new binary type for `.gitattributes`: `*.png` and `*.ico` were already binary, and SVG/JSON/`.alt.txt` are text.
- **`lint:tokens` allowlist is `src/lib/brand-assets.json` only.** `manifest.ts` reads its colours and icon paths from that JSON, so it contains no hex and no `/brand/` literal and needs no entry (task text listed both). `lint:tokens` now scans `.json` under `src/` so the allowlist entry is real.
- **No XML dependency.** `scripts/brand/svg.mjs` has a small tokenizer; the mark selector supports `tag.class` only. Class fills are inlined into the derived SVGs (no `<style>`). Artwork bounds are measured from a 4x render, not parsed from path data.
- **Extra safety checks** beyond the task list: `<tspan>`/`<textPath>`, `<iframe>`/`<embed>`/`<object>`/`<audio>`/`<video>`, DOCTYPE/ENTITY, `@import`, external `url()`, `data:` and `javascript:` values. Every problem is listed at once, with line numbers, and nothing is written.
- **Padding:** wordmark viewBox = artwork + 12 units on every side; mark viewBox = square around the "0" with 12 units clear (`brand.config.json`).
- **`brand-assets.json`** lists each asset with its repo-relative `file`, public `src` where there is one, and sizes read from the written PNG headers. `manifest.ts` uses the plate colour for `theme_color` and `background_color`.
- **`.alt.txt` files have no trailing newline** (Next copies them verbatim into `og:image:alt`; a newline showed up as "Rumor Zero
").
- **`metadataBase`** comes from the existing `NEXT_PUBLIC_SITE_URL` (no new env variable), so `og:image` and `twitter:image` are absolute.
- **No CI regenerate-and-diff check** (for 0C): PNG bytes can differ across OS/libvips builds. Tests check sizes, structure and the text outputs (`build.test.ts` fails if a committed SVG/JSON/txt asset is stale).
- **Verified in a real browser** (headless Edge, `/dev/ui#logo`): every Logo renders at exactly 24/36/48 px with its width from the artwork ratio, named "Rumor Zero" (`alt=""` when decorative), on all three surfaces. All 13 generated URLs answer 200 in `next dev` with the right content type.

**Required tests:** SVG safety check (each forbidden construct); mark extraction and viewBox cropping; ICO writer (header and entries); asset dimension tests that read PNG headers (no extra dependency); `brand-assets.json` shape; Logo render, sizes and accessible name; guard test.

**Recommended models**
- **Plan:** Sonnet 5.5 · medium. A small, well-bounded asset pipeline.
- **Implement:** Sonnet 5.5 · medium. Straightforward scripting plus one component.

---

## Part 0C: App shell, API relay, API client, CI
**Status:** [x] Done (2026-10-01)
**Goal:** the three page layouts; the single-origin API relay (the core of the free topology); the base API client; and a CI pipeline that also proves the Cloudflare build works on Linux.
**Depends on:** 0A, 0B, 0D.
**Stitch files to convert:** app shell (sidebar + top bar) from `b1_home_feed`; `MarketingNav`/`MarketingFooter` from `a1_logged_out_home`; auth card layout from `a2_sign_up`. Every brand mark in them (text wordmark, emblem tiles, "Fact Social") becomes `<Logo/>` (ANALYSIS e.2).

**Frontend scope**
- **API relay** `src/app/api/[...path]/route.ts`, per ANALYSIS d / ARCHITECTURE §1:
  - handles all methods; allow-lists request headers (including `If-None-Match` and `If-Modified-Since`, for cached profile photos); sets `X-RZ-Proxy-Secret` and `X-RZ-Client-IP`
  - streams bodies (`duplex:'half'`, also used for photo uploads in 14B), `redirect:'manual'`
  - copies back every `Set-Cookie` via `getSetCookie()`, plus an allow-list of response headers: `Content-Type`, `Content-Length`, `Cache-Control`, `ETag`, `Last-Modified`, `Content-Disposition`, `X-Content-Type-Options`, `Content-Security-Policy`, `Retry-After`
  - ~70 s timeout, returning `503 backend_waking`
  - never forwards `Host` or hop-by-hop headers
- `src/lib/api/client.ts`: relative `/api` base, JSON helpers, error normalisation for both the DRF and allauth shapes, and a 401 hook (refresh is wired in Part 1). `types.ts` holds the Post and User shapes from ARCHITECTURE §9.
- `src/lib/auth/AuthProvider.tsx` skeleton: in-memory token store, plus a refresh-lock helper built on the Web Locks API.
- **Shell components:**
  - `AppShell`: ≥1280 px full rail; 768–1279 px icon dock; <768 px top bar + bottom nav
  - `Sidebar`: `<Logo size="md"/>` at the top, then Home, Search, Notifications, Profile, Bookmarks (placeholder until 7B), **New post**, a Moderation link placeholder, Settings, user card. The icon dock shows `<Logo variant="mark"/>`.
  - `TopBar`: search input → `/search?q=`
  - `MobileNav` (top bar with `<Logo size="sm"/>`), `AuthLayout` (`<Logo size="lg"/>` on every auth card), `MarketingNav`, `MarketingFooter` (logo + "© 2026 Rumor Zero")
  - No text wordmark, no emblem tiles, no "Fact Social" or other taglines
- Route groups `(marketing)`, `(auth)`, `(app)` with placeholder pages; a basic `not-found`.
- OpenNext setup:
  - `wrangler.jsonc`: `name: "rumor-zero"`, `nodejs_compat`, assets binding, `vars.BACKEND_ORIGIN` placeholder
  - `open-next.config.ts` (default cache, **no R2**)
  - `initOpenNextCloudflareForDev()`
  - scripts `preview`/`deploy`/`upload`/`cf-typegen`. They run on Linux only; don't run them on Windows.
- `playwright.config.ts` (webServer starts Django + Next) and `e2e/smoke.spec.ts`.

**Backend scope:** none beyond what E2E needs (e.g. a CI env file built from `.env.example`).

**CI** `.github/workflows/ci.yml`, on push and PR:
- **backend:** ubuntu, Python 3.13, `postgres:18` + `redis` services; builds `backend/.env` from `backend/.env.example` (test values only; there is no real `.env` in CI), with the Postgres service using the example's user, password and database so `DATABASE_URL` needs no override; ruff, pytest, makemigrations check
- **frontend:** Node 24, `npm ci`, lint, typecheck, lint:tokens, vitest, `next build`, `npx @opennextjs/cloudflare build`
- **e2e:** Playwright chromium against both servers

All three jobs run on test values only; no secrets.

**API endpoints:** none new (the relay forwards `/api/health/`).

**Acceptance criteria**
- [x] With Django running, `http://localhost:3000/api/health/` returns Django's JSON through the relay
- [x] The backend receives the correct `X-RZ-Client-IP` and secret; spoofed client headers from the browser are dropped
- [x] Multiple `Set-Cookie` headers survive the relay; with the backend stopped, the relay returns `503 {"code":"backend_waking"}`
- [x] Cache headers and a `304 Not Modified` pass through the relay unchanged
- [x] The shell matches Stitch b1 at 1280 px and is usable at 1024 px (icon dock) and 390 px (bottom nav); the current page has `aria-current="page"`
- [x] Every brand mark in the shell, auth and marketing layouts is `<Logo/>` (the 0D guard test still passes)
- [x] The Playwright smoke test passes locally
- [x] After you push, all CI jobs are green on GitHub, including the OpenNext build on Linux

**Deviations and decisions (2026-10-01):**
- **User decisions:** the logged-out shell shows only Home and Search (plus Log in / Sign up); phones get a top bar and five bottom tabs (Home, Search, New post, Notifications, Profile) with an account sheet for Bookmarks, Settings and Moderation; marketing links go only to pages that exist (About, Community Guidelines, Press and Contact dropped). ARCHITECTURE §10 and ANALYSIS a.3 record them.
- **Request bodies are buffered (≤ 6 MB), not streamed** (the scope said `duplex:'half'` streaming). Django can't read chunked bodies and OpenNext buffers them on Workers anyway; the real-HTTP test proves bodies arrive with `Content-Length`. Over 6 MB → 413 `payload_too_large`.
- **Relay additions** (ARCHITECTURE §1, ANALYSIS d): `User-Agent` is forwarded; a `Location` pointing at the backend's own `/api/` is returned as a relative URL, any other is dropped; `Content-Length` is copied only without `Content-Encoding`; the 70 s timer covers the wait for headers only; an upstream non-JSON 502/503/504 also becomes `backend_waking`; `BACKEND_ORIGIN` must be https (http only for loopback).
- **`skipTrailingSlashRedirect: true`** in `next.config.ts`: Next's default redirect turned `/api/health/` into `/api/health`, which loops with Django's `APPEND_SLASH`. A `redirects()` rule keeps page URLs slash-less (`/home/` → `/home`, covered by E2E).
- **CI runs one OpenNext build step** (`npx opennextjs-cloudflare build` runs `next build` itself), covering both build items. Action majors: checkout, setup-python, setup-node and upload-artifact all `@v7`.
- **Versions:** `@opennextjs/cloudflare` 1.20.7, `wrangler` 4.145.0 (SETUP said 4.143.0), `@playwright/test` 1.63.0, all exact devDependencies. No new env variable.
- **First CI run (2026-10-01):** backend and e2e were green. The frontend job failed in its last step, the OpenNext build: `ERR_MODULE_NOT_FOUND: Cannot find package 'esbuild'`.
  - Cause: `@opennextjs/cloudflare` imports esbuild without declaring it (upstream #1339). `vite` 8's optional esbuild peer stops npm from hoisting the copy it relied on.
  - Fix: `esbuild` 0.28.1 as an exact devDependency (wrangler's version, one shared copy, `npm audit` clean). See SETUP B3 for when to remove it.
  - The OpenNext build was then run on Linux in a `node:24` container, from exactly the files CI checks out (no env files).
  - The next CI run (on `60cfffc`, "Fix: add missing esbuild dependency") passed all three jobs, as the user reported on 2026-10-01. The agent couldn't open the run itself: `gh` isn't installed and the repository is private.
- **Basic `not-found`, `error` and `global-error`** now (ARCHITECTURE §14 places their logo in 0C); Part 15 polishes them. Fonts moved to `src/app/fonts.ts` so `global-error` can reuse them. The root title template is `"%s · Rumor Zero"`.
- **The top-bar search box keeps b1's compact classes** instead of the 44 px `TextField`, so the bar matches Stitch.
- **`/dev/shell`** (dev-only, 404 in production) shows the shell with a sample user for the Stitch comparison, because there is no sign-in until Part 1. `?user=none` shows the logged-out shell.
- The toast region moved to `bottom-20 md:bottom-space-lg` so the phone bottom bar doesn't cover it.
- **Verified locally:** headless Edge at 1280 next to Stitch b1 (same rail, header and item geometry; differences are the planned logo, Bookmarks, "New post" and no Ledger pill); Playwright at 1024 and 390 (no horizontal overflow); a scratchpad echo backend for the header, cookie and 304 checks. ANALYSIS c-35's "CPU check" belongs to Part 18 and was reworded.

**Required tests:** relay unit tests with mocked `fetch` (request and response header allow-lists, secret and IP injection, cookie passthrough, 304 passthrough, timeout → 503, method and body passthrough); API client error normalisation; shell render tests (nav items, active state, responsive variants, logo placement); E2E smoke.

**Recommended models**
- **Plan:** Opus 5.5 · high. The relay, cookies and client-IP trust are subtle and security-relevant.
- **Implement:** Sonnet 5.5 · high. Many moving parts, but each is well specified.

---

## Part 1: Auth core (sign up, log in, tokens, log out)
**Status:** [x] Done (2026-10-03)
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
- [x] Sign-up (test Turnstile key) logs you in; the "Verify your email" banner shows; the verification email appears in the `runserver` console
- [x] `refresh_token` never appears in any JSON body, JS-readable cookie, or local/session storage. `rz_refresh` is HttpOnly, SameSite=Lax, `Path=/api/auth/`, has no Domain, and is Secure when `AUTH_COOKIE_SECURE=True`.
- [x] A page reload keeps you logged in; logout clears memory and the cookie; the old refresh token then fails
- [x] Refresh and logout return 403 without the correct `Origin` or `X-Requested-With`
- [x] Stored password hashes start with `argon2$argon2id$`
- [x] Duplicate email, taken or invalid username, weak password and a failed Turnstile each show the right field error
- [x] Repeated failed logins are rate-limited per real client IP (through the relay)
- [x] Unverified users get 403 `email_unverified` on a verified-only endpoint (a test-only view until Part 4 adds real ones)
- [x] Two tabs open at token expiry both stay logged in (no rotation race)

**Deviations and decisions (plan approved 2026-10-02; built 2026-10-03; all recorded in ARCHITECTURE §2/§3/§7/§9/§10/§12 and ANALYSIS c-18/d):**
- **User decisions:** superusers count as verified (`createsuperuser` + backfill migration `accounts.0002_verify_superuser_emails`); Turnstile fails closed ("We couldn't run the bot check. Try again in a minute."); a readable hint cookie `rz_session=1` lets anonymous page loads skip the refresh call.
- **`AuthApiMiddleware`** (`apps/accounts/middleware.py`) instead of a cookie adapter alone. Every request under `/api/auth/` passes through it:
  - only `auth/login`, `auth/signup` and `tokens/refresh` (POST) and our logout answer; everything else is 404;
  - **every** unsafe request needs `Origin == FRONTEND_ORIGIN` + `X-Requested-With: rumor-zero` (allauth parses `text/plain` bodies as JSON, so login and signup needed it too);
  - `meta.refresh_token`, `meta.session_token` (the raw session key) and `data.refresh_token` are stripped, and every body becomes JSON (the DEBUG 500 page printed cookies);
  - login, signup and refresh ignore `Authorization`/`X-Session-Token`, so the "409 when already authenticated" case can't happen. Its test became "a Bearer token on signup is ignored".
- **Turnstile is checked before allauth runs**, so a bot never learns "email taken". stdlib `urllib`, no new dependency. Failed checks count against the signup limit; a full limit answers 429 without calling Cloudflare.
- **Race-safe refresh** (`apps/accounts/tokens.py`): the session row is locked, and a rotated token keeps working for 60 s. A concurrency test with allauth's own strategy shows one tab losing its token without it.
- **Settings:** `HEADLESS_FRONTEND_URLS` moved here from Part 2 (headless-only mode refuses to send the verification email without them); `ACCOUNT_EMAIL_SUBJECT_PREFIX = "[Rumor Zero] "`; allauth's rate limits pinned; only allauth's auth backend; our `JWTAuthentication` (deleted/inactive user → 401, not 500). Startup guards: `JWT_SIGNING_KEY` ≥ 32 characters and ≠ `DJANGO_SECRET_KEY`; `FRONTEND_ORIGIN` a bare origin, https with `DEBUG` off; with `DEBUG` off, `AUTH_COOKIE_SECURE=True` and `EMAIL_PROVIDER=brevo`. `backend/.env.example`'s JWT placeholder grew from 30 to 40 characters. No new variable.
- **Frontend:** `RequestOptions.token: false` also skips the 401 refresh hook (the session's own `/me` call passes its token explicitly, so it can't deadlock on a refresh). The session logic is framework-free (`src/lib/auth/session.ts`); `AuthProvider` binds it. Login and logout are broadcast on `BroadcastChannel("rz-auth")`. The username check shows nothing while debouncing.
- **Copy:** a2 and a3 headings and subtitles kept; a2's "Protected by Turnstile" callout is the real widget; "Complexity metric" is "Password strength" (0B); the jargon footers, a3's attempt counter, "Remember me" and rate-limit notice are dropped (ANALYSIS b-2, b-5). "Forgot password?" waits for Part 2, the Google button for Part 3.
- **`Avatar` initials skip a leading "@"** (a one-line 0B fix): every new account has a blank display name, so the shell showed "@V".
- **Known until Part 2:** allauth's default verification email text names the backend host ("Hello from localhost:8000!"); its only link already points at `FRONTEND_ORIGIN`. Part 2 replaces the templates.
- **Verified locally:** curl against `runserver` (signup cookies, console email, rotation + 60 s grace, 403 without `Origin`/header, logout), 11 failed logins through the relay (the 11th gets `too_many_login_attempts`, a direct call from another address doesn't), Playwright and headless-Chromium screenshots next to Stitch a2/a3 at 1280 and 390 px (0 px overflow), the always-fail Turnstile secret, and the E2E suite in dev and CI mode. CI itself runs when you push: its E2E job needs `challenges.cloudflare.com` from the runner (browser and Django).

**Required tests**
- Backend: signup, login, refresh and logout API; cookie attributes; the CSRF checks; username availability (case, reserved words, format); Turnstile verification mocked (pass/fail/missing); Argon2; rate limiting; `/me` fields including staff-only `admin_url`; `IsEmailVerified`.
- Frontend: SignupForm/LoginForm validation and error rendering; AuthProvider timers and the lock (fake timers); username-check debounce.
- E2E: sign up → banner → reload still logged in → log out.

**Recommended models**
- **Plan:** Opus 5.5 · xhigh. Security-critical, and it integrates allauth headless JWT with a custom cookie adapter.
- **Implement:** Opus 5.5 · high. Correctness matters more than speed in auth code.

---

## Part 2: Email verification & password reset
**Status:** [x] Done (2026-10-07)
**Goal:** the complete email flows from guide §4.3: verification (24-hour links), resend, and forgot/reset password with no account enumeration.
**Depends on:** 1.
**Stitch files to convert:** `a4_verify_email`, `a5_forgot_password`, `a6_reset_password`.

**Backend scope**
- `HEADLESS_FRONTEND_URLS` pointing at `FRONTEND_ORIGIN`.
- Branded plain-text + HTML templates: "Rumor Zero", no fabricated org names. The HTML version shows the logo from `FRONTEND_ORIGIN/brand/email-logo.png` (0D; alt "Rumor Zero", width 160). The plain-text version has no image.
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

**API endpoints:** allauth `…/auth/email/verify` (POST), `…/auth/password/request` (POST), `…/auth/password/reset` (GET key check, POST) · ours: `POST /api/v1/me/verification-email/` (allauth's `…/auth/email/verify/resend` is the code-flow view and stays closed).

**Acceptance criteria**
- [x] The console link verifies the account; the banner disappears; verified-only actions work
- [x] A link older than 24 h, or one already used, shows the expired state with a working resend
- [x] Forgot-password responses are identical for existing and non-existing emails (status and body)
- [x] Reset logs you in, and previously issued refresh tokens stop working
- [x] Emails come from `DEFAULT_FROM_EMAIL` and link to `FRONTEND_ORIGIN` only (including the logo image URL)

**Deviations and decisions (plan approved 2026-10-07; built 2026-10-07; recorded in ARCHITECTURE §3/§7/§9/§10/§12/§14):**
- **User decisions (2026-10-06):**
  - Sign-up lands on `/verify-email` (a4), not `/home`; "Continue browsing read-only" goes on to `safeNextPath(?next=) ?? /home`.
  - New post is `aria-disabled` for unverified users (rail and bottom tab), and a click shows a toast.
  - Verification emails: 1 per 60 s per address plus 10 resends a day; reset requests: allauth's per-minute limits plus 10 a day per address and 50 a day per IP.
  - An unknown address gets no email (`ACCOUNT_EMAIL_UNKNOWN_ACCOUNTS=False`); the answer is identical.
- **Resend is our own endpoint** (`POST /api/v1/me/verification-email/`: 204 · 409 `already_verified` · 429 `verification_email_throttled`), not the task's `auth/email/verify/resend`, which is allauth's code-mode view.
- **Daily caps are separate allauth actions** (`confirm_email_daily`, `reset_password_daily`): allauth keys a rate's history by action and "per" type only, so a combined rate pruned the entries the day rate needs. Rule: never repeat a "per" type inside one action.
- **Verify is always anonymous** and its success (allauth: 401 with nobody logged in) is normalised to 200; the link never logs anyone in. The reset key has a header-based pre-check (`GET auth/password/reset` + `X-Password-Reset-Key`, forwarded by the relay and denied in Sentry), so a dead link shows the expired state before anyone types a password.
- **Reset links last 24 h** (`PASSWORD_RESET_TIMEOUT`, Django's default is 3 days). A reset deletes this browser's old session; other sessions die on their next refresh (changed auth hash).
- **Emails:** templates in `backend/templates/account/email/` (the `allauth` app precedes ours, so app templates would be shadowed); text + HTML, logo from `FRONTEND_ORIGIN/brand/email-logo.png`, no backend host, hex values copied from the Stitch tokens. `AccountAdapter.add_message()` is a no-op (it would set a `messages` cookie).
- **Found while testing:** allauth defers `jwt` and `cryptography`; two simultaneous first sign-ins on a cold server raced inside the import and answered 500. `AccountsConfig.ready()` now imports them (`test_startup.py`). The bug is older than this part (Part 1's E2E got lucky with fewer parallel sign-ups).
- **Frontend:** `signInWithToken` and a `user-changed` broadcast (the other tabs reload `/me` once, with no echo); `next-path` blocks `/reset-password` and `/verify-email/…`; key pages set `noindex` and `no-referrer`. The a4/a5/a6 emblem tiles, state switcher, "Simulate instant link click", "Secured Node", "Protocol standard", audit IDs and fabricated emails are dropped (ANALYSIS b-5); a6's "12 characters" is 8. "Forgot password?" sits in a3's options row under the password field (Stitch's place for it), not in the label row. The waiting Resend button is a4's tinted state.
- **Admin:** no "mark email verified" action (Part 10 follow-up). Out of scope: marking the email verified on a reset, a password-changed email (Part 14), `clearsessions` (Part 9/17). A provider failure on resend still answers 204 (the adapter swallows send errors, as at sign-up).
- **Verified:** see HANDOFF (backend 577 tests, frontend 708, E2E 15 in dev and CI mode, curl and browser checks recorded in `docs/test-command.md` Part 2). CI itself runs when you push.

**Required tests:** verify flow; expiry with time control; resend throttle; reset flow, token revocation and enumeration-safe responses; email subject, from and link host; frontend state components; E2E: sign up → read the email file → open the link → verified → post button enabled.

**Recommended models**
- **Plan:** Opus 5.5 · high. The enumeration-safety and session-revocation edge cases need careful design.
- **Implement:** Sonnet 5.5 · high. It follows the patterns set in Part 1.

---

## Part 3: Continue with Google
**Status:** [x] Done (2026-10-08). Acceptance criterion 4 (the real-Google check) is pending your manual check: `docs/test-command.md` Part 3, steps 6 to 8.
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
- [x] A new Google user is created with a generated username, verified, and logged in (refresh cookie set)
- [x] An existing email/password user signing in with the same Google email ends up in the **same** account (a Gmail or Workspace address; see the deviations)
- [x] Wrong-audience, expired or forged ID tokens are rejected with 400
- [ ] It works end to end on `http://localhost:3000` with your client ID (manual check). **Pending you:** needs a real Google account, so the agent could not run it. The real button renders (410×44 px, 0 px overflow at 1280 and 390 px), a click opens Google's own sign-in window, and closing it changes nothing; the sign-in itself is `docs/test-command.md` Part 3, steps 7 and 8.

**Deviations and decisions (plan approved 2026-10-08; built 2026-10-08 to 2026-10-09; recorded in ARCHITECTURE §2/§3/§7/§9/§10/§12 and ANALYSIS b-2, c-29 and the GoogleButton row):**
- **User decisions (2026-10-07):**
  - An **unverified** local account that matches the Google email is linked: its password becomes unusable (whoever signed up with someone else's address is locked out), the address is marked verified, and other sessions end at their next refresh. A verified one keeps its password.
  - Only addresses Google itself hosts link to an existing account: `@gmail.com`, or a token with an `hd` (Workspace) claim. Any other matching address answers 400 `google_link_requires_password`. A *new* person with any verified address can sign up. This narrows "auto-connect by verified email" above, following Google's ID-token guide.
  - Staff accounts (moderators, superusers) are never linked by email (400 `staff_password_login`); one that linked Google earlier still signs in.
  - The username comes from Google's **first name**, not the email local part (ANALYSIS c-29, b-2): `ada`, `ada_4821`, or `member_xxxxxx` for non-Latin or reserved names. The display name stays **blank**.
- **Google's own button** (an iframe), not Stitch's custom button with the inline "G": Google returns an ID token only from its own button. `design/` is untouched. a3's uppercase code-font "or" rule is the shared `Divider` (a2's style).
- **No close event:** Google gives its button no callback for a closed popup, so "errors for a closed popup" became "nothing happens".
- **Our shape check before allauth** (`apps/accounts/google.py`): allauth 65.19.5 answers 500 for a header without `kid` and for HS256 against the RSA key; both are 400 now. `process: "connect"` is refused (Part 14's).
- **The `login` rate bucket** (30/min per IP, shared with password logins) covers every Google attempt, valid or not: 429.
- **`/me` is two queries** (`google_connected` is a real `exists()`); two tests were renamed or changed from one query. ARCHITECTURE §9 says so.
- **`SocialAccount.extra_data`** keeps only `sub`, `email`, `email_verified` and `hd`. `SocialApp` and `SocialToken` are unregistered from the admin.
- **Built differently from the plan:** `GoogleButton` has no `context` prop (Google's `context` option only changes One Tap's text, which isn't used); the forms take an optional `googleClientId` prop for tests, like `siteKey`.
- **Found while testing:** with a made-up client ID the real Google script loads and logs "The given client ID is not found" with a 0×0 iframe, so the button is invisible until the ID is right (the guide's step 6 says so). `allauth` fetches Google's certificates on every sign-in (no cache; Part 16).
- **Not done (Part 14/16):** Settings "Signed in with Google", username rename, the "account connected" email, CSP and COOP for Google (ARCHITECTURE §12), caching Google's certificates, and a retry on a username or email race (an `IntegrityError` is still a 500).
- **Verified:** see HANDOFF (backend 704 tests, frontend 747, E2E 15 in dev and CI mode, curl and browser checks recorded in `docs/test-command.md` Part 3). The PowerShell blocks of that section were not run on Windows. CI itself runs when you push.

**Required tests:** backend with Google token verification mocked (new user, link, wrong `aud`, `email_verified=false`, expired); username generation uniqueness; frontend button visibility and callback. E2E isn't feasible for real Google, so use the manual checklist above.

**Recommended models**
- **Plan:** Opus 5.5 · high. Account linking and takeover edge cases need careful thought.
- **Implement:** Sonnet 5.5 · medium. Small surface area once the plan exists.

---

## Part 4: Posts (composer + Recent feed)
**Status:** [x] Done (2026-10-09; built 2026-10-08 to 2026-10-09)
**Goal:** create opinion/fact posts with the selector, with up to 5 optional sources (URL or DOI) on fact posts (ARCHITECTURE §4c), and see them in a reverse-chronological public feed (guide roadmap step 3). Fact posts stay `pending`; the pipeline comes in Part 9.
**Depends on:** 1.
**Stitch files to convert:**
- `b2_post_composer_modal`, including the optional "Primary source URL or DOI" field (shown for Fact only), turned into a list of up to 5 fields. The emergency toggle stays hidden until 11C.
- `b1_home_feed`: the page layout, PostCard (with a one-line source under fact claims, styled like the evidence drawer: the first source, then "+N more"), and the **Recent** tab. The inline composer is replaced by a trigger that opens the modal.

**Backend scope**
- `posts.Post` with **every** column from ARCHITECTURE §2 except `search_vector` (Part 12), including the `sources` array, emergency and `pre_removal_status` columns (emergency logic arrives in 11C, removal appeals in 11). Check constraints and indexes as listed. Add `django.contrib.postgres` to `INSTALLED_APPS` for `ArrayField` (part of Django; no new dependency).
- `posts.validators`: source normalisation and validation exactly per ARCHITECTURE §4c (URL or DOI, per element); the list rules (at most 5, no duplicates after normalisation); `source_kind(value)` derives `url`/`doi`. **Never fetched.**
- `posts.services.create_post`:
  - opinion → `published`, fact → `pending`
  - `fact_posts_per_day` quota from PlatformSettings; throttle `post_create`
  - accepts `sources` (fact only, 0–5)
  - refuses `is_emergency=true` with 400 `emergency_unavailable` until 11C
- Post serializer (ARCHITECTURE §9 shape, all fields present; counts and flags that later parts fill are `0` / `false` / `null` for now).
- `GET/POST /api/v1/posts/`: global Recent feed in the ARCHITECTURE §9 feed shape (`{pinned: [], results: [{kind:"post", …}], next_cursor}`), cursor pagination, excluding removed and deleted posts.
- `GET /api/v1/me/fact-quota/`.
- Basic admin registration.

**Frontend scope**
- `/home` with Tabs: Recent now; Following arrives in Part 6.
- `FeedList`: cursor LoadMore, skeletons, empty and error states.
- `PostCard`: every status variant via StatusBadge/VerdictStripe; fact vs opinion typography; `SourceLink` line (first source's host or `doi.org/…`, then "+N more" when there are more; `rel="nofollow ugc noopener noreferrer"`). "+N more" becomes a link to the detail page in Part 5.
- `ComposerModal`:
  - text with a 500-char counter
  - required Opinion/Fact segmented control
  - optional "Source (URL or DOI)" list for Fact only: one field to start, "Add another source" up to 5, a remove button on extra rows, inline validation per row (including duplicates), empty rows dropped before submit, and a "DOI preferred" hint
  - quota line "n/10 fact posts left today"
  - disabled with a verify prompt for unverified users
  - submitting and error states
- The shell's "New post" button opens the composer.
- Optimistic insert at the top of the feed.

**API endpoints:** `POST /api/v1/posts/`, `GET /api/v1/posts/?cursor=`, `GET /api/v1/me/fact-quota/`.

**Acceptance criteria**
- [x] An opinion appears as OPINION in italic serif; a fact appears with CHECKING FACTS… and a neutral stripe
- [x] Unverified users can't post: the UI explains why and the API returns 403
- [x] Posting without a type, empty, or over 500 chars is blocked on both client and server
- [x] The 11th fact post in a rolling 24 hours is refused with a clear message (429 `fact_quota_exceeded`); the quota line updates (the day became a rolling 24 h window: user decision 2026-10-08)
- [x] Load more never duplicates or skips posts when new ones arrive meanwhile
- [x] DB constraints reject an opinion with `verified_*`, a fact with `published`, an opinion with sources, more than 5 sources, an empty source element, and an emergency opinion
- [x] Source validation, on both client and server:
  - rejected: `javascript:`/`data:` URLs, credentials in URLs, IP or `localhost` hosts, malformed DOIs
  - `doi:10.1000/xyz` and `https://doi.org/10.1000/xyz` are both stored as `10.1000/xyz`
  - a 6th source and duplicates after normalisation are refused; one bad element refuses the whole post with a per-index error
  - sources keep the order entered
- [x] The server makes no network request for any source (a test with outbound network blocked)

**Deviations and decisions (plan approved 2026-10-08; built 2026-10-08 to 2026-10-09; recorded in ARCHITECTURE §2/§3/§4/§4c/§9/§10, ANALYSIS D7 and the b-3 quota row, SETUP B1, STRUCTURE, MEMORY):**
- **User decisions (2026-10-08):**
  - The fact quota is a **rolling 24 hours**, not a calendar day, and counts deleted and removed fact posts. (task.md and Stitch said "of the day" / "today".)
  - **`idna==3.20` is pinned** in `requirements.txt` (already installed through `requests`/`anymail`). In 3.20 `transitional` is ignored, so the call is `idna.encode(host, uts46=True)`.
  - **"Optimistic insert" means insert on success**: the composer shows "Posting…" until the API answers, then the server's post goes to the top of Recent with no refetch. (Not a placeholder card that appears before the answer.)
  - Posting away from `/home` stays on the page and toasts.
- **Defaults approved with the plan:** quota refusal is 429 `fact_quota_exceeded` + `Retry-After`; a limit of 0 is 403 `fact_posts_paused`; one extra partial index for Recent (`posts_recent_idx`); characters are counted in code points everywhere (the `Textarea` counter changed, with no `maxLength`); the posts admin is read-only until Part 10; the composer keeps its draft when closed; the submit button stays enabled and shows every problem; a toast after every successful post.
- **Found while building (all handled):**
  - `varchar(500)[]` **cannot refuse** a long source through Django: its `::varchar(500)[]` cast truncates silently. `normalize_source` is the guard; ARCHITECTURE §2 says so.
  - A crafted cursor position was a **500** (DRF passes it into the queryset filter): `FeedPagination` validates it (404).
  - DRF runs throttles on every method, so the combined GET/POST view picks permissions and throttles by method.
  - `idna` 3.20 rejects `_` and `ab--cd` in ASCII labels, which browsers accept: ASCII hosts use our own label rule; only non-ASCII hosts go through `idna`.
  - The browser's `new URL()` repairs input (`\`, `%xx` in hosts, `https:example.com`, `127.1`), so the page mirrors the server's algorithm (shared `source_vectors.json`, 172 cases) and uses `URL` only for punycode. **The page can't check that an `xn--` label is a real A-label** (the server does; its 400 lands on that row).
  - `sourceLabel()` for a non-http value had an empty host (blank row): it falls back to the raw value.
- **Built differently from the plan:**
  - The §9 post object has **23** keys (the plan said 24); the tests pin the 23.
  - The "too many sources" check lives in `validate_sources` (the serializer field just calls it).
  - `TextField` has no `ref`, so rows and fields are focused by `id` (no change to Part 0B's primitive).
  - The submit button reads **"Post"** until a type is chosen (it said "Post opinion" before; misleading).
  - The footer wraps on a phone: the allowance above, the buttons below.
  - `apps/accounts/serializers.py` gained `UserSummarySerializer` (Part 7B's `reposted_by` reuses it); `run_together` moved from `test_tokens.py` to the accounts `conftest.py`; ARCHITECTURE §4's `is_active_emergency` lives in `apps/posts/emergency.py` until Part 9.
- **Closed here:** the 0C follow-ups (`onNewPost` wired to the composer; PostCard's header no longer wraps the author name at 390 px).
- **Not done (later parts):** the emergency toggle and `pinned` (11C); "+N more" as a link (5); an **idempotency key** for `POST /api/v1/posts/` (a relay timeout after Django saved the post makes a retry a duplicate; the composer's message mentions it) and the cursor guard for other lists that use the core `CursorPagination` (both Part 16); toasts still render below an open `<dialog>` (0B follow-up; the composer shows its errors inline).
- **Verified:** see HANDOFF (backend 1087 tests, frontend 1089, E2E 20 in dev and CI mode, the Linux blocks of `docs/test-command.md` Part 4 run verbatim from the doc, screenshots at 1280 and 390 px). The PowerShell blocks of that section were not run on Windows. CI itself runs when you push.

**Required tests:** model constraints; source validator table (URLs, DOIs, IDN/punycode, every rejection) plus list rules (0, 5 and 6 sources, duplicates, per-index errors, order kept) and `source_kind`; `create_post` (status by type, quota, throttle, sources, emergency refused); feed shape (`sources: [{value, kind}]`), ordering, exclusion and cursor stability; query count constant for 20 posts with sources; frontend Composer validation and states (add/remove source rows, limit 5, duplicates), PostCard variants and SourceLink ("+N more"), FeedList pagination; E2E: log in → post a fact with a DOI and a URL → CHECKING FACTS… and the line "doi.org/… +1 more" in the feed.

**Recommended models**
- **Plan:** Opus 5.5 · high. The central schema (status constraints, indexes, future fields) is decided here.
- **Implement:** Sonnet 5.5 · high. Substantial but well specified UI and API work.

---

## Part 5: Post detail, sharing, deletion, status polling
**Status:** [x] Done (2026-10-09)
**Goal:** a shareable, indexable post page (guide §1.1), author soft-delete (D6), and live badge updates by polling (guide §5.1 step 5).
**Depends on:** 4.
**Stitch files to convert:** `b3_post_detail_forensic_proof`. Only the claim header, author row, verdict block, the primary-sources registry (as `SourceList`) and action bar. The comments area is Part 7; repost/bookmark are 7B; the gauge, tiles and chart are 11D. Drop the ledger and hashes, and the registry's sample titles, org-type chips, "% match" and archive lines.

**Backend scope**
- `GET /api/v1/posts/{id}/`:
  - deleted → 404
  - removed → tombstone payload, content hidden except to the author
- `DELETE /api/v1/posts/{id}/`: author only; sets `deleted_at`.
- `GET /api/v1/posts/status/?ids=`: at most 50 ids; uncached; returns status, confidence and verdict_source only.

**Frontend scope**
- `/p/[id]` with **light SSR**: `generateMetadata` (title = excerpt + " · Rumor Zero", description = status label, OG tags) plus the claim text.
- `PostDetail`: big claim; verdict explanation per status ("Checked automatically · 94% confidence" / "Reviewed by a moderator" + `verdict_note`); `SourceList` under "Sources (N)": every source numbered 01, 02 … in the order entered, each with its full value (host shown in punycode for internationalised domains; DOIs link to `https://doi.org/…`) and an open-in-new link. The PostCard's "+N more" now links here.
- "Copy link"; Delete (own post, confirmation modal).
- `useStatusPolling`: visible tab only, 10 s backing off to 60 s, stops after 10 min. Used by the feed and the detail page.
- PostCards link to the detail page.

**API endpoints:** `GET/DELETE /api/v1/posts/{id}/`, `GET /api/v1/posts/status/`.

**Acceptance criteria**
- [x] `curl` of `/p/<id>` returns HTML containing the claim text and the correct `<title>`/OG tags (title, `og:*`, `twitter:*`, canonical; a removed post is "Removed post" with `noindex`)
- [x] Changing a post's status in the Django shell updates the badge in an open tab without a reload (about 10 s; on the feed and on the page; E2E and a headless-browser run)
- [x] Polling pauses on a hidden tab and stops after 10 min (10 minutes of *visible* time; covered by the fake-timer tests, **not watched in a real hidden tab**)
- [x] After the author deletes a post it's gone from feeds and detail (404) but still visible in the admin (the admin row is covered by a Django-client test and a new "By deleted at" filter; the pages were not opened by a person)
- [x] A removed post shows the tombstone to the public

**Deviations and decisions (plan approved 2026-10-09; built 2026-10-09; recorded in ARCHITECTURE §3/§4/§9/§10, ANALYSIS b-2 "Removed", STRUCTURE, MEMORY):**
- **User decisions (2026-10-09):**
  - **A removed post's "tombstone payload" is the normal 23 keys with `content`, `sources`, `verdict_note` blanked** (and, by default, `confidence_score` and `verdict_source`). The author's name and the post time stay visible to the public; the author sees the full post. The rule is in `PostSerializer`, so no later list can leak a removed post.
  - **A `status_poll` throttle (120/min per client IP) was added** to the public status endpoint (ARCHITECTURE §3 had none).
- **Defaults approved with the plan:**
  - The detail, delete and status shapes and codes: 404 for deleted, unknown or malformed ids (the author included); delete is 204, then 404 (403 `not_author` for others, no verified email needed, any status deletable, the post still counts toward the fact quota); the status endpoint is public with no authentication, in the order asked, a removed post answers `removed` with nulls and deleted ids are left out, 400 on `ids` for none, over 50 or a malformed id.
  - Polling covers `pending` posts only, counts **visible** time (10 min), waits 10 s × 1.5 up to 60 s, restarts for a new pending id, and is silent on errors.
  - The claim is a stretched card link with `prefetch={false}`; "+N more" goes to `/p/{id}#sources`; the detail claim is `text-headline-md` (28 px; b3's 36 px would be about 20 lines for 500 characters at 390 px); times are absolute UTC; Copy link copies `window.location.origin + /p/{id}`; delete ends on `/home` with a toast; the SSR fetch has a 5 s timeout and falls back to generic tags and a client fetch.
- **Built differently from the plan:**
  - `useStatusPolling` filters its own ids (a post that settled or vanished drops out), so `status-overlay.ts`'s `pendingPostIds` takes only the loaded posts.
  - `lib/api/backend-origin.ts` was extracted from `relay.ts` (`readConfig` now calls it; same rules), and `server.ts` holds the SSR read.
  - `brand-guard.test.ts` allow-lists `features/posts/post-metadata.ts` and its test: the page must name the static share images itself, because a page-level `openGraph`/`twitter` replaces the root layout's whole object (MEMORY).
  - The admin filter is Django's `EmptyFieldListFilter`, headed **"By deleted at"** (All / Empty / Not empty), not "Deleted by author".
  - The E2E status flip (`setPostState`, `manage.py shell` against the same database) was kept: it passes locally in both modes.
  - The status endpoint's removed-post branch computes confidence through the shared `shown_confidence()`, which is already null for a removed post (a redundant check was dropped).
- **Found while building (all fixed):**
  - **StrictMode aborts the signed-in detail fetch** and the "already fetched" marker was set too early, so the author got no Delete button when arriving from a card (the E2E suite found it; the unit test now mounts the page after the session settled, inside `<StrictMode>`, and fails on the old code).
  - A removed post's author page showed an **empty "Verdict" card**: `VerdictBlock` now renders nothing for `removed`.
  - A page-level `openGraph` drops the root's `og:image`; the brand guard refused the image name outside the brand files (above).
- **Not done (later parts):**
  - The removal reason, `can_appeal` and `RemovedPostCard` (Part 11); the review queue must skip posts with `deleted_at` set (Part 10; the admin is still read-only).
  - CSP is unchanged (nothing new loads); the `status_poll` value and the cursor guard for other lists (Part 16); a Workers CPU check of `/p/[id]` (error 1102, Part 18; not measurable locally).
  - Counts and `*_by_me` on the page (7/7B); profile lists will reuse the polling hook (6).
  - A signed-in author sees no Delete button for a moment: the server render is the anonymous view, and `is_mine` arrives with the signed-in fetch.
- **Verified:** see HANDOFF (backend 1160 tests, frontend 1210, E2E 24 in dev and CI mode, the Linux blocks of `docs/test-command.md` Part 5 run verbatim from the doc, headless-browser runs with screenshots at 1280 and 390 px). The PowerShell blocks of that section were not run on Windows. CI itself runs when you push.

**Required tests:** detail visibility matrix (anonymous / author / other × each status and deleted); delete permissions; status endpoint (limits, exclusions, query count); `useStatusPolling` with fake timers and visibility changes; PostDetail states; E2E: create → open detail → copy link.

**Recommended models**
- **Plan:** Sonnet 5.5 · high. Standard work, but the SSR-vs-CPU-limit trade-off needs attention.
- **Implement:** Sonnet 5.5 · medium. Straightforward once planned.

---

## Part 6: Profiles, follows, Following feed
**Status:** [x] Done (2026-10-09)
**Goal:** public profiles, follow/unfollow, follower and following lists, and the fan-out-on-read Following feed with a short cache (guide §9.2).
**Depends on:** 4.
**Stitch files to convert:**
- `c1_user_profile`: header, counts, post list. Drop the side widgets and trust metrics (the credibility score comes in 11B, the Credibility widget in 11D).
- `c3_following_list`: tabs and user rows. Drop the chips and metrics (the score comes in 11B).
- `b1_home_feed`: the Following tab.

**Backend scope**
- `social.Follow`: unique pair, no self-follow check.
- `POST/DELETE /api/v1/users/{u}/follow/`: idempotent.
- `GET /api/v1/users/{u}/`: display name, bio, joined date, counts (followers / following / posts / verified / FALSE), `is_following`, `is_me`.
- `…/posts/`: cursor, in the ARCHITECTURE §9 feed shape (that user's reposts join in 7B); excludes removed and deleted.
- `…/followers/`, `…/following/`.
- `GET /api/v1/feed/`: followed + own posts in the §9 feed shape (`pinned` stays empty until 11C); first page cached per user for `FEED_CACHE_SECONDS`; cache busted when you post or change a follow.

**Frontend scope**
- `/u/[username]` (light SSR header): ProfileHeader with Follow button or "Edit profile" (→ `/settings`, Part 14), counters labelled "Verified" and "FALSE"; post list with filter chips All / Facts / Opinions.
- `/u/[username]/followers` and `/following` with Tabs; `UserRow` + `FollowButton` (optimistic, with rollback).
- The Following tab on `/home`, with the empty state "Follow people to see their posts here" → Recent.

**API endpoints:** the users/follow endpoints above, plus `GET /api/v1/feed/`.

**Acceptance criteria**
- [x] Follow and unfollow are idempotent; self-follow returns 400; counts update (201 then 200, 204 always; `cannot_follow_self`; the profile's follower count moves, and so does the button, optimistically)
- [x] The Following feed shows only followed accounts + your own posts, newest first; your new post shows immediately despite the cache (the cache holds only ids and your own feed is cleared when you post, follow or unfollow)
- [x] An unknown username returns 404; lookup is case-insensitive (also for inactive and malformed names; `/u/Ada` redirects to `/u/ada`)
- [x] List endpoints use a constant number of queries (followers, following, a person's posts, the Following feed and the profile; each pinned with 3 and 20 rows)

**Deviations and decisions (plan approved 2026-10-09; built 2026-10-09; recorded in ARCHITECTURE §2/§3/§9/§10, ANALYSIS c-37, STRUCTURE, ENV_GUIDE, MEMORY):**
- **User decisions (2026-10-09):**
  - **`/home` tabs: Recent first and default, Following second**, for signed-in users only (b1 lists Following first).
  - **The Following cache holds only the ids of page 1**; the posts are loaded fresh on every request.
  - **Profile counters: `verified` and `FALSE` include deleted posts** (not removed ones); `posts` counts only what the public can see.
  - **The author's avatar and name link to `/u/<username>`** on post cards and the post page (not in this part's list).
- **Defaults approved with the plan:** names are looked up by NFKC + lower-case + exact match (unknown, inactive or malformed: 404); follow needs a verified email (201/200), unfollow only a login (204 always), both throttled by `follow` 100/h; `GET /api/v1/feed/` needs a login but not a verified email; `FEED_CACHE_SECONDS` 0 to 300 (0 = off); profile and user-row objects carry a `reputation` block (always `score: null` until 11B); a read-only `FollowAdmin`; `/u/Ada` redirects (307) to `/u/ada`; counters print as "1,420"; `FilterChips` All / Facts / Opinions; the profile is one column at `max-w-reading`; Edit profile links to `/settings` (a placeholder until Part 14).
- **Built differently from the plan:**
  - The cursor check moved into **`TimestampCursorMixin`** in `apps/core/pagination.py` (the plan said "a small mixin"; `FeedPagination` and `UserListPagination` use it; `FeedPagination` gained an `envelope()` helper for the cached feed).
  - **`services.lookup_name`** (a `[a-z0-9_]{3,30}` full match before any query) was added after a test found that a NUL byte in the name was a 500.
  - The two list pages are `ƒ` (dynamic) routes in the build although they read nothing on the server; they take their name from the path.
  - **`social.spec.ts` is a serial file with two shared accounts**, and `signUp` in `e2e/helpers.ts` now waits up to 30 s for `/verify-email` (see MEMORY); `posts.spec.ts` expects two links on a card.
  - `FollowButton`'s hover label shares one grid cell with "Following" (the first version hid it with `display: none` and the accessible name fell back to the title).
  - `ProfilePosts` adds your own new post to the top of your own profile when the filter matches (not in the plan; a few lines and tested).
  - `docs/ENV_GUIDE.md` filed `FEED_CACHE_SECONDS` with the admin-editable PlatformSettings values; it is a plain setting, and the three rows were corrected.
  - ARCHITECTURE §2: the plain `index(following)` became two composite indexes (`following, created_at DESC, id DESC` and `follower, created_at DESC, id DESC`).
  - "No self-follow check" in this part's scope line contradicted ARCHITECTURE §2 and the acceptance criterion; it was built as a DB check constraint plus a 400.
- **Found while building (all fixed):** the NUL-byte 500 above; a mutation check showed `_by_status` unused in the counters (the verdict-of-deleted-posts rule had no test) and that removed posts weren't covered in the page of ids; the hover label bug; E2E sign-up flakiness under load; a brand-guard failure when a test named the share image files.
- **Not done (later parts):**
  - Likes, comments, reposts and bookmarks (7, 7B); `FeedList` still skips `repost` items, and 7B turns the Following cursor into `(activity_at, item id)`.
  - The credibility score on profiles and rows (11B/11D); the Edit profile page, rename (14); profile photos at 256 px (14B); people search reuses `UserRow` (12); follow notifications (13).
  - Part 16: the `follow` rate and the cache TTL are guesses; Upstash command use (a Following first-page view costs one to three commands); the cursor guard for the remaining core-pagination lists.
  - Part 18: Workers CPU of `/u/[username]` (the same escape hatch as `/p/[id]`).
  - Unfollowing inside your own Following list doesn't change the tab count shown above it.
- **Verified:** see HANDOFF (backend 1336 tests, frontend 1320, E2E 29 in dev and CI mode, 26 backend and 44 frontend mutation checks, an EXPLAIN of the Following query, the Linux blocks of `docs/test-command.md` Part 6 extracted from the doc and run verbatim, screenshots at 1280 and 390 px). The PowerShell blocks of that section were not run on Windows. CI itself runs when you push.

**Required tests:** constraints; follow API idempotency; feed composition, caching and invalidation; profile counts; query counts; FollowButton optimistic and rollback; E2E: A follows B → B posts → A sees it under Following.

**Recommended models**
- **Plan:** Sonnet 5.5 · high. The feed caching and invalidation details matter.
- **Implement:** Sonnet 5.5 · medium. Standard social-graph CRUD.

---

## Part 7: Likes & comments
**Status:** [x] Done (2026-10-10)
**Goal:** likes with DB-enforced uniqueness and flat comments (guide §3.3, §9).
**Depends on:** 5.
**Stitch files to convert:** `b3_post_detail_forensic_proof` (discussion section: composer + list; no Reply, no comment IDs or likes); action bars in `b1_home_feed` and `a1_logged_out_home` (like and comment here; repost and bookmark in 7B).

**Backend scope**
- `social.Like` (index `(post, created_at)`, also used by the stats in 11D) + `POST/DELETE /api/v1/posts/{id}/like/`.
- `social.Comment`:
  - `GET` (oldest first, cursor) and `POST` (verified only, ≤500 chars, throttle `comment`) on `/api/v1/posts/{id}/comments/`
  - `DELETE /api/v1/comments/{id}/` for your own comments
  - `is_hidden` excluded from lists
- `like_count`, `comment_count` and `liked_by_me` annotated into the Post serializer.
- CommentAdmin with a "Hide" action.

**Frontend scope:** `LikeButton` (optimistic; filled glyph in `secondary`), comment count on cards; `CommentList` + `CommentComposer` on `/p/[id]` (counter, Ctrl+Enter to submit, delete own, empty state).

**API endpoints:** the like and comment endpoints above.

**Acceptance criteria**
- [x] Like toggling is idempotent and counts stay correct under concurrent requests (201 then 200, 204 always; `get_or_create`; threaded tests: two simultaneous likes by one user make one row, six users are all counted, two simultaneous comment deletes give one success)
- [x] Unverified users get 403; comments over 500 chars are rejected (403 `email_unverified` for likes and comments, 400 "Keep it to 500 characters." for 501 code points; an emoji counts as one)
- [x] Hidden comments disappear for everyone but staff (in no API list and no count for anyone, staff included; staff see them in Django Admin, where Hide and Unhide are actions; user decision 2026-10-10)
- [x] Feed queries stay constant with annotations (Recent 1 anonymous / 2 signed in, profile posts 2 / 3, the Following feed 3 on a miss, the comment list 2 / 3, each pinned at 3 and 20 rows)

**Deviations and decisions (plan approved 2026-10-10; built 2026-10-10; recorded in ARCHITECTURE §2/§3/§8/§9/§10, ANALYSIS c-38, STRUCTURE, MEMORY):**
- **User decisions (2026-10-10):**
  - **Hidden comments are Django Admin only** (not in the API for staff either).
  - **Deleting your own comment is a soft delete**: a new `comments.deleted_at` column (ARCHITECTURE §2 had none), like posts (D6).
  - **CommentAdmin has Hide and Unhide** (this part said only "Hide").
- **Defaults approved with the plan:** like is 201 / 200 / 204 with `{"liked": true}`; likes and comments need a post the public can see (removed, deleted, unknown and malformed ids are a JSON 404; pending and under review are allowed); unlike works on a removed post; comments are oldest first on `(created_at, id)`, five keys, `comment` throttle on POST only; the counts are correlated subqueries added by `PostQuerySet.for_list(viewer)`; one partial index `comments_post_visible_idx` replaces §2's plain `(post, created_at)`; `LikeButton` mirrors `FollowButton` with local state; `PostCard` takes an `actions` node; comments are fetched by the page, not server-rendered; the new E2E tests join `social.spec.ts` (no new sign-up).
- **Built differently from the plan:**
  - `PostActions` has no `onLikeChange` prop and `PostDetail` doesn't mirror the like into its post: a mutation check showed nothing read it (the button keeps its own state). `LikeButton`'s own `onChange` stays, tested, for callers that need it.
  - `LikeButton` tests `!user` only (the `anonymous` status check was redundant, found by a mutation check).
  - The accessible name is one `sr-only` span ("Like 3"); the visible label and count are `aria-hidden` (adjacent inline spans read "Like3").
  - `_count` moved from `social/serializers.py` into `social/engagement.py` (`count_subquery`), and `content_field()` was extracted from `PostCreateSerializer` so comments share the posts' messages.
  - The composer is a plain `Textarea` with a counter, not Stitch's box with the textarea inside it (the field already has the secondary focus border).
  - Test helper `renderWithSessionAndToast` was added (`FeedList` cards now need the session and the toast region).
- **Found while building (all handled):**
  - `User.save` derives `is_staff` from `role`, so a test user made with `is_staff=True` was silently not staff (the "staff can't hide" test passed for the wrong reason until it used `role=Role.MODERATOR`).
  - After posting, focus must be restored in an effect: a disabled `fieldset` drops it and `finally` runs while the DOM is still disabled.
  - The accessible-name trap above; Playwright's `getByText` matches a textarea holding that text (MEMORY).
  - The icon glyphs `favorite` and `chat_bubble` are not in DESIGN.md's "one glyph per concept" list (ANALYSIS c-38).
- **Not done (later parts):**
  - Reposts, bookmarks (7B; `repost_count` and the other `*_by_me` stay 0 / false), reports (8), notifications for likes and comments (13; the services are the single write path to hook into, and a deleted or hidden comment must not notify).
  - Part 8 must decide whether `counts_toward_threshold` ("≥1 post or comment") counts a soft-deleted comment (the principle used for posts says it does). Part 10 grants `social.change_comment` to the Moderators group (Hide and Unhide are already gated on it) and its review queues skip deleted comments. 11D's daily comment counts must use the same predicate as the partial index.
  - Part 16: the `like` and `comment` rates are guesses; the counts are correlated subqueries (a stored counter if a post reaches many thousands of likes); the cursor guard for any list still on the bare core pagination. Part 18: a Workers CPU check of `/p/[id]` (the discussion is client-only, so the server side is unchanged).
  - Known limits: a like made in one list isn't copied into another mounted list showing the same post (Recent and Following on `/home`; every route change refetches); comment drafts aren't kept across navigation; comments don't update live; a comment you add while older pages are unloaded stays last until they load.
- **Verified:** see HANDOFF (backend 1485 tests, frontend 1410, E2E 32 in dev and CI mode, 23 backend and 34 frontend mutation checks, an EXPLAIN of the comment and like queries, the Linux blocks of `docs/test-command.md` Part 7 extracted from the doc and run verbatim, a scripted-browser check of the feed, the post page, the phone width and Django Admin). The PowerShell blocks of that section were not run on Windows. CI itself runs when you push.

**Required tests:** constraint and race tests, API permissions, query counts, frontend components; E2E: like + comment on a post.

**Recommended models**
- **Plan:** Sonnet 5.5 · medium. Well-understood CRUD.
- **Implement:** Sonnet 5.5 · medium. Well-understood CRUD.

---

## Part 7B: Bookmarks & reposts
**Status:** [x] Done (2026-10-10)
**Goal:** private bookmarks and plain reposts (D5; ARCHITECTURE §4d). A repost carries the original's live label and never triggers a new check.
**Depends on:** 6 (Following feed, profiles), 7 (action bar).
**Stitch files to convert:**
- `b1_home_feed`, `a1_logged_out_home`, `b3_post_detail_forensic_proof`: the repost counter (`cached`; Stitch's "Citations" becomes "Reposts") and the bookmark button (`bookmark_border`, filled `bookmark` when saved) in the action bars. Logged-out visitors get a "Log in to …" prompt.
- `c1_user_profile`: reposts inside the post list.
- The `/bookmarks` page has no Stitch screen: compose it from the `b1_home_feed` layout.

**Backend scope**
- `social.Bookmark` and `social.Repost` exactly per ARCHITECTURE §2 (with `Repost.status_at_repost`).
- `social.services`:
  - **Reposts** (§4d):
    - refused: your own post (409 `cannot_repost_own`), a FALSE-labelled post (409 `cannot_repost_false`), a removed or deleted post (404)
    - reposting a repost reposts the original
    - idempotent, email-verified only; `status_at_repost` is recorded
  - **Bookmarks:** idempotent, any logged-in user (no email verification: bookmarks are private).
- Endpoints: `POST/DELETE /api/v1/posts/{id}/repost/`, `POST/DELETE /api/v1/posts/{id}/bookmark/`, `GET /api/v1/me/bookmarks/` (cursor on bookmark time; deleted and removed posts dropped). Throttles `repost`, `bookmark`.
- Serializer: `repost_count`, `reposted_by_me`, `bookmarked_by_me` annotated, with no N+1. Bookmark counts are never exposed.
- **Following feed** (ARCHITECTURE §9):
  - posts **and** reposts by followed accounts + you, ordered by activity time
  - a stable cursor over `(activity_at, item id)`
  - the same post at most once per page (the most recent activity wins)
- Profile lists include that user's reposts. The Recent feed stays originals only.
- Repost items whose original was deleted or removed come back as `kind:"repost"` with `post: {"id", "unavailable": true}`.
- The feed cache is busted on repost and unrepost.
- Admin registration (read-only).
- Score effects of reposts come in 11B; the `repost` notification in 13.

**Frontend scope**
- `RepostButton`: optimistic with rollback; disabled with the reason for your own, FALSE or removed posts.
- `BookmarkButton`: optimistic.
- `RepostHeader` ("Reposted by @x"), `UnavailablePostCard` ("This post is no longer available").
- `/bookmarks`: sidebar item; empty state "Posts you bookmark appear here. Only you can see them."; cursor LoadMore.

**API endpoints:** the repost and bookmark endpoints above.

**Acceptance criteria**
- [x] Repost and bookmark toggles are idempotent, and counts stay correct under concurrent requests (201 then 200, 204 always; `get_or_create`; threaded tests: two simultaneous reposts or bookmarks by one user make one row, six users are all counted, a repost waits for a concurrent status change and records the status at commit)
- [x] Reposting your own post, a FALSE-labelled post or a removed post is refused with the right code, and the button explains why (409 `cannot_repost_own`, 409 `cannot_repost_false`, 404 for a removed or deleted one; `RepostButton` is `aria-disabled` with the reason as its title, hint and toast)
- [x] A repost always shows the original's current label (change the status in the Django shell → the repost's badge updates: pending → VERIFIED 94% in the Following feed even on a cache hit, and a poll turns a repost's badge by itself)
- [x] When the original is deleted or removed, the repost shows "This post is no longer available" (`{"id", "unavailable": true}`; `UnavailablePostCard`, with Undo repost on your own)
- [x] Another user can never see your bookmarks: the API returns only your own, and there are no counts anywhere (no route for anyone else's, `BookmarkAdmin` is superuser-only, no bookmark count in any object)
- [x] The mixed Following feed never skips or duplicates items across pages while new posts and reposts arrive (a keyset cursor over `(activity_at, kind, post id, reposter id)`; arrivals and changes during a walk tested; 150 seeded random walks agree with an independent reference)
- [x] Feed, profile and bookmark lists use a constant number of queries (Following 4 on a miss / 3 on a hit with reposts, 3 / 2 with only posts; profile 3 anonymous / 4 signed in; bookmarks 3; each pinned at 3 and 20 items)

**Deviations and decisions (plan approved 2026-10-10; built 2026-10-10; recorded in ARCHITECTURE §2/§3/§4d/§8/§9/§10, ANALYSIS c-39, STRUCTURE, MEMORY):**
- **User decisions (2026-10-10):**
  - **`BookmarkAdmin` is superuser-only** (read-only; no moderator permission opens it, even after Part 10).
  - **A repost of a deleted or removed original can be taken back** (`DELETE …/repost/` is 204 whenever the post row exists); your own "no longer available" card has **Undo repost**.
  - **The page hides later repeats** of a post across pages of a list (the API keeps "once per page").
  - **Profile chips filter reposts by the original's type**, stubs included.
- **Defaults approved with the plan:** 201/200/204 with `{"reposted": true}` and `{"bookmarked": true}`; the repost checks run not-found, existing (200), own, FALSE; `status_at_repost` is recorded under a `FOR NO KEY UPDATE` row lock and a DB check limits it to the four repostable statuses; the keyset timeline and its cursor token (integer microseconds, strict decoding, 404 for anything else), the `2 × size + 1` window, cache v2 holding keys, profile lists with no dedupe; `GET /me/bookmarks/` in the §9 envelope on `BookmarkPagination`; `RepostButton`/`BookmarkButton` mirror `LikeButton`; `PostCard`'s `header` slot, `RepostHeader`, `UnavailablePostCard`; `/bookmarks` built from the profile page's container with c4's heading; the new E2E tests join `social.spec.ts` (no new sign-up).
- **Built differently from the plan:**
  - The repost side of the union stays **one** branch: `EXPLAIN` at 300,000 reposts and 200 follows showed a separate `IN` branch plus a "my reposts" branch no faster (about 11 ms against 11 to 18 ms), so the plan's conditional "third branch" was not built (recorded for Part 16).
  - The repost button's visible word is **"Repost"**, not "Reposts" (the word must be part of the accessible name "Repost 3"); its hint is short and its toast long, as `LikeButton`'s.
  - `BookmarkAdmin` has no `has_module_permission` override: Django already hides a model with no view permission from the admin index (a mutation check showed it dead).
  - `isUnavailable` and `visibleItems` live in a new `features/posts/feed-items.ts`; `repost-rules.ts` (`repostBlockedReason`) is new; `PostActions` takes the post instead of separate props.
  - The E2E tests are four (two with the shared accounts, one with a visitor and the disabled reasons, one for a phone); a third person's post comes from a new `seedPost()` helper, not a sign-up.
- **Found while building (all handled):**
  - A bare OR cursor filter can't use an index: each side carries a redundant `created_at <= t` (a test reads the SQL).
  - `LikeButton` repeated one constant hint id in every unverified card (now `useId`; `FollowButton` still has it).
  - `FeedList`, `pendingPostIds` and the `gone` filter all assumed `kind: "post"`; the tests that pinned that were changed on purpose.
  - A system `ruff` (anaconda, first on `PATH`) ran when the venv wasn't activated and reformatted three files (MEMORY).
  - Two of my own test expectations were wrong (a repost correctly hides the original on the same page; a cached page can't show a new repost for 30 s), and one mutation survivor each on the backend (the bookmark throttle scope: equal rates) and the frontend (the zero clamp), all fixed with tests.
- **Not done (later parts):**
  - Score effects of reposts (11B reads `status_at_repost`), the `repost` notification (13; `social.services.repost` is the single write path), reports and the flag button (8), daily repost counts in 11D (`reposts_post_created_idx`), export and account deletion of bookmarks and reposts (14).
  - Part 16: the `repost`/`bookmark` rates are guesses; the reposts side of the Following union is a sequential scan and a top-N sort; `FollowButton`'s constant hint id.
  - Known limits: your new repost isn't inserted into an open list; a like, repost or bookmark made in one list isn't copied into another mounted list showing the same post; if the repost that won a page's once-per-page rule is undone, a follower's cached page has no item for that post until the TTL (30 s) ends.
- **Verified:** see HANDOFF (backend 1875 tests, frontend 1510, E2E 36 in dev and CI mode, 38 backend and 31 frontend mutation checks, `EXPLAIN` of the feed union and the bookmark page, the Linux blocks of `docs/test-command.md` Part 7B extracted from the doc and run verbatim, a scripted-browser check of the feed, the profile, the Bookmarks page, the phone width and Django Admin). The PowerShell blocks of that section were not run on Windows. CI itself runs when you push.

**Required tests:** constraints; service rules; API permissions and codes; feed union ordering, per-page dedupe and cursor stability; query counts; components (optimistic + rollback, disabled reasons, unavailable card); E2E: A reposts B's post → C (who follows A) sees "Reposted by A"; bookmark a post → it appears on /bookmarks.

**Recommended models**
- **Plan:** Opus 5.5 · high. A stable cursor over mixed posts and reposts is easy to get subtly wrong.
- **Implement:** Sonnet 5.5 · high. Well specified once the feed query is designed.

---

## Part 8: Reporting & threshold
**Status:** [x] Done (2026-10-10)
**Goal:** one report per user per post; a windowed, brigading-resistant threshold that sends posts to review while keeping them visible (guide §6; ARCHITECTURE §5).
**Depends on:** 5.
**Stitch files to convert:** `d1_report_post_modal`, with plain-language reasons (ANALYSIS b-5).

**Backend scope**
- `reports.Report` exactly per ARCHITECTURE §2.
- `POST /api/v1/posts/{id}/report/` implementing ARCHITECTURE §5: `select_for_update`, `report_count`, `counts_toward_threshold`, window count.
- Create `apps/pipeline/routing.py` with `merge_flag`, `enter_review` and `apply_report_threshold(post, n, cfg, now)` (the pipeline part is added in Part 9; the emergency threshold branch in 11C).
- `posts.services` owns the status write.
- `reported_by_me` in the serializer.
- Read-only ReportAdmin.

**Frontend scope:** `ReportModal`:
- 5 reasons; the details textarea is required for "Something else"
- states: submitting, success toast, **"You reported this"** (disabled), "Verify your email to report", own post (no report action)

The Report action is a **flag button** in the card's action bar and a "Report" button on the detail page (user decision 2026-10-10; this section said "overflow menu", see the deviations).

**API endpoints:** `POST /api/v1/posts/{id}/report/`.

**Acceptance criteria**
- [x] 5 counting reports within 24 h move the post to UNDER REVIEW (`flagged_reason=reports`); it stays visible (the fifth counting report, through the API, moves it with `pre_review_status` kept; the detail page, Recent and a visitor still show its text; E2E: a reload shows UNDER REVIEW with the text)
- [x] Reports outside the window, from new inactive accounts, or dismissed don't count (a report exactly one window old counts and one a microsecond older doesn't; an account under 24 h old with no post or comment is stored as not counting; dismissed and actioned reports and other posts' reports are left out)
- [x] Reporting twice returns 409 and shows "You reported this"; reporting your own post → 403; a removed or deleted post → 404 (409 `already_reported`, even after a dismissal; 403 `cannot_report_own`; 404 for a removed or deleted post, its author included; the flag turns into a filled "You reported this")
- [x] The 11th report in an hour → 429 (the real 10 + 1 requests; a 401 and an unverified email don't count, a 400 does)
- [x] Concurrent reports can't skip the threshold (a threaded transaction test): real threads: two simultaneous reports by one person make one, six people are all counted and the post reaches review, and two reports waiting behind a held `FOR NO KEY UPDATE` row lock with three counting reports committed end with the post under review and `report_count == 5` (without the lock both would count four)

**Deviations and decisions (plan approved 2026-10-10; built 2026-10-10; recorded in ARCHITECTURE §2/§3/§4/§4d/§5/§8/§9/§10, ANALYSIS c-40, STRUCTURE, MEMORY):**
- **User decisions (2026-10-10):**
  - **The report action is a flag button**, as Stitch b1/b3 draw it, not an overflow menu (this section said "PostCard overflow menu"). No menu component was built.
  - **What makes a young account's report count:** a post that isn't removed or a comment that isn't hidden; the reporter's **deleted** posts and comments still count, moderated ones don't (Part 7 had left the soft-deleted comment open).
  - **FALSE posts follow the docs** (they go to UNDER REVIEW with `pre_review_status=verified_false`), and **a post under review after being FALSE can't be reposted** (409 `cannot_repost_false`; one condition in `social.services.repost`).
- **Defaults approved with the plan:** `FOR NO KEY UPDATE` on the post with the `visible()` filters in the locking query; the check order (401, 403 `email_unverified`, 429, malformed id 404, 400, then 404, 403 `cannot_report_own`, 409 `already_reported`); 201 `{"reported": true}` whatever the effect; reports are permanent (no withdrawing); no `IntegrityError` catch (the lock makes the duplicate check race-free); the window has **no upper bound**; every visible status can be reported; the five reasons for facts and opinions alike; no reason preselected in the dialog; `apps/pipeline` made with `startapp` now (only `routing.py`; Part 9 adds to it); `posts.services.record_report` as the one status write; `apply_report_threshold` returns True only when the post **entered** review (Part 13's hook); `merge_flag` raises `ValueError` for an appeal onto a post under review for the pipeline, reports or both; five named database checks on `reports` (including `reports_resolution_consistent`: Part 10's Dismiss must set `resolved_at` with `status`); the modal is built on the first click and kept, and the flag stays one `<button>`.
- **Built differently from the plan:** none of substance. `ReportModal` stores the focus target of a server field error in a ref and focuses it in an effect once the form has unlocked (a disabled fieldset ignores `focus()`; found by a test); `ReportButton` also hides itself when the session's user id equals the author's (the anonymous server-rendered view doesn't know `is_mine`); a test-only helper, `aged_user`, and an autouse `report_settings` fixture were added.
- **Design-review appendix (arrived after approval, not part of the approved plan; the approved plan was built as written):** A1 `enter_review` refuses a removed post and A2 a decisive late pipeline FALSE on a reported post would make the new repost refusal reveal a hidden verdict were **not adopted**. A2 is recorded for Part 9 (below); every item of its "B" list that only sharpened the plan (no upper bound on the window, no `.only()` on the locked post, the return value of `apply_report_threshold`, extra boundary tests, the exception codes, the ReportAdmin never listing the details) is built.
- **Found while building (all handled):**
  - A server field error can't take focus while the fieldset is disabled (see above).
  - The test session's user is `u-1`, also `makePost`'s default author, so the flag was hidden in tests until the post got another author.
  - A mutation run found three weak tests (the Escape-while-sending test was vacuous because the disabled button had taken the focus, the filled glyph wasn't asserted, and one pattern didn't match); all fixed.
  - A test of mine used `getByText("Bo")`, which matches inside other words; E2E markers must not contain "report" (`/report/i` matches the claim link).
- **Not done (later parts):**
  - **Part 9:** the processor selects `status='pending'` only, so a pending fact that reports sent to review would never be checked: it must also take under-review facts with `pre_review_status='pending'` and no `pipeline_checked_at`; a decisive late FALSE on a reported post sets `pre_review_status=verified_false` without the label ever being public, which the "under review after FALSE" repost refusal would then reveal (narrow the condition or accept it); the processor must not hold the post row lock across its 20 s call.
  - **Part 10:** moderator permissions on `ReportAdmin`, the `PostAdmin` report inline, Dismiss and the other actions (open reports become `dismissed` or `actioned`, `resolved_at` and `resolved_by` set in the same write), the queue's report-count ordering. **11B:** `report_upheld`. **11C:** the emergency threshold branch of `apply_report_threshold`. **13:** notify the author when `record_report` returns True, in the same transaction. **14:** export and account deletion of reports (deleting a reporter cascades their rows but must not decrement `report_count`). **16:** the `report` rate (a guess), the dev gallery's three copies of the reason list.
  - Known limits: a report made in one list isn't copied into another mounted list showing the same post (every route change refetches); the post page flickers from "Report" to "Reported" once the signed-in view lands for someone who reported before.
- **Verified:** see HANDOFF (backend 2066 tests, frontend 1580, E2E 38 in dev and CI mode, 46 backend and 36 frontend mutation checks, the Linux blocks of `docs/test-command.md` Part 8 extracted from the doc and run verbatim, a scripted-browser check of the card, the dialog, the post page, the phone width and Django Admin). The PowerShell blocks of that section were not run on Windows. CI itself runs when you push.

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
- `apps/pipeline/contract.py`: validated dataclasses (`PipelineRequest` carries `sources`, a tuple of 0–5 strings, ARCHITECTURE §6).
- `clients.py`: `StubPipelineClient` (rules in ARCHITECTURE §6; ignores `sources`) and `HttpPipelineClient` (sends `{post_id, content, sources}`; tested with a mocked HTTP layer).
- `routing.apply_pipeline_result(post, result, cfg, now)` (the emergency branch is added in 11C).
- `processor.process_pending` with `FOR UPDATE SKIP LOCKED`, retries, backoff and max attempts; emergencies first (`is_emergency DESC`), then oldest.
- Inline kick on commit (daemon thread, closes its DB connection).
- `manage.py process_pending [--loop --interval N]`.
- `POST /api/internal/tick/` (secret; small batch; returns `{"processed": n}`).
- Confidence threshold read from PlatformSettings.

**Frontend scope:** verdict explanation copy per `verdict_source`; confirm the polling from Part 5 picks up changes.

**API endpoints:** `POST /api/internal/tick/`.

**Acceptance criteria**
- [ ] Locally, a fact containing `#true` becomes VERIFIED 95% within seconds; `#false` becomes FALSE 92%; `#unsure` becomes UNDER REVIEW (pipeline)
- [ ] The pipeline request includes the post's `sources` in order (empty when there are none)
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
- `moderation.ModerationAction`: append-only, from/to status, post snapshot, `subject_user`. The **full action list** from ARCHITECTURE §2 is created now, so later parts don't alter the constraint.
- `moderation.services`: `mark_verified`, `mark_false`, `dismiss_reports`, `remove` (stores `pre_removal_status`), `escalate`. Each is transactional, applies ARCHITECTURE §4, and logs.
- `PostAdmin` review queue per ARCHITECTURE §8: list columns, filters, search, inlines, bulk actions with a confirmation form for `verdict_note`/notes; verdict actions for facts only, labelled "Mark verified" and **"Mark FALSE"** (D4). The emergency ordering and filter work from 11C (the columns already exist).
- Also: ReportAdmin; ModerationActionAdmin (read-only, full access seniors only); CommentAdmin hide; UserAdmin (role editable by seniors only); PlatformSettings admin (seniors only, including the emergency limits).
- A Groups and permissions data migration.
- Site header: the logo (`templates/admin/base_site.html` using the static `core/brand/logo-admin.png` from 0D) and "Rumor Zero moderation".

**Frontend scope:** a "Moderation" sidebar link for staff (from `/me.admin_url`, opens in a new tab); hidden for everyone else.

**API endpoints:** none new (the admin is server-rendered).

**Acceptance criteria**
- [ ] Moderators can review and act, but can't edit roles or PlatformSettings, delete users, or see the full audit log. Seniors can do all of that.
- [ ] Every bulk action produces the ARCHITECTURE §4 result and exactly one `moderation_actions` row per post, with correct from/to status
- [ ] Verified/false actions aren't offered for opinion posts
- [ ] Dismiss reports restores `pre_review_status` (or leaves `pipeline` when the flag was `both`), and those reports stop counting
- [ ] Remove stores `pre_removal_status` (the status before review, if the post was under review)
- [ ] The admin header shows the logo and "Rumor Zero moderation"
- [ ] The queue page with 100 flagged posts uses a bounded number of queries

**Required tests:** each service × each starting state; the permission matrix per role through the admin test client; audit rows; query counts; sidebar link visibility.

**Recommended models**
- **Plan:** Opus 5.5 · high. Permissions and audit correctness have legal weight (guide §16).
- **Implement:** Sonnet 5.5 · high. Django Admin configuration, well specified.

---

## Part 11: Appeals & removed-post tombstones
**Status:** [ ] Not started
**Goal:** the "Request another look" path for authors of FALSE-labelled **and removed** posts (guide §8.4, §16; c-7; ANALYSIS f-2: removals now lower a public score) and proper tombstones for removed posts.
**Depends on:** 10.
**Stitch files to convert:** the "Request another look / appeal" button in `b3_post_detail_forensic_proof`; the removed tombstone card in `c1_user_profile`, whose "Request Appeal" button is now used for removal appeals.

**Backend scope**
- `moderation.Appeal` with `kind` (`label` | `removal`), per ARCHITECTURE §2.
- `POST /api/v1/posts/{id}/appeal/`: author only, one per post, throttle `appeal`:
  - `verified_false` → kind `label` → `enter_review(APPEAL)`
  - `removed` → kind `removal`; the post stays removed and hidden
- Admin appeal inline and filter (by kind). Label appeals are resolved through the Part 10 verdict actions. Removal appeals use two new actions: **Restore post** (→ `pre_removal_status`, appeal `overturned`, logged `restored`) and **Keep removed** (appeal `upheld`). Both link the `ModerationAction`.
- The different-moderator rule (seniors exempt), for both kinds.
- `can_appeal` / `appeal_status` for the author only.
- Reversing score events on an overturned appeal is added in 11B.

**Frontend scope:** `AppealModal` (optional reason ≤500 chars, states) for FALSE-labelled and removed posts; an APPEAL PENDING chip for the author; the outcome shown on the detail page; `RemovedPostCard` (public and author variants, the author variant with "Request another look") on the profile and detail pages.

**API endpoints:** `POST /api/v1/posts/{id}/appeal/`.

**Acceptance criteria**
- [ ] Only the author of a FALSE-labelled or removed post can appeal, once (others 403, a second appeal 409)
- [ ] The appealed post appears in the admin queue under `appeal` (with its kind); the moderator who made the original call can't resolve it unless senior
- [ ] Label appeals: overturning gives VERIFIED, upholding keeps FALSE
- [ ] Removal appeals: Restore returns the post to its previous status and it reappears in feeds; Keep removed leaves it hidden
- [ ] The author sees the outcome

**Required tests:** API rules for both kinds, service transitions (including restore targets), the moderator rule, serializer fields per viewer, AppealModal and chip; E2E: the author files an appeal (resolved through a service fixture).

**Recommended models**
- **Plan:** Opus 5.5 · high. Removal appeals add a restore path to the state machine.
- **Implement:** Sonnet 5.5 · high. Builds directly on the Part 10 services.

---

## Part 11B: Credibility score
**Status:** [ ] Not started
**Goal:** a public per-account credibility score (0–100, starting at 50) driven by fact-check outcomes (D5; ARCHITECTURE §4a; guide §16).
- Stored as an append-only ledger plus a denormalised score.
- Fully reversible, with a visible appeal path.

**Depends on:** 7B (repost events), 10 (moderator actions), 11 (appeals and restores).
**Stitch files to convert:**
- `c1_user_profile`: the header meta row ("99.1% Audit Trust Score" → "Credibility 72", or "New").
- `c3_following_list`: the trust metric in user rows ("96.4% Audit Trust • 84 Verified Claims" → "Credibility 72 · 84 verified").
- The ring, trend and history visuals come in 11D.

**Backend scope**
- New app `apps/reputation`:
  - `scoring.py`, pure functions with no I/O: `score(p, n)`, the weight table, which reposts and reports count (ARCHITECTURE §4a).
  - `models.ReputationEvent` exactly per ARCHITECTURE §2 (append-only; admin read-only).
  - `services.py`, the **only** writer of the ledger and of `users.reputation_score` / `reputation_sample`:
    - `record_post_outcome(post, now)`, `record_removal(post, now)`, `record_report_upheld(report, now)`, `reverse_post_events(post, now)`
    - all run in the caller's transaction, with `select_for_update()` on the user row
- Hooks, called explicitly (no signals) from `posts.services` (pipeline verdicts) and `moderation.services` (Mark verified, Mark FALSE, Remove, Restore, appeal outcomes):
  - A re-label reverses the old event and adds the new one.
  - An overturned appeal or a restore reverses the events of the author **and every reposter**.
  - Dismissed reports and failed appeals change nothing.
- `reputation_sample` counts un-reversed own-post events. The public score is `null` below 3.
- Emergency weight: an `is_emergency` post that ends FALSE records `emergency_false` (N + 3) instead of `fact_false`, even before the emergency UI exists (the column is there since Part 4).
- `python manage.py recompute_reputation [--user <username>] [--check]`: rebuilds the denormalised fields from the ledger; `--check` fails on any difference.
- Endpoints:
  - `GET /api/v1/users/{u}/reputation/`: score or null, sample, verified / FALSE / removed counts, the last 10 public events with post links.
  - `GET /api/v1/me/reputation/events/`: your full ledger, cursor.
  - The `reputation` block also appears in `GET /api/v1/users/{u}/` and in user rows.
- Admin: a read-only ReputationEvent list (filter by kind, search by username); UserAdmin shows the score with a link.

**Frontend scope**
- `CredibilityBadge` (the score, or "New" below 3 events) in ProfileHeader and UserRow, with a "How this is calculated" link to `/how-it-works#credibility` (content in Part 15).
- The score is **never** shown on post cards.

**API endpoints:** the two reputation endpoints above.

**Acceptance criteria**
- [ ] Every row of the ARCHITECTURE §4a weight table has a passing test, including the emergency weight, the repost timing rule and the reporter cap
- [ ] An overturned appeal or a restore returns the author and every reposter to exactly their previous score
- [ ] Re-running the same verdict never double-counts; deleting a post keeps its events
- [ ] Scores are hidden publicly (API `null`, UI "New") until 3 counted events
- [ ] `recompute_reputation --check` passes after a randomised sequence of verdicts, removals, restores and appeals
- [ ] Profile and user-row endpoints keep a constant query count

**Required tests:** scoring pure-function table; one service test per event kind; reversal paths (appeal overturned, restore, re-label); concurrency (two verdicts for the same author at once); recompute; API and privacy (no private ledger data in the public endpoint); CredibilityBadge.

**Recommended models**
- **Plan:** Opus 5.5 · xhigh. A public score with legal weight must be exactly reversible and auditable.
- **Implement:** Opus 5.5 · high. Ledger and transaction correctness justify the stronger model.

---

## Part 11C: Emergency posts
**Status:** [ ] Not started
**Goal:** authors can flag a fact post as an emergency (D5; ARCHITECTURE §4b):
- pinned at the top of feeds for 24 hours
- still fact-checked, first
- shown in violet
- protected by abuse safeguards

**Depends on:** 9 (routing), 10 (moderator actions), 11B (score gate and emergency weight).
**Stitch files to convert:**
- `b2_post_composer_modal`: the emergency toggle and warning box, with the copy rewritten (D8). No "bypass", no "permanent marker".
- `b1_home_feed`: the "Emergency dispatch active" banner (→ the pinned-section header) and the emergency card (violet stripe, EMERGENCY chip, `bolt`).
- `c1_user_profile`: the emergency card in the post list.
- `d2_moderator_peer_review_queue`: reference only ("Retract Emergency Status" → the admin action **Demote emergency**).

**Backend scope**
- `posts.services.create_post` accepts `is_emergency` for fact posts only.
  - Eligibility, all values from PlatformSettings (ARCHITECTURE §4b): email verified, account age, score, block, 1 per 24 h, fact quota (emergency posts count toward it).
  - It sets `emergency_expires_at`.
- `GET /api/v1/me/fact-quota/` adds `emergency: {allowed, reason, next_allowed_at}`.
- `is_active_emergency(post, now)` and the routing changes in ARCHITECTURE §4:
  - a FALSE result on an active emergency is never final
  - the emergency report threshold applies while active
  - **No scheduler**: expiry is checked at read time.
- The processor and the admin queue take active emergencies first.
- Feeds (ARCHITECTURE §9):
  - the `pinned` list: Recent pins all active emergencies; Following pins those from followed accounts + you
  - newest first, max 3, plus `pinned_total`
  - pinned posts are left out of `results`
  - `GET /api/v1/posts/emergencies/` returns all active ones; the serializer gains `emergency_active`
- Moderation (ARCHITECTURE §8), all logged:
  - Mark FALSE on an emergency also demotes it and blocks the author for `emergency_false_cooldown_days`
  - the **Demote emergency** action
  - **Block emergency posting** on UserAdmin
  - the "Emergency (active)" filter
- The `emergency_demoted` notification is wired in Part 13.

**Frontend scope**
- Composer:
  - The emergency Toggle appears only for Fact. When not allowed, it's disabled with the reason in plain words.
  - When on, it shows a warning box and a required confirmation checkbox: "I understand emergency posts are checked first, and misuse lowers my credibility score and blocks emergency posting for 30 days."
  - The button reads "Post emergency — will be checked".
- `EmergencyChip` + violet stripe while active. The card takes its status colour after expiry or demotion.
- `PinnedEmergencies` at the top of both feed tabs: b1 banner style, dismissible for the session, "Show all" expands in place.
- Detail-page note after expiry or demotion: "Posted as an emergency on <date>. Priority ended." or "… removed by a moderator."

**API endpoints:** `GET /api/v1/posts/emergencies/`; the extended `GET /api/v1/me/fact-quota/`.

**Acceptance criteria**
- [ ] An emergency opinion is refused by the API and by the DB constraint
- [ ] Each ineligibility reason is returned and shown: unverified, too new, score below 40, blocked, daily limit, fact quota
- [ ] Expiry depends only on time: pinned at 23 h 59 min, not pinned at 24 h 01 min (time-controlled test, no job running)
- [ ] A pipeline FALSE on an active emergency gives UNDER REVIEW (top of the admin queue), never FALSE; after expiry a FALSE result is applied normally
- [ ] A moderator's Mark FALSE unpins the post at once, blocks the author's emergency posting for 30 days and applies the −3 score event
- [ ] 2 counting reports send an active emergency to review; the same post after expiry needs 5
- [ ] At most 3 pinned posts show, none repeated in the list below
- [ ] The processor handles emergencies before older pending posts
- [ ] Every new row of the ARCHITECTURE §4 table has a passing test

**Required tests:** routing rows (pure functions with `now`); eligibility matrix; feed pinning, exclusion and expiry with time control; processor ordering; admin actions and audit rows; composer states; PinnedEmergencies. E2E: an eligible user posts an emergency → it's pinned in Recent → a moderator marks it FALSE (service fixture) → it's no longer pinned and shows FALSE.

**Recommended models**
- **Plan:** Opus 5.5 · xhigh. It changes the core state machine and is the highest-harm feature.
- **Implement:** Opus 5.5 · high. Time-dependent routing and abuse rules need precise implementation.

---

## Part 11D: Charts & stats
**Status:** [ ] Not started
**Goal:** the Stitch charts, re-purposed for data we really have (D5; ANALYSIS f-6): how a fact post was checked and how it spread, and an account's credibility over time.
**Depends on:** 7B (repost data), 11B (credibility data).
**Stitch files to convert:**
- `b3_post_detail_forensic_proof`:
  - "Consensus Gauge" → a confidence meter with the threshold marked
  - the three tiles → Confidence · Threshold and margin · Time to verdict
  - the "Exhibit A" bar chart → reposts and likes per day
- `c1_user_profile`: the "Epistemic Standing" ring widget → the Credibility widget.
- `b4_search_results`: the sparkline → the 30-day credibility trend inside that widget.
- `c2_account_settings`: the "Credibility Index" bar → CredibilityPanel (placed on the settings page in Part 14).

**Backend scope**
- `GET /api/v1/posts/{id}/stats/` (ARCHITECTURE §9):
  - same visibility as the detail endpoint
  - confidence and threshold only for `verdict_source=pipeline`
  - `seconds_to_verdict`, `verdict_at`, and `daily` buckets (UTC days, the first 14 days after posting) of reposts, likes and comments
  - a constant number of queries; uncached
- `GET /api/v1/users/{u}/reputation/` gains `trend`: 30 daily points from the ledger's `score_after` (null while the score is hidden).

**Frontend scope**
- `src/components/ui/charts/`:
  - `MeterBar` (with a threshold marker), `StatTile`, `BarChart` (token-built HTML bars, as Stitch b3 does), `RingGauge` and `Sparkline` (inline SVG using `currentColor` + token classes)
  - each has `role="img"`, an `aria-label` summary and a visually hidden data table, and no animation with reduced motion
  - **no chart library**
- `PostStats` on `/p/[id]` ("How this was checked"). Moderator verdicts show "Reviewed by a moderator" and the time to decision, with no %.
- `CredibilityWidget` on profiles: ring (score or "New"), "20 verified · 3 FALSE", the 30-day sparkline, "How this is calculated".
- `CredibilityPanel`: score bar and your full history, with reversed items marked and an "Ask for another look" link on each negative item. Shown on your own profile now, and in settings from Part 14.

**API endpoints:** `GET /api/v1/posts/{id}/stats/`; `trend` on the reputation endpoint.

**Acceptance criteria**
- [ ] Moderator-decided posts never show a confidence %; pending posts show no meter
- [ ] Every chart has a text alternative (screen-reader table) and uses token colours only (`lint:tokens` passes)
- [ ] `package.json` has no chart library
- [ ] The stats and trend endpoints use a constant number of queries; a post with no activity shows empty bars, not an error
- [ ] Day buckets are correct across UTC midnight (time-controlled test)

**Required tests:** stats endpoint (shape, visibility per status and viewer, bucket boundaries, query counts); trend endpoint; each chart primitive (render, aria, empty data); PostStats and CredibilityWidget states. E2E: open a `#true` fact → the meter shows 95 % with the threshold at 85 %.

**Recommended models**
- **Plan:** Sonnet 5.5 · high. The data mapping and accessibility need care.
- **Implement:** Sonnet 5.5 · medium. Presentational components plus two read endpoints.

---

## Part 12: Search
**Status:** [ ] Not started
**Goal:** Postgres full-text search over posts, plus people search (guide §10), with no new service.
**Depends on:** 6, 11B (the credibility score in people results).
**Stitch files to convert:** `b4_search_results`: query box, Posts/People tabs, filter chips, result cards, load more. Drop Primary Sources, certainty sort, the claim-data telemetry box and the contributor spotlight (ANALYSIS b-3).

**Backend scope**
- `search_vector` `GeneratedField` + GIN index migration.
- `GET /api/v1/search/`:
  - `type=posts`: `websearch` query, `SearchRank`, filters `post_type` and `status`, excludes removed and deleted
  - `type=users`: prefix match on username and display name, returned with the `reputation` block (never sorted by it)
  - Pagination: bounded offset (max 5 pages), because rank order can't use a cursor. Documented deviation.
  - Throttled per IP.

**Frontend scope:** `/search` (from the top bar): tabs; chips All / Facts / Opinions / Verified / FALSE / Under review; results with query terms highlighted using a safe text-splitting util (no HTML); UserRows with CredibilityBadge; empty and no-results states; load more.

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
**Depends on:** 7, 7B, 10, 11, 11C (all the event sources).
**Stitch files to convert:** `c4_notifications`. The item types are rebuilt for the MVP and there are no filter tabs. The emergency item's `tertiary` styling is used for `emergency_demoted`.

**Backend scope**
- `notifications.Notification` with every type in ARCHITECTURE §2.
- `notifications.services.notify()`, called explicitly (no signals) from: follow, like, comment, repost, pipeline verdict and under-review, moderator remove and verdict, emergency priority removed (11C), appeal resolved (label and removal appeals).
- Dedupe follow, like and repost; no self-notifications.
- `GET /api/v1/notifications/` (cursor), `GET …/unread-count/` (indexed, ≤2 queries, uncached), `POST …/mark-read/` (`ids` or `all`).

**Frontend scope:** `/notifications`: items with a glyph, actor avatar, post excerpt, relative time and unread dot; mark all as read; mark read on click. A sidebar unread badge via `useUnreadCount` (30 s, visible-only). Empty state.

**API endpoints:** the three notification endpoints above.

**Acceptance criteria**
- [ ] Each event creates exactly one notification for the right recipient; none for your own actions; repeated like/unlike or repost/unrepost doesn't spam
- [ ] The unread count uses ≤2 queries and polling stops on a hidden tab

**Required tests:** one creation test per event type, dedupe, API, NotificationItem variants, hook timers; E2E: B likes A's post → A sees the badge and the item.

**Recommended models**
- **Plan:** Sonnet 5.5 · medium. The hooks into existing services are straightforward.
- **Implement:** Sonnet 5.5 · medium. Straightforward.

---

## Part 14: Account settings, data export, account deletion
**Status:** [ ] Not started
**Goal:** users can edit their profile, manage their password, download their data, and delete their account (guide §16 GDPR/CCPA note).
**Depends on:** 6, 7, 7B, 11B, 11D.
**Stitch files to convert:** `c2_account_settings`, subset only (ANALYSIS b-1). The avatar card comes in 14B; the "Credibility Index" bar is the CredibilityPanel from 11D.

**Backend scope**
- `PATCH /api/v1/me/`: display_name, username (validated, unique), bio ≤280.
- `POST /api/v1/me/password/`: only if the password is usable.
- `GET /api/v1/me/export/`: JSON of your own profile, posts, comments, likes, follows, bookmarks, reposts, reports, appeals and your credibility history (ledger rows).
- `DELETE /api/v1/me/`:
  - confirmed by password, or by typing your username for Google-only accounts
  - cascades your content, bookmarks, reposts and ledger rows
  - moderation logs keep their snapshots
  - logs you out

**Frontend scope:** `/settings` with sections:
- Profile (display name, username, bio with counter; the photo is added in 14B)
- Account (email read-only with a verified chip; change password, or "Signed in with Google")
- Credibility (the CredibilityPanel from 11D: score, history, "Ask for another look" links)
- Your data (Download JSON)
- Danger zone (delete modal with typed confirmation)

Plus toasts and field errors.

**API endpoints:** the four `/me` endpoints above.

**Acceptance criteria**
- [ ] Profile edits show up everywhere; a taken username gives a field error
- [ ] The export contains all of your own data (including bookmarks, reposts and credibility history) and nothing private about anyone else
- [ ] Deletion removes the user and their content, logs them out, and the audit trail keeps its post snapshots

**Required tests:** API validation, export contents and privacy, deletion cascade and audit retention, forms; E2E: edit profile → export → delete account.

**Recommended models**
- **Plan:** Opus 5.5 · medium. Deletion cascades and privacy correctness deserve the stronger model.
- **Implement:** Sonnet 5.5 · medium. Standard forms and endpoints.

---

## Part 14B: Photo avatars
**Status:** [ ] Not started
**Goal:** optional profile photos (D5), with initials as the fallback everywhere (ANALYSIS f-7; ARCHITECTURE §4e):
- processed so that nothing from the uploaded file survives except resized pixels
- stored in Postgres, with no new service

**Depends on:** 14 (settings page). Uses the relay's cache-header passthrough from 0C.
**Stitch files to convert:**
- `c2_account_settings`: the avatar card ("Verified Institutional Avatar" → "Profile photo": preview, Upload, Remove).
- Every avatar spot, through the 0B `Avatar` primitive now given `avatar_url`: sidebar user card, top bar, post cards, detail author, comments, user rows, notifications, profile header.

**Backend scope**
- Add `Pillow` 12.3.x to `requirements.txt` (SETUP B1). Why: decoding, validation and re-encoding need a real image library. Pillow is the standard one, with prebuilt wheels for Windows and Render.
- `accounts.Avatar` per ARCHITECTURE §2, and `apps/accounts/avatars.py` implementing ARCHITECTURE §4e exactly:
  - format checked by decoding
  - pixel and size limits before the full decode
  - EXIF orientation applied, then all metadata dropped
  - centre crop, WebP at 256 and 96 px
  - the original discarded
- Endpoints:
  - `PUT /api/v1/me/avatar/`: multipart `file`; email-verified; not `avatar_uploads_blocked`; throttle `avatar_upload`
  - `DELETE /api/v1/me/avatar/`
  - `GET /api/v1/avatars/{user_id}/{version}-{size}.webp`: public; headers per ARCHITECTURE §4e; a wrong version or size → 404
- `avatar_url` in every author/user payload, built from `avatar_version` (no extra query).
- Admin: AvatarAdmin (thumbnail, newest first) with **Remove photo** and **Block photo uploads**, logged as `avatar_removed` / `avatar_blocked` with `subject_user`.
- The export includes your photo (256 px, base64); account deletion removes it.

**Frontend scope**
- `AvatarUploader` in /settings → Profile:
  - file input with `accept="image/jpeg,image/png,image/webp"`
  - square preview; the browser downscales to ≤1024 px before upload
  - progress
  - errors: too large, wrong type, too small, blocked, unverified
  - Remove photo
- `Avatar` shows the photo (`alt=""` beside the name, or the name as alt when alone) and falls back to initials on error.

**API endpoints:** the three avatar endpoints above.

**Acceptance criteria**
- [ ] A JPEG with GPS EXIF comes back as WebP with no EXIF, GPS, ICC or XMP data
- [ ] Each of these is refused with a clear error and without large memory use: SVG, GIF, HEIC, a PNG renamed to `.jpg`, a file over 5 MB, an image over 25 MP (decompression bomb), one under 128×128
- [ ] Only WebP is ever served; the original upload is never stored
- [ ] Changing the photo changes its URL; old URLs return 404
- [ ] Image responses carry the immutable cache header, `nosniff` and the sandbox CSP; a repeat request through the relay gets 304
- [ ] A moderator's Remove photo switches the user to initials everywhere at once; Block photo uploads makes uploads fail with 403
- [ ] Unverified users get 403 `email_unverified`

**Required tests:** processing unit tests with fixtures generated in the test (EXIF/GPS, rotation, each rejected type, bomb, tiny image); API permissions, throttle and headers; admin actions and audit rows; export and deletion; AvatarUploader states; Avatar fallback. E2E: upload a photo → it shows in the sidebar and on your post cards.

**Recommended models**
- **Plan:** Opus 5.5 · high. Handling untrusted files is security-sensitive.
- **Implement:** Sonnet 5.5 · high. The plan pins down every limit and header.

---

## Part 15: Landing & static pages
**Status:** [ ] Not started
**Goal:** the public face: a landing page, "How verification works", Privacy and Terms (required by Google OAuth and guide §16), error pages, and proper titles everywhere.
**Depends on:** 4 (the landing preview uses the Recent feed), 11B and 11C (the page explains them).
**Stitch files to convert:** `a1_logged_out_home`; `design/stitch/code.html` (layout for the taxonomy table, the confidence-ramp illustration and the FAQ only, with copy rewritten); marketing footer.

**Backend scope:** none.

**Frontend scope**
- `/`: prerendered, with `<Logo/>`.
  - Hero, 3 feature cards in plain language, a live preview of 4 recent posts fetched client-side.
  - "© 2026 Rumor Zero"; no fabricated organisations or people; no taglines from Stitch.
  - Logged-in visitors see "Go to your feed".
- `/how-it-works`:
  - the status table rendered with the real StatusBadges (including EMERGENCY), and the lifecycle
  - an FAQ with real answers: why opinions aren't checked, reports, appeals (FALSE labels and removals), the pipeline, emergency posts, and why reposts keep the original's label
  - a `#credibility` section: how the score is calculated in plain words, what raises and lowers it, when it's shown, and how to appeal. Marked **"needs legal review"** (guide §16).
- `/privacy`, `/terms`: placeholder text clearly marked **"needs legal review"**. The Terms placeholder has explicit sections on verification labels and the credibility score.
- `not-found` and `error` pages (with `<Logo/>`).
- `<title>` = "<Page> · Rumor Zero" on every route. The favicon, icons and share image already exist from 0D.

**API endpoints:** none new.

**Acceptance criteria**
- [ ] The landing page matches the a1 layout, and none of the Stitch sample names, organisations or taglines appear anywhere
- [ ] `/how-it-works#credibility` explains every event in the ARCHITECTURE §4a table and the appeal path
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
**Depends on:** every part above (0A–15, including 0D, 7B, 11B–11D and 14B). Needs k6 (SETUP A6).
**Stitch files to convert:** none.

**Backend scope**
- Go through ARCHITECTURE §12 point by point, including the new rows:
  - profile-photo abuse (disguised files, decompression bombs, SVG, oversized)
  - source-list handling (all sources of a post) and the "never fetched" test
  - the emergency safeguards
  - the credibility score's appeal and audit path
- `check --deploy` clean.
- Security headers and cookie flags verified by tests; admin path confirmed.
- Throttle review; secret-leak scan of the repo (patterns); logging review (no tokens or PII).
- `seed_demo` command (dev-only; refuses when DEBUG=False) creating around 10k posts.
- `.github/dependabot.yml` (pip, npm, github-actions, weekly).
- `pip-audit`/`npm audit`, triaged.

**Frontend scope:** a Content-Security-Policy in `next.config.ts` headers that allows only self, Turnstile and Google Identity Services (`img-src 'self' data:` plus Google's button images, which covers the logo and `/api/v1/avatars/`); verify there are no violations and no `dangerouslySetInnerHTML`; the full E2E journey suite.

**Load test:** `loadtest/*.js` k6 scripts against the local stack with seeded data (`seed_demo` also creates reposts, bookmarks and a few active emergencies):
- feed read at 50 VUs, including reposts and pinned emergencies
- post create
- report burst
- avatar image fetch
- `EXPLAIN` on the hot queries

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
**Depends on:** 16. You do the account and dashboard steps in ENV_GUIDE §2.0–2.6; the active agent prepares the config and checklists and **never handles secret values**.
**Stitch files to convert:** none.

**Backend scope**
- `render.yaml` Blueprint: rootDir `backend`, build and start commands from ENV_GUIDE §2.6, health check path, auto-deploy after checks; env var **keys** only (including the optional `EMERGENCY_*` keys), with secrets marked `sync: false`.
- A production settings review. Pillow installs from its prebuilt Linux wheel, so no system packages are needed; photo processing stays within 512 MB thanks to the limits in ARCHITECTURE §4e.
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
- A Playwright production smoke test (`PLAYWRIGHT_BASE_URL=<FRONTEND>`):
  - the landing page loads with the favicon and an `og:image` that returns 200
  - the signup page shows the Turnstile widget
  - `/api/health/` through the relay works
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
- [ ] A shared post link shows the Rumor Zero preview image; a profile photo upload works end to end in production
- [ ] Emails arrive with the logo image loading from `<FRONTEND>/brand/email-logo.png`
- [ ] The FRONTEND URL is filled in ARCHITECTURE §0; the ENV_GUIDE master table matches reality

**Required tests:** the production smoke suite, the keepalive workflow run, the k6 smoke run.

**Recommended models**
- **Plan:** Opus 5.5 · high. Cross-service wiring (origins, keys, cookies, build vs runtime variables) is where deployments fail.
- **Implement:** Sonnet 5.5 · medium. Configuration plus a small workflow and tests.
