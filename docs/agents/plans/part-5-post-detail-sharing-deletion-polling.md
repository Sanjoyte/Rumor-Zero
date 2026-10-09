# Plan: Part 5, Post detail, sharing, deletion, status polling

- **Status:** APPROVED by the user (Sanjoy Rozario) on 2026-10-09, together with the decisions and
  defaults below. Not implemented yet.
- **Drafted:** 2026-10-09 by Claude (Sonnet 5.5). **Implement with:** Sonnet 5.5 · medium (task.md).
- **Evidence:** read-only. The Part 4 backend and frontend code, ARCHITECTURE §2/§3/§4/§9/§10/§13,
  ANALYSIS b-2/c-26/c-35/d, Stitch b3 and c1, Next 16.3.8's `resolve-metadata.js`, and DRF/Django
  behaviour as recorded in MEMORY.

## Context

Part 5 turns the feed into something shareable and live:
- `/p/[id]`: a public, indexable post page with a light server render (Stitch b3);
- the author's soft delete (D6);
- `GET /api/v1/posts/status/`, and a `useStatusPolling` hook so "CHECKING FACTS…" badges update
  without a reload, on the feed and on the detail page.

**Dependencies (checked 2026-10-09).**
- Part 5 depends only on Part 4: `[x] Done (2026-10-09)` in both places in `task.md`, committed as
  `2b1fb19` ("Implemented Part 4…"). The tree was clean at the start of the planning session.
- Its chain is Done too: 1 → 0C → 0A, 0B, 0D, plus 2 and 3.
- Still open and **not blocking**: Part 3's real-Google check (criterion 4), and CI for Parts 2, 3 and 4
  (not run yet; you push and report).

**Your decisions (2026-10-09):**
1. **Removed post, public view: the same 23 keys with the sensitive fields blanked.** The author's name
   and the post time stay visible; `content` is `""`, `sources` is `[]`, and `verdict_note` is `""`.
   I also blank `confidence_score` and `verdict_source`. The author sees the full post.
2. **Add a `status_poll` throttle now:** 120/min per client IP.

## Scope

**In:** the three endpoints, the `delete_post` service, the `status_poll` scope, `/p/[id]`,
`PostDetail` with `VerdictBlock`/`SourceList`/Copy link/Delete, `useStatusPolling` on the feed and the
detail page, cards that link to the detail page, tests, E2E, docs.

**Not in Part 5:**
- Comments (7), likes, reposts and bookmarks (7B), the report button (8), the appeal button and
  `RemovedPostCard` polish (11), emergency note (11C), the stats panel (11D).
- Hash/ledger/chart blocks from b3.
- `robots.ts`/`sitemap.ts` (not asked for).
- Any new dependency or service.

## What the research found

- **`PostQuerySet.visible()` hides removed posts**, so the detail view needs a new `not_deleted()`.
- **`verdict_note` is ungated today** in `PostSerializer`: the tombstone must blank it.
- **A page-level `openGraph` or `twitter` replaces the parent's whole object**
  (`resolve-metadata.js:182-191`), and the root's static share image is merged only at the root. So
  `/p/[id]` must set `type`, `siteName`, `images` (`/opengraph-image.png`, `/twitter-image.png`) and a
  title with the " · Rumor Zero" suffix itself: OG titles don't get the template.
- **A public GET with a stale Bearer token is a 401** (`JWTAuthentication`). The client already
  refreshes and retries; the status endpoint sets `authentication_classes = []` and the poller sends
  no token.
- **A `<uuid:>` URL converter answers Django's HTML 404**, not JSON. Routes use `<str:post_id>` and the
  view parses it (the literal `status/` route first).
- **`(app)/layout.tsx` is a client component, but its `children` still render on the server**, and
  `/p/` isn't protected. The first auth state is `loading`, so `PostDetail`'s first render must not
  depend on the user.
- **Existing tests assert that cards have no link** (`PostCard.test.tsx` ≈ L131/145/150,
  `SourceLink.test.tsx`, `e2e/posts.spec.ts` ≈ L109). They change on purpose.
- **`useCursorFeed` has no "patch an item" action.** Polling results go in an overlay map instead.
- `server-only` isn't installed; the SSR helper is a plain module (no secret is read).
- `Post.updated_at` is `auto_now`: `save(update_fields=[…])` must list it.
- Next prefetches in-view links, and every request is a Worker request (100k/day), so card links use
  `prefetch={false}`.
- The Workers 10 ms CPU limit can't be measured locally. Part 18 checks error 1102 on `/p/[id]`.

## Defaults where the docs are silent (approved with the plan)

