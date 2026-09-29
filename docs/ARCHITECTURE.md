# Rumor Zero: Architecture (single source of truth)

A condensed digest of `docs/fact-based-social-platform-architecture-guide.pdf`, with every resolution from `docs/ANALYSIS.md` applied. **Build from this file.** Open the PDF only if something here is missing or unclear, and then fix this file.
Section refs like "guide §7.2" point to the PDF; "c-3" or "D1" point to ANALYSIS.md.

## 0. Names (single source of truth)

| Thing | Value |
|---|---|
| Display name (UI, emails, dashboards) | **Rumor Zero** (never the earlier working name) |
| Slug (repo, npm package, services, URLs) | **`rumor-zero`** |
| Underscore form (only where required) | `rumor_zero`: Django project package, Postgres database/user |
| GitHub repo | `rumor-zero` |
| Backend service (Render) | `rumor-zero-api` → `https://rumor-zero-api.onrender.com` (fallbacks: ENV_GUIDE §2.0) |
| Frontend Worker (Cloudflare) | `rumor-zero` → `https://rumor-zero.<account-subdomain>.workers.dev` |
| npm package name | `rumor-zero-frontend` |
| Deployed URLs: **fill in at Part 17/18** | FRONTEND = `…` · BACKEND = `…` |
| Cookie / header prefixes | cookie `rz_refresh`; headers `X-RZ-Proxy-Secret`, `X-RZ-Client-IP`, `X-RZ-Cron-Secret`; `X-Requested-With: rumor-zero` |

## 1. System shape

- **One backend monolith**: Django 5.2 LTS + DRF + django-allauth (headless), on Render free.
- **One frontend**: Next.js 16 (App Router, TS, Tailwind v4), on Cloudflare Workers via OpenNext.
- **One database**: Postgres 18 (Neon).
- **One cache**: Redis (Upstash).
- **No Celery, no Kubernetes, no microservices, no GraphQL, no search engine, no object storage** (guide §0).

```
Browser → <FRONTEND> (Next.js/Worker) ─ /api/* API relay ─→ <BACKEND>/api/* (Django) → Postgres, Redis
Moderators → <BACKEND>/<ADMIN_URL_PATH> (Django Admin, session login, direct)
UptimeRobot → GET /api/health/ (5 min, no DB) · cron-job.org → POST /api/internal/tick/ (hourly)
GitHub Actions → GET /api/health/deep/ (daily, DB+Redis) · CI on every push/PR
```

**Topology rule (ANALYSIS d):** the browser only ever talks to `<FRONTEND>`.

- `frontend/src/app/api/[...path]/route.ts` (the **API relay**) forwards `/api/*` to `BACKEND_ORIGIN`.
  - It allow-lists request headers, keeps every `Set-Cookie`, uses `redirect:'manual'`, and has a ~70 s timeout that returns `503 {"code":"backend_waking"}`.
  - It adds `X-RZ-Proxy-Secret` and `X-RZ-Client-IP` (from `cf-connecting-ip`).
- Django's `ClientIPMiddleware` sets `REMOTE_ADDR` from `X-RZ-Client-IP` **only** if the secret matches; otherwise it uses the right-most `X-Forwarded-For` entry. allauth (`ALLAUTH_TRUSTED_PROXY_COUNT=0`) and DRF (`NUM_PROXIES=0`) then read `REMOTE_ADDR`.
- No CORS anywhere. `django-cors-headers` is not installed.
- Next's `proxy.ts`/middleware is **not used**.

**Rendering (c-35; the Worker gives 10 ms CPU per request):**
- Prerender static pages: `/`, `/how-it-works`, `/privacy`, `/terms`, auth pages.
- `/p/[id]` and `/u/[username]` do a light SSR: `generateMetadata` + the claim text / profile header, fetched server-to-server from `BACKEND_ORIGIN` without auth.
- Everything personalised is client-rendered via `/api`.
- Polling runs only while `document.visibilityState === 'visible'`.

## 2. Data model (final)

Conventions:
- UUID v4 primary keys, except `likes`/`follows`, which use a bigint `id` plus a unique pair. Django 5.2's `CompositePrimaryKey` isn't supported by the admin, so the guide's composite-PK intent is kept as a DB **unique constraint**.
- `timestamptz` everywhere, stored and returned in UTC.
- Text fields are `''` rather than NULL unless noted.
- Every status and enum is a Django `TextChoices` backed by a DB `CheckConstraint`.

### users: `accounts.User` (`AUTH_USER_MODEL`, must exist before the first migration)

`AbstractBaseUser` + `PermissionsMixin`.

