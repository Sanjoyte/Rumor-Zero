# Plan: Part 12, Search

- **Status:** APPROVED by the user (Sanjoy Rozario) on 2026-10-20, together with the four decisions and the defaults below;
  drafted 2026-10-20 by Claude (Sonnet 5.5). Saved here and linked from HANDOFF at approval (HANDOFF's stale "11D is uncommitted at
  `5704bb7`" lines were corrected then), so step 0 only needs to verify the workspace and record the baselines. **Not implemented yet.**
- **Implement with:** Sonnet 5.5 · medium (task.md).
- **Evidence (all read-only):** HANDOFF, MEMORY, `task.md` (Part 12 and the notes left by 6/11B/11D), ARCHITECTURE §2/§3/§9/§10/§12,
  ANALYSIS b-3/c-31/b4, STRUCTURE, the guide's §10 (PDF text; it only says "Postgres full-text, stemming, GIN"), the 11D plan (format);
  backend `posts/{models,views,serializers,pagination,urls}.py`, `social/{serializers,views,services}.py`, `accounts/models.py`,
  `core/{pagination,middleware}.py`, `rumor_zero/{settings,urls}.py`, Django 5.2.17 `contrib/postgres/search.py`; two Explore agents
  (backend; frontend + Stitch b4) and a Plan-agent design review that finished **before** this version (its findings are folded in and
  marked "(review)").

## Context

Part 12 adds Postgres full-text search over posts and a people search with no new service (guide §10, ANALYSIS c-31): a stored
generated `search_vector` column with a GIN index, `GET /api/v1/search/`, and the `/search` page (Stitch b4) with Posts and People tabs,
filter chips, highlighted query terms and "Load more". People rows are the follower rows (credibility badge, verified count, Follow
button). Removed and deleted posts never appear. Search is public and read-only.

**Dependency check (2026-10-20).** Part 12 depends on **6** (Done 2026-10-09) and **11B** (Done 2026-10-19). Their chains (4, 3, 2, 1, 0C,
0A/0B/0D, 7, 7B, 8–11) and 11C/11D are Done. **Open but not blocking:** Part 3 criterion 4 (real-Google check), CI for Parts 2 to 11D
(not reported), the Part 17 stub-verdict launch blocker.

**Workspace:** HEAD `b2f8ad5` ("Implemented Part 11D: Charts & stats"), clean tree, Docker up, ports 3000/8000 free. HANDOFF still says
11D is uncommitted at `5704bb7` (stale; corrected in step 0). Baselines (from HANDOFF, re-measured in step 0): `pytest` 3715,
`npm test` 1933, E2E 45.

**Already in place:** `PostQuerySet.visible()/for_list(viewer)`, `PostSerializer` (25 keys, strict counts), `FeedPagination.envelope`,
`feed_item`, `social.serializers.{user_row, reputation_block, verified_count}`, `UserRow` + `CredibilityBadge variant="row"`, `Tabs`,
`FilterChips`, `LoadMore`, `EmptyState`, `useCursorFeed`, `FeedList`, `useStatusPolling`, `Connections.tsx` (the template for the
People list), the top bar's `GET /search?q=` form (`next/form`, `name="q"`) and a placeholder `app/(app)/search/page.tsx`, the relay (forwards
any `/api/` path and query string), the `username` column's `varchar_pattern_ops` "_like" index (Django creates it for a unique varchar),
the tokens `bg-secondary-fixed` / `text-on-secondary-fixed`, E2E `seedPost` / `seedAuthor` / `setPostState`.

## Your decisions (2026-10-20)

1. **People match:** username **prefix** + any **word of the display name** (the start, or after a space, hyphen or apostrophe). No
   extension and no new index: `users` is scanned for the name half (the username half can use the `_like` index). A trigram index is a
   Part 16 option.
2. **Filter chips:** one row of six, pick one: All / Facts / Opinions / Verified / FALSE / Under review. The API still accepts
   `post_type` and `status` together.
3. **Rate limit:** `search` **60/min per client IP**, counted by IP for signed-in users too (a small throttle class, because DRF's
   `ScopedRateThrottle` keys on the user once signed in).
