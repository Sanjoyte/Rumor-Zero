# Plan: Part 7, Likes & comments

- **Status:** APPROVED by the user (Sanjoy Rozario) on 2026-10-10, together with the three decisions and the
  defaults below. Saved here and linked from `HANDOFF.md`. **IMPLEMENTED 2026-10-10** (Claude, Sonnet 5.5).
  Deviations: see `task.md` Part 7 and `docs/agents/HANDOFF.md` (`PostActions` has no `onLikeChange` and `PostDetail`
  doesn't mirror the like; `LikeButton` tests `!user` only; the accessible name is one `sr-only` span;
  `count_subquery` moved into `engagement.py` and `content_field()` was shared; a plain `Textarea` instead of Stitch's
  boxed composer; `renderWithSessionAndToast` added). Drafted 2026-10-10 by Claude (Sonnet 5.5).
- **Implement with:** Sonnet 5.5 · medium (task.md).
- **Evidence (read-only):** HANDOFF, MEMORY, `task.md` Part 7, ARCHITECTURE §2/§3/§7/§8/§9/§10, ANALYSIS (b3/b1/a1
  rows, "Like", "Comments"), STRUCTURE, Stitch a1/b1/b3, DESIGN.md, and two Explore passes over the backend
  (`apps/social`, `apps/posts`) and the frontend (`features/posts`, `features/social`, `components/ui`, E2E).

## Context

Part 7 adds the first engagement: **likes** (a DB-unique toggle) and **flat comments** on posts. Today
`PostSerializer` emits literal `like_count: 0`, `comment_count: 0`, `liked_by_me: false`
(`apps/posts/serializers.py:123-129`), `PostCard` has no action bar, and `/p/[id]` has no discussion area. The
`like` (300/h) and `comment` (60/h) throttle rates already exist in `settings.py`.

**Dependency check (done 2026-10-10).** Part 7 depends only on **Part 5**: `[x] Done (2026-10-09)` in both places
in `task.md`. Its chain is Done too: 4 → 1 → 0C → 0A/0B/0D, plus 2, 3 and 6. HEAD is `15c1d8a` ("Implementation
Part 6"), tree clean. Open but not blocking: Part 3 criterion 4 (real-Google check) and CI for Parts 2 to 6 (not
run yet).
**Two things differ from HANDOFF:** it still calls Part 6 "uncommitted" (the user committed it; step 0 fixes the
text), and `docker compose ps` shows **no containers running**, so step 0 starts Postgres + Redis.

**Your decisions (2026-10-10):**
1. **Hidden comments: Django Admin only.** The API and the page never return a hidden comment to anyone, staff
   included; it doesn't count in `comment_count`.
2. **Deleting your own comment is a soft delete** (a new `deleted_at` column, like posts, D6). This changes
   ARCHITECTURE §2, which listed no such column.
3. **CommentAdmin has Hide and Unhide actions** (task.md said only "Hide").

## Scope

**In:** `social.Like` and `social.Comment` + migration `0002`; like/unlike; list/create/delete comments;
`like_count`, `comment_count`, `liked_by_me` annotated into every post list and the detail; `LikeAdmin`,
`CommentAdmin`; `LikeButton`, comment-count link, `PostActions` bar on cards and the detail page; `CommentList`,
`CommentComposer` and the discussion section on `/p/[id]`; tests, E2E, docs.

**Not in Part 7:** reposts and bookmarks (7B; `repost_count`, `reposted_by_me`, `bookmarked_by_me` stay 0/false),
reporting (8), notifications for likes and comments (13), any moderation-actions row (Part 10 creates that table),
Reply, comment IDs, comment likes and comment reports (dropped, ANALYSIS), Stitch's attach buttons and role chip,
live updates of comments, any new dependency, service or env variable.

## What the research found (all handled below)

- **Choke point for annotations.** Post lists are built in four places: `posts/views.py:67` (feed), `:121` (detail),
  `social/views.py:53` (profile posts) and `social/feed.py:39-42` (`load_posts`, the Following feed, which takes no
  viewer today). All call `Post.objects…for_list()`. Giving `for_list()` a `viewer` argument annotates every list in
  one place, and the Following cache stores only ids, so counts are never stale.