| Field | Type | Notes |
|---|---|---|
| id | uuid PK | |
| username | varchar(30) unique | lowercase `^[a-z0-9_]{3,30}$`, stored lowercase; reserved words blocked (`admin`, `api`, `settings`…) |
| email | varchar(254) unique | stored lowercase; never shown publicly |
| password | Django hasher field | **Argon2id** first in `PASSWORD_HASHERS` (PBKDF2 fallback). Google-only accounts get `set_unusable_password()`, never NULL (c-11). |
| display_name | varchar(50) | blank → UI falls back to `@username` |
| bio | varchar(280) | |
| role | `user` \| `moderator` \| `senior_moderator` | default `user`. **Source of truth**: on save, syncs Django Groups "Moderators" / "Senior moderators" and `is_staff = role != user` (c-10). |
| is_email_verified | bool, default false | mirror of allauth `EmailAddress.verified` for the primary email (signal `email_confirmed`); true for Google sign-ups |
| is_active, is_staff, is_superuser, last_login | Django | |
| avatar_url | varchar null | reserved for Phase 2, **unused** (text-only) |
| created_at | timestamptz, indexed | |

- Google identities live in allauth's `socialaccount_socialaccount (provider, uid)`. There are no `oauth_*` columns (c-12).
- Emails live in allauth's `account_emailaddress`.

### posts: `posts.Post`

| Field | Type | Notes |
|---|---|---|
| id | uuid PK | |
| author | FK users, CASCADE, indexed | |
| content | text, 1–500 chars (CheckConstraint) | plain text only |
| post_type | `opinion` \| `fact` | chosen explicitly by the author, immutable |
| status | `pending` \| `published` \| `verified_true` \| `verified_false` \| `under_review` \| `removed` | c-1. Checks: opinion ⇒ status ∈ {published, under_review, removed}; fact ⇒ status ≠ published |
| flagged_reason | `pipeline` \| `reports` \| `both` \| `appeal`, null | why it is under review |
| pre_review_status | status enum, null | restored when a review is dismissed (c-5) |
| confidence_score | numeric(5,2) null, 0–100 check | from the pipeline |
| pipeline_verdict | `true` \| `false` \| `inconclusive`, null | from the pipeline |
| pipeline_result | jsonb null | raw `raw_result`, schema-less (guide §7.1) |
| pipeline_attempts | smallint, default 0 | |
| pipeline_next_attempt_at | timestamptz null | backoff |
| pipeline_checked_at | timestamptz null | |
| verdict_source | `pipeline` \| `moderator`, null | c-6. Moderator verdicts show no % |
| verdict_note | varchar(500) | public note set by a moderator |
| report_count | int, default 0 | **lifetime** counter, updated in the report-insert transaction (guide §3.2 note) |
| escalated_at | timestamptz null | c-9 |
| moderated_by | FK users SET_NULL null | last moderator to act |
| moderated_at | timestamptz null | |
| deleted_at | timestamptz null | author soft delete (D6): hidden everywhere, kept for audit |
| search_vector | `GeneratedField(SearchVector('content', config='english'), db_persist=True)` | GIN index (c-31) |
| created_at, updated_at | timestamptz | |

Indexes:
- `(status, created_at DESC)`
- `(author_id, created_at DESC)`
- GIN `(search_vector)`
- partial `(created_at) WHERE post_type='fact' AND status='pending' AND deleted_at IS NULL` (queue)
- partial `(created_at) WHERE status='under_review'` (review queue)

### Social graph

| Table | Fields | Constraints / indexes |
|---|---|---|
| follows | id bigint, follower FK, following FK, created_at | unique(follower, following); check follower ≠ following; index(following) (guide §3.5) |
| likes | id bigint, user FK, post FK, created_at | unique(user, post) (prevents double-likes at the DB level); index(post) |
| comments | id uuid, post FK, author FK, content 1–500, is_hidden bool (moderator), created_at | index(post, created_at); flat, no replies |

All FKs to users and posts CASCADE.

### reports

| Field | Type | Notes |
|---|---|---|
| id | uuid PK | |
| post, reporter | FKs CASCADE | **unique(post, reporter)**, one per user per post (guide §6.1) |
| reason | `inaccurate` \| `misleading` \| `harassment` \| `spam` \| `other` | labels in ANALYSIS b-5 |
| details | varchar(500) | required when reason = `other` |
| status | `open` \| `dismissed` \| `actioned`, default open | dismissed/actioned reports stop counting |
| counts_toward_threshold | bool | computed at insert (§4) |
| resolved_by | FK users null | |
| resolved_at | timestamptz null | |
| created_at | timestamptz | index(post, created_at) |

### moderation_actions (audit trail, append-only)

