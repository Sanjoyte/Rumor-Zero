# Plan: Part 13, Notifications

- **Status:** APPROVED by the user (Sanjoy Rozario) on 2026-10-20, together with the decisions and the defaults below; drafted
  2026-10-20 by Claude (Sonnet 5.5). Saved here and linked from HANDOFF at approval, so step 0 only needs to verify the workspace, record
  the baselines and apply the small corrections noted there. **Implemented 2026-10-20 (Claude, Sonnet 5.5); the as-built differences are in `task.md` Part 13 and ANALYSIS c-47.**
- **Implement with:** Sonnet 5.5 · medium (task.md).
- **Evidence (read-only):** HANDOFF, MEMORY, `task.md` Part 13 and the notes left by 7/7B/8/9/10/11/11C/12, ARCHITECTURE §2/§3/§4b/§9/§10,
  ANALYSIS c4/c-notes, STRUCTURE; backend `social/services.py`, `posts/services.py`, `pipeline/routing.py`, `reports/services.py`,
  `moderation/{services,rules}.py`, `social/admin.py`; frontend shell, `useStatusPolling`, `useCursorFeed`, `Connections`, `BookmarkList`,
  Stitch `c4_notifications/code.html`; two Explore agents (backend hook points; frontend + Stitch).

## Context

Part 13 adds the DB-backed notifications of guide §11: a `notifications` app, `notify()` called explicitly (no signals) from the existing
write services in the **same transaction**, three endpoints, and a `/notifications` page with an unread badge in the shell polled every
30 s while the tab is visible. Nothing in the repository exists yet (no app, no route body, no `NOTIFICATION_POLL` constant).

**Dependency check (2026-10-20): all Done.** Part 13 depends on **7** (2026-10-10), **7B** (2026-10-10), **10** (2026-10-13), **11**
(2026-10-13) and **11C** (2026-10-20); their chains (0A–0D, 1–6, 8, 9, 11B, 11D, 12) are Done too. Open but not blocking: Part 3 criterion 4,
CI for Parts 2–12 (not reported), the Part 17 stub-verdict launch blocker. **Workspace:** HEAD `30649b4` ("Implemented Part 12: Search"),
clean tree. Baselines (from HANDOFF, re-measured in step 0): `pytest` 3894, `npm test` 2043, E2E 51.

## Your decisions (2026-10-20)

1. **Appeal-closing actions send two items:** `appeal_resolved` **plus** the usual `verdict` / `removed` (Mark verified, Mark FALSE, Remove
   on a label appeal). Restore and Keep removed send `appeal_resolved` only (no verdict / removal happened).
2. **Mark FALSE on an active emergency sends two:** `verdict` (FALSE) + `emergency_demoted`. Demote sends `emergency_demoted` only.
3. **Dismiss reports is silent** (and so are Escalate, an automatic block or lift, and your own appeal being filed). Nine types, no tenth.
4. **The open page reloads itself:** when the 30 s poll sees the unread count rise on `/notifications`, the first page is fetched and the
   new items are put on top (nothing resets; loaded pages and scroll stay).
5. **Author only:** reposters are not told of the original's verdict or removal (follow-up).
6. **Follow back:** the new-follower item has Stitch's button (`FollowButton`); the API sends `actor.following` on follow items.
7. **No retention job:** nothing is pruned; recorded as a Part 16/17 follow-up.

## Defaults I will use (tell me if you disagree)

- **A new column `outcome`** (varchar, blank) on the model, a small addition to ARCHITECTURE §2: `verdict` → `true`/`false`,
  `appeal_resolved` → `upheld`/`overturned`, everything else blank. Without it an old item would change meaning when the post is
  re-labelled later. (`under_review`, `removed`, `emergency_demoted` need none.)
- **Moderation items have no actor** (`actor` NULL for every system type): the author is never told *which* moderator, and a reporter
  is never revealed. `under_review` from reports reads the same as from the pipeline ("is under review").
- **Dedupe is permanent and database-enforced** for `follow`, `like`, `repost`: like → unlike → like gives one item, and the item stays
  after an unlike (it is a record, not a live state). Comments, verdicts, reviews, removals and appeals are one item per event.
- **Items vanish with what they point at:** `delete_post` deletes the post's notifications; `delete_comment` and the admin's Hide delete the
  comment's notification (in the same transaction). So the list and the unread count stay consistent with no joins; Unhide does not bring
  one back.
