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
| Logo | master `design/logo.svg` (read-only; accessible name "Rumor Zero"). Derived assets come only from `npm run brand:build` (Part 0D). The UI shows the brand only through `<Logo/>`. See §14. |
| Credibility score | called "Credibility score" in the UI and `reputation` in code (§4a) |

## 1. System shape

- **One backend monolith**: Django 5.2 LTS + DRF + django-allauth (headless), on Render free.
- **One frontend**: Next.js 16 (App Router, TS, Tailwind v4), on Cloudflare Workers via OpenNext.
- **One database**: Postgres 18 (Neon).
- **One cache**: Redis (Upstash).
- **No Celery, no Kubernetes, no microservices, no GraphQL, no search engine, no object storage** (guide §0). Profile photos are small re-encoded WebP files kept in Postgres (§4e).
- **Posts and comments are text-only.** The only images are profile photos and the logo.

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
- Link-preview images and icons are static files (§14). Nothing generates images at request time.

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
| avatar_version | varchar(16) null | null = no photo (initials). Set by the avatar service (14B); the photo URL is built from it (§9). Replaces the old unused `avatar_url`. |
| avatar_uploads_blocked | bool, default false | set by a moderator (14B) |
| reputation_score | smallint, default 50, check 0–100 | denormalised credibility score. Written **only** by `apps/reputation/services.py` (§4a) |
| reputation_sample | int, default 0 | un-reversed own-post events counted in the score; the score is public only when ≥ 3 |
| emergency_blocked_until | timestamptz null | no emergency posts before this time: set automatically after a FALSE emergency, or by a moderator (§4b) |
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
| source | varchar(500), default '' | optional, fact posts only: a validated http(s) URL or a bare DOI (§4c). **Never fetched.** Immutable. |
| source_kind | `''` \| `url` \| `doi` | checks: set iff `source` is set; `source` only when `post_type='fact'` |
| is_emergency | bool, default false | chosen at creation, immutable; check: only when `post_type='fact'` (§4b) |
| emergency_expires_at | timestamptz null | `created_at + emergency_duration_hours`, stored at creation; check: set iff `is_emergency` |
| emergency_demoted_at | timestamptz null | priority ended early (moderator demotion or FALSE verdict) |
| status | `pending` \| `published` \| `verified_true` \| `verified_false` \| `under_review` \| `removed` | c-1. Checks: opinion ⇒ status ∈ {published, under_review, removed}; fact ⇒ status ≠ published |
| flagged_reason | `pipeline` \| `reports` \| `both` \| `appeal`, null | why it is under review |
| pre_review_status | status enum, null | restored when a review is dismissed (c-5) |
| pre_removal_status | status enum, null | set by Remove; restored when a removal appeal is overturned (§4) |
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
- partial `(is_emergency DESC, created_at) WHERE post_type='fact' AND status='pending' AND deleted_at IS NULL` (queue; emergencies first)
- partial `(created_at) WHERE status='under_review'` (review queue)
- partial `(emergency_expires_at) WHERE is_emergency AND emergency_demoted_at IS NULL AND deleted_at IS NULL` (pinned emergencies)

The source, emergency and `pre_removal_status` columns are created in Part 4 with the rest of the table. Their logic arrives in Parts 4/5 (source), 11 (removal appeals) and 11C (emergency), so no later schema change is needed.

### Social graph

| Table | Fields | Constraints / indexes |
|---|---|---|
| follows | id bigint, follower FK, following FK, created_at | unique(follower, following); check follower ≠ following; index(following) (guide §3.5) |
| likes | id bigint, user FK, post FK, created_at | unique(user, post) (prevents double-likes at the DB level); index(post, created_at) (also feeds the stats in 11D) |
| comments | id uuid, post FK, author FK, content 1–500, is_hidden bool (moderator), created_at | index(post, created_at); flat, no replies |
| bookmarks | id bigint, user FK, post FK, created_at | unique(user, post); index(user, created_at DESC). **Private**: never exposed to anyone but the owner (7B, §4d) |
| reposts | id bigint, user FK, post FK, status_at_repost (status enum), created_at | unique(user, post); index(post, created_at); index(user, created_at DESC). Rules in §4d (7B) |

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
| post | FK SET_NULL null | null for account-level actions |
| subject_user | FK users SET_NULL null | the account acted on (emergency block, photo removal/block) |
| post_snapshot | text | copy of content at action time (so the log survives deletion) |
| moderator | FK users SET_NULL null | |
| action | `verified` \| `marked_false` \| `dismissed_report` \| `removed` \| `escalated` \| `restored` \| `emergency_demoted` \| `emergency_blocked` \| `avatar_removed` \| `avatar_blocked` | guide §3.4 plus the D5 features. The whole list is created in Part 10, so later parts never alter the constraint. |
| from_status, to_status | status enum, null | "what it was before" (null for account-level actions) |
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
| kind | `label` \| `removal` | `label` for a FALSE label, `removal` for a removed post (ANALYSIS f-2) |
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
| type | `follow` \| `like` \| `comment` \| `repost` \| `verdict` \| `under_review` \| `removed` \| `emergency_demoted` \| `appeal_resolved` | |
| post | FK CASCADE null | |
| comment | FK CASCADE null | |
| is_read | bool, default false | |
| created_at | timestamptz | |

- Indexes: `(recipient, created_at DESC)` and partial `(recipient) WHERE is_read=false`.
- `follow`, `like` and `repost` are de-duplicated per (recipient, actor, type, post).
- No self-notifications.

### reputation_events: `reputation.ReputationEvent` (append-only ledger, Part 11B)