| Field | Type | Notes |
|---|---|---|
| id | uuid PK | |
| post | FK SET_NULL null | |
| post_snapshot | text | copy of content at action time (so the log survives deletion) |
| moderator | FK users SET_NULL null | |
| action | `verified` \| `marked_false` \| `dismissed_report` \| `removed` \| `escalated` | guide §3.4 |
| from_status, to_status | status enum | "what it was before" |
| appeal | FK appeals null | set when the action resolves an appeal |
| notes | text | internal rationale |
| created_at | timestamptz | |

Admin: read-only for everyone, visible only to seniors in full (guide §8.2).

### appeals (c-7)

| Field | Type | Notes |
|---|---|---|
| id | uuid PK | |
| post | FK CASCADE, **unique** | at most 1 appeal per post in the MVP |
| author | FK CASCADE | must be the post's author |
| reason | varchar(500) | |
| status | `open` \| `upheld` \| `overturned` | upheld = original label kept |
| original_moderator | FK users null | |
| resolved_by | FK users null | |
| resolved_at | timestamptz null | |
| created_at | timestamptz | |

### notifications (guide §11)

| Field | Type | Notes |
|---|---|---|
| id | uuid PK | |
| recipient | FK CASCADE | |
| actor | FK SET_NULL null | |
| type | `follow` \| `like` \| `comment` \| `verdict` \| `under_review` \| `removed` \| `appeal_resolved` | |
| post | FK CASCADE null | |
| comment | FK CASCADE null | |
| is_read | bool, default false | |
| created_at | timestamptz | |

- Indexes: `(recipient, created_at DESC)` and partial `(recipient) WHERE is_read=false`.
- `follow` and `like` are de-duplicated per (recipient, actor, type, post).
- No self-notifications.

### platform_settings (singleton, id=1) (c-13)

- Fields: `report_threshold`, `report_window_hours`, `report_min_account_age_hours`, `confidence_threshold`, `fact_posts_per_day`, `updated_by`, `updated_at`.
- Seeded from env defaults by a data migration.
- Editable **only by senior moderators** in Django Admin.
- Read through a 60 s cache; every change is logged.

## 3. Configuration values

| Name | Default | Env var | Editable in admin |
|---|---|---|---|
| Report threshold | 5 | `REPORT_THRESHOLD` | ✅ seniors |
| Report window (hours) | 24 | `REPORT_WINDOW_HOURS` | ✅ |
| Min account age for a report to count (hours) | 24 | `REPORT_MIN_ACCOUNT_AGE_HOURS` | ✅ |
| Confidence threshold (0–100) | 85 | `CONFIDENCE_THRESHOLD` | ✅ |
| Fact posts per user per day | 10 | `FACT_POSTS_PER_DAY` | ✅ |
| Feed cache TTL (s) | 30 | `FEED_CACHE_SECONDS` | — |
| Access / refresh token lifetime | 15 min / 14 days | `JWT_ACCESS_TOKEN_MINUTES` / `JWT_REFRESH_TOKEN_DAYS` | — |
| Email-confirmation link validity | 1 day | code (`ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS`) | — |
| Pipeline: batch size / max attempts / timeout | 10 / 5 / 20 s | code constants | — |
| Pipeline retry backoff | 2^attempts min, cap 60 min | code | — |
| Post / comment / appeal text max | 500 chars | code | — |
| Bio / display name max | 280 / 50 | code | — |
| Page size | 20 (max 50) | code | — |
| Notification poll | 30 s, visible tab only | frontend constant | — |
| Pending-status poll | 10 s → back off to 60 s, stop after 10 min | frontend constant | — |

DRF throttles (per user, Redis-backed; scope → rate):
- `post_create` 30/h
- `comment` 60/h
- `like` 300/h
- `follow` 100/h
- `report` **10/h** (guide §6.3)
- `appeal` 5/day
- `username_check` 30/min per IP

Auth endpoints use allauth's `ACCOUNT_RATE_LIMITS` (login failures, signup, reset, confirm-email resend).

## 4. Post status lifecycle and routing (guide §5, §6, §7; fixes c-1…c-7)

### Events → transitions

