# Plan: Part 7B, Bookmarks & reposts

- **Status:** APPROVED by the user (Sanjoy Rozario) on 2026-10-10, together with the four decisions and the
  defaults below. Saved here and linked from `HANDOFF.md`. **IMPLEMENTED 2026-10-10** (Claude, Sonnet 5.5).
  Deviations: see `task.md` Part 7B and `docs/agents/HANDOFF.md` (the third repost branch was **not** built: `EXPLAIN`
  at 300,000 reposts showed it no faster; the repost button's visible word is "Repost", not "Reposts"; the unverified
  hint is short and its toast long, as `LikeButton`'s; `BookmarkAdmin` has no `has_module_permission` override, which
  was redundant; `visibleItems` and `isUnavailable` live in a new `features/posts/feed-items.ts`). Drafted 2026-10-10
  by Claude (Opus 5.5).
- **Implement with:** Sonnet 5.5 · high (task.md).
- **Evidence (read-only):** HANDOFF, MEMORY, `task.md` Part 7B (+ the Part 7 record), ARCHITECTURE
  §2/§3/§4a/§4d/§8/§9/§10, ANALYSIS (D5, b1/b3/c1 rows, ActionBar row, f-4), STRUCTURE, the Part 7 plan,
  `apps/social/{feed,views,services,models,engagement,admin,pagination}.py`, `apps/posts/{models,serializers,
  views,pagination}.py`, `apps/core/pagination.py`, two Explore passes (the frontend feed/social code; Stitch
  a1/b1/b3/c1 + DESIGN.md) and a Plan-agent review of the feed cursor (folded in: the redundant `<= t`,
  integer-microsecond tokens, the full key in the cache, `FOR NO KEY UPDATE`, the empty-page rule, the test list).
  A read-only prototype confirmed that
  Django 5.2.17 compiles two ordered, sliced `values_list` querysets joined by `union(all=True)` into
  `(SELECT … ORDER BY … LIMIT n) UNION ALL (SELECT … ORDER BY … LIMIT n) ORDER BY 1 DESC, 2 DESC, … LIMIT n`.

## Context

Part 7B adds **private bookmarks** and **plain reposts** (D5; ARCHITECTURE §4d). The post object already carries
`repost_count`, `reposted_by_me` and `bookmarked_by_me`, but as literal `0`/`false` (`apps/posts/serializers.py:132-135`);
the `repost` (100/h) and `bookmark` (300/h) throttle rates already exist in `settings.py`; the frontend types
already have `FeedItem` with `kind: "repost"` and `UnavailablePost` (`src/lib/api/types.ts:76-83`), and
`feedItemKey` already keys a repost as `repost:<reposter>:<post>`. `/bookmarks` is a placeholder page, already
in the rail, the phone sheet and `PROTECTED_PREFIXES`. The hard part is the **Following feed**, which must mix
posts and reposts with a stable cursor and at most one copy of a post per page.

**Dependency check (2026-10-10).** Part 7B depends on **Part 6** (`[x] Done (2026-10-09)`) and **Part 7**
(`[x] Done (2026-10-10)`), both in the summary table and in their sections. Their chains (5, 4, 1, 0C, 0A/0B/0D,
plus 2 and 3) are Done. Open, not blocking: Part 3 criterion 4 (real-Google check), CI for Parts 2 to 7.
**Workspace:** HEAD `c562e70` ("Implemented Part 7…"), tree clean; Docker Postgres + Redis up and healthy.
HANDOFF still calls Part 7 "uncommitted" (the user committed it): step 0 fixes that text.

**Your decisions (2026-10-10):**
1. **Bookmark admin: superusers only.** `BookmarkAdmin` is registered read-only, and only a superuser can open
   it (moderators never see anyone's bookmarks, even after Part 10 grants permissions).
2. **A repost of a deleted or removed original can be taken back.** `DELETE …/repost/` is 204 whenever the post
   row exists (deleted and removed included); your own "no longer available" card has **Undo repost**.
3. **The page hides later repeats.** Once a post is on screen, an older activity of it on a later page is not shown
   again (all feed lists); the API keeps its "once per page" rule.
4. **Profile chips filter reposts by the original's type** (reposts of facts under Facts, of opinions under
   Opinions; All shows everything).

