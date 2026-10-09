# Plan: Part 6, Profiles, follows, Following feed

- **Status:** APPROVED by the user (Sanjoy Rozario) on 2026-10-09, together with the four decisions and the
  defaults below. Saved here and linked from `HANDOFF.md`. **Not implemented yet.**
- **Drafted:** 2026-10-09 by Claude (Sonnet 5.5). **Implement with:** Sonnet 5.5 · medium (task.md).
- **Evidence (read-only):** HANDOFF, MEMORY, `task.md` Part 6, ARCHITECTURE §2/§3/§9/§10, ANALYSIS
  (c1/c3/b1 rows, D4), Stitch b1/c1/c3, and the Part 4/5 backend and frontend code (two Explore passes plus
  direct reads). DRF's cursor pagination was checked in the installed source.

## Context

Part 6 makes people findable and followable: public profiles (`/u/[username]`), follower and following lists,
follow/unfollow, and the Following feed on `/home`. It is the first social-graph code: `apps/social/` does not
exist yet, `/u/[username]` is a `Placeholder`, and `HomeFeed` has one hard-coded tab.

**Dependency check (done 2026-10-09).** Part 6 depends only on Part 4: `[x] Done (2026-10-09)` in both places
in `task.md`. Its chain is Done too: 1 → 0C → 0A, 0B, 0D, plus 2, 3 and 5. HEAD is `b5b8089` ("Implementation
Part 5"), the tree is clean. (HANDOFF still says Part 5 is uncommitted; the user committed it, so step 0
corrects that.) Open but not blocking: Part 3's real-Google check, and CI for Parts 2 to 5 (not run yet).

**Your decisions (2026-10-09):**
1. **Home tabs: Recent first and default, Following second.** Following exists for signed-in users only;
   visitors see Recent alone. Its empty state ("Follow people to see their posts here") has an action that
   switches to Recent.
2. **The Following cache holds only the post ids of page 1.** Posts are loaded fresh on every request, so a
   deleted or removed post vanishes at once and Part 7's like state is never stale.
3. **Profile counters:** `verified` and `FALSE` count every non-removed post with that status, **deleted ones
   included** (deleting can't erase a FALSE label; matches the ledger rule that deleting undoes nothing,
   ARCHITECTURE §4a). `posts` counts only what the public can see.
4. **Author avatar and name link to `/u/<username>`** on post cards and on the post page.

## Scope

**In:** the `social.Follow` model and migration; follow/unfollow; profile, posts, followers, following and
Following-feed endpoints; the `FEED_CACHE_SECONDS` setting and the cache; `/u/[username]` (light SSR),
`/u/[username]/followers` and `/following`; `FollowButton`, `UserRow`, `ProfileHeader`; the Following tab;
author links on cards and the post page; tests, E2E, docs.

**Not in Part 6:** likes and comments (7), reposts and bookmarks (7B; `FeedList` still skips `repost` items),
the credibility score and Credibility widget (11B/11D), settings and the Edit-profile page (14; the button just
links to `/settings`), profile photos (14B), search (12), follow notifications (13), Stitch's share/more
buttons, ORCID/affiliation, trust metrics, side widgets, chips and the in-list filter on c3, any new
dependency or service.

## What the research found

- **Nothing exists yet.** No `apps/social/`, no `/api/v1/users/*` or `/feed/`, no `FollowButton`/`UserRow`/
  `ProfileHeader`, no profile types, no optimistic-update pattern in the frontend.
- **Already in place:** the `follow` throttle scope (100/h) and its settings test; `IsEmailVerified`;
  `normalize_username`; `FeedPagination` (feed envelope + cursor guard); `useCursorFeed`, `FeedList`,
  `useStatusPolling`, `status-overlay.ts`; `Tabs`, `FilterChips`, `EmptyState`, `Avatar`, `Button`/
  `buttonClasses`, `useToast`; the shell's Profile links to `/u/<username>`; `ComposerTrigger`'s pattern for
  visitors (login link) and unverified users (`aria-disabled` + toast).
- **`FEED_CACHE_SECONDS` is only a stub:** it is in `backend/.env.example` and no `.py` file reads it.
  `ENV_GUIDE.md` (lines ~111, 382, 562) wrongly files it with the admin-editable PlatformSettings seeds.
