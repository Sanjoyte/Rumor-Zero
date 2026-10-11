# Rumor Zero

A text-only social platform where every post is labelled **Opinion** or **Fact**, and facts get checked.

- **Opinions** publish immediately.
- **Fact posts** appear with a "Checking facts…" badge. A fact-check pipeline then marks them verified
  true, **FALSE**, or under review. (The pipeline is a stub for now.)
- **Reports** (a threshold within a time window) and **author appeals** (of FALSE labels and removals)
  go to human moderators, who work in Django Admin.
- **Emergency fact posts** are pinned for 24 hours, still fact-checked first, and protected by abuse
  safeguards.
- Every account has a public **credibility score** (0–100) driven by fact-check outcomes, with an
  appeal path.
- Also: follow, like, comment, repost, bookmark, up to five optional sources (URL or DOI) on fact
  posts, charts, search, notifications and profile photos.

Posts and comments are text-only. The only images are profile photos and the logo.

## Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.13, Django 5.2 LTS, Django REST Framework, django-allauth (headless + JWT) |
| Database / cache | Postgres 18 (Neon in production), Redis (Upstash in production) |
| Frontend | Node 24, Next.js 16 (App Router, TypeScript), Tailwind CSS v4 |
| Hosting | Render (backend), Cloudflare Workers via OpenNext (frontend), all free tier |
| Tests / CI | pytest-django, Vitest + React Testing Library, Playwright, GitHub Actions |

It is one monolith: no Celery, Kubernetes, microservices, GraphQL, search engine or object storage.
The browser only talks to the frontend origin. `/api/*` goes through an API relay
(`frontend/src/app/api/[...path]/route.ts`) to Django.

## Repository layout

```text
backend/    Django project (rumor_zero/) and apps/{core,accounts,posts,social,reports,pipeline,moderation,reputation,notifications}
frontend/   Next.js app: src/app, src/components, src/features/<domain>, src/lib, e2e/
docs/       ARCHITECTURE, ANALYSIS, STRUCTURE, SETUP, ENV_GUIDE, agents/
design/     logo.svg and Stitch exports (read-only)
task.md     ordered build plan, acceptance criteria and status
compose.yaml  local Postgres + Redis
```

## Getting started (Linux)

Full tool and account setup is in [docs/SETUP.md](docs/SETUP.md); environment variables are in
[docs/ENV_GUIDE.md](docs/ENV_GUIDE.md). Windows commands are in both.

```bash
docker compose up -d                  # repo root: Postgres 18 + Redis

# backend
cd backend
python3.13 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env                  # then fill in values
python manage.py migrate
python manage.py runserver            # http://localhost:8000 (admin: /admin/)

# frontend (second terminal)
cd frontend
npm ci
cp .env.example .env.local            # then fill in values
npm run dev                           # http://localhost:3000
```

## Testing and checks

```bash
# backend (needs Postgres up)
pytest
ruff check . ; ruff format --check .
python manage.py makemigrations --check --dry-run

# frontend
npm run lint ; npm run typecheck ; npm test
npm run test:e2e                      # Playwright, starts both servers
npm run build
```

More commands per part: [docs/test-command.md](docs/test-command.md).

## Status

Built part by part; see [task.md](task.md) for the full list. Parts 0–9 are done (foundation, auth,
posts and feeds, social features, reporting, and the fact-check pipeline stub with routing). Next up is
Part 10, the human review panel in Django Admin. Deployment (Parts 17–18) is last.

## Documentation

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): product and technical source of truth
- [docs/ANALYSIS.md](docs/ANALYSIS.md): design decisions and their reasoning
- [docs/STRUCTURE.md](docs/STRUCTURE.md): where every file goes
- [AGENTS.md](AGENTS.md): conventions and rules for Claude Code and Codex contributors
