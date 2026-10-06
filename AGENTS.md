# Rumor Zero: shared agent instructions

This is the canonical instruction file for **both Codex and Claude Code**. Codex reads it
directly. `CLAUDE.md` tells Claude Code to read it. Keep shared rules here instead of maintaining
two copies that can drift.

**Name:** Rumor Zero · **slug:** `rumor-zero` · underscore form `rumor_zero` only where
Python/Postgres require it. Never use the project's earlier working name. All names and URLs:
`docs/ARCHITECTURE.md §0`.

Rumor Zero is a social platform where every post is **text-only** and labelled **Opinion** or
**Fact**:

- Opinions publish immediately.
- Fact posts appear with a "Checking facts…" badge. A fact-check pipeline (stubbed for now) then
  marks them verified true, FALSE, or under review. Labels always say FALSE, never "debunked".
- Reports (threshold within a time window) and author appeals (FALSE labels and removals) send
  posts to human moderators, who work in Django Admin.
- Emergency fact posts are pinned for 24 h, still fact-checked first, and protected by abuse
  safeguards.
- Every account has a public **credibility score** (0–100) driven by fact-check outcomes, with an
  appeal path.
- Also: follow, like, comment, repost, bookmark, up to five optional sources (URL or DOI) on fact
  posts, charts, search, notifications, profile photos.
- The only images are profile photos and the logo.

## Read these first

Read only what the current part needs, but always read these before planning or editing:

1. `docs/agents/HANDOFF.md`: live cross-agent state and the exact next action.
2. `docs/agents/MEMORY.md`: durable discoveries that are not already recorded elsewhere.
3. The named part in `task.md`: ordered scope, acceptance criteria, required tests and status.
4. Relevant sections of `docs/ARCHITECTURE.md`: **product and technical source of truth**.
5. The current part's approved plan under `docs/agents/plans/`, when one exists.

Use these only when relevant:

- `docs/ANALYSIS.md`: decisions D1–D10 and their reasoning. Section f holds Stitch-only rules.
- `docs/STRUCTURE.md`: where every file goes.
- `docs/SETUP.md` / `docs/ENV_GUIDE.md`: tools, accounts and env vars.
- Visual source of truth: `design/stitch/**/code.html` + `design/stitch/DESIGN.md` (read-only;
  `screen.png` is only a reference).
- Logo: `design/logo.svg` (read-only master; `design/logo.png` is an older raster, unused). Rules
  and assets: `docs/ARCHITECTURE.md §14`.
- Re-read the PDF in `docs/` only when `ARCHITECTURE.md` is silent, then update
  `ARCHITECTURE.md` with the conclusion.

## Claude ↔ Codex coordination

1. **One writer at a time.** Never run Claude and Codex concurrently in the same checkout. A
   takeover is sequential: the current agent writes a checkpoint, stops, and the next agent
   verifies the workspace before continuing.
2. At the start of a part, inspect `git status`, `git diff` and `docs/agents/HANDOFF.md` using
   read-only commands. Do not discard or overwrite work you did not create.
3. Before implementation, save the user-approved plan as
   `docs/agents/plans/part-<ID>-<short-title>.md`. The plan must list scope, files, ordered steps,
   tests and stop conditions so either agent can execute it.
4. Update `docs/agents/HANDOFF.md` after a meaningful checkpoint, after running tests, before a
   planned switch, when blocked, or when context/usage is running low. Record facts, not a chat
   transcript. Include the exact next command or edit.
5. Update `docs/agents/MEMORY.md` only for durable discoveries or decisions likely to matter in
   later parts and not already captured by `ARCHITECTURE.md`, `ANALYSIS.md` or `task.md`. Never put
   secrets, guesses, routine progress or transient failures there.
6. Source ownership:
   - shared workflow/coding rule → `AGENTS.md`
   - Claude-only startup/tool behavior → `CLAUDE.md` or `.claude/settings.json`
   - Codex-only defaults/command policy → `.codex/config.toml` or `.codex/rules/`
   - live continuation state → `docs/agents/HANDOFF.md`
   - durable learned context → `docs/agents/MEMORY.md`
   - approved implementation plan → `docs/agents/plans/`
   - product/technical decision → `docs/ARCHITECTURE.md` and, for D-decisions, `docs/ANALYSIS.md`
   - build progress and acceptance criteria → `task.md`
7. Do not mirror the same prose into `CLAUDE.md` and `AGENTS.md`. Both agents may maintain all of
   the files above, but each fact has one canonical home.
8. A handoff is not complete until the outgoing agent records changed files, validation results,
   blockers and the next exact action. The incoming agent must verify those claims from the
   current files before editing.

Cross-vendor takeover is not automatic. If one service reaches its usage limit, the user starts
the other agent with the takeover prompt in `task.md`; the repository files carry the context.

