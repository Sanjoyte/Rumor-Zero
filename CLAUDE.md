# CLAUDE.md: Rumor Zero

**Name:** Rumor Zero · **slug:** `rumor-zero` · underscore form `rumor_zero` only where Python/Postgres require it.
Never use the project's earlier working name. All names and URLs: `docs/ARCHITECTURE.md §0`.

Rumor Zero is a **text-only** social platform where every post is labelled **Opinion** or **Fact**:
- Opinions publish immediately.
- Fact posts appear with a "Checking facts…" badge. A fact-check pipeline (stubbed for now) then marks them verified true, verified false, or under review.
- Reports (threshold within a time window) and author appeals send posts to human moderators, who work in Django Admin.
- Also: follow, like, comment, search, notifications.

## Read these first
- `docs/ARCHITECTURE.md`: **source of truth** (schema, status lifecycle, auth, API, config values). Follow it. Re-read the PDF in `docs/` only if ARCHITECTURE is silent, then update ARCHITECTURE.
- `task.md`: ordered build parts, scope, acceptance criteria, status.
- `docs/ANALYSIS.md`: decisions D1–D10 and the reasoning behind them. `docs/STRUCTURE.md`: where every file goes.
- `docs/SETUP.md` / `docs/ENV_GUIDE.md`: tools, accounts, env vars.
- Visual source of truth: `design/stitch/**/code.html` + `design/stitch/DESIGN.md` (read-only; `screen.png` is only a reference).

## Stack
- **Backend:** Python 3.13, Django 5.2 LTS, DRF, django-allauth (headless + JWT), Postgres 18 (Neon), Redis (Upstash), gunicorn on Render free.
- **Frontend:** Node 24, Next.js 16 App Router + TypeScript, Tailwind CSS v4 (`@theme` tokens from Stitch), Cloudflare Workers via OpenNext.
- **Tests:** pytest-django · Vitest + React Testing Library · Playwright. **CI:** GitHub Actions.
- One monolith. No Celery, Kubernetes, microservices, GraphQL, search engine, or object storage.
- The browser only talks to the frontend origin. `/api/*` goes through the **API relay** (`frontend/src/app/api/[...path]/route.ts`) to Django.

## Folder map
```
backend/    manage.py · rumor_zero/ (settings, urls) · apps/{core,accounts,posts,social,reports,pipeline,moderation,notifications}
frontend/   src/app (routes; api/[...path] = relay) · src/components/{ui,shell} · src/features/<domain> · src/lib/{api,auth} · e2e/
docs/       ARCHITECTURE, ANALYSIS, STRUCTURE, SETUP, ENV_GUIDE, original PDF
design/stitch/   Stitch exports (read-only)
.github/workflows/ci.yml · compose.yaml (local Postgres + Redis) · task.md
```

## Commands (exist after Part 0; PowerShell)
```powershell
docker compose up -d                        # repo root: local Postgres 18 + Redis
# backend (cd backend)
py -3.13 -m venv .venv                      # once
.\.venv\Scripts\Activate.ps1                # every new terminal
pip install -r requirements-dev.txt
python manage.py migrate
python manage.py runserver                  # http://localhost:8000 (admin: /admin/)
python manage.py process_pending --loop     # optional: local pipeline sweeper
pytest                                      # backend tests (needs Postgres up)
pytest --cov=apps
ruff check . ; ruff format --check .        # lint + format check (fix: ruff format .)
python manage.py makemigrations --check --dry-run
# frontend (cd frontend)
npm install
npm run dev                                 # http://localhost:3000
npm run lint ; npm run typecheck ; npm test # eslint, tsc --noEmit, vitest run
npm run test:e2e                            # Playwright (starts both servers)
npm run build
```
- The shell is **Windows PowerShell 5.1**: no `&&`, so use `;` or `if ($?) { … }`. The Bash tool (Git Bash) also exists.
- gunicorn and the OpenNext build don't run on Windows. They run in CI, on Render, and in Cloudflare Workers Builds.