## Scope

**In:** `social.Repost`, `social.Bookmark` + migration `0003`; repost/unrepost, bookmark/unbookmark,
`GET /api/v1/me/bookmarks/`; `repost_count`, `reposted_by_me`, `bookmarked_by_me` in `with_engagement`; the mixed
Following feed and profile lists (a new keyset timeline), cache v2; `RepostAdmin`, `BookmarkAdmin`; `RepostButton`,
`BookmarkButton`, `RepostHeader`, `UnavailablePostCard`, the action bars, `/bookmarks`; tests, E2E, docs.

**Not in 7B:** score effects of reposts (11B: `status_at_repost` is only recorded), the `repost` notification (13),
reports and the flag button (8), quote reposts or a repost menu, client-side insertion of your new repost into an
open list, Recent changes (originals only), any new dependency, service or env variable.

## What the research found (all handled below)

- **DRF's cursor can't page a union.** `CursorPagination` filters the queryset (`created_at__lt=…`), and Django
  refuses `filter()` after `union()`. The mixed lists need their own keyset paginator; the filter goes into each
  side before the union. Recent and the bookmark list stay on DRF's cursor.
- **Repost ids are bigint, post ids uuid** (AGENTS.md, §2), so no single "item id" column exists. The sort key
  becomes `(activity_at, kind, post id, reposter id)`, which is unique without the repost's own id (one repost per
  user and post). This is task.md's "(activity_at, item id)" in a form both tables share; recorded as a deviation.
- **`with_engagement` is the one place for counts** (MEMORY Part 7); the three new fields join it and
  `PostSerializer` reads them strictly, so no list can forget them.
- **Frontend assumptions to undo:** `FeedList` renders only `kind === "post"` (`FeedList.tsx:94-99`, pinned by the
  test "leaves reposts out (Part 7B)"); `pendingPostIds` skips reposts (`status-overlay.ts:33`, pinned by
  `status-overlay.test.ts:44-57`); the `gone` filter ignores reposts; `PostCard` has no header slot.
- **Duplicate DOM ids:** `LikeButton` uses a module-constant hint id (`"like-hint"`), so a feed of unverified
  viewers repeats it; with three hinted buttons per card this gets worse. The new buttons use `useId()` and
  `LikeButton` is switched to it (a one-line fix of the action bar it shares). `FollowButton` has the same bug: a
  follow-up, not touched.
- **Stitch:** b1/b3 put `cached` + count in the left group (b3 labels it "Citations", which becomes "Reposts", f-4)
  and `bookmark_border` alone on the right (`justify-between`; the flag button is Part 8). No screen shows a filled
  `bookmark`, a "Reposted by" header, an unavailable card or a bookmarks page; DESIGN.md's glyph list has `cached`
  but not `bookmark`/`bookmark_border` (recorded in ANALYSIS as Part 7 did for `favorite`).
- **E2E sign-up budget:** the suite uses 16 of allauth's 20 sign-ups a minute. 7B's three-person test seeds the
  post's author and post with `manage.py shell` (no sign-up, no login) and reuses the two shared accounts.

## The mixed timeline (Following feed and profile lists)

New module `apps/social/timeline.py` (pure helpers + one query builder); `feed.py` keeps the caching.

- **Item key**, sorted descending, all non-null:
  post item `(post.created_at, 0, post.id, ZERO_UUID)`; repost item `(repost.created_at, 1, repost.post_id,
  repost.user_id)`. Unique because a post is unique by id and a repost by (user, post).