| Current status | Event | New status | Other effects |
|---|---|---|---|
| (new) | author creates **opinion** | `published` | never enters the pipeline |
| (new) | author creates **fact** | `pending` | visible now with "Checking facts…" (guide §5.2); inline kick queued on commit |
| `pending` | pipeline result, verdict `true`/`false` **and** confidence ≥ threshold | `verified_true` / `verified_false` | `verdict_source=pipeline`; notify author (`verdict`) |
| `pending` | pipeline result, `inconclusive` **or** confidence < threshold | `under_review` | `flagged_reason=pipeline`, `pre_review_status=pending`; notify (`under_review`) |
| `pending` | pipeline failed `max_attempts` times | `under_review` | `flagged_reason=pipeline`; error kept in `pipeline_result` |
| `pending` / `published` / `verified_*` | report threshold crossed | `under_review` | `flagged_reason=reports`, `pre_review_status=<old>`; notify author |
| `under_review` | report threshold crossed | unchanged | `pipeline`→`both`; `reports`/`both`/`appeal` unchanged |
| `under_review` (reports, pipeline result arrives late) | decisive result | unchanged | store result; `pre_review_status=verified_*`, `verdict_source=pipeline` |
| `under_review` (reports, pipeline result arrives late) | low / inconclusive result | unchanged | `flagged_reason=both` |
| `under_review` | moderator **Mark verified** (fact only) | `verified_true` | `verdict_source=moderator`, `flagged_reason=null`, open reports→`actioned`; log action; notify |
| `under_review` | moderator **Mark false** (fact only) | `verified_false` | same as above |
| `under_review` | moderator **Dismiss reports** | `pre_review_status` if flag was `reports`; stays `under_review` with `flagged_reason=pipeline` if flag was `both` | open reports→`dismissed`; log |
| any except `removed` | moderator **Remove** | `removed` | reports→`actioned`; log; notify (`removed`) |
| any | moderator **Escalate** | unchanged | `escalated_at=now`; log |
| `verified_false` (author, no prior appeal) | author **appeals** | `under_review` | `flagged_reason=appeal`, `pre_review_status=verified_false`; appeal `open` |
| `under_review` (appeal) | Mark verified | `verified_true` | appeal `overturned`; notify `appeal_resolved` |
| `under_review` (appeal) | Mark false | `verified_false` | appeal `upheld`; notify `appeal_resolved` |
| `removed` | any pipeline or report event | unchanged | ignored |
| any | author deletes | unchanged | `deleted_at=now`; hidden from every list and detail view |

Also:
- A pipeline result is **ignored** when `verdict_source=moderator` (humans win).
- An appeal must be resolved by a moderator other than `original_moderator` unless the resolver is a senior (`APPEAL_REQUIRE_DIFFERENT_MODERATOR`).
- Opinions: moderators can only Dismiss or Remove.

### Routing: pure functions in `apps/pipeline/routing.py` (no I/O, exhaustively unit-tested)

```python
def merge_flag(existing, new):                      # None+x=x; x+x=x; pipeline+reports=both;
    ...                                             # appeal stays appeal; both stays both

def enter_review(post, reason):
    if post.status == UNDER_REVIEW:
        post.flagged_reason = merge_flag(post.flagged_reason, reason)
    else:
        post.pre_review_status, post.status, post.flagged_reason = post.status, UNDER_REVIEW, reason

def apply_pipeline_result(post, result, cfg):       # called by the processor inside a transaction
    if post.post_type != FACT or post.status == REMOVED or post.verdict_source == MODERATOR:
        return                                      # humans and removals win
    post.pipeline_verdict, post.confidence_score, post.pipeline_result = result.verdict, result.confidence_score, result.raw_result
    decisive = result.verdict in (TRUE, FALSE) and result.confidence_score >= cfg.confidence_threshold
    label = VERIFIED_TRUE if result.verdict == TRUE else VERIFIED_FALSE
    if post.status == PENDING:
        if decisive: post.status, post.verdict_source = label, PIPELINE
        else:        enter_review(post, PIPELINE)
    elif post.status == UNDER_REVIEW:
        if decisive: post.pre_review_status, post.verdict_source = label, PIPELINE
        else:        post.flagged_reason = merge_flag(post.flagged_reason, PIPELINE)

def apply_report_threshold(post, counting_reports, cfg):
    if post.status != REMOVED and counting_reports >= cfg.report_threshold:
        enter_review(post, REPORTS)
```

All status writes go through `apps/posts/services.py` (plus `apps/moderation/services.py` for moderator actions), which wrap the pure functions in `transaction.atomic()` with `select_for_update()` on the post row. **No other code assigns `post.status`.**

### Badges (frontend, ANALYSIS b-2)