4. **People order:** exact username, then username prefix, then display-name word matches; A–Z by username inside each. Never by
   credibility, followers or anything else.

## Scope

**In:** migration `posts.0003` (`search_vector` + GIN `posts_search_idx`); `GET /api/v1/search/` (posts and users); a `search` throttle scope +
`IPScopedRateThrottle`; a bounded-offset helper in `core/pagination.py`; the `/search` page (query box, Posts / People tabs, chips,
highlighted terms, prompt / no-results / error / throttled states, Load more); `features/search/*`; additive highlight props on
`PostCard` / `UserRow`; additive `endLabel` on `FeedList`; a 429 branch in the two list-error helpers; dev-gallery specimens; one E2E
spec (+ a `deleted` state in `setPostState`); docs and `docs/test-command.md` Part 12 (both guides).

**Not in 12:** typo tolerance or a search engine; search-as-you-type or suggestions; searching comments, sources or reposts; sort
options; result totals / tab counts; saved or recent searches; a trigram index; a server-built highlight (`ts_headline`); mentions and
hashtags; any cache; the Part 14 export (it must skip `search_vector`; recorded below).

## Design

### 1. Schema: `posts.0003_search_vector`

- `Post.search_vector = GeneratedField(expression=SearchVector("content", config="english"), output_field=SearchVectorField(),
  db_persist=True)` and `Meta.indexes += GinIndex(fields=["search_vector"], name="posts_search_idx")` (the 7th index). Compiled (review,
  checked offline): `to_tsvector('english'::regconfig, COALESCE("content", ''))` with the parameters inlined by the Postgres schema
  editor, the documented immutable pattern; the migration serialises as `SearchVector('content', config='english')` and
  `makemigrations --check` stays clean.
- **Step 1 is a spike and a stop-and-ask gate:** `sqlmigrate` must show `GENERATED ALWAYS AS (to_tsvector('english'::regconfig,
  COALESCE("content", ''))) STORED`; `migrate`, `makemigrations --check`, `migrate posts 0002` and a re-apply must all work. If Postgres or
  Django refuses, stop and ask (fallback: a functional GIN index on the same expression, with the query repeating it).
- A stored generated column rewrites the table under a lock and the GIN build blocks writes: fine before launch; Part 17's `migrate` runs
  it once. No backfill (Postgres computes it).
- **`PostQuerySet.for_list` also `defer("search_vector")`** (`models.py:77`, next to `defer("pipeline_result")`), so no list or detail pulls
  a tsvector string per post into Python. (review) Every list and detail path goes through `for_list` (feed, pinned, profile, bookmarks,
  detail, moderation); the timeline's `union()` is over `values_list`; nothing in `apps/` enumerates `Post` fields (`PostAdmin` has explicit
  `fieldsets`). Services' full-row loads carry the column harmlessly; `Post.objects.create` gets it back through `RETURNING`.
