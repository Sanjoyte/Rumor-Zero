# CLAUDE.md — Fact-Based Social Platform

Persistent project memory for Claude Code. Read this in full at the start of every session.
Source spec: the architecture guide this project is built from. Reference it by section number
(e.g. "§7.1") when you need the full rationale behind a decision below.
If this file conflicts with something assumed earlier in a stale session, this file wins.

## Stack — pinned, don't substitute without asking
- Frontend: Next.js (React) → deployed on **Cloudflare Pages**, not Vercel (Vercel's Hobby plan
  ToS forbids commercial use; Cloudflare Pages explicitly allows it)
- Backend: Django + Django REST Framework
- Database: PostgreSQL on Neon
- Cache / queue: Redis on Upstash
- Auth: djangorestframework-simplejwt — short-lived access token kept in memory (React state)
  only, NEVER localStorage; refresh token in an httpOnly, Secure, SameSite=Lax cookie —
  plus django-allauth for Google OAuth
- Password hashing: Argon2id first in `PASSWORD_HASHERS`, PBKDF2 kept only as a fallback for old hashes
- Bot / spam defense: Cloudflare Turnstile on signup + django-ratelimit on auth/report endpoints
- Background jobs (MVP only): a DB-polling Django management command — NOT Celery yet
- Search (MVP only): Postgres full-text (`tsvector` + GIN index) — NOT Elasticsearch/Meilisearch yet
- Email: Resend, not SendGrid (SendGrid's free tier no longer exists)

## Architectural decisions — don't "improve" these without asking first
- Monolith: one Django service, one Next.js app. No microservices, no GraphQL gateway.
- Cursor-based pagination on every feed query. Never OFFSET/LIMIT on the main feed.
- Feed is fan-out-on-read, cached in Redis for 20–60s. No precomputed per-user timelines.
- UUID primary keys everywhere, not auto-increment integers.

## Core enums — use these exact string values, everywhere, in every file
- `users.role`: `user` | `moderator` | `senior_moderator`
- `posts.post_type`: `opinion` | `fact`
- `posts.status`: `pending` | `published` | `verified_true` | `verified_false` | `under_review` | `removed`
  - ⚠️ `published` is REQUIRED for opinion posts (they skip verification entirely). The source
    guide's schema table lists only 5 values and omits it, but the submit-flow and routing-logic
    sections both require it. Don't drop it from a DB CHECK constraint, a Django `choices` tuple,
    or a serializer's enum — that mismatch is exactly the kind of thing that only shows up when
    someone tries to create an opinion post.
- `posts.flagged_reason`: `pipeline` | `reports` | `both` (nullable). If you build the appeals
  flow, decide first whether an appeal needs its own value here, then update this line.
- `moderation_actions.action`: `verified` | `marked_false` | `dismissed_report` | `removed` | `escalated`

## The fact-check pipeline contract — stable; build everything else against this shape
Input:  `{ post_id: UUID, content: string }`
Output: `{ verdict: "true" | "false" | "inconclusive", confidence_score: number (0-100), raw_result: <any JSON> }`
`raw_result` → `posts.pipeline_result` (JSONB). Schema-less on purpose — the real pipeline drops
in later against this exact contract with no migration needed anywhere else.

## Config values — Django settings, never hard-coded inside a function
- `REPORT_THRESHOLD = 5` (reports inside a rolling 24h window)
- `CONFIDENCE_THRESHOLD = 82` (starting point in the 80–85 range; retune once real score
  distributions exist)
- Reports from accounts younger than 24h don't count toward the threshold yet

## Commands
- Backend tests: `pytest` (run from `/backend`)
- Frontend tests: `npm test` (Jest + React Testing Library)
- E2E: `npx playwright test`
- Migrations: `python manage.py makemigrations && python manage.py migrate`
- Backend dev server: `python manage.py runserver`  ·  Frontend dev server: `npm run dev`

## Security rules — non-negotiable
- ORM / parameterized queries only. Never build raw SQL by string concatenation.
- The JWT access token lives in memory only. Never localStorage, ever, for any reason.
- `dangerouslySetInnerHTML` on user content only after running it through DOMPurify.
- `.env` is git-ignored from the first commit.
- A report's threshold check and its report-count increment happen inside one DB transaction.
- Never edit a migration after it has merged — write a new migration instead.

## Compact instructions
When compacting this conversation, always preserve: the current Django migration state, any
failing test output, and the enum table and pipeline contract above.

## Growing this file
Keep this file under ~150 lines. Once backend- and frontend-specific conventions start crowding
it out, split them into `backend/CLAUDE.md` and `frontend/CLAUDE.md` — Claude Code loads this
root file plus whichever subdirectory's file matches wherever it's actually reading or working,
so Django-only rules stay out of context during pure frontend sessions. See PLAN.md for what's
built and what's next.