- **The 201 answer of `POST /posts/`** serializes a fresh, unannotated instance. If the serializer silently
  defaulted a missing annotation to 0, a future list that forgets to annotate would show zeros. So the serializer
  reads the annotations strictly and the create view sets the zeros explicitly.
- **Comments need an ascending cursor.** `TimestampCursorMixin` (`core/pagination.py:63`) only parses the position,
  so it works with `ordering=("created_at","id")`; its docstring says `-created_at` and gets fixed. A crafted cursor
  stays a 404.
- **The partial-index form matters.** Django compiles `is_hidden=False` as `NOT "is_hidden"` in both a filter and an
  index condition, so one partial index serves the list and the correlated count; an `EXPLAIN` in verification
  proves it (as Part 6 did).
- **`moderation_actions` doesn't exist** (Part 10) and its action enum has no comment kind, so a Hide writes
  Django's own admin `LogEntry` as its audit trail. No model permissions are granted to the Moderators group yet
  (Part 10), so today only a superuser can hide; the action is gated on `social.change_comment`.
- **`PostCard` is props-only** (Part 0B) and its claim is a stretched link, so the action bar is an `actions`
  slot filled by `FeedList` and `PostDetail`, with `relative z-10` on the buttons.
- **`useCursorFeed` has no append or remove.** Comments are oldest first, so a new comment goes at the end.
- **E2E sign-up budget.** The suite makes about 16 of the 20 sign-ups a minute. The new E2E tests join the serial
  describe in `social.spec.ts` and reuse its two shared accounts (zero new sign-ups).
- **Icons.** The full `material-symbols` font is installed (no subset); `favorite` (FILL 0 = outline, `filled` =
  solid) and `chat_bubble` exist. DESIGN.md's glyph list names neither, `design/` is read-only and `lint-tokens`
  checks only icon sizes, so the addition is recorded in ANALYSIS.

## Defaults where the docs are silent (approved with the plan)

**API**
- `POST /api/v1/posts/{id}/like/` (`IsAuthenticated` + `IsEmailVerified`, throttle `like`, `get_or_create`): **201**
  `{"liked": true}` when new, **200** the same body when it already existed. `DELETE` (`IsAuthenticated` only,
  same throttle bucket as POST): **204** always. Check order: auth → permissions (401/403 never count) → throttle →
  lookup.