- **Tests changed on purpose, in step 1 (review: the flip breaks the suite the moment the field exists):** `posts/tests/test_models.py`
  (`test_there_is_no_search_vector_yet` becomes "stored generated column + GIN index", the planned-index list gains `posts_search_idx`,
  `test_for_list_joins_the_author_and_defers_the_pipeline_blob` also asserts the deferral). `PostFactory` needs no change.
  **Search tests always set `content` explicitly** (the factory's default "Post number {n}" would match "post" and "number").

### 2. `GET /api/v1/search/`

`?q=&type=posts|users&post_type=fact|opinion&status=pending|published|verified_true|verified_false|under_review&cursor=2..5`

- **Who/what:** public; keeps the default authentication (a Bearer token is read so `liked_by_me` and `is_following` are right; a stale one
  is a 401 like every list: the client refreshes and retries); `AllowAny`; `never_cache`; throttle `search` through `IPScopedRateThrottle`;
  GET only (405 otherwise). It lives in `apps/posts` (STRUCTURE): `posts/search.py` (query cleaning, `search_posts`, one shared builder the
  view and the EXPLAIN test both call), `social/search.py` (`search_people`: it needs users and follows), `SearchView` in `posts/views.py`
  (imports `social` inside the function, the existing pattern), route `v1/search/` in `posts/urls.py` (no sibling pattern, so no ordering rule).
- **`q` for posts:** control characters removed (NUL would be a Postgres 500), trimmed, 1–200 code points. Missing or blank → 400
  `{"q": ["Enter something to search for."]}`; over 200 → 400 `{"q": ["Keep it to 200 characters."]}`. (review) **A query with no positive term**
  (only `-word` and `or` tokens: `-foo` would be `!'foo'`, which GIN answers by scanning the whole index and matches nearly every post) answers
  an empty 200 with **no database query**; the highlight util drops the same tokens, so the two stay aligned. Stop-word-only queries just
  match nothing. `type` defaults to `posts` (any other value → 400 on `type`); `post_type` / `status` outside their lists, and
  `status=removed`, → 400 on that field; both filters are ignored for `type=users`.
- **Posts query:** `Post.objects.visible()` (never removed or deleted; **no other exclusion**, so pending, under review, active emergencies and
  a suspended author's posts are found, as in the feeds; search has no pinned section) `.filter(search_vector=SearchQuery(q,
  search_type="websearch", config="english"))` `.annotate(rank=SearchRank(F("search_vector"), query))` (review: **`F(...)`, not the string**: a string
  is wrapped in `SearchVector` and re-parses the stored vector's text with the default config) `.order_by("-rank", "-created_at", "-id")`
  `.for_list(viewer)[offset:offset+21]`. One SELECT, no DISTINCT or GROUP BY. A guard test asserts `to_tsvector(COALESCE(` is **not** in the SQL
  and `@@` is. Filters are ANDed. Envelope = the §9 feed shape (`FeedPagination.envelope`, `feed_item`): `{pinned: [], pinned_total: 0,
  results: [{kind:"post", post, reposted_by:null, activity_at}], next_cursor}`, so `FeedList` renders it unchanged.
- **People:** `User.objects.filter(is_active=True)` + `verified_count(OuterRef("pk"))` + `Exists(Follow…)` for a signed-in viewer, the 9-key
  `user_row`; envelope `{results, next_cursor}` with **no** `pinned` keys. (review) Query cleaning: remove `Cc`/`Cs` characters (DEL and C1
  too), `normalize_username` (NFKC, strip, lower), collapse whitespace, drop a leading `@`, cut at 64 **after** normalising (NFKC can
  expand); if nothing alphanumeric or `_` is left, answer empty 200 with no query (otherwise `"-"` would match display names through
  `icontains`). Match: `username__startswith` (Django escapes `%` `_` `\`, which matters because `_` is a legal username character) OR
  `display_name__istartswith` OR `display_name__icontains` of `" " + q`, `"-" + q`, `"'" + q`, `"’" + q`: all Django lookups, no regex built from
  user text. The query is matched as typed (a phrase prefix, not word by word). Order: `Case(username == q → 0, username startswith → 1, else 2)`
  then `username`. A blank display name simply never matches the name arms.
- **Pagination (documented deviation from §9's cursor rule):** rank order has no timestamp, so the position is an **offset**: 20 per page,
  at most **5 pages (100 results)**, `LIMIT 21 OFFSET (page−1)×20`. A shared helper in `apps/core/pagination.py` (no app imports; (review) the right
  home for something generic) parses the cursor and builds the next one. `next_cursor` is the **next page number as a plain string**
  (`"2"`..`"5"`), `null` when there is no 21st row or the cap is reached. An empty or missing `cursor` is page 1 (as `is_first_page`); any
  other value outside `"2".."5"` (`"1"`, `"0"`, `"6"`, `"02"`, `"abc"`, a space) raises `NotFound("Invalid cursor")`: `{"detail": "Invalid
  cursor", "code": "not_found"}` like every crafted cursor (the client restarts from the top). Results can shift between pages if posts
  arrive meanwhile (accepted). `page_size` is fixed at 20.
- **Queries:** posts 1 anonymous / 2 signed in (the JWT user + the page); people 1 / 2; whatever the page holds (tests seed likes, reposts,
  appeals and 20 rows). A negation-only or blank-after-cleaning query: 0 (+1 for a signed-in viewer's user lookup).
- **Leaks:** nothing the feeds don't show: `PostSerializer` still blanks what it blanks; only `visible()` posts are reachable; source URLs and
  comments are not indexed. Search text appears in access logs and in Sentry request URLs on an error: documented in ARCHITECTURE §12
  (review), scrubbing is a Part 16 option.

### 3. Throttle

`apps/core/throttles.py` (new): `IPScopedRateThrottle(ScopedRateThrottle)` overriding only `get_cache_key` to key on `get_ident(request)` (the
relay-forwarded client IP from `ClientIPMiddleware`); `allow_request` still sets `scope`/`rate` first (review: checked in DRF 3.18.1).
`REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["search"] = "60/min"`. 429 `throttled` + `Retry-After`. Authentication and permissions run first,
so a 401 never counts; a 400 or a 405 does (the throttle runs before validation). ARCHITECTURE §3's list is headed "per user": the `search`
line states the exception (`username_check` and `status_poll` already are).

### 4. Frontend

- **Route (review: static, not dynamic):** `app/(app)/search/page.tsx` stays a **static** page: `metadata = { title: "Search", robots: { index:
  false, follow: true } }` (no `openGraph`, so nothing for the brand guard) rendering `<Suspense fallback={<SearchSkeleton/>}><SearchPage/></Suspense>`;
  the client component reads `useSearchParams()`. A server page awaiting `searchParams` would make every query, tab and chip change an
  extra Worker request on the free tier (the repo avoids that elsewhere). Public (not in `PROTECTED_PREFIXES`). The page must not rewrite
  the URL (`e2e/smoke.spec.ts:57` pins `/search?q=vaccines$`).
- **URL is the state:** `?q=&type=posts|users&filter=all|facts|opinions|verified|false|review`, parsed by a pure `search-params.ts` (clamps,
  defaults, first value of a repeated key). Tabs `router.push` (the filter is dropped for People), chips `router.replace`, the query form
  submits a GET (`next/form`, hidden `type`/`filter`).
- **`features/search/`:**
  - `SearchBar`: b4's box (`search` icon, editable, clear "×", `maxLength` 200). (review) The form gets `aria-label="Search results"` and the field
    "Search query", so the two `role="search"` landmarks (top bar ≥768 px) have different names; on a phone this is the only field.
  - `SearchPage`: heading, bar, `Tabs` Posts / People (no counts), `FilterChips` on Posts only. The chips are b4's: Verified dot `primary`,
    Under review `verdict-review`, FALSE `error`, Opinions `outline-variant`. (review) `FilterChips` toggles a pressed chip off to `[]`, so
    `onChange={(s) => setFilter(s[0] ?? "all")}` (as `ProfilePage`); it has no `idPrefix` (only `Tabs` does). Six chips wrap on 390 px.
  - `PostResults` (`useCursorFeed` + `useStatusPolling` + `FeedList`, as `ProfilePosts`), `PeopleResults` (as `Connections`: skeleton rows, `UserRow`
    list, Load more; (review) `RowSkeleton` is private to `Connections.tsx`, so it is exported from there), `search-api.ts`, `search-params.ts`,
    `highlight.ts` + `Highlight.tsx`, `messages.ts`. Results are keyed `${type}:${filter}:${q}` so a change remounts (the hook ignores a new
    `fetchPage`).
- **States:** no `q` → an `EmptyState` prompt, **no request**; skeletons; results; none → "No results for “q”" + "Try different words or remove a
  filter"; error + Try again; **429 (review)**: `FeedList` shows `feedErrorMessage` (503 only today) and `waitText` says "in a minute" for any
  wait under 90 s, so both list-error helpers (`posts/messages.ts`, `social/messages.ts`) gain an additive 429 branch: "You're going too fast.
  Try again in a minute." (retry-after through `waitText`); after page 5, "That's the first 100 results. Try more specific words to narrow them
  down." through a new optional `endLabel` prop on `FeedList` (and the People list's own `LoadMore`).
- **Highlight (client-side, no HTML, review: stems compared for equality, not `startsWith`):** `highlight.ts` exports `queryTerms(q)`, `lightStem(word)`
  and `splitByTerms(text, terms)`. Terms: drop quotes, `-word` tokens and `or`; ≥2 characters, lower-cased, a short English stop-word list
  skipped, at most 8. `lightStem` is the few Snowball rules that matter: strip `'s`; `ies` → `i`; `y` → `i`; `ing`/`ed` (≥3 letters left) then
  undouble `bb dd ff gg mm nn pp rr tt`; a trailing `s`; a trailing `e`. So `running`, `runs`, `run` share `run`, while `runner`/`runway` do not (Postgres
  doesn't match them either). Text is split into word and non-word runs with `/[\p{L}\p{N}]+|[^\p{L}\p{N}]+/gu`; a word is a match when
  `lightStem(word)` is one of the terms' stems. **No regular expression is built from user text**, so no injection or backtracking. `Highlight.tsx`
  renders `<mark>` with Stitch's `bg-secondary-fixed text-on-secondary-fixed rounded-lg px-space-xs py-0.5` (`not-italic` inside opinions). It is
  approximate by design (the server stems with Snowball), so a result can match without a mark.
- **Shared components, additive only:** `PostCard` gains `highlight?: string[]` (the claim text only; it swaps `{content}` for `<Highlight/>` when
  set); (review) `FeedList` and `FeedCard` pass it straight to `PostCard`, and **`toPostCardProps` is left alone** (its test uses `toEqual` on the whole
  object); `UserRow` gains `highlight?: string[]` for name, handle and bio. Defaults leave every existing render unchanged.
- **Dev gallery:** `Section id="stitch-search"` in `StitchSections.tsx` (a highlighted card, chips, tabs, people rows, the prompt, no-results and
  throttled states), the link in `UiGallery`, the heading in `app/dev/ui/page.test.tsx`.
- **Lint traps (review):** `lint:tokens` scans strings in tests too, so no bare "shadow" / "rounded" words or `dangerouslySetInnerHTML` in
  fixtures; the `\p{L}` regex literal is fine at the project's TS target.

### 5. E2E (`frontend/e2e/search.spec.ts`, no sign-up: the suite sits at 16 of 20 sign-ups a minute)

`seedPost("runs <marker>")` and a search for "running <marker>" finds it (stemming) with the term marked; a `setPostState(…, "removed")` post and a
`"deleted"` one are absent; a `verified_true` fact appears under Verified and not under Opinions; People: the `seedAuthor` username prefix (it
contains `_`, which exercises the escaping); the top-bar form submits to `/search?q=`; the empty page shows the prompt; no horizontal overflow
at 390 px. Scope the search box with `getByRole("main")` (the top bar has a second one). (review) **Mind the rate limit:** every E2E request
comes from 127.0.0.1, React Strict Mode in dev doubles the first fetch, and the suite runs in parallel, so keep the spec to about 20 search
requests (the smoke test now makes one real search too); if it flakes, give each test its own `X-Forwarded-For`. `setPostState` gains a
`"deleted"` state (`Post.objects.filter(pk=…).update(deleted_at=timezone.now())`).

## Defaults where the docs are silent (approved with the plan)

- Submit-only search (no live search, no debounce); `page_size` fixed at 20; `q` max 200; no minimum length.
- Posts rank by `SearchRank` (default normalisation), then newest; a stop-word-only or negation-only query is an empty 200, not an error.
- Suspended authors' posts stay in post search (as in Recent); suspended users are not in People.
- People are matched on the typed phrase, not word by word.
- Tabs show no counts (no totals are computed); chips are on Posts only; switching tab resets the chip.
- A search page is `noindex, follow` with a fixed title "Search".
- Highlighting is client-side and approximate; excluded `-terms` and `or` are never highlighted.
- Pending facts are searchable and show "Checking facts…" with the usual 10 s polling (the same `FeedList` wiring as profiles).
- The 100-result note appears whenever page 5 was loaded and was full (it can't tell "exactly 100" from "more").

## Files

**Backend**
- New: `posts/migrations/0003_search_vector.py`, `posts/search.py`, `social/search.py`, `core/throttles.py`, tests
  `posts/tests/{test_search_query,test_api_search_posts,test_search_index}.py`, `social/tests/test_api_search_people.py`,
  `core/tests/{test_throttles,test_pagination_offset}.py`, a `_like` index pin in `accounts/tests/`.
- Changed: `posts/{models,views,urls}.py` (field, index, `defer`, view, route), `core/pagination.py` (the bounded-offset helper),
  `rumor_zero/settings.py` (the `search` rate).
- Existing tests changed on purpose: `posts/tests/test_models.py`, `core/tests/test_settings.py` (`test_all_eleven_throttle_scopes…` → twelve,
  `"search": 60/min`).

**Frontend**
- New: `features/search/{SearchPage,SearchBar,PostResults,PeopleResults,Highlight,highlight,search-api,search-params,messages}.ts(x)`
  (+ tests), `e2e/search.spec.ts`.
- Changed: `app/(app)/search/page.tsx` (+ a test), `lib/api/types.ts` (search types), `features/posts/{PostCard,FeedList,messages}.ts(x)`,
  `features/social/{UserRow,Connections,messages}.ts(x)` (the `highlight` prop, the `RowSkeleton` export, the 429 branches, `endLabel`; their
  tests), `features/dev/{StitchSections,UiGallery}.tsx`, `app/dev/ui/page.test.tsx`, `e2e/helpers.ts` (`"deleted"`).

**Docs:** ARCHITECTURE §2 (`search_vector` and the index exist), §3 (`search` 60/min per IP), §9 (the endpoint, the offset deviation, query counts),
§10 (the page), §12 (search text in logs/Sentry); ANALYSIS **c-46** (the people rule, the offset deviation); STRUCTURE (index count, files); MEMORY (a
Part 12 entry); `task.md` (criteria, decisions and deviations, both status spots, a note in Part 14: the export must skip `search_vector`, and in Part
16: search under load); `docs/test-command.md` Part 12 in both guides; HANDOFF; this plan's status line.

## Steps (each ends green before the next)

0. Verify the workspace (HEAD `b2f8ad5`, clean tree, Docker up, ports free); re-measure baselines (`pytest`, `npm test`, E2E). Save this plan as
   `docs/agents/plans/part-12-search.md`, link it from HANDOFF, fix its stale 11D lines.
1. **Spike (stop-and-ask gate), with the test flip:** field + index, `makemigrations`, `ruff check --fix . ; ruff format .`, `migrate`, `sqlmigrate`,
   `makemigrations --check`, `migrate posts 0002` and re-apply; update `test_models.py` (above); `defer("search_vector")` in `for_list`.
2. Index tests: generated `ALWAYS`, the GIN definition (`USING gin (search_vector)`), the `username` `_like` index pin, and the EXPLAIN gate
   (below).
3. `core/throttles.py` + the setting + tests; update `test_settings`.
4. `core/pagination.py` helper + `posts/search.py` + `social/search.py` (pure cleaning and page parsing first) with unit tests.
5. `SearchView` + route + API tests for posts, then for people.
6. Frontend: types, `search-params`, `highlight` (+ tests), `search-api`.
7. 7a `Highlight` and the additive props on `PostCard` / `UserRow` / `FeedList` (+ tests) and the 429 branches; 7b `SearchBar`, `PostResults`,
   `PeopleResults`, `SearchPage`, the route; 7c gallery specimens.
8. E2E spec and helper; the whole frontend suite, then E2E in dev mode and with `CI=1`.
9. Mutation checks (backend then frontend, nothing else running), headless Chromium at 1280 and 390 px, docs, `docs/test-command.md`, `task.md`,
   MEMORY, HANDOFF.

## Tests

- **Backend posts:** "running" finds "run" and "runs"; websearch syntax (`"exact phrase"`, `-word`, `or`); stop-word-only and negation-only → empty
  200 (the latter with no database query); **ranking** (term frequency: "storm warning storm" outranks "storm"; newest first on ties;
  deterministic across pages); the SQL-shape guard (`F` rank, `@@`); **exclusions** (removed, deleted, for every viewer including the author; a
  late-pipeline-TRUE post under review stays `under_review`); pending / under review / active emergency / suspended author are found; each filter
  alone and combined, invalid values 400, `status=removed` 400; **pagination** (pages 1–5, the 21-row look-ahead, cap → null, empty `cursor` = page 1,
  crafted cursors 404 with the shared shape, no repeats within a walk); blank / NUL / DEL / too-long `q`; 25 keys and the feed envelope; flags for a
  viewer; stale token 401; anonymous works; never cached; 405; **query counts** 1 / 2.
- **Backend people:** username prefix; `_`, `%`, `\` in `q` are literal (`a_c` doesn't match `abc`); case-insensitive; NFKC; display-name word start
  (start, after space / hyphen / apostrophe), not mid-word; `"-"`, `"'"`, `"@"`, whitespace-only → empty 200; inactive excluded; the 9 row keys equal the
  follower rows'; `counts.verified` includes deleted posts; `reputation.score` null under 3; `is_following` / `is_me`; **order** (exact, prefix, name;
  A–Z; a higher score never jumps ahead; stable across pages); the cap; query counts 1 / 2; post filters ignored.
- **Backend infra:** the generated column and GIN definition; **EXPLAIN gate (review)**: ~200 rows with varied content, `ANALYZE posts_post`,
  `SET LOCAL enable_seqscan = off` (safe inside the `db` transaction), `qs.explain(format="json")` of the very queryset the shared builder returns,
  assert "Bitmap Index Scan" and `posts_search_idx` (GIN has no plain index scan, so leave bitmap scans on); a manual natural-plan check at 10k rows
  in step 9. Throttle: the real 60 + 1 requests (rates are bound at import), another IP unaffected (relay-header pattern of `test_api_status.py`),
  signed-in and anonymous from one IP share the bucket, a stale-token 401 doesn't count, a 400 does, another scope untouched, plus a `get_cache_key`
  unit test with `APIRequestFactory`. Offset helper: every cursor string. `makemigrations --check` clean.
- **Frontend:** `highlight` (stems, the doubled-consonant and `e` rules, quotes, `-word`, `or`, stop words, caps, Unicode, an HTML-looking string stays
  text, `runner` / `runway` unmarked); `search-params` (clamps, defaults, repeated keys); `search-api` (encoding of `& # % + space` and emoji, the
  cursor); `SearchBar`; `SearchPage` + results (prompt, loading, results with marks, none, error + retry, 429 text, Load more, the 100 note, tab and
  chip URL changes, chip re-click → All, people rows with the badge, the remount key); `PostCard` / `UserRow` / `FeedList` additions; the route
  (metadata `noindex`); the 429 branches of both helpers; `/dev/ui`.
- **E2E:** as §5.

## Verification

- Backend (venv activated in **every** call): `ruff check .`, `ruff format --check .`, `python manage.py makemigrations --check --dry-run`,
  `python manage.py check`, `pytest`; the migration rolled back and re-applied on the dev database; the real query's `EXPLAIN` printed.
- Frontend: `npm run lint`, `lint:tokens`, `typecheck`, `format:check`, `npm test`, `NEXT_PUBLIC_GOOGLE_CLIENT_ID= npm run build`,
  `npm run test:e2e` (dev and `CI=1`).
- Headless Chromium at 1280 and 390 px against `runserver` + `next dev`: the prompt, a posts result with marks, each chip, a people result, none,
  throttled; no horizontal scroll. `docs/test-command.md` Part 12: the Linux blocks run verbatim.

## Stop conditions

- The spike fails (Postgres or Django rejects the generated column): stop and ask.
- Anything needing a new dependency, service or extension (e.g. `pg_trgm`), a `design/` edit, or a change to the access-token storage rule.
- An existing test failing for a reason this plan doesn't name: stop and report rather than adjust it.
- The search query's plan not using the GIN index on the test table: stop and report before shipping.

## Follow-ups to record (not done here)

- **Part 14:** the data export must not include `search_vector`.
- **Part 16:** search under load (ranking a very common word sorts every match; the throttle is per IP only); scrubbing the search query from Sentry
  request URLs and access logs; a trigram index for people; `ts_headline` if the client highlight proves too approximate.
- **Later:** typo tolerance (the guide's Meilisearch upgrade path); comment and source search.