| Field | Type | Notes |
|---|---|---|
| id | uuid PK | |
| user | FK users CASCADE | whose score changes |
| kind | `fact_true` \| `fact_false` \| `emergency_false` \| `post_removed` \| `repost_true` \| `repost_false` \| `repost_emergency_false` \| `repost_removed` \| `report_upheld` \| `reversal` | weights in §4a |
| positive, negative | numeric(6,2) | the event's P and N weights (both ≥ 0); a `reversal` row carries the negated values of the row it cancels |
| post | FK posts SET_NULL null | the post the event is about |
| moderation_action | FK moderation_actions SET_NULL null | the moderator action that caused it, if any |
| reverses | FK self null, **unique** | set only on `reversal` rows (check: `kind='reversal'` iff set); a row can be reversed once |
| score_after | smallint | the user's score right after this row (drives the trend chart) |
| created_at | timestamptz | index(user, created_at) |

Rows are never updated or deleted, except by account deletion (CASCADE). Admin is read-only.

### avatars: `accounts.Avatar` (Part 14B)

| Field | Type | Notes |
|---|---|---|
| user | OneToOne users, **PK**, CASCADE | one photo per account |
| image_256, image_96 | bytea | re-encoded WebP only (§4e); never the original upload |
| version | varchar(16) | first 16 hex characters of the SHA-256 of `image_256`; copied into `users.avatar_version` |
| bytes_total | int | for the storage budget (§13) |
| created_at, updated_at | timestamptz | |

A separate table keeps image bytes out of every `users` query.

### platform_settings (singleton, id=1) (c-13)

- Fields: `report_threshold`, `report_window_hours`, `report_min_account_age_hours`, `confidence_threshold`, `fact_posts_per_day`, the six emergency limits (`emergency_duration_hours`, `emergency_posts_per_day`, `emergency_min_account_age_days`, `emergency_min_reputation`, `emergency_report_threshold`, `emergency_false_cooldown_days`; §3), `updated_by`, `updated_at`. All are created in Part 0A.
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
| Emergency duration (hours) | 24 | `EMERGENCY_DURATION_HOURS` | ✅ (applies to new emergencies; the expiry is stored at creation) |
| Emergency posts per user per 24 h (they also count as fact posts) | 1 | `EMERGENCY_POSTS_PER_DAY` | ✅ |
| Min account age for emergency posts (days) | 7 | `EMERGENCY_MIN_ACCOUNT_AGE_DAYS` | ✅ |
| Min credibility score for emergency posts | 40 | `EMERGENCY_MIN_REPUTATION` | ✅ |
| Report threshold while an emergency is active | 2 | `EMERGENCY_REPORT_THRESHOLD` | ✅ |
| Emergency ban after a FALSE emergency (days) | 30 | `EMERGENCY_FALSE_COOLDOWN_DAYS` | ✅ |
| Pinned emergencies shown per feed | 3 (+ "Show all") | code | — |
| Credibility: start / prior weight / public after | 50 / 10 imaginary events / 3 counted events | code (`apps/reputation/scoring.py`) | — |
| Credibility: reporter credit cap | 4 upheld reports per 30 days | code | — |
| Source field max length | 500 chars | code | — |
| Profile photo limits | ≤ 5 MB, ≤ 25 MP, ≥ 128×128 px; stored as WebP 256 + 96 px | code (§4e) | — |
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
- `repost` 100/h
- `bookmark` 300/h
- `avatar_upload` 5/day
- `username_check` 30/min per IP

The emergency limit (1 per 24 h) is a service rule checked against the DB, not a throttle.

Auth endpoints use allauth's `ACCOUNT_RATE_LIMITS` (login failures, signup, reset, confirm-email resend).

## 4. Post status lifecycle and routing (guide §5, §6, §7; fixes c-1…c-7)

### Events → transitions