**API**
- **Detail:** `GET /api/v1/posts/{id}/` is public and never cached. Deleted or unknown ids, or a
  malformed id, are 404 `not_found` (JSON), the author included. A removed post is the full object
  for its author and the blanked object for everyone else; this rule lives **in `PostSerializer`**, so
  no later list can leak a removed post. `can_appeal` stays false until Part 11.
- **Delete:** `DELETE /api/v1/posts/{id}/` → 204, author only (403 `not_author`, a new code from §9),
  `IsAuthenticated` only (deleting your own text needs no verified email), no throttle of its own.
  Any status can be deleted (ARCHITECTURE §4); status is unchanged and the post still counts toward
  the 24 h fact allowance. A second DELETE is 404 (the post is already hidden).
- **Status:** `GET /api/v1/posts/status/?ids=a,b` → `{"results": [{id, status, confidence_score,
  verdict_source}]}`, in the order requested. A removed post answers `status: "removed"` with nulls
  (so an open tab learns it is gone); deleted and unknown ids are omitted. No ids, more than 50, or a
  malformed id → 400 on `ids`. Public, no token, `Cache-Control: no-store`, one query for 50 ids, and
  throttled by `status_poll` (120/min per IP).

**Frontend**
- **Polling** covers `pending` posts only (ANALYSIS b-2). The 10-minute budget counts **visible** time:
  a hidden tab pauses and polls once on return. Delays: 10 s × 1.5 each time, capped at 60 s. A new
  pending id (a post you just made) restarts the schedule. Errors are silent and still count. Nothing
  is shown when it stops.
- **In a feed:** a polled `removed` turns the card into the existing tombstone card; a post that
  vanishes (deleted) is hidden. **On the detail page:** the badge changes at once, then one silent
  refetch brings the rest (`verdict_note`).
- **Card link:** the claim text is a stretched link, so the whole card opens the post (`interactive`
  Card was built for this). Source links stay separate and sit above it. "+N more" links to
  `/p/{id}#sources`.
- **Detail typography:** card font tokens at `text-headline-md` (28 px). b3's 36 px would run to about
  20 lines for 500 characters at 390 px.
- **Dates:** the detail header shows an absolute UTC time ("Oct 9, 2026, 2:05 PM UTC"): it is the same
  on the server and in the browser, so no hydration mismatch.
- **Opinion pages:** no verdict block and no sources; one neutral line, "Opinions aren't
  fact-checked." A fact with no sources shows "The author didn't add any sources."
- **Copy link** copies `window.location.origin + /p/{id}`, toast "Link copied." (a failure says to copy
  the address bar).
- **Delete:** the modal says what happens and, for a fact, that it still counts toward today's
  allowance. Success → `router.replace("/home")` plus a toast "Post deleted."; a 404 (already gone)
  takes the same exit.
- **Back link:** "Back to Home" (a `Link`; a shared link may have no history).
- **SSR:** one anonymous `no-store` fetch of `BACKEND_ORIGIN` with a 5 s timeout, shared by
  `generateMetadata` and the page through React `cache()`. A non-UUID id is `notFound()` with no fetch.
  A backend timeout or 5xx isn't a 404: it renders the shell with generic metadata and the client
  fetches. Removed → `robots: noindex`, title "Removed post".
- **Admin:** a "Deleted by author" filter (`deleted_at` empty-field filter) on the read-only posts
  admin, so the deleted post is easy to find.

## Files

**Backend** (`backend/`)
- `apps/posts/models.py`: `PostQuerySet.not_deleted()`; `visible()` builds on it.
- `apps/posts/serializers.py`: `shown_confidence(post)` extracted; the tombstone rule in
  `PostSerializer`; `status_item(post)`.
- `apps/posts/services.py`: `delete_post(*, post_id, user, now=None)` and its two domain errors; the
  docstring.
- `apps/posts/exceptions.py`: `NotAuthorError` (403 `not_author`).
- `apps/posts/views.py`: `PostDetailView` (GET public, DELETE authenticated, per method like
  `PostListView`), `PostStatusView`.
- `apps/posts/urls.py`: `v1/posts/status/` before `v1/posts/<str:post_id>/`.
- `apps/posts/admin.py`: the filter.
- `rumor_zero/settings.py`: `"status_poll": "120/min"`.
- Tests: new `test_api_detail.py`, `test_api_delete.py`, `test_api_status.py`; additions to
  `test_services.py`, `test_models.py`, `test_admin.py`, `test_no_network.py`;
  `apps/core/tests/test_settings.py` (ten scopes → eleven).

**Frontend** (`frontend/`)
- New `src/lib/api/backend-origin.ts` (the origin check extracted from `relay.ts`'s `readConfig`, same
  rules, same result for the relay) and `src/lib/api/server.ts` (`fetchPublicPost`).
