# PLAN.md — Build Roadmap

A living checklist, not a one-time document. Check items off as they land on `main`; edit this
file whenever a decision changes instead of letting it go stale.

## How to work through a phase
1. Start a fresh session per phase — don't carry Phase 2's context into Phase 3. `Shift+Tab`
   into plan mode, or launch with `claude --permission-mode plan`.
2. Point Claude at this phase's checklist and the guide section(s) it names. Let it explore the
   current code before proposing anything.
3. Review the plan before approving — `Ctrl+G` opens it in your editor in the terminal; the
   VS Code extension opens it as a commentable Markdown document automatically.
4. Approve, let it implement, then hand it the "Done when" line as something to actually run and
   show you evidence of, not just assert.
5. Check the box, commit, `/clear`, move to the next phase. If you've corrected the same thing
   twice in one phase, `/clear` and restate the instruction more specifically rather than
   correcting a third time.

## Phase 0 — Repo bootstrap (not in the original roadmap — do this first)
- [ ] `git init`; `.gitignore` excludes `.env`, `node_modules/`, `__pycache__/`, `*.pyc`
- [ ] Decide layout: monorepo (`backend/`, `frontend/`) — recommended so one session can see
      both sides of the API contract at once
- [ ] Add `CLAUDE.md` and this file to the repo root
- [ ] `.mcp.json` for shared MCP config (Neon, Context7 — see the tools guidance you were given)
- **Done when:** an empty Django project and an empty Next.js project both run locally, and the
  first commit is in.

## Phase 1 — Project skeleton (guide §1–2, §14)
- [ ] Django + DRF backend, Next.js frontend, Neon DB connected
- [ ] Deployed skeleton: Render (backend) + Cloudflare Pages (frontend — not Vercel)
- [ ] Cloudflare in front (DNS/CDN/TLS); Turnstile keys generated, not wired up yet
- **Done when:** a health-check endpoint answers in production on both free hosts.

## Phase 2 — Auth (guide §4)
- [ ] `users` table/migration, full field list from §3.1
- [ ] Signup: email + username + password OR Google OAuth; Turnstile token required
- [ ] Argon2id first in `PASSWORD_HASHERS`
- [ ] Email verification via Resend, 24h token expiry
- [ ] django-allauth Google OAuth wired
- [ ] simplejwt access/refresh split, exactly as CLAUDE.md's security rules describe
- [ ] django-ratelimit on signup/login
- **Done when:** pytest covers signup, login, token refresh, and a triggered rate limit, all
  green — and a human can actually sign up, verify, and log in through the deployed frontend.

## Phase 3 — Posts + feed, no verification yet (guide §5.1, §9)
- [ ] `posts` table/migration — confirm the `published` status value is in the DB constraint and
      any serializer choices before this migration lands (see CLAUDE.md's enum note)
- [ ] Opinion → `status='published'` immediately; Fact → `status='pending'`, visible immediately
      with a "Checking facts…" badge (no pipeline call yet — that's Phase 6)
- [ ] Reverse-chronological feed, cursor-based pagination, the `(status, created_at DESC)` index
- [ ] `select_related`/`prefetch_related` on the feed query from the start, not retrofitted later
- **Done when:** the feed query doesn't N+1 against 50+ seeded posts — check the query count in
  a test, or with `django-debug-toolbar` locally.

## Phase 4 — Follow / like / comment (guide §3.3, §9)
- [ ] `follows`, `likes`, `comments` tables — composite keys exactly as specified
- [ ] Feed becomes "posts from people I follow," Redis-cached 20–60s
- **Done when:** a test that bypasses API-level validation still can't create a duplicate like —
  proving the database constraint is what's actually stopping it, not just the serializer.

## Phase 5 — Reporting (guide §6)
- [ ] `reports` table, unique `(post_id, reporter_id)` constraint
- [ ] `REPORT_THRESHOLD` as a setting; `report_count` updated in the same transaction as the insert
- [ ] Reports from accounts younger than 24h don't count yet; reporting itself is rate-limited
- **Done when:** one test proves 5 reports from 5 distinct, aged accounts flips a post to
  `under_review`, and another proves 5 reports from brand-new accounts doesn't.

## Phase 6 — Pipeline stub + routing (guide §7)
- [ ] Fake pipeline endpoint returning `{verdict, confidence_score, raw_result}` (rule-based or
      random) matching CLAUDE.md's contract exactly
- [ ] DB-polling worker (not Celery yet) picks up `pending` posts, calls the stub, writes the
      result back
- [ ] Routing logic matches §7.2's pseudocode exactly; `CONFIDENCE_THRESHOLD` is a setting
- **Done when:** pytest covers every branch — opinion, high-confidence true, high-confidence
  false, low confidence, and a report pushing an already-verified post back to `under_review`.

## Phase 7 — Human Review Panel (guide §8)
- [ ] Two Django Groups (Moderator, Senior Moderator/Admin) with the §8.2 permission split
- [ ] Custom admin view filtered to `under_review`: content, type, flagged_reason, confidence,
      report reasons
- [ ] Bulk actions — Mark Verified, Mark Unverified/False, Dismiss Reports, Remove Post — each
      writing a `moderation_actions` row
- [ ] Appeals action — resolve the `flagged_reason` question from CLAUDE.md before writing this
- **Done when:** each bulk action has a test asserting both the status change and the audit-log
  row it should have created.

## Phase 8 — Search + notifications (guide §10–11)
- [ ] GIN index + `tsvector` search on `posts.content`
- [ ] `notifications` table, frontend polls every 15–30s
- **Done when:** a manual search for "running" finds a post containing "run" — stemming is
  actually working, not just substring match.

## Phase 9 — Security pass + load test (guide §12–13)
- [ ] Walk every row of the §12 security table against the real codebase, not from memory
- [ ] k6 script against the feed and auth endpoints; fix what it finds before moving on
- **Done when:** a k6 run against seeded data passes with no failed thresholds, and every row in
  §12 has a checkmark against actual code.

## Phase 10 — Launch (guide §14–15)
- [ ] Sentry wired on both frontend and backend
- [ ] GitHub Actions keep-alive ping (backend + DB + Redis) on a schedule
- [ ] Privacy Policy / Terms of Service in place — a lawyer has looked at the verification-label
      language specifically (§16)
- [ ] Final `.env`/secrets audit on both hosts
- **Done when:** a cold visitor can sign up, post a fact, watch it resolve, and report a post —
  entirely on the deployed free infrastructure — with Sentry catching whatever breaks.

## Post-MVP (guide §19 — resist starting these early)
Images/video via Cloudflare R2 · the real fact-checking pipeline (drops into the §7.1 contract
with zero other changes) · an algorithmic feed · Community-Notes-style crowd rating · native
mobile apps.

For any of these, since the spec isn't pre-written the way Phases 0–10 are: have Claude
interview you with the `AskUserQuestion` tool first, write the result to its own `SPEC.md`, then
start a fresh session to implement against that spec.
