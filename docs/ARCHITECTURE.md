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
| Cookie / header prefixes | cookies `rz_refresh` (httpOnly refresh token) and `rz_session` (readable hint); headers `X-RZ-Proxy-Secret`, `X-RZ-Client-IP`, `X-RZ-Cron-Secret`; `X-Requested-With: rumor-zero` |
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

- `frontend/src/app/api/[...path]/route.ts` (the **API relay**) forwards `/api/*` to `BACKEND_ORIGIN`. The logic is in `src/lib/api/relay.ts` (route files may only export handlers). Rules (Part 0C):
  - **Config:** `BACKEND_ORIGIN` must be `https:` (plain `http:` only for loopback hosts, so the secret never travels in clear) and a bare origin; `PROXY_SHARED_SECRET` must be set. Otherwise `500 {"code":"relay_misconfigured"}`, logging the variable name only.
  - **Path:** the target is `BACKEND_ORIGIN + pathname + search` of `request.url` (Next has already resolved `..`, `%2e%2e` and `\`). Encoded `%2F`, `%5C` or `%00` → 400; a target outside `/api/` or off the backend origin → 404.
  - **Trailing slashes:** `next.config.ts` sets `skipTrailingSlashRedirect: true`, because Next's built-in `/:path+/ → /:path+` redirect would loop with Django's `APPEND_SLASH`. One `redirects()` rule still strips the slash from page URLs (`/home/` → `/home`). OpenNext already exempts `/api/` and honours the flag.
  - **Request headers allow-list:** `Accept`, `Authorization`, `Content-Type`, `Cookie`, `Origin`, `X-Requested-With`, `If-None-Match`, `If-Modified-Since`, `User-Agent`. Then it adds `X-RZ-Proxy-Secret` and `X-RZ-Client-IP`. `Host`, hop-by-hop headers, `X-Forwarded-*`, `Content-Length` and any client `X-RZ-*` are never forwarded.
  - **Client IP:** `cf-connecting-ip` (set by Cloudflare's edge), else the right-most `X-Forwarded-For` entry, after a charset/length check (Django re-parses it). Locally `next dev` keeps a client-sent `X-Forwarded-For` (`??=` in Next's server), so only local dev can be spoofed.
  - **Bodies are buffered, not streamed:** Django (runserver and WSGI) reads `CONTENT_LENGTH`, so a chunked body would arrive empty, and OpenNext buffers request bodies on Workers anyway. Over 6 MB (declared or counted) → `413 {"code":"payload_too_large"}`; the runtime sets `Content-Length`.
  - **Fetch:** `redirect:'manual'`, `cache:'no-store'`, signal = the client's abort + a 70 s timer that is **cleared when headers arrive**, so a long download isn't cut off. Any failure before headers (timeout, refused, DNS), or an upstream non-JSON 502/503/504 (Render's own error page), → `503 {"detail": "…", "code":"backend_waking"}` with `Retry-After: 30` and `Cache-Control: no-store`. A status outside 200–599 → 502 `bad_gateway`.
  - **Response headers allow-list:** `Content-Type`, `Cache-Control`, `ETag`, `Last-Modified`, `Content-Disposition`, `X-Content-Type-Options`, `Content-Security-Policy`, `Retry-After`; every `Set-Cookie` (via `getSetCookie()`); `Content-Length` only when the upstream has no `Content-Encoding` (fetch decodes gzip/br); `Location` only when it points at the backend's own `/api/`, rewritten as a relative URL. 204/205/304 and HEAD responses have no body.
- Django's `ClientIPMiddleware` sets `REMOTE_ADDR` from `X-RZ-Client-IP` **only** if the secret matches (constant-time compare, and the IP must parse); otherwise it uses the right-most `X-Forwarded-For` entry (only that one: everything to its left is client-supplied, so an unparseable right-most entry leaves `REMOTE_ADDR` alone). It is the first middleware and **removes both `X-RZ-*` headers from `request.META`**, so no later code, log line or error report can see them. allauth (`ALLAUTH_TRUSTED_PROXY_COUNT=0`) and DRF (`NUM_PROXIES=0`) then read `REMOTE_ADDR`.
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
- Headings below are logical names. Physical tables keep Django's defaults (`accounts_user`, `core_platformsettings`, …).

### users: `accounts.User` (`AUTH_USER_MODEL`, must exist before the first migration)

`AbstractBaseUser` + `PermissionsMixin`. **`USERNAME_FIELD = "email"`** (Django Admin logs in with the email, case-insensitively), `REQUIRED_FIELDS = ["username"]`, so `createsuperuser` asks for email, username, password.

| Field | Type | Notes |
|---|---|---|
| id | uuid PK | |
| username | varchar(30) unique | lowercase `^[a-z0-9_]{3,30}$`, stored lowercase. Input is NFKC-normalised, stripped and lowercased before validation (so "Ada" is stored as `ada`). Reserved words are blocked by **exact match**, case-insensitively (`admin` is reserved, `ada_admin` is not); the list is `RESERVED_USERNAMES` in `apps/accounts/validators.py`. A DB check enforces the format. |
| email | varchar(254) unique | stripped and lowercased on save (a DB check enforces lowercase); never shown publicly |
| password | Django hasher field | **Argon2id** first in `PASSWORD_HASHERS` (PBKDF2 fallback). Google-only accounts get `set_unusable_password()`, never NULL (c-11). |
| display_name | varchar(50) | blank → UI falls back to `@username` |
| bio | varchar(280) | |
| role | `user` \| `moderator` \| `senior_moderator` | default `user`. **Source of truth**: on save, syncs Django Groups "Moderators" / "Senior moderators" and `is_staff = is_superuser or role != user` (c-10). Groups are **cumulative**: `moderator` → "Moderators"; `senior_moderator` → both "Moderators" and "Senior moderators" (Part 10 gives the senior group only the extra permissions). Only those two groups are managed; other groups are left alone. The sync runs on create and when `role` changes, so a `last_login`-only save stays one query. In Django Admin `is_staff` and `groups` are read-only (editing them would fight the sync). `createsuperuser` leaves `role = user`, so the superuser keeps Django Admin access through `is_superuser`. |
| is_email_verified | bool, default false | mirror of allauth `EmailAddress.verified` for the primary email (signal `email_confirmed`); true for Google sign-ups and for accounts a Google sign-in linked to (allauth never sends `email_confirmed` for Google emails, so `social_account_added` sets it, §7). **Superusers count as verified** (user decision 2026-10-01): `createsuperuser` sets it and creates a verified primary `EmailAddress`, and migration `accounts.0002_verify_superuser_emails` did the same for existing superusers. |
| is_active, is_staff, is_superuser, last_login | Django | |
| avatar_version | varchar(16) null | null = no photo (initials). Equal to the `Avatar` row's `version`. Written **only** by `apps/accounts/avatars.py` (`save_photo`, `delete_photo`), with `.update()` under the account's lock; the photo URL is built from it (§9) at no extra query. **A full `User.save()` never writes it** (Part 14B; the rule of the score and the emergency block), so a stale copy saved by the admin form or allauth's `set_password` can't bring a removed photo back. Replaces the old unused `avatar_url`. |
| avatar_uploads_blocked | bool, default false | Block photo uploads sets it and Allow photo uploads clears it (§4e, §8). Written **only** by `apps/moderation/services.py`, with `.update()`; a full `User.save()` never writes it, so a stale save can't lift a block |
| reputation_score | smallint, default 50, check 0–100 | denormalised credibility score. Written **only** by `apps/reputation/services.py` (§4a, a `bulk_update`) and repaired by `recompute_reputation`. **A full `User.save()` never writes it** (Part 11B): a save of a loaded account without `update_fields` (allauth's `set_password`, the admin form) writes every other loaded field, so it can't write back a score read earlier in the request |
| reputation_sample | int, default 0 | un-reversed own-post events counted in the score; the score is public only when ≥ 3. Same writers and the same `User.save` rule as `reputation_score` |
| emergency_blocked_until | timestamptz null | no emergency posts before this time (a block ending now is over). Written **only** by `apps/moderation/services.py`, with `.update()`, and always equal to `rules.standing_block_end` of the account's `emergency_blocked` / `emergency_unblocked` rows (§4b, Part 11C): set after a FALSE emergency or by a moderator's Block, lifted by an Unblock or by the overturn of that FALSE. **A full `User.save()` never writes it** (the Part 11B rule for the score) |
| created_at | timestamptz, indexed | |

- Google identities live in allauth's `socialaccount_socialaccount (provider, uid)`. There are no `oauth_*` columns (c-12). Its `extra_data` keeps only `sub`, `email`, `email_verified` and `hd` (Part 3): Google's name, picture and locale are never stored. `SocialApp` (the app is configured in settings) and `SocialToken` (tokens aren't stored) are unregistered from the admin; `SocialAccount` stays, to show who linked Google.
- Emails live in allauth's `account_emailaddress`.

### posts: `posts.Post`

| Field | Type | Notes |
|---|---|---|
| id | uuid PK | |
| author | FK users, CASCADE, indexed | |
| content | text, 1–500 chars (CheckConstraint) | plain text only. Counted in **code points** (`char_length`, Python `len`, the client counter), so an emoji is 1 |
| post_type | `opinion` \| `fact` | chosen explicitly by the author, immutable |
| sources | `varchar(500)[]` (`ArrayField`), default `[]`, not null | optional, fact posts only: 0–5 validated http(s) URLs or bare DOIs, in the order entered (§4c). **Never fetched.** Immutable. Checks: at most 5 elements; empty unless `post_type='fact'`; no empty and no NULL element. The kind (`url`/`doi`) is derived, not stored. The 500-character limit per element is enforced by `validators.normalize_source`, **not** by the column: Django writes `%s::varchar(500)[]` and an explicit cast truncates silently (a plain literal INSERT would raise) |
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
| report_count | int, default 0 | **lifetime** counter of every report (counting or not), updated by `posts.services.record_report` in the report-insert transaction (guide §3.2 note); never decremented |
| review_started_at | timestamptz null | when the post entered review (`routing.enter_review`; a merge into an existing review leaves it); cleared when a moderator ends the review. The queue's "waiting" column and sort. Check `posts_post_review_started_consistent`: set exactly while `status='under_review'` (Part 10) |
| escalated_at | timestamptz null | c-9. Set only on a post under review; cleared when the review ends (Part 10) |
| moderated_by | FK users SET_NULL null | last moderator to act |
| moderated_at | timestamptz null | |
| deleted_at | timestamptz null | author soft delete (D6): hidden everywhere, kept for audit |
| search_vector | `GeneratedField(SearchVector('content', config='english'), db_persist=True)` | Part 12 (migration `posts.0003`): `to_tsvector('english'::regconfig, COALESCE(content, ''))`, stored, never written by Django; GIN index `posts_search_idx` (c-31). `for_list()` defers it, so no list pulls a tsvector per post |
| created_at, updated_at | timestamptz | `created_at` has `default=timezone.now`, not `auto_now_add`: the service passes `now` and tests place posts in the past |

Indexes (Django limits an index name to 30 characters; the `author` FK has no index of its own because `(author_id, created_at DESC)` covers it):
- `(status, created_at DESC)` (`posts_status_created_idx`)
- `(author_id, created_at DESC)` (`posts_author_created_idx`; it also serves the fact-quota count)
- GIN `(search_vector)` (`posts_search_idx`, Part 12)
- partial `(is_emergency DESC, created_at) WHERE post_type='fact' AND status='pending' AND deleted_at IS NULL` (queue; emergencies first)
- partial `(review_started_at) WHERE status='under_review'` (review queue, longest wait first; `posts_review_queue_idx`, re-pointed from `created_at` in Part 10)
- partial `(emergency_expires_at) WHERE is_emergency AND emergency_demoted_at IS NULL AND deleted_at IS NULL` (pinned emergencies)
- partial `(created_at DESC, id DESC) WHERE deleted_at IS NULL AND NOT status='removed'` (`posts_recent_idx`, added in Part 4): the Recent feed lists every status except removed, which `(status, created_at)` cannot serve

The sources, emergency and `pre_removal_status` columns are created in Part 4 with the rest of the table. Their logic arrives in Parts 4/5 (sources), 11 (removal appeals) and 11C (emergency), so no later schema change is needed.

### Social graph

| Table | Fields | Constraints / indexes |
|---|---|---|
| follows | id bigint, follower FK, following FK, created_at | unique(follower, following); check follower ≠ following (`follows_pair_unique`, `follows_not_self`); two composite indexes serve the lists, newest follow first: `(following, created_at DESC, id DESC)` for a user's followers and `(follower, created_at DESC, id DESC)` for who they follow (Part 6; they replace the guide's plain `index(following)`, §3.5). Written only by `apps/social/services.py` |
| likes | id bigint, user FK, post FK, created_at | unique(user, post) (`likes_pair_unique`: prevents double-likes at the DB level, and serves "did I like this?"); index(post, created_at) (`likes_post_created_idx`; also feeds the stats in 11D). Written only by `apps/social/services.py` |
| comments | id uuid, post FK, author FK, content 1–500, is_hidden bool (moderator), deleted_at timestamptz null (the author's soft delete, Part 7), created_at | flat, no replies. Check `comments_content_length` (1–500). One **partial** index `comments_post_visible_idx` on `(post, created_at, id)` `WHERE NOT is_hidden AND deleted_at IS NULL` serves both the list and the count (it replaces the plain `(post, created_at)`; 11D's daily counts must use the same predicate); the author FK keeps its own index for account deletion and export. A hidden or deleted comment is in no list and no count. Written only by `apps/social/services.py` (and the admin's Hide/Unhide) |
| bookmarks | id bigint, user FK, post FK, created_at | `bookmarks_pair_unique` (user, post); `bookmarks_user_created_idx` (user, created_at DESC, id DESC). **Private**: never exposed to anyone but the owner (Part 7B, §4d). Written only by `apps/social/services.py` |
| reposts | id bigint, user FK, post FK, status_at_repost, created_at | `reposts_pair_unique` (user, post); `reposts_status_allowed` check: `status_at_repost` is `pending`, `published`, `verified_true` or `under_review` (the only states a post can be reposted in, §4d); `reposts_post_created_idx` (post, created_at), which also feeds the stats in 11D; `reposts_user_created_idx` (user, created_at DESC, post DESC) for a person's reposts, newest first (the profile list and the repost side of the Following feed). `created_at` defaults to `timezone.now` so tests can place reposts in time. Rules in §4d. Written only by `apps/social/services.py` |

All FKs to users and posts CASCADE.

### reports: `reports.Report` (Part 8)

| Field | Type | Notes |
|---|---|---|
| id | uuid PK | |
| post, reporter | FKs CASCADE | **`reports_pair_unique` (post, reporter)**: one per user per post **for life** (guide §6.1), so a dismissed or actioned report is not a second try. `post` has no index of its own (both composites lead with it); `reporter` keeps its index (account deletion and export) |
| reason | `inaccurate` \| `misleading` \| `harassment` \| `spam` \| `other` | labels in ANALYSIS b-5; `reports_reason_valid` |
| details | varchar(500), blank | trimmed, counted in code points; `reports_other_needs_details`: `other` needs words |
| status | `open` \| `dismissed` \| `actioned`, default open | dismissed/actioned reports stop counting; `reports_status_valid` |
| counts_toward_threshold | bool, no default | decided once, at insert (§5); the service always sets it |
| resolved_by | FK users SET_NULL null | set with `resolved_at` by Part 10 |
| resolved_at | timestamptz null | `reports_resolution_consistent`: `open` exactly while `resolved_at` is null, so a bulk Dismiss must set both |
| created_at | timestamptz, `default=timezone.now` | `reports_post_created_idx` (post, created_at) serves the windowed count (the service passes `now`; tests place reports in time) |

Written only by `apps/reports/services.py`. A report never shows its details or its reporter to anyone but moderators (§9); `__str__` and the admin list leave the text out. Deleting a reporter's account deletes their rows, but `posts.report_count` (a lifetime counter) and the post's review state stay as they were (Part 14 must not decrement it).

### moderation_actions (audit trail, append-only)

`moderation.ModerationAction` (Part 10; table `moderation_moderationaction`).

| Field | Type | Notes |
|---|---|---|
| id | uuid PK | |
| post | FK SET_NULL null, `related_name="moderation_actions"` | null for account-level actions, and after the post is deleted (the snapshot stays). No FK index of its own: `modaction_post_created_idx` leads with it |
| subject_user | FK users SET_NULL null | the account acted on (emergency block, photo removal/block) |
| post_snapshot | text | copy of content at action time (so the log survives deletion) |
| moderator | FK users SET_NULL null | |
| action | `verified` \| `marked_false` \| `dismissed_report` \| `removed` \| `escalated` \| `restored` \| `kept_removed` \| `emergency_demoted` \| `emergency_blocked` \| `emergency_unblocked` \| `avatar_removed` \| `avatar_blocked` \| `avatar_unblocked` | guide §3.4 plus the D5 features. Part 10 created ten kinds; **Part 11 added `kept_removed`** ("Keep removed" had no kind; migration `moderation.0003` widened `moderation_action_valid`, and it can't be reversed once such a row exists); **Part 11C added `emergency_unblocked`** (an Unblock, or the automatic lift when a FALSE label is overturned; migration `moderation.0006`, the same caveat). **Part 14B added `avatar_unblocked`** ("Allow photo uploads" had no kind; migration `moderation.0008`, the same caveat). Part 10 writes the first five, Part 11 `restored` and `kept_removed`, Part 11C the three `emergency_*`, Part 14B the three `avatar_*` (no post, `subject_user` set; Block photo uploads on an account with a photo writes `avatar_removed` and then `avatar_blocked`, 1 µs apart) |
| from_status, to_status | status enum, null | "what it was before" (null for account-level actions, the block and unblock rows included; `emergency_demoted` has from = to); database checks `moderation_action_from_status_valid` / `…_to_status_valid` |
| blocked_until | timestamptz null | Part 11C: the end of an `emergency_blocked` row's block (its time + `emergency_false_cooldown_days`). Check `moderation_action_blocked_until_kind`: set **iff** `action='emergency_blocked'` |
| public_note | varchar(500), blank | **what the author may be shown** (user decision 2026-10-11): the verdict note of Mark verified / Mark FALSE (also copied to `Post.verdict_note`) and the "reason shown to the author" of Remove (never copied to `Post.verdict_note`, so Part 11's Restore needs no undo). Part 11 shows the author the `public_note` of the post's latest `removed` row |
| appeal | FK `moderation.Appeal` SET_NULL null, `related_name="moderation_actions"` | **Part 11:** set on the row of the action that **resolves** an appeal (Mark verified, Mark FALSE or Remove on a label appeal; Restore; Keep removed), never on Escalate |
| notes | text | internal rationale (moderators only) |
| created_at | timestamptz, `default=timezone.now` | taken once the post's row lock is held, so the log's order is the order things happened |

- Indexes: `modaction_post_created_idx` `(post, created_at DESC)` for the history on a post's page, and `modaction_created_idx` `(created_at DESC)` for the log.
- **Append-only in code:** `save()` of an existing row and `delete()` raise. Deleting a post or an account only nulls the link (the collector's `SET_NULL` is an `UPDATE` that calls neither).
- Written only by `apps/moderation/services.py`.
- **An account's block and unblock rows** (Part 11C) carry `subject_user`; an automatic one also carries the post (P's FALSE, or its overturn), a manual one none. They are **strictly increasing in time per account** (`max(now, the account's last block row + 1 µs)`, written under the account's lock, the ledger's rule): otherwise an Unblock that committed first but stamped a later time than a waiting Mark FALSE would read the new block as already lifted. A post-linked row loses its post only through a hard delete of the post, which happens only with the account's deletion, so a row with no post is a manual one.
- **Permission** (Part 11C): `moderation.block_emergency_posting` ("Can block or unblock emergency posting", `ModerationAction.Meta.permissions`), granted to the Moderators group by migration `moderation.0007` (§8).
- **Permission** (Part 14B): `moderation.moderate_profile_photos` ("Can remove profile photos and block or allow photo uploads"), granted with `accounts.view_avatar` to the Moderators group by migration `moderation.0009` (§8).

Admin: read-only for everyone. The full list (`ModerationActionAdmin`, with the account acted on and a search by its username since Part 11C) is for senior moderators and superusers (`moderation.view_moderationaction`); a moderator sees only a post's own history, as an inline on its page (guide §8.2, user decision 2026-10-11), and an account's emergency blocks on the account's page (§8). Account and settings changes have no `moderation_actions` kind and are written to Django's own admin log with their values (§8).

### appeals: `moderation.Appeal` (c-7; Part 11; table `moderation_appeal`)

| Field | Type | Notes |
|---|---|---|
| id | uuid PK | |
| post | `OneToOneField(Post, CASCADE, related_name="appeal")` | the "FK CASCADE, unique" of this table in Django's idiom (a unique `ForeignKey` is warning W342): **at most one appeal per post for life**, whatever became of it |
| author | FK users CASCADE, `related_name="appeals"` | must be the post's author (the service checks it); its index serves account deletion and export |
| kind | `label` \| `removal` | `appeals_kind_valid`; `label` for a FALSE label, `removal` for a removed post (ANALYSIS f-2) |
| reason | varchar(500), blank | the author's words, trimmed, counted in code points; `__str__` leaves them out |
| status | `open` \| `upheld` \| `overturned`, default `open` | `appeals_status_valid`; upheld = the original decision stands |
| original_moderator | FK users SET_NULL null, `related_name="+"` | who made the call being appealed, set by `file_appeal` (below); null = any moderator may decide |
| resolved_by | FK users SET_NULL null, `related_name="+"` | |
| resolved_at | timestamptz null | `appeals_resolution_consistent`: `open` exactly while null (the resolving write sets `status`, `resolved_by` and `resolved_at` together) |
| created_at | timestamptz, `default=timezone.now` | the service passes `now` |

Written only by `apps/moderation/services.py` (`file_appeal`, and the five actions that resolve one); a row changes once, from `open` to `upheld` or `overturned`, and goes only with its post or account (CASCADE). **`original_moderator`:** for a *label* appeal, the moderator of the post's latest `marked_false` row **when `verdict_source=moderator`**, null for a pipeline FALSE (not `post.moderated_by`: a later Dismiss of reports on the FALSE post would make the dismisser look like the labeller); for a *removal* appeal, the moderator of the post's latest `removed` row. Two moderators who each marked a post FALSE over time: only the latest counts. Migrations `moderation.0003_appeal` (the model, the `appeal` link, the `kept_removed` kind) and `0004_appeal_permission` (`moderation.view_appeal` for moderators; its reverse returns to Part 10's lists, not to nothing).

### notifications: `notifications.Notification` (guide §11; Part 13)

Table `notifications_notification`. Written only by `apps/notifications/services.py`, called explicitly (no signals) from the write services **inside their transaction**.

| Field | Type | Notes |
|---|---|---|
| id | uuid PK | |
| recipient | FK users CASCADE, `related_name="notifications"` | no FK index of its own: `notifications_list_idx` leads with it |
| actor | FK users SET_NULL null, `related_name="+"` | null for the five moderation types. An actor's account deletion **deletes** the items it caused (Part 14: `notifications.services.discard_for_actor`, first in `accounts.deletion.delete_account`), so "Someone liked your post" is never left behind; the SET_NULL stays as the database backstop |
| type | `follow` \| `like` \| `comment` \| `repost` \| `verdict` \| `under_review` \| `removed` \| `emergency_demoted` \| `appeal_resolved` | nine, no tenth |
| post | FK posts CASCADE null | |
| comment | FK comments CASCADE null | |
| outcome | varchar(12), blank | **Part 13's addition:** `verdict` → `true` / `false`, `appeal_resolved` → `upheld` / `overturned`, everything else blank. Stored so an old item can't change meaning when the post is labelled again |
| is_read | bool, default false | |
| created_at | timestamptz, `default=timezone.now` | the service passes `now`; one action's items are stamped 1 µs apart (verdict or removal, then `emergency_demoted`, then `appeal_resolved`) so their order is stable |

- **Named checks:** `notifications_type_valid`; `notifications_outcome_valid` (per type); `notifications_shape_valid` (`follow`: no post, no comment; `comment`: both; the other seven: a post and no comment); `notifications_not_self` (`actor <> recipient`; a null actor passes). No check requires an actor (SET_NULL would break it).
- **Indexes:** `notifications_list_idx` `(recipient, -created_at, -id)` for the list; partial `notifications_unread_idx` `(recipient) WHERE is_read = false` for the count (the count query must filter `is_read=False`, the index's own predicate; an `EXPLAIN` test pins it); partial `notifications_post_idx`, `notifications_comment_idx` and `notifications_actor_idx` (`WHERE … IS NOT NULL`) serve the cleanups and an account deletion's SET_NULL.
- **Dedupe is permanent and enforced by the database:** partial unique indexes `notifications_post_event_unique` `(recipient, actor, type, post) WHERE type IN (like, repost)` (**the type is in the key**: a like and a repost of one post by one person are two items) and `notifications_follow_unique` `(recipient, actor) WHERE type = follow`. `notify()` writes with `bulk_create([item], ignore_conflicts=True)` (`ON CONFLICT DO NOTHING`; CHECK violations still raise), so like → unlike → like gives one item and two simultaneous requests give one. An item is a record, not a live state: it stays after an unlike or an unfollow.
- No self-notifications (`notify()` drops `actor == recipient`; the table refuses it too). Comments, verdicts, reviews, removals and appeals are one item per event.
- **Items go with what they are about:** `delete_post` deletes the post's items, `delete_comment` and the admin's Hide delete the comment's (all in the same transaction as the change; Unhide doesn't bring one back); the list also filters `post.deleted_at IS NULL`.
- Migration `notifications.0001_initial` (depends on `posts.0003`, `social.0003`).

### reputation_events: `reputation.ReputationEvent` (append-only ledger, Part 11B)

Table `reputation_reputationevent`.

| Field | Type | Notes |
|---|---|---|
| id | uuid PK | |
| user | FK users CASCADE, `related_name="reputation_events"` | whose score changes. No FK index of its own: `repevent_user_created_idx` leads with it |
| kind | `fact_true` \| `fact_false` \| `emergency_false` \| `post_removed` \| `repost_true` \| `repost_false` \| `repost_emergency_false` \| `repost_removed` \| `report_upheld` \| `reversal` | `EventKind` with plain-language labels ("Fact labelled FALSE", "Repost of a fact verified true", "Report upheld by a moderator", …); weights in §4a; check `reputation_event_kind_valid` |
| positive, negative | numeric(6,2) | the event's P and N weights; a `reversal` row carries the negated values of the row it cancels. Check `reputation_event_weights_sign`: a reversal has both ≤ 0, every other row both ≥ 0 |
| post | FK posts SET_NULL null, `related_name="reputation_events"`, indexed | the post the event is about (`settle_post` reads a post's rows by it) |
| moderation_action | FK moderation_actions SET_NULL null, no index | the moderator action that caused it (the Mark FALSE or Remove that earned a `report_upheld`, the Restore that reversed a removal); null for the pipeline |
| reverses | `OneToOneField(self, CASCADE, null, related_name="reversed_by")` | set only on `reversal` rows (check `reputation_event_reverses_iff_reversal`); the unique index means a row is reversed at most once |
| score_after | smallint, check 0–100 | the user's score right after this row (drives 11D's trend) |
| created_at | timestamptz, `default=timezone.now` | **strictly increasing per user**: the service writes `max(now, the user's last row + 1 µs)`, so a writer whose `now` is older (it waited for a lock) still comes after the row it waited for, and 11D's "last `score_after` of each day" and the cursor never see ties |

- Index `repevent_user_created_idx (user, created_at)` serves the totals, the reporter cap, both endpoints and the trend.
- **Append-only in code:** `save()` of an existing row and `delete()` raise (as `ModerationAction`). Rows go only with their account (CASCADE, through the collector). A post's hard delete only nulls the link: `SET_NULL` is a queryset `UPDATE`, which calls neither method, so "never updated" has that one exception. A post's soft delete (D6) changes nothing.
- Written only by `apps/reputation/services.py`. Admin is read-only (§8).

### avatars: `accounts.Avatar` (Part 14B)

| Field | Type | Notes |
|---|---|---|
| user | OneToOne users, **PK**, CASCADE | one photo per account |
| image_256, image_96 | bytea | re-encoded WebP only (§4e); never the original upload |
| version | varchar(16) | first 16 hex characters of the SHA-256 of `image_256`; copied into `users.avatar_version` |
| bytes_total | int | for the storage budget (§13) |
| created_at, updated_at | timestamptz | |

A separate table keeps image bytes out of every `users` query. **As built (Part 14B, migration `accounts.0003_avatar`):** `Avatar` is the model's name, Django Admin calls it "profile photo" (`verbose_name`, no schema effect); checks `avatars_version_format` (16 lowercase hex characters) and `avatars_bytes_total_positive`; `created_at` is when the account first had a photo and survives a replacement, `updated_at` moves. Written **only** by `apps/accounts/avatars.py`, which is also the only code that sets `users.avatar_version`; the row goes with its account (CASCADE) and the `avatar_*` audit rows stay with `subject_user` nulled. Nothing here can hold the original upload: there is no column for it.

### platform_settings (singleton, id=1) (c-13)

- Fields: `report_threshold`, `report_window_hours`, `report_min_account_age_hours`, `confidence_threshold`, `fact_posts_per_day`, the six emergency limits (`emergency_duration_hours`, `emergency_posts_per_day`, `emergency_min_account_age_days`, `emergency_min_reputation`, `emergency_report_threshold`, `emergency_false_cooldown_days`; §3), `updated_by`, `updated_at`. All are created in Part 0A.
- Seeded from env defaults by a data migration (a missing or empty variable falls back to its default; an invalid or out-of-range one stops startup, naming the variable).
- Every field is a `PositiveSmallIntegerField` with a DB `CheckConstraint`: ≥ 1 for `report_threshold`, `report_window_hours`, `emergency_duration_hours` and `emergency_report_threshold`; 0–100 for `confidence_threshold` and `emergency_min_reputation`; ≥ 0 for the rest (a per-day value of 0 works as a kill switch). `id` is fixed at 1 by a check.
- Editable **only by senior moderators** in Django Admin (`core.change_platformsettings`; a moderator holds `view_platformsettings` and gets the page read-only). Added only when the row is missing.
- Read through a 60 s cache (`apps.core.services.get_platform_settings()`; a save clears it now and again on commit); every change is logged with old → new values ("Report threshold: 5 → 3; Confidence threshold: 85 → 90.") in Django's admin log, on the object's History page (Part 10).

## 3. Configuration values

| Name | Default | Env var | Editable in admin |
|---|---|---|---|
| Report threshold | 5 | `REPORT_THRESHOLD` | ✅ seniors |
| Report window (hours) | 24 | `REPORT_WINDOW_HOURS` | ✅ |
| Min account age for a report to count (hours) | 24 | `REPORT_MIN_ACCOUNT_AGE_HOURS` | ✅ |
| Confidence threshold (0–100) | 85 | `CONFIDENCE_THRESHOLD` | ✅ |
| Fact posts per user per **rolling 24 hours** (deleted and removed ones count) | 10 | `FACT_POSTS_PER_DAY` | ✅ (0 pauses fact posts) |
| Emergency duration (hours) | 24 | `EMERGENCY_DURATION_HOURS` | ✅ (applies to new emergencies; the expiry is stored at creation) |
| Emergency posts per user per 24 h (they also count as fact posts) | 1 | `EMERGENCY_POSTS_PER_DAY` | ✅ |
| Min account age for emergency posts (days) | 7 | `EMERGENCY_MIN_ACCOUNT_AGE_DAYS` | ✅ |
| Min credibility score for emergency posts | 40 | `EMERGENCY_MIN_REPUTATION` | ✅ |
| Report threshold while an emergency is active | 2 | `EMERGENCY_REPORT_THRESHOLD` | ✅ |
| Emergency ban after a FALSE emergency (days) | 30 | `EMERGENCY_FALSE_COOLDOWN_DAYS` | ✅ |
| Pinned emergencies shown per feed | 3 (+ "Show all") | code (`apps/posts/pinned.py` `PINNED_SHOWN`) | — |
| Credibility: start / prior weight / public after | 50 / 10 imaginary events / 3 counted events; the score is rounded **half up** (Part 11B) | code (`apps/reputation/scoring.py`: `START_SCORE`, `PUBLIC_AFTER`) | — |
| Credibility: reporter credit cap | 4 un-reversed `report_upheld` credits per rolling 30 days (one exactly 30 days old no longer counts); at the cap no row is written | code (`REPORT_CREDIT_CAP`, `REPORT_CREDIT_WINDOW`) | — |
| Sources per fact post | 5 | code (+ DB check) | — |
| Source max length | 500 chars each | code (+ column type) | — |
| Profile photo limits | server: ≤ 5 MB, ≤ 25 MP (**WebP ≤ 12 MP**: Pillow 13 decodes it at about 16 bytes a pixel), ≥ 128×128 px; stored as WebP 256 + 96 px; **one decode at a time site-wide** (Postgres advisory lock, 10 s wait, then 503 `photo_busy`). The browser accepts originals up to **20 MB** and shrinks them first (§4e) | code (`apps/accounts/avatars.py`) | — |
| Following-feed cache TTL (s), first page only (Part 6) | 30 | `FEED_CACHE_SECONDS` (0 to 300; **0 turns the cache off**). Read by Django settings, **not** a PlatformSettings value | — |
| Access / refresh token lifetime | 15 min / 14 days | `JWT_ACCESS_TOKEN_MINUTES` / `JWT_REFRESH_TOKEN_DAYS` | — |
| Email-confirmation link validity | 1 day | code (`ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS`) | — |
| Pipeline: batch size / max attempts / timeout | 10 / 5 / 20 s for the whole call (10 s per socket operation) | code constants (`processor.BATCH_SIZE`, `routing.MAX_ATTEMPTS`, `clients.TIMEOUT_SECONDS`) | — |
| Pipeline retry backoff | 2^attempts min, cap 60 min; a try is counted when it is claimed (Part 9) | code (`routing.backoff`) | — |
| Pipeline lease / tick budget / kick threads | 5 min / 25 s (the tick takes its first post always, another only if the worst case still fits) / at most 4 per process (Part 9) | code (`processor.LEASE`, `core.views.TICK_BUDGET_SECONDS`, `processor.MAX_KICK_THREADS`) | — |
| Post / comment / appeal text max | 500 chars | code | — |
| Bio / display name max | 280 / 50 | code | — |
| Page size | 20 (max 50) | code | — |
| Notification poll | 30 s, visible tab only (`NOTIFICATION_POLL_MS` in `features/notifications/UnreadCountProvider.tsx`); the first answer after mount or after a hidden tab comes at once | frontend constant | — |
| Pending-status poll | 10 s → back off to 60 s, stop after 10 min | frontend constant | — |

DRF throttles (per user, Redis-backed; scope → rate; `username_check`, `status_poll` and `search` are per client IP; seventeen scopes since Part 14):
- `post_create` 30/h
- `comment` 60/h (Part 7): `POST …/comments/` only; reading and deleting never count, and a 401, 403 or 404 doesn't either (a 400 does)
- `like` 300/h (Part 7): `POST` and `DELETE …/like/` share it, per user; a 401 or 403 doesn't count
- `follow` 100/h (Part 6): `POST` and `DELETE …/follow/` share it, per user; a 401 or 403 doesn't count
- `report` **10/h** (guide §6.3; Part 8): `POST …/report/` only. A 401 or `email_unverified` never counts; from the throttle on, every answer does (a 400, a 404, a 403 `cannot_report_own` or a 409 included, as for a repost's 409)
- `appeal` 5/day
- `repost` 100/h (Part 7B): `POST` and `DELETE …/repost/` share it, per user; a 401 or 403 doesn't count, a 409 does
- `bookmark` 300/h (Part 7B): `POST` and `DELETE …/bookmark/` share it, per user; separate from `like`
- `avatar_upload` 5/day (Part 14B): `PUT /me/avatar/` only, per signed-in person. A 401 or 403 (`email_unverified`, `photo_uploads_blocked`) never counts, since permissions run before throttles; a photo refused with a 400 does. `DELETE` has no throttle
- `username_check` 30/min per IP
- `status_poll` **120/min per IP** (Part 5; user decision 2026-10-09): `GET /api/v1/posts/status/`, the public endpoint the badge poller calls (up to 50 ids, one query, uncached). One tab polling at its fastest makes 6 a minute, so 120 covers about 20 tabs behind one address. It never authenticates, so it counts by client IP only, and reading the feed or a post doesn't touch it.
- `search` **60/min per IP** (Part 12; user decision 2026-10-20): `GET /api/v1/search/`. It counts by client IP **also for signed-in users** (`apps.core.throttles.IPScopedRateThrottle`; DRF's `ScopedRateThrottle` would key on the user), so accounts don't multiply the allowance. Authentication and permissions run first, so a 401 never counts; a 400 or 405 does.
- `notifications` **120/min per user** (Part 13): `GET /api/v1/notifications/`, `GET …/unread-count/` and `POST …/mark-read/` share it (`ScopedRateThrottle`, keyed by the signed-in user). One visible tab polls the count twice a minute, so 120 leaves room for several tabs and for reading the list. Authentication runs first, so a 401 never counts.
- `profile_update` 30/h, `password_change` 10/h, `data_export` 10/h and `account_delete` 10/h (Part 14; user decision 2026-10-20): all per signed-in user (`ScopedRateThrottle`). `MeView` picks the scope by method (`PATCH` → `profile_update`, `DELETE` → `account_delete`, `GET` none), so reading `/me` never uses them up. A 401 or 403 never counts, a 400 does: an Argon2 hash costs about 100 MiB, so the wrong-password paths of the password change and the deletion stay throttled.

The emergency limit (1 per 24 h) is a service rule checked against the DB, not a throttle.

**Fact quota (Part 4; user decision 2026-10-08):** a rolling window, not a calendar day. `posts.services.fact_quota()` counts the author's fact posts with `created_at > now − 24 h`, **including ones deleted or removed later** (otherwise deleting and reposting would get around it); a post exactly 24 h old no longer counts. Opinions and other people's posts don't count. `create_post` locks the author's `users` row before counting (`SELECT … FOR NO KEY UPDATE` since Part 11C, Part 11B's rule for every user lock: it still serialises two posts, a block and the ledger, but not the `KEY SHARE` every insert pointing at the author takes at commit), so two simultaneous fact posts at 9/10 let exactly one through. The same lock returns the author's fresh row, which the emergency rules read (§4b). `fact_quota()` also returns the times of the window's emergencies (`emergency_times`, in the same one query). Refusals: **429 `fact_quota_exceeded`** with `Retry-After` (seconds until a slot frees; the answer tells it apart from the throttle's 429 `throttled`), and **403 `fact_posts_paused`** when the limit is 0. `next_slot_at` is the `(used − limit + 1)`-th oldest counted post plus 24 h, which is right even after the limit is lowered.

**`post_create` applies to `POST /api/v1/posts/` only.** DRF runs throttles on every method, so the view picks permissions and throttles by method (`get_permissions`, `get_throttles`): reading the feed never uses up the posting allowance. The check order is authentication → permissions (401/403) → throttle (429 `throttled`) → validation (400) → service (400/403/429), so a 401 or 403 never counts against the 30/h, but a 400 or a quota refusal does.

Auth endpoints use allauth's `ACCOUNT_RATE_LIMITS`, keyed on `REMOTE_ADDR` (the real client IP from `ClientIPMiddleware`). Part 1 pins allauth 65.19.5's defaults:
- `login` 30/min per IP (every login POST);
- `login_failed` 10/min per IP **and** 5 per 300 s per account (key `host:email`, lowercased). It is counted *before* the password is checked, so a full IP bucket refuses even the right password; a success gives its own count back. The answer is **400 `too_many_login_attempts`**, not 429.
- `signup` 20/min per IP → 429. Failed and unavailable Turnstile checks count too (§7).
- **Part 2 email limits** (user decisions 2026-10-06):
  - `confirm_email` **1 per 60 s per address**: the resend cooldown, matching the countdown in the UI (allauth's default is 3 min). It is allauth's own action, so the sign-up email counts too.
  - `confirm_email_daily` **10 per day per address**: resends only (the sign-up email doesn't count). Consumed by `resend_verification_email()` after a send, checked in dry-run first.
  - `reset_password` 20/min per IP **and** 5/min per address (allauth's defaults, now pinned) → 429.
  - `reset_password_daily` **50 per day per IP and 10 per day per address**: checked by `AuthApiMiddleware` in dry-run before allauth runs and consumed only after a 200, so a 400 or a refused request never counts. The address is the lowercased, trimmed email, as allauth keys it.
  - `reset_password_from_key` 20/min per IP (pinned): the reset POST.
- **Part 3:** `auth/provider/token` ("Continue with Google") has no limit of its own in allauth, and every call fetches Google's certificates. `AuthApiMiddleware` consumes allauth's **`login`** bucket (30/min per IP, shared with password logins) for every attempt, valid or not, before anything else is checked, and answers **429** `{"status":429}` when it is full (§7).
  - **Never repeat a "per" type inside one action.** allauth keeps one history list per action and "per" type (`core/internal/ratelimit.py`, `get_cache_key`), so `"1/60s/key,10/1d/key"` shares one list and the minute rate prunes the entries the day rate needs (a simulation let 20 of 20 resends through). Daily caps are therefore separate actions (`*_daily`).
  - The verification email itself is skipped silently when the cooldown is hit (allauth's link mode); our resend view reports it as 429 `verification_email_throttled` with no `Retry-After`, because the full bucket may be the minute one or the day one.

## 4. Post status lifecycle and routing (guide §5, §6, §7; fixes c-1…c-7)

### Events → transitions

| Current status | Event | New status | Other effects |
|---|---|---|---|
| (new) | author creates **opinion** | `published` | never enters the pipeline |
| (new) | author creates **fact** | `pending` | visible now with "Checking facts…" (guide §5.2); inline kick queued on commit. With `is_emergency`: eligibility checked first (§4b), `emergency_expires_at` stored |
| `pending` | pipeline result, verdict `true`/`false` **and** confidence ≥ threshold | `verified_true` / `verified_false` | `verdict_source=pipeline`; notify author (`verdict`) |
| `pending` | pipeline result, `inconclusive` **or** confidence < threshold | `under_review` | `flagged_reason=pipeline`, `pre_review_status=pending`; notify (`under_review`) |
| `pending` | pipeline failed `max_attempts` times | `under_review` | `flagged_reason=pipeline`; error kept in `pipeline_result` |
| `under_review` (reports, not yet checked: `pre_review_status=pending`) | pipeline failed `max_attempts` times | unchanged | `flagged_reason=both`; error kept (Part 9: reported pending facts are still checked) |
| `pending` / `published` / `verified_*` | report threshold crossed | `under_review` | `flagged_reason=reports`, `pre_review_status=<old>`; notify author |
| `under_review` | report threshold crossed | unchanged | `pipeline`→`both`; `reports`/`both`/`appeal` unchanged |
| `under_review` (reports, pipeline result arrives late) | decisive **TRUE** | unchanged | store result; `pre_review_status=verified_true`, `verdict_source=pipeline` (Dismiss restores VERIFIED; the source stays private meanwhile, §9) |
| `under_review` (reports, pipeline result arrives late) | decisive **FALSE** | unchanged | store result; `flagged_reason=both`, `pre_review_status` stays `pending`: a moderator decides (user decision 2026-10-11, Part 9: no hidden FALSE is ever stored, so nothing can reveal it and Dismiss can't make a post FALSE without a human) |
| `under_review` (reports, pipeline result arrives late) | low / inconclusive result | unchanged | `flagged_reason=both` |
| `pending` (**active emergency**) | pipeline result FALSE, confidence ≥ threshold | `under_review` | treated as not decisive: `flagged_reason=pipeline`, `pre_review_status=pending`; top of the admin queue; the post keeps its priority (§4b) |
| `under_review` (reports, **active emergency**, late result) | pipeline result FALSE, confidence ≥ threshold | unchanged | treated as not decisive: `flagged_reason=both` (no `pre_review_status=verified_false`, so dismissing reports can't make it FALSE without a human). Since Part 9 this is the rule for every post, so 11C adds nothing here |
| `pending` / `published` / `verified_*` (**active emergency**) | **emergency** report threshold (2) crossed | `under_review` | as for the normal threshold; priority kept |
| `under_review` | moderator **Mark verified** (fact only) | `verified_true` | `verdict_source=moderator`, `verdict_note` = the public note (blank clears it), `flagged_reason`, `pre_review_status`, `review_started_at` and `escalated_at` cleared, open reports→`actioned`; log action (Part 10); notify. An emergency keeps its priority. |
| `under_review` | moderator **Mark FALSE** (fact only) | `verified_false` | same as above. On an **active** emergency also `emergency_demoted_at=now` and a second row `emergency_demoted` (1 µs later). On **any** emergency whose label this changes (the ledger's new `emergency_false` row; not an upheld label appeal or a post already FALSE), the author is blocked: a row `emergency_blocked` (post P, `blocked_until` = its time + `emergency_false_cooldown_days`, nothing at 0 days) and `emergency_blocked_until` recomputed. Part 13 notifies `emergency_demoted` |
| `under_review` | moderator **Dismiss reports** | `pre_review_status` if flag was `reports` (the review fields are cleared as above); stays `under_review` with `flagged_reason=pipeline` if flag was `both` (the status it came from, the wait and any escalation are kept) | open reports→`dismissed`; log. Refused with no `reports` in the flag, or when `pre_review_status` isn't a status the post could return to (`no_prior_status`) |
| any except `removed` | moderator **Remove** | `removed` | `pre_removal_status` = the old status (its `pre_review_status` if it was `under_review`); the review fields are cleared; reports→`actioned`; log with the optional "reason shown to the author" (`public_note`); `Post.verdict_note` is not touched; notify (`removed`) |
| `under_review` | moderator **Escalate** | unchanged | `escalated_at=now`; log. Only on a post under review (Part 10; Part 11 adds removed posts with an open removal appeal), and not twice. It never locks the post: any moderator can still act |
| any (**active emergency**) | moderator **Demote emergency** | unchanged | `emergency_demoted_at=now`; log `emergency_demoted` (from = to = the status); no reports or appeal touched; refused (`not_active_emergency`) on anything else; Part 13 notifies `emergency_demoted` |
| `under_review` (label appeal on a FALSE **emergency**) | moderator **Mark verified** (overturned) | `verified_true` | as the appeal row above; the ledger reverses the `emergency_false` row, so the block that FALSE brought is lifted: a row `emergency_unblocked` (post P, the moderator) and the column recomputed (another standing block, manual or another FALSE emergency, keeps the account blocked). A Restore reverses only the removal's rows and lifts nothing (Part 11C) |
| `pending` (emergency, **expired or demoted**) | pipeline result FALSE, confidence ≥ threshold | `verified_false` | as any decisive FALSE, and the author is blocked as for a moderator's FALSE (a row with no moderator; Part 11C) |
| `verified_false` (author, no prior appeal) | author **appeals** (label) | `under_review` | `flagged_reason=appeal`, `pre_review_status=verified_false`, `review_started_at=now` (through `routing.enter_review`); appeal `open`, kind `label`. A FALSE post that reports sent to review is `under_review`, so it can't be appealed until that review ends |
| `under_review` (appeal) | Mark verified | `verified_true` | appeal `overturned`; notify `appeal_resolved` |
| `under_review` (appeal) | Mark FALSE | `verified_false` | appeal `upheld`; notify `appeal_resolved` |
| `under_review` (label appeal) | moderator **Remove** | `removed` | appeal `upheld`, linked to the `removed` row (user decision 2026-10-13); the different-moderator rule applies |
| `removed` (author, no prior appeal) | author **appeals** (removal) | unchanged (stays hidden) | `flagged_reason=appeal` only (`review_started_at` stays null, so the Part 10 check holds); appeal `open`, kind `removal`; listed in the admin queue next to the posts under review and under the `appeal` filter |
| `removed` (removal appeal) | moderator **Restore post** | `pre_removal_status` (a fact that was `pending` and that the pipeline has already had its say on goes **`under_review`** instead: `flagged_reason=pipeline`, `pre_review_status=pending`, the clock starts now, a moderator gives the label; user decision 2026-10-13) | `flagged_reason=null`, `pre_removal_status` and `escalated_at` cleared; the label, its source and every `pipeline_*` field stay; appeal `overturned`; log `restored`; a post back to `pending` is kicked after the commit like a new fact; notify `appeal_resolved` |
| `removed` (removal appeal) | moderator **Keep removed** | unchanged | `flagged_reason` and `escalated_at` cleared; appeal `upheld`; log `kept_removed`; notify `appeal_resolved` |
| `removed` | any pipeline or report event | unchanged | ignored |
| any | author deletes (`DELETE /api/v1/posts/{id}/`, Part 5) | unchanged | `deleted_at=now` (the row stays for audit and the admin); hidden from every list and detail view (404, the author included); still counts toward the fact quota; a second delete is 404; only the author (403 `not_author`) |

Also:
- A pipeline result is **ignored** when `verdict_source=moderator` (humans win). More precisely (Part 9), a result or a failure is applied only while the post is **awaiting a check** (`routing.is_awaiting_check`, the same rule as the queue's `awaiting_check_q`): a fact, not deleted, with no `verdict_source`, that is `pending` or under review **for reports only** with `pre_review_status=pending`. Anything else (removed, decided by a moderator, already checked) is ignored and nothing is written, `updated_at` included. A result for a post the author deleted meanwhile, or for a try whose lease a newer claim took over, is dropped (§6).
- An appeal must be resolved by a moderator other than `original_moderator` unless the resolver is a senior moderator or a superuser (`APPEAL_REQUIRE_DIFFERENT_MODERATOR`, a constant in `rules.py`). It applies to every action that resolves an appeal (a verdict or Remove on a label appeal, Restore, Keep removed) and **not** to Escalate, which is what the first moderator should do. The refusal is `original_moderator` ("you made the first decision"). A decided appeal is never reopened.
- **Restore post** and **Keep removed** take internal notes only (user decision 2026-10-13): the author is told the outcome in plain words and sees the original removal reason (the `public_note` of the post's latest `removed` row, the `removal_reason` key of §9).
- Opinions: moderators can only Dismiss, Remove or Escalate (no verdict).
- **Who may act on what (Part 10, `apps/moderation/rules.py`):** nobody acts on **their own post, except a superuser**, and every action refuses a post its author **deleted**. Each refusal has a code (`deleted`, `own_post`, `opinion`, `not_under_review`, `no_reports`, `no_prior_status`, `already_removed`, `already_escalated`; Part 11 adds `no_removal_appeal` and `original_moderator`) and a short text; a mixed selection changes what it can and lists the rest as skipped. The services re-check under the row lock.
- **Leaving review** (Mark verified/FALSE, Dismiss back to the old status, Remove) clears `flagged_reason`, `pre_review_status`, `review_started_at` and `escalated_at`, so a later review doesn't look old or escalated (the `escalated` row stays in the log). **No moderator action touches `pipeline_*`** (`pipeline_attempts` is Part 9's claim token) or `confidence_score`.
- "Active emergency" is always computed at read time from the stored columns (`is_active_emergency`, below). No job ever flips a flag.
- Every verdict, removal, restore and appeal outcome also calls the reputation service in the same transaction (§4a, Part 11B): `moderation.services._perform` calls `reputation.services.settle_post` after its audit row for **every action but Escalate** (Dismiss can make a late TRUE public; Keep removed finds nothing to do), and `posts.services.record_pipeline_result` calls it only when the outcome is `labelled` (a result held for a review records nothing, so a late TRUE stays private). `file_appeal`, `record_report`, `delete_post`, `repost` and `unrepost` never touch the ledger. `reports.services.resolve_open_reports` returns the reporters it resolved, for the credit.

### Routing: pure functions in `apps/pipeline/routing.py` (no I/O, exhaustively unit-tested)

```python
def merge_flag(existing, new):                      # None+x=x; x+x=x; pipeline+reports=both;
    ...                                             # appeal stays appeal; both stays both

def enter_review(post, reason, now):
    if post.status == UNDER_REVIEW:
        post.flagged_reason = merge_flag(post.flagged_reason, reason)      # the wait is not restarted
    else:
        post.pre_review_status, post.status, post.flagged_reason = post.status, UNDER_REVIEW, reason
        post.review_started_at = now                                       # Part 10: the queue's clock

def is_active_emergency(post, now):                 # read-time only; no scheduler (§4b). Defined in apps/posts/emergency.py
                                                    # (Part 4, where the serializer reads it) and imported here (Part 11C);
                                                    # active_emergency_q(now) is the same rule as a query (tested on every state)
    return (post.is_emergency and post.emergency_demoted_at is None and now < post.emergency_expires_at
            and post.status != REMOVED and post.deleted_at is None)

def is_awaiting_check(post):                        # = awaiting_check_q(), the queue's Q (Part 9)
    return (post.post_type == FACT and post.deleted_at is None and post.verdict_source is None
            and (post.status == PENDING
                 or (post.status == UNDER_REVIEW and post.flagged_reason == REPORTS
                     and post.pre_review_status == PENDING)))

def apply_pipeline_result(post, result, cfg, now):  # posts.services writes it, row locked (§6)
    if not is_awaiting_check(post):
        return IGNORED                              # humans, removals and finished checks win
    post.pipeline_verdict, post.confidence_score, post.pipeline_result = result.verdict, result.confidence_score, result.raw_result
    post.pipeline_checked_at, post.pipeline_next_attempt_at = now, None
    decisive = result.verdict in (TRUE, FALSE) and result.confidence_score >= cfg.confidence_threshold
    decisive = decisive and not (result.verdict == FALSE and is_active_emergency(post, now))   # Part 11C
    if post.status == PENDING:
        if decisive: post.status, post.verdict_source = label(result), PIPELINE      # LABELLED
        else:        enter_review(post, PIPELINE)                                   # ENTERED_REVIEW
    else:                                           # under review for reports: a late result
        if decisive and result.verdict == TRUE:
            post.pre_review_status, post.verdict_source = VERIFIED_TRUE, PIPELINE    # Dismiss restores it
        else:                                       # a late FALSE goes to a human (decision 2026-10-11)
            post.flagged_reason = merge_flag(post.flagged_reason, PIPELINE)        # → both

def apply_pipeline_failure(post, error, now):       # the same guard; attempts were counted at claim
    post.pipeline_result = {"error": error.kind, "detail": error.detail, "attempt": post.pipeline_attempts}
    if post.pipeline_attempts < MAX_ATTEMPTS:       # 5
        post.pipeline_next_attempt_at = now + backoff(post.pipeline_attempts)       # RETRY
    else:                                           # give up: a moderator decides
        post.pipeline_next_attempt_at = None
        if post.status == PENDING: enter_review(post, PIPELINE)
        else:                      post.flagged_reason = merge_flag(post.flagged_reason, PIPELINE)

def apply_report_threshold(post, counting_reports, cfg, now):
    threshold = cfg.emergency_report_threshold if is_active_emergency(post, now) else cfg.report_threshold
    if post.status != REMOVED and counting_reports >= threshold:
        enter_review(post, REPORTS)
```

`now` is a parameter everywhere so tests control time. Part 8 built `merge_flag`, `enter_review` and `apply_report_threshold` (`apps/pipeline/routing.py`; `apply_report_threshold` returns True only when the post **entered** review, and `merge_flag` raises `ValueError` for an appeal onto a post under review for the pipeline, reports or both, and for anything that is not a flag). Part 9 built `awaiting_check_q`/`is_awaiting_check`, `backoff`, `MAX_ATTEMPTS`, `apply_pipeline_result` and `apply_pipeline_failure`; both return an `Outcome` (`ignored`, `labelled`, `entered_review`, `updated_review`, `retry`), and Part 13 notifies the author on `labelled` and `entered_review`. Part 11C added the emergency branches (the FALSE on an active emergency, the emergency report threshold).

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
def score(p, n):   # p, n = sums of the positive / negative weights of all ledger rows (reversals included)
    # round(100 * (5 + p) / (10 + p + n)), a half rounded UP, computed exactly in quarter units:
    P, N = 4 * p, 4 * n; D = 40 + P + N
    return (200 * (20 + P) + D) // (2 * D)        # starts at 50; the 10 imaginary events damp swings
```

- **Half up, exactly** (Part 11B): Python's `round` rounds a half to even ((0, 30) is 12.5 and must give 13), and floats can't be trusted near a half. Every weight is a multiple of 0.25, so the sums are too; `score` refuses a negative sum or one that isn't a quarter.
- **Public only when `reputation_sample ≥ 3`** (`scoring.public_score`). Below that the API returns `score: null` and the UI says "New". Emergency eligibility always uses the stored score.
- A new account moves 50 → 45 after one FALSE, 50 → 55 after one TRUE, 50 → 38 after a FALSE emergency, and to 62 after three TRUE (61.5).

**Events** (the only ones that exist):

| Kind | Who | When | Weight |
|---|---|---|---|
| `fact_true` | author | a fact post becomes `verified_true` (pipeline or moderator) | P + 1 |
| `fact_false` | author | a fact post becomes `verified_false` | N + 1 |
| `emergency_false` | author | an `is_emergency` post becomes `verified_false` (replaces `fact_false`) | N + 3 |
| `post_removed` | author | a moderator removes the post (any type); it **adds to** the label's event, it doesn't replace it (user decision 2026-10-13): a removed FALSE post costs N+1 and N+2 | N + 2 |
| `report_upheld` | reporter | a moderator's **Remove**, or a **Mark FALSE that changed the label** (the post wasn't already FALSE before the review: a pipeline FALSE that reports sent to review, or a label appeal, credits nobody; user decision 2026-10-13), resolves the report while it is open. Never the deciding moderator's own report. At most 4 un-reversed credits per reporter per rolling 30 days | P + 0.25 |
| `repost_true` / `repost_false` / `repost_emergency_false` / `repost_removed` | reposter | the original reaches that outcome **and** the repost was made while it was `pending` or `under_review` (`status_at_repost`, read literally: a repost made during a review counts when the review ends) | P + 0.25 / N + 0.5 / N + 1 / N + 0.5 |
| `reversal` | same user as the row it cancels | the outcome is overturned (below) | the negated weights |

Nothing else changes the score:
- An emergency verified TRUE is a plain `fact_true`, with no bonus.
- Dismissed reports cost the author and the reporter nothing.
- Opinions only count when removed.
- A failed appeal costs nothing.
- Reposting an already-checked post earns nothing.
- Reviews freeze the score: entering review changes nothing, and a pipeline's late TRUE held in `pre_review_status` records nothing until it becomes public (at a Dismiss, dated then).

**One reconciling writer** (`reputation.services.settle_post`, Part 11B; it replaces the four functions the task first named). A post's events are kept in step with its *state*, not written event by event:
- Every row belongs to one of two **slots**. **LABEL**: the author's `fact_*`/`emergency_false`, the reposters' `repost_true`/`repost_false`/`repost_emergency_false`, and the `report_upheld` rows a Mark FALSE earned. **REMOVAL**: `post_removed`, `repost_removed`, and the `report_upheld` rows a Remove earned (a credit's slot comes from its `moderation_action`).
- `scoring.desired(status, is_emergency)`: `verified_true` sets LABEL to TRUE, `verified_false` to FALSE (EMERGENCY FALSE for an emergency); **any other status keeps LABEL as it is** (a review, `pending`, a removed post keeping its label). `removed` sets REMOVAL; any other status empties it.
- `scoring.changes()` then **reverses** every un-reversed row of a set slot whose kind no longer matches (a credit matches only a negative outcome, so a FALSE that becomes TRUE also reverses the Mark FALSE's credits; user decision 2026-10-13) and **adds** what is missing: the author's row; a row for every eligible reposter (a current repost made while undecided, **or** an un-reversed reposter row they already hold in the slot: a repost undone after the verdict keeps its row and moves to the new kind on a re-label, one undone before any verdict gets nothing); and the reporters the caller passes, in the action's slot.
- So a re-label reverses the old outcome for the author **and every reposter** and records the new one; a **Restore** reverses only the REMOVAL slot (author, reposters and that removal's credits) and keeps the label; Keep removed, a re-sent verdict or Mark FALSE upholding a label appeal find nothing to do. Running it twice writes nothing (**idempotent**), and an overturned appeal or a restore returns everyone to exactly what the final outcome alone would have given them.

**Rules**
- **Writes:** only `apps/reputation/services.py` writes the ledger and `users.reputation_score` / `reputation_sample` (a `bulk_update`, so `User.save` and its group sync never run; `recompute_reputation` repairs them). It is called explicitly (no signals) from `posts.services` and `moderation.services`, inside their transaction, **after the caller has locked the post** (`settle_post` raises outside a transaction).
- **Locks:** the post first (the caller's `FOR NO KEY UPDATE`), then every affected user, **sorted by id, with `FOR NO KEY UPDATE`**, not a plain `FOR UPDATE`: a moderator's audit row and `moderated_by` take `KEY SHARE` on users' rows at commit (the foreign keys are deferred), and a plain `FOR UPDATE` on someone who is deciding another post at the same time deadlocks with it (a race test shows it). Never a user and then a post (Part 14's account deletion must keep this order); one `settle_post` per transaction. Nothing to do means nothing is locked.
- **The cap is read after the users' lock** (two decisions at once would both see room for one more), and so are the totals: one grouped aggregate per write (Postgres refuses an aggregate with `FOR UPDATE`, so the lock is its own query). Each new row's `score_after` runs through the user's rows in the order they are written (reversals first, then additions).
- **Deletion:** deleting a post (D6) doesn't undo its events, and undoing a repost after the verdict doesn't either.
- **No backfill** (user decision 2026-10-13): the ledger started empty in Part 11B. A post labelled before it gets its missing events at its next moderator action, dated that day.
- **Recompute:** `python manage.py recompute_reputation [--user <username>] [--check]` rebuilds the two stored fields from the ledger in chunks of 500 accounts (each chunk locked as the service locks), and prints "Recomputed N accounts: M changed.". `--check` writes nothing and fails (non-zero exit) on any stored difference, on a `score_after` that doesn't follow from the rows before it, on times that don't strictly increase, and on a reversal that cancels another person's row, another reversal, or not exactly its row.

**Display** (Part 11B; 11D adds the widget and the trend)
- **Neutral** (user decision 2026-10-13): grey `on-surface-variant` text, never the teal or the `verified` seal that mean a verified fact. The profile header's meta row reads "Credibility 72" or "Credibility: New" (with "A score shows once 3 of their posts have been checked or removed." as its title and screen-reader text) and a "How this is calculated" link; follower/following rows show c3's neutral chip "Credibility 72" or "Credibility: New" and "· 84 verified" (no link in rows).
- The score appears in the profile header, user rows and people search (Part 12), plus the Credibility widget (ring, counts, 30-day trend; 11D).
- The owner's full history (`GET /api/v1/me/reputation/events/`) is the `CredibilityPanel` (Part 11D): on your own profile now and in settings from Part 14. It shows the **real** score (50 for a new account) as a neutral bar, "Others see New until 3 of your posts are checked." while the public score is hidden, and the rows behind a disclosure: reversed rows struck through with the word "Reversed", and on each of your negative rows that still stands "Ask for another look" (a link to the post page, where the appeal button lives) or the appeal's state in words.
- **The widget** (11D; Stitch c1's ring, b4's sparkline) sits on every profile between the header and the filter chips: a neutral grey ring (the score, or "New"), "20 verified · 3 FALSE" (the dots carry the verdict colours), the 30-day line, "How this is calculated". The ring and counts come from the profile payload; only the trend is fetched, and only while the score is public.
- A "How this is calculated" section lives on `/how-it-works#credibility` (the text and the anchor arrive with Part 15).
- The score is **never shown on post cards**, and people are never ranked by it.

**Appeal path and legal caution (guide §16)**
- Label appeals (FALSE) and removal appeals (§4) both exist.
- An overturned appeal reverses the events for the author and every reposter, so the score returns exactly to what it would have been.
- The ledger is the audit trail; moderators and up can read all of it in Django Admin (§8).
- The Terms of Service wording about labels and the score needs legal review before launch.

## 4b. Emergency posts (D5, ANALYSIS f-1; Part 11C)

**What:** a flag on a **fact** post. The post is pinned at the top of feeds for `emergency_duration_hours` (24), still fact-checked (first), and shown in violet (`tertiary`).

**Eligibility** (the pure `apps/posts/emergency.py` `refusal`, checked in `posts.services.create_post` under the author's lock on the fresh row; also reported by `GET /api/v1/me/fact-quota/` as `emergency: {allowed, reason, next_allowed_at, block_days}`). The first failing rule wins, in this order; a refusal is **403 `emergency_not_allowed`** with `reason` and `next_allowed_at` (null when no time will: a paused setting, the score, the email):

| Rule | Reason code |
|---|---|
| email verified | `unverified` (null) |
| account age ≥ `emergency_min_account_age_days` (7; exactly 7 days old passes) | `account_too_new` (`created_at + N days`) |
| `reputation_score ≥ emergency_min_reputation` (40; the stored score, public or not) | `score_too_low` (null) |
| `emergency_blocked_until` is null or ≤ now | `blocked` (the block's end) |
| fewer than `emergency_posts_per_day` (1) emergencies in the rolling 24 h, deleted and removed ones included (0 pauses them) | `daily_limit` (the `(used − limit + 1)`-th oldest + 24 h; null when paused) |
| the fact quota still has room (emergency posts count toward it) | `fact_quota` (`next_slot_at`; null when fact posts are paused) |

An emergency **opinion** is a 400 on `is_emergency` ("Only fact posts can be emergencies.") from the serializer, the service and, last, the database check `posts_post_emergency_fact_only`.

**Lifecycle**
- **Creation:** `emergency_expires_at = created_at + emergency_duration_hours` is stored.
- **Active:** `is_active_emergency(post, now)` (§4) is computed on every read. There is no scheduler, which matters because free hosts sleep.
- **Pipeline:** emergencies are processed first. A TRUE result gives `verified_true`, and the post stays pinned until expiry. A FALSE result while active never becomes FALSE automatically: the post goes to `under_review`, sits at the top of the admin queue, and **keeps its priority**. The same applies to inconclusive or low-confidence results and to reports: priority is kept through any review until expiry or a moderator's FALSE.
- **Moderator Mark FALSE:** `verified_false`, the priority ends at once (`emergency_demoted_at`), and the author is blocked from emergency posts for `emergency_false_cooldown_days` (30). The score takes the `emergency_false` event (N + 3). Three audit rows, 1 µs apart: `marked_false`, `emergency_demoted`, `emergency_blocked`.
- **Any FALSE label on an emergency blocks** its author (user-approved default, Part 11C): a moderator's, or the pipeline's after expiry or demotion (a row with no moderator). The trigger is the ledger's new `emergency_false` row, so a re-sent verdict, an upheld label appeal or a Dismiss back to FALSE never blocks twice.
- **How a block ends** (user decision 2026-10-19): the automatic block lifts by itself when that FALSE label is overturned (an `emergency_unblocked` row with the post), unless another block still stands; a moderator's **Block emergency posting** (UserAdmin) lasts `emergency_false_cooldown_days` too; **Unblock emergency posting** lifts every block early. `users.emergency_blocked_until` is always the latest end among the blocks still standing (`rules.standing_block_end`): an unblock with no post lifts every earlier block, one with post P only P's.
- **Other moderator actions:** Demote emergency ends priority without a label change. Remove works as usual and doesn't demote: a Restore inside the 24 hours pins the post again (its removal was the mistake). Mark verified, Dismiss and Escalate leave the priority alone. All of these are logged.
- **Reports:** while the post is active, `emergency_report_threshold` (2) replaces `report_threshold` (5).
- **After expiry or demotion:** it's a normal post with its status colour. The detail page shows "Posted as an emergency on <date>. Priority ended." (or "… Priority removed by a moderator." when `emergency_demoted`, §9).

**Pinning (feeds, §9)**
- Recent pins all active emergencies; Following pins those from followed accounts plus you.
- Newest first, at most 3 in `pinned`, with `pinned_total` for "Show all" (`GET /api/v1/posts/emergencies/`).
- **Every pinnable post** is left out of `results`, on every page, not only the 3 shown. Reposts never pin: on Following a repost **of a pinnable post** is left out too (it would repeat it), while a repost of another emergency stays, with the chip.
- Profiles and bookmarks never pin (`pinned: []`; an emergency shows inline with its chip).

**Notifications:** the author gets `emergency_demoted` when priority is removed early (Part 13: Demote sends it alone, Mark FALSE on a pinned emergency sends the verdict **and** it). The automatic block after a FALSE emergency and its lift notify nobody. Out of scope: follower alerts, email or push, and moderator email alerts.

## 4c. Sources / DOI (D5, ANALYSIS f-3; Parts 4–5)

- **Scope:** optional, fact posts only, **0–5 sources per post**, kept in the order entered, immutable, each at most 500 chars. Stored in the `sources` array column (§2). Changed from one source to up to five by the user on 2026-10-01.
- **Each source** is an http(s) URL or a DOI, validated and normalised by the rules below. Every element must be valid, or the whole post is refused.
- **Duplicates:** two sources that are equal after normalisation are refused (`doi:10.1000/xyz` and `https://doi.org/10.1000/xyz` are the same source).
- **DOI input:** `10.<4–9 digits>/<suffix>` (Crossref's recommended pattern `^10\.\d{4,9}/[-._;()/:A-Za-z0-9]+$`). A leading `doi:` or `https://doi.org/` / `http://dx.doi.org/` is accepted and stripped. Stored bare, e.g. `10.1038/s41558-024-02102`.
- **URL input:**
  - `http` or `https` only;
  - a host with a dot, no user/password, no IP-address or `localhost` hosts, no whitespace or control characters;
  - internationalised hosts are converted to punycode for storage and display.
- **Kind is derived, not stored:** a stored DOI is bare and starts with `10.`; a stored URL always starts with `http://` or `https://`. One helper, `posts.validators.source_kind(value)`, returns `doi` or `url`, and the serializer uses it.
- **API input:** `POST /api/v1/posts/` takes an optional `sources: ["…", …]` (at most 5 strings; the client drops empty rows). On the wire the answers are messages only (the core handler sends no `code` for validation errors): `{"sources": {"1": ["…"]}}` per bad index, every bad index at once, `{"sources": ["You can add up to 5 sources."]}` for the list rule (checked first: six sources with one bad element give only this), and `Same as source 1.` on the **later** of two equal ones. The codes `invalid_source`, `invalid_doi`, `empty_source`, `source_too_long`, `too_many_sources`, `duplicate_source` exist inside the server (tests read them with `get_codes()`). Sources on an opinion are refused.
- **Normalisation (Part 4)** is one algorithm in two languages: `apps/posts/validators.py` and `frontend/src/features/posts/sources.ts`, both driven by `apps/posts/tests/source_vectors.json`. The browser's `URL` parser is deliberately **not** the algorithm (it turns `\` into `/`, decodes `%xx` in hosts and accepts `https:example.com`).
  1. Trim **ASCII** whitespace only (JS `trim()` and Python `strip()` disagree on U+FEFF and others); empty → `empty_source`; over 2,000 characters → `source_too_long`.
  2. **DOI first:** a `doi:` prefix (any case, spaces or tabs after it) must be followed by a DOI, else `invalid_doi`; `http(s)://(dx.)doi.org/` is tried as a DOI and, if what follows isn't one (a query, say), the input is an ordinary URL; bare text starting `10.` must be a DOI. The pattern is `10\.[0-9]{4,9}/[-._;()/:A-Za-z0-9]+` matched as a whole, with no ignore-case flag (`[0-9]`, not `\d`; no trailing newline; no Kelvin sign), and the prefix is matched ASCII-only (`httpſ://` is not https). Stored bare, case kept; two DOIs that differ only in case are duplicates.
  3. **Characters:** any `\` or character in Unicode category Cc, Cf (bidi marks), Cs (lone surrogates), Zs, Zl or Zp is refused.
  4. **Split** with RFC 3986's appendix-B expression (the same in both languages, not `urlsplit`): the scheme (lower-cased) must be `http` or `https`, `//authority` is required, `@` (credentials) is refused, the port must be 1–65535 in ASCII digits, and the scheme's default port is dropped.
  5. **Host:** no `%`, `[` or `]`; ASCII hosts are lower-cased, non-ASCII ones go through `idna.encode(host, uts46=True)` (UTS #46, the browsers' rules: `faß.de` → `xn--fa-hia.de`, not the old IDNA 2003 `fass.de`; idna 3.20 ignores `transitional` and is always non-transitional; the client uses the browser's own `URL` for punycode only). Each label must match `[a-z0-9_]([a-z0-9_-]{0,61}[a-z0-9_])?` (underscores and `--` inside are allowed, as browsers do; **idna's own check would reject both for ASCII hosts, so ASCII hosts never go through it**); at least two labels, at most 253 characters; no trailing dot or empty label; not `localhost` or `*.localhost`; the last label must not be numeric or `0x…` (WHATWG reads `127.1` and `0x7f.1` as IPv4). Only the server checks that an `xn--` label really is an A-label (`idna.decode`); a browser accepts `xn--zzzz.example`, so the page can't tell and the server's 400 lands on that row.
  6. **Rebuild** as `scheme://host[:port]` + path (`/` when empty) + query + fragment as typed; only non-ASCII characters are percent-encoded (UTF-8, uppercase hex). The result must be at most 500 characters (after punycode and encoding).
  The function is idempotent.
- **Never fetched.** The server makes no request to any source: no previews, no HEAD checks (no SSRF). A test enforces this.
- **Display:**
  - Fact cards keep one line: the first source's host (or `doi.org/…` for a DOI), then "+N more" when there are more. From Part 5, "+N more" links to the detail page.
  - The detail page shows every source as a numbered list (01, 02 …) with the full value and an open-in-new link, under "Sources (N)". This is the Stitch b3 "primary sources" registry without its sample titles, org-type chips, "% match" and archive/hash lines.
  - DOIs link to `https://doi.org/<doi>`. Links use `rel="nofollow ugc noopener noreferrer"` and `target="_blank"`, and the text is plain.
- **Pipeline:** passed as `sources` in `PipelineRequest` (§6) for the future real pipeline. The stub ignores it.

## 4d. Bookmarks and reposts (D5, ANALYSIS f-4; Part 7B)

**Bookmarks**
- Any logged-in user can bookmark (no email verification needed, because bookmarks are private).
- Toggling is idempotent.
- `GET /api/v1/me/bookmarks/` lists your bookmarks, newest bookmark first, and drops deleted and removed posts (§9).
- `bookmarked_by_me` appears in the post object. No count is ever exposed, and `BookmarkAdmin` is **superuser-only** (user decision 2026-10-10): no moderator permission opens it, now or after Part 10.
- A removed or deleted post can't be bookmarked (404), but a bookmark can be taken back from a removed post; your own posts and FALSE ones can be bookmarked.

**Reposts**
- Plain reposts only: one per user per post, and never of a repost (reposting a repost reposts the original).
- Refused:
  - your own posts (`cannot_repost_own`);
  - posts that are `verified_false`, **and posts under review that were `verified_false` before the review** (`pre_review_status`; `cannot_repost_false`; Part 8, user decision 2026-10-10: reports can move a FALSE post to review, which must not reopen it to reposts). `pre_review_status` is never public, so the button can't be disabled in advance for this case: the click is answered 409 and the rollback toast says "Posts labelled FALSE can't be reposted.". Since Part 9 this only ever concerns a FALSE label that was public before the review: a FALSE the pipeline finds while the post is already under review for reports is never stored as the label to restore (§4), so the refusal can't reveal it;
  - removed or deleted posts (404).
- Email-verified users only. `status_at_repost` is recorded (the status at commit: the repost locks the post row with `FOR NO KEY UPDATE`).
- **Order of the checks:** a post the public can see (404 otherwise), then an existing repost (**200**: a post that turned FALSE after you reposted it doesn't refuse you), then your own post (409 `cannot_repost_own`), then FALSE or under review after FALSE (409 `cannot_repost_false`).
- **You can always take a repost back**, whatever became of the original (user decision 2026-10-10): `DELETE …/repost/` is 204 whenever the post row exists, deleted and removed included, so your own "no longer available" card always has an **Undo repost**.
- A repost has no content and no status of its own. It always shows the original's **live** label, and nothing is re-checked.
- If the original is later deleted or removed, the repost item shows "This post is no longer available".
- Following feed and profiles show reposts ("Reposted by @x"); Recent shows originals only. A profile's Facts and Opinions chips filter a repost by the **original's** type (stubs included; user decision 2026-10-10).
- A repost has no id in the API: `POST` and `DELETE` always name the original post, so "reposting a repost" reposts the original.
- A post shows once per page (§9); the page also hides a repeat that comes back on a later page (user decision 2026-10-10).
- The original author is notified (`repost`, de-duplicated). Score effects are in §4a.

## 4e. Profile photos (D5, ANALYSIS f-7, c-49; Part 14B)

**Upload:** `PUT /api/v1/me/avatar/` (multipart `file`). Needs a verified email (403 `email_unverified`) and uploads that are not blocked (403 `photo_uploads_blocked`); both are permissions, so neither counts against the throttle `avatar_upload` (5/day, PUT only; a refused photo does count). `DELETE /api/v1/me/avatar/` removes the photo; it needs a login only (a blocked or unverified person can still take their photo down) and has no throttle. Both answer from the account's lock (`FOR NO KEY UPDATE` on the user, never a post, so they can't deadlock with `delete_account`).

**The original never touches the disk or the database.** The view's only upload handler (`PhotoUploadHandler`) keeps the file in memory and stops at 5 MB of file data, whatever the declared length said (Django's default pair would spool anything over 2.5 MB to a temp file). A declared `Content-Length` over 5 MB + 64 KiB is refused before the body is read (400 `photo_too_large`); a body that lies is cut off at the cap. Only the `file` field is read.

**Processing** (`apps/accounts/avatars.py`, Pillow 13.0.0):
1. `Image.open(…, formats=("JPEG", "PNG", "WEBP"))`: no other decoder ever sees the bytes, and the extension and `Content-Type` are never read. SVG, GIF, HEIC, BMP, TIFF, animated PNG/WebP and anything damaged are 400 `photo_unsupported`. A multi-picture JPEG (MPO, some cameras) is read as its first frame.
2. **The header is checked before any pixel exists:** at most 25,000,000 pixels (WebP: 12,000,000; 400 `photo_too_many_pixels`) and at least 128 × 128 (400 `photo_too_small`). Pillow only warns between 1× and 2× of `MAX_IMAGE_PIXELS` and raises above 2×, so the explicit check is the rule; `MAX_IMAGE_PIXELS` is 25 MP so a bomb over 2× raises at open.
3. JPEGs are decoded with `draft()` (1/2, 1/4 or 1/8 scale as far as the result stays at least 256 px). Then the **centre square** is flattened onto white (any transparency) and shrunk by a whole factor **in horizontal bands**, so no second full-size copy exists (Pillow's own `reduce` converts a whole RGBA image to premultiplied form first: 314 MB on a 300 × 83,000 panorama). The EXIF orientation is applied to the small result.
4. Two **new** images, 256 and 96 px (LANCZOS), are built from pixel bytes and saved as WebP, quality 80: no EXIF, ICC or XMP chunk is written because the image has none to give (the encoder takes them only from save options). The colour profile is not converted: browser-made uploads are already sRGB, and parsing untrusted ICC is more attack surface.
5. `version` = first 16 hex of the SHA-256 of the 256 px image: identical pixels give the same URL, a new photo a new one. The `Avatar` row and `users.avatar_version` are written together, after the account is locked and **checked again** (active, verified, not blocked: a Block that committed while the photo was decoding wins, 403).
6. Every decoder error is a refusal (`photo_unsupported`), never a 500.

**One decode at a time, site-wide.** Render runs 2 workers × 4 threads in 512 MB, and a 25 MP RGBA PNG decodes to about 100 MB. The decode runs inside `pg_advisory_xact_lock(<constant>)` taken with `SET LOCAL lock_timeout = '10s'`; a timeout is **503 `photo_busy` with `Retry-After: 5`**. The lock is transaction-scoped, so it can't leak. Measured peaks above the process baseline, in a fresh interpreter (`test_avatar_memory.py`): 25 MP RGBA PNG about 112 MB, 300 × 83,000 RGBA panorama about 103 MB, 24 MP JPEG about 10 MB, 12 MP WebP about 189 MB; refused bombs 1 to 5 MB.

**Serving:** `GET|HEAD /api/v1/avatars/{user_id}/{version}-{96|256}.webp`
- public, no authentication (a stale token is not a 401), no throttle; the id must be a canonical UUID and the name must match `[0-9a-f]{16}-(96|256).webp`; **a wrong version or size, an unknown account or a removed photo is a 404** (`{"detail", "code": "not_found"}`);
- one query: the image column of `Avatar` filtered by user **and** version; when `If-None-Match` matches `"<version>-<size>"` an `exists()` and a **304** that never loads the bytes (a wrong version is still 404, not 304);
- headers on 200 and 304: `Content-Type: image/webp` (200), `Cache-Control: public, max-age=31536000, immutable`, `ETag: "<version>-<size>"`, `X-Content-Type-Options: nosniff`, `Content-Security-Policy: default-src 'none'; sandbox`, `Content-Disposition: inline; filename="avatar.webp"`;
- goes through the relay like every `/api` call, which passes these headers and the 304 back unchanged (checked by `relay.test.ts` and the E2E test, no relay change was needed).

**Sizes:** `GET /me` and `GET /users/{username}/` give the **256** URL (the settings preview is 56 px and the profile header 80 px, crisp at 2×); every list item gives **96** (post authors, comments, `reposted_by`, user rows, people search, notification actors).

**Everywhere:** `author.avatar_url` / `user.avatar_url` is null when there's no photo. `<Avatar>` falls back to initials when there's no photo, on load error, and after removal, and loads its image with `loading="lazy" decoding="async"` (each photo is one Worker request per browser, §13).

**Moderation:** `AvatarAdmin` (thumbnails, newest change first; the image columns are never loaded) with **Remove photo** and **Block photo uploads**, and `UserAdmin` with those two and **Allow photo uploads**, all logged with `subject_user` (§8). **Block photo uploads also removes the current photo** (user decision 2026-10-21); Allow lifts the block and does not bring the photo back. Nobody is notified (the nine notification types stay nine); the settings card shows the block. A suspended account's photo is still served (Part 16 decides suspension visibility). There is no user-facing "report photo" in the MVP (follow-up). The Google profile picture is never imported.

**Browser:** every file is decoded and drawn again in the browser (centre square, at most 1024 px, JPEG 0.9 on white), so GPS never leaves the device; originals up to 20 MB are accepted, because the result is small. The server redoes everything.

**Export and deletion:** the export carries your photo as `account.photo` = `{format: "webp", size: 256, data: <base64>}` (null without one) and `account.photo_uploads_blocked`; deleting the account deletes the `Avatar` row with it.

## 5. Reporting (guide §6; c-2; Part 8)

`POST /api/v1/posts/{id}/report/` `{reason, details?}` (`apps/reports/`):
1. **Before the service:** logged in, **email verified** (401 / 403 `email_unverified`; neither counts against the throttle), throttle `report` 10/h (429; from here every answer counts), a well-formed id (JSON 404), the body (400).
2. **Inside `transaction.atomic()`** (`reports.services.file_report`), in this order:
   - lock the post: `Post.objects.visible().select_for_update(no_key=True, of=("self",))`; none (unknown, deleted, removed, **its author too**) → **404**. `FOR NO KEY UPDATE` serialises reports with each other and with status writes (a delete, a moderator's action) but not with the `FOR KEY SHARE` that likes, comments and bookmark inserts take on a busy post. A report that waited for a delete or a removal re-checks the row and finds nothing;
   - your own post → **403 `cannot_report_own`**;
   - an earlier report by you (any status) → **409 `already_reported`**. The lock makes this check race-free; the unique pair is the last-resort guard (no `IntegrityError` catch);
   - insert the report; `posts.services.record_report` adds 1 to `report_count` (every report, counting or not);
   - `counts_toward_threshold` = reporter account age ≥ `report_min_account_age_hours` (**inclusive**) **or** the reporter has taken part: **a post that isn't removed or a comment that isn't hidden. Posts and comments the reporter deleted themselves still count** ("deleting undoes nothing", as for the fact quota); content a moderator took down (removed posts, hidden comments) earns no trust (user decision 2026-10-10). An established account costs no query;
   - `n` = this post's reports with `status='open' AND counts_toward_threshold AND created_at >= now - window` (**inclusive**; **no upper bound**: `now` is taken before a lock wait, so a report that waited can carry a `now` older than a committed row that must still count), the new one included;
   - `apply_report_threshold(post, n, cfg, now)` (`apps/pipeline/routing.py`; threshold 2 instead of 5 while an emergency is active, §4b, from Part 11C);
   - save `report_count`, `status`, `flagged_reason`, `pre_review_status` and `updated_at` (all `Post` writes stay in `posts/services.py`).
3. **201 `{"reported": true}`**, always the same: the answer never says whether this report sent the post to review. The post stays visible while under review (guide §6.4), a FALSE post included (it goes to `under_review` with `pre_review_status=verified_false`, so Dismiss restores FALSE; it can't be reposted meanwhile, §4d). Redis is never used for the count.
4. When a moderator later removes the post or marks it FALSE, every report that was still open becomes `actioned`, and each reporter gets the `report_upheld` credit (§4a, capped).

Bodies: `reason` is required and one of the five ("Choose a reason." for missing, null or unknown); `details` is trimmed, at most 500 code points ("Keep it to 500 characters."), and required when the reason is `other` (`{"details": ["Tell us what's wrong."]}`); undeclared fields (`status`, `reporter`, `counts_toward_threshold`) are ignored. Reports are permanent: there is no withdrawing one.

## 6. Pipeline contract and processing (guide §5.4, §7.1; c-21)

```python
# apps/pipeline/contract.py — frozen dataclasses, validated on construction
PipelineRequest(post_id: UUID, content: str, sources: tuple[str, ...])   # 0–5 validated URLs/DOIs (§4c), never fetched by us
PipelineResult(verdict: Literal["true","false","inconclusive"],
               confidence_score: Decimal,   # 0–100, quantized to 0.01
               raw_result: dict)            # stored verbatim in posts.pipeline_result

class PipelineClient(Protocol):
    def check(self, request: PipelineRequest) -> PipelineResult: ...
```

- **The contract (Part 9)** is checked when a request or a result is built (`ContractError`, a `ValueError`): `sources` is a **tuple** of 0–5 non-empty strings of at most 500 characters (a list is refused), `content` 1–500 code points; `verdict` is exactly one of the three; `confidence_score` is a `Decimal`, `int` or numeric string (a `bool`, a float, NaN and infinity are refused), checked 0–100 on the exact value, then rounded half up to 0.01 (what is stored, shown and compared with the threshold); `raw_result` is an object. `PipelineResult.from_json` reads the three keys of a JSON answer (others are ignored; a JSON number goes through its text, so 91.5 is exactly 91.50).
- **`StubPipelineClient`** (`PIPELINE_BACKEND=stub`) is deterministic, so tests and demos are predictable:
  - content containing `#true` → (true, 95)
  - `#false` → (false, 92)
  - `#unsure` → (inconclusive, 40)
  - the **first** of these tags in the text decides; a tag counts in any case but only as a whole tag (`#True.` yes, `#trueish` no)
  - otherwise the SHA-256 of the UTF-8 content gives the confidence (`50 + bytes 0–1 mod 50`, so 50–99) and the verdict (`true` when byte 2 is even, else `false`; never `inconclusive`). Python's own `hash()` changes per process and is never used. At the seeded threshold of 85, about 15 % of untagged facts become VERIFIED, 15 % FALSE and 70 % UNDER REVIEW
  - `raw_result={"stub": true, "rule": "#true" | "#false" | "#unsure" | "hash"}`; `sources` are ignored
- **Production (user decision 2026-10-11, a launch blocker for Part 17):** `.env.example` says production runs the stub until a real pipeline exists. With the stub, any author can write `#true` to get VERIFIED 95%, and about 15 % of untagged facts get a hash-chosen FALSE that would feed the public credibility score (§4a). Part 9 builds the stub as specified; **before any deploy, Part 17 must decide how production gets verdicts** (a real pipeline, or a mode that applies no automatic labels).
- **`HttpPipelineClient`** (`PIPELINE_BACKEND=http`, future): `POST PIPELINE_URL` with `{post_id, content, sources}`, `Authorization: Bearer PIPELINE_API_KEY`, 20 s for the whole call (10 s per socket operation, the body read in chunks; the DNS lookup has no timeout). It expects `{verdict, confidence_score, raw_result}`. Standard library only (like Turnstile), **no redirect is followed**, at most 64 KB of answer. Failures are `PipelineError(kind, detail)` with `kind` `timeout`, `network`, `http_status`, `bad_response` or `contract`; the detail is our own text, never the answer's body or the key. It is the only module of `apps/pipeline` that may open a connection, and only to `PIPELINE_URL` (`apps/reports/tests/test_no_network.py` names it). Swapping it in changes nothing else.
- **Settings:** `PIPELINE_BACKEND` is `stub` (default) or `http`; with `http`, `PIPELINE_URL` must be `https://` (plain `http://` only to a loopback host, the relay's rule) and `PIPELINE_API_KEY` is required; anything else stops startup naming the variable. `PIPELINE_INLINE_KICK` defaults to True (empty counts as the default). Tests pin the stub and turn the kick off (§11).
- **Processor** (`apps/pipeline/processor.py`; Part 9). The `posts` table is the queue. A post is **due** when it is awaiting a check (§4: a fact, not deleted, no `verdict_source`, and `pending` **or under review for reports while still pending**, because reports can arrive before the check) and `pipeline_next_attempt_at` is null or ≤ now; order **active emergencies first** (Part 11C: `Case(When(active_emergency_q(now), then=1), default=0) DESC`; an expired or demoted emergency waits its turn), then oldest (`created_at`, `id`). One post at a time, in three steps, so the post's row is **never locked while the pipeline thinks** (reports, reposts, deletes and moderators would wait up to 20 s):
  1. **Claim** (a short `transaction.atomic(durable=True)`): lock the first due post with `FOR NO KEY UPDATE SKIP LOCKED` (the kick waits for the lock instead of skipping, because a report holds a row for a moment), add 1 to `pipeline_attempts` (that number is the claim's **token**: a try is counted when it is claimed, not when it fails, so a post that crashes the worker every time still ends) and set `pipeline_next_attempt_at = now + 5 min`, the **lease** that keeps every other processor away. `updated_at` doesn't move. A post already at `MAX_ATTEMPTS` (every earlier try died mid-call) is given up at once without a call (`lease_expired`).
  2. **Call** the client outside any transaction. Building the request is part of the try, and **any** exception is a failed try (an unexpected one is recorded as `error` with its class name only).
  3. **Apply** in `posts.services.record_pipeline_result` / `record_pipeline_failure` (`atomic(durable=True)`, the row locked with `FOR NO KEY UPDATE`): the answer is **dropped** when the post was deleted meanwhile or its `pipeline_attempts` no longer equals the token (the lease ran out and a newer claim took the post); otherwise the pure routing (§4) decides, and an ignored post is not written at all. `pipeline_next_attempt_at` ends null after a result or a give-up, holds the backoff after a failure, and is left alone when an answer is ignored or dropped (it would overwrite a newer lease).
  - `process_pending(limit=10, now=None, client=None, deadline=None)` repeats that up to `limit` times and returns how many posts it handled; with a `deadline` it **always takes the first post** and another only while `monotonic() + client.max_seconds` still fits (the stub takes no time, so it does 10; a real pipeline about 1 to 5). A post that fails in an unexpected way is logged and skipped (its lease brings it back); a failing claim ends the run. `process_post(post_id)` does one post (the kick).
  - Logging: INFO per outcome (the post id, never its content), WARNING per failed try (the kind), ERROR when it gives up (one Sentry event per abandoned post).
- **Triggers:**
  - (1) **Inline kick:** `create_post` registers `transaction.on_commit` for a **fact** while `PIPELINE_INLINE_KICK` is on; the callback **never raises** (an error after the commit would turn a saved post's 201 into a 500 and invite a duplicate) and starts a **daemon** thread (`pipeline-kick`) that runs `process_post` and then closes its own database connections. At most 4 such threads per process (a `BoundedSemaphore`); when all are busy the post waits for the sweeper. A post whose transaction rolls back queues nothing.
  - (2) `POST /api/internal/tick/` (header `X-RZ-Cron-Secret`, checked like the deep health check; missing, wrong or non-ASCII → 403 `permission_denied`; GET → 405), hourly from cron-job.org: `process_pending(limit=10, deadline=now + 25 s)` → `200 {"processed": n}`, well inside cron-job.org's 30 s and gunicorn's 60 s. It authenticates no user and has no throttle (the secret is the guard).
  - (3) `python manage.py process_pending [--limit N] [--loop] [--interval S]` for local dev: one run checks **everything that is due** (in batches of `--limit`, 1–100, default 10) and prints "Processed N fact posts."; `--loop` repeats that every `--interval` seconds (default 5) until Ctrl+C.
  - With the hourly tick, a try that fails waits for the next tick, so retries in production take hours (a note for when a real pipeline arrives).
  - No Celery, no worker service.

## 7. Authentication (guide §4; D1, c-17, c-18, d)

**Library:** django-allauth 65.19.5 **headless**, client `app`, with our strategy `apps.accounts.tokens.RumorZeroJWTTokenStrategy` (a subclass of allauth's `JWTTokenStrategy`; see "Tokens and sessions"). The settings map from our env vars:

| allauth setting | Value |
|---|---|
| `HEADLESS_JWT_ALGORITHM` | `HS256` |
| `HEADLESS_JWT_PRIVATE_KEY` | `JWT_SIGNING_KEY` (≥ 32 characters and ≠ `DJANGO_SECRET_KEY`, or Django refuses to start) |
| `HEADLESS_JWT_ACCESS_TOKEN_EXPIRES_IN` | `JWT_ACCESS_TOKEN_MINUTES × 60` (1–60 min) |
| `HEADLESS_JWT_REFRESH_TOKEN_EXPIRES_IN` | `JWT_REFRESH_TOKEN_DAYS × 86400` (1–90 days) = `REFRESH_TOKEN_SECONDS` |
| `HEADLESS_JWT_ROTATE_REFRESH_TOKEN` | True |
| `HEADLESS_JWT_STATEFUL_VALIDATION_ENABLED` | False (set explicitly) |
| DRF authentication class | `apps.accounts.authentication.JWTAuthentication` (allauth's `JWTTokenAuthentication`, plus: a deleted or inactive user's token → 401, never a 500) |

Other settings:
- `HEADLESS_ONLY=True`; `HEADLESS_CLIENTS=("app",)`
- `HEADLESS_FRONTEND_URLS` (set in Part 1: headless-only mode refuses to send the verification email without them): `account_confirm_email` = `FRONTEND_ORIGIN/verify-email/{key}`; `account_reset_password_from_key` = `FRONTEND_ORIGIN/reset-password/{key}`; `account_reset_password` = `FRONTEND_ORIGIN/forgot-password`; `account_signup` = `FRONTEND_ORIGIN/signup`
- `FRONTEND_ORIGIN` must be a bare origin (normalised: lowercase, no trailing slash) and https when `DEBUG` is off. With `DEBUG` off, `AUTH_COOKIE_SECURE` must be True and `EMAIL_PROVIDER` must be `brevo` (console and file would put links in logs or on disk). Each guard fails naming the variable, never its value.
- `ACCOUNT_ADAPTER = apps.accounts.adapter.AccountAdapter`: NFKC-folds the username before allauth's own (lowercase-only) uniqueness check; sets the token session's lifetime at login; a failed email send is logged by exception class only and never turns a saved sign-up into a 500 (so a provider failure on resend still answers 204). Part 2: `add_message()` does nothing (headless-only shows no Django messages, and allauth skips it only for headless-marked requests: with `django.contrib.messages` installed it would set a `messages` cookie on the frontend origin), and `send_mail()` adds `frontend_origin` and `email_logo_url` (`FRONTEND_ORIGIN/brand/email-logo.png`) to the template context.
- `ACCOUNT_LOGIN_METHODS={"email"}`, `ACCOUNT_SIGNUP_FIELDS=["email*","username*","password1*"]`, `ACCOUNT_PRESERVE_USERNAME_CASING=False`, `ACCOUNT_EMAIL_SUBJECT_PREFIX="[Rumor Zero] "`
- `ACCOUNT_EMAIL_VERIFICATION="optional"`: unverified users can log in and browse; writes are blocked by the `IsEmailVerified` permission (guide §4.3 step 4). Sign-up sends the verification email and logs the user in.
- `ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS=1`
- `ACCOUNT_LOGIN_ON_PASSWORD_RESET=True`
- `ACCOUNT_EMAIL_UNKNOWN_ACCOUNTS=False` (user decision 2026-10-06): an unknown address gets no email, and the HTTP answer is identical. A small timing difference is accepted: sign-up already reveals taken emails, behind Turnstile.
- `ACCOUNT_PREVENT_ENUMERATION=True` (allauth's default, pinned): with False the reset form raises `unknown_email`.
- `PASSWORD_RESET_TIMEOUT=86400`: reset links last 24 h (Django's default is 3 days), matching Stitch a5 and the verification link.
- `ACCOUNT_RATE_LIMITS`: pinned (§3), including the Part 2 email limits
- Email templates live in `backend/templates/account/email/`: `allauth` precedes `apps.accounts` in `INSTALLED_APPS`, so templates inside our app would be shadowed. allauth ships only `.txt`; we add `.html`. Details under "Emails" below.
- **Startup:** `AccountsConfig.ready()` connects the `email_confirmed` receiver and imports `jwt` and `cryptography.hazmat.primitives.ciphers` (`TOKEN_LIBRARIES`). allauth defers both until the first token it makes, and two sign-ins arriving together at a cold server then raced inside the import (`cannot access submodule 'ciphers' … circular import` → 500). `test_startup.py` pins it.
- `AUTHENTICATION_BACKENDS` = allauth's backend only. It also serves the Django Admin login (it accepts the email as `username`). Adding `ModelBackend` would hash a wrong password twice (Argon2 uses 100 MiB per hash).
- `SESSION_ENGINE` stays Django's database backend: refresh locks the session row and logout deletes it.
- **Google (Part 3):**
  - `allauth.socialaccount` and `allauth.socialaccount.providers.google` are in `INSTALLED_APPS` (allauth's six `socialaccount` migrations run on `migrate`; we add none).
  - `GOOGLE_OAUTH_CLIENT_ID` is read by `google_client_id(env)` (`env_helpers.py`): blank **disables** Google (no production guard; the endpoint is a 404 and the frontend hides the button); a value must have no whitespace, end with `.apps.googleusercontent.com` and be at most 200 characters, else Django refuses to start naming the variable, never the value.
  - `SOCIALACCOUNT_PROVIDERS["google"]["APPS"]` holds one app, `{client_id, secret: "", key: ""}`: the ID-token flow needs no client secret. `VERIFIED_EMAIL=False` (Google's own `email_verified` claim is used as it is).
  - `SOCIALACCOUNT_ADAPTER=apps.accounts.adapter.SocialAccountAdapter`; `SOCIALACCOUNT_EMAIL_AUTHENTICATION` and `…_AUTO_CONNECT` are True (Google's address links to an existing account, subject to the rules below); `SOCIALACCOUNT_AUTO_SIGNUP=True` (a sign-up must **never pend**: a pending social sign-up answers 401 and needs `X-Session-Token`, which `AuthApiMiddleware` strips); `SOCIALACCOUNT_STORE_TOKENS=False`; `SOCIALACCOUNT_REQUESTS_TIMEOUT=5` (fetching Google's certificates). `ACCOUNT_EMAIL_NOTIFICATIONS` stays False; allauth's own "account connected" mail therefore never goes out, and ours does (Part 14, "Account settings" below).

**Account settings (Part 14; user decisions 2026-10-20).**
- **Profile:** `PATCH /api/v1/me/` edits `display_name` (≤50 code points, one line), `username` (`normalize_username` then `validate_username`; the old name is free at once, no cooldown, only the `profile_update` throttle) and `bio` (≤280, `\r\n` → `\n`, no control characters). Other keys are ignored. It needs a verified email (`IsEmailVerified`). `accounts.services.update_profile` saves with `update_fields` (never the verification flag, the score or the emergency block) and turns a lost unique-index race into the same 400 "That username is taken.".
- **Password change:** `POST /api/v1/me/password/`. An account without a usable password (Google-only) gets **409 `password_not_set`** (use Forgot password). The current password is checked (400 on `current_password`), then Django's validators (400 on `new_password`). Under a `select_for_update` lock on this device's `django_session` row (the lock a refresh takes, `tokens.py`) the session gets the new `_auth_user_hash`, so **this device stays signed in** and every other session ends at its next refresh. A "password changed" email goes out after the commit.
- **Google connected email:** the `social_account_added` receiver (it fires only when Google links to an *existing* account; a Google sign-up fires `user_signed_up`) sends "Continue with Google is now connected" after the commit, and adds a line when `wipe_password` had removed the password (the address was unverified).
- **Deleting:** `DELETE /api/v1/me/` with `{password}`, or `{username}` for an account without a password. Staff (`is_staff`) and any account that wrote Django Admin log entries get **403 `staff_account`** (`LogEntry.user` cascades; the admin's delete page protects the same accounts). `accounts.deletion.delete_account(user, session_key=…)` locks **every post of the account first, then the user** (the order `settle_post` takes), deletes the notifications the account caused, this device's session row and the user (the database cascades per §2), and the response expires `rz_refresh` and `rz_session`. Every other session fails at its next refresh because the user row is gone; its `django_session` row is left for `clearsessions` (Part 17). A post created and settled at the very instant of the deletion can still deadlock; Postgres aborts one side and the client may retry. `report_count` is never decremented.
- **Export:** `GET /api/v1/me/export/` (§9), one query per section, columns named explicitly.

**Endpoints** (confirmed in Part 1; allauth's paths have no trailing slash). `path("api/auth/logout/", …)` and `path("api/auth/", include("allauth.headless.urls"))` come before `api/`:

| Path | Notes |
|---|---|
| `POST /api/auth/app/v1/auth/signup` | `{email, username, password, turnstile_token}` → 200 `{data.user, meta.access_token}`. Field errors carry `param` `email`, `username`, `password` or `turnstile_token`. |
| `POST /api/auth/app/v1/auth/login` | `{email, password}` → 200, same shape. A wrong password is `email_password_mismatch` (param `password`); a rate limit is **400** `too_many_login_attempts` (no param). |
| `POST /api/auth/app/v1/tokens/refresh` | no body (the cookie is the token) → 200 `{data.access_token}`; a bad, rotated or revoked token → bare `{"status":400}` |
| `POST /api/auth/app/v1/auth/email/verify` | `{key}` → **200 `{"status":200}`** (Part 2). Always anonymous: the middleware drops `Authorization`/`X-Session-Token`, and allauth's "success with nobody logged in" **401** is turned into 200. Errors keep allauth's 400 `invalid_or_expired_key` (param `key`: expired, used and forged keys alike), `email_taken`. A link never logs anyone in (`ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION` stays False). |
| `POST /api/auth/app/v1/auth/password/request` | `{email}` → 200 `{"status":200}` for existing, unknown, inactive and unverified addresses alike (same bytes); a malformed email → 400 (param `email`); limits → 429 `{"status":429}` (§3). Only an existing, active account gets the email. |
| `GET /api/auth/app/v1/auth/password/reset` | key in the **`X-Password-Reset-Key`** header → 200 `{data.user}` or 400 `invalid_password_reset` (param `key`); not rate limited. The reset page's pre-check, so a dead link shows the expired state before anyone types a password. The relay forwards the header; Sentry's denylist includes it. |
| `POST /api/auth/app/v1/auth/password/reset` | `{key, password}` → 200 like login (`meta.access_token`, refresh cookie set: `ACCOUNT_LOGIN_ON_PASSWORD_RESET`). Errors: 400 `invalid_password_reset` (param `key`; used, expired, forged), or the password validators' codes (param `password`). Single use: the key's hash covers the password, `last_login` and the user's emails. |
| `POST /api/v1/me/verification-email/` | ours (`IsAuthenticated`, Bearer; Part 2) → **204** sent · **409 `already_verified`** · **429 `verification_email_throttled`**. allauth's documented `auth/email/verify/resend` is the code-mode view (it always answers 409 with links), and `PUT account/email` exposes the whole email-management view, answers a bare 403 when throttled and mails a dead link for a verified address, so resend is our own endpoint. |
| `POST /api/auth/app/v1/auth/provider/token` | Part 3, "Continue with Google": `{provider:"google", process:"login", token:{client_id, id_token}}` → 200 like login (`meta.access_token`, refresh cookie set). 404 while `GOOGLE_OAUTH_CLIENT_ID` is blank. Errors (all 400, no `param` unless noted): `invalid_token` (param `token`: anything that isn't a good Google ID token for our client), `google_email_unverified`, `account_inactive`, `staff_password_login`, `google_link_requires_password`; 429 from the `login` bucket. See "Continue with Google" below. |
| `POST /api/auth/logout/` | ours → always 204 |

**Allow-list:** `AuthApiMiddleware` (`apps/accounts/middleware.py`, right after allauth's `AccountMiddleware`) handles every request under `/api/auth/`. Only the allauth endpoints above (login, signup, refresh, verify, password request and provider token POST; password reset GET and POST) and our logout answer; every other path or method under `/api/auth/` is 404 (allauth also mounts `config`, `auth/session`, `account/email`, `auth/email/verify/resend`, password change, phone endpoints, and the social `auth/provider/signup`, `auth/provider/redirect` and `account/providers`).

**CSRF:** allauth's app views are CSRF-exempt and parse any body as JSON whatever its Content-Type, so a cross-site `<form enctype="text/plain">` could log someone in. Every unsafe request under `/api/auth/` (not only refresh and logout) needs `Origin == FRONTEND_ORIGIN` exactly and `X-Requested-With: rumor-zero`, else **403 `csrf_failed`**. Through the relay Django sees `Host` = the backend and `Origin` = the frontend, so Django's own CSRF check couldn't work here; our logout view is `csrf_exempt` for that reason. SameSite=Lax on the cookie is a second layer.

**Cookies and secrets:** allauth's login and signup bodies carry three secrets in `meta`: `access_token`, `refresh_token` and `session_token` (the raw Django session key, which works as `X-Session-Token`). Refresh puts the new pair in `data`.
- The middleware removes `meta.refresh_token`, `meta.session_token` and `data.refresh_token` from every `/api/auth/` response; only the access token reaches JavaScript (memory only).
- A refresh token found there is moved into **`rz_refresh`**: `HttpOnly; SameSite=Lax; Path=/api/auth/; Max-Age=REFRESH_TOKEN_SECONDS` (seconds, 1 209 600 by default); `Secure` = `AUTH_COOKIE_SECURE`; no `Domain`, so it is a host-only cookie of `<FRONTEND>` (it arrives through the relay).
- **`rz_session=1`** is a non-secret hint (user decision 2026-10-01): same attributes but readable by JavaScript and `Path=/`. It is set and deleted together with `rz_refresh`, so an anonymous page load needs no refresh call.
- Every body under `/api/auth/` becomes JSON. A non-JSON or unparsable one, such as Django's DEBUG 500 page (which prints cookies), is replaced by `{"status": <code>}`. Our own errors use allauth's envelope `{"status", "errors":[{code, param?, message}]}`. Every response gets `Cache-Control: no-store`.
- Login, signup, refresh, **verify, the password-reset calls and the Google sign-in** drop any incoming `Authorization` and `X-Session-Token` header (before the safe-method return, so a GET with a stale Bearer isn't answered 410 either), so they never run as an existing session (no 409 "already authenticated", no 410). A verification link and a reset key work for whoever holds them.
- **Verify normalisation:** a POST to `auth/email/verify` that allauth answers 401 becomes `200 {"status":200}`.
- **Reset daily cap:** a POST to `auth/password/request` first runs `reset_password_daily` in dry-run for the email in the body (skipped when `email` is missing or not a string: a per-key rate with no key raises, and allauth answers 400 anyway); a full bucket → 429. It is consumed for real only when the answer is 200.
- **Reset logs in:** a successful reset issues tokens like a login, so the middleware sets the cookies and **deletes the session behind this browser's old `rz_refresh` cookie** (`_ISSUING_ENDPOINTS`). Every other session ends on its next refresh: Django's `get_user` flushes a session whose auth hash no longer matches the new password (`test_refresh_fails_once_the_password_changes`). There is no eager sweep, because DB sessions aren't indexed by user. As with logout, an access token already issued stays valid for up to 15 min.
- **Refresh:** the body is replaced with `{"refresh_token": <cookie>}`; a token sent in the body is never used. No cookie → 401 without touching the database. Two `rz_refresh` cookies (refresh or logout) → 400 `invalid_cookie`. A refresh answered 400/401/410 deletes both cookies; a 5xx keeps them.
- **Log in again** (login, signup, reset or Google sign-in with an old `rz_refresh` cookie): the session behind the old cookie is deleted.

**Turnstile:** on sign-up only (guide §4.1), checked **before allauth runs**, because Django validates all form fields together: a form-level check would still answer "email taken" to a bot.
- First allauth's own `signup` limit in dry-run mode (the same IP bucket): when it is full → 429 and Cloudflare isn't asked.
- `turnstile_token` missing, not a string, blank or over 2048 characters → 400 `turnstile_failed` (param `turnstile_token`).
- `apps/accounts/turnstile.py` posts `secret`, `response`, `remoteip` and an `idempotency_key` to `https://challenges.cloudflare.com/turnstile/v0/siteverify` with the standard library (5 s timeout, one retry with the same key after a network error or 5xx). A rejected token → 400 `turnstile_failed`. **Fails closed** (user decision 2026-10-01): siteverify unreachable, unreadable, or answering `invalid-input-secret`, `missing-input-secret` or `internal-error` → 400 `turnstile_unavailable` "We couldn't run the bot check. Try again in a minute." A rejected secret is logged naming `TURNSTILE_SECRET_KEY`. The token and secret are never logged.
- A failed or unavailable check counts against the signup limit; a passing one is counted by allauth itself, so each attempt counts once.
- Local dev and CI use Cloudflare's always-pass test keys (site key `1x00000000000000000000AA`, secret `1x0000000000000000000000000000000AA`; the secret `2x0000000000000000000000000000000AA` always fails). The test token is `XXXX.DUMMY.TOKEN.XXXX`.

**Continue with Google (Part 3):** `AuthApiMiddleware` and `SocialAccountAdapter` around allauth's `provider/token`; allauth does the verification.
- **Before allauth** (`google.check_provider_token_request`, no network): after the CSRF guard and the `login` rate limit, the body must be `provider: "google"`, `process: "login"` (not `connect`, which is Part 14's) and a `token` dict whose `client_id` equals `GOOGLE_OAUTH_CLIENT_ID` and whose `id_token` is a string of at most 4096 characters with an unverified header `alg: RS256` and a non-empty `kid` of at most 200 characters; anything else is 400 `invalid_token`. This closes two 500s in allauth 65.19.5: a header without `kid` (KeyError) and `alg: HS256` checked against Google's RSA key (TypeError). A `client_id` mismatch logs a warning that names both variables, never the values.
- **allauth then checks** the signature (it fetches Google's certificates on every call: no cache, 5 s timeout), `iss`, `aud`, `exp` and `iat` (no leeway: a server clock behind Google's gives occasional 400s) and one-time `jti` (the shared cache). A failure is 400 `invalid_token`.
- **`SocialAccountAdapter.pre_social_login`** (after allauth's lookup, before any link, password wipe or save; each refusal is a 400 with no session, cookie or row left behind), in order:
  1. no Google email marked verified → `google_email_unverified` (this also guarantees a sign-up never pends);
  2. the matched user is inactive → `account_inactive` (allauth would link, and maybe wipe the password, before `perform_login` refuses);
  3. matched **by email** and the user is staff (moderator or superuser) → `staff_password_login`;
  4. matched by email, the address isn't `@gmail.com` and the token has no `hd` (Workspace) claim → `google_link_requires_password`. Google is authoritative for an address only when it hosts it; otherwise `email_verified` only means "verified when the account was created" and the address may have changed hands (Google's ID-token guide).

  A returning Google link (same `sub`) skips 3 and 4. A *new* person with any verified address can sign up.
- **New user** (`save_user`): username from Google's first name (`usernames.generate_username`: ASCII-folded, `[a-z0-9_]`, ≤ 20 characters, `ada`, else `ada_dddd`, else `member_xxxxxx`; reserved words and non-Latin names go to `member_…`; **never from the email address**, because the handle is public; user decision 2026-10-07), `is_email_verified=True`, an unusable password, a verified primary `EmailAddress`, a blank `display_name`. `populate_user` trims `extra_data` to `sub`, `email`, `email_verified` and `hd`.
- **Linking** (existing account, Gmail or Workspace address; user decision 2026-10-07): allauth's `wipe_password` makes the password unusable when the address was unverified (whoever signed up with someone else's address is locked out; other sessions end at their next refresh, because the session auth hash changed), then `connect()` fires `social_account_added`, whose receiver marks the `EmailAddress` verified (creating the row when the account has none) and sets `users.is_email_verified`. A verified address keeps its password. An access token issued earlier works for up to 15 min, as after logout.
- A closed popup: Google gives its button no event, so the page simply stays as it was.

**Tokens and sessions:**
- Refresh-token state lives in the Django session (jti → exp). allauth's own rotation removes the used token at once, without a lock, so two tabs refreshing together overwrite each other's session save, and a response lost after the commit strands the browser with a dead cookie. `RumorZeroJWTTokenStrategy.refresh_token()` therefore:
  1. locks the `django_session` row (`select_for_update`) for the whole refresh;
  2. validates the token against the session read inside the lock;
  3. keeps the used token valid for a **60 s grace period** (never longer than its own expiry) instead of removing it, and prunes expired ids;
  4. issues the new pair and saves the session; a session deleted meanwhile (`UpdateError`) is a plain 400.
  It reuses allauth's internal helpers (`headless/tokens/strategies/jwt/internal.py`), so it is re-checked whenever allauth is upgraded.
- Access tokens are validated statelessly (signature and expiry), so one still works for up to 15 min after logout.
- The token session's lifetime is set at login (`set_expiry(REFRESH_TOKEN_SECONDS)`) and slides with each refresh. Admin sessions keep `SESSION_COOKIE_AGE`. Run `clearsessions` periodically (Part 9/17).
- Refresh goes through Django's `get_user`: an inactive user, or a changed password (session auth hash), ends every refresh token.
- `sid` in a token is the session key encrypted with a key derived from `DJANGO_SECRET_KEY`, so rotating that key logs everyone out (ENV_GUIDE §2.13).
- **Logout** deletes the session behind the cookie (only signature and expiry are checked, so a rotated cookie still identifies it), which ends every refresh token issued for it, and deletes both cookies. It is idempotent.

**Flows** (frontend `lib/api` and `lib/auth`):

| Flow | Steps |
|---|---|
| Sign up (a2) | email + username (live check `GET /api/v1/auth/username-available/?u=`, 400 ms debounce) + password + the Turnstile token → allauth signup → access token in memory + refresh cookie → verification email sent → **`/verify-email`** (user decision 2026-10-06; "Continue browsing read-only" goes on to `safeNextPath(?next=)` or `/home`, where the unverified banner shows). |
| Verify email (a4) | `/verify-email` is "check your inbox" (never redirected away): signed in and unverified → the address, a read-only callout, Resend with a 60 s countdown, "Continue browsing read-only"; signed in and verified → "Start posting"; anonymous → "Log in to resend". The link `<FRONTEND>/verify-email/{key}` opens `VerifyEmailStatus`: it waits for the session to leave `loading`, then **always** POSTs the key once (signed in or not): Verifying… → Verified ("Start posting", or "Log in to start posting" when anonymous; a signed-in tab reloads `/me` and tells the others) · already verified (a used link, a verified user) · expired ("Send a new link": inline resend when signed in, else "Log in to send a new link" → `/login?next=/verify-email`). The `email_confirmed` signal sets `users.is_email_verified` (only when the confirmed address is the user's current email). The route param is decoded once (`src/lib/auth/email-key.ts`: Next re-encodes every param, and allauth's key contains `:`, sent as `%3A`), then matched against `^[A-Za-z0-9_:-]{1,300}$`; a malformed link shows the expired state with no request. |
| Resend | `POST /api/v1/me/verification-email/` (banner Resend, `/verify-email`, the expired state). `useResendVerification` runs the 60 s countdown against a deadline (a throttled background tab doesn't stretch it), restarts it after a send or a 429, and on a 409 reloads `/me`. |
| Log in (a3) | email + password → tokens → `safeNextPath(?next=)` or `/home`. One dismissible banner on failure; allauth rate-limits failures. |
| Google (a2/a3) | `GoogleButton` (§10) loads `https://accounts.google.com/gsi/client` on the auth pages only, `initialize`s once per page and draws Google's own button (an iframe, "Continue with Google") above the form with an "or" rule. A credential → "Signing in with Google…" → `googleLogin` = `POST …/auth/provider/token {provider:"google", process:"login", token:{client_id, id_token}}` → `signInWithToken(access token)` → `useRedirectWhenLoggedIn` goes to `safeNextPath(?next=)` or `/home` (a Google sign-up never goes to `/verify-email`: it is already verified, and it skips Turnstile). Failures use the form's banner (`googleErrorMessage`). Only JS origins are registered at Google; no redirect URI, no client secret. |
| Forgot / reset (a5/a6) | `/forgot-password`: an idle form and a separate **sent** state; every 200 shows "If an account exists for {typed email}, we've sent a link to reset your password. It expires in 24 hours." (errors: malformed email on the field, 429, 503, network). The link `<FRONTEND>/reset-password/{key}` shows a skeleton while `GET auth/password/reset` checks the key (400 → "This link has expired" + "Request a new link"; a check that can't run still shows the form, since the submit decides), then the form: new password (strength meter, 8-character minimum), confirm (mismatch error on that field), callout "This also signs you out on your other devices". Success: `signInWithToken`, toast "Password changed. You're logged in.", `/home`. Key format `^[0-9a-z-]{1,200}$`. |
| Stay logged in | `src/lib/auth/session.ts` (framework-free) behind `AuthProvider`. The access token lives **only in memory**, never in localStorage (guide §4.6). On load, refresh **only when the `rz_session` hint is present**, then `GET /api/v1/me/`. The next refresh is scheduled at `max(lifetime/2, lifetime − 60 s)` after a token arrives (the lifetime is `exp − iat`, so the browser's clock doesn't matter); a tab coming back into view refreshes at once if one is due. A refresh answered 400/401/403/410 → anonymous; a network error or 5xx → keep the state and retry after 2 s, 5 s, 15 s, then every 30 s while visible. On a 401 from the API: if a refresh finished in the last 10 s just retry, else refresh once and retry. Only the refresh POST runs inside the **Web Lock** `rz-refresh` (shared by all tabs; Web Locks aren't re-entrant, so `/me` never waits on it). If a refreshed token's `sub` differs from the current user (another account logged in in another tab), `/me` is reloaded. Login and logout are broadcast on `BroadcastChannel("rz-auth")`; an anonymous tab that hears "login" refreshes. **`user-changed`** (sent by `reloadMe()` after the email got verified) makes every *authenticated* tab reload `/me` once (`loadMe()`, which never posts, so there is no echo); an anonymous tab ignores it. `signInWithToken(token)` is the login for a password reset. |
| Log out | `POST /api/auth/logout/` inside the lock → on 204 clear memory, timers and user, broadcast → `/login`. On failure nothing changes and a toast says "Couldn't log out. Check your connection and try again." |

**Permissions:**
- `IsAuthenticated` for all writes.
- `IsEmailVerified` (`apps/accounts/permissions.py`, code `email_unverified`, 403; anonymous still gets 401) for creating posts (including emergencies), comments, likes, follows, reposts, reports, appeals and profile photos (unverified = read-only). Bookmarks are private, so they only need a login.
- `IsModerator` / `IsSeniorModerator` for admin.
- The superuser is created from your PC (ENV_GUIDE §2.6) and counts as verified (§2).

**Emails (Part 2):** templates in `backend/templates/account/email/`, rendered by allauth's `render_mail`.
- `.txt` files use `{% autoescape off %}`; `.html` files are `<!DOCTYPE html>` with a table layout, inline styles and every line under 998 characters (longer lines make Django quoted-printable-encode that part). `<prefix>_message.html` becomes the HTML alternative when it exists; the text part comes first.
- `base_message.txt` keeps `block content` (so any email we don't override still renders) and no longer prints the API host (`django.contrib.sites` isn't installed, so allauth's stock footer showed "localhost:8000"). Copy says only "Rumor Zero": no organisation names, no site domain.
- `base_message.html`: the logo `<img src="{{ email_logo_url }}" alt="Rumor Zero" width="160">` in an `inverse-surface` `#283044` cell, body on `#ffffff` with text `#131b2e`/`#3c4946`, a button `secondary` `#006398` on `#ffffff`, and the link repeated as text. The hex values are copied from the Stitch tokens, because email clients can't read CSS variables (so they are the one place raw hex is allowed outside the logo build).
- Verification: subject "Verify your email" (sign-up variant "Welcome to Rumor Zero: verify your email"), body with the button and "This link expires 24 hours after it was sent." Reset: "Reset your password", "This link expires in 24 hours and works once. If you didn't ask for it, ignore this email: your password stays the same." Subjects get the `[Rumor Zero] ` prefix.
- Every link and the logo use `FRONTEND_ORIGIN`; `From` is `DEFAULT_FROM_EMAIL`. `test_emails.py` checks both, the HTML alternative, line lengths and the Brevo payload (anymail's Brevo backend builds sender, subject, `textContent` and `htmlContent` without any network call; its test backend takes the same messages).
- `EMAIL_PROVIDER=file` writes every email to `backend/tmp/mail/*.log` (git-ignored). Playwright starts Django that way, and `frontend/e2e/mailbox.ts` reads the newest email for a unique address and takes the first `http://localhost:3000/(verify-email|reset-password)/…` link from the plain-text part.

## 8. Moderation panel: Django Admin (guide §8; d2 is a reference only)

Part 10 built the panel in `apps/moderation/` (`rules.py` the pure rules, `services.py` the five actions, `roles.py` the groups, `admin.py` the screens) and, for accounts and settings, in `apps/accounts/admin.py` and `apps/core/admin.py`.

- **Roles** (Groups and model permissions, synced from `User.role` by `User.save`; the groups and their permissions are created by data migration `moderation.0002_role_groups`, which holds its own frozen copy of the lists in `roles.py`; `test_roles.py` fails until a later change to a list adds a migration):
  - *Moderator* (group "Moderators"): `posts.view_post`, `posts.change_post` (gates the actions; the page itself stays read-only), `reports.view_report`, `social.view_comment`, `social.change_comment`, `accounts.view_user`, `core.view_platformsettings`, `moderation.view_appeal` (Part 11, migration `0004`), `reputation.view_reputationevent` (Part 11B, migration `0005_reputation_permission`; user decision 2026-10-13: moderators and up read the whole credibility ledger), `moderation.block_emergency_posting` (Part 11C, migration `0007_emergency_permission`; user decision 2026-10-19: moderators and up, seniors through the Moderators group), `moderation.moderate_profile_photos` and `accounts.view_avatar` (Part 14B, migration `0009_photo_permissions`; moderators and up). Each later list change adds a migration with its own frozen lists; `0005`'s reverse returns to `0004`'s lists, `0007`'s to `0005`'s, `0009`'s to `0007`'s.
  - *Senior moderator* (in both groups; extras only): `accounts.change_user`, `accounts.delete_user`, `core.change_platformsettings`, `moderation.view_moderationaction`, `admin.view_logentry`.

| Capability | Non-staff | Moderator | Senior | Superuser |
|---|---|---|---|---|
| Admin login | redirect to login | ✓ | ✓ | ✓ |
| Queue, post pages, a post's moderation history (inline) | none | ✓ | ✓ | ✓ |
| The post actions (Mark verified/FALSE, Dismiss, Remove, Escalate, Restore, Keep removed, Demote emergency) | none | ✓ (not own posts) | ✓ (not own posts) | ✓ (own posts too) |
| Block / Unblock emergency posting (Part 11C); an account's emergency blocks on its page | none | ✓ (not superusers or self) | ✓ (not superusers or self) | ✓ |
| Reports list; comments with Hide/Unhide | none | ✓ | ✓ | ✓ |
| Users: view | none | ✓ | ✓ | ✓ |
| Users: `role`, `is_active` (suspend), Mark email verified | none | none | ✓ others; not superusers or self | ✓ |
| Users: delete | none | none | ✓ one at a time; not superusers or self | ✓ |
| Users: email, password, profile, `is_superuser` | none | none | none | ✓ |
| Platform settings (all eleven fields) | none | view | edit | ✓ |
| Full moderation log; Django's admin log; History pages | none | none | ✓ | ✓ |
| Credibility ledger (the whole list, a post's events, an account's link; read-only) | none | ✓ | ✓ | ✓ |
| Bookmarks, likes, follows, reposts | none | none | none | ✓ (unchanged) |

- **Review queue:** `PostAdmin`, which is **read-only for everyone** (`has_change_permission` is always False; a POST to a post's change URL is a 403). Every change goes through `moderation.services`.
  - **"Show" filter:** the default is the *review queue*: `status='under_review'` **or** (`status='removed'` and `flagged_reason='appeal'`, a removal appeal), not deleted by the author. "All posts" shows everything. Choosing a Status, or "Deleted by author", also leaves the queue (otherwise "Status: removed" on top of the queue would always be empty).
  - Columns: the claim (excerpt, links to the page), type, status, reason (`flagged_reason`), **pipeline** ("FALSE 92%", "TRUE 95%", "Inconclusive 40%", "—": Part 9 asked to show the late verdict), reports (`report_count`, sortable), **waiting** (`timesince(review_started_at)`, sortable), posted (`created_at`, sortable), escalated, emergency (Active / Ended / —: *ended* means expired or demoted), author.
  - Filters: Show, **appeal** (FALSE label / Removal: posts with an *open* appeal of that kind; Part 11), flagged reason, type, status, Escalated, "Deleted by author", and **emergency** (Active / Ended, Part 11C: choosing it leaves the queue, like a status, so a moderator can find an active emergency that isn't under review and demote it). The Reason column reads "Appeal (FALSE label)" or "Appeal (removal)" (the flag is the same; the status tells them apart).
  - Default order: `-report_count`, then **in the queue since** ascending (longest wait first, nulls last), then `-created_at`, all after **active emergencies first** (Part 11C: `Case(When(active_emergency_q(Now()), then=1), default=0) DESC`; Postgres' `STATEMENT_TIMESTAMP()`; the Emergency column sorts by it). "In the queue since" is `review_started_at` for a post under review and the open appeal's `created_at` for a removed post (the *Waiting* column and its sort use the same expression).
  - Search: content, author username. 100 posts a page; the page uses a constant number of queries.
  - The post page: fields grouped as Post / Review / Pipeline / Emergency (all read-only), with three inlines, the **appeal** (kind, status, the author's reason, created, original moderator, resolved by and at; viewable with `moderation.view_appeal`, read-only, one query with its two moderators), **reports** (time, reporter, the reporter's account age when reporting, reason, details, whether it counts, status) and **moderation history** (time, action, moderator, from → to, public note, notes; visible with `posts.view_post`, so moderators see it without the full log), and **credibility events** (Part 11B: time, user, kind, "P / N" such as "N +1" or a reversal's "N −1", score after; oldest first; viewable with `reputation.view_reputationevent`, read-only, one query with the users).
- **The post actions** (eight since Part 11C), bulk actions on the list and buttons on the post page, each calling `moderation.services` once per post (own transaction, row locked, rules re-checked) and writing one `moderation_actions` row:
  - *Mark verified*, *Mark FALSE* (fact posts only; optional public note), *Dismiss reports*, *Remove posts* (optional "reason shown to the author"), *Escalate to senior*. *Restore post* and *Keep removed* (Part 11: the two ways to resolve a removal appeal; internal notes only, and the confirmation's status column reads "Under review" where Restore sends a checked fact to review) make it seven; *Demote emergency* is 11C. A button or a row is offered only when `rules.refusal` allows it: Restore and Keep removed need a removed post with an open removal appeal, Escalate is also offered there, and none of the appeal actions is offered to the moderator who made the first decision (seniors and superusers excepted). **`AppealAdmin`** lists every appeal read-only for moderators and up (created, post, author, kind, status, original moderator, resolved by and at; filters kind, status, created; search by the author's username); the author's words show on an appeal's own page, not in the list.
  - **Confirmation:** the first POST renders a page listing the posts that will change (claim, type, status → new status, reason, reports, pipeline) and the skipped ones with their reason, with the note fields (public note ≤ 500 code points, internal notes ≤ 2,000). It carries the evaluated, capped ids (at most **100** posts; more is an error) and **never** `select_across`: the apply step acts on exactly the posts shown. The form posts back to the same full URL, so the filters survive. The result is a success message ("Marked 3 posts verified.") and a warning for refusals found under the lock ("Skipped 2: 1 opinion: no verdict, 1 not under review.").
  - **Buttons on a post's page** sit in the object tools (outside the page's own form) and post to the full list (`?queue=all`, because an action's queryset is the filtered list); only the actions that apply to this post are offered (an opinion never gets the verdicts), and the moderator returns to the post page afterwards. A list filtered to opinions drops Mark verified/FALSE from its dropdown.
- **Logs (seniors only):** `ModerationActionAdmin`, the full moderation log (time, action, moderator, post snapshot linked while the post exists, from → to; filters action and time; search snapshot and moderator), and `LogEntryAdmin`, Django's admin log, which holds what has no `moderation_actions` kind: role and suspension changes, Mark email verified, platform settings and Hide/Unhide of comments, with old → new values. Both are read-only. An object's **History page** (accounts, platform settings, comments, posts) also needs `admin.view_logentry` (`HistoryNeedsLog`); the History link is hidden from those who can't open it.
- **Accounts** (`UserAdmin`): a superuser has the whole form. A senior sees the page read-only except `role` and `is_active`, never sees the password field, can't edit, suspend or delete a superuser or themselves, has no password page and no bulk delete, and may run **Mark email verified** (`accounts.services.verify_email_by_staff`: verifies the account's own address, creating the allauth `EmailAddress` row if missing; skips verified accounts; logged "Marked email verified"). **Suspension** is `is_active=False`: allauth refuses login, `JWTAuthentication` refuses the access token and a refresh fails; the account's content stays up. **Deleting** an account shows a summary (a count per kind of what goes with it, never the rows' text: bookmarks are private) and asks for no permission on the cascaded models; an account that **wrote admin log entries can't be deleted, only suspended**, so the log keeps its records. The change message carries values ("Role: moderator → senior moderator.", "Active: yes → no.").
- Comments (Part 7): *Hide comments* and *Unhide comments* bulk actions on a read-only `CommentAdmin` (list: text, author, post, hidden, deleted; filters: hidden, "By deleted at", created; search: text, username; no add, change or delete). Both need `social.change_comment`, which the Moderators group holds. Each change writes Django's own admin log entry ("Hidden" / "Unhidden"), because `moderation_actions` has no comment kind. Unhide doesn't undelete a comment its author deleted. `LikeAdmin` is read-only.
- **Demote emergency** (Part 11C): a button and bulk action offered only on an active emergency (`rules.refusal` → `not_active_emergency` otherwise, in any status), internal notes only, dropped from an opinions-only list like the verdicts. The confirmation tables gain an **Emergency** column (Active / Ended / —); Demote's "after" cell and Mark FALSE's on an active emergency add "(priority ends)", and Mark FALSE's adds "author blocked N days" when it will block (an emergency not already FALSE before the review, N > 0).
- **Block / Unblock emergency posting** (Part 11C, `UserAdmin`): two bulk actions gated on `moderation.block_emergency_posting` (moderators hold it, so a view-only account list still offers them), each with a confirmation page (`moderation/admin/confirm_account_action.html`: the account, its block now and after, the skipped ones with their reason, internal notes) that posts back the shown, capped ids (100) and never trusts `select_across`; malformed ids are dropped first. They call `moderation.services.block_emergency_posting` / `unblock_emergency_posting` (account lock, refusals `superuser_account`, `own_account`, `no_block_length`, `already_blocked`, `not_blocked`, `no_account`). A list filter "Emergency posting" (Blocked / Not blocked); `emergency_blocked_until` stays read-only; the account's page lists its block and unblock rows (time, action, by, post link, until, notes) as a read-only **Emergency blocks** field for holders of the permission (a field, not an inline: an inline formset would make the account form's own POST carry its management form).
- **Profile photos** (Part 14B; user decisions 2026-10-21). Three bulk actions gated on `moderation.moderate_profile_photos`: **Remove photo**, **Block photo uploads** (also removes the photo) and **Allow photo uploads**, through `moderation.services.remove_photo` / `block_photo_uploads` / `allow_photo_uploads` (account lock; refusals `no_account`, `superuser_account`, `own_account`, `no_photo`, `uploads_already_blocked`, `uploads_not_blocked`; the photo state is read from the locked row). They share the Part 11C confirmation flow (`AccountActionsMixin` in `apps/accounts/admin.py`, one `AccountActionSpec` per action; `moderation/admin/confirm_account_action.html` takes its column headings and the list to go back to from the context): the account, its photo state now and after, the skipped ones with their reason, internal notes only, at most 100 accounts, the shown ids posted back, malformed ids dropped. **`AvatarAdmin`** (`accounts.view_avatar`, moderators and up) lists the accounts that have a photo, newest change first, with a thumbnail (the public 96 px URL: the admin is on the backend host that serves it), a link to the account, `bytes_total` and the time; search by username; no add, change or delete; Remove photo and Block photo uploads only (an avatar's primary key is its account's id). **`UserAdmin`** has all three, so an account without a photo can still be blocked or allowed; a list filter "Photo uploads" (Blocked / Allowed); and a read-only **Photo** field on the account page (the thumbnail or "No photo", "Uploads blocked / allowed" and the account's `avatar_*` rows: time, action, by, notes) for holders of the permission, a field and not an inline for the reason given under "Block / Unblock emergency posting". The two bytea columns are `defer`red everywhere in the admin.
- Reposts and bookmarks (Part 7B): `RepostAdmin` is a read-only list (user, post, status at repost, created; filter by status at repost; search by username). `BookmarkAdmin` is read-only and **superuser-only** (`has_view_permission` is `is_superuser`, so Django also leaves it off the admin index): a moderator holding every bookmark permission still gets 403, because bookmarks are private (§4d).
- Notifications (Part 13): `NotificationAdmin` is a read-only list (time, recipient, type, outcome, actor, the post's excerpt, read; filters type, read, created; search by recipient or actor username; no add, change or delete, History for seniors only). No moderator permission was added, so only a superuser sees it by default: it is for support, and a person's notifications are not a moderation matter.
- Reports (Part 8): `ReportAdmin` is a read-only list (post, reporter, reason, status, whether it counts, created; filters status, reason, counts, created; search by reporter username; no add, change or delete). The list and `__str__` never show the details text; the page of one report does, for whoever may view it (moderators, `reports.view_report`). Reports are resolved only by the moderation services (`reports.services.resolve_open_reports` sets `status`, `resolved_by` and `resolved_at` together).
- **Credibility ledger** (Part 11B; `apps/reputation/admin.py`): `ReputationEventAdmin` is a read-only list for moderators and up (time, user, kind, P / N, score after, the post linked by its excerpt, "Reversed" from an `Exists`; filters kind and created; search by username; `?user__id__exact=<id>` lists one account's rows; no add, change or delete; constant queries). A row's own page shows its `moderation_action` and the row it `reverses`. **`UserAdmin`** shows a read-only **Credibility** field instead of the two raw columns in "Account state": "72 · 23 counted events · View events" when public, "New (2 counted events, score 55) · View events" otherwise, the link opening the account's rows. The two columns are never in a form.
- **Header:** the admin shows the logo (`core/brand/logo-admin.png`, §14: the full wordmark on its `#283044` plate, with the header taking the plate's colour) and "Rumor Zero moderation" (`templates/admin/base_site.html`; `site_header`, `site_title` and `index_title` are set in `apps/core/admin.py`; the login page shows it too). The image has an empty `alt`: the name is written beside it. It is served at `<BACKEND>/<ADMIN_URL_PATH>`. `/api/v1/me/` returns `admin_url` only to staff, so the sidebar "Moderation" link never exposes the path to others.

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
  - Codes: 400 validation · 401 unauthenticated · 403 forbidden (`email_unverified`, `not_author`, `cannot_report_own`…) · 404 · 409 conflict (`already_reported`, `already_appealed`) · 429 throttled (+`Retry-After`) · 503 `backend_waking` (relay).
- **Toggles are idempotent:** `POST` like/follow/repost/bookmark → 201 (200 if already there); `DELETE` → 204.
- **Performance:** every list uses `select_related("author")` plus annotated `like_count`, `comment_count`, `repost_count`, `liked_by_me`, `reposted_by_me`, `bookmarked_by_me`, `reported_by_me`. No N+1 (guide §9.3). Tests assert query counts.
- **Home feed (Following):**
  - Fan-out-on-read: posts by `followed ∪ {me}` **plus reposts by them** (Part 7B), ordered by activity time (`apps/social/timeline.py`). The sort key is `(activity_at, kind, post id, reposter id)`, newest first: a post is `(created_at, 0, post id, zero uuid)`, a repost `(created_at, 1, post id, reposter id)`. It is unique without the repost's own bigint id (post ids are uuids, so no single "item id" column exists; this key is the "item id" of the Part 7B brief). A repost of a post sorts before the post at the same instant.
  - **The cursor** is a bare base64url token of `<epoch microseconds>|<kind>|<post uuid>|<reposter uuid>` (an integer, not ISO text), decoded strictly (canonical form only): anything else, including a Part 6 cursor, is a JSON 404 `not_found`, and the client starts again from the top. New posts and reposts always sort above any cursor, so nothing is skipped or repeated across pages while they arrive. As with any timestamp cursor, a row that commits after a reader paged past its time is missed by that walk.
  - **The query:** each side is filtered "after the cursor" (with a redundant `created_at <= t`, because a bare OR can't use an index), ordered by its own columns (posts: `posts_recent_idx`; reposts: `created_at DESC, post_id DESC, user_id DESC`), cut to `2 × page_size + 1` rows, `UNION ALL`ed and ordered again. The post side is an index scan; the reposts side is a sequential scan and a top-N sort, about 11 to 18 ms at 300,000 reposts and 200 follows (recorded for Part 16).
  - **A page** is the longest prefix of the next `2 × page_size` rows that holds at most `page_size` distinct posts, showing the first (most recent) row of each; the rows it hid are consumed, so the cursor always advances and a page may hold fewer than `page_size` items (60 reposts of one post in a row give a one-item page). Profile lists never dedupe (you can't repost your own post), so their pages are full.
  - The first page is cached per user for `FEED_CACHE_SECONDS` (guide §9.2). **Only the keys of the page and the next cursor are cached** (user decision 2026-10-09; keys since 7B: a post and a repost are different items), under `social:following-feed:v2:<user_id>` → `{"items": [[microseconds, kind, post id, reposter id], …], "next": token | null}` with a strict shape check (malformed is a miss); the posts and reposts are loaded again on every request, so a deleted or removed post disappears at once (a repost of it becomes a stub), an undone repost leaves the page (reposts are matched on the pair **and** their time, so an undone-and-redone one doesn't show at its old place), a label is the original's live one, and likes and counts (Part 7) are never stale (a page may then hold fewer than 20, or none with a next cursor: the client offers "Load more"). Only a first page asked without `cursor` and `page_size` is cached. The cache is cleared (now and again at commit) when **you** post, follow, unfollow, repost or undo a repost; a post or repost by someone you follow reaches you after at most the TTL. One accepted limit: if the repost that won a page's once-per-page rule is undone, a follower's cached page has no item for that post until the TTL ends.
  - The `pinned` list (Part 11C) is computed on each first-page request (no `cursor`, or an empty one), cache hits included, by one query (`apps/posts/pinned.py`: the 3 newest active emergencies of `followed ∪ me` with the viewer's counts and a `Window(Count)` for `pinned_total`). The posts side of the page excludes every pinnable post and the reposts side excludes reposts **of** them (`post_id NOT IN` the pinnable ids, in the same SQL). The cached keys were filtered when cached: an emergency that ends while a follower's first page is cached is in neither list until the TTL (30 s) ends; accepted. **No shared cache for Recent's list** (it is one indexed query, and a cache of ids would still need a query for the viewer's flags; a deviation from the first design). First page +1 query: 4 on a miss and 3 on a hit (5 / 4 with a repost on the page).
  - Status polling is never cached.
- **Recent feed:** originals only, newest first, plus the site-wide `pinned` list on the first page (every active emergency is out of `results` on every page).
- **Recent is the first and default tab on `/home`; Following is the second, for signed-in users only** (user decision 2026-10-09).

**Feed response** (Recent, Following and profile post lists all use this shape from Part 4, so it never changes):

```json
{ "pinned": [ {Post} ], "pinned_total": 1,
  "results": [
    {"kind": "post",   "post": {Post}, "reposted_by": null, "activity_at": "…"},
    {"kind": "repost", "post": {Post}, "reposted_by": {"id": "uuid", "username": "bo", "display_name": "Bo", "avatar_url": null}, "activity_at": "…"} ],
  "next_cursor": "…" }
```

- `pinned` holds up to 3 active emergencies, newest first, on the first page of Recent and Following (Part 11C; §4b), with `pinned_total`; it is `[]` after the first page and on profile and bookmark lists. Recent never contains `kind: "repost"`. For a repost, `reposted_by` is the user summary and `activity_at` is the repost's time; for a post, `activity_at` is its `created_at` (on `GET /me/bookmarks/` it is the bookmark's time).
- A repost whose original was deleted or removed comes back as `"post": {"id": "uuid", "unavailable": true}` → "This post is no longer available".

**Post object** (all list and detail endpoints):

```json
{ "id": "uuid",
  "author": {"id": "uuid", "username": "ada", "display_name": "Ada", "avatar_url": null},
  "content": "…", "post_type": "fact", "status": "verified_true",
  "sources": [{"value": "10.1038/s41558-024-02102", "kind": "doi"},
              {"value": "https://www.iea.org/reports/renewables-2023", "kind": "url"}],
  "is_emergency": false, "emergency_active": false, "emergency_expires_at": null, "emergency_demoted": false,
  "confidence_score": "94.00", "verdict_source": "pipeline", "verdict_note": "",
  "like_count": 3, "comment_count": 1, "repost_count": 2,
  "liked_by_me": false, "reposted_by_me": false, "bookmarked_by_me": false, "reported_by_me": false,
  "is_mine": false, "can_appeal": false, "appeal_status": null, "removal_reason": "", "created_at": "…" }
```

- The object has exactly these **25 keys** (the tests pin them; Part 11 added `removal_reason`, Part 11C `emergency_demoted`); nothing else leaks (no `flagged_reason`, pipeline fields, `report_count` or moderation fields).
- **A removed post is a tombstone for everyone but its author** (Part 5; user decision 2026-10-09): the same 25 keys, with `content` `""`, `sources` `[]`, `verdict_note` `""`, `confidence_score` null and `verdict_source` null; the author block, `post_type`, `status: "removed"` and `created_at` stay (so the public sees whose post it was and when). Its author gets the full object, with `removal_reason` (below). The rule lives in `PostSerializer`, so no list can leak a removed post's text.
- `sources` is `[]` for opinions and for facts without sources; `kind` is derived from the stored value (§4c).
- `confidence_score` is non-null only for `verified_*` with `verdict_source=pipeline`.
- `verdict_source` is non-null only for `verified_*` (Part 9; the same in `GET /api/v1/posts/status/`): a post under review may already hold the pipeline's late TRUE, which stays private until a moderator acts, and a removed post shows none, its author included.
- `emergency_active` is computed at serialization with `now` (§4b); a list uses one `now` for its filters and its serializer. `emergency_demoted` (Part 11C) is `emergency_demoted_at is not None`: a moderator ended the priority early (Demote, or Mark FALSE while active); the post page uses it once the priority is over. A tombstone keeps both.
- **Counts (Parts 7, 7B and 8):** `like_count`, `comment_count`, `repost_count`, `liked_by_me`, `reposted_by_me`, `bookmarked_by_me` and `reported_by_me` are correlated subqueries added by `PostQuerySet.for_list(viewer)` (`apps/social/engagement.py`), so every list and the detail count in the same query as the posts (a list stays 1 query anonymous, 2 signed in). `comment_count` leaves out hidden and deleted comments; `repost_count` counts every repost row; the four `*_by_me` flags are `false` for visitors (`reported_by_me` is an `Exists` on `reports_pair_unique` and stays true for life, a dismissed report included). Nobody ever sees a bookmark or report count. `PostSerializer` reads them strictly (a post that was not counted raises), and the 201 answer of a new post gets explicit zeros (`engagement_defaults`). A removed post's tombstone keeps its counts. Nothing is cached: the Following feed caches only ids.
- `avatar_url` is `/api/v1/avatars/{user_id}/{avatar_version}-96.webp`, or null (initials). The 256 px size is used by `/me` and the profile (Part 14B).
- `flagged_reason`, report details and bookmark counts are never public.
- `appeal_status` (`open` \| `upheld` \| `overturned` \| null) is only returned to the author; `can_appeal` is true for their `verified_false` or `removed` posts that have no appeal (open or resolved); false for everyone else. **`removal_reason`** (Part 11; user decision 2026-10-13) is the `public_note` of the post's latest `removed` row for the author of a **removed** post, and `""` for everyone else and every other post (`verdict_note` keeps meaning only the label's note). All three come from `PostQuerySet.for_list(viewer)` (`apps/moderation/queries.py`: two correlated subqueries, no extra query; `PostSerializer` reads them strictly, a new post gets `appeal_defaults`).
- The public `reputation` block (`{"score": 72 | null, "sample": 23}`) is on user objects (profile, user rows, people search), **not** on post authors.

**Endpoint index** (the part that adds each):

| Part | Method & path | Purpose |
|---|---|---|
| 0A | GET `/api/health/` · GET `/api/health/deep/` | health |
| 1 | POST `/api/auth/app/v1/auth/signup`, `/api/auth/app/v1/auth/login`, `/api/auth/app/v1/tokens/refresh` (allauth; no trailing slash) · POST `/api/auth/logout/` · GET `/api/v1/auth/username-available/?u=` · GET `/api/v1/me/` | auth core (§7; shapes below) |
| 2 | POST allauth `…/auth/email/verify` · POST `…/auth/password/request` · GET + POST `…/auth/password/reset` · POST `/api/v1/me/verification-email/` (ours; allauth's `…/auth/email/verify/resend` stays closed) | email flows (§7) |
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

**Posts (Part 4):**
- `GET /api/v1/posts/` (public, never cached): the feed shape above, newest first (`created_at` then `id`), every status except `removed` and deleted posts and, since Part 11C, except the active emergencies (pinned on the first page instead), 20 per page (`?page_size=` up to 50): a first page is 2 queries anonymous and 3 signed in (the page, the pinned list, the user), a later page 1 and 2, whatever the page holds. The cursor's position is validated (a crafted one is 404 `not_found`, not a 500); a whole page sharing one timestamp falls back to a plain offset, which can't happen with microsecond timestamps.
- `POST /api/v1/posts/` `{content, post_type, sources?}` (verified user; `IsAuthenticated` + `IsEmailVerified`, throttle `post_create`, §3) → **201** with the post object. `content` is trimmed, 1–500 code points ("Write something first." / "Keep it to 500 characters."); `post_type` is required ("Choose Opinion or Fact."); undeclared fields (`status`, `author`, `created_at`, …) are ignored. Errors: 400 per field (`{"content": […]}`, `{"post_type": […]}`, `{"sources": …}` per §4c), `is_emergency: true` on an opinion is 400 `{"is_emergency": ["Only fact posts can be emergencies."]}`; an emergency the rules refuse (§4b) is **403** `{"detail": <plain words>, "code": "emergency_not_allowed", "reason", "next_allowed_at": ISO | null}` (a hand-built `Response`: an `APIException` with a dict detail would turn a null into the string "None"; a full fact quota or paused fact posts is this answer too, with reason `fact_quota`), 403 `email_unverified`, 403 `fact_posts_paused`, 429 `fact_quota_exceeded` (+ `Retry-After`), 429 `throttled`.
- `GET /api/v1/me/fact-quota/` (`IsAuthenticated`, never cached): `{limit, used, remaining, window_hours: 24, next_slot_at: ISO | null}`. `next_slot_at` is set only when nothing is left and `limit > 0`. Part 11C added `"emergency": {"allowed", "reason", "next_allowed_at", "block_days"}` (§4b; `block_days` is the current `emergency_false_cooldown_days`, so the composer states the real length); a login is enough, so an unverified account learns its `unverified` reason here. Still 2 queries (you, your fact posts of the window).
- `GET /api/v1/posts/emergencies/?feed=recent|following` (Part 11C; public for `recent`, the default; `following` needs a login → 401; any other value → 400 `{"feed": [...]}`; `never_cache`): every active emergency that feed pins, newest first, `{results: [Post], next_cursor}`, 20 a page up to 50 (`EmergencyPagination`: `TimestampCursorMixin`, a crafted cursor is a 404). 1 query anonymous, 2 signed in (both scopes). The literal route sits before `posts/<str:post_id>/`.

**Posts (Part 5):**
- `GET /api/v1/posts/{id}/` (public, never cached; sent with the token when there is one, so `is_mine` is right): the post object above. 1 query anonymous, 2 signed in. 404 `not_found` (JSON) for an unknown, malformed or **deleted** id, the author included. A removed post is the tombstone for everyone but its author. A stale Bearer token is a 401 here (the client refreshes and retries); the status endpoint avoids that.
- `DELETE /api/v1/posts/{id}/` (`IsAuthenticated`; no verified email needed, no throttle of its own) → **204**. 403 `not_author` for anyone else, 404 for a deleted or unknown post (so a second delete is 404), 401 anonymous. Any status can be deleted; the status is unchanged. Done by `posts.services.delete_post` (row lock, `deleted_at` and `updated_at` only).
- `GET /api/v1/posts/status/?ids=a,b` (public, no authentication at all, never cached, throttle `status_poll` 120/min per IP, §3): `{"results": [{id, status, confidence_score, verdict_source}]}` in the order asked, one query. `confidence_score` follows the post object's rule. A removed post answers `status: "removed"` with nulls; deleted and unknown ids are left out. 400 on `ids` (messages only) for none, more than **50** distinct, or a malformed id.
- The literal `status/` route is listed before `posts/<str:post_id>/`; ids are parsed by hand because a `<uuid:>` URL converter answers Django's HTML 404.

**Social graph (Part 6):**
- **Lookup:** the username in the URL is NFKC-normalised, trimmed and lower-cased (`lookup_name`, at most 64 characters, must fit `[a-z0-9_]{3,30}`) and matched exactly on the unique index. An unknown, **inactive** or malformed name is a JSON 404 `not_found`, never a 500 (a NUL byte used to be one).
- `GET /api/v1/users/{username}/` (public, never cached; a stale Bearer token is a 401 as on the post detail): `{id, username, display_name, bio, avatar_url, created_at, counts: {followers, following, posts, verified, false}, reputation: {score, sample}, is_following, is_me}` (10 keys). **One query anonymous, two signed in** (the counts and `is_following` are subquery annotations). `posts` counts the posts the public can see (not deleted, not removed); **`verified` and `false` also count the author's deleted posts**, so deleting can't erase a FALSE label (user decision 2026-10-09; removed posts are in neither, their status is `removed`). `reputation.score` is `null` until `reputation_sample` reaches 3; from Part 11B both come from the credibility ledger (§4a). `is_following` and `is_me` are `false` for visitors.
- `GET …/{username}/posts/` (public): the §9 feed envelope (`pinned: []`), newest first, `Post.objects.visible()` of that author (the author's own removed posts stay out too), `FeedPagination`, optional `?post_type=fact|opinion` (anything else: 400 on `post_type`). **On your own profile the list also holds your removed posts** (Part 11; user decision 2026-10-13): the author's tombstone with your text, the reason and the appeal; a repost of someone else's removed post is still the "no longer available" stub, and to every other viewer a removed post is not listed.
- `GET …/{username}/followers/` and `…/following/` (public): `{results: [row], next_cursor}`, newest follow first (`TimestampCursorMixin` guards the cursor: a crafted one is 404), row = `{id, username, display_name, bio, avatar_url, reputation, counts: {verified}, is_following, is_me}` (9 keys; `counts.verified` is Part 11B's, for c3's "· 84 verified": the person's verified posts, deleted ones included, the profile's own rule, as one correlated subquery); inactive users are left out; `is_following` is an `Exists` annotation, so the list is one query plus the lookup (3 signed in).
- `POST …/{username}/follow/` (`IsAuthenticated` + `IsEmailVerified`, throttle `follow`, `get_or_create`): **201** `{"is_following": true}` when new, **200** the same body when it already existed, **400 `cannot_follow_self`**, 404, 403 `email_unverified`, 401. `DELETE` (`IsAuthenticated` only): **204** always (also when you weren't following), 404 for an unknown user.
- `GET /api/v1/feed/` (`IsAuthenticated`, not verified-only; `never_cache`): posts by `followed ∪ {me}` that are visible, the §9 envelope (the pinned emergencies on the first page, Part 11C), `FeedPagination` ordering `(-created_at, -id)`. Cache: see "Home feed (Following)" above. 3 queries on a miss (the user, the ids, the posts), 2 on a hit, plus 1 for the pinned list on a first page.

**Likes and comments (Part 7):**
- **Which posts:** likes and comments need a post the public can see: a deleted, removed (its author too), unknown or malformed id is a JSON 404 `not_found`. Every other status is allowed, pending and under review included (ANALYSIS c1). Ids are parsed by hand (`parse_post_id`), never a `<uuid:>` converter.
- `POST /api/v1/posts/{id}/like/` (`IsAuthenticated` + `IsEmailVerified`, throttle `like`, `get_or_create`): **201** `{"liked": true}` when new, **200** the same body when it already existed; you may like your own post. `DELETE` (`IsAuthenticated` only): **204** always, also when there was no like and also on a removed post (a like can always be taken back); 404 only for an unknown, malformed or deleted post.
- `GET /api/v1/posts/{id}/comments/` (public, never cached; a stale Bearer token is a 401 as on the detail): `{results: [comment], next_cursor}`, **oldest first** on `(created_at, id)` (`CommentPagination`: `TimestampCursorMixin`, so a crafted cursor is 404), 20 per page (`?page_size=` up to 50). Hidden and deleted comments are left out, for everyone. 404 when the post isn't visible. **2 queries anonymous, 3 signed in**, however many comments.
- **Comment object (5 keys):** `{id, author: {id, username, display_name, avatar_url}, content, is_mine, created_at}`; `is_mine` is computed in Python from the request user. Nothing about moderation ever shows.
- `POST …/comments/` `{content}` (`IsAuthenticated` + `IsEmailVerified`, throttle `comment` on POST only, as `PostListView`) → **201** with the comment object. `content` is trimmed, 1–500 code points, with the posts' messages ("Write something first." / "Keep it to 500 characters."; `content_field()` is shared with `PostCreateSerializer`); undeclared fields (`author`, `is_hidden`, `created_at`) are ignored. 400 per field, 401, 403 `email_unverified`, 404, 429 `throttled`.
- `DELETE /api/v1/comments/{id}/` (`IsAuthenticated`; no verified email needed, no throttle of its own) → **204**: sets `deleted_at` under a row lock (`select_for_update`), so two simultaneous deletes give one success. 403 `not_author` for anyone else (the post's author included); 404 for an unknown, malformed, hidden or already-deleted comment, or one on a post the public can't see (so a second delete is 404).

**Reposts and bookmarks (Part 7B):**
- `POST /api/v1/posts/{id}/repost/` (`IsAuthenticated` + `IsEmailVerified`, throttle `repost`): **201** `{"reposted": true}` when new, **200** the same when it already existed (the first row and its `status_at_repost` are kept). Errors: 401, 403 `email_unverified`, **404** for an unknown, malformed, deleted or removed post (its author too), **409 `cannot_repost_own`** "You can't repost your own post.", **409 `cannot_repost_false`** "Posts labelled FALSE can't be reposted.", 429. `DELETE` (`IsAuthenticated` only): **204** always, also when there was nothing to take back and also when the original is deleted or removed; 404 only for an unknown or malformed id. Both clear your cached Following page.
- `POST /api/v1/posts/{id}/bookmark/` (`IsAuthenticated` only, throttle `bookmark`): **201** `{"bookmarked": true}` / **200**; 404 for an unknown, malformed, deleted or removed post; your own posts, FALSE ones and pending ones are fine. `DELETE`: **204** always, also on a removed post; 404 for an unknown, malformed or deleted one.
- `GET /api/v1/me/bookmarks/` (`IsAuthenticated`, not verified-only, never cached; a stale Bearer token is a 401): the §9 envelope (`pinned: []`), items `{"kind": "post", "post": {Post}, "reposted_by": null, "activity_at": <bookmark time>}`, newest bookmark first on `(created_at, id)` (`BookmarkPagination`: `TimestampCursorMixin`, so a crafted cursor is 404), `?page_size=` up to 50. Deleted and removed posts are dropped in the bookmark query itself, so pages stay full (the bookmark rows stay). **Only ever the caller's**; there is no route for anyone else's. **3 queries**: the user, the bookmark page, the posts.
- `GET /api/v1/feed/` and `GET /api/v1/users/{username}/posts/` return reposts (see "Home feed (Following)" above). Profile lists: the user's visible posts and **all** their reposts, ordered by activity; `?post_type=` filters a repost by its original's type. A repost of an original that is deleted or removed is `{"kind": "repost", "post": {"id": "uuid", "unavailable": true}, "reposted_by": {…}, "activity_at": "…"}`: no text, nothing else. **Queries:** the Following feed 4 on a miss and 3 on a hit when the page holds a repost (the user, the keys, the posts, the reposts), one fewer when it holds only posts; a profile 3 anonymous and 4 signed in.

**Reports (Part 8):**
- `POST /api/v1/posts/{id}/report/` `{reason, details?}` (`IsAuthenticated` + `IsEmailVerified`, throttle `report`, POST only: any other method is 405, `never_cache`): **201** `{"reported": true}` whether or not this report sent the post to review. Errors: 401, 403 `email_unverified`, 429 (+ `Retry-After`), **404** for an unknown, malformed, deleted or removed post (its author too), **400** per field (`{"reason": ["Choose a reason."]}`, `{"details": [...]}`), **403 `cannot_report_own`** "You can't report your own post.", **409 `already_reported`** "You already reported this post.". The rules and their order are in §5. Every visible status can be reported, pending and under review included; the same five reasons apply to facts and opinions.
- `POST /api/v1/posts/{id}/appeal/` `{reason?}` (`IsAuthenticated` + `IsEmailVerified`, throttle `appeal` 5 a day, **POST only**: the throttle is not applied to other methods, which are 405, `never_cache`): **201** with the post object as its author now sees it (a FALSE post comes back `under_review` with `appeal_status: "open"`; a removed post stays `removed` with its text). `reason` is optional, trimmed, at most 500 code points (400 `{"reason": ["Keep it to 500 characters."]}`). Errors: 401, 403 `email_unverified` (neither counts against the allowance), 429 (+ `Retry-After`; from the throttle on every answer counts), **404** for a malformed, unknown or deleted id (its author too), **403 `not_author`**, **409 `already_appealed`** "You already asked for another look at this post." (one appeal per post for life; it wins over `not_appealable`), **409 `not_appealable`** "Only posts labelled FALSE or removed can be appealed.". The service (`moderation.services.file_appeal`) locks the post with `FOR NO KEY UPDATE`, so two simultaneous appeals give one `Appeal`; the rules and their order are in §4.
- The post object's `reported_by_me` says whether *you* reported it; no report, count, reason or reporter is ever public (`report_count` and `flagged_reason` stay out of the object).

**Pipeline (Part 9):**
- `POST /api/internal/tick/` (no user authentication, no throttle, `never_cache`; header `X-RZ-Cron-Secret`): **200** `{"processed": n}` after checking up to 10 due fact posts within a 25 s budget (§6). A missing, wrong or non-ASCII secret is **403** `permission_denied` and checks nothing; any other method is **405**. A stale Bearer header is ignored.
- A fact post's 201 answer is always `pending`: the check runs after the commit, and the page's status polling (§10, Part 5) picks the verdict up (the first poll comes after 10 s).

**Auth payloads (Part 1):**
- `GET /api/v1/me/` (`IsAuthenticated`, never cached, **two queries**: the user, and the `google_connected` `exists()` check): `{id, username, display_name, bio, email, is_email_verified, role, has_usable_password, google_connected, avatar_url, avatar_uploads_blocked, public_score}` (12 keys; Part 14B: `avatar_url` is the 256 px image, and `avatar_uploads_blocked` lets the settings card show the block before anyone picks a file). `bio` and `public_score` (`reputation.scoring.public_score`: the score once the sample reaches 3, else null) are columns of the user row (Part 14), so the count stays two. `google_connected` is true when the user has a Google `SocialAccount` (Part 3); `avatar_url` follows the rule above. Staff (`is_staff`: moderators and superusers) also get `admin_url`, the absolute Django Admin URL on the backend host. Anonymous → 401 `not_authenticated`.
- `PUT /api/v1/me/avatar/` (Part 14B; multipart `file`; `IsAuthenticated` + `IsEmailVerified` + not blocked, scope `avatar_upload`, never cached): 200 with the new `/me` object. Refusals are `{"detail", "code"}`: 403 `email_unverified`, 403 `photo_uploads_blocked`; 400 `photo_missing`, `photo_too_large`, `photo_unsupported`, `photo_too_small`, `photo_too_many_pixels`; 415 for a body that is not multipart; 429 from the throttle; 503 `photo_busy` with `Retry-After: 5`. `DELETE /api/v1/me/avatar/` (`IsAuthenticated`, no throttle): 204, also when there is no photo. `GET|HEAD /api/v1/avatars/{user_id}/{version}-{96|256}.webp`: public image bytes (§4e).
- `PATCH /api/v1/me/` (Part 14; `IsAuthenticated` + `IsEmailVerified`, scope `profile_update`): body `{display_name?, username?, bio?}`, answers 200 with the `/me` object. A field error is `{"field": ["message"]}` (400); a taken username is `{"username": ["That username is taken."]}`. Other keys are ignored.
- `POST /api/v1/me/password/` (Part 14; scope `password_change`): `{current_password, new_password}` → 204 · 400 on the field · **409 `password_not_set`**.
- `GET /api/v1/me/export/` (Part 14; scope `data_export`): a JSON download (`Content-Disposition: attachment; filename="rumor-zero-<username>-<YYYY-MM-DD>.json"`), `{format: "rumor-zero-export", version: 1, exported_at, account, posts, comments, likes, following, followers, bookmarks, reposts, reports, appeals, credibility_history, notifications}`. Thirteen queries whatever the volume (Part 14B added the photo). `account` also holds `photo` (`{format: "webp", size: 256, data: <base64>}` or null) and `photo_uploads_blocked`. It holds your own posts (deleted and removed ones included, with the removal reason), comments, likes, bookmarks, reposts with `status_at_repost`, follows (the other person's id and public username), your reports and appeals (never `counts_toward_threshold`, a moderator's identity or `notes`), the whole credibility ledger (reversals included, without the live `appeal` state) and the notifications you received (actor username or null). Never: another person's email, role or score, `search_vector`, `pipeline_result`, `flagged_reason`, `report_count`.
- `DELETE /api/v1/me/` (Part 14; scope `account_delete`): `{password}` or `{username}` → 204 (cookies expired) · 400 on the field · **403 `staff_account`**.
- `GET /api/v1/auth/username-available/?u=` (no authentication, `username_check` 30/min per IP, never cached, at most one query): normalises like sign-up (NFKC, trimmed, lowercase), then answers `{username, available, reason: null|"invalid"|"reserved"|"taken", message}`. Input over 64 characters is `invalid` without normalising; a missing `u` → 400 `{"u": [...]}`.

**Stats and credibility payloads (11B, 11D):**
- `GET /api/v1/posts/{id}/stats/` (Part 11D; public, **never authenticates** (`authentication_classes = []`, so a stale token isn't a 401), `never_cache`, no throttle yet (Part 16)):
  - Visibility: an unknown, malformed or **deleted** id is a JSON 404, and so is a **removed** post, **for everyone, its author included** (the rule of likes, comments and reposts; nothing renders stats for it). This tightens "the same as the detail endpoint".
  - Returns exactly six keys: `{confidence_score, confidence_threshold, verdict_source, seconds_to_verdict, verdict_at, daily: [{date, reposts, likes, comments}]}`.
  - `confidence_score` and `verdict_source` are the post object's own values (`shown_confidence`, `shown_verdict_source`), so a late pipeline TRUE held under review stays private. `confidence_threshold` is **today's** `confidence_threshold` setting, set only when `confidence_score` is (pipeline labels only; never for a moderator's verdict). The threshold at the time of the check is not stored (follow-up).
  - `verdict_at` is set only for `verified_*` posts: the pipeline's `pipeline_checked_at`, or for a moderator's label the `created_at` of the latest `verified`/`marked_false` audit row whose `to_status` is the post's current status (**not** `moderated_at`, which every later moderator action overwrites; no row → null). `seconds_to_verdict` is `max(0, verdict_at − created_at)` in whole seconds, null when `verdict_at` is. A pending, published or under-review post has all five check fields null.
  - `daily` is always **14 entries**, zero-filled, from the UTC date of `created_at` (day 0 is a partial day), counted by `TruncDate(created_at, UTC)` inside `[midnight(day 0), +14 days)` so each series is a range scan of its `(post, created_at)` index (comments use the partial index's predicate: not hidden, not deleted). Likes and reposts that were taken back are hard-deleted and so absent. The payload depends only on the post and its rows, never on the clock.
  - **2 queries whatever the activity** (the post with a correlated moderator-verdict-time subquery, then one `UNION ALL` of the three grouped counts), plus one when the platform-settings cache is cold. Uncached.
- `GET /api/v1/users/{username}/reputation/` (Part 11B; public, **never authenticates** (`authentication_classes = []`, so a stale token isn't a 401: the answer doesn't depend on who asks), `never_cache`, no throttle; the username is looked up as on the profile, so an unknown, inactive or malformed one is a JSON 404):
  - `{"score": 72 | null, "sample": 23, "verified": 20, "false": 3, "removed": 1, "recent": [{"kind", "label", "post_id", "created_at", "reversed"}]}`;
  - `verified`, `false` and `removed` count the account's posts **by status, deleted ones included** (the profile header's rule, so the two never disagree);
  - `recent` is the last 10 **own-post** rows (`fact_true`, `fact_false`, `emergency_false`, `post_removed`), newest first, with `reversed` (an `Exists`); repost rows, report credits and reversal rows never appear (user decision 2026-10-13). `post_id` is null when the author deleted the post (or it is gone). No weight, `score_after`, reporter, moderator or reversal link is ever in it;
  - **2 queries** (the account with its three counts, then the rows), whatever the ledger holds;
  - Part 11D adds `trend: [30 × {date, score}]`, **null while `score` is null**: the 30 UTC days ending **today** (oldest first), each the last row's `score_after` of that UTC day (rows have strictly increasing times, so no ties), carried forward over quiet days, starting from the last `score_after` before the window (50 for a new ledger). Once the score is public the earlier days show the raw `score_after`, including days before the third counted event. Only `{date, score}`: nothing private. **3 queries when public, 2 when hidden** (the account with the baseline as a scalar subquery and its counts; the recent rows; one `DISTINCT ON (day)` query).
- `GET /api/v1/me/reputation/events/` (Part 11B; `IsAuthenticated`, `never_cache`): your whole ledger, newest first, reversal rows included, `{results, next_cursor}` (`TimestampCursorMixin` on `(-created_at, -id)`, 20 per page, `?page_size=` up to 50, a crafted cursor is a 404). Only ever your own. **2 queries** (you, then the page with its posts, their appeals and the reversed rows joined). Row (11 keys): `{id, kind, label, positive, negative, score_after, created_at, post_id, reverses, reversed, appeal}`:
  - `positive`/`negative` are decimal strings ("0.25", a reversal's "-1.00"); a reversal's `label` is "Reversed: <the row's label>" and `reverses` its id;
  - `post_id` follows the public rule (null for a deleted post);
  - `appeal` is set only on your **own negative rows that still stand** (`fact_false`, `emergency_false`, `post_removed`, not reversed): `{"status": "open" | "upheld" | "overturned" | null, "can_appeal": bool}`, where `can_appeal` is the post object's rule (a `verified_false` or `removed` post of yours, not deleted, with no appeal yet); every other row has `null` (a repost or a report has no appeal of its own).

**Search (guide §10; Part 12):** `GET /api/v1/search/?q=&type=posts|users&post_type=fact|opinion&status=pending|published|verified_true|verified_false|under_review&cursor=2..5`. Public, read-only, `never_cache`, throttle `search` (60/min per IP, §3); a Bearer token is still read (so `liked_by_me` and `is_following` are right; a stale one is a 401 like every list).
- **`q`:** control characters removed (tab and line breaks become spaces), trimmed, 1–200 code points. Missing or blank → 400 `{"q": ["Enter something to search for."]}`; over 200 → 400 `{"q": ["Keep it to 200 characters."]}`. `type` defaults to `posts`; any other value, an unknown `post_type`, an unknown `status` or `status=removed` → 400 on that field. The two filters are ANDed, and ignored for `type=users`.
- **Posts:** `Post.objects.visible()` (never removed or deleted; **nothing else is excluded**: pending, under review, active emergencies and suspended authors' posts are found, as in the feeds) filtered by `search_vector = SearchQuery(q, search_type="websearch", config="english")` and ordered by `SearchRank(F("search_vector"), query)` (an `F`, not the string: a string is wrapped in `SearchVector` and re-parses the stored vector's text with the wrong configuration), then newest, then id. Websearch syntax works: `"exact phrase"`, `-word`, `or`; stemming is Postgres's (`running` finds `run`, `runs`). A query with **no positive term** (`-foo`, `or`) answers an empty 200 with no database query (`!'foo'` walks the whole GIN index and matches nearly every post). Answer = the feed envelope (`pinned: []`, `pinned_total: 0`, `results` of `{kind:"post", post, reposted_by:null, activity_at}`, `next_cursor`), so `FeedList` renders it unchanged. 1 query for a visitor, 2 signed in.
- **People:** active users whose username **starts with** the query or whose display name has a word that does (the start, or after a space, hyphen or apostrophe; matched as typed, a phrase prefix). The query is NFKC-normalised, lower-cased, spaces collapsed, a leading `@` dropped and cut at 64 characters after normalising; text with no letter, digit or `_` is an empty 200. `%`, `_` and `\` are literal. Order: exact username, username prefix, name matches, A–Z by username inside each: **never by credibility** or followers. Rows are the 9-key follower rows (`reputation` block, `counts.verified`, `is_following`, `is_me`); the answer is `{results, next_cursor}` with no `pinned` keys. 1 query / 2 signed in.
- **Pagination (documented deviation from the cursor rule above):** rank order has no timestamp to put in a cursor, so the position is a **bounded offset**: 20 per page (fixed), at most **5 pages (100 results)**, `LIMIT 21 OFFSET (page−1)×20`. `next_cursor` is the next page number as a plain string (`"2"`..`"5"`), `null` when there is no 21st row or page 5 was reached. An empty or missing `cursor` is page 1; any other value outside `"2".."5"` is a 404 `Invalid cursor`, like every crafted cursor. Results can shift between pages while posts arrive (accepted). The helper is `apps.core.pagination.paginate_offset`.
- Nothing is leaked that the feeds don't show; source URLs and comments are not indexed. The search text is in the request URL (§12).

**Notifications (guide §11; Part 13):** all three endpoints need a login (`IsAuthenticated`, an unverified email is fine), are `never_cache`d, and share the throttle `notifications` (120/min per user, §3).
- `GET /api/v1/notifications/` → `{results: [...], next_cursor}`, newest first (`created_at`, then `id`; a `TimestampCursorMixin` pagination, so a crafted cursor is a 404 `Invalid cursor`), 20 a page (`?page_size=` up to 50). **2 queries** (the user, the page), whatever it holds: the actor, post and comment come in the same query (`select_related` + `only`, so no `pipeline_result` and no `search_vector`), and `following` is an `Exists`. Each item has eight keys: `id`, `type`, `outcome` (§2), `is_read`, `created_at`, `actor` (`{id, username, display_name, avatar_url}` plus `following` on a `follow` only; **null** for the five moderation types, a deleted account **and a suspended one**), `post` (`{id, excerpt, post_type, status}` or null; the excerpt is made on the server: whitespace collapsed, at most 140 code points and `…`) and `comment` (`{id, excerpt}` or null). Items whose post the author deleted are left out. No moderator, reason or reporter is ever in an item (a removal's reason is on the post, for its author).
- `GET /api/v1/notifications/unread-count/` → `{"count": n}`, exact, uncached, **2 queries** (the user, one count on `notifications_unread_idx`). The badge shows `99+` above 99.
- `POST /api/v1/notifications/mark-read/` body `{"ids": [uuid, …]}` (1 to 50) **or** `{"all": true}`, exactly one → `{"count": <unread left>}`. Only your own unread rows change; other people's and unknown ids are ignored (200). 400 (messages only) for neither, both, an empty list, more than 50, a non-uuid id, `{"all": false}` or a body that isn't an object. `all` locks the rows in id order first.
- **Which events send what** (called from the write services in the same transaction; the recipient is always the post's author unless noted): follow (recipient: the person followed, actor: the follower), like, comment (carries the comment), repost (actor: the reposter; only the original's author is told, not its reposters); `verdict` from the pipeline's label (`record_pipeline_result`, `labelled`) and from a moderator's Mark verified or Mark FALSE **only when the label changes** (`pre_review_status` differs from the new status: a Mark FALSE on a post that was already FALSE sends nothing); `under_review` from the pipeline (`entered_review`, a result or the last failed try) and from the report that reaches the threshold (`record_report` returned True; a merge into an existing review sends nothing); `removed` from Remove; `emergency_demoted` from Demote and from Mark FALSE on an active emergency (**with** the verdict); `appeal_resolved` (recipient `appeal.author`, `outcome` upheld or overturned) from every action that closes an appeal, **in addition to** the verdict or removal that came with it. Silent: Dismiss reports, Escalate, filing an appeal, the automatic emergency block and lift, bookmarks, and a moderator acting on their own post (only a superuser can). One action's items are stamped 1 µs apart (§2).
- **Known limits:** a like that commits just after `delete_post` leaves a stray row (the list filters it; the count can't join, so it counts until the item is read; accepted). Nothing is pruned: retention is a Part 16/17 follow-up, as is an idle cutoff for the 30-second poll of a visible but untouched tab (each poll is one Worker request).

## 10. Frontend conventions

- Server Components by default. `"use client"` only where there's state or events.
- All API calls go through `src/lib/api/client.ts` (relative `/api` base). **Never** call `BACKEND_ORIGIN` from the browser.
- Styling:
  - Tokens live only in `globals.css` `@theme`.
  - Use Stitch class names (`bg-surface-container-low`, `font-claim-headline text-claim-headline`, `max-w-reading`, `px-space-md`).
  - **No** Tailwind default palette, no arbitrary hex, only `rounded-lg`/`rounded-full`, `shadow-sm` only.
  - Fact text: `font-claim-headline text-claim-headline`. Opinion text: `font-claim-opinion text-claim-opinion italic`.
- User text is rendered as plain text (`whitespace-pre-wrap break-words`). Never `dangerouslySetInnerHTML` (ESLint `react/no-danger` and `npm run lint:tokens` both enforce it).
- **Design-system build (Part 0B):**
  - `globals.css` resets the Tailwind defaults (`--color-*`, `--font-*`, `--text-*`, `--radius-*`, `--shadow-*`), then holds the 49 DESIGN.md colour tokens, 13 type tokens, `--radius-lg`, the named spacing and `--container-*` widths. `npm run lint:tokens` fails on anything outside them.
  - `shadow-sm` is overridden to Tailwind v3's lighter value (`0 1px 2px 0 rgb(0 0 0 / 0.05)`), because Stitch was built on v3.
  - `@tailwindcss/forms` runs with `strategy: "class"`; each form primitive adds its own `form-*` class.
  - Utilities for the same CSS property never sit on one element together (CSS order, not class order, would decide). Variants are chosen with `cond ? a : b`, and components take their font through a prop (`mono`) rather than an override.
  - The icon font CSS is imported into `@layer components`, so the `text-[1rem]` size utilities still beat its 24px default.
  - Password strength is advisory: Weak / Fair / Good / Strong from `scorePassword()`; the Django validators decide.
  - `StatusBadge` is driven by the pure `statusBadgeSpec()` and `stripeTone()` in `src/lib/post-display.ts`, a one-to-one copy of the §4 badge table; a published opinion shows only its OPINION chip.
  - `<dialog>` modals: Esc and the close button call `onClose`; focus goes to the `data-autofocus` element (else the first control) and returns to the opener; a scrim click does not dismiss unless `dismissOnBackdrop` is set.
  - A server-rendered avatar `<img>` can fail before hydration, so `Avatar` also checks for an already-finished, zero-width image.
- Avatars use `<Avatar>`: the user's photo when `avatar_url` is set (14B), otherwise initials, and initials on load error. Icons use `<Icon name="…"/>` (Material Symbols, self-hosted).
- The brand is shown **only** through `<Logo/>` (§14). Never re-create the old text wordmark or the emblem tiles.
- **Layouts (Part 0C):** route groups `(marketing)` (MarketingNav + MarketingFooter), `(auth)` (AuthLayout: the a2 card with `<Logo size="lg"/>`) and `(app)` (AppShell); components in `src/components/shell/`.
  - AppShell (Stitch b1 classes): the `w-64` rail at ≥1280 px, a `w-16` icon dock at 768–1279 px (labels `sr-only xl:not-sr-only`, so links keep their names), and below 768 px a top bar (`<Logo size="sm"/>` + account avatar) plus a bottom bar. The fixed top bar (search → `GET /search?q=`, avatar) shows from 768 px. Pages choose their own container width.
  - Rail items: Home `/home`, Search, Notifications, Profile `/u/<username>`, Bookmarks, **New post** (opens the composer from Part 4), then Moderation (only with `admin_url`; Django Admin in a new tab), Settings and the user card with a menu (Profile, Settings, Log out).
  - Phones (user decision 2026-10-01): bottom tabs Home, Search, New post, Notifications, Profile; the top-bar avatar opens a bottom sheet with Bookmarks, Settings, Moderation, Log out.
  - **Logged out** (user decision 2026-10-01): only Home and Search, with Log in / Sign up in place of the user card and avatar; the bottom bar is Home, Search, Log in.
  - **Session states (Part 1):** the server render and the first client render are `loading` (the user isn't known yet). While loading, the user card (or Log in / Sign up), the top-bar avatar and the third bottom tab are same-size `Skeleton`s; the rail keeps its width. Without the `rz_session` hint the shell turns logged-out right after hydration.
  - **`/settings` (Part 14, Stitch c2 subset):** `src/features/settings/` (`SettingsPage`, `ProfileForm`, `AvatarUploader`, `photo-prep.ts`, `AccountSection`, `ChangePasswordModal`, `DataExportCard`, `DeleteAccountModal`, `settings-api.ts`, `messages.ts`). Five sections behind an anchor nav: Profile (**Part 14B: the `AvatarUploader` card first**, outside the form and its fieldset: a hidden `<input type=file accept="image/jpeg,image/png,image/webp">` behind an Upload / Change photo button; the browser checks in order the type, the size (20 MB), whether `createImageBitmap(file, {imageOrientation: "from-image"})` can decode it and that the short side is at least 128; then a square 96 px preview with **Use this photo** and Cancel; the upload shows a `ProgressBar` with a real percentage ("Uploading… 42%", "Saving…" at 100%) from `apiFetch`'s `onUploadProgress`, which swaps only the transport to XMLHttpRequest, wrapped in a `Response`, so the token, the single 401 refresh-and-retry, `signal` and `normalizeError` are one code path and progress restarts on the retry; Cancel aborts it and reloads `/me`; **Remove photo** needs no confirmation; a blocked account sees the reason and no Upload, an unverified one a disabled button and the hint, and both can still remove the photo; `photo-prep.ts` re-encodes every file to a centre-square JPEG of at most 1024 px on a white canvas, so GPS never leaves the device); the form: save bar only while dirty; username availability reuses `useUsernameAvailability`, skipped for your own name; locked with a notice while the email is unverified), Account (email and chip; Change password, or "Signed in with Google" with a Forgot-password link), Credibility (`<CredibilityPanel publicScore={user.public_score} defaultOpen />`), Your data (the export is fetched through `api.get` and saved as a `Blob` link) and the danger zone (a password, or the typed username, enables Delete; staff see the reason instead of the button). After a 204 the page calls `endSession()` (anonymous plus a `logout` broadcast, no request), tells the app frame through `AccountExitContext.begin()` so it doesn't send the visitor to `/login?next=/settings`, and goes to `/home` with the toast "Your account has been deleted."
  - **Route guard:** `PROTECTED_PREFIXES` (`/notifications`, `/bookmarks`, `/settings`; `src/lib/auth/route-guard.ts`) show a page skeleton while loading and send anonymous visitors to `/login?next=<path and query>` (`router.replace`). `/home`, `/search` and profiles stay public. Logging out goes to `/login` (never back to the protected page).
  - **`UnverifiedBanner`** at the top of `<main>` while `user.is_email_verified` is false: a warning `Alert` "Verify your email to post, comment and report. Check your inbox for the link." Since Part 2 it has a **Resend link** button with the 60 s countdown ("Resend link (42s)"): `(app)/layout.tsx` owns `useResendVerification` and answers with toasts, and passes `AppShell` only `onResend`, `resendSecondsLeft` and `resending`, so the shell stays presentational (`AppShell.test` renders it without the Auth and Toast providers).
  - **New post while unverified** (user decision 2026-10-06): the rail button and the bottom tab are `aria-disabled` (not `disabled`, so they stay focusable), with `aria-disabled:cursor-not-allowed aria-disabled:opacity-60`, no hover colour, and an `aria-describedby` hint "Verify your email to post." (a separate `sr-only` span with its own id for each copy, outside the button). A click calls `onNewPostBlocked`, which the layout turns into a toast: "Verify your email to post. Check your inbox, or resend the link from the banner." It becomes a normal button once `/me` says verified.
  - **Auth pages:** `/login`, `/signup` and `/forgot-password` stay prerendered, and so does `/verify-email`; `/verify-email/[key]` and `/reset-password/[key]` are dynamic (they take the key as a route param, pass it raw to a client component, and set `robots: noindex` and `referrer: no-referrer`, because the key is a single-use secret in the address). "Forgot password?" sits in a3's options row under the password field. Sign-up goes to `/verify-email` (`?next=` rides along), through a `submitted` ref that keeps `useRedirectWhenLoggedIn` from sending the new account to `/home`; a visitor who is already logged in still goes to `next ?? /home`. A logged-in visitor goes on to `safeNextPath(?next=)` or `/home`; `next` is read from `window.location` (useSearchParams on a static page needs a Suspense boundary). `safeNextPath` (`src/lib/auth/next-path.ts`) keeps only same-origin paths: no backslash or control character, no `//…` after resolving dot segments, and nothing under `/api`, `/login`, `/signup`, `/reset-password` or `/verify-email/…` (the key-bearing pages; `/verify-email` itself is allowed). The API relay also forwards `x-password-reset-key`.
  - **`GoogleButton`** (`src/features/auth/GoogleButton.tsx`, Part 3; loader `src/lib/google-identity.ts`, call `googleLogin` in `src/lib/auth/auth-api.ts`): Google's own rendered button, then a shared `Divider` ("or log in with email" on a3, "or continue with email" on a2). It can't be Stitch's custom button with the inline "G": Google returns an ID token only from its own button or One Tap. Options: `theme: outline`, `size: large`, `text: continue_with`, `shape: rectangular`, `logo_alignment: center`, `locale: en`, width = the card's width clamped to 200–400 px. The client ID comes from `NEXT_PUBLIC_GOOGLE_CLIENT_ID` (a `clientId` prop overrides it in tests); **empty renders nothing** (no button, no rule, no script). The script loads only here, on `/login` and `/signup`, once (`loadGoogleIdentity`); `initialize` runs once per page (Google keeps only the last call), with the credential routed through a module-level handler the mounted button replaces and releases on unmount. `busy`, `disabled`, `onError` and `onAttempt` are read through refs, because Google keeps the first callbacks. While another sign-in is submitting (`disabled`), or one Google sign-in is running, a credential is ignored. Failures go to the form's banner (`googleErrorMessage`: `invalid_token`, `google_email_unverified`, `account_inactive`, `staff_password_login`, `google_link_requires_password`, else the usual 429/503/network text); a script that can't load shows an inline error and keeps the rule. A closed popup has no event: nothing happens. Playwright pins an empty client ID for both servers, so E2E never reaches Google.
  - **Search (Part 12):** `/search` (Stitch b4) is a **static** page (`metadata`: title "Search", `robots: noindex, follow`, no `openGraph`) rendering `<Suspense><SearchPage/></Suspense>`; the client reads `useSearchParams()`, so a query, tab or chip change costs no Worker request. The address is the state: `?q=&type=posts|users&filter=all|facts|opinions|verified|false|review` (`search-params.ts`). The query box is a `next/form` GET to `/search` (hidden `type`/`filter` only when not the default), tabs Posts / People `router.push`, the six single-choice chips `router.replace` (pressing the chosen chip is All; no chips on People), and a missing `q` shows a prompt and requests nothing. Posts reuse `FeedList` (+ `useStatusPolling`, so a pending fact's badge updates); People reuse `UserRow` (credibility chip, Follow). The query's words are marked client-side (`highlight.ts`: text split into word runs, compared by a light stemmer, no HTML and no regular expression from user text; approximate by design). After page 5 the list says "That's the first 100 results. Try more specific words to narrow them down."; a 429 says "You're going too fast. Try again in a minute." Not built from b4: result counts, the sort menu, Primary Sources, the claim-data box, the contributor spotlight.
  - **Notifications (Part 13):** `UnreadCountProvider` (`features/notifications/`, mounted in `(app)/layout.tsx` above `ComposerProvider`) polls `GET /notifications/unread-count/` at once when a signed-in session is ready, then every 30 s **only while `document.visibilityState` isn't `hidden`**; a hidden tab stops the timer and aborts the request, coming back polls at once; errors are silent. `useUnreadCount()` gives `{count, arrivals, set, adjust}`: `set` and `adjust` bump a version, so a poll that started before a local change is dropped when it lands; `arrivals` rises when a poll sees *more* than it knew (never on the first answer). `AppShell` stays presentational (`unreadCount` prop): `Sidebar` shows a pill after the label at ≥1280 px and a corner number on the icon in the dock, `MobileNav` a corner number on the bell tab; the link's whole name is its `aria-label` ("Notifications, 3 unread": browsers put a space before a separate hidden span, which would read "Notifications , 3 unread"), the visible number is `aria-hidden`, `99+` above 99, the colours invert on the active item. `/notifications` (Stitch c4; **static**, `robots: noindex, nofollow`, already in `PROTECTED_PREFIXES`) is `NotificationsPage` on the unchanged `useCursorFeed`: the title, an "N unread" chip (the server's count, not the loaded items'), **Mark all as read** (optimistic, rolled back with a toast), `NotificationItem` rows (a tile or the actor's avatar with a corner glyph, the sentence, a quote of the post, `formatRelativeTime`, an unread dot) whose whole row is the link (a stretched `after:` on the sentence's link; the **Follow back** `FollowButton` of a follow sits above it at `z-10`, never inside the link), opening an item marks it read at once and in the background, and when `arrivals` rises the first page is fetched again and its items are put on top (oldest first; an item already shown is replaced by the fresher copy) without resetting the loaded pages. Verdict, review, removal and emergency chips reuse `StatusBadge` and `EmergencyBadge` (no percentage: the item stores only `true`/`false`). Not built from c4: the filter tabs, the citation and sensor-audit items, the ledger-sync row and the preferences link.
- **Composer and Recent feed (Part 4):** `ComposerProvider` (`features/posts/`, mounted above the shell in `(app)/layout.tsx`) owns the draft, the request and the one `ComposerModal`; every "New post" button (rail, phone tab, the `/home` card) calls `useComposer().open`. Decisions of 2026-10-08:
    - **Insert on success:** the modal shows "Posting…" and stays open until the API answers; on 201 it closes, the draft is cleared, listeners (`onPosted`) get the server's post (`HomeFeed` puts it at the top, with no refetch) and a toast says "Posted." or "Posted. Checking the facts…". Errors keep the draft and stay in the composer. Away from `/home` the post just toasts.
    - **The provider, not the modal, owns the request:** Esc or × can close the modal while a post is on its way (the relay waits up to 70 s). The result is still handled: success clears the draft and toasts; failure keeps the draft and toasts that it is saved.
    - The draft (text, type, source rows) survives Cancel, Esc and ×, in memory only, and is cleared by a successful post or a change of user.
    - Characters are counted in code points (`countCharacters`, §2), with no `maxLength` attribute. The type has no default. The submit button stays enabled (except while posting): clicking it shows every problem and focuses the first. It reads "Post" until a type is chosen, then "Post opinion" or "Post fact, will be checked". A fact that the known allowance says will be refused isn't sent.
    - Source rows: one to start, "Add another source" up to 5, remove on rows 2–5, a check on blur and on submit (including "Same as source N."), empty rows dropped when sending; a server error at `sources.N` lands on the Nth **sent** source's row (empty rows are dropped, so not necessarily row N).
    - Unverified users get `aria-disabled` triggers and Part 2's toast; visitors see "Log in to post" (`/login?next=`); the modal itself shows a disabled form with a verify prompt (after a 403 `email_unverified` too).
    - `HomeFeed` (`/home`): a Recent tab and, for signed-in users, a Following tab (Part 6, below), the composer trigger card (b1's inline composer as a button) and `FeedList` over `useCursorFeed` (generic: waits for the session, reloads when the user changes, `prepend` kept apart from loaded pages and de-duplicated by key, one Load more at a time, a cursor 404 starts again from the top). A card shows a fact's first source and "+N more" (`SourceLink`); a blank display name shows `@username` once.
  - **Post page and polling (Part 5):**
    - `/p/[id]` (in the `(app)` shell, dynamic `ƒ`, public) has a **light server render**: one anonymous `no-store` fetch of `BACKEND_ORIGIN` (5 s timeout, no secret, `lib/api/server.ts`; the origin rule is shared with the relay in `lib/api/backend-origin.ts`) shared by `generateMetadata` and the page through React `cache()`. The claim and its status are in the HTML; `PostDetail` starts from that post (the anonymous view) and a signed-in visitor fetches once more to get `is_mine` and the author's full removed post. A non-UUID id is `notFound()` with no fetch; the backend's 404 is a real HTTP 404; a timeout or 5xx isn't a 404 (generic tags, the client fetches).
    - **Metadata:** title = the first ~70 characters of the claim (the root template adds " · Rumor Zero"); description = `Fact · VERIFIED 94%` / `Opinion`; canonical `/p/{id}`. **A page-level `openGraph` or `twitter` replaces the root layout's whole object** (Next doesn't merge it, and the root's static share image is merged only at the root), so the page sets `type: "article"`, `siteName`, the title with the suffix typed by hand, and the static `/opengraph-image.png` and `/twitter-image.png` itself (`post-metadata.ts`, allow-listed in the brand guard test). A removed post gets "Removed post", the tombstone description and `robots: noindex`.
    - **Page:** back link; one card (stripe, `CategoryChip`, `StatusBadge`, claim in `text-headline-md` with the card's fonts, author row with an absolute UTC time, Copy link and, for the author, Delete); `VerdictBlock` ("Checked automatically · 94% confidence", "Reviewed by a moderator" + the note, under review, pending; none for a published opinion or a removed post); `SourceList` ("Sources (N)", `01`… with the full value and an open-in-new link, `id="sources"`; "The author didn't add any sources."). A removed post is `RemovedPostCard` (Part 11): to a reader the author row and "This post was removed by a moderator."; to the author their claim as the page's `<h1>`, "Only you can see this text.", the reason a moderator gave and the appeal area (below), with the sources and Delete kept and no action bar, verdict or discussion.
    - **Cards link to the page:** the claim is a stretched link (`after:absolute after:inset-0`), `prefetch={false}` (every request is a Worker request), source links sit above it (`z-10`), and "+N more" goes to `/p/{id}#sources`.
    - **Delete:** a confirmation modal (a fact's copy says it still counts toward the allowance); success toasts "Post deleted." and `router.replace("/home")`; a 404 counts as deleted.
    - **`useStatusPolling`** (10 s, then × 1.5 up to 60 s; 10 minutes of **visible** time; a hidden tab pauses and checks once on return; a new pending id restarts the schedule; silent errors; at most 50 ids; public, `token: false`): the feed and the page pass it the posts loaded as `pending` and it stops asking about each one when it settles or vanishes. Results are an **overlay** (`status-overlay.ts`), not a rewrite of the feed: a polled `removed` turns the card into the tombstone card, a vanished post is hidden, and on the page the badge changes at once and one silent refetch brings the rest. `usePostDetail` marks a viewer as fetched only on success, because StrictMode aborts the first request.
  - **Profiles, follows and the Following tab (Part 6):**
    - **`/u/[username]`** (in the `(app)` shell, dynamic `ƒ`, public) has a **light server render** like `/p/[id]`: one anonymous `no-store` fetch of `BACKEND_ORIGIN` (5 s timeout, `fetchPublicProfile` in `lib/api/server.ts`) shared by `generateMetadata` and the page through `cache()`. A name that can't be a username is `notFound()` with no fetch; the backend's 404 is a real HTTP 404 (with `noindex`); a timeout or 5xx renders the shell and the client fetches. `/u/Ada` **redirects (307) to `/u/ada`**. Metadata (`profile-metadata.ts`): title `Name (@user)` or `@user`, description = the bio's first 160 characters or "Posts by @user on Rumor Zero.", canonical `/u/{username}`, `openGraph` type `profile` with the site name, the title suffix typed by hand and the two static share images (the descriptors are exported from `post-metadata.ts`, the one allow-listed place that names them).
    - **Page (Stitch c1; `max-w-reading`, one column, because c1's 12-column grid exists for the dropped side widgets):** `ProfileHeader` (avatar size 20, the name as the one `h1`, `@username` once when the display name is blank, bio as plain text, **Follow/Following or Edit profile** (a link to `/settings`), "Joined March 2024 · 42 posts · Credibility 72 How this is calculated" (Part 11B, below), counters **Followers**, **Following** (links to the lists), **Verified** (primary dot), **FALSE** (error dot), printed in full "1,420"), then `FilterChips` All / Facts / Opinions and the person's posts (`ProfilePosts`: `useCursorFeed` + `FeedList` + `useStatusPolling`; remounted with `key={username:filter}` because `useCursorFeed` doesn't refetch when `fetchPage` changes; on your own profile a post you make is added at the top when it matches the filter). Not built from c1: the seal and "Author" badge, affiliation, peer reviews, share and more buttons, the Published/Pending/Discourse control, the filter button, the "pending items visible only to author" callout (it contradicts the guide), the four side widgets.
    - **Viewer-specific data:** the server render is the anonymous view. A signed-in visitor fetches once more for `is_following` and `is_me` (`useProfile`, modelled on `usePostDetail`: a viewer is marked as fetched only on success, because StrictMode aborts the first request); until that lands the button area is a same-size skeleton, so it never flashes the wrong state.
    - **`FollowButton`:** Follow (primary) / Following (secondary; hover shows "Unfollow" in the same grid cell, so the width and the accessible name "Following" don't change). Optimistic: it flips at once, tells the parent (`onChange`, so the profile's follower count moves by one), and on a failure goes back and toasts (403 `email_unverified` "Verify your email to follow people…", 429 with the wait, 404, 401, network). One request at a time (the `loading` state, plus a ref for two clicks in one tick). Visitors get a "Follow" link to `/login?next=/u/<name>`; unverified users an `aria-disabled` button with a hint and the Part 2 toast; nobody gets a button on their own row or profile.
    - **`/u/[username]/followers` and `/following`** (Stitch c3; client-rendered, `noindex`, no server read): "← Back to Name (@user)", `Tabs` Followers/Following with counts (each tab is its own address, `router.push`), `UserRow`s in a `divide-y` card (avatar, name, handle, bio line, the credibility line (Part 11B, below), `FollowButton`), Load more, skeletons, empty and error states. Not built from c3: the network header card, category chips, the in-list filter, tiers, the "more" menu, the directory banner. Unfollowing in a list keeps the row.
  - **Credibility score (Part 11B; `features/reputation/CredibilityBadge.tsx`, a Server-Component-safe presentational component):** neutral on purpose (user decision 2026-10-13): grey `text-on-surface-variant`, no teal, no `verified` seal, no glyph (DESIGN.md reserves those for a verified fact).
    - `variant="header"`, in `ProfileHeader`'s meta row after the post count: "Credibility 72" (`font-label-code text-label-code`), or "Credibility: New" with the title and screen-reader text "A score shows once 3 of their posts have been checked or removed.", then a **"How this is calculated"** link to `/how-it-works#credibility` (`prefetch={false}`; the page's section and anchor arrive in Part 15).
    - `variant="row"`, in `UserRow` on its own line (`pl-12`, outside the profile link, so the link's name stays the person's name): c3's neutral chip (`rounded-lg border border-outline-variant/30 bg-surface-container px-space-xs py-0.5 font-label-badge text-label-badge text-on-surface-variant`) "Credibility 72" or "Credibility: New" (the same title), then "· 84 verified" (`formatCount`, from the row's `counts.verified`). No link in rows: twenty identical links would be noise.
    - **Never on post cards** (`PostCard` and `FeedList` tests pin it); the profile's server render already carries the score, so it shows without a client fetch.
    - **Home (Following tab):** `Tabs` = Recent, Following (the second only when signed in). Following loads **lazily** (`enabled` turns on at the first selection and stays on, so `/home` makes no extra request and switching back keeps the list); a post you make is prepended to both feeds; status polling takes the pending ids of the **active** tab's feed. Empty state "Follow people to see their posts here" with a **See Recent** button. `FeedList` takes an optional `empty` node.
    - **Author links:** `PostCard` gets `author.href` (`/u/{username}`); the avatar and name are one link above the stretched claim link (`relative z-10`), the time stays outside it. The removed-post tombstone card has no author block. `PostDetail`'s author row is a link (also on a tombstone: the author is public).
  - **Likes and comments (Part 7; `features/social/`):**
    - **`LikeButton`** mirrors `FollowButton`: the heart flips and the count moves at once (a filled `favorite` glyph in `secondary` when liked, outline otherwise) and goes back, with a toast, if the request fails; one request at a time (a ref, for two clicks in one tick); `aria-pressed` with a stable name ("Like 3" in one `sr-only` span, the visible label and count `aria-hidden`). A visitor gets a link to `/login?next=/p/<id>`; an unverified email an `aria-disabled` button with the Part 2 toast ("Verify your email to like posts…"), unless it already has a like to take back; while the session loads, an inert same-size look-alike. The count is the server's number moved by your own like (state seeded from props and re-synced with the "adjust state while rendering" pattern); a like made in one list is not copied into another mounted list showing the same post (Recent and Following on `/home`), which every route change repairs by refetching.
    - **Action bar:** `PostActions` (like + `CommentCountLink`, `chat_bubble` + count → `/p/{id}#comments`; counts print with `formatCompactNumber`, glyphs 1.125 rem as b1/b3). `PostCard` stays presentational: it takes an `actions` node, which `FeedList` fills (`FeedCard`) and puts under the sources (`relative z-10`, above the stretched claim link); the removed tombstone card has none. On `/p/[id]` the bar sits in the claim card's action row beside Copy link, with the words "Like" and "Comments" from `sm` up and the comment link jumping to `#comments`.
    - **Discussion on `/p/[id]`** (`CommentSection`, `id="comments"`, after `SourceList`; not shown for a removed post, whose API answers 404, its author included): the heading "Comments (N)" with "Oldest first", `CommentComposer`, `CommentList`, `DeleteCommentModal`. Comments are fetched by the page (`useComments` = `useCursorFeed`, which gained `append` and `remove`), **not server-rendered**, so the light SSR and its Workers CPU cost are unchanged. The composer is a `Textarea` with `maxCount={500}`, the server's messages, Ctrl/Cmd+Enter, a lock while posting, focus returned afterwards, the draft kept on a failure and cleared on success; visitors get "Log in to comment", an unverified email a locked box with "Verify your email to comment.". A new comment goes at the **end** of the loaded list (it is the newest; if older pages are still unloaded it stays last until they arrive, and its copy from a later page wins its place); a delete asks first and removes the row at once; `PostDetail` keeps the heading and the action row's count in step (`patch({comment_count})`). Comment drafts live in component state only (no provider, unlike post drafts). Rows are Stitch b3's cards (`Avatar` 8, name linking to the profile, `@handle`, relative time with the full UTC date as `title`, plain `whitespace-pre-wrap` text, a **Delete** text button on your own).
  - **Reposts and bookmarks (Part 7B; `features/social/`, `features/bookmarks/`):**
    - **Action bar:** `PostActions` takes the post. On a card: like, comments and repost on the left (`gap-space-lg`), the bookmark alone on the right (b1's `justify-between`); on `/p/[id]` one row (like, comments, repost, bookmark) beside Copy link, with the words "Like", "Comments" and "Repost" from `sm` up. A repost item's buttons act on the **original** (`post.id`).
    - **`RepostButton`** mirrors `LikeButton` (optimistic, rollback with a toast, one request at a time, `aria-pressed`, a stable name "Repost 3", visitor link, session-loading look-alike). The `cached` glyph is `secondary` when reposted. It is **disabled with the reason** (`aria-disabled`, `title`, an `aria-describedby` hint from `useId`, a click toasts the reason) for your own post, a FALSE post or a removed post (`repostBlockedReason`), and for an unverified email ("Verify your email to repost posts."), unless you already reposted it: an undo is never blocked.
    - **`BookmarkButton`:** `bookmark` glyph, filled in `secondary` when saved, no count, any signed-in user; the same optimistic pattern. `LikeButton`'s hint id now comes from `useId` too (a feed of unverified viewers repeated one constant id).
    - **`RepostHeader`** ("↻ Reposted by Name", a link to the profile, `relative z-10`) goes in `PostCard`'s new `header` slot; **`UnavailablePostCard`** is the tombstone's look with the header and "This post is no longer available", plus **Undo repost** when the repost is yours (it calls the API, removes the item with `feed.remove`, toasts "Repost removed.").
    - **`FeedList`** renders repost items, turns a repost whose original was polled as `removed`, found gone or sent as a stub into the unavailable card, and **hides a post that already showed higher up** (`visibleItems`: an older activity of it that comes back on a later page, a second reposter, the original after its repost; user decision 2026-10-10). The empty state shows only when nothing more can load (a cached page can come back empty with a next cursor). `pendingPostIds` includes the originals of reposts (a repost shows the live label), each id once.
    - **`/bookmarks`** (`BookmarkList`, client-rendered, `noindex`, in `PROTECTED_PREFIXES`): the profile page's container, a visible `h1` "Bookmarks", `FeedList` over `useCursorFeed` (enabled only for a settled signed-in session), polling of pending posts, the empty state "No bookmarks yet" / "Posts you bookmark appear here. Only you can see them.". An un-bookmarked card stays until the next load. Your new repost isn't inserted into an open list; the next load shows it.
  - **Reports (Part 8; `features/reports/`, the action bars):** user decision 2026-10-10: the report action is a **flag button**, as Stitch b1/b3 draw it, not an overflow menu (`task.md` said "overflow menu"; DESIGN.md's glyph list names `more_horiz` for overflow menus but no `flag`, recorded in ANALYSIS c-40).
    - **Action bar:** a card's right-hand group is the bookmark and the flag (`gap-space-md`); on `/p/[id]` the row ends with Bookmark and "Report". `PostActions` takes the post's `author`, `content` and `post_type` too (the modal quotes them). A repost item reports the original.
    - **`ReportButton`** mirrors `LikeButton`'s states: session loading → an inert same-size look-alike; a visitor → a link to `/login?next=/p/<id>` ("Log in to report"); **your own post → nothing** (`is_mine`, or the session's user id equal to the author's, so the server-rendered anonymous view hides it as soon as the session settles); an unverified email → `aria-disabled` with the hint "Verify your email to report posts." and the Part 2 toast; reported → a filled `flag` in `secondary`, named "You reported this", `aria-disabled` but not dimmed, a click only toasts "You already reported this post.". It is **one `<button>` element throughout**, so focus returns to it after a report (`Modal` returns focus only from the dialog's `close` event). The modal is built on the first click and then kept (a feed doesn't carry 20 dialogs). Cards show the glyph only (`title` "Report this post"); the post page adds the word from `sm` up ("Report", "Reported"), inside the accessible name. State is seeded from `reported_by_me` and re-synced when it changes ("adjust state while rendering").
    - **`ReportModal`** (Stitch d1, `max-w-modal`, `footerTone="plain"`, plain-language copy from ANALYSIS b-5): the post quoted in d1's neutral-stripe card (name, `@handle`, the claim clamped to three lines, italic for opinions); the five reasons as `RadioCardGroup` with **none preselected** (d1 preselects the first; a default would bias what people report); "Details" (`Textarea`, `maxCount` 500, "Optional." / "Required for “Something else”."); an info `Alert` "What happens next" ("When several people report a post, a moderator reviews it. The post stays visible meanwhile, and nothing is removed automatically."); the footer "Reports are private. The author is never told who reported.", Cancel and **Submit report**. Submit checks everything, shows every problem (a reason error is a `<p role="alert">` under the group) and focuses the first. Sending locks the form in a `fieldset disabled`, and the modal can't be closed then. A problem the server finds after sending takes the focus only once the form has unlocked (a disabled fieldset ignores `focus()`). Outcomes: 201 → close and toast "Report sent. Thank you."; 409 `already_reported` → close, "You already reported this post.", button reported; 404 → close, "This post is no longer available.", button unchanged; 403 `email_unverified` → a warning "Verify your email to report."; 400 → the server's messages on their fields; 429 → "You're reporting too fast. Try again in about N minutes."; network, 503 and the rest → an error `Alert` with the choices kept. Not built from d1: "Claim Hash", the "Evidentiary Integrity Protocol" eyebrow, the "Editorial Consensus Threshold" callout and "Cryptographic report signature" (jargon, D8), the preview badge at the bottom.
  - **Appeals and removed posts (Part 11; `features/appeals/`, `features/posts/RemovedPostCard.tsx`):**
    - **`AppealButton`** ("Request another look", Stitch b3's button without "/ APPEAL VERDICT", `ml-auto`) renders only for `is_mine && can_appeal` (both from the server, so a caller doesn't check): nothing for a visitor or while the session loads; an unverified email → `aria-disabled` with a `useId` hint and the Part 2 toast; otherwise it builds `AppealModal` on the first click and keeps it. It is **one `<button>`**. A request that went through gives the caller the returned post (`onFiled`), and "already appealed", "can't be appealed" and "gone" give a toast and `onStale` (the page refetches the post).
    - **`AppealModal`** (`Modal`, "Request another look", eyebrow "Appeal", `gavel`, `footerTone="plain"`; ReportModal's pattern: the fieldset lock, no closing while sending, focus after a field error once the form unlocks): the post quoted, one line saying what is appealed ("Your post is labelled FALSE." or "A moderator removed your post." + "Reason given: …"), an optional `Textarea` "Why should we look again?" (`maxCount` 500), an info note "What happens next" (a moderator who didn't make the first decision looks again; a FALSE post shows UNDER REVIEW meanwhile, a removed one stays hidden; once for each post), Cancel / **Send request**. Failures map in `messages.ts` (`appealFailure`).
    - **`AppealOutcome`** is the author's one line from `appeal_status` and the status (open: "You asked for another look. A moderator who didn't make the first decision will review it."; upheld: "…the post stays removed" / "…the FALSE label stays" / "…the decision stands"; overturned: "…A moderator reversed the decision."). `PostDetail` renders it beside `VerdictBlock`, not inside it (a published opinion's block is one neutral line, so a restored opinion's outcome would never show). The APPEAL PENDING chip (Part 0B) sits beside the badges.
    - **`RemovedPostCard`:** everyone but the author gets the tombstone (`Tombstone.tsx`: no text, no author, no links; `PostCard` keeps a guard that renders it for any removed post, so no caller can show a removed post's words or action bar); the author gets their own words (the card's claim fonts, plain text), "Only you can see this text.", "Reason given: …" when there is one, then the appeal area. A request that went through is kept in the card (`filed`) so the chip survives `FeedCard` building a new post object on every poll, until the server's own copy knows the status. `FeedList` renders it for a removed item (loaded, or found removed by the poll); your own profile lists your removed posts this way, and a repost of someone else's removed post is still the "no longer available" stub.
  - **Emergency posts (Part 11C; `features/posts/`):**
    - **Display rule:** `emergencyShown(post)` (`lib/post-display.ts`) = `emergency_active` unless the status is `verified_false` or `removed`: the status poll carries no `emergency_active`, but a FALSE always ends the priority, so a polled FALSE or removal ends the violet stripe and the EMERGENCY chip at once. Cards (`post-card-props.ts`) and `PostDetail` use it. Expiry while a page is open shows on the next load (no client timer, no hydration risk).
    - **Composer** (`ComposerModal`, `ComposerProvider`, `draft.ts`, `emergency-copy.ts`): for a fact only, b2's emergency row with its copy rewritten (D8): "Emergency" / "Pinned at the top of feeds and checked before other posts." and `Toggle tone="tertiary" label="Emergency post"`. It is disabled until the allowance has loaded and while `quota.emergency.allowed` is false, with the reason in plain words as its `aria-describedby` (`emergencyReasonText`; an answer without the block reads as "not allowed", so a frontend ahead of its backend doesn't crash). On: b2's warning box ("Use this only for urgent safety or public-health news.") and a required `Checkbox` with the confirmation sentence (`confirmationText(block_days)`, the clause dropped at 0 days); unticked at submit → "Tick the box to confirm." under it, focused, `aria-invalid` and linked (`Checkbox` merges a caller's `aria-describedby` with its description's id). The button reads **"Post emergency, will be checked"** (`bolt`, the same primary blue: DESIGN.md keeps primary actions blue). `is_emergency: true` is sent only when the toggle is on **and** the allowance allows it; the provider turns a toggle the allowance no longer allows off while rendering (never in an effect), and switching to Opinion turns toggle and tick off. A 403 `emergency_not_allowed` shows the server's words, turns the toggle and tick off (the text stays) and refreshes the allowance. Success toasts "Posted. It's pinned while it's checked."
    - **`PinnedEmergencies`** (Stitch b1's dispatch banner as the section header; presentational with a `renderCard` slot, so `/dev/ui` renders it without a session): `<section aria-labelledby>` with a `bolt` tile, "EMERGENCY POSTS", "Pinned for a limited time and checked first.", up to 3 cards (`HomeFeed` passes the feed's exported `FeedCard`, so the action bar and the polled status work), "Show all (N)" when more are pinned (loads `GET /api/v1/posts/emergencies/?feed=…` in place through `useCursorFeed`, with Load more) and × to fold it to one line ("2 emergency posts pinned" and **Show**; focus moves between × and Show). The fold is remembered per feed and per tab in `sessionStorage` (`rz:pinned-collapsed:<feed>`, the folded ids; `pinned-collapse.ts`), **written only on a click**, read through `useSyncExternalStore` with a null server snapshot (no hydration mismatch), guarded by try/catch with an in-memory fallback; a post that wasn't pinned when × was pressed opens it again. A post the poll finds FALSE, removed or gone leaves the section. No token is ever stored there.
    - **`HomeFeed`:** each tab's panel renders its own `PinnedEmergencies` (from its first page's `head`: `useCursorFeed` keeps the first page's `head` through Load more and clears it on a fresh load; `fetchRecentFeed` / `fetchFollowingFeed` return it) above its `FeedList`; polling includes the pinned posts loaded as pending; an emergency you just made goes into the pinned section of both tabs, not the lists; `FeedList` takes `alreadyShown` (the pinned ids), so `visibleItems` hides a later repeat or a repost of one; with pinned posts above an empty list the empty state reads "No other posts yet".
    - **`EmergencyNote`** on `/p/[id]`, in the claim card under the author row, neutral grey (no violet): "Posted as an emergency on Oct 19, 2026. Priority ended." or "… Priority removed by a moderator." (`emergency_demoted`), once the post is an emergency that no longer shows as one (`formatDate`, UTC).
  - Menus and the sheet are native `popover` elements with explicit positioning (a popover is centred by default). `aria-current="page"` comes from `usePathname()` on the item and everything below it (`/u/ada/followers` keeps Profile active).
  - Marketing links go only to pages that exist (user decision 2026-10-01): nav How it works, Log in, Sign up; footer How verification works, Privacy, Terms, "© 2026 Rumor Zero".
  - Titles: the root metadata template is `"%s · Rumor Zero"`. `not-found`, `error` and `global-error` are basic AuthLayout cards with the logo (Part 15 polishes them). `/dev/shell` previews the shell with a sample user in development only.
- Images (logo, avatars) are plain `<img>` with explicit width/height. `next/image` optimisation is not used: on Workers it needs Cloudflare Images, and our images are already pre-sized. SVG is never inlined from a file.
- Charts are token-built HTML/SVG (`src/components/ui/charts/`, 11D: `MeterBar`, `BarChart`, `RingGauge`, `Sparkline`, `StatTile`), each graphic a `figure` holding a `role="img"` element with an `aria-label` summary and, as its **sibling** (children of an image are presentational), a visually hidden `<table>`. `StatTile` is plain text. No animation, so reduced motion is satisfied. No chart library (`no-chart-library.test.ts`). The post page's "How this was checked" (`PostStats`, facts only) shows the confidence meter with the threshold tick and three tiles for a pipeline label, "Reviewed by a moderator" and a time (never a %) for a moderator's, a one-line note while pending or under review, and the reposts-and-likes bar chart for every fact; credibility visuals are neutral grey, the confidence meter keeps its verdict tone.
- Source links (every source of a post): `rel="nofollow ugc noopener noreferrer"`, `target="_blank"`, plain-text label (§4c).
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
  - **hermetic:** tests never depend on the developer's real `backend/.env`. They set what they need through the `settings` fixture or `monkeypatch`; CI builds its env file from `backend/.env.example`. The root conftest pins the stub pipeline, turns the inline kick off (a test turns it on when it needs it) and forbids the HTTP pipeline client's default opener; a test that leaves a `pipeline-kick` thread running fails (Part 9).
- **Frontend:** Vitest + React Testing Library for components and hooks.
- **E2E:** Playwright for one user flow per part where it applies (e.g. sign up → post a fact → see CHECKING FACTS… → verdict badge).
- **CI (`.github/workflows/ci.yml`, Part 0C):** on push to `main`, pull requests and manual dispatch; read-only permissions; superseded runs cancelled; 15 min per job; no secrets (env files are copied from the `.env.example` files).
  - **backend:** Python from `.python-version`, `postgres:18` (the example's `rumor_zero` user/password/database) + `redis:8-alpine` services; ruff check, ruff format --check, `makemigrations --check --dry-run`, pytest.
  - **frontend:** Node from `.nvmrc`; `npm ci`; lint, typecheck, lint:tokens, format:check, vitest; then `npx opennextjs-cloudflare build`, which runs `next build` itself (Linux only). No env file in this job: the OpenNext build copies `.env*` files into the Worker bundle.
  - **e2e:** the same services, a `backend/.venv`, `npx playwright install --with-deps chromium`, `next build`, then Playwright (`playwright.config.ts` starts Django and `next start`); the report is uploaded on failure (7 days).
  - Render deploys **only after CI passes**. There is no PNG regenerate-and-diff check (§14).

## 12. Security checklist (guide §12)

| Risk | Mitigation |
|---|---|
| SQL injection | ORM only; no string-built SQL |
| XSS | plain-text rendering; no HTML from users; no tokens in storage |
| CSRF | Bearer header for the API; **every unsafe `/api/auth/` request** (login, signup, refresh, logout) needs `Origin == FRONTEND_ORIGIN` + `X-Requested-With: rumor-zero` (allauth's views accept `text/plain` JSON), plus SameSite=Lax on the cookies; admin uses Django CSRF (§7) |
| Brute force | allauth rate limits + DRF throttles on the real client IP (relay header + secret) |
| Bots / brigading | Turnstile on signup, email verification before writes, new-account report weighting, report throttle |
| Stolen DB | Argon2id; allauth stores only signed/hashed keys |
| Secrets | env vars only; `.env*` git-ignored; either agent needs explicit user authorization before reading or editing local env files; production env files denied; Dependabot |
| Transport | HTTPS everywhere (Render/Cloudflare TLS); `SECURE_PROXY_SSL_HEADER`, HSTS, secure cookies in prod |
| Admin exposure | unguessable `ADMIN_URL_PATH`, staff-only, path never public |
| Search text (Part 12) | the query is in the request URL (`GET /api/v1/search/?q=…`), so it appears in access logs and, on a server error, in the Sentry event's URL. Posts are public, so this is low risk; scrubbing the query from Sentry URLs is a Part 16 option |
| Error reports (Sentry) | `send_default_pii=False` alone strips only a fixed list of standard headers such as Authorization, Cookie and X-Forwarded-For (sentry-sdk 2.71.0), so settings also add `x-rz-proxy-secret`, `x-rz-cron-secret`, `x-rz-client-ip` and `x-password-reset-key` (a live reset link, sent by the reset page's key check) to the `EventScrubber` denylist, and set `max_request_body_size="never"` and `include_local_variables=False`. Request bodies (passwords, allauth keys, emails), relay/cron secrets, client IPs and frame locals never reach Sentry. |
| Uploaded images (profile photos) | decode-and-re-encode with Pillow 13.0.0 (JPEG/PNG/WebP in, WebP out; only those three decoders ever see the bytes); size, pixel (25 MP, WebP 12 MP) and dimension limits checked from the header before any pixel is decoded; EXIF/GPS/ICC/XMP dropped (a fresh image is built from pixel bytes); original never stored and never on disk (in-memory 5 MB upload handler); one decode at a time site-wide; served from our origin with `nosniff` + `default-src 'none'; sandbox` + a version-checked ETag; no SVG uploads (§4e) |
| User-supplied links (up to 5 sources/DOIs per post) | http/https only; no credentials, IP or localhost hosts; punycode shown; `rel="nofollow ugc noopener noreferrer"`; **never fetched server-side** (no SSRF) (§4c) |
| Emergency abuse | eligibility gates, 1 per 24 h, lower report threshold, human confirmation of FALSE, 30-day block, moderator demote/block (§4b) |
| Public credibility score (reputational/legal risk, guide §16) | only automated from labels; audit ledger; exact reversal on appeal; label and removal appeals; never ranked or shown on cards; Terms need legal review (§4a) |
| Google sign-in (Part 3) | Only RS256 ID tokens with a `kid` for **our** client ID reach allauth, which checks signature, `iss`, `aud`, `exp`, `iat` and one-time `jti`; Google's email must be verified; links by email only for addresses Google hosts (Gmail, or Workspace `hd`), never to staff or inactive accounts; an unverified local account loses its password when linked; `provider/token` shares the `login` rate limit; profile data is not stored (§7). **Part 16's CSP must allow Google Identity Services** (`https://accounts.google.com/gsi/` for `script-src`, `style-src`, `frame-src` and `connect-src`), and COOP must stay unset or be `same-origin-allow-popups`, or the popup breaks. |
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

**Master:** `design/logo.svg` (read-only; you replace it, Claude and Codex never edit `design/`). `design/logo.png` is an earlier raster version, kept but **not used**.

**What the SVG is (current version, recoloured by you and inspected 2026-09-30):**
- `viewBox="0 0 1000 1000"`, no width/height, transparent background, 2.2 KB.
- The wordmark "Rum0r":
  - R, u, m, r in neutral grey `#898a8d` (class `cls-2`)
  - the "0" and a full-width underline in cyan `#23b5d8` (class `cls-1`)
- All text is outlined paths: no fonts, scripts, links or bitmaps.
- The artwork spans x 121.4–878.6, y 413.0–625.7 of the 1000 box (≈ 3.6 : 1); the rest of the square is empty.
- The "0" is the only `<path>` in the cyan class, currently `path.cls-1` (x ≈ 664.4–779.2, y ≈ 413.0–584.9). The underline is a `<rect>` in the same class.
- Class names can change whenever the file is re-exported, so the mark selector lives in `brand.config.json`, and the build fails if it doesn't match exactly one path.
- Accessible name everywhere: **"Rumor Zero"** (the logo reads "Rum0r").
- The first version (2026-09-29, teal `#19aa96` + amber `#f4a361`) was practically identical to the Verified and Under-review colours (ΔE 1.5 and 0.6). This version replaced it.

**Colour check against the Stitch tokens** (CIE76 ΔE; above ≈ 10 is clearly a different colour):

| Logo colour | Nearest Stitch tokens | Verdict |
|---|---|---|
| grey `#898a8d` | `outline` `#6c7a76` (ΔE 10) | a neutral, like Stitch's text/outline greys. No clash. |
| cyan `#23b5d8` | `secondary-fixed-dim` `#93ccff` (ΔE 22), `secondary-container` `#5bb8fe` (ΔE 23), `primary-container` `#00a896` (ΔE 32) | clearly distinct from every verdict colour. It sits between the blue **action** family and the Verified teal. **No verdict clash.** |

- DESIGN.md keeps colour for verdicts and actions, so the logo colours still live **only inside the logo image**. They never become tokens, buttons, links or badges; a cyan button would read as an action or as "verified".

| Contrast (WCAG ratio) | grey letters | cyan "0" / underline |
|---|---|---|
| on `surface-container-lowest` `#ffffff` (sidebar, cards) | 3.45 : 1 | 2.42 : 1 |
| on `surface` `#faf8ff` (page) | 3.28 : 1 | 2.30 : 1 |
| on `inverse-surface` `#283044` | 3.81 : 1 | 5.43 : 1 |
| on `on-surface` `#131b2e` | 4.97 : 1 | 7.09 : 1 |

- The grey letters pass 3 : 1 on every surface.
- The cyan "0" is below 3 : 1 on light surfaces. Logotypes are exempt from WCAG 1.4.3 / 1.4.11, so this is recorded, not blocking. The "0" is still clearly visible, but a slightly darker cyan would make it crisper on white.
- Both colours are ≥ 3.8 : 1 on the dark plate.
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
| Email logo | `frontend/public/brand/email-logo.png` | 320 px wide, shown at 160 | HTML emails (Part 2) via `FRONTEND_ORIGIN/brand/email-logo.png`: the adapter adds `email_logo_url` to every email's context, and `base_message.html` shows it in a `#283044` cell |
| Google logo | `frontend/public/brand/google-oauth-logo.png` | 120×120, < 1 MB | optional consent-screen upload (ENV_GUIDE §2.9) |
| Admin logo | `backend/apps/core/static/core/brand/logo-admin.png` | 64 px tall | Django admin header (Part 10) |
| Asset list | `frontend/src/lib/brand-assets.json` | — | generated; read by `Logo`, `manifest.ts` and the root metadata |

- Icons and the mark use the cyan "0" on the `inverse-surface` plate (5.4 : 1). The share image, email, Google and admin logos use the full wordmark on the same plate.
- Plate details (Part 0D, `brand.config.json`):
  - `favicon.ico`, `icon.svg`, `icon-192.png` and `icon-512.png` sit on a **rounded-square** plate (22 % radius, transparent corners). `apple-icon.png`, `icon-maskable-512.png` and the share, email, Google and admin logos are full-bleed, opaque rectangles.
  - The wordmark SVG is cropped to the measured artwork plus 12 units on every side; the mark is the "0" centred in a square viewBox with 12 units clear. Bounds are measured from a 4x render, so no path parser is needed.
  - Derived SVGs have their class fills inlined (no `<style>`), so nesting them in plates cannot clash on class names.
  - The maskable icon keeps the mark inside the central 80 % circle (checked by a pixel-scan test). `manifest.ts` uses the plate colour for `theme_color` and `background_color`.
  - The `.alt.txt` files hold exactly `Rumor Zero` with no trailing newline: Next copies them verbatim into `og:image:alt`.
  - PNG bytes are reproducible on the same machine but not guaranteed across operating systems, so CI does not regenerate-and-diff; tests check sizes, structure and the text outputs instead.
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
2. Check that the mark selector in `frontend/scripts/brand/brand.config.json` still picks the "0" (re-exports can rename classes).
3. Run `npm run brand:build` in `frontend/`.
4. Compare the printed contrast table with this section and update it.
5. Commit the regenerated files.