- New `src/app/(app)/p/[id]/page.tsx`.
- New in `src/features/posts/`:
  - `post-metadata.ts`
  - `PostDetail.tsx`
  - `usePostDetail.ts`
  - `VerdictBlock.tsx`
  - `SourceList.tsx`
  - `CopyLinkButton.tsx`
  - `DeletePostModal.tsx`
  - `useStatusPolling.ts`
  - `status-overlay.ts`
  - tests next to each
- Changed:
  - `PostCard.tsx` (`href`) and `post-card-props.ts` (the link)
  - `SourceLink.tsx` (`moreHref`)
  - `FeedList.tsx` and `HomeFeed.tsx` (the overlay, polling)
  - `posts-api.ts` (`fetchPost`, `deletePost`, `fetchStatuses`)
  - `lib/api/types.ts` (`PostStatusUpdate`)
  - `lib/format.ts` (`formatFullDateTime`)
  - the existing no-link tests.
- New `e2e/post-detail.spec.ts`; `e2e/helpers.ts` (a status-flip helper); `e2e/posts.spec.ts`
  (the link assertion).

**Docs:** ARCHITECTURE (§3 throttle list, §4 delete row, §9 post/status/delete/tombstone text and the
endpoint index, §10 `PostDetail` + polling + metadata gotcha), ANALYSIS (b-2 "Removed": the reason
arrives with Parts 10/11), STRUCTURE, MEMORY (3 entries), `task.md`, HANDOFF,
`docs/test-command.md` (a "Part 5" section in **both** guides, Linux first).

## Steps

0. **Start:** this plan is already saved and linked from HANDOFF "Active work". Check `git status`
   and `git diff` against HANDOFF, then `docker compose up -d`.
1. **Backend foundations.**
   - `not_deleted()`, `shown_confidence()`, the tombstone rule, `status_item()`.
   - `delete_post` with a row lock (`select_for_update` inside `transaction.atomic()`, filtered on
     `deleted_at IS NULL`) that saves only `deleted_at` and `updated_at`.
   - `NotAuthorError`, the `status_poll` scope, the settings test.
2. **Backend views and routes.**
   - `PostDetailView`: `get_permissions` and `never_cache` as in `PostListView`; the id is parsed as a
     UUID by hand.
   - `PostStatusView`: `authentication_classes = []`, `ScopedRateThrottle` with scope `status_poll`,
     `ids` parsing (dedupe, order kept).
   - The admin filter.
3. **Backend tests** (below), then `pytest`, `ruff check .`, `ruff format --check .`,
   `makemigrations --check --dry-run` (expect no migration).
4. **Frontend plumbing.**
   - `backend-origin.ts`, `server.ts`, the types, the API functions, `formatFullDateTime`.
   - `useStatusPolling` and `status-overlay.ts` (`effectiveStatus`, `pendingIds`), with tests first.
5. **Cards and feed.** `PostCard`/`SourceLink`/`toPostCardProps` links; `FeedList` and `HomeFeed` take
   the overlay and poll; update the three existing "no link" tests.
6. **Detail page.**
   - `post-metadata.ts` and `page.tsx`.
   - `usePostDetail` with `PostDetail`: SSR `initial`, a refetch only when signed in or when there was
     no `initial`, 404 → not-found state, error → retry.
   - `VerdictBlock`, `SourceList` (b3 registry rows, `id="sources"`, links via `sourceHref`, `rel`
     as Part 4), `CopyLinkButton`, `DeletePostModal`, and the tombstone view (the blanked post: author
     row plus "This post was removed by a moderator.").
7. **Frontend checks:** `npm run lint`, `lint:tokens`, `typecheck`, `format:check`, `npm test`.
8. **E2E and build:** `npm run test:e2e`; `NEXT_PUBLIC_GOOGLE_CLIENT_ID= npm run build` (expect
   `/p/[id]` as `ƒ`), then `CI=1 npm run test:e2e`.
9. **Manual and docs:** curl `/p/<id>` against `next dev`; the endpoint checks; the Part 5 section of
   `docs/test-command.md` (Linux blocks run verbatim from the doc); a screenshot of `/p/<id>` at 1280
   and 390 px beside Stitch b3 (0 px overflow); the doc edits; `task.md` (criteria, deviations, both
   status spots); HANDOFF.

## Tests

**Backend**
- Detail visibility matrix: anonymous / author / other × `pending`, `published`, `verified_true`,
  `verified_false`, `under_review`, `removed` and deleted. The 23 keys always. Removed: author full,
  others blanked (the five fields) with the author block kept. Deleted: 404 for everyone. Sources
  with `kind`. `verdict_note` shown for a moderator verdict. Confidence only for pipeline verdicts.
  Malformed and unknown ids → JSON 404. `no-store`. Queries: 1 anonymous, 2 signed in. A stale Bearer
  → 401 (pins the behaviour).
