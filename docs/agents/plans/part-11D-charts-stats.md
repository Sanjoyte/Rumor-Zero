# Plan: Part 11D, Charts & stats

- **Status:** APPROVED by the user (Sanjoy Rozario) on 2026-10-20, together with the four decisions and the defaults
  below; drafted 2026-10-20 by Claude (Sonnet 5.5). Saved here and linked from HANDOFF at approval (HANDOFF's stale "11C is
  uncommitted" line was corrected then), so step 0 only needs to verify the workspace and record the baselines.
  **Implemented 2026-10-20 (Claude, Sonnet 5.5); uncommitted.** Deviations are listed in `task.md` Part 11D.
- **Implement with:** Sonnet 5.5 · medium (task.md).
- **Evidence (all read-only):** HANDOFF, MEMORY, `task.md` 11B/11C/11D/14, ARCHITECTURE §2/§4/§4a/§9/§10, ANALYSIS f-5/f-6,
  STRUCTURE; backend `posts/{views,urls,models,serializers}.py`, `pipeline/routing.py`, `moderation/{models,rules,services}.py`,
  `reputation/{views,serializers,services,scoring,models}.py`, `social/{models,engagement}.py`, `core/{models,services}.py`;
  frontend `PostDetail`, `VerdictBlock`, `ProfilePage`, `ProfileHeader`, `CredibilityBadge`, `ProgressBar`, `lint-tokens.mjs`,
  `globals.css`, the dev gallery, API modules, E2E helpers; three Explore agents (backend, frontend, Stitch b3/c1/b4/c2 +
  DESIGN.md).

## Context

Part 11D turns data we really have into the Stitch charts (D5, ANALYSIS f-6): **how a fact post was checked** (a confidence
meter with the auto-label threshold marked, three tiles, time to verdict), **how it spread** (reposts and likes per day, first
14 days, verdict day marked), and **an account's credibility over time** (ring, counts, 30-day sparkline on every profile; the
owner's full history with reversed rows marked and an "Ask for another look" link on your own profile). No chart library;
every chart is token-built HTML/SVG with a text alternative. Two read endpoints are new or extended.

**Dependency check (2026-10-20).** 11D depends on **7B** (Done 2026-10-10) and **11B** (Done 2026-10-19). Their chains (11, 10,
9, 8, 7, 6, 5, 4, 3, 2, 1, 0C, 0A/0B/0D) are Done, as are 11C (the post object has 25 keys) and the pipeline (Part 9) the meter
reads. Open but not blocking: Part 3 criterion 4, CI for Parts 2 to 11C (not reported), the Part 17 stub launch blocker.

**Workspace:** HEAD `ee63914` ("Part 11C: Emergency posts"), clean tree. HANDOFF still says 11C is uncommitted (stale).

**Already in place (no schema change):** `posts.confidence_score/verdict_source/pipeline_checked_at/created_at`; ModerationAction
rows for every moderator verdict (index `modaction_post_created_idx (post, -created_at)`); `likes_post_created_idx`,
`reposts_post_created_idx`, partial `comments_post_visible_idx` (and `social.engagement.shown_comments()`, its predicate);
`repevent_user_created_idx (user, created_at)` with strictly increasing times per person and `score_after` on every row;
`GET /users/{u}/reputation/` (2 queries, no auth) and `GET /me/reputation/events/` (11-key rows with the `appeal` block);
frontend `CredibilityBadge` (+ `CREDIBILITY_HELP_HREF`, `NEW_SCORE_HINT`), `ProgressBar`, `Skeleton`, `Card`, `LoadMore`,
`useCursorFeed`, `formatConfidence`, E2E `seedAuthor` / `seedCheckedFacts` / `processPost` / `logIn`. No migration is needed.

## Your decisions (2026-10-20)

1. **Threshold: the live setting, honest wording.** The meter marks today's `confidence_threshold`. If it was raised above the
   post's confidence since the check, the tile says "Below today's threshold of N%" instead of a negative margin. Storing the
   threshold per verdict is a follow-up (needs a posts migration and a one-line write in Part 9's routing).
2. **The owner sees the real score.** CredibilityPanel's bar shows the stored score (50 for a new account) and each row its
   "score after", with the note "Others see New until 3 of your posts are checked." while the public score is hidden.
3. **The spread chart is for fact posts only.** Opinions get no stats section (the endpoint still answers for them, with null
   check fields).
4. **Credibility visuals are neutral grey** (ring, bar, sparkline): extends your 2026-10-13 badge decision. The post's
   confidence meter keeps its verdict tone (teal for TRUE, red for FALSE).

## Scope

**In:** `GET /api/v1/posts/{id}/stats/`; `trend` on `GET /api/v1/users/{u}/reputation/`; `components/ui/charts/` (MeterBar,
StatTile, BarChart, RingGauge, Sparkline + a shared hidden data table); `PostStats`; `CredibilityWidget`; `CredibilityPanel`;
API calls, types, `formatDuration` / `formatShortDate` / `formatWeight`; dev gallery sections; a no-chart-library guard test;
one E2E spec; docs and `docs/test-command.md` Part 11D (both guides).

**Not in 11D:** the panel in Settings (Part 14 mounts the same component); the `/how-it-works#credibility` text and anchor
(Part 15); storing the threshold per verdict; notifications; search (12); any cache or throttle for the new endpoint (Part 16).

## Design

### 1. `GET /api/v1/posts/{id}/stats/`

- **Where:** `PostStatsView` in `apps/posts/views.py`; route `posts/<str:post_id>/stats/` in `posts/urls.py` (an extra path
  segment, so it can't be taken for an id); pure builders in new `apps/posts/stats.py`. The posts app reaches the other apps only
  through function-local imports, as `for_list` does: the daily counts live in `social/engagement.py` (`daily_engagement`), the
  moderator verdict time in `moderation/queries.py` (`with_verdict_time`).
- **Access:** `authentication_classes = []`, `AllowAny`, `never_cache`, no throttle (like `PostStatusView` and
  `ReputationView`: the answer doesn't depend on who asks, so a stale Bearer token is not a 401). `parse_post_id` by hand; an
  unknown, malformed or **deleted** id is a JSON 404. A **removed** post is 404 for everyone, its author included (the rule of
  likes, comments and reposts; nothing renders stats for it). This tightens ARCHITECTURE §9's "same visibility as detail".
- **Payload (6 keys, pinned by a test):**
  `{confidence_score, confidence_threshold, verdict_source, seconds_to_verdict, verdict_at, daily:[{date, reposts, likes, comments} × 14]}`.
  - `confidence_score` and `verdict_source` come from the post object's own helpers (`shown_confidence`,
    `shown_verdict_source`), so a late pipeline TRUE held under review stays private, exactly as in the detail endpoint.
  - `confidence_threshold` = `get_platform_settings().confidence_threshold` (cached) when `confidence_score` is non-null, else
    null. One threshold serves TRUE and FALSE.
  - `verdict_at` (only for `verified_*`, else null): pipeline → `pipeline_checked_at`; moderator → `created_at` of the latest
    ModerationAction with `action in (verified, marked_false)` and `to_status = post.status` (a correlated `Subquery`
    annotation, so no extra query). **Not** `moderated_at`: every moderator action (Demote, Dismiss, Escalate) overwrites it. No
    action row → null (no fallback).
  - `seconds_to_verdict = max(0, int((verdict_at - created_at).total_seconds()))`, null when `verdict_at` is null.
  - pending, published, under review: all five check fields null.
- **`daily`:** `day0` = the UTC date of `created_at`; exactly **14 entries**, `day0 … day0+13`, zero-filled, `date` as
  `YYYY-MM-DD`. Day 0 is a partial day. Rows are counted by `TruncDate("created_at", tzinfo=UTC)` inside the window
  `[midnight(day0), midnight(day0) + 14 days)`, so each series is a range scan of its `(post, created_at)` index. Comments use
  `shown_comments()` (hidden and deleted comments never count). The payload therefore depends only on the post and its rows,
  never on the clock. Likes and reposts are hard-deleted when taken back, so buckets show surviving rows only (documented).
- **Queries:** the post with the verdict-time subquery (1) + one `UNION ALL` of the three grouped counts (1) = **2, whatever the
  activity**. psycopg may reject an untyped literal label in a union: then `Cast(Value(...), CharField())`, and if that fails
  three grouped queries (4 total, still constant). The test pins whichever count is built.

### 2. `trend` on the reputation endpoint

- `trend: [30 × {date, score}]`, **null while `public_score` is null** (sample < 3). Emits only `{date, score}` (the existing
  "nothing private" test greps for `score_after`).
- Window: 30 UTC days ending **today** (`today-29 … today`). Baseline = a scalar `Subquery` annotation on the existing user
  query (the last `score_after` before the window's first midnight, 50 = `START_SCORE` when none): no extra query. The days'
  values = one `DISTINCT ON (day)` query ordered `day, -created_at` (the last row of each UTC day; rows are strictly increasing
  per person, so no ties), run only when the score is public. Python carries the value forward over quiet days.
  **Queries: 3 when public, 2 when hidden** (was 2).
- The builder is a pure function `build_trend(base, last_by_day, today)` in new `apps/reputation/trend.py`, so the UTC-midnight
  and carry-forward cases are tested with a given `today` (no clock patching: `timezone.now()` is called once in the view).
- As the docs say, once the score is public the earlier days show the raw `score_after`, including days before the third counted
  event.

### 3. Frontend

**Chart primitives (`src/components/ui/charts/`)** — each graphic is `<figure>`: a `div role="img" aria-label={summary}` holding
the visuals, and a **sibling** `sr-only` `<table>` (children of `role="img"` are presentational, so a table inside it would be
invisible to a screen reader). No `animate-*`, no transitions (reduced motion is satisfied by having none). Heights and widths
via inline `style` percentages (the `ProgressBar` precedent; `lint:tokens` allows it). Colour only through token classes
(`bg-*`, `text-*`, `stroke-current`).
- `MeterBar` — track + fill (`tone`: `primary` | `error` | `neutral`), an optional threshold **tick** at `left: N%` with its
  caption, "0%" and "100%" at the ends. Table: Confidence, Threshold, Margin.
- `BarChart` — grouped bars per day (flex columns, heights as % of a rounded-up maximum, two dashed gridlines at 0 and max), a
  legend with the series' glyphs and words, an optional marker on one column (the verdict day: a neutral tick and the word
  "Verdict" in the legend), axis labels for the first, middle and last day (`formatShortDate`, UTC). Empty data → empty bars and
  the caption "No reposts or likes yet." Table: one row per day, one column per series.
- `RingGauge` — SVG `viewBox 0 0 36 36`, one track circle and one value circle (`pathLength=100`, dash `v 100`, `-rotate-90`
  on the circle so the arc starts at 12 o'clock; Stitch's path was rotated to 9 o'clock by mistake), centre text in HTML. A null
  or 0 value draws the track only (a round cap would draw a dot). Table: the score or "New".
- `Sparkline` — SVG `viewBox 0 0 112 24` (uniform, so the end dot stays round), the path built by a tested pure function
  (`sparkline-path.ts`: auto-scaled, minimum span of 10 points so a flat line doesn't zoom noise), an end dot. Table: date and
  score for each day.
- `StatTile` — label, value, optional sub-line (Stitch b3's tile). It is plain text, not an image, so it has no `role="img"`
  (a recorded deviation from "each has `role="img"`").
- Guard test `no-chart-library.test.ts` reads `package.json` and fails on `recharts|chart.js|d3|victory|nivo|visx|echarts|
  apexcharts|highcharts`.

**`PostStats` (`features/posts/`)** — `PostStatsView` (presentational, used by `/dev/ui`) + `PostStats` (fetches through
`usePostStats`, modelled on `usePostDetail`: abort on cleanup, a viewer marked fetched only on success, refetch when
`status`/`verdict_source`/`confidence_score` change so the live badge flip updates it). Client-side only: the page's light SSR is
unchanged. Rendered in `PostDetail` after `VerdictBlock` / `AppealOutcome` and before `SourceList`, for **facts** (the removed
branch returns earlier). Heading "How this was checked" (`h2.font-headline-sm`, like Verdict). States:
- loading → a same-size `Skeleton`; fetch failure → nothing (silent, like polling).
- pending → "Checking facts… The result and how it was reached appear here."; under review → "A moderator is taking a look. There
  is no automatic result to show." (no meter, no tiles).
- `verified_*` by pipeline → `MeterBar` (tone = the verdict: teal TRUE, red FALSE, tick at the threshold) + three tiles:
  **Confidence** "95%" · **Threshold and margin** "85%" and "+10 points" (or "Below today's threshold of N%") · **Time to
  verdict** (`formatDuration`: "under 1 s", "2 min 14 s").
- `verified_*` by a moderator → "Reviewed by a moderator" and one tile, **Time to decision**; **never a %**.
- every fact → a second card "Reposts and likes": the `BarChart` (reposts `secondary`, likes `outline`; comments only in the
  hidden table), caption "First 14 days after posting (UTC)".

**`CredibilityWidget` (`features/reputation/`)** — on every profile, between `ProfileHeader` and the filter chips, outside the
header (its tests look for "68" and "FALSE" inside the Profile region). Heading "Credibility" (no seal), `RingGauge` neutral
(score, or "New" with `NEW_SCORE_HINT`), "20 verified · 3 FALSE" with the dots `bg-primary` / `bg-error` (verdict colours, as
c1's counters), the 30-day `Sparkline` (neutral) with "Last 30 days", and the "How this is calculated" link
(`CREDIBILITY_HELP_HREF`). The ring and counts come from the profile payload already loaded (so they are in the server render);
only `trend` needs `fetchReputation(username)` (public, `token: false`): skeleton while loading, nothing on failure or when
`trend` is null. The header's `CredibilityBadge` stays.

**`CredibilityPanel` (`features/reputation/`)** — only when `profile.is_me && viewerReady` (the server render never shows it).
Loads page 1 of `GET /me/reputation/events/` on mount through `useCursorFeed`. A card: heading "Your credibility history", a
neutral `MeterBar` with the **real score** (newest row's `score_after`, 50 when the ledger is empty) and, while the public score
is null, "Others see New until 3 of your posts are checked."; the history list is a disclosure ("Show history (N)") with Load
more. A row: label, date, the change (`formatWeight`: "+1", "−0.25"), "score after N", a link "View post" (`/p/<id>`, when
`post_id`), **Reversed** rows struck through with a "Reversed" word, reversal rows as ordinary rows ("Reversed: …"). On an own
negative row that still stands: **"Ask for another look"** (a `Link` to `/p/<id>`, `prefetch={false}`, where the existing
`AppealButton` lives) when `appeal.can_appeal && post_id`, otherwise the appeal's state in words ("Appeal open", "Appeal upheld
— the decision stands", "Appeal overturned"). Empty ledger → `EmptyState`; failure → `Alert` with Retry. Props: `defaultOpen`
(false on the profile, true in Settings from Part 14).

**API, types, helpers:** `fetchPostStats(id, signal)` in `posts-api.ts` (`token: false`); new `reputation-api.ts`
(`fetchReputation`, `fetchMyReputationEvents` with `withCursor`); types `PostStats`, `DailyBucket`, `ReputationSummary` (with
`trend`), `LedgerEntry`, `LedgerAppeal` in `lib/api/types.ts`; `formatDuration`, `formatShortDate`, `formatWeight` in
`lib/format.ts`.

**Dev gallery:** the primitives in `DisplaySections.tsx`; `PostStatsView` and `CredibilityWidgetView` / `CredibilityPanelView`
specimens (no providers, no fetch) in `StitchSections.tsx`.

### 4. E2E (`frontend/e2e/stats.spec.ts`, no sign-up)

`seedAuthor("stat")` + `seedCheckedFacts(username, 1)` (the real stub pipeline) → an anonymous visitor opens `/p/<id>`: the
meter's name says 95% confidence with the threshold read from the platform settings (a helper `confidenceThreshold()` next to
`emergencySettings()`, since the E2E backend uses the developer's seed — 85 by default), the three tiles show, and the spread
chart is present with a text alternative. A second test: an author with 3 checked facts → their profile shows the ring "62", the
"3 verified · 0 FALSE" line and the sparkline; the same author logged in sees the panel with 3 rows and no appeal link on
positive rows.

## Defaults where the docs are silent (approved with the plan, 2026-10-20)

- Stats of a removed post: 404 for everyone (above). Stats are unauthenticated and unthrottled (Part 16 reviews load).
- `daily` is always 14 zero-filled UTC calendar days from the post's UTC date (day 0 partial); days after today are simply zero.
- The chart draws reposts and likes (as the docs say); comments are in the payload and in the hidden table.
- `verdict_at` for a pipeline label is the check time. Known edge: a late pipeline TRUE made public by a moderator's Dismiss
  shows the earlier check time (recorded as a follow-up).
- Pending / under-review facts show a one-line note, not an empty meter; a failed fetch hides the section.
- The "Ask for another look" action is a link to the post page, where the existing appeal button already lives; no modal is
  opened from a ledger row (a row has no post text).
- Weights print as "+1", "+0.25", "−2" (minus sign U+2212), trailing zeros dropped.
- The stats chart doesn't refresh when you like the post on the same page; a reload or a status change does.
- Chart tones: meter = verdict tone, credibility = neutral (`text-on-surface-variant` on `text-surface-container-highest`),
  BarChart reposts `secondary` / likes `outline`; final shades are checked in the headless screenshots.

## Files

**Backend**
- New: `posts/stats.py`, `reputation/trend.py`, tests `posts/tests/{test_stats,test_api_stats}.py`,
  `social/tests/test_daily_engagement.py`, `reputation/tests/{test_trend,test_api_trend}.py`.
- Changed: `posts/{views,urls}.py`, `social/engagement.py`, `moderation/queries.py`, `reputation/{views,serializers}.py`.
- Existing tests that change on purpose: `reputation/tests/test_api_reputation.py` (the `KEYS` set, the exact JSON of a new
  account, `test_two_queries_however_many_events` → 3 public / 2 hidden).

**Frontend**
- New: `components/ui/charts/{MeterBar,StatTile,BarChart,RingGauge,Sparkline,ChartTable,sparkline-path}.tsx|ts` (+ tests, +
  `no-chart-library.test.ts`); `features/posts/{PostStats,usePostStats}.ts(x)` (+ tests); `features/reputation/{CredibilityWidget,
  CredibilityPanel,reputation-api,useReputationTrend,ledger-copy}.ts(x)` (+ tests); `e2e/stats.spec.ts`.
- Changed: `lib/api/types.ts`, `lib/format.ts` (+ tests), `features/posts/{posts-api,PostDetail,test-helpers}.ts(x)`,
  `features/social/{ProfilePage,test-helpers}.tsx`, `features/dev/{DisplaySections,StitchSections}.tsx`, `e2e/helpers.ts`.
- Existing tests that change on purpose: `PostDetail.test.tsx` (its partial `posts-api` mock gains `fetchPostStats`),
  `ProfilePage.test.tsx` (a `reputation-api` mock), `app/dev/ui/page.test.tsx`.

**Docs:** ARCHITECTURE §9 (stats rules, 404 for removed, trend) / §10 / §4a display; ANALYSIS f-6 "as built"; STRUCTURE; MEMORY
(Part 11D entries); `task.md` (criteria, decisions and deviations, both status spots, notes in 14 and 15);
`docs/test-command.md` Part 11D in both guides; HANDOFF; this plan's status line.

## Steps (each ends green before the next)

0. Verify the workspace (HEAD, clean tree, Docker up); baselines `pytest` (3644), `npm test` (1782), E2E (43). Save this plan,
   link it from HANDOFF, correct its stale 11C line.
1. Pure backend builders + tests: `posts/stats.py` (daily buckets, verdict fields), `reputation/trend.py`.
2. Queries and the view: `daily_engagement`, `with_verdict_time`, `PostStatsView`, URL; API + query-count tests.
3. `trend` in the reputation view and serializer; update the three existing tests.
4. Frontend types, API calls, format helpers + tests.
5. Chart primitives + tests + guard test + gallery specimens; `lint`, `lint:tokens`, `typecheck`, `format:check`.
6. `PostStats` + hook + `PostDetail` wiring + tests.
7. `CredibilityWidget`, `CredibilityPanel`, `ProfilePage` wiring + tests.
8. E2E spec and helper; the whole suite in dev mode and with `CI=1`.
9. Mutation checks (backend, then frontend; nothing else running meanwhile), headless Chromium at 1280 and 390 px, docs,
   `docs/test-command.md`, `task.md`, MEMORY, HANDOFF.

## Tests

- **Backend pure/API:** the 6-key payload; per status × viewer (anonymous, other, author, stale token ignored, malformed /
  unknown / deleted / removed → 404, opinion → nulls); confidence and threshold only for pipeline labels; a late TRUE under
  review stays null; moderator label → `verdict_at` from the verdict's audit row **not** a later Demote's `moderated_at`;
  `seconds_to_verdict` ≥ 0 and null without a time; **buckets** across UTC midnight (rows at 23:59:59.999999 and 00:00:00 land
  in adjacent days; the 14-day edge in and out; a post created at 23:59:30), zero-fill of an empty post, hidden / deleted
  comments excluded, a taken-back like absent, rows after day 13 ignored; **query count identical for 1 and 50 rows per
  table**; no private field. Trend: 30 points, baseline before the window, 50 before the first row, carry-forward, last row
  of a day with several, midnight edges, null while hidden, 3 / 2 queries, `{date, score}` only.
- **Frontend:** each primitive (render, `role="img"`, label, sibling table, empty data, clamping, tones, no `animate-`);
  `sparkline-path`; the no-chart-library guard; `PostStats` states (loading, error, pending, under review, pipeline TRUE and
  FALSE, margin and "Below today's threshold", moderator with **no %**, refetch on a status flip, opinion not rendered, removed
  not rendered); `CredibilityWidget` (score, New, trend loading / failed / null); `CredibilityPanel` (real score and note,
  rows, reversed, appeal link vs state words, empty, error, Load more, only for `is_me`); `ProfilePage` composition; format
  helpers; `/dev/ui`.
- **E2E:** as §4.

## Verification

- Backend (venv in every call): `ruff check .`, `ruff format --check .`, `python manage.py makemigrations --check --dry-run`,
  `python manage.py check`, `pytest`; `recompute_reputation --check` on the dev database.
- Frontend: `npm run lint`, `lint:tokens`, `typecheck`, `format:check`, `npm test`, `NEXT_PUBLIC_GOOGLE_CLIENT_ID= npm run
  build`, `npm run test:e2e` (dev and `CI=1`).
- Headless Chromium at 1280 and 390 px: a pipeline-TRUE and a pipeline-FALSE post page, a moderator-labelled one, a pending
  one, the spread chart (empty and with data), a profile with a score and a new one, the owner's panel with a reversed row and
  an appeal link; no horizontal scroll. `docs/test-command.md` Part 11D: the Linux blocks extracted and run verbatim.

## Stop conditions

- Anything that needs a migration, a new dependency or service, a chart library, or a `design/` edit: stop and ask.
- A trend or stats query that can't stay constant: stop and report.
- An existing test failing for a reason this plan doesn't name: stop and report rather than adjust it.
- Any need to touch the access-token storage rule or to store something in browser storage.

## Follow-ups to record (not done here)

- **Part 14:** mount `CredibilityPanel defaultOpen` in Settings.
- **Part 15:** `/how-it-works#credibility` text and anchor.
- **Part 16:** the unthrottled stats endpoint; the `DISTINCT ON` trend query and the daily union under load.
- **Later:** store the threshold used per verdict; `verdict_at` for a late pipeline TRUE made public by a Dismiss.