- **DRF's `CursorPagination` accepts `.values()` rows** (`_get_position_from_instance` handles dicts), which
  makes the ids-only cache possible.
- **The username column is unique and always lowercase** (DB check), so the cheap case-insensitive lookup is
  `username=normalize_username(raw[:64])`, an exact hit on the unique index (`iexact` can't use it).
- **No `(author, status)` index exists** on posts; counts use `posts_author_created_idx` and filter the rest
  (fine for one author).
- **A stale Bearer token on a public GET is a 401** (`JWTAuthentication`); `apiFetch` refreshes and retries,
  and the SSR read is anonymous.
- **Existing tests assert how many links a card has** (`PostCard.test.tsx` ~131/145/150/156/201-220,
  `e2e/posts.spec.ts` ~110-111) and `HomeFeed.test.tsx:51-58` asserts exactly one tab. They change on purpose.
- **`useCursorFeed` does not refetch when `fetchPage` changes** (it reads it through a ref): a changed filter
  or username needs a new `resetKey` or a remount (`key=`).
- **A page-level `openGraph` replaces the root's whole object** (MEMORY 2026-10-09): `/u/[username]` must set
  type, siteName, title suffix and the static share images itself.
- **task.md's scope line "no self-follow check" contradicts ARCHITECTURE §2 ("check follower ≠ following") and
  the acceptance criterion ("self-follow returns 400").** Built per ARCHITECTURE: a DB `CheckConstraint` plus a
  400. The task wording is fixed when the part is closed.

## Defaults where the docs are silent (approved with the plan)

**API**
- **Lookup:** `normalize_username(raw[:64])` then `username=`; unknown **or inactive** user → 404 `not_found`.
  A malformed name is a 404 as well (never a 500).
- **Profile** `GET /api/v1/users/{username}/` (public, `never_cache`):
  `{id, username, display_name, bio, avatar_url, created_at, counts: {followers, following, posts, verified,
  false}, reputation: {score, sample}, is_following, is_me}`. `is_*` are `false` for visitors. `reputation`
  follows ARCHITECTURE §9 from the existing columns (`score` is `null` until the sample reaches 3, so always
  `null` until 11B); the page ignores it for now. **One query anonymous, two signed in**: counts and
  `is_following` are subquery annotations on the user query.
- **Counts:** `followers`/`following` from `follows`; `posts` = not deleted and not removed; `verified` =
  `status='verified_true'`, `false` = `status='verified_false'`, both **including deleted posts**.
- **Posts** `GET …/{username}/posts/` (public): the §9 feed envelope (`pinned: []`), newest first, only
  `Post.objects.visible()` of that author (the author's own removed posts stay out too), optional
  `?post_type=fact|opinion` (anything else → 400 on `post_type`), `FeedPagination`.
- **Lists** `GET …/followers/` and `…/following/` (public): `{results: [row], next_cursor}`, newest follow
  first, row = `{id, username, display_name, bio, avatar_url, reputation, is_following, is_me}`; inactive users
  are left out; `is_following` is an `Exists` annotation, so signed in or not the page is one query (plus the
  target lookup).
- **Follow** `POST …/{username}/follow/`: `IsAuthenticated` + `IsEmailVerified` (ARCHITECTURE §7), throttle
  `follow` 100/h (per user), `get_or_create`: **201** `{"is_following": true}` new, **200** same body if it
  already existed, **400** `cannot_follow_self`, 404 unknown/inactive, 403 `email_unverified`, 401 anonymous.
  **Unfollow** `DELETE`: `IsAuthenticated` only (no verified email), same throttle, **204** always (also when
  you weren't following), 404 unknown. A 400 or 404 counts toward the throttle, a 401/403 doesn't (the order in
  MEMORY: authentication → permissions → throttle → validation).
- **Following feed** `GET /api/v1/feed/` (`IsAuthenticated` only, `never_cache`): the §9 envelope; posts by
  `followed ∪ {me}` (visible only), `FeedPagination` ordering `(-created_at, -id)`. Reposts join in 7B, and
  then the cursor becomes `(activity_at, item id)` there.
- **Cache (decision 2):** key `social:following-feed:v1:<user_id>`, value `{"ids": [...], "next": token|null}`,
  stored only for a first page asked without `cursor` or `page_size`, TTL `FEED_CACHE_SECONDS` (default 30,
  accepted range 0 to 300, **0 turns the cache off**). A hit loads `Post.objects.visible().for_list()` by those
  ids and keeps their order (a post that has become invisible is dropped, so a page may hold fewer than 20).
  `bust_following_feed(user_id)` deletes the key now and again `on_commit` (the PlatformSettings pattern); it
  runs for **your own** cache on follow, unfollow and when you post. Posts by people you follow reach you after
  at most the TTL (accepted in ARCHITECTURE §9). Never cached across users.
- **Pagination guard:** the cursor-position check moves from `FeedPagination` into a small mixin in
  `apps/core/pagination.py`, so the two list endpoints share it (a crafted cursor is 404, never 500). This
  closes Part 4's Part-16 follow-up for the new lists only.
- **Follows indexes** (ARCHITECTURE §2 says `index(following)`): two composite indexes,
  `(following, created_at DESC, id DESC)` for the followers list and `(follower, created_at DESC, id DESC)` for
  the following list, both with the unique pair. ARCHITECTURE §2 is updated.
- **Admin:** a read-only `FollowAdmin` (like `PostAdmin`); changes go through `social.services`.

**Frontend**
- **Home:** `Tabs` = Recent, Following (the second only when `status === "authenticated"`); the tab is
  component state. The Following feed loads **lazily**: `enabled` turns on at first selection and stays on, so
  `/home` makes no extra request and switching back keeps the list. A post you make is prepended to both
  feeds. Status polling takes the pending ids of the **active** tab's feed.
- **`FeedList` gets an optional `empty` prop** (default unchanged). Following empty state: icon `group`,
  "Follow people to see their posts here", action "See Recent" (switches the tab). Profile empty state: "No
  posts yet" ("{name} hasn't posted yet." / "You haven't posted yet.").
- **Profile page** (`max-w-reading`, one column; c1's 12-column grid exists only for the dropped side widgets):
  header card (c1 classes), then the post list with `FilterChips` All / Facts / Opinions (single select; ignore
  an empty selection), list remounted with `key={username:filter}`. Header: `Avatar` size 20 (80 px; there is no
  96 px size), name `h1` (`@username` when the display name is blank, shown once), handle, `Follow`/`Following`
  (primary / secondary, hover text "Unfollow") or **Edit profile** (a `buttonClasses` link to `/settings`) on
  your own page, bio (`whitespace-pre-wrap break-words`), meta row "Joined March 2024 · 42 posts"
  (new `formatMonthYear`, UTC like the rest), counters in c1's panel: **Followers** and **Following** (links to
  the lists), **Verified** (dot `primary`), **FALSE** (dot `error`). Counts print with `toLocaleString("en-US")`
  ("1,420", as in Stitch), not compact. Dropped: seal and "Author" badge, affiliation, trust score, peer
  reviews, share/more buttons, the segmented Published/Pending/Discourse control, the filter button, the
  "pending items visible only to author" callout (it contradicts the guide), the four side widgets.
- **Light SSR** like `/p/[id]`: one anonymous `no-store` fetch (5 s timeout) shared by `generateMetadata` and the
  page via `cache()`; a malformed name is `notFound()` with no fetch; the backend's 404 is a real 404; a timeout
  or 5xx renders the shell and the client fetches. A canonical redirect: `/u/Ada` → `/u/ada`
  (`redirect()` when the returned username differs). Metadata: title `Ada (@ada)` / `@ada`, description =
  the bio's first ~160 characters or "Posts by @ada on Rumor Zero.", canonical `/u/ada`, `openGraph` type
  `profile` with siteName, title suffix and the two static images; images come from a descriptor exported by
  `post-metadata.ts` (already allow-listed by the brand guard), so the guard needs no change.
- **Viewer-specific data:** the server render is the anonymous view. A signed-in visitor fetches once for
  `is_following`/`is_me` (`useProfile`, modelled on `usePostDetail`: mark the viewer as fetched in the success
  handler, StrictMode-safe). Until that lands the button shows a same-size skeleton, so it never flashes the
  wrong state.
- **`FollowButton`:** optimistic flip; the request is single-flight (the button is `loading`); a failure rolls
  back and toasts (403 `email_unverified`: "Verify your email to follow."; 429 with the wait; 404 "That account
  is gone."; else generic). Visitors get a "Follow" link to `/login?next=/u/<name>`; unverified users get an
  `aria-disabled` button with the same toast; your own row/profile has none. The profile's follower count moves
  by ±1 through `onChange`.
- **Lists** (`/u/[username]/followers`, `/following`): a client page, no server render (`noindex`, title only).
  A "← Back to {name} (@username)" link, `Tabs` Followers/Following with counts (routed: `router.push` to the
  sibling URL), a `Card`-style `divide-y` list of `UserRow`s (Avatar 10, name, handle, optional bio line,
  `FollowButton`; no chips, filter, trust metrics, "more" menu, directory banner), Load more, skeletons, empty
  ("No followers yet." / "Not following anyone yet.") and error states. Unfollowing in your own Following list
  keeps the row (its button becomes "Follow", so it can be undone).
- **Author links:** `PostCard` gets `author.href` (from `toPostCardProps`); the avatar and name are one link
  that sits above the stretched claim link (`relative z-10`, like source links). The removed-post tombstone
  card has no author block today, so no link there. `PostDetail`'s author row links too (also on a tombstone:
  the author is public). On a profile's own list the link points at the page you are on (harmless).

## Files

**Backend** (`backend/`)
- New app `apps/social/` (`mkdir` first, then `startapp social apps/social`, `name = "apps.social"`, then
  `ruff check --fix . ; ruff format .`): `models.py` (`Follow`: bigint id, `follower`/`following` FKs CASCADE
  with `related_name`, `created_at` default `timezone.now`, `UniqueConstraint(follower, following)`,
  `CheckConstraint(follower != following)`, the two composite indexes), `services.py` (`follow`, `unfollow`,
  `SelfFollow`), `feed.py` (cache key, `bust_following_feed`, `following_page_ids`, hydration),
  `serializers.py` (profile, user row, counts annotations), `views.py`, `urls.py`, `exceptions.py`
  (`CannotFollowSelfError`, 400), `admin.py`, `pagination.py` (`UserListPagination`), `migrations/0001_initial.py`,
  `tests/`.
- Changed: `rumor_zero/settings.py` (`apps.social`, `FEED_CACHE_SECONDS` via `int_in_range(…, 30, 0, 300)`),
  `rumor_zero/urls.py` (include), `apps/core/pagination.py` (guard mixin), `apps/posts/pagination.py` (uses the
  mixin; an `envelope()` helper reused by the cached feed), `apps/posts/services.py` (`create_post` busts the
  author's feed cache), `backend/.env.example` (comment: range, 0 = off), `apps/core/tests/test_settings.py`.
- Tests: new `apps/social/tests/` (`factories.py`, `conftest.py` if needed, `test_models.py`,
  `test_services.py`, `test_api_profile.py`, `test_api_follow.py`, `test_api_lists.py`, `test_api_user_posts.py`,
  `test_api_feed.py`, `test_feed_cache.py`, `test_admin.py`, `test_no_network.py`); small additions to
  `apps/posts/tests` for the pagination mixin and the `create_post` bust.

**Frontend** (`frontend/`)
- New: `src/lib/api/server.ts` gains `fetchPublicProfile`; `src/features/social/`: `social-api.ts`,
  `FollowButton`, `UserRow`, `ProfileHeader`, `ProfilePage`, `ProfilePosts`, `useProfile`, `Connections`,
  `profile-metadata.ts`, `messages.ts`, `test-helpers.tsx`, a test for each; routes
  `src/app/(app)/u/[username]/page.tsx` (replaced), `followers/page.tsx`, `following/page.tsx`;
  `e2e/social.spec.ts`.
- Changed: `lib/api/types.ts` (`UserProfile`, `UserRowData`, `UserListResponse`), `lib/format.ts`
  (`formatMonthYear`), `features/posts/{HomeFeed,FeedList,PostCard,PostDetail,post-card-props,post-metadata}.tsx`
  and their tests, `e2e/posts.spec.ts` (link count), `e2e/helpers.ts` (a follow helper if useful).

**Docs:** ARCHITECTURE §2 (follows indexes), §3 (`FEED_CACHE_SECONDS`, cache note), §9 (endpoint shapes,
profile/row objects, counters rule), §10 (profile, lists, Following tab, author links); ANALYSIS (c1/c3/b1 notes:
counters rule, author links, tab order); STRUCTURE; ENV_GUIDE (fix the `FEED_CACHE_SECONDS` rows);
`backend/.env.example`; MEMORY (new entries only for durable discoveries); `task.md` (criteria, deviations,
both status spots, the "no self-follow check" wording); HANDOFF; `docs/test-command.md` ("Part 6" section in
**both** guides, Linux first).

## Steps

0. **Start.** This plan is already saved and linked from HANDOFF "Active work". `git status` and `git diff`
   against HANDOFF, then `docker compose up -d`. Set HANDOFF's phase to "implementing".
1. **Backend foundation.** App skeleton, `Follow` model, migration (review `sqlmigrate`), settings and
   `FEED_CACHE_SECONDS`, admin, factories. `ruff check --fix . ; ruff format .`.
2. **Pagination.** Core guard mixin; `FeedPagination` on top of it (behaviour unchanged: its tests stay green);
   `UserListPagination`.
3. **Services and cache.** `follow`/`unfollow`; `feed.py`; the `create_post` bust.
4. **Views and routes.** Profile, posts, followers, following, follow/unfollow, feed; method-based permissions
   and throttles; `never_cache`; the literal-route order; include in `rumor_zero/urls.py`.
5. **Backend tests**, then `python -m pytest`, `ruff check .`, `ruff format --check .`,
   `makemigrations --check --dry-run`, `manage.py check`. **Plan check:** in a transaction that rolls back,
   seed about 20k posts and 200 follows and `EXPLAIN` the Following ids query; if it won't use an index on
   posts, switch the filter from a subquery to a materialised id list and record the choice.
6. **Frontend plumbing.** Types, `social-api.ts` (every call uses the token path; none passes `token: false`),
   `fetchPublicProfile`, `formatMonthYear`, `profile-metadata.ts`, the post-metadata image descriptor.
7. **Components, bottom-up, tests first:** `FollowButton`, `UserRow`, `ProfileHeader`, `useProfile`,
   `ProfilePosts`, `ProfilePage`, `Connections`; the three routes.
8. **Existing screens.** `FeedList` `empty` prop; `PostCard`/`PostDetail`/`toPostCardProps` author links and
   the three "link count" tests; `HomeFeed` tabs, lazy Following feed, prepend to both, polling from the active
   tab; `HomeFeed.test.tsx` and `e2e/posts.spec.ts` updated.
9. **Frontend checks:** `npm run lint`, `lint:tokens`, `typecheck`, `format:check`, `npm test`, then
   `NEXT_PUBLIC_GOOGLE_CLIENT_ID= npm run build`, `npm run test:e2e`, and `CI=1 npm run test:e2e` after the build.
10. **Manual and docs.** curl checks of every endpoint, `curl /u/<name>` for title/OG/canonical, headless
    screenshots of `/u/<name>`, a followers list and the Following tab at 1280 and 390 px beside Stitch c1/c3/b1
    (0 px horizontal overflow); the doc edits; the `docs/test-command.md` Part 6 section (Linux blocks run
    verbatim from the doc); `task.md`; HANDOFF with every command and result.

## Tests

**Backend**
- **Model:** unique pair; self-follow refused by the DB check; both composite indexes exist; deleting a user
  deletes their follows both ways.
- **Services:** follow is idempotent (`created` flag), self-follow raises, unfollow of a non-follow is a no-op,
  two simultaneous follows (`run_together`, `transaction=True`) give one row and no error, cache bust on commit.
- **Profile:** 23-key-style pinned key set; case-insensitive lookup (`/ADA/`, ` Ada`); unknown, inactive and
  malformed names → JSON 404; counts for every rule (visible `posts`; `verified`/`false` include deleted and
  exclude removed; followers/following); `is_following`/`is_me` for visitor, other user, self; `reputation`
  block `score: null` below 3 events; stale Bearer → 401; `no-store`; queries 1 anonymous, 2 signed in with 3
  and 20 rows of data.
- **Follow:** 401, 403 `email_unverified`, 400 `cannot_follow_self`, 404, 201 then 200, DELETE 204 twice, an
  unverified user can unfollow, throttle (the real 100 POSTs, then 429 `throttled` + `Retry-After`; a 401/403
  doesn't count), counts move.
- **Lists and user posts:** order newest first with ties; cursor walk with no repeat or gap when rows arrive
  meanwhile; crafted cursor → 404; inactive users and others' posts excluded; removed/deleted posts excluded
  (including the author's own); `post_type` filter and its 400; `pinned: []`; constant queries (3 vs 20 rows).
- **Feed:** 401 anonymous; composition (followed + own, newest first; nobody else's, removed, deleted); the
  cache: a second request reads from the cache (fewer queries), a post made by you appears at once (bust), a
  follow/unfollow busts, a followed user's new post shows after the TTL (`clock` fixture), another user's cache
  is untouched, a deleted or removed post disappears from a cached page with no bust, `cursor`/`page_size`
  bypass it, `FEED_CACHE_SECONDS=0` disables it, a stored value is ids only (no text).
- **Settings:** `FEED_CACHE_SECONDS` default, bounds, empty. **Admin:** read-only, listed. **No network.**
- **Mutation checks as in Parts 4 and 5** (remove a rule by hand; a test must fail): the self-follow check, the
  unique pair, the inactive filter, the deleted-posts-in-counters rule, the removed exclusion, the ids-only
  cache (store full posts), the bust on follow/unfollow/post, the hydration visibility filter, the cursor guard,
  the verified-email permission, the throttle, `get_or_create`.

**Frontend**
- `FollowButton`: optimistic flip and counter, rollback + toast per error, single-flight, visitor link, unverified
  `aria-disabled`, own profile, hover label, `aria-pressed`.
- `ProfileHeader` (blank-name rule, bio as plain text, links, joined month, counters), `UserRow`, `Connections`
  (routed tabs, load more, empty/error/skeleton, own row, rows' buttons), `ProfilePage` (SSR initial,
  signed-in refetch behind a gate inside `<StrictMode>`, 404, error/retry, chips refetch via the new key,
  empty states, polling overlay), `HomeFeed` (Recent default, Following only when signed in, lazy fetch,
  empty-state action, prepend to both, polling ids), `FeedList` `empty`, `PostCard`/`PostDetail` author links
  (above the claim link, none on the tombstone), `social-api` paths, `profile-metadata`, `fetchPublicProfile`
  (only an `accept` header), `formatMonthYear`, brand guard still green.
- **E2E (`social.spec.ts`):** A and B sign up verified; A follows B on `/u/<B>`; B posts; A's Following tab
  shows it (the sequence keeps A's first Following load after both events, so the 30 s cache can't hide it);
  unfollow; `/u/<B>` upper-case redirects; crawler `request.get('/u/<B>')` has the right `<title>`, `og:*`,
  canonical; a 390 px page with no horizontal overflow; self-follow impossible in the UI.

## Verification (end to end)

- Every command in steps 5, 9 and 10, results recorded in HANDOFF.
- `curl http://localhost:3000/u/<name>` shows the display name or handle in `<title>`, `og:title`, `og:image`,
  `twitter:image` and the canonical link; `/u/nobody` is a 404 page.
- Acceptance: follow/unfollow idempotent, self-follow 400, counts update; Following shows only followed + own
  posts, newest first, and your new post appears at once despite the cache; unknown user 404 and
  case-insensitive lookup; constant query counts on every list endpoint.

## Stop conditions

Stop and ask if: a new dependency, service or env variable (beyond reading the existing `FEED_CACHE_SECONDS`) is
needed; the Following query can't be made reasonable without a schema change beyond the two follows indexes; the
author link can't be added without breaking the claim link; any Part 4 or Part 5 contract must change; or
anything outside Part 6's list needs changing.

## Follow-ups to record (not done here)

- **Part 7/7B:** the Following cache keeps only ids, so `*_by_me` and counts stay fresh; 7B turns the cursor into
  `(activity_at, item id)` and `FeedList` starts rendering reposts.
- **Part 11B:** `reputation` is in the profile and row objects already; the UI shows the score and a verified
  count then. **Part 14:** Edit profile page, username rename. **Part 14B:** profiles use the 256 px photo.
- **Part 12:** people search reuses `UserRow`. **Part 13:** a `follow` notification.
- **Part 16:** the `follow` rate (100/h) and cache TTL are guesses; the cursor guard for the other core-pagination
  lists; Upstash command use (a Following first-page view costs one to three commands).
- **Part 18:** Workers CPU of `/u/[username]` (same escape hatch as `/p/[id]`).