## Stack

- **Backend:** Python 3.13, Django 5.2 LTS, DRF, django-allauth (headless + JWT), Postgres 18
  (Neon), Redis (Upstash), gunicorn on Render free.
- **Frontend:** Node 24, Next.js 16 App Router + TypeScript, Tailwind CSS v4 (`@theme` tokens from
  Stitch), Cloudflare Workers via OpenNext.
- **Tests:** pytest-django · Vitest + React Testing Library · Playwright. **CI:** GitHub Actions.
- One monolith. No Celery, Kubernetes, microservices, GraphQL, search engine or object storage.
- The browser only talks to the frontend origin. `/api/*` goes through the **API relay**
  (`frontend/src/app/api/[...path]/route.ts`) to Django.

## Folder map

```text
backend/    manage.py · rumor_zero/ (settings, urls) · apps/{core,accounts,posts,social,reports,pipeline,moderation,reputation,notifications}
frontend/   src/app (routes; api/[...path] = relay) · src/components/{ui,shell} · src/features/<domain> · src/lib/{api,auth} · scripts/brand · public/brand · e2e/
docs/       ARCHITECTURE, ANALYSIS, STRUCTURE, SETUP, ENV_GUIDE, agents/, original PDF
design/     logo.svg (master logo) · logo.png (old, unused) · stitch/ (Stitch exports), all read-only
.claude/    Claude Code permissions
.codex/     Codex defaults and command rules
.github/workflows/ci.yml · compose.yaml (local Postgres + Redis) · task.md
```

## Commands (exist after Part 0; Linux bash, Windows differences below)

```bash
docker compose up -d                        # repo root: local Postgres 18 + Redis
# backend (cd backend)
python3.13 -m venv .venv                    # once
source .venv/bin/activate                   # every new terminal
pip install -r requirements-dev.txt
python manage.py migrate
python manage.py runserver                  # http://localhost:8000 (admin: /admin/)
python manage.py process_pending --loop     # optional: local pipeline sweeper
pytest                                      # backend tests (needs Postgres up)
pytest --cov=apps
ruff check . ; ruff format --check .        # lint + format check (fix: ruff format .)
ruff check --fix . ; ruff format .          # right after startproject/startapp/makemigrations
python manage.py makemigrations --check --dry-run
# frontend (cd frontend)
npm ci                                      # clean install from package-lock.json (first time)
npm run dev                                 # http://localhost:3000
npm run lint ; npm run typecheck ; npm test # eslint, tsc --noEmit, vitest run
npm run test:e2e                            # Playwright (starts both servers)
npm run build
npm run brand:build                         # after Part 0D: regenerate assets from design/logo.svg
```

- **Two machines.** From 2026-10-06 the user works on **Linux** (Ubuntu/Debian/Mint, bash). The earlier
  machine is **Windows 11 with PowerShell 5.1**. Check the platform before choosing shell syntax.
  `docs/SETUP.md`, `docs/ENV_GUIDE.md` and `docs/test-command.md` hold both versions, Linux first.
- Windows differences: `py -3.13 -m venv .venv` and `.\.venv\Scripts\Activate.ps1`; PowerShell 5.1 has
  no `&&` (use `;` or `if ($?) { … }`); Git Bash also exists; `npx playwright install chromium`
  without `--with-deps`.