| status / condition | Badge | Glyph | Colour | % shown |
|---|---|---|---|---|
| pending | CHECKING FACTS… | `progress_activity` (spins; static with reduced motion) | neutral, dashed border | no |
| published (opinion) | OPINION category chip only | — | neutral | no |
| verified_true, pipeline | VERIFIED 94% | `check_circle` | primary | yes |
| verified_true, moderator | VERIFIED · REVIEWED | `check_circle` | primary | no |
| verified_false, pipeline | FALSE 88% | `cancel` | error | yes |
| verified_false, moderator | FALSE · REVIEWED | `cancel` | error | no |
| under_review | UNDER REVIEW (+ APPEAL PENDING chip, author only) | `hourglass_top` | verdict-review | no |
| removed | tombstone card "Removed by a moderator" | `block` | neutral | no |

The 4 px stripe on the card uses the same colour; opinion and pending use `outline-variant`.

## 5. Reporting (guide §6; c-2)

`POST /api/v1/posts/{id}/report/`:
1. **Pre-checks:** logged in, **email verified**, not the author, post visible (not removed or deleted), throttle `report` 10/h.
2. Inside `transaction.atomic()`:
   - `select_for_update()` the post
   - insert the report (the unique constraint turns a duplicate into **409**)
   - `report_count += 1`
   - `counts_toward_threshold` = reporter account age ≥ `report_min_account_age_hours` **or** reporter has ≥1 post or comment (guide §6.3)
   - `n` = count of this post's reports with `status='open' AND counts_toward_threshold AND created_at >= now - window`
   - `apply_report_threshold(post, n, cfg)`
   - save
3. The post stays visible while under review (guide §6.4). Redis is never used for the count.

## 6. Pipeline contract and processing (guide §5.4, §7.1; c-21)

```python
# apps/pipeline/contract.py — frozen dataclasses, validated on construction
PipelineRequest(post_id: UUID, content: str)
PipelineResult(verdict: Literal["true","false","inconclusive"],
               confidence_score: Decimal,   # 0–100, quantized to 0.01
               raw_result: dict)            # stored verbatim in posts.pipeline_result

class PipelineClient(Protocol):
    def check(self, request: PipelineRequest) -> PipelineResult: ...
```

- **`StubPipelineClient`** (`PIPELINE_BACKEND=stub`) is deterministic, so tests and demos are predictable:
  - content containing `#true` → (true, 95)
  - `#false` → (false, 92)
  - `#unsure` → (inconclusive, 40)
  - otherwise a hash of the content gives the confidence (50–99) and verdict
  - `raw_result={"stub": true, "rule": …}`
- **`HttpPipelineClient`** (`PIPELINE_BACKEND=http`, future): `POST PIPELINE_URL` with `{post_id, content}`, `Authorization: Bearer PIPELINE_API_KEY`, 20 s timeout. It expects `{verdict, confidence_score, raw_result}`. Swapping it in changes nothing else.
- **Processor** `process_pending(limit=10, now)`:
  - selects fact posts with `status='pending'`, `deleted_at IS NULL`, `pipeline_next_attempt_at` null or ≤ now, oldest first, `FOR UPDATE SKIP LOCKED`;
  - calls the client and routes the result;
  - on error: `attempts += 1`, then backoff; at `max_attempts` → `enter_review(post, PIPELINE)`.
- **Triggers:**
  - (1) **Inline kick:** `transaction.on_commit` → a daemon thread processes that post (`PIPELINE_INLINE_KICK`, off in tests).
  - (2) `POST /api/internal/tick/` (header `X-RZ-Cron-Secret`), hourly from cron-job.org. It returns `{"processed": n}` in < 30 s.
  - (3) `python manage.py process_pending [--loop]` for local dev.
  - No Celery, no worker service.

## 7. Authentication (guide §4; D1, c-17, c-18, d)

**Library:** django-allauth **headless**, client `app`, `HEADLESS_TOKEN_STRATEGY = allauth.headless.tokens.strategies.jwt.JWTTokenStrategy`. The settings map from our env vars:

| allauth setting | Value |
|---|---|
| `HEADLESS_JWT_ALGORITHM` | `HS256` |
| `HEADLESS_JWT_PRIVATE_KEY` | `JWT_SIGNING_KEY` |
| `HEADLESS_JWT_ACCESS_TOKEN_EXPIRES_IN` | `JWT_ACCESS_TOKEN_MINUTES × 60` |
| `HEADLESS_JWT_REFRESH_TOKEN_EXPIRES_IN` | `JWT_REFRESH_TOKEN_DAYS × 86400` |
| `HEADLESS_JWT_ROTATE_REFRESH_TOKEN` | True |
| DRF authentication class | `allauth.headless.contrib.rest_framework.authentication.JWTTokenAuthentication` |