- **Cursor token** = base64url of `"<epoch microseconds>|<kind>|<post uuid>|<reposter uuid>"` (an integer, not ISO:
  `isoformat()` drops `.000000` and offsets vary; convert with `EPOCH + timedelta(microseconds=n)`, never a float).
  Decoding is strict: exactly four fields, kind 0 or 1, kind 0 requires the zero reposter, canonical UUIDs
  (`str(UUID(s)) == s`); `ValueError` (covers `binascii.Error`, `UnicodeDecodeError`), `OverflowError` and
  `TypeError` all answer a JSON 404 `not_found`. An empty `cursor=` is the first page (not cached, as today).
  `page_size` is read with `FeedPagination().get_page_size(request)` (junk → 20, > 50 → 50, DRF parity). Old DRF
  tokens from Part 6 clients are 404, and `useCursorFeed` already restarts from the top on a cursor 404.
- **Query:** for each side, a Q for "key < cursor" built from the cursor's constants **plus a redundant
  `created_at <= t`** (the OR alone can't become an index condition, so a deep page would scan from the top):
  post side `created_at <= t AND (created_at < t OR k = 1 OR id < ref)`; repost side `created_at <= t AND
  (created_at < t OR (k = 1 AND (post_id < ref OR (post_id = ref AND user_id < by))))`. Each side is ordered by its
  own columns (posts `created_at DESC, id DESC`, which `posts_recent_idx` serves; reposts `created_at DESC, post_id
  DESC, user_id DESC`) and sliced to `F = 2 × page_size + 1`, then `union(all=True)`, ordered by the four columns and
  sliced to `F`; the zero reposter is `Value(ZERO_UUID, output_field=UUIDField())`. Following: posts =
  `Post.objects.visible()` by followed ∪ me (today's `following_queryset`); reposts = every repost by followed ∪ me,
  whatever the original's state (so unavailable ones show). If `EXPLAIN` on seeded data shows a sequential scan of
  reposts, "my reposts" becomes a third sliced branch (same key). Profile: the user's visible posts and the user's
  reposts; `?post_type=` filters posts and, through a join, the reposts' originals.
- **Per-page dedupe** (pure `take_page(rows, size)`), formally: *a page is the longest prefix of the next `2 × size`
  rows that holds at most `size` distinct posts, showing only the first (most recent) row of each post.* Dropped rows
  are consumed. `next_cursor` = the key of the prefix's last row when any fetched row (the probe, row `F`, included)
  follows it, else null. The first row is always kept, so every page advances; a page holds at most `size` items and
  may hold fewer (already allowed, §9); 60 reposts of one post in a row give a one-item page, and the post may show
  again on the next page with another reposter (the frontend hides that repeat, decision 3). New posts and reposts
  always sort above any cursor, so nothing is skipped or repeated across pages while they arrive. Profiles never
  dedupe (you can't repost your own post), so their pages are always full.
- **Hydration:** posts with `Post.objects.visible().for_list(viewer).filter(pk__in=…)` (a post item whose post is
  gone is dropped; a repost item whose original isn't visible becomes `{"id", "unavailable": true}`). **Following:**
  reposts are re-read with an OR of `Q(user_id=…, post_id=…)` pairs (the unique index; not `user_id__in ×
  post_id__in`, which over-fetches) + `select_related("user")`, and matched on the pair **and** `created_at`, so an
  undone, or undone-and-redone, repost drops its item from a cached page instead of showing out of order.
  **Profile:** no re-read; the reposter is the profile's user and `activity_at` comes from the union row.
- **Queries** (an empty `__in`/pair list makes no query, so tests seed both kinds and pin each case at 3 and 20
  items): Following 4 on a miss / 3 on a hit with reposts, 3 / 2 with posts only (today's numbers); profile posts
  3 anonymous / 4 signed in; bookmarks 3.
- **Cache v2:** `social:following-feed:v2:<user_id>` → `{"items": [[at_us, kind, post_id, reposter_id], …], "next":
  token | null}` (the full key), strict shape check (malformed = miss). Busted (now + `on_commit`) by follow, unfollow,
  `create_post`, **repost and unrepost**. Other people's reposts reach you after at most the TTL, like their posts.
- **Accepted limits (documented in §9 and tested):** if the repost that won a page's dedupe is undone, a follower's
  cached page loses that post until the TTL (the hidden item went with it); a page can then be empty while `next` is
  set, so `FeedList` shows the empty state only when nothing more can load (otherwise Load more). As in v1, a row whose
  transaction commits after a reader paged past its timestamp is missed by that walk; the repost transaction is kept
  short.

## Defaults where the docs are silent (approved with the plan)

**API**
- `POST /api/v1/posts/{id}/repost/` (`IsAuthenticated` + `IsEmailVerified`, throttle `repost`, shared with DELETE):
  **201** `{"reposted": true}`, **200** the same when it existed (the first row and its `status_at_repost` are kept).
  Order: auth → permissions (401/403 never count) → throttle → lookup. **404** unknown, malformed, deleted, removed;
  then an existing repost answers **200** (so a post that turned FALSE after you reposted it doesn't 409); then
  **409 `cannot_repost_own`** "You can't repost your own post."; then **409 `cannot_repost_false`** "Posts labelled
  FALSE can't be reposted." (only `verified_false`; pending, published, verified true and under review are allowed).
  The service locks the post row with `select_for_update(no_key=True)` inside `atomic()` (it still serialises with
  status writes, but doesn't block the `FOR KEY SHARE` locks that like, comment and bookmark inserts take on a busy
  post), so `status_at_repost` is the status at commit, and uses `get_or_create`. `Repost.created_at` uses
  `default=timezone.now`. A DB check limits `status_at_repost` to those four allowed statuses.
- `DELETE …/repost/` (`IsAuthenticated`): **204** always when the post row exists, deleted and removed included
  (decision 2); 404 unknown or malformed. Both bust the reposter's feed cache.
- "Reposting a repost reposts the original" holds by construction: a repost has no id of its own in the API, and a
  repost item's buttons act on `post.id`, the original (a frontend test pins it).
- `POST /api/v1/posts/{id}/bookmark/` (`IsAuthenticated` only, throttle `bookmark`, shared with DELETE): **201**
  `{"bookmarked": true}` / **200**; 404 unknown, malformed, deleted, removed; your own posts, FALSE and pending are
  allowed. `DELETE`: **204** always, also on a removed post; 404 unknown, malformed, deleted (mirrors unlike).
- `GET /api/v1/me/bookmarks/` (`IsAuthenticated`, not verified-only, `never_cache`; a stale Bearer is 401): the §9
  envelope (`pinned: []`), items `{"kind": "post", "post", "reposted_by": null, "activity_at": <bookmark time>}`,
  newest bookmark first on `(created_at, id)` (`BookmarkPagination`: `TimestampCursorMixin`), deleted and removed
  posts dropped in the bookmark query (pages stay full), `?page_size` ≤ 50, **3 queries**. Only ever the caller's.
- **Counts:** `repost_count` counts every repost row; `reposted_by_me` and `bookmarked_by_me` are `Exists`
  (false for visitors). A removed post's tombstone keeps its counts. No bookmark count anywhere.
- **Admin:** `RepostAdmin` read-only (user, post, status at repost, created; filter by status; search username).
  `BookmarkAdmin` read-only and **superuser-only** (`has_module_permission`/`has_view_permission` →
  `is_superuser`), no add/change/delete (decision 1).

**Frontend**
- **`PostActions`** takes the post: left group Like · Comments · Repost (`gap-space-lg`), right group Bookmark
  (b1's `justify-between`, `gap-space-md`); on the post page "Like", "Comments", "Reposts" words from `sm` up (b3);
  the bookmark is a glyph only.
- **`RepostButton`** mirrors `LikeButton`: `cached` (1.125 rem), `text-secondary` when reposted, `aria-pressed`, one
  `sr-only` name "Repost 3"; optimistic ±1, single-flight ref, rollback + toast (`repostFailureMessage`: the 409
  reasons, `email_unverified`, 429 with the wait, 404, 401, network, waking). Loading → inert look-alike; visitor →
  a link to `/login?next=/p/<id>`; **disabled with the reason** (`aria-disabled`, `title`, an `aria-describedby`
  hint from `useId`, a click toasts the reason) for your own post, a FALSE post or a removed post, unless you already
  reposted it (then it stays enabled, so you can take it back); unverified → `aria-disabled` + "Verify your email to
  repost posts…" unless already reposted.
- **`BookmarkButton`:** `bookmark_border`, filled `bookmark` in `text-secondary` when saved, `sr-only` "Bookmark" +
  `aria-pressed`, no count; any signed-in user (unverified too); optimistic + rollback + toast; visitor → login link.
- **`PostCard`** gets a `header?: ReactNode` slot (first in the card, `relative z-10`). **`RepostHeader`**: `cached`
  (sm) + "Reposted by " + a link to `/u/<username>` showing the display name or `@username` (§2's fallback), in
  `font-label-code text-label-code text-outline`.
- **`UnavailablePostCard`:** the tombstone card's look (neutral, `block` glyph) with the `RepostHeader` and "This post
  is no longer available"; when the repost is yours, an **Undo repost** text button (decision 2): on success the item
  is removed from the list (`feed.remove(key)`) with a toast; on failure a toast.
- **`FeedList`:** renders repost items (header + card, or the unavailable card); a repost whose original is polled as
  `removed` or vanishes becomes the unavailable card; `pendingPostIds` includes reposts of pending posts; **later
  repeats are hidden** (an item whose post id already rendered higher up is skipped; decision 3), which also keeps one
  post's buttons from drifting apart in one list; React keys stay `feedItemKey` (`repost:<reposter>:<post>`). The
  empty state shows only when the list is empty **and** nothing more can load (a cached page can come back empty
  with a cursor); otherwise Load more.
- **`/bookmarks`** (`features/bookmarks/BookmarkList.tsx`; route stays thin, `robots: noindex`): the profile page's
  container classes, a visible `h1` "Bookmarks" (c4's header), `FeedList` over `useCursorFeed` (`resetKey` = user id),
  polling of pending posts, empty state (`bookmark` glyph) "No bookmarks yet" / "Posts you bookmark appear here.
  Only you can see them.", Load more. Un-bookmarking keeps the card until the next load (as "unfollowing in a list
  keeps the row", Part 6).
- Your new repost isn't inserted into an open list (the next load shows it; the server clears your Following cache).

## Files

**Backend (`backend/`)**
- New: `apps/social/timeline.py`; `apps/social/migrations/0003_repost_bookmark.py` (ruff-normalised); tests below.
- Changed: `apps/social/models.py` (`Repost`, `Bookmark`), `services.py` (`repost`, `unrepost`, `bookmark`,
  `unbookmark`, the two refusals), `exceptions.py` (`CannotRepostOwnError`, `CannotRepostFalseError`, 409),
  `engagement.py` (three annotations, defaults), `feed.py` (v2 cache over the timeline), `views.py` (`RepostView`,
  `BookmarkView`, `BookmarkListView`; `FeedView` and `UserPostsView` on the timeline), `urls.py`, `pagination.py`
  (`BookmarkPagination`), `serializers.py` (repost item, unavailable stub), `admin.py`; `apps/posts/serializers.py`
  (strict reads; `feed_item(post_data, activity_at=None)`). Existing tests that change on purpose:
  `test_feed_cache` (the `{"ids","next"}` shape test, and the malformed-value and wrong-case tests, which would pass
  for the wrong reason against v2), `test_services` (cache-bust tests that seed `{"ids": …}`), `test_api_user_posts`
  (query count 2/3 → 3/4), `test_engagement_counts` (the constant-queries table gains reposts and `/me/bookmarks/`),
  `posts/tests/test_api_create` (`POST_KEYS` values). The crafted-cursor tests stay valid.

**Frontend (`frontend/`)**
- New: `features/social/{RepostButton,BookmarkButton,RepostHeader,UnavailablePostCard}.tsx`,
  `features/bookmarks/BookmarkList.tsx`, a `*.test.tsx` for each.
- Changed: `features/social/{PostActions,LikeButton,social-api,messages,test-helpers}`;
  `features/posts/{PostCard,FeedList,PostDetail,status-overlay,test-helpers}` (+ `repostEntry`/`unavailableEntry`
  factories) and their tests (`FeedList.test` "leaves reposts out (Part 7B)" and `status-overlay.test` L44-57 flip on
  purpose); `app/(app)/bookmarks/page.tsx`; `e2e/helpers.ts` (`seedPost`, `setPostState` `verified_false`),
  `e2e/social.spec.ts`.

**Docs:** ARCHITECTURE §2 (reposts/bookmarks: indexes, the `status_at_repost` check), §8 (both admins), §9 (7B
endpoints, the timeline key and token, query counts, cache v2), §10 (a 7B bullet); ANALYSIS (c-39: the four
decisions, the key deviation, glyphs and unbuilt Stitch screens); STRUCTURE; MEMORY; `task.md`; this plan's status
line; `docs/test-command.md` "Part 7B" in **both** guides; HANDOFF.

## Steps (each ends green before the next)

0. **Start.** `git status` (clean at `c562e70` plus this plan and HANDOFF); `docker compose ps` healthy; ports
   3000/8000 free; fix HANDOFF's "Part 7 uncommitted" text.
1. **Models + migration** (`Repost`: bigint id, FKs `db_index=False`, `status_at_repost` `TextChoices` + check,
   `reposts_pair_unique`, `reposts_post_created_idx (post, created_at)`, `reposts_user_created_idx (user,
   -created_at, -post)`; `Bookmark`: `bookmarks_pair_unique`, `bookmarks_user_created_idx (user, -created_at,
   -id)`); related names mirror `Like`; `(user, -created_at, -post)` gives per-user range scans and index-only scans
   of the four selected columns, and serves the profile as a plain ordered scan. `makemigrations`, `ruff check --fix . ; ruff format .`, review `sqlmigrate`.
2. **Services** + the cache bust; model and service tests, races.
3. **Engagement** annotations and defaults; strict serializer; count tests.
4. **Timeline** (`timeline.py`), then `feed.py` v2 and the two views; timeline and feed tests (the brute-force test
   first).
5. **Endpoints** (repost, bookmark, bookmark list), URLs, admin; API and admin tests; mutation checks.
6. **Frontend data layer:** `social-api` (`repostPost`, `unrepostPost`, `bookmarkPost`, `unbookmarkPost`,
   `fetchBookmarks`), `messages`, test factories, `pendingPostIds`.
7. **Frontend UI:** buttons, `PostActions`, `LikeButton` `useId`, `PostCard` header, `RepostHeader`,
   `UnavailablePostCard`, `FeedList`, `PostDetail`, `BookmarkList` + route. Screenshots at 1280 and 390 px.
8. **E2E** in `social.spec.ts` (+ helpers).
9. **Docs, `task.md`, plan status, HANDOFF**; run the new `test-command.md` Linux blocks verbatim against live Django
   and `next dev`; clean up the guide's test accounts.

## Tests

**Backend** (`apps/social/tests/`)
- `test_models_repost_bookmark`: both pair constraints, the `status_at_repost` check, cascades, index definitions.
- `test_services_repost_bookmark`: every refusal and its order, allowed statuses, `status_at_repost` kept on a
  repeat, unrepost on deleted/removed, bookmark rules; `run_together` races (`transaction=True`): two simultaneous
  reposts (and bookmarks) by one user → one row; six users → count 6; the cache bust now and at commit.
- `test_timeline` (pure): `take_page` as a table (no duplicates; a duplicate inside the window; trailing duplicates
  after `size` kept; the stop at the first new post; a window of one post → one item, cursor at row `2·size − 1`,
  `next` set; fewer than `F` rows → `next` null; exactly `2·size` rows all walked → null; size 1); the token
  (round-trips with microseconds 0 and 999999 and both kinds; every rejection above → 404); the two key filters.
- `test_timeline_db`: tie order with frozen `created_at` (repost before post, then post id, then reposter, all
  descending); 10 items on one timestamp page cleanly; one side with 3 × `F` older rows than the other (the per-side
  slice); the row a cursor points at deleted → the next page is still right; **arrivals during a walk** (page size 2;
  before each fetch add a new post, a repost of a seen post and one of an unseen post: the pages concatenate to the
  starting snapshot); **changes during a walk** (an unseen repost undone disappears; an unrepost + repost moves to the
  top and isn't repeated).
- **Randomised brute force** (`random.Random(seed)`, seeds 0 to 49; hypothesis isn't installed), with the cache on
  and off: me, 3 to 5 followed users and a stranger, 30 to 80 posts and reposts, timestamps from a pool of 4 instants
  (ties everywhere), random deleted and removed originals, page size in {1, 2, 3, 5}. Phase 1: pages equal a Python
  reference (sort on `(at, kind, ref, by)`, apply the formal rule) item by item (kind, post id, reposter, activity,
  unavailable) and end with `next` null. Phase 2, random changes between fetches: keys strictly decrease across pages,
  no key twice, no post twice in a page, at most `size` per page, every surviving original item is shown unless a
  same-page item of its post with a larger key is, and the walk ends within N + 1 requests.
- `test_api_feed_reposts` (+ changes to `test_api_feed`, `test_feed_cache`): mixed items, the stub shape for deleted
  and removed originals, my reposts, reposts of my posts, per-page dedupe (newest wins; stubs dedupe too), a
  cross-page repeat allowed, cached page 1 + live page 2 = the uncached walk, the cached `next` still valid after
  arrivals, an undone (or redone) repost dropped on a cache hit, a follower's cached page losing a post whose winning
  repost was undone and getting it back after the TTL, v2 shape, busting on repost **and** unrepost (now and at commit;
  followers' caches untouched), **4 / 3 queries with reposts, 3 / 2 posts only**.
- `test_api_user_posts` (changed): reposts included, stubs too, chips by the original's type, 400 still for a bad
  `post_type`, pages always full, **3 / 4 queries**.
- `test_api_repost`, `test_api_bookmark`: 201 → 200 → 204, every code, 401/403, the real 100 + 1 and 300 + 1 throttle
  runs with `Retry-After`, DELETE shares the bucket, 401/403 don't count.
- `test_api_bookmark_list`: only your own (two users), order, deleted and removed dropped with full pages, cursor and a
  crafted one (404), unverified allowed, anonymous 401, **3 queries at 3 and 20**.
- `test_engagement_counts` (changed): the three fields per viewer, visitors false, the tombstone keeps counts, the
  strict serializer raises without them, constant queries.
- `test_admin_repost_bookmark`: both read-only; `BookmarkAdmin` 403 for a moderator even with `view_bookmark`, 200 for
  a superuser.
- Changed: `posts/test_api_create` (zeros on the 201), `test_no_network`.
- **Mutation checks** (about 28): each refusal, the refusal order (existing before own/FALSE), the row lock,
  `get_or_create` (both), the `status_at_repost` value, unrepost on deleted, the unrepost cache bust, bookmark without
  verification, both throttle scopes, each key-filter branch, the redundant `<= t` (an `EXPLAIN` assertion or a query
  text check), the dedupe, "first wins", the probe/next rule, the kind-0 zero-reposter check, the unavailable stub, the
  repost re-read and its `created_at` match, the v2 shape check, the cache bust, the `post_type` join, the bookmark
  list owner filter, its removed filter, the `reposted_by_me`/`bookmarked_by_me` viewer filters, the admin superuser
  gate.

**Frontend** (Vitest + RTL): `RepostButton` (optimistic, rollback and toast per code, single-flight in one tick, the
three disabled reasons, enabled to undo, unverified, visitor, loading, `aria-pressed`, re-sync), `BookmarkButton`
(same minus reasons; unverified allowed), `RepostHeader`, `UnavailablePostCard` (Undo only on yours, removal and
toasts), `PostActions` (both variants, acts on `post.id` for a repost item), `FeedList` (repost card, unavailable
card, polled removed and vanished originals, later repeats hidden, an empty page with `hasMore` shows Load more and
not the empty state), `status-overlay` (reposts polled), `BookmarkList`
(loading, empty, list, Load more, error + retry, un-bookmark keeps the card, mounted behind a settled session in
`<StrictMode>`), `LikeButton` (unique hint ids), `social-api`, `messages`.

**E2E** (`social.spec.ts`, serial, shared `fan` and `star`, zero new sign-ups; `seedPost` makes a third author and
post in the database): star reposts the seeded post, then fan follows star (which clears fan's cache) and sees
"Reposted by …" under Following; the shell flips the original to verified true → the repost's badge updates; flips it
to removed → "This post is no longer available"; star undoes it from their profile; fan bookmarks a post → it's on
`/bookmarks`, star's `/bookmarks` stays empty; star's own post and a FALSE post have a disabled Repost with the
reason; a visitor gets login links; `/bookmarks` and a card with four actions fit 390 px. Each test leaves the follow
as it found it.

## Verification (end to end)

- Backend: `python -m pytest`, `ruff check .`, `ruff format --check .`, `makemigrations --check --dry-run`,
  `manage.py check`; `sqlmigrate social 0003` reviewed; `EXPLAIN ANALYZE` in a rolled-back transaction (thousands
  of posts and reposts) of the Following union, the profile union and the bookmark page, recording which indexes
  serve each side.
- Frontend: `npm run lint`, `lint:tokens`, `typecheck`, `format:check`, `npm test`,
  `NEXT_PUBLIC_GOOGLE_CLIENT_ID= npm run build`, `npm run test:e2e` (dev, five runs in a row), `CI=1 npm run test:e2e`
  after the build.
- Manual: the doc's own curl blocks (every API row above) run verbatim; headless-Chromium screenshots at 1280 and
  390 px with 0 px horizontal overflow on `/home` (Following with reposts), a profile, `/p/[id]` and `/bookmarks`;
  Django Admin as a superuser and as a moderator.
- Tick the seven acceptance criteria in `task.md` with notes; record commands and results in HANDOFF.

## Stop conditions

Stop and ask if: a test, lint or type check fails for a reason the plan didn't anticipate; the union can't be built
with the ORM as prototyped, or `EXPLAIN` shows the post side no longer uses `posts_recent_idx`; the E2E suite needs a
new sign-up; a new dependency, service or env variable looks necessary; anything in `design/` would change; or the
work reaches into 8 (reports), 11B (scores) or 13 (notifications). Docker not healthy is a stop until fixed.

## Follow-ups to record (not done here)

- 11B: repost score events read `status_at_repost`; "undoing a repost after the verdict doesn't undo events".
- 13: `repost` notification hooks in `social.services.repost` (de-duplicated per §2).
- 11D: daily repost counts use `reposts_post_created_idx`.
- 14: data export includes your bookmarks and reposts; account deletion cascades.
- `FollowButton`'s constant hint id (duplicate DOM ids in lists).
- 16: the `repost`/`bookmark` rates are guesses; the repost side of the Following union sorts all reposts by followed
  accounts after the cursor (fine at MVP scale; see the EXPLAIN in HANDOFF).
- Known limits: your new repost isn't inserted into an open list; a like/repost/bookmark made in one list isn't
  mirrored into another mounted list (Recent vs Following).