- Delete: 204 and `deleted_at` set, `updated_at` moved, status unchanged, row still in the database
  and listed in the admin; gone from the feed and the detail; 2nd DELETE 404; other user 403
  `not_author`; anonymous 401; staff non-author 403; an unverified author may delete; deleting a
  removed post works; the fact allowance still counts it; a threaded double delete (`run_together`,
  `transaction=True`) gives one 204 and one 404; the SQL has `FOR UPDATE`; it doesn't use up
  `post_create`.
- Status: public, a garbage Bearer still 200; the 4-key shape; one case per status; removed → nulls;
  deleted and unknown omitted; 0 ids, 51 ids and a bad id → 400 on `ids`; 50 OK; duplicates collapsed;
  1 query for 50 ids; `no-store`; the 121st request in a minute → 429 while another IP is fine (the
  headers pattern in `test_username_available.py`); no `post_create` use.
- Service, model and serializer units; the no-network test now also reads a detail with sources.
- Mutation checks as in Part 4: drop the tombstone blanking, the author check, the row lock, the
  `deleted_at` filter on status, the 50-id cap, `authentication_classes = []`: each must fail a test.

**Frontend**
- `useStatusPolling` (fake timers): first tick at 10 s, backoff to 60 s, hidden pause and one
  immediate poll on return, stop at 10 min of visible time, restart for a new id, nothing for an
  empty list, abort on unmount, a stale response ignored, errors silent, ids over 50 trimmed.
- Overlay: `effectiveStatus`, removed → tombstone card, gone → hidden.
- `PostCard`/`SourceLink` links (`prefetch` off, source links not nested in the card link).
- `PostDetail` states: initial from SSR, signed-in refetch, anonymous no refetch, loading, error,
  not-found, tombstone (public and author), every status's `VerdictBlock`, opinion and no-source
  notes, author-only Delete.
- `SourceList` (numbering `01`…, DOI → `https://doi.org/…`, `rel`), `CopyLinkButton` (success and
  failure), `DeletePostModal` (copy, busy, error, success redirect), `post-metadata` (title, OG,
  twitter, canonical, noindex, fallback), `formatFullDateTime`.
- **E2E (`post-detail.spec.ts`):**
  1. Sign up verified → post a fact with a DOI and a URL → open it from the card → claim, "Sources (2)",
     `01`/`02` → Copy link (clipboard permission) → anonymous `request.get('/p/<id>')` HTML has the claim,
     the `<title>` and the OG tags including `og:image`.
  2. Delete → confirm → on `/home` without it; `/p/<id>` is a 404 page.
  3. Status flip: a helper runs `manage.py shell` with the backend venv to set the post `verified_true`,
     and the open tab's badge changes within ~15 s. If the helper can't be made reliable both locally
     and in CI, drop it and record the deviation; the manual check in `test-command.md` covers it.

## Verification (end to end)

- Every command in steps 3, 7, 8, results recorded in HANDOFF.
- `curl http://localhost:3000/p/<id>` shows the claim text, the right `<title>`, `og:title`,
  `og:description`, `og:image`, `twitter:image` and the canonical link (acceptance 1).
- Django shell `Post.objects.filter(pk=…).update(status="verified_true")` on a pending post updates the
  badge in an open tab without a reload (acceptance 2). Hidden tab: no requests; stops after 10
  minutes of visible time (acceptance 3, unit-tested and watched in DevTools).
- Delete as the author: gone from Recent, `/p/<id>` 404, still in Django Admin → Posts (acceptance 4).
- Set a post `removed` in the shell: anonymous visitor sees the blanked tombstone, the author sees the
  full post marked removed (acceptance 5).
- `docs/test-command.md` Part 5 steps, with the Linux blocks extracted from the doc and run verbatim.

## Stop conditions

Stop and ask if: a new dependency, service or env variable turns out to be needed; the claim text
can't reach the server-rendered HTML through the client `(app)` layout; the OG tags can't be made
complete without touching the root layout; a required test can't pass without changing a Part 4
decision; or anything outside Part 5's list needs changing.

## Follow-ups to record (not done here)

- **Part 10:** the review queue must skip posts with `deleted_at` set; the admin is still read-only.
- **Part 11:** `RemovedPostCard`, the removal reason, `can_appeal`, and the appeal button.
- **Part 16:** CSP unchanged (nothing new loads); the public `ids` endpoint's throttle value; the
  cursor guard for other lists.
- **Part 18:** watch Workers error 1102 on `/p/[id]`; if the 10 ms limit bites, the metadata-only
  fallback or Workers Paid is the escape hatch (ANALYSIS c-35).
- **Part 6:** profile lists reuse `useStatusPolling` and the overlay.
- **Part 7/7B:** counts and `*_by_me` on `PostDetail`.