Other settings:
- `HEADLESS_ONLY=True`; `HEADLESS_CLIENTS=("app",)`
- `HEADLESS_FRONTEND_URLS`: `account_confirm_email` = `FRONTEND_ORIGIN/verify-email/{key}`; `account_reset_password_from_key` = `FRONTEND_ORIGIN/reset-password/{key}`
- `ACCOUNT_LOGIN_METHODS={"email"}`, `ACCOUNT_SIGNUP_FIELDS=["email*","username*","password1*"]`
- `ACCOUNT_EMAIL_VERIFICATION="optional"`: unverified users can log in and browse; writes are blocked by the `IsEmailVerified` permission (guide §4.3 step 4)
- `ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS=1`
- `ACCOUNT_LOGIN_ON_PASSWORD_RESET=True`
- `SOCIALACCOUNT_EMAIL_AUTHENTICATION(_AUTO_CONNECT)=True`: Google emails are pre-verified, so they link to an existing email account
- An adapter auto-generates a username for Google sign-ups (c-29)

**Mount point:** `path("api/auth/", include("allauth.headless.urls"))`, so endpoints look like `/api/auth/app/v1/auth/login`. The exact paths are confirmed while planning Part 1; update this section if they differ.

**Refresh-cookie adapter** (`apps/accounts/cookies.py`: a middleware on `/api/auth/` paths, ~100 lines, fully tested):
- **Response contains `meta.refresh_token`** (login, signup, provider-token, reset-with-login, refresh):
  - remove it from the JSON;
  - set cookie `rz_refresh` with `HttpOnly; Secure(=AUTH_COOKIE_SECURE); SameSite=Lax; Path=/api/auth/; Max-Age=JWT_REFRESH_TOKEN_DAYS`;
  - no `Domain` attribute, so it's a host-only cookie of `<FRONTEND>`, because it arrives through the relay.
- **`POST …/tokens/refresh`:**
  - require `Origin == FRONTEND_ORIGIN` and `X-Requested-With: rumor-zero` (CSRF, c-18);
  - inject the cookie value as `refresh_token`;
  - put the rotated token back into the cookie.
- **`POST /api/auth/logout/`** (ours): same CSRF checks; ends the allauth session so the refresh token is revoked; deletes the cookie (`Max-Age=0`).

**Flows** (frontend `lib/api` and `lib/auth`):

| Flow | Steps |
|---|---|
| Sign up (a2) | email + username (live check `GET /api/v1/auth/username-available/?u=`) + password + Turnstile token → allauth signup. The server verifies Turnstile via `https://challenges.cloudflare.com/turnstile/v0/siteverify` in the custom signup form (if headless ignores extra fields, a pre-check on that endpoint). → access token in memory + refresh cookie → verification email sent → UI shows the a4 "check your inbox" state and the unverified banner. |
| Verify email (a4) | link `<FRONTEND>/verify-email/{key}` → POST key to allauth → `users.is_email_verified=true` |
| Log in (a3) | email + password → tokens. A generic error on failure; allauth rate-limits failures. |
| Google (a2/a3) | Google Identity Services button → ID token → `POST …/auth/provider/token {provider:"google", process:"login", token:{client_id, id_token}}` → allauth verifies the token's `aud` = `GOOGLE_OAUTH_CLIENT_ID` → tokens. Only JS origins are registered; no redirect URI, no client secret. |
| Forgot / reset (a5/a6) | request → always shows "if an account exists…" (no enumeration) → link `<FRONTEND>/reset-password/{key}` → new password → logged in; other sessions invalidated |
| Stay logged in | Access token lives **only in memory** (React context), never in localStorage (guide §4.6). On load, and 60 s before expiry, call refresh. On a 401, refresh once and retry, else log out. Refreshes are serialised across tabs with the **Web Locks API** (`navigator.locks.request('rz-refresh')`), so token rotation can't race. |
| Log out | `POST /api/auth/logout/` → clear memory + cookie |

**Permissions:**
- `IsAuthenticated` for all writes.
- `IsEmailVerified` (code `email_unverified`, 403) for creating posts, comments, likes, follows, reports and appeals (unverified = read-only).
- `IsModerator` / `IsSeniorModerator` for admin.
- The superuser is created from your PC (ENV_GUIDE §2.6).

**Turnstile:** on signup only (guide §4.1). Local dev uses the always-pass test keys.

## 8. Moderation panel: Django Admin (guide §8; d2 is a reference only)

- **Roles:**
  - *Moderator*: review queue, the actions below, can't change roles or delete users.
  - *Senior moderator*: + manage moderator accounts (edit `role`), edit `PlatformSettings`, full audit log.
  - Implemented with Groups and model permissions synced from `role`.