- gunicorn does not run on Windows, and neither does the OpenNext build. The build runs on Linux (CI,
  Cloudflare Workers Builds, the user's Linux PC), never from a checkout with a real `.env.local`.
  gunicorn runs on Render.

## Code conventions

### Backend

- Domain code lives in `backend/apps/<name>/`. Logic goes in `services.py`; views and serializers
  stay thin.
- **Only** `apps/posts/services.py` and `apps/moderation/services.py` change `Post.status` (and the
  emergency fields). Routing rules are pure functions in `apps/pipeline/routing.py`.
- **Only** `apps/reputation/services.py` writes credibility-ledger rows and `users.reputation_*`.
  Posts and moderation services call it explicitly in the same transaction; the ledger is
  append-only.
- "Active emergency" is computed at read time (`is_active_emergency(post, now)`). No scheduler or
  job ever flips it.
- A user-supplied source URL is validated and stored, **never fetched** by the server.
- Status-changing writes use `transaction.atomic()` + `select_for_update()`.
- Models use UUID PKs (bigint for follows/likes/bookmarks/reposts), `created_at`, enums as
  `TextChoices` + DB `CheckConstraint`s, and every model is registered in the admin.
- Use `timezone.now()`, and give time-dependent functions a `now` parameter for tests. UTC
  everywhere.
- Settings come only from env via django-environ (process env overrides `.env`). A new setting
  also goes into `backend/.env.example` + `docs/ENV_GUIDE.md`.
- ruff line length is 100. Tests live in `apps/<name>/tests/test_*.py` with factory-boy. Assert
  query counts on list endpoints.
- Generated code (`startproject`/`startapp` output and every new migration) is normalised with
  `ruff check --fix . ; ruff format .` straight after generation, then kept formatted. Django only
  auto-runs black, which we don't install, so its raw output is single-quoted and fails
  `ruff format --check`. Don't exclude migrations from ruff.
- A new app: create `apps/<name>/` first (`startapp` refuses a missing folder), run
  `python manage.py startapp <name> apps/<name>`, then set `name = "apps.<name>"` in its `apps.py`.

### Frontend

- TypeScript strict. Server Components by default; `"use client"` only where there is state or
  events.
- Every API call goes through `src/lib/api/client.ts` (relative `/api`). Never call the backend
  origin from the browser.
- The access token lives **in memory only**, never in localStorage or sessionStorage.
- UI primitives are in `src/components/ui`, screens compose `src/features/<domain>`, and route
  files stay thin.
- Tokens exist **only** in `src/app/globals.css` (`@theme`). Copy class names from Stitch. Use no
  Tailwind default palette, no raw hex, only `rounded-lg`/`rounded-full`, and `shadow-sm` only.
- Fact text uses `font-claim-headline text-claim-headline`; opinions add `italic` with the
  `claim-opinion` tokens.
- Icons use `<Icon name="…"/>`. Avatars use `<Avatar>`: the user's photo when set, initials
  otherwise and on load error.
- Show the brand **only** through `<Logo/>` (`src/components/ui/Logo.tsx`). Never re-create the old
  text wordmark or emblem tiles, and never hand-edit files in `public/brand/`; they are generated
  by `npm run brand:build`.
- The logo's colours (grey `#898a8d`, cyan `#23b5d8`) stay inside the image. Never use them for UI.
- Charts are token-built HTML/SVG with a text alternative. No chart library.
- User content is plain text (`whitespace-pre-wrap`). Never use `dangerouslySetInnerHTML`.
- `NEXT_PUBLIC_*` is for non-secrets only. A new variable goes into `frontend/.env.example` +
  `docs/ENV_GUIDE.md`.
- Component tests sit next to the code as `*.test.tsx`; E2E specs go in `frontend/e2e/`.

## Hard rules

1. **Never run git commands that change state:** add, commit, push, pull, fetch, merge, rebase,
   reset, checkout, switch, restore, branch, tag, stash, rm, mv, clean, cherry-pick, revert,
   config, remote, init, clone and related mutations. The same applies to `gh` writes. Read-only
   `git status`, `git diff`, `git log` and `git show` are fine. **The user does all git
   operations.** Claude has `.claude/settings.json`; Codex has `.codex/rules/default.rules`; this
   prose still applies where enforcement cannot.
2. **Never print, log, echo or commit secrets.**
   - Real env files (`backend/.env`, `frontend/.env.local`) may be read or edited only when the
     user explicitly asks and authorizes it. Never repeat values in chat, command output, logs or
     other files; refer to variables by name. New variables still go into `*.env.example` and
     `docs/ENV_GUIDE.md`.
   - `.dev.vars`, `.env.development.local`, `.env.test.local`, `.env.production` and
     `.env.production.local` stay denied. Production secrets never go into any file.
   - Never ask the user to paste a secret into chat. Tests use values from example files. Logs
     must not contain tokens, passwords or keys.
3. **Free tier only.** Ask before adding any new external service, SaaS or paid dependency.
   Prefer no new dependency and explain why whenever one is added.
4. **Work only on the part the user names, and stop when it is done.** Do not change other parts
   beyond what that part strictly needs; list anything else as a follow-up.
5. When a part is finished, update both status locations in `task.md`: tick its acceptance
   criteria, set `Status: [x] Done (YYYY-MM-DD)`, update the summary table, and note deviations.
6. Every part includes the listed tests. A part is not done while any required test, lint or type
   check fails. Record the exact commands and results in `HANDOFF.md`.
7. Follow `docs/ARCHITECTURE.md`. If a part changes a design decision, update it (and
   `ANALYSIS.md` for D-decisions) in the same part and report the change.
8. Posts and comments stay text-only: no image, video or file uploads. The only images are profile
   photos (Part 14B) and the logo. **`design/` is read-only:** never modify, move or delete
   `design/logo.*` or anything in `design/stitch/`. The user supplies design changes.
9. Do not let `create-next-app` add `frontend/CLAUDE.md` or `frontend/AGENTS.md`
   (`--no-agents-md`).
10. If project documentation appears wrong or outdated (version, free-tier limit, dashboard path,
    API behavior), verify it against current primary documentation, update the relevant source of
    truth, and tell the user.