- **`outcome` for ties:** one action's items are stamped 1 µs apart (the `_TICK` of Part 11C): verdict / removed, then
  `emergency_demoted`, then `appeal_resolved` on top.
- **Throttle:** new scope `notifications`, **120/min per user**, shared by the three endpoints (one tab polls 2/min). A 401 never counts.
- **Unread count** is exact (`{"count": n}`); the badge shows `99+` above 99. `mark-read` answers `{"count": <unread left>}`.
- **A suspended actor** (`is_active=False`) is shown as "Someone" (the serializer blanks it), as profiles of suspended people 404.
- **Excerpts** are made on the server (first 140 code points, collapsed whitespace, `…`) from the post's text. Recipients are always
  the post's author, so a removed post's text is theirs to see. A `verdict` chip comes from the stored `outcome`, with no percentage.

## Scope

**In:** app `apps/notifications` (model, migration, `services.py`, serializer, three views, admin, throttle scope); hooks in `social`,
`posts`, `reports`, `moderation` services; delete/hide cleanup; `/notifications` page; `features/notifications/*`; unread badge in the rail,
dock and phone tab via a provider in `(app)/layout.tsx`; dev-gallery specimens; one E2E spec; docs and `docs/test-command.md` Part 13 (both
guides).

**Not in 13:** email or push; follower alerts; notification preferences, filter tabs, "Mentions"; reposter notices; retention; live push;
a notification for Dismiss / Escalate / blocks; grouping ("3 people liked…"); a tab-title counter.

## Backend design

**Model** `notifications.Notification` (table `notifications_notification`, UUID PK, `created_at` default `timezone.now`):
`recipient` FK users CASCADE (`related_name="notifications"`, `db_index=False`), `actor` FK users SET_NULL null (`related_name="+"`),
`type` (`TextChoices`, 9 values), `post` FK CASCADE null, `comment` FK CASCADE null, `outcome` varchar(12) blank, `is_read` bool.
Named checks: `type` valid; `outcome` valid per type; shape per type (`follow`: no post/comment; `comment`: both; the other seven: post,
no comment); `notifications_not_self` (`actor <> recipient`, NULL passes after an account deletion). **No check requires an actor** (SET_NULL
would break it).
Indexes: `(recipient, -created_at, -id)` for the list; partial `(recipient) WHERE is_read = false` for the count (the count query must use
`filter(is_read=False)`, the same predicate form; an EXPLAIN test pins it); partial **unique** `UniqueConstraint`s with `condition=` (Django emits
partial unique indexes): `(recipient, actor, type, post)` for `type IN (like, repost)` (**type is in the key**, ARCHITECTURE §2: a like and a
repost of one post by one person are two items) and `(recipient, actor)` for `type = follow`. Partial indexes on `post`, `comment` and `actor`
(`WHERE … IS NOT NULL`, FKs set `db_index=False`) serve `discard_for_*`, Part 14's cascades and the actor SET_NULL. `__str__` defined (ruff DJ008).

**`notifications/services.py`** (no signals): `notify(*, type, recipient, actor=None, post=None, comment=None, outcome="", now=None)`
asserts it runs inside a transaction (the `_require_transaction` pattern; its test needs `transaction=True`, because pytest-django `db`
tests are always inside one), returns None for a self-notification, and writes every type with one `bulk_create([obj], ignore_conflicts=True)`
(review-verified for Django 5.2.17: a bare `ON CONFLICT DO NOTHING` arbitrates against the partial unique indexes, the client-set UUID needs no
read-back, `atomic(savepoint=False)` keeps `durable=True` callers valid; CHECK violations still raise, and a test pins that). Named helpers keep call sites one line: `followed`, `liked`, `commented`, `reposted`, `verdict_reached`, `entered_review`,
`removed`, `emergency_demoted`, `appeal_resolved`, plus `discard_for_post(post_id)` and `discard_for_comment(comment_id)`.