- **Review queue:** `PostAdmin`, default filter `status=under_review`.
  - Columns: content (truncated), type, flagged_reason, confidence, report_count, age in queue, escalated.
  - Filters: flagged_reason (pipeline / reports / both / appeal), type, escalated.
  - Sort: report_count, created_at.
  - Search: content, author username.
  - Inlines: reports (reason, details, reporter age), appeal, moderation history.
- **Bulk actions**, each calling `moderation.services` and writing `moderation_actions`:
  - *Mark verified*, *Mark false* (fact posts only; optional public `verdict_note`)
  - *Dismiss reports*
  - *Remove post*
  - *Escalate to senior*
- Comments: *Hide comment*.
- The admin header reads "Rumor Zero moderation". It is served at `<BACKEND>/<ADMIN_URL_PATH>`. `/api/v1/me/` returns `admin_url` only to staff, so the sidebar "Moderation" link never exposes the path to others.

## 9. API conventions

- **Base paths:**
  - `/api/v1/…` app API
  - `/api/auth/…` allauth headless + cookie adapter
  - `/api/health/` (no DB, 0 queries, enforced by a test), `/api/health/deep/` (DB + Redis, secret header)
  - `/api/internal/tick/` (secret header)
- **Format:** JSON, snake_case. IDs are UUID strings. Timestamps are ISO-8601 UTC (`2026-09-29T12:00:00Z`). Plain-text content is never HTML.
- **Auth:** `Authorization: Bearer <access>`. Public GETs work anonymously.
- **Pagination:** cursor-based (guide §9.1), `?cursor=<opaque>` → `{"results": [...], "next_cursor": "…" | null}`. Page size 20. No absolute `next` URLs (they'd point past the relay).
- **Errors:**
  - DRF shape `{"detail": "...", "code": "..."}` (custom handler adds `code`), or `{"field": ["msg"]}` for validation.
  - allauth endpoints keep allauth's `{"status":…, "errors":[{code,param,message}]}`; the frontend client normalises both.
  - Codes: 400 validation · 401 unauthenticated · 403 forbidden (`email_unverified`, `not_author`…) · 404 · 409 conflict (`already_reported`, `already_appealed`) · 429 throttled (+`Retry-After`) · 503 `backend_waking` (relay).
- **Toggles are idempotent:** `POST` like/follow → 201 (200 if already there); `DELETE` → 204.
- **Performance:** every list uses `select_related("author")` plus annotated `like_count`, `comment_count`, `liked_by_me`, `reported_by_me`. No N+1 (guide §9.3). Tests assert query counts.
- **Home feed:** fan-out-on-read (`author IN followed ∪ {me}`, newest first), first page cached per user for `FEED_CACHE_SECONDS` (guide §9.2). Status polling is never cached.

**Post object** (all list and detail endpoints):

```json
{ "id": "uuid", "author": {"id": "uuid", "username": "ada", "display_name": "Ada"},
  "content": "…", "post_type": "fact", "status": "verified_true",
  "confidence_score": "94.00", "verdict_source": "pipeline", "verdict_note": "",
  "like_count": 3, "comment_count": 1, "liked_by_me": false, "reported_by_me": false,
  "is_mine": false, "can_appeal": false, "appeal_status": null, "created_at": "…" }
```

- `confidence_score` is non-null only for `verified_*` with `verdict_source=pipeline`.
- `flagged_reason` and report details are never public.
- `appeal_status` is only returned to the author.

**Endpoint index** (the part that adds each):

| Part | Method & path | Purpose |
|---|---|---|
| 0A | GET `/api/health/` · GET `/api/health/deep/` | health |
| 1 | allauth `/api/auth/app/v1/auth/signup`, `…/auth/login`, `…/tokens/refresh`, POST `/api/auth/logout/` · GET `/api/v1/auth/username-available/` · GET `/api/v1/me/` | auth core |
| 2 | allauth `…/auth/email/verify`, `…/auth/email/verify/resend`, `…/auth/password/request`, `…/auth/password/reset` | email flows |
| 3 | allauth `…/auth/provider/token` | Google |
| 4 | POST/GET `/api/v1/posts/` (global recent) · GET `/api/v1/me/fact-quota/` | posts |
| 5 | GET/DELETE `/api/v1/posts/{id}/` · GET `/api/v1/posts/status/?ids=a,b` | detail, polling |
| 6 | GET `/api/v1/users/{username}/` · `…/posts/` · `…/followers/` · `…/following/` · POST/DELETE `…/follow/` · GET `/api/v1/feed/` | social graph |
| 7 | POST/DELETE `/api/v1/posts/{id}/like/` · GET/POST `/api/v1/posts/{id}/comments/` · DELETE `/api/v1/comments/{id}/` | likes, comments |
| 8 | POST `/api/v1/posts/{id}/report/` | reports |
| 9 | POST `/api/internal/tick/` | pipeline sweeper |
| 11 | POST `/api/v1/posts/{id}/appeal/` | appeals |
| 12 | GET `/api/v1/search/?q=&type=posts\|users&post_type=&status=` | search |
| 13 | GET `/api/v1/notifications/` · GET `…/unread-count/` · POST `…/mark-read/` | notifications |
| 14 | PATCH `/api/v1/me/` · POST `/api/v1/me/password/` · GET `/api/v1/me/export/` · DELETE `/api/v1/me/` | settings |

**Search (guide §10):** `SearchQuery(q, search_type="websearch", config="english")` against `search_vector`, ranked with `SearchRank`, newest first on ties. Users are matched by `username`/`display_name` prefix. Removed and deleted posts are excluded.

## 10. Frontend conventions

- Server Components by default. `"use client"` only where there's state or events.
- All API calls go through `src/lib/api/client.ts` (relative `/api` base). **Never** call `BACKEND_ORIGIN` from the browser.
- Styling:
  - Tokens live only in `globals.css` `@theme`.
  - Use Stitch class names (`bg-surface-container-low`, `font-claim-headline text-claim-headline`, `max-w-reading`, `px-space-md`).
  - **No** Tailwind default palette, no arbitrary hex, only `rounded-lg`/`rounded-full`, `shadow-sm` only.
  - Fact text: `font-claim-headline text-claim-headline`. Opinion text: `font-claim-opinion text-claim-opinion italic`.
- User text is rendered as plain text (`whitespace-pre-wrap break-words`). Never `dangerouslySetInnerHTML`.
- Avatars are initials only. Icons use `<Icon name="…"/>` (Material Symbols, self-hosted).
- Accessibility:
  - Every status is shown by glyph **and** label **and** colour (DESIGN.md).
  - Modals use `<dialog>`, focus-visible rings in `secondary`, labels bound to inputs.
- Tokens never go in `localStorage`/`sessionStorage`.

## 11. Testing (guide §17). Every part ships tests.

- **Backend (pytest-django, real Postgres 18):**
  - models and constraints
  - services and the **routing table in §4** (one test per row)
  - API permissions and throttles
  - query counts
  - `/api/health/` = 0 queries
- **Frontend:** Vitest + React Testing Library for components and hooks.
- **E2E:** Playwright for one user flow per part where it applies (e.g. sign up → post a fact → see CHECKING FACTS… → verdict badge).
- **CI (`.github/workflows/ci.yml`):** ruff + pytest (Postgres service), eslint + tsc + vitest + `next build` + `opennextjs-cloudflare build` (Linux), Playwright. Render deploys **only after CI passes**.

## 12. Security checklist (guide §12)

| Risk | Mitigation |
|---|---|
| SQL injection | ORM only; no string-built SQL |
| XSS | plain-text rendering; no HTML from users; no tokens in storage |
| CSRF | Bearer header for the API; refresh/logout checked by Origin + custom header + SameSite=Lax; admin uses Django CSRF |
| Brute force | allauth rate limits + DRF throttles on the real client IP (relay header + secret) |
| Bots / brigading | Turnstile on signup, email verification before writes, new-account report weighting, report throttle |
| Stolen DB | Argon2id; allauth stores only signed/hashed keys |
| Secrets | env vars only; `.env*` git-ignored; Claude denied reading real env files; Dependabot |
| Transport | HTTPS everywhere (Render/Cloudflare TLS); `SECURE_PROXY_SSL_HEADER`, HSTS, secure cookies in prod |
| Admin exposure | unguessable `ADMIN_URL_PATH`, staff-only, path never public |

## 13. Free-tier budgets to respect (verified 2026-09-29)

| Service | Budget | Design consequence |
|---|---|---|
| Cloudflare Workers | 100k requests/day, 10 ms CPU | prerender; poll only when visible; escape hatch in ANALYSIS d |
| Render | 750 h/month, sleeps after 15 min, 512 MB, no SMTP/workers/cron | 5-min UptimeRobot ping on the no-DB health endpoint; inline kick + hourly tick; Brevo API for email |
| Neon | 100 CU-h/month, 0.5 GB, sleeps after 5 min | never ping the DB frequently; direct connection with `CONN_HEALTH_CHECKS=True` |
| Upstash | 500K commands/month, archived after ~30 days idle | Redis only for the feed cache and throttles; daily deep ping |
| Brevo | 300 emails/day | only verification + reset emails |
| Sentry | 5K errors/month | traces sample rate 0.0 |
| GitHub Actions | 2,000 min/month if private | CI + one daily job; no 10-min cron |