- **Which posts:** like and comment need a post the public can see: a deleted, removed, unknown or malformed id is a
  JSON 404 `not_found` (a removed post's author gets 404 too). Every other status is allowed, **pending and under
  review included** (ANALYSIS c1). Unlike works on a removed post (it deletes your row; a like can always be
  taken back) and is 404 only for unknown, malformed or deleted ids.
- `GET /api/v1/posts/{id}/comments/` (public, `never_cache`; a stale Bearer is a 401 as on the detail):
  `{results: [comment], next_cursor}`, **oldest first** on `(created_at, id)`, 20 per page (`?page_size=` ≤ 50).
  Excludes hidden and deleted comments. 404 when the post isn't visible.
- **Comment object (5 keys):** `{id, author: {id, username, display_name, avatar_url}, content, is_mine,
  created_at}` (`user_summary`; `is_mine` computed in Python from the request user).
- `POST …/comments/` `{content}` (verified user, throttle `comment` **on POST only**, as Part 4's `get_throttles`)
  → **201** the comment object. `content` is trimmed, 1–500 code points, with the posts' messages ("Write
  something first." / "Keep it to 500 characters."); undeclared fields are ignored.
- `DELETE /api/v1/comments/{id}/` (`IsAuthenticated`, no throttle, no verified email, as Part 5's delete) → **204**,
  sets `deleted_at` under a row lock. 403 `not_author` for others; 404 for an unknown, malformed, hidden or
  already-deleted comment or one on a post the public can't see (so a second delete is 404).
- **Counts:** `like_count` = rows in `likes`; `comment_count` = comments neither hidden nor deleted;
  `liked_by_me` = `Exists`. All correlated subqueries, so a list stays **1 query anonymous, 2 signed in** (the
  existing numbers) whatever it holds. A removed post's tombstone keeps its counts; nothing leaks.
- **Admin:** `LikeAdmin` read-only (like `FollowAdmin`). `CommentAdmin`: list (excerpt, author, post, hidden, deleted,
  created), filters (hidden, "By deleted at", created), search (content, author username), every field read-only, no
  add, change or delete. Actions **Hide comments** and **Unhide comments**, gated by `has_hide_permission`
  (`request.user.has_perm("social.change_comment")`); each changes only the rows that need it, writes a
  `LogEntry` per comment and reports the count. Unhide doesn't undelete.

**Frontend**
- **LikeButton** mirrors `FollowButton`: optimistic flip with rollback and an error toast, single-flight ref,
  `aria-pressed` with a stable name ("Like" in an `sr-only` span plus the count). States: session loading → an
  inert same-size look-alike (no layout shift); visitor → a `Link` to `/login?next=/p/<id>`; unverified →
  `aria-disabled` with the Part 2 toast "Verify your email to like posts."; verified → the button. You can like
  your own post. Liked = `<Icon name="favorite" filled>` in `text-secondary`; not liked = outline.
- **Local state, no global store.** The button holds `{liked, count}` seeded from props and re-synced with the
  "adjust state while rendering" pattern (MEMORY). A like made on one list is not copied into another list that
  shows the same post at the same moment (Recent and Following on `/home` both stay mounted); every route change
  refetches, so this is the only gap. Recorded as a known limit.
- **Action bar** (b1 classes `flex items-center gap-space-lg pt-space-sm border-t border-outline-variant/20
  text-outline font-label-code text-label-code`, glyph `lg` = 1.125 rem as b1/b3 use, not a1's 0.875): like, then
  a comment link (`chat_bubble` + count → `/p/{id}#comments`). Counts print with `formatCompactNumber` ("1.4K").
  No bar on a removed post's tombstone card. On the detail page the bar sits in the claim card's action row beside
  Copy link, with "Like" / "Comments" labels from `sm` up (b3's pattern), and the comment link is `#comments`.
- **Discussion section** after `SourceList`: `id="comments"`, heading "Comments" with the count (Stitch's "Public
  Discussion & Counter-Evidence", "Dispatches" and the "SECTION III" eyebrow become plain words per ANALYSIS) and an
  "Oldest first" label. **Composer** (b3's box: `focus-within:border-secondary`, `Textarea` with `maxCount={500}`
  and a hidden label): placeholder "Add a comment…", button "Comment", hint "Ctrl + Enter to post" from `sm` up,
  Ctrl/⌘+Enter submits, blank or over 500 code points is refused client-side with the server's messages, the draft
  is kept on a failure and cleared on success, the field is locked while posting. Visitor → "Log in to comment"
  (`loginRedirectFor`); unverified → a disabled composer with "Verify your email to comment." **Row**
  (b3's card classes): `Avatar` size 8, name linking to `/u/<username>`, `@handle`, relative time (full UTC date
  as `title`), text as plain `whitespace-pre-wrap break-words`, and for your own comment a "Delete" text button
  (Stitch's REPLY/REPORT button style) opening a confirm modal ("Delete this comment?"). Empty: `EmptyState`
  "No comments yet" / "Start the discussion." Loading: three skeleton rows. Error: `Alert` with Try again.
  **Load more comments** at the bottom (cursor).
- **Client-only fetch.** Comments are not server-rendered (they don't feed the metadata and the Workers CPU budget
  is tight); the page's light SSR is unchanged. Nothing renders for a removed post (a tombstone or its author's
  view), whose API answers 404.
- A new comment goes at the **end** of the loaded list (it is the newest). If older pages are still unloaded it
  stays at the end, and when they load the id is de-duplicated; this only shows beyond 20 comments.
- Comment drafts live in component state only (no provider, unlike post drafts).

## Files

**Backend (`backend/`)**
- New: `apps/social/engagement.py` (`with_engagement(queryset, viewer)`, `engagement_defaults(post)`),
  `apps/social/migrations/0002_like_comment.py` (normalised with ruff), tests below.
- Changed: `apps/social/models.py` (`Like`, `Comment`), `services.py` (`like`, `unlike`, `add_comment`,
  `delete_comment`, `visible_post_or_none`), `views.py` (like, comments list/create, comment delete),
  `urls.py` (three routes), `serializers.py` (`comment_data`), `pagination.py` (`CommentPagination`), `exceptions.py`
  (if a comment-specific error is needed), `admin.py`, `feed.py` (`load_posts(ids, viewer)`);
  `apps/posts/models.py` (`for_list(viewer=None)` with a local import of `social.engagement`, commented as the one
  deliberate dependency back on social), `serializers.py` (strict counts), `views.py` (pass `viewer`; zeros on the
  201); `apps/core/pagination.py` (docstring); the content field shared with the posts serializer (extract if it
  isn't importable); existing tests that pin the zero placeholders or build `PostSerializer` input directly.

**Frontend (`frontend/`)**
- New in `src/features/social/`: `LikeButton`, `CommentCountLink`, `PostActions`, `CommentSection`, `CommentComposer`,
  `CommentList`, `CommentItem`, `DeleteCommentModal`, `useComments` (a thin wrapper over `useCursorFeed`) and a
  `*.test.tsx` for each.
- Changed: `features/social/social-api.ts` (+tests; export `withCursor`), `messages.ts` (`likeFailureMessage`,
  `commentFailureMessage`, verify messages), `test-helpers.tsx`; `lib/api/types.ts` (`Comment`);
  `features/posts/{PostCard,FeedList,PostDetail,useCursorFeed}.tsx/.ts` + tests (`PostCard` gets `actions?:
  ReactNode`; `useCursorFeed` gets `append` and `remove`; if that gets awkward, a dedicated `useComments` hook
  instead); `e2e/social.spec.ts` (+ likes and comments tests), `e2e/posts.spec.ts` (a card now has more links).

**Docs:** ARCHITECTURE §2 (comments: `deleted_at`, the partial index replaces the plain `(post, created_at)`),
§8, §9 (like/comment endpoints, comment object, the annotations sentence), §10 (Part 7 bullet); ANALYSIS (a new
c-38 row for the three decisions and the glyphs; the Like/Comments rows); STRUCTURE; MEMORY (1 or 2 entries);
`task.md` (criteria, deviations, both status spots); this plan's status line; `docs/test-command.md` "Part 7" in
**both** guides (Linux blocks run verbatim from the doc); HANDOFF.

## Steps (ordered; each ends green before the next)

0. **Start.** `git status` (clean at `15c1d8a` plus the plan and HANDOFF edits), `docker compose up -d` and confirm
   healthy (it was down on 2026-10-10), ports 3000/8000 free. (The plan is already saved and linked, and HANDOFF's
   "uncommitted" text already corrected.)
1. **Models + migration.** `Like` (bigint id, user and post FKs CASCADE, `db_index=False`, `created_at` default
   `timezone.now`; `likes_pair_unique`; `likes_post_created_idx` on `(post, created_at)`). `Comment` (uuid id, post FK
   `db_index=False`, author FK with its default index for account deletion and export in Part 14, `content`,
   `is_hidden`, `deleted_at`, `created_at`; check `comments_content_length` 1–500; partial index
   `comments_post_visible_idx` on `(post, created_at, id)` where not hidden and not deleted). `makemigrations`,
   `ruff check --fix . ; ruff format .`, review `sqlmigrate`.
2. **Services** (`social/services.py`): `like` (visible post, `get_or_create`), `unlike`, `add_comment` (visible post,
   `now` parameter), `delete_comment` (row lock, visibility rules above, sets `deleted_at`). One write path, so
   Part 13 can hook notifications in later.
3. **Annotations.** `social/engagement.py` + `for_list(viewer)`; thread `viewer` through the four call sites and
   `load_posts`; make `PostSerializer` read strictly; zeros on the create 201.
4. **Views, URLs, pagination, serializers** per the API defaults. Routes:
   `v1/posts/<str:post_id>/like/`, `…/comments/`, `v1/comments/<str:comment_id>/` (ids parsed by hand with
   `parse_post_id`, never a `<uuid:>` converter). Backend tests + mutation checks.
5. **Admin** (`LikeAdmin`, `CommentAdmin` with Hide/Unhide) + tests.
6. **Frontend data layer:** types, `social-api`, `messages`, `useCursorFeed` `append`/`remove`, `useComments`.
7. **Frontend UI:** `LikeButton`, `CommentCountLink`, `PostActions`, the `PostCard` slot, `FeedList`; then
   `CommentComposer`, `CommentItem`, `CommentList`, `DeleteCommentModal`, `CommentSection` and `PostDetail`.
   Screenshots at 1280 and 390 px next to Stitch b1/b3 (headless Chromium via Playwright, scratchpad scripts).
8. **E2E** in `social.spec.ts`; update `posts.spec.ts` for the new links.
9. **Docs, `task.md`, plan status, HANDOFF**; run the Linux blocks of the new `test-command.md` section verbatim
   against live Django and `next dev`; record cleanup of the test accounts.

## Tests

**Backend** (new files under `apps/social/tests/`; every list endpoint keeps pinned query counts)
- `test_models_engagement`: both constraints, blank and 501-code-point content (emoji = 1), cascades, the index and
  partial-index definitions.
- `test_services_engagement`: idempotent like (get_or_create), unlike of a removed post, comment rules, a
  `run_together` race (`transaction=True`) for two simultaneous likes by one user (one row) and for N users (count
  N), and for two simultaneous deletes (one success, one 404) **with a control run** that proves the lock.
- `test_api_like`: 201 → 200 → 204 ×2, 401, 403 `email_unverified`, 404 matrix (unknown, malformed, deleted,
  removed), pending and under-review allowed, the real 300 + 1 throttle test with `Retry-After`, 401/403 not
  counted, unlike shares the bucket.
- `test_api_comments`: oldest-first order, cursor stability while a comment arrives, a crafted cursor → 404, hidden
  and deleted excluded, 404 for a removed or deleted post, the 5-key shape, `is_mine`, anonymous OK, stale Bearer
  → 401, page size, **2 queries anonymous / 3 signed in at 3 and 20 comments**.
- `test_api_comment_create`: 401, 403, validation (blank, whitespace, 500 vs 501, emoji, undeclared fields), trim,
  throttle on POST only (GET never counts; the real 60 + 1 requests), 404 states, no network.
- `test_api_comment_delete`: author 204 and the row survives with `deleted_at`, 403 `not_author`, 404 repeat /
  hidden / unknown / malformed, `comment_count` drops, 401.
- `test_engagement_counts`: real counts in Recent, detail, profile posts and the Following feed (also on a cache
  hit, where ids are cached and counts are fresh); hidden and deleted comments not counted; `liked_by_me` per
  viewer, false for visitors; the tombstone keeps counts; **constant queries at 3 and 20 posts with likes and
  comments**; the strict serializer raises for an unannotated post.
- `test_admin_engagement`: both changelists, read-only, Hide/Unhide as superuser, a staff user without
  `change_comment` can't, `LogEntry` written, an already-hidden row isn't re-logged, Unhide of a deleted comment
  leaves it deleted.
- Changed: `test_api_create` (23 keys, zero counts on the 201), `posts/test_models.for_list`, the query-count tests
  in posts and social, `core/test_pagination`.
- **Mutation checks** (a rule removed by hand, a test must fail), about 15: the like pair uniqueness, `get_or_create`,
  each of the visible-post filters, the hidden and deleted filters in the list and in the count, `liked_by_me` user
  filter, the verified-email permission, the throttle scopes, the author check, the delete lock, the content limit,
  the cursor guard, ascending order, `is_mine`, the Hide permission.

**Frontend** (Vitest + RTL, tests beside the code): `LikeButton` (optimistic, rollback and toast per error code,
single-flight in one tick, the loading, visitor and unverified states, `aria-pressed`, re-sync when props change,
count format), `PostActions`, `CommentComposer` (counter, blank, over 500, Ctrl/⌘+Enter, locked while posting, draft
kept on failure and cleared on success, visitor and unverified states), `CommentItem` (plain-text rendering,
Delete only on yours), `CommentList` (loading, empty, error + retry, load more, append, remove, de-duplication),
`DeleteCommentModal`, `CommentSection` mounted behind a settled session inside `<StrictMode>` (MEMORY: the detail
bug), `useCursorFeed` `append`/`remove`, `PostCard` actions slot, `FeedList` (bar on posts, none on the tombstone),
`PostDetail` (section shown, hidden for removed, count sync), `social-api`, `messages`.
**E2E** (added to `social.spec.ts`, shared accounts): B likes A's post from the feed (count 1, survives a reload),
unlikes; B comments on the post page (appears, count shows on the card after going back), A sees it, B deletes it.

## Verification (end to end)

- Backend (`backend/`, venv): `python -m pytest`, `ruff check .`, `ruff format --check .`,
  `python manage.py makemigrations --check --dry-run`, `python manage.py check`; `sqlmigrate social 0002`
  reviewed; `EXPLAIN ANALYZE` (rolled-back transaction) for the comment list, the count subquery and the like
  count to prove `comments_post_visible_idx` and `likes_post_created_idx` are used.
- Frontend (`frontend/`): `npm run lint`, `lint:tokens`, `typecheck`, `format:check`, `npm test`,
  `NEXT_PUBLIC_GOOGLE_CLIENT_ID= npm run build`, `npm run test:e2e` (dev, five runs in a row) and
  `CI=1 npm run test:e2e` after the build.
- Manual: curl against `runserver` for every API row above (the doc's own blocks, extracted and run verbatim);
  headless-Chromium screenshots at 1280 and 390 px with **0 px horizontal overflow** on `/home` and `/p/[id]`;
  a Django-admin check of Hide/Unhide.
- Record every command and result in `HANDOFF.md`; tick the four acceptance criteria in `task.md` with notes
  ("Like toggling is idempotent and counts stay correct under concurrent requests", "Unverified users get 403;
  comments over 500 chars are rejected", "Hidden comments disappear for everyone but staff", "Feed queries stay
  constant with annotations").

## Stop conditions

Stop and ask before continuing if: a test, lint or type check fails for a reason the plan didn't anticipate; the
partial index isn't used by the count query; a new dependency, service or env variable looks necessary; anything in
`design/` would need to change; the E2E suite exceeds the sign-up budget; or the work reaches past Part 7 (7B's
reposts and bookmarks, 8's reports, 13's notifications). Docker not healthy is a stop until fixed.

## Follow-ups to record (not done here)

- Part 13: notification hooks in the `social.services` write paths (skip deleted and hidden comments; de-duplicate
  likes per ARCHITECTURE §2).
- Part 8: decide whether `counts_toward_threshold` ("≥1 post or comment") counts a soft-deleted comment; the
  principle used for posts and the fact quota says it does.
- Part 7B: `repost_count`, `reposted_by_me`, `bookmarked_by_me` join `with_engagement`; 11D's daily comment counts
  must use the same predicate as the partial index.
- Part 10: grant `social.change_comment` to the Moderators group (the Hide/Unhide actions are already gated on it);
  review queues skip deleted comments.
- Part 16: the `like` and `comment` rates are guesses; counts are correlated subqueries (denormalised counters if a
  post reaches many thousands of likes); the cursor guard for any list still on the bare core pagination; Part 18:
  Workers CPU of `/p/[id]` with the comment section (client-only, so unchanged server-side).
- Known limits: a like isn't mirrored into a second mounted list; comment drafts aren't kept across navigation;
  no live comment updates.