**Hooks (all in the caller's transaction; `notify` never opens one, so `atomic(durable=True)` callers stay valid):**

| Event | Where | Recipient / actor | Notes |
|---|---|---|---|
| follow | `social.services.follow` (wrap in `atomic`) | target / follower | only when `created` |
| like | `social.services.like` (wrap in `atomic`) | post author / liker | `get_visible_post` adds `author_id` to `.only(...)`; only when `created`; not own post |
| comment | `social.services.add_comment` (`atomic`) | post author / commenter | not own post; carries `comment` |
| repost | `social.services.repost` (already atomic) | original's author / reposter | only when `created` |
| verdict (pipeline) | `posts.services.record_pipeline_result`, `LABELLED` | author / none | `outcome` from `post.status`; after `settle_post` |
| under review | same function, `ENTERED_REVIEW`; `record_pipeline_failure`, `ENTERED_REVIEW` | author / none | `UPDATED_REVIEW`, `RETRY`, `IGNORED` send nothing |
| under review (reports) | `reports.services.file_report` | author / none | keep the return of `record_report` (now discarded) |
| verdict (moderator) | `moderation.services._perform` | author / none | kinds `VERIFIED`, `MARKED_FALSE` |
| removed | `_perform`, kind `REMOVED` | author / none | |
| emergency demoted | `_perform`, `effect.demoted` or kind `EMERGENCY_DEMOTED` | author / none | |
| appeal resolved | `_perform`, `effect.appeal_status` set | `appeal.author_id` / none | `outcome` = `upheld` / `overturned` |

`_perform` skips every item when `moderator.pk == post.author_id` (only a superuser can act on their own post). **Refinement of decision 1
(review):** a `verdict` item is sent only when the label **changes** (`post.pre_review_status` differs from the new status); Mark FALSE on a
post that was already FALSE (a report review, or an upheld label appeal) sends no repeat "FALSE" item, so an upheld label appeal gets
`appeal_resolved` only, an overturned one (Mark verified) gets both, and Remove on a label appeal gets `removed` + `appeal_resolved`.
Restore of an already-checked fact (which lands in `under_review`) sends `appeal_resolved/overturned` only; written down, not a bug.
Cleanup: `delete_post` calls `discard_for_post` (a plain `DELETE`, so the one `FOR UPDATE` that `test_api_delete` counts is unchanged);
`delete_comment` calls `discard_for_comment`; `CommentAdmin._set_hidden(hidden=True)` is **wrapped in `transaction.atomic()` per comment**
(Django's changelist action is not atomic) and calls it too. The list also filters `post__deleted_at IS NULL` (a like that commits just after
`delete_post` leaves a stray row; the count can't join, so that rare race is accepted and documented). Mark-read `all` and `discard_for_post`
may lock one author's rows in different orders: the update locks in `id` order (`ORDER BY id FOR UPDATE` subquery), the delete accepts it.

**API** (`apps/notifications/{urls,views,serializers}.py`, `include` in `rumor_zero/urls.py`, all `IsAuthenticated`, `never_cache`, throttle
`notifications`):
- `GET /api/v1/notifications/` → `{results: [...], next_cursor}`; 20 a page up to 50; ordering `("-created_at", "-id")`; a
  `TimestampCursorMixin` pagination (a crafted cursor is a 404). Each item: `id, type, outcome, is_read, created_at, actor`
  (`{id, username, display_name, avatar_url, following?}` or null; `following` only on `follow`, one `EXISTS` in the same query),
  `post` (`{id, excerpt, post_type, status}` or null), `comment` (`{id, excerpt}` or null). **2 queries** (user, page); `following` is an
  `EXISTS` with `OuterRef("actor_id")` as `social/views.py:108-113`; `select_related` with `.defer("post__pipeline_result",
  "post__search_vector")` (not `post__content`: the excerpt needs it). The 1 µs ticks matter: DRF's cursor position is the first ordering
  key and UUID ties are random.
- `GET /api/v1/notifications/unread-count/` → `{"count": n}`; **2 queries** (user, count on the partial index); uncached.
- `POST /api/v1/notifications/mark-read/` body `{"ids": [uuid, …≤50]}` **or** `{"all": true}`, exactly one (else 400); only your unread rows
  change; other people's or unknown ids are ignored; a non-uuid id or `{"all": false}` is 400; → `{"count": <left unread>}`.

## Frontend design

- `lib/api/types.ts`: `NotificationType`, `NotificationData`, `NotificationPage`.
- `features/notifications/`: `notifications-api.ts` (list with cursor, count, mark-read), `messages.ts` (+ throttled/waking branches like
  `social/messages.ts`), `UnreadCountProvider.tsx` + `useUnreadCount.ts`, `NotificationItem.tsx`, `NotificationList.tsx`, `test-helpers`.
- **Poller:** `NOTIFICATION_POLL_MS = 30_000`. Fetches at mount when `status === "authenticated"`, then every 30 s **only while
  `document.visibilityState !== "hidden"`** (as `useStatusPolling`, since jsdom can say "prerender"); hidden stops the timer and aborts the
  request; back to visible polls at once. Errors are silent (the last count stays). `count` is derived (`authenticated ? state.count : 0`), no
  setState in an effect. Exposes `{count, set(n), adjust(delta), arrivals}`; `arrivals` is a counter that increments when a poll sees a higher
  count than the last known one. A poll that started before a local change is dropped (version check), so a stale, higher answer never
  fires it; the mark-read answer `{count}` is authoritative (`set`). Context value memoised.
- **Provider** wraps `AppFrame` in `(app)/layout.tsx`; `AppFrame` passes `unreadCount` to `AppShell` (which stays presentational: no
  `useAuth` in it). `Sidebar` and `MobileNav` render a badge on the Notifications link only: a pill after the label at `xl`, a corner dot
  with the number on the dock and the phone tab; `sr-only` ", N unread"; `99+`; inverted colours on the active item. `nav-items.ts` is unchanged.
- **`/notifications`** (static, `noindex`; already in `PROTECTED_PREFIXES`): title + "N unread" chip (Stitch classes) + **Mark all as
  read** (a `<button>`, optimistic, rolled back with a toast on failure), the list on `useCursorFeed` **unchanged** (a `readIds` Set in the
  list: `read = item.is_read || readIds.has(id)`; Mark all adds every loaded id), `LoadMore`, skeleton / error / throttled / empty
  (`EmptyState`) states. When `arrivals` changes, `fetchPage(null)` is called directly and the unseen items are `prepend`ed oldest first
  (current keys read through a ref set in an effect, for `react-hooks/refs`).
- **Item:** the whole row is clickable through a **stretched link** (`after:absolute after:inset-0`), with `FollowButton` at `relative z-10`
  (no button inside a link; hidden when the actor is null or suspended); `prefetch={false}`. Stitch's `rounded-r-lg` fails `lint:tokens`: only
  `rounded-lg` / `rounded-full` and `shadow-sm`. `follow` → actor profile + `FollowButton`; `like`/`comment`/`repost` → actor avatar with a corner badge,
  excerpt, post link; `verdict` → glyph tile + Verified / FALSE chip; `under_review` → `hourglass_top`; `removed` → `block`;
  `emergency_demoted` → `bolt` in `tertiary`; `appeal_resolved` → `gavel`, "upheld" / "overturned". Click marks read (optimistic,
  fire-and-forget `mark-read`) and navigates. Unread dot `bg-secondary` + `sr-only` "Unread". Time via `formatRelativeTime`.
  No filter tabs, no footer "preferences" link.

## Files expected to change

- **New backend:** `backend/apps/notifications/{__init__,apps,models,services,serializers,views,urls,admin}.py`,
  `migrations/0001_initial.py`, `tests/{conftest,factories,test_*}.py`.
- **Changed backend:** `apps/social/{services,admin}.py`, `apps/posts/services.py`, `apps/reports/services.py`,
  `apps/moderation/services.py`, `rumor_zero/{settings,urls}.py`, `apps/core/tests/test_settings.py`, `backend/.env.example` only if a
  variable is added (none expected).
- **New frontend:** `frontend/src/features/notifications/*` (+ tests), `e2e/notifications.spec.ts`.
- **Changed frontend:** `lib/api/types.ts`, `app/(app)/{layout.tsx,layout.test.tsx,notifications/page.tsx}`,
  `components/shell/{AppShell,Sidebar,MobileNav}.tsx` (+ tests), `features/dev/{StitchSections,UiGallery}.tsx` and `/dev/ui` test.
- **Docs:** ARCHITECTURE §2/§3/§9/§10, ANALYSIS (new entry), STRUCTURE, MEMORY, `task.md` (at implementation, not now),
  `docs/test-command.md` (Part 13 in both guides), HANDOFF.

## Ordered steps

0. Verify workspace (`git status`, HEAD `30649b4`, ports free, Docker up), save this plan under `docs/agents/plans/`, link it in HANDOFF,
   measure baselines.
1. (The spike gate of the draft is dropped: review confirmed `ignore_conflicts` against partial unique indexes in Django 5.2.17's source;
   it becomes an ordinary dedupe test in step 3.)
2. App skeleton: `startapp` into `apps/notifications/` (set `name = "apps.notifications"`), model, migration, `ruff check --fix . ; ruff format .`,
   admin (read-only, `HistoryNeedsLog`), `INSTALLED_APPS`, URL include, `notifications` rate, and the one existing test that pins the scopes
   (`core/tests/test_settings.py:~394`, `test_all_twelve_throttle_scopes…` → thirteen, `notifications` 120/min).
3. `services.py` + model/service tests (types, shape checks, dedupe, self, outcome checks, order ticks).
4. Hooks into `social`, `posts`, `reports`, `moderation`; cleanup in `delete_post`, `delete_comment`, `_set_hidden`. The review found no other
   caller of these services and no existing test that should break (the count/lock pins in `moderation/test_services.py:392`,
   `posts/test_services_pipeline.py:166`, `test_api_delete.py:158` stay valid); run the whole suite and list any that do in HANDOFF.
5. Serializer, views, urls; API tests (auth, list shape, cursor 404, 2-query pins, unread count, mark-read ids/all/other-user/bad body,
   throttle, `following` flag, suspended actor, deleted/hidden items gone).
6. Race tests (two simultaneous likes / follows / reposts → one item; threads, `transaction=True`).
7. Frontend api module, types, messages, provider + poller (+ fake-timer tests), badge in the shell, item, list, page, specimens.
8. E2E `notifications.spec.ts` (B likes A's post → A's badge and item; click marks read; mark all; no self-notification), reusing
   `seedAuthor`/`logIn`/`moderate` (no new sign-ups beyond the 20/min budget). The 30 s poll is never waited for: the badge appears on load
   or after `page.reload()`; one test dispatches `visibilitychange` (hidden, then visible). `layout.test.tsx` mocks the new api module
   (as `posts-api`), `AppShell` gets an optional `unreadCount?`, tests that query the link by exact name "Notifications" are checked
   (a count above 0 makes it "Notifications, N unread").
9. Docs (ARCHITECTURE §2/§3/§9/§10, ANALYSIS, STRUCTURE, MEMORY, task.md both status spots, `test-command.md` both guides), mutation
   checks, headless-Chromium visual check at 1280 and 390 px, full validation, HANDOFF.

## Tests (required by task.md, plus the extras above)

One creation test per event type (11 rows in the hook table, both TRUE and FALSE, all five appeal actions, Demote and Mark FALSE),
dedupe (like/unlike/like, follow/unfollow/follow, repost/unrepost/repost), no self-notification (including a superuser moderating their
own post), no item on `UPDATED_REVIEW`/`RETRY`/Dismiss/Escalate/`file_appeal`, API, `NotificationItem` variants, hook timers (visible,
hidden, return, abort, unmount), E2E. Backend query pins: list 2, unread-count 2.

## Verification

`ruff check .`, `ruff format --check .`, `makemigrations --check --dry-run`, `manage.py check`, `pytest` (threaded tests 10 runs);
`npm run lint`, `lint:tokens`, `typecheck`, `format:check`, `npm test`, `NEXT_PUBLIC_GOOGLE_CLIENT_ID= npm run build`, `npm run test:e2e`
(dev mode and `CI=1`, rebuild first); `docs/test-command.md` Linux blocks run against live Django; headless Chromium at 1280/390 px, 0 px
horizontal overflow.

## Risks recorded for later parts (not built in 13)

- **Part 16/17 budget:** a visible idle tab polls forever (unlike the 10-minute status poll): each poll is a Worker request and keeps
  Render/Neon awake. Follow-up: an idle cutoff.
- **Part 14:** export includes nothing from this table by default (decide); account deletion must delete by actor too (a like cascades
  away, its notification would stay as "Someone liked") and in a fixed order (MEMORY note). **Part 12 is unaffected.**
- Tests to add from the review: like + repost of one post by one person = two items; `{"all": false}` and a non-uuid id are 400; hard
  delete of the recipient removes rows and of the actor leaves `actor` NULL ("Someone"); EXPLAIN on the count; CHECK violations still raise
  through `ignore_conflicts`.

## Stop conditions

A hook needs a status write outside `posts`/`moderation` services; any
required test, lint or type check fails; a new dependency or service looks necessary (none expected); an existing test change is not
explained by a Part 13 behaviour.