## Code conventions
**Backend**
- Domain code lives in `backend/apps/<name>/`. Logic goes in `services.py`; views and serializers stay thin.
- **Only** `apps/posts/services.py` and `apps/moderation/services.py` change `Post.status`. The routing rules are pure functions in `apps/pipeline/routing.py`.
- Status-changing writes use `transaction.atomic()` + `select_for_update()`.
- Models:
  - UUID PKs (bigint for follows/likes)
  - `created_at`
  - enums as `TextChoices` + DB `CheckConstraint`s
  - every model registered in the admin
- Use `timezone.now()`, and give time-dependent functions a `now` parameter for tests. UTC everywhere.
- Settings come only from env via django-environ (process env overrides `.env`). A new setting also goes into `backend/.env.example` + `docs/ENV_GUIDE.md`.
- ruff (line length 100). Tests live in `apps/<name>/tests/test_*.py` with factory-boy. Assert query counts on list endpoints.

**Frontend**
- TypeScript strict. Server Components by default; `"use client"` only where there's state or events.
- Every API call goes through `src/lib/api/client.ts` (relative `/api`). Never call the backend origin from the browser.
- The access token lives **in memory only**, never in localStorage or sessionStorage.
- UI primitives are in `src/components/ui`, screens compose `src/features/<domain>`, and route files stay thin.
- Styling:
  - Tokens exist **only** in `src/app/globals.css` (`@theme`). Copy class names from Stitch.
  - **No** Tailwind default palette, no raw hex, only `rounded-lg`/`rounded-full`, `shadow-sm` only.
  - Fact text uses `font-claim-headline text-claim-headline`; opinions add `italic` with the `claim-opinion` tokens.
- Icons via `<Icon name="…"/>` (Material Symbols). Avatars are initials only.
- User content is plain text (`whitespace-pre-wrap`). Never `dangerouslySetInnerHTML`.
- `NEXT_PUBLIC_*` is for non-secrets only. A new variable goes into `frontend/.env.example` + `docs/ENV_GUIDE.md`.
- Component tests sit next to the code as `*.test.tsx`; E2E specs go in `frontend/e2e/`.

## Hard rules
1. **Never run git commands that change state**: add, commit, push, pull, fetch, merge, rebase, reset, checkout, switch, restore, branch, tag, stash, rm, mv, clean, cherry-pick, revert, config, remote, init, clone. The same goes for `gh` write commands. Read-only git (`status`, `diff`, `log`, `show`) is fine. **The user does all git operations.** `.claude/settings.json` enforces most of this; the rule applies even where it doesn't.
2. **Never print, log, echo or commit secrets.**
   - Don't read or write real env files (`backend/.env`, `frontend/.env.local`, `.dev.vars`); they're denied. Edit only `*.env.example`.
   - Never ask the user to paste a secret into chat.
   - Tests use the test values from the example files. Logs must not contain tokens, passwords or keys.
3. **Free tier only.** Ask before adding any new external service, SaaS, or paid dependency. Prefer adding no dependency at all, and say why whenever you add one.
4. **Work only on the part the user names, and stop when it's done.** No changes to other parts beyond what that part strictly needs; list anything else as a follow-up.
5. **When a part is finished, update its status in `task.md`**: tick its acceptance criteria, set `Status: [x] Done (YYYY-MM-DD)`, and note any deviations.
6. **Every part includes tests**, as listed in its "Required tests". A part isn't done while any test, lint or type check fails.
7. **Follow `docs/ARCHITECTURE.md` rather than re-reading the PDF** unless necessary. If a part changes a design decision, update ARCHITECTURE.md (and ANALYSIS.md for D-decisions) in the same part and say so.
8. Stay text-only: no image, video or file uploads, and no photo avatars.
9. Don't let `create-next-app` add `frontend/CLAUDE.md` or `AGENTS.md` (`--no-agents-md`).
10. If something in these docs is wrong or outdated (a version, a free-tier limit, a dashboard path), verify it on the web, fix the doc, and tell the user.