| Current status | Event | New status | Other effects |
|---|---|---|---|
| (new) | author creates **opinion** | `published` | never enters the pipeline |
| (new) | author creates **fact** | `pending` | visible now with "Checking facts…" (guide §5.2); inline kick queued on commit. With `is_emergency`: eligibility checked first (§4b), `emergency_expires_at` stored |
| `pending` | pipeline result, verdict `true`/`false` **and** confidence ≥ threshold | `verified_true` / `verified_false` | `verdict_source=pipeline`; notify author (`verdict`) |
| `pending` | pipeline result, `inconclusive` **or** confidence < threshold | `under_review` | `flagged_reason=pipeline`, `pre_review_status=pending`; notify (`under_review`) |
| `pending` | pipeline failed `max_attempts` times | `under_review` | `flagged_reason=pipeline`; error kept in `pipeline_result` |
| `pending` / `published` / `verified_*` | report threshold crossed | `under_review` | `flagged_reason=reports`, `pre_review_status=<old>`; notify author |
| `under_review` | report threshold crossed | unchanged | `pipeline`→`both`; `reports`/`both`/`appeal` unchanged |
| `under_review` (reports, pipeline result arrives late) | decisive result | unchanged | store result; `pre_review_status=verified_*`, `verdict_source=pipeline` |
| `under_review` (reports, pipeline result arrives late) | low / inconclusive result | unchanged | `flagged_reason=both` |
| `pending` (**active emergency**) | pipeline result FALSE, confidence ≥ threshold | `under_review` | treated as not decisive: `flagged_reason=pipeline`, `pre_review_status=pending`; top of the admin queue; the post keeps its priority (§4b) |
| `under_review` (reports, **active emergency**, late result) | pipeline result FALSE, confidence ≥ threshold | unchanged | treated as not decisive: `flagged_reason=both` (no `pre_review_status=verified_false`, so dismissing reports can't make it FALSE without a human) |
| `pending` / `published` / `verified_*` (**active emergency**) | **emergency** report threshold (2) crossed | `under_review` | as for the normal threshold; priority kept |
| `under_review` | moderator **Mark verified** (fact only) | `verified_true` | `verdict_source=moderator`, `flagged_reason=null`, open reports→`actioned`; log action; notify. An emergency keeps its priority. |
| `under_review` | moderator **Mark FALSE** (fact only) | `verified_false` | same as above. On an emergency, also `emergency_demoted_at=now` (if active), author `emergency_blocked_until = now + emergency_false_cooldown_days`, notify `emergency_demoted` |
| `under_review` | moderator **Dismiss reports** | `pre_review_status` if flag was `reports`; stays `under_review` with `flagged_reason=pipeline` if flag was `both` | open reports→`dismissed`; log |
| any except `removed` | moderator **Remove** | `removed` | `pre_removal_status` = the old status (its `pre_review_status` if it was `under_review`); reports→`actioned`; log; notify (`removed`) |
| any | moderator **Escalate** | unchanged | `escalated_at=now`; log |
| any (**active emergency**) | moderator **Demote emergency** | unchanged | `emergency_demoted_at=now`; log `emergency_demoted`; notify `emergency_demoted` |
| `verified_false` (author, no prior appeal) | author **appeals** (label) | `under_review` | `flagged_reason=appeal`, `pre_review_status=verified_false`; appeal `open`, kind `label` |
| `under_review` (appeal) | Mark verified | `verified_true` | appeal `overturned`; notify `appeal_resolved` |
| `under_review` (appeal) | Mark FALSE | `verified_false` | appeal `upheld`; notify `appeal_resolved` |
| `removed` (author, no prior appeal) | author **appeals** (removal) | unchanged (stays hidden) | appeal `open`, kind `removal`; listed in the admin queue under the `appeal` filter |
| `removed` (removal appeal) | moderator **Restore post** | `pre_removal_status` | `flagged_reason=null`; appeal `overturned`; log `restored`; notify `appeal_resolved` |
| `removed` (removal appeal) | moderator **Keep removed** | unchanged | appeal `upheld`; notify `appeal_resolved` |
| `removed` | any pipeline or report event | unchanged | ignored |
| any | author deletes | unchanged | `deleted_at=now`; hidden from every list and detail view |

Also:
- A pipeline result is **ignored** when `verdict_source=moderator` (humans win).
- An appeal must be resolved by a moderator other than `original_moderator` unless the resolver is a senior (`APPEAL_REQUIRE_DIFFERENT_MODERATOR`).
- Opinions: moderators can only Dismiss or Remove.
- "Active emergency" is always computed at read time from the stored columns (`is_active_emergency`, below). No job ever flips a flag.
- Every verdict, removal, restore and appeal outcome also calls the reputation service in the same transaction (§4a).

### Routing: pure functions in `apps/pipeline/routing.py` (no I/O, exhaustively unit-tested)

```python
def merge_flag(existing, new):                      # None+x=x; x+x=x; pipeline+reports=both;
    ...                                             # appeal stays appeal; both stays both

def enter_review(post, reason):
    if post.status == UNDER_REVIEW:
        post.flagged_reason = merge_flag(post.flagged_reason, reason)
    else:
        post.pre_review_status, post.status, post.flagged_reason = post.status, UNDER_REVIEW, reason

def is_active_emergency(post, now):                 # read-time only; no scheduler (§4b)
    return (post.is_emergency and post.emergency_demoted_at is None and now < post.emergency_expires_at
            and post.status != REMOVED and post.deleted_at is None)

def apply_pipeline_result(post, result, cfg, now):  # called by the processor inside a transaction
    if post.post_type != FACT or post.status == REMOVED or post.verdict_source == MODERATOR:
        return                                      # humans and removals win
    post.pipeline_verdict, post.confidence_score, post.pipeline_result = result.verdict, result.confidence_score, result.raw_result
    decisive = (result.verdict in (TRUE, FALSE) and result.confidence_score >= cfg.confidence_threshold
                and not (result.verdict == FALSE and is_active_emergency(post, now)))  # a human confirms FALSE on a live emergency
    label = VERIFIED_TRUE if result.verdict == TRUE else VERIFIED_FALSE
    if post.status == PENDING:
        if decisive: post.status, post.verdict_source = label, PIPELINE
        else:        enter_review(post, PIPELINE)
    elif post.status == UNDER_REVIEW:
        if decisive: post.pre_review_status, post.verdict_source = label, PIPELINE
        else:        post.flagged_reason = merge_flag(post.flagged_reason, PIPELINE)

def apply_report_threshold(post, counting_reports, cfg, now):
    threshold = cfg.emergency_report_threshold if is_active_emergency(post, now) else cfg.report_threshold
    if post.status != REMOVED and counting_reports >= threshold:
        enter_review(post, REPORTS)
```

`now` is a parameter everywhere so tests control time. Parts 8 and 9 already take `now`; Part 11C adds the emergency branches.

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
| **active emergency** (any status above except removed) | **EMERGENCY** chip, shown next to the status badge | `bolt` | tertiary | no |

- The 4 px stripe on the card uses the same colour; opinion and pending use `outline-variant`.
- While an emergency is active the stripe is `tertiary` (violet) whatever the status. After expiry or demotion the card looks like any other post with that status, and only the detail page keeps a neutral note ("Posted as an emergency on …").
- Labels say **FALSE** everywhere (D4); "debunked" is never used.

## 4a. Credibility score (`reputation`; D5, ANALYSIS f-5; Part 11B)

**Formula** (pure functions in `apps/reputation/scoring.py`):

```python
def score(p, n):              # p, n = sums of the positive / negative weights of all ledger rows (reversals included)
    return round(100 * (5 + p) / (10 + p + n))   # starts at 50; the 10 imaginary events damp single-post swings
```

- **Public only when `reputation_sample ≥ 3`.** Below that the API returns `score: null` and the UI says "New". Emergency eligibility always uses the stored score.
- A new account moves 50 → 45 after one FALSE, 50 → 55 after one TRUE, and 50 → 38 after a FALSE emergency.

**Events** (the only ones that exist):

| Kind | Who | When | Weight |
|---|---|---|---|
| `fact_true` | author | a fact post becomes `verified_true` (pipeline or moderator) | P + 1 |
| `fact_false` | author | a fact post becomes `verified_false` | N + 1 |
| `emergency_false` | author | an `is_emergency` post becomes `verified_false` (replaces `fact_false`) | N + 3 |
| `post_removed` | author | a moderator removes the post (any type) | N + 2 |
| `report_upheld` | reporter | the reported post is removed or marked FALSE by a moderator while the report is open; at most 4 counted per reporter per rolling 30 days | P + 0.25 |
| `repost_true` / `repost_false` / `repost_emergency_false` / `repost_removed` | reposter | the original reaches that outcome **and** the repost was made while it was `pending` or `under_review` (`status_at_repost`) | P + 0.25 / N + 0.5 / N + 1 / N + 0.5 |
| `reversal` | same user as the row it cancels | the outcome is overturned (§ below) | the negated weights |

Nothing else changes the score:
- An emergency verified TRUE is a plain `fact_true`, with no bonus.
- Dismissed reports cost the author and the reporter nothing.
- Opinions only count when removed.
- A failed appeal costs nothing.
- Reposting an already-checked post earns nothing.

**Rules**
- **Idempotent:** at most one un-reversed outcome row per (user, post, role). Re-applying the same verdict is a no-op.
- **Re-labels:** when a label changes (moderator re-decision, appeal overturned, restore), the service appends `reversal` rows for the old outcome, for the author **and every reposter**, then records the new outcome.
- **Deletion:** deleting a post (D6) doesn't undo its events, and undoing a repost after the verdict doesn't either.
- **Writes:** only `apps/reputation/services.py` writes the ledger and `users.reputation_score` / `reputation_sample`. It is called explicitly (no signals) from `posts.services` and `moderation.services`, inside their transaction, with `select_for_update()` on the user row. `score_after` is stored on every row.
- **Recompute:** `python manage.py recompute_reputation [--user …] [--check]` rebuilds the denormalised fields from the ledger; `--check` fails on any difference.

**Display**
- The score appears in the profile header, user rows and people search, plus the Credibility widget (ring, counts, 30-day trend; 11D).
- The owner's full history is in settings, with reversed rows marked and an "Ask for another look" link on each negative row.
- A "How this is calculated" section lives on `/how-it-works#credibility`.
- The score is **never shown on post cards**, and people are never ranked by it.

**Appeal path and legal caution (guide §16)**
- Label appeals (FALSE) and removal appeals (§4) both exist.
- An overturned appeal reverses the events for the author and every reposter, so the score returns exactly to what it would have been.
- The ledger is the audit trail.
- The Terms of Service wording about labels and the score needs legal review before launch.

## 4b. Emergency posts (D5, ANALYSIS f-1; Part 11C)

**What:** a flag on a **fact** post. The post is pinned at the top of feeds for `emergency_duration_hours` (24), still fact-checked (first), and shown in violet (`tertiary`).

**Eligibility** (checked in `posts.services.create_post`; also reported by `GET /api/v1/me/fact-quota/` as `emergency: {allowed, reason, next_allowed_at}`):

| Rule | Reason code |
|---|---|
| email verified | `unverified` |
| account age ≥ `emergency_min_account_age_days` (7) | `account_too_new` |
| `reputation_score ≥ emergency_min_reputation` (40) | `score_too_low` |
| `emergency_blocked_until` is null or in the past | `blocked` |
| fewer than `emergency_posts_per_day` (1) emergencies in the last 24 h | `daily_limit` |
| the fact quota still has room (emergency posts count toward it) | `fact_quota` |

**Lifecycle**
- **Creation:** `emergency_expires_at = created_at + emergency_duration_hours` is stored.
- **Active:** `is_active_emergency(post, now)` (§4) is computed on every read. There is no scheduler, which matters because free hosts sleep.
- **Pipeline:** emergencies are processed first. A TRUE result gives `verified_true`, and the post stays pinned until expiry. A FALSE result while active never becomes FALSE automatically: the post goes to `under_review`, sits at the top of the admin queue, and **keeps its priority**. The same applies to inconclusive or low-confidence results and to reports: priority is kept through any review until expiry or a moderator's FALSE.
- **Moderator Mark FALSE:** `verified_false`, the priority ends at once (`emergency_demoted_at`), and the author is blocked from emergency posts for `emergency_false_cooldown_days` (30). The score takes the `emergency_false` event (N + 3).
- **Other moderator actions:** Demote emergency ends priority without a label change. Remove works as usual. **Block emergency posting** (UserAdmin) sets `emergency_blocked_until`. All of these are logged.
- **Reports:** while the post is active, `emergency_report_threshold` (2) replaces `report_threshold` (5).
- **After expiry or demotion:** it's a normal post with its status colour. The detail page shows "Posted as an emergency on <date>. Priority ended." (or "… removed by a moderator").

**Pinning (feeds, §9)**
- Recent pins all active emergencies; Following pins those from followed accounts plus you.
- Newest first, at most 3 in `pinned`, with `pinned_total` for "Show all" (`GET /api/v1/posts/emergencies/`).
- Pinned posts are left out of `results`. Reposts never pin (a repost of an emergency shows as a normal item with the chip).

**Notifications:** the author gets `emergency_demoted` when priority is removed early. Out of scope: follower alerts, email or push, and moderator email alerts.

## 4c. Source / DOI (D5, ANALYSIS f-3; Parts 4–5)

- **Scope:** optional, fact posts only, one per post, immutable, at most 500 chars. It's stored in `source` + `source_kind`.
- **DOI input:** `10.<4–9 digits>/<suffix>` (Crossref's recommended pattern `^10\.\d{4,9}/[-._;()/:A-Za-z0-9]+$`). A leading `doi:` or `https://doi.org/` / `http://dx.doi.org/` is accepted and stripped. Stored bare, e.g. `10.1038/s41558-024-02102`, with `source_kind=doi`.
- **URL input:**
  - `http` or `https` only;
  - a host with a dot, no user/password, no IP-address or `localhost` hosts, no whitespace or control characters;
  - internationalised hosts are converted to punycode for storage and display;
  - `source_kind=url`.
- **Never fetched.** The server makes no request to the URL: no previews, no HEAD checks (no SSRF). A test enforces this.
- **Display:** fact cards show one line with the host (or `doi.org/…` for a DOI); the detail page shows the full value. DOIs link to `https://doi.org/<doi>`. Links use `rel="nofollow ugc noopener noreferrer"` and `target="_blank"`, and the text is plain.
- **Pipeline:** passed as the optional `source` in `PipelineRequest` (§6) for the future real pipeline. The stub ignores it.

## 4d. Bookmarks and reposts (D5, ANALYSIS f-4; Part 7B)

**Bookmarks**
- Any logged-in user can bookmark (no email verification needed, because bookmarks are private).
- Toggling is idempotent.
- `GET /api/v1/me/bookmarks/` lists your bookmarks, newest bookmark first, and drops deleted and removed posts.
- `bookmarked_by_me` appears in the post object. No count is ever exposed.

**Reposts**
- Plain reposts only: one per user per post, and never of a repost (reposting a repost reposts the original).
- Refused:
  - your own posts (`cannot_repost_own`);
  - posts that are `verified_false` (`cannot_repost_false`);
  - removed or deleted posts (404).
- Email-verified users only. `status_at_repost` is recorded.
- A repost has no content and no status of its own. It always shows the original's **live** label, and nothing is re-checked.
- If the original is later deleted or removed, the repost item shows "This post is no longer available".
- Following feed and profiles show reposts ("Reposted by @x"); Recent shows originals only.
- The original author is notified (`repost`, de-duplicated). Score effects are in §4a.

## 4e. Profile photos (D5, ANALYSIS f-7; Part 14B)

**Upload:** `PUT /api/v1/me/avatar/` (multipart `file`). Email-verified only, not when `avatar_uploads_blocked`, throttle `avatar_upload` 5/day. `DELETE /api/v1/me/avatar/` removes it.

**Processing** (`apps/accounts/avatars.py`, Pillow):
1. Reject anything over 5 MB before reading it fully.
2. Open with Pillow and require the decoded format to be JPEG, PNG or WebP. The extension and `Content-Type` are ignored. SVG, GIF, HEIC and animated images are refused.
3. Check the dimensions before decoding the pixels: at most 25 MP (`Image.MAX_IMAGE_PIXELS`), at least 128×128. JPEGs are decoded with `draft()` to save memory.
4. Apply the EXIF orientation (`ImageOps.exif_transpose`), convert to RGB, centre-crop to a square, and resize (LANCZOS) to 256 and 96 px.
5. Encode as WebP (quality ≈ 80) with **no** EXIF, ICC or XMP. Only these two images are stored; the upload is discarded.
6. Save the `Avatar` row and set `users.avatar_version`, which gives a new URL.

**Serving:** `GET /api/v1/avatars/{user_id}/{version}-{96|256}.webp`
- public; a wrong version or size returns 404;
- headers: `Content-Type: image/webp`, `Cache-Control: public, max-age=31536000, immutable`, `ETag`, `X-Content-Type-Options: nosniff`, `Content-Security-Policy: default-src 'none'; sandbox`, `Content-Disposition: inline; filename="avatar.webp"`;
- goes through the relay like every `/api` call, and the relay passes these headers and `304` back.

**Everywhere:** `author.avatar_url` / `user.avatar_url` is null when there's no photo. `<Avatar>` falls back to initials when there's no photo, on load error, and after removal.

**Moderation:** AvatarAdmin (thumbnails, newest first) with **Remove photo** and **Block photo uploads**, logged with `subject_user`. There is no user-facing "report photo" in the MVP (follow-up). The Google profile picture is never imported.

## 5. Reporting (guide §6; c-2)

`POST /api/v1/posts/{id}/report/`:
1. **Pre-checks:** logged in, **email verified**, not the author, post visible (not removed or deleted), throttle `report` 10/h.
2. Inside `transaction.atomic()`:
   - `select_for_update()` the post
   - insert the report (the unique constraint turns a duplicate into **409**)
   - `report_count += 1`
   - `counts_toward_threshold` = reporter account age ≥ `report_min_account_age_hours` **or** reporter has ≥1 post or comment (guide §6.3)
   - `n` = count of this post's reports with `status='open' AND counts_toward_threshold AND created_at >= now - window`
   - `apply_report_threshold(post, n, cfg, now)` (threshold 2 instead of 5 while an emergency is active, §4b)
   - save
3. The post stays visible while under review (guide §6.4). Redis is never used for the count.
4. When a moderator later removes the post or marks it FALSE, every report that was still open becomes `actioned`, and each reporter gets the `report_upheld` credit (§4a, capped).

## 6. Pipeline contract and processing (guide §5.4, §7.1; c-21)

```python
# apps/pipeline/contract.py — frozen dataclasses, validated on construction
PipelineRequest(post_id: UUID, content: str, source: str | None)   # source = the validated URL or DOI (§4c), never fetched by us
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
- **`HttpPipelineClient`** (`PIPELINE_BACKEND=http`, future): `POST PIPELINE_URL` with `{post_id, content, source}`, `Authorization: Bearer PIPELINE_API_KEY`, 20 s timeout. It expects `{verdict, confidence_score, raw_result}`. Swapping it in changes nothing else.
- **Processor** `process_pending(limit=10, now)`:
  - selects fact posts with `status='pending'`, `deleted_at IS NULL`, `pipeline_next_attempt_at` null or ≤ now, **emergencies first** (`is_emergency DESC`), then oldest first, `FOR UPDATE SKIP LOCKED`;
  - calls the client and routes the result with `apply_pipeline_result(post, result, cfg, now)`;
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
- `IsEmailVerified` (code `email_unverified`, 403) for creating posts (including emergencies), comments, likes, follows, reposts, reports, appeals and profile photos (unverified = read-only). Bookmarks are private, so they only need a login.
- `IsModerator` / `IsSeniorModerator` for admin.
- The superuser is created from your PC (ENV_GUIDE §2.6).

**Turnstile:** on signup only (guide §4.1). Local dev uses the always-pass test keys.

## 8. Moderation panel: Django Admin (guide §8; d2 is a reference only)

- **Roles:**
  - *Moderator*: review queue, the actions below, can't change roles or delete users.
  - *Senior moderator*: + manage moderator accounts (edit `role`), edit `PlatformSettings`, full audit log.
  - Implemented with Groups and model permissions synced from `role`.
- **Review queue:** `PostAdmin`, default filter `status=under_review`, plus removed posts with an open removal appeal.
  - Columns: content (truncated), type, flagged_reason, confidence, report_count, age in queue, escalated, emergency (active / expired / —).
  - Filters: flagged_reason (pipeline / reports / both / appeal), appeal kind (label / removal), type, escalated, emergency (active).
  - Default order: **active emergencies first**, then report_count, then created_at. Sortable by report_count and created_at.
  - Search: content, author username.
  - Inlines: reports (reason, details, reporter age), appeal, moderation history, credibility events for this post.
- **Bulk actions**, each calling `moderation.services` and writing `moderation_actions`:
  - *Mark verified*, *Mark FALSE* (fact posts only; optional public `verdict_note`)
  - *Dismiss reports*
  - *Remove post*
  - *Escalate to senior*
  - *Demote emergency* (11C)
  - *Restore post* / *Keep removed* (removal appeals, 11)
- Users: *Block emergency posting* (11C); *Remove photo*, *Block photo uploads* (14B). These are logged with `subject_user`.
- Comments: *Hide comment*.
- Credibility ledger: read-only list (filters by kind; search by username). UserAdmin shows the score with a link to the user's rows.
- The admin header shows the logo (`core/brand/logo-admin.png`, §14) and "Rumor Zero moderation" (`templates/admin/base_site.html`). It is served at `<BACKEND>/<ADMIN_URL_PATH>`. `/api/v1/me/` returns `admin_url` only to staff, so the sidebar "Moderation" link never exposes the path to others.

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
- **Toggles are idempotent:** `POST` like/follow/repost/bookmark → 201 (200 if already there); `DELETE` → 204.
- **Performance:** every list uses `select_related("author")` plus annotated `like_count`, `comment_count`, `repost_count`, `liked_by_me`, `reposted_by_me`, `bookmarked_by_me`, `reported_by_me`. No N+1 (guide §9.3). Tests assert query counts.
- **Home feed (Following):**
  - Fan-out-on-read: posts by `followed ∪ {me}` **plus reposts by them** (7B), ordered by activity time. The cursor is `(activity_at, item id)`, and the same post appears at most once per page (the most recent activity wins).
  - The first page is cached per user for `FEED_CACHE_SECONDS` (guide §9.2). The cache is busted when you post, repost or change a follow.
  - The `pinned` list is computed separately on each first-page request (a short shared cache for Recent). An emergency may therefore look active up to 30 s after it expires; that's accepted.
  - Status polling is never cached.
- **Recent feed:** originals only, newest first, plus the site-wide `pinned` list.

**Feed response** (Recent, Following and profile post lists all use this shape from Part 4, so it never changes):

```json
{ "pinned": [ {Post} ], "pinned_total": 1,
  "results": [
    {"kind": "post",   "post": {Post}, "reposted_by": null, "activity_at": "…"},
    {"kind": "repost", "post": {Post}, "reposted_by": {"id": "uuid", "username": "bo", "display_name": "Bo", "avatar_url": null}, "activity_at": "…"} ],
  "next_cursor": "…" }
```

- `pinned` is `[]` until Part 11C, and always `[]` after the first page and on profile lists. Recent never contains `kind: "repost"`.
- A repost whose original was deleted or removed comes back as `"post": {"id": "uuid", "unavailable": true}` → "This post is no longer available".

**Post object** (all list and detail endpoints):

```json
{ "id": "uuid",
  "author": {"id": "uuid", "username": "ada", "display_name": "Ada", "avatar_url": null},
  "content": "…", "post_type": "fact", "status": "verified_true",
  "source": "10.1038/s41558-024-02102", "source_kind": "doi",
  "is_emergency": false, "emergency_active": false, "emergency_expires_at": null,
  "confidence_score": "94.00", "verdict_source": "pipeline", "verdict_note": "",
  "like_count": 3, "comment_count": 1, "repost_count": 2,
  "liked_by_me": false, "reposted_by_me": false, "bookmarked_by_me": false, "reported_by_me": false,
  "is_mine": false, "can_appeal": false, "appeal_status": null, "created_at": "…" }
```

- `confidence_score` is non-null only for `verified_*` with `verdict_source=pipeline`.
- `emergency_active` is computed at serialization with `now` (§4b).
- `avatar_url` is `/api/v1/avatars/{user_id}/{avatar_version}-96.webp`, or null (initials). The 256 px size is used on profiles.
- `flagged_reason`, report details and bookmark counts are never public.
- `appeal_status` is only returned to the author; `can_appeal` is true for their FALSE-labelled or removed posts without a previous appeal.
- The public `reputation` block (`{"score": 72 | null, "sample": 23}`) is on user objects (profile, user rows, people search), **not** on post authors.

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
| 7B | POST/DELETE `/api/v1/posts/{id}/repost/` · POST/DELETE `/api/v1/posts/{id}/bookmark/` · GET `/api/v1/me/bookmarks/` | reposts, bookmarks |
| 8 | POST `/api/v1/posts/{id}/report/` | reports |
| 9 | POST `/api/internal/tick/` | pipeline sweeper |
| 11 | POST `/api/v1/posts/{id}/appeal/` | appeals (FALSE labels and removals) |
| 11B | GET `/api/v1/users/{username}/reputation/` · GET `/api/v1/me/reputation/events/` | credibility score |
| 11C | GET `/api/v1/posts/emergencies/` · `emergency` block added to GET `/api/v1/me/fact-quota/` | emergency posts |
| 11D | GET `/api/v1/posts/{id}/stats/` · `trend` added to the reputation endpoint | charts |
| 12 | GET `/api/v1/search/?q=&type=posts\|users&post_type=&status=` | search |
| 13 | GET `/api/v1/notifications/` · GET `…/unread-count/` · POST `…/mark-read/` | notifications |
| 14 | PATCH `/api/v1/me/` · POST `/api/v1/me/password/` · GET `/api/v1/me/export/` · DELETE `/api/v1/me/` | settings |
| 14B | PUT/DELETE `/api/v1/me/avatar/` · GET `/api/v1/avatars/{user_id}/{version}-{size}.webp` | profile photos |

**Stats and credibility payloads (11B, 11D):**
- `GET /api/v1/posts/{id}/stats/`:
  - Visibility is the same as the detail endpoint.
  - Returns `{confidence_score, confidence_threshold, verdict_source, seconds_to_verdict, verdict_at, daily: [{date, reposts, likes, comments}]}`.
  - The confidence fields are null unless `verdict_source=pipeline`.
  - `daily` covers the first 14 UTC days after posting, from grouped counts on `(post, created_at)` indexes, with a constant number of queries. Uncached.
- `GET /api/v1/users/{u}/reputation/` returns:
  - `{score | null, sample, verified, false, removed, recent: [≤ 10 public events: kind, label, post_id, created_at, reversed]}`;
  - from 11D, also `trend: [30 × {date, score}]` (null while the score is hidden).
- `GET /api/v1/me/reputation/events/`: your whole ledger (cursor), including reversal rows and links to appeal.

**Search (guide §10):** `SearchQuery(q, search_type="websearch", config="english")` against `search_vector`, ranked with `SearchRank`, newest first on ties. Users are matched by `username`/`display_name` prefix and returned with their `reputation` block (never sorted by it). Removed and deleted posts are excluded.

## 10. Frontend conventions

- Server Components by default. `"use client"` only where there's state or events.
- All API calls go through `src/lib/api/client.ts` (relative `/api` base). **Never** call `BACKEND_ORIGIN` from the browser.
- Styling:
  - Tokens live only in `globals.css` `@theme`.
  - Use Stitch class names (`bg-surface-container-low`, `font-claim-headline text-claim-headline`, `max-w-reading`, `px-space-md`).
  - **No** Tailwind default palette, no arbitrary hex, only `rounded-lg`/`rounded-full`, `shadow-sm` only.
  - Fact text: `font-claim-headline text-claim-headline`. Opinion text: `font-claim-opinion text-claim-opinion italic`.
- User text is rendered as plain text (`whitespace-pre-wrap break-words`). Never `dangerouslySetInnerHTML`.
- Avatars use `<Avatar>`: the user's photo when `avatar_url` is set (14B), otherwise initials, and initials on load error. Icons use `<Icon name="…"/>` (Material Symbols, self-hosted).
- The brand is shown **only** through `<Logo/>` (§14). Never re-create the old text wordmark or the emblem tiles.
- Images (logo, avatars) are plain `<img>` with explicit width/height. `next/image` optimisation is not used: on Workers it needs Cloudflare Images, and our images are already pre-sized. SVG is never inlined from a file.
- Charts are token-built HTML/SVG (`src/components/ui/charts/`, 11D), each with `role="img"`, an `aria-label` summary and a visually hidden data table. No chart library.
- Source links: `rel="nofollow ugc noopener noreferrer"`, `target="_blank"`, plain-text label (§4c).
- Accessibility:
  - Every status is shown by glyph **and** label **and** colour (DESIGN.md).
  - Modals use `<dialog>`, focus-visible rings in `secondary`, labels bound to inputs.
- Tokens never go in `localStorage`/`sessionStorage`.

## 11. Testing (guide §17). Every part ships tests.

- **Backend (pytest-django, real Postgres 18):**
  - models and constraints
  - services and the **routing table in §4** (one test per row, including the emergency rows, with a controlled `now`)
  - the credibility weight table in §4a (one test per event kind, plus reversals and `recompute_reputation --check`)
  - profile-photo processing with generated fixtures (EXIF/GPS, bombs, wrong types)
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
| Uploaded images (profile photos) | decode-and-re-encode with Pillow (JPEG/PNG/WebP in, WebP out); size, pixel and dimension limits before decoding; EXIF/GPS/ICC/XMP dropped; original never stored; served from our origin with `nosniff` + `default-src 'none'; sandbox`; no SVG uploads (§4e) |
| User-supplied links (source/DOI) | http/https only; no credentials, IP or localhost hosts; punycode shown; `rel="nofollow ugc noopener noreferrer"`; **never fetched server-side** (no SSRF) (§4c) |
| Emergency abuse | eligibility gates, 1 per 24 h, lower report threshold, human confirmation of FALSE, 30-day block, moderator demote/block (§4b) |
| Public credibility score (reputational/legal risk, guide §16) | only automated from labels; audit ledger; exact reversal on appeal; label and removal appeals; never ranked or shown on cards; Terms need legal review (§4a) |
| Logo SVG | our own file, checked by the brand build (no scripts, links, bitmaps or text) and served as `<img>` (§14) |

## 13. Free-tier budgets to respect (verified 2026-09-29)

| Service | Budget | Design consequence |
|---|---|---|
| Cloudflare Workers | 100k requests/day, 10 ms CPU | prerender; poll only when visible; escape hatch in ANALYSIS d. Each profile photo costs one request per browser (then cached for a year). Logo and icons are static assets, which are free and don't count. |
| Render | 750 h/month, sleeps after 15 min, 512 MB, no SMTP/workers/cron | 5-min UptimeRobot ping on the no-DB health endpoint; inline kick + hourly tick; Brevo API for email; emergency expiry computed at read time; photo limits keep decoding memory small |
| Neon | 100 CU-h/month, 0.5 GB, sleeps after 5 min | never ping the DB frequently; direct connection with `CONN_HEALTH_CHECKS=True`. Profile photos ≈ 20 KB each (5,000 ≈ 100 MB); `avatars.bytes_total` lets you watch it |
| Upstash | 500K commands/month, archived after ~30 days idle | Redis only for the feed cache and throttles; daily deep ping |
| Brevo | 300 emails/day | only verification + reset emails |
| Sentry | 5K errors/month | traces sample rate 0.0 |
| GitHub Actions | 2,000 min/month if private | CI + one daily job; no 10-min cron |

## 14. Branding and logo (D9, changed 2026-09-29; ANALYSIS e, f-8; Part 0D)

**Master:** `design/logo.svg` (read-only; you replace it, Claude never edits `design/`). `design/logo.png` is an earlier raster version, kept but **not used**.

**What the SVG is (inspected 2026-09-29):**
- `viewBox="0 0 1000 1000"`, no width/height, transparent background, 2.6 KB.
- The wordmark "Rum0r": R, u, m, r in teal `#19aa96` (class `cls-1`); the "0" and a full-width underline in amber `#f4a361` (class `cls-2`).
- All text is outlined paths: no fonts, scripts, links or bitmaps.
- The artwork spans x 121.4–878.6, y 413.0–625.7 of the 1000 box (≈ 3.6 : 1); the rest of the square is empty. The "0" is the only `path.cls-2` (x 664.5–779.2, y 413.0–584.9).
- Accessible name everywhere: **"Rumor Zero"** (the logo reads "Rum0r").

**Colour check against the Stitch tokens (flagged):**

| Logo colour | Nearest Stitch token | Consequence |
|---|---|---|
| teal `#19aa96` | `primary-container` `#00a896` (Verified family) | practically the Verified colour |
| amber `#f4a361` | `verdict-review` `#F4A261` (Under review) | practically the Under-review colour |

- DESIGN.md reserves colour for verdicts, so these two colours live **only inside the logo image**. They never become tokens, buttons, links or badges. UI keeps using the verdict tokens for verdicts only.
- If the match with the verdict colours isn't intended, recolouring is a one-command change (below).

| Contrast (WCAG ratio) | teal letters | amber "0" / underline |
|---|---|---|
| on `surface-container-lowest` `#ffffff` (sidebar, cards) | 2.9 : 1 | 2.0 : 1 |
| on `surface` `#faf8ff` (page) | 2.8 : 1 | 1.9 : 1 |
| on `inverse-surface` `#283044` | 4.5 : 1 | 6.4 : 1 |
| on `on-surface` `#131b2e` | 5.9 : 1 | 8.4 : 1 |

- Logotypes are exempt from WCAG 1.4.3 / 1.4.11, so this is recorded, not blocking. The logo reads best on dark surfaces.
- In the (light) app it sits directly on the light surfaces as designed. Every generated **plate** (favicon, app icons, share image, email, Google, admin) puts it on `inverse-surface` `#283044`, a Stitch token.
- Rumor Zero has no dark theme (Stitch is light-only). "Works on dark" covers dark browser tabs, dark-mode email clients, link previews and dark UI spots such as toasts.

**Component:** `frontend/src/components/ui/Logo.tsx`, the only way the UI shows the brand:
- `variant="wordmark"` (default) or `"mark"` (the "0" alone);
- `size="sm" | "md" | "lg"` = 24 / 36 / 48 px tall;
- accessible name "Rumor Zero", or `decorative` (`alt=""`) when the name is written next to it;
- plain `<img>` with width/height; never inlined.

It reads `src/lib/brand-assets.json`.

**Derived assets:** generated by `npm run brand:build` (`frontend/scripts/brand/build-brand-assets.mjs` + `brand.config.json`, Part 0D). They are committed and never edited by hand.

| Asset | Path | Size | Used by |
|---|---|---|---|
| Wordmark | `frontend/public/brand/logo.svg` (viewBox cropped to the artwork + padding) | any | every `<Logo/>` wordmark |
| Mark | `frontend/public/brand/mark.svg` (the "0" path in its own square viewBox) | any | `<Logo variant="mark"/>` (tablet icon dock) |
| Favicon | `frontend/src/app/favicon.ico` (16, 32, 48; PNG-in-ICO) + `frontend/src/app/icon.svg` | — | browser tabs (Safari and older browsers use the .ico) |
| Apple touch icon | `frontend/src/app/apple-icon.png` | 180×180, opaque plate | iOS home screen |
| App icons | `frontend/public/brand/icon-192.png`, `icon-512.png`, `icon-maskable-512.png` (mark inside the 80 % safe zone) + `frontend/src/app/manifest.ts` | — | Android / install |
| Share image | `frontend/src/app/opengraph-image.png`, `twitter-image.png` (+ `.alt.txt` "Rumor Zero") | 1200×630 | link previews (static, because the Worker's 10 ms CPU limit rules out generating them) |
| Email logo | `frontend/public/brand/email-logo.png` | 320 px wide, shown at 160 | HTML emails (Part 2) via `FRONTEND_ORIGIN/brand/email-logo.png` |
| Google logo | `frontend/public/brand/google-oauth-logo.png` | 120×120, < 1 MB | optional consent-screen upload (ENV_GUIDE §2.9) |
| Admin logo | `backend/apps/core/static/core/brand/logo-admin.png` | 64 px tall | Django admin header (Part 10) |
| Asset list | `frontend/src/lib/brand-assets.json` | — | generated; read by `Logo`, `manifest.ts` and the root metadata |

- Icons and the mark use the amber "0" on the `inverse-surface` plate. The share image, email, Google and admin logos use the full wordmark on the same plate.
- The build **only reads** `design/`. It fails if the master contains `<script>`, `<foreignObject>`, `on*` attributes, external `href`/`xlink:href`, embedded bitmaps or `<text>`, or has no `viewBox`. It prints the contrast table above.

**Placements:**
- Part 0C:
  - app sidebar top (wordmark `md`)
  - tablet icon dock (mark)
  - mobile top bar (wordmark `sm`)
  - auth card header (wordmark `lg`)
  - marketing nav (`md`) and footer (`sm` + "© 2026 Rumor Zero")
  - 404/500 pages
- Part 2: emails.
- Part 10: Django admin header.
- Part 0D: favicon, app icons, share image.

The old marks replaced are listed in ANALYSIS e.2; DESIGN.md's sidebar wordmark spec (line 243) is overridden here.

**Changing the logo later:**
1. Replace `design/logo.svg` yourself.
2. Run `npm run brand:build` in `frontend/`.
3. Compare the printed contrast table with this section and update it.
4. Commit the regenerated files.
