# Plan: Part 4, Posts (composer + Recent feed)

- **Status:** APPROVED by the user (Sanjoy Rozario) on 2026-10-08, together with the decisions and
  defaults below. Saved here and linked from `docs/agents/HANDOFF.md` at planning time; not
  implemented yet.
- **Drafted:** 2026-10-08 by Claude (Opus 5.5). A separate design-review pass checked it against the
  installed sources, and its findings are folded in. **Implement with:** Sonnet 5.5 · high (task.md).
- **Evidence:** read-only research. Django 5.2.17, DRF 3.18.1 and idna 3.20 read in
  `backend/.venv/lib/python3.13/site-packages/`; browser URL parsing checked with Node 24's `URL`
  (the WHATWG parser browsers use).

## Context

`task.md` Part 4 adds the first real content:
- opinion and fact posts, written in the b2 composer modal;
- up to 5 sources (URL or DOI) on fact posts;
- a public, newest-first **Recent** feed on `/home` (b1).

Fact posts stay `pending` ("CHECKING FACTS…"); the pipeline is Part 9. The part also fixes the
central `posts.Post` schema (every ARCHITECTURE §2 column except `search_vector`), so later parts
add logic, not risky schema changes.

**Dependencies.**
- Part 4 depends only on Part 1, which is Done (2026-10-03, CI green).
- Parts 2 and 3 are also Done. Part 3's criterion 4 is your manual real-Google check; it doesn't
  affect Part 4.
- HEAD is `6cd67d0` ("Part 3: Continue with Google") and the tree is clean.

**Already there to reuse** (verified):
- **Backend:**
  - the `post_create` 30/h throttle rate;
  - `PlatformSettings.fact_posts_per_day` through `get_platform_settings()` (60 s cache);
  - `apps.core.pagination.CursorPagination` and the core exception handler;
  - `IsEmailVerified` (403 `email_unverified`) and `avatar_url()`;
  - `UserFactory`, `access_token_for()` and `run_together()` (in the accounts tests);
  - `django_assert_num_queries`.
- **Frontend:**
  - `features/posts/PostCard.tsx` (presentational, every status variant), `StatusBadge`,
    `VerdictStripe`, `CategoryChip` and `lib/post-display.ts`;
  - the `Post`, `PostSource`, `FeedItem` and `FeedResponse` types;
  - the `api.*` client (Bearer token, one retry after a 401, and `fieldErrors["sources.1"]` for
    `{"sources": {"1": [...]}}`);
  - the UI primitives `Modal`, `SegmentedControl`, `Textarea` (with its counter), `TextField`,
    `Button`, `Alert`, `useToast`, `Skeleton`, `EmptyState`, `LoadMore` and `Tabs`;
  - a mock composer in `features/dev/StitchSections.tsx`;
  - `AppShell.onNewPost`, which nothing passes yet;
  - the E2E helpers `signUp()` and `waitForEmailLink()`.

**Your decisions (2026-10-08):**
1. **The fact quota is a rolling 24-hour window.** Every fact post created in the last 24 h counts,
   **including ones deleted or removed later**; otherwise deleting and reposting would get around
   it. The composer says "7/10 fact posts left", and at 0 it says when the next one frees up.
2. **Pin `idna==3.20`** in `backend/requirements.txt`. It is already installed through requests and
   anymail, BSD-licensed, and needs no service.
   - Python's built-in codec is IDNA 2003 and turns `faß.de` into `fass.de`, a different site.
     Browsers and `idna` (UTS #46) give `xn--fa-hia.de`.
   - **Found in review:** in 3.20 the `transitional` argument is deprecated and ignored, because
     the package is always non-transitional. So we call `idna.encode(host, uts46=True)`. You get
     the behaviour you chose; only the call differs.
3. **"Optimistic insert" means insert on success.**
   - The composer shows "Posting…" until the API answers.
   - On 201 it closes, and the post the server returned goes to the top of Recent with no refetch.
   - Errors stay in the composer with the text intact.
4. **Posting from a page without the feed:** you stay on the page and get a toast. `/home` adds the
   post to the top when it is open.

**Defaults where the docs are silent** (approve or change them together with the plan):
- **Quota refused → 429 `fact_quota_exceeded`** with `Retry-After` (seconds until the next slot).
  - It is a rate over time with a known retry time.
  - The code tells it apart from the `post_create` throttle's 429 `throttled`.
  - The composer checks the code before the status.
- **Fact limit set to 0** (the admin kill switch) → **403 `fact_posts_paused`**, with no
  `Retry-After`. The composer says "Fact posts are paused right now."
- **One extra partial index for Recent:** `(created_at DESC, id DESC) WHERE deleted_at IS NULL AND
  NOT status='removed'`. The listed `(status, created_at)` index can't serve "every status except
  removed, newest first". It goes into ARCHITECTURE §2.
- **Characters are counted in code points everywhere,** so the client counter matches Python's
  `len` and Postgres's `char_length`: an emoji counts 1, not 2. The `Textarea` counter changes to
  match, and it gets no `maxLength` attribute, which counts UTF-16 units.
- **Content is trimmed at both ends.** Whitespace-only text counts as empty. Newlines inside are
  kept.
- **Host names:** underscores are allowed (browsers accept them), and so is `--` inside a label.
  Labels can't start or end with `-`. A trailing dot (`example.com.`) is refused.
- **Recent is not cached in Part 4.** ARCHITECTURE §9 caches only Following's first page and the
  pinned list.
- **The posts admin is read-only until Part 10,** so nothing bypasses `posts.services`.
- **Closing the composer keeps the draft.** Cancel, Esc and × keep the text, type and source rows
  in memory. A successful post or a change of user (logout) clears them. Nothing goes to storage.
- **Every "New post" entry point follows Part 2's rule:**
  - an unverified user gets `aria-disabled` and the same toast;
  - the `/home` trigger card does the same;
  - anonymous visitors see "Log in to post" (`/login?next=/home`);
  - the modal still shows a disabled form with the verify prompt if it is ever open for an
    unverified user, for example after a 403 `email_unverified`.
- **The submit button stays enabled** (except while posting). Clicking it shows each error and
  focuses the first invalid control, instead of a silently disabled button.
- **A toast after every successful post,** on `/home` too: "Posted." or "Posted. Checking the
  facts…". Once the modal closes, it is the only screen-reader announcement.
- **A blank display name on a card** shows `@username` in bold with the separate handle hidden (no
  "@ada @ada").
- **The 0C follow-up is fixed here:** at 390 px the card header no longer wraps the name. The name
  truncates, and the chips wrap under it on phones.
- **Submit labels** come from the 0B mock: "Post opinion" / "Post fact, will be checked".

## Backend

### Setup
- `rumor_zero/settings.py`: add `"django.contrib.postgres"` after `staticfiles` (it is part of
  Django) and `"apps.posts"` after `apps.accounts` to `INSTALLED_APPS`.
- `requirements.txt`: add `idna==3.20` (decision 2). SETUP.md B1 gets a row. No new env variable.
- Create the app:
  1. `mkdir apps/posts`
  2. `python manage.py startapp posts apps/posts`
  3. set `name = "apps.posts"`
  4. replace the generated `tests.py` with a `tests/` package that has an `__init__.py`. The
     basenames `test_models.py` and `test_admin.py` also exist in accounts, so collection needs the
     package.
  5. run `ruff check --fix . ; ruff format .`
- URLs:
  - `rumor_zero/urls.py` gets `path("api/", include("apps.posts.urls"))` after the accounts include.
  - `apps/posts/urls.py` has `v1/posts/` and `v1/me/fact-quota/`.
  - Accounts' `v1/me/` is an exact match, so these don't collide with it.

### Model (`apps/posts/models.py`)
`Post` has every §2 column except `search_vector` (Part 12).

**Choices.** `TextChoices` for:
- `PostType`: opinion, fact
- `PostStatus`: the six statuses
- `FlaggedReason`: pipeline, reports, both, appeal
- `PipelineVerdict`: true, false, inconclusive
- `VerdictSource`: pipeline, moderator

**Fields:**

| Field | Definition |
|---|---|
| `id` | UUID |
| `author` | FK, CASCADE, `related_name="posts"`, with `db_index=False` and a comment: the `(author, -created_at)` index covers it |
| `content` | `TextField` |
| `post_type` | choices field |
| `sources` | `ArrayField(CharField(max_length=500), default=list, blank=True)` |
| `is_emergency`, `emergency_expires_at`, `emergency_demoted_at` | §2 columns |
| `status` | no default: the service always sets it |
| `flagged_reason`, `pre_review_status`, `pre_removal_status`, `pipeline_verdict`, `verdict_source` | nullable `CharField`s with choices, marked `# noqa: DJ001` as in accounts |
| `confidence_score` | `Decimal(5,2)`, null |
| `pipeline_result` | JSON, null |
| `pipeline_attempts` | `PositiveSmallIntegerField`, default 0 |
| `pipeline_next_attempt_at`, `pipeline_checked_at` | §2 columns |
| `verdict_note` | `CharField(500)`, blank |
| `report_count` | `PositiveIntegerField`, default 0 |
| `escalated_at` | §2 column |
| `moderated_by` | FK, SET_NULL, `related_name="+"` |
| `moderated_at`, `deleted_at` | §2 columns |
| `created_at` | `default=timezone.now`, **not** `auto_now_add`, so the service and factories can set it |
| `updated_at` | `auto_now` |

**`PostQuerySet`** (no filtering default manager; the quota must see every row):
- `.visible()`: not deleted and not removed;
- `.for_list()`: `select_related("author")` and `defer("pipeline_result")`.

Parts 5, 6 and 12 reuse both.

**`CheckConstraint`s** use `condition=` and are named `posts_post_<rule>` (each under 63
characters):
- content length 1–500: `GreaterThanOrEqual(Length("content"), 1) & LessThanOrEqual(Length("content"),
  500)`. That is `char_length`, so it counts code points. No `trim()`: Postgres's `trim` strips only
  spaces. The serializer rejects blank text.
- every enum column holds one of its choices. Nullable ones are written as
  `Q(x__in=…) | Q(x__isnull=True)`.
- an opinion's status ∈ {published, under_review, removed}; a fact's status ≠ published.
- at most 5 sources: `sources__len__lte=5`. Verified: `__len` compiles to
  `coalesce(array_length(sources, 1), 0)`, so `[]` counts as 0.
- only facts have sources: `Q(post_type="fact") | Q(sources__len=0)`.
- no empty source: `~Q(sources__contains=[""])`.
- no NULL source: `array_position(sources, NULL) IS NULL`, through a `Func`.
- `is_emergency` ⇒ fact.
- `emergency_expires_at` is set iff `is_emergency`.
- `confidence_score` is null or 0–100.

**Indexes.** Django limits index names to 30 characters (`Index.max_name_length`).

| Name | Index |
|---|---|
| `posts_status_created_idx` | `(status, -created_at)` |
| `posts_author_created_idx` | `(author, -created_at)`; it also serves the quota count |
| `posts_pending_queue_idx` | `(-is_emergency, created_at) WHERE post_type='fact' AND status='pending' AND deleted_at IS NULL` |
| `posts_review_queue_idx` | `(created_at) WHERE status='under_review'` |
| `posts_pinned_emerg_idx` | `(emergency_expires_at) WHERE is_emergency AND emergency_demoted_at IS NULL AND deleted_at IS NULL` |
| `posts_recent_idx` (**new**) | `(-created_at, -id) WHERE deleted_at IS NULL AND NOT status='removed'` |

The GIN index on `search_vector` arrives in Part 12.

**Migration.**
1. Run `makemigrations posts`, then normalise the file with ruff.
2. Review the SQL with `python manage.py sqlmigrate posts 0001`.
3. Stop if any constraint compiles differently from the rules above.

### Validators (`apps/posts/validators.py`)
These are pure functions with no I/O and no DRF; they raise Django `ValidationError`s with codes. One
algorithm is used on **both** sides, and the frontend mirrors it step for step. The frontend must not
lean on `new URL()`, which turns `\` into `/`, decodes `%xx` in hosts and accepts `https:example.com`.

**`normalize_source(value) -> str`:**
1. **Input checks.**
   - Not a string → `invalid_source`.
   - Trim **ASCII** whitespace only (`" \t\r\n"`; JS `trim()` and Python `strip()` disagree on
     other characters).
   - Empty → `empty_source`.
   - More than 2,000 characters → `source_too_long`, before any work.
2. **Characters.** Any character in category Cc, Cf, Cs, Zs, Zl or Zp, or any `\`, →
   `invalid_source`.
   - Lone surrogates (Cs) would otherwise crash the encoder.
   - Cf covers the bidi controls.
3. **DOI.**
   - A `doi:` prefix (any case, optional spaces after it) is stripped. The rest **must** be a DOI,
     else `invalid_doi`.
   - The prefixes `http(s)://doi.org/` and `http(s)://dx.doi.org/` (any case) are tried as a DOI.
     If what remains isn't a DOI, the input is handled as an ordinary URL.
   - Bare text starting with `10.` must be a DOI, else `invalid_doi`.
   - The pattern is `re.compile(r"10\.[0-9]{4,9}/[-._;()/:A-Za-z0-9]+").fullmatch`, with no
     `IGNORECASE`. `[0-9]` instead of `\d` keeps out Unicode digits; `fullmatch` instead of `$`
     refuses a trailing newline; and no `IGNORECASE` keeps out the Kelvin sign and long s.
   - The DOI is stored bare, with its case kept.
4. **URL split.** Use the RFC 3986 appendix B regex
   `^([A-Za-z][A-Za-z0-9+.-]*):(//([^/?#]*))?([^?#]*)(\?[^#]*)?(#.*)?$` on both sides, not
   `urlsplit`. This gives an identical split in both languages.
   - The scheme, lowercased, must be `http` or `https`. `javascript:`, `data:`, `ftp:` and a bare
     `example.com` → `invalid_source` ("Use a link that starts with https://, or a DOI such as
     10.1000/xyz").
   - The `//authority` part is required.
   - `@` in the authority means credentials → `invalid_source`.
   - The port must be 1–65535 in ASCII digits. `:80` is dropped for http and `:443` for https.
5. **Host.**
   - `%`, `[` and `]` are refused (encoded hosts, IPv6).
   - An ASCII host is lowercased. A non-ASCII host goes through `idna.encode(host, uts46=True)`; on
     the client, through `new URL("http://" + host + "/").hostname`, used **only** for punycode.
     Catch `idna.IDNAError` and `UnicodeError`.
   - Every label must match `^[a-z0-9_](?:[a-z0-9_-]{0,61}[a-z0-9_])?$`.
   - An `xn--` label must decode (`idna.decode`) to reject fake A-labels.
   - At least two labels; at most 253 characters.
   - The host must not be `localhost` or `*.localhost`.
   - It must not "end in a number": a last label matching `[0-9]+` or `0x[0-9a-f]*` is refused.
     WHATWG reads `127.1`, `0x7f.1` and `1.2.3.4` as IPv4.
   - An empty label (`a..b`, trailing dot) is refused.
   - Errors give `invalid_source` with a specific message where it helps ("IP addresses and
     localhost aren't allowed").
6. **Rebuild** as `scheme://host[:port]`, then the path (or `/` when empty), then the query and
   fragment exactly as typed. Only non-ASCII characters are percent-encoded: UTF-8 with uppercase
   hex, which Python's `quote(ch, safe="")` and JS's `encodeURIComponent(ch)` produce identically.
7. **Length.** Over 500 characters after normalising → `source_too_long`. Punycode and
   percent-encoding make values longer.

The function is idempotent: normalising a normalised value gives it back.

**Other helpers:**
- `source_kind(value)`: `doi` when the value starts with `10.`, else `url`.
- `validate_sources(values) -> list[str]`:
  - Checks every element and collects **all** per-index errors into
    `ValidationError({"1": [ValidationError(msg, code=…)]})`.
  - Then checks for duplicates. URLs must match exactly after normalising; DOIs compare
    case-insensitively. A duplicate gets `duplicate_source` on the **later** index ("Same as
    source 1").
  - Order is kept.
  - The "too many" check happens in the serializer field, first.

### Emergency rule (`apps/posts/emergency.py`)
`is_active_emergency(post, now)` is the pure function from §4.
- It lives here and not in `apps/pipeline/routing.py`, because `apps/pipeline` doesn't exist until
  Part 9, and creating the folder now would make Part 9's `startapp` refuse it. Part 9's
  `routing.py` imports it.
- The serializer uses it for `emergency_active`, which is always false in Part 4.
- ARCHITECTURE §4 and STRUCTURE are updated to match.

### Services (`apps/posts/services.py`)
**Constants and domain errors.** `FACT_QUOTA_WINDOW = timedelta(hours=24)`. The domain errors
carry no HTTP details:
- `EmergencyUnavailable`
- `FactQuotaExceeded(next_slot_at)`
- `FactPostsPaused`

**`fact_quota(user, *, now)`** returns `FactQuota(limit, used, remaining, next_slot_at)`:
- **`used`** counts the user's fact posts with `created_at > now − 24 h`, **deleted and removed
  ones included**. A post exactly 24 h old no longer counts.
- **`remaining`** is `max(limit − used, 0)`.
- **`next_slot_at`** is set only when nothing is left and `limit > 0`: the `created_at` of the
  `(used − limit + 1)`-th oldest counted post, plus 24 h. That is right even after the limit is
  lowered.
- It runs at most two queries.

**`create_post(*, author, content, post_type, sources=(), is_emergency=False, now=None)`:**
1. `is_emergency` → `EmergencyUnavailable` first, even on an opinion, before anything is written.
2. An opinion with sources → `ValidationError({"sources": …})`, a safety net behind the serializer.
3. Then, inside `transaction.atomic()`:
   - **Fact:**
     1. `_lock_author()`, i.e. `User.objects.select_for_update().only("pk").get(pk=…)`.
     2. Read `get_platform_settings().fact_posts_per_day`.
     3. A limit of 0 → `FactPostsPaused`.
     4. `_fact_posts_in_window()`.
     5. Nothing left → `FactQuotaExceeded`.
     6. Status `pending`.

     Under READ COMMITTED, a second request counts only after it gets the lock, so it sees the
     first one's insert.
   - **Opinion:** status `published`.
   - `Post.objects.create(..., created_at=now)`.

There is no pipeline kick; that is Part 9. `_lock_author` and `_fact_posts_in_window` are separate
functions so the race test can widen the window.

### API
**`apps/accounts/serializers.py`**: add `UserSummarySerializer` `{id, username, display_name,
avatar_url}`, reusing `avatar_url()`. Part 7B reuses it for `reposted_by`.

**`apps/posts/serializers.py`:**
- **`SourcesField`** (custom field):
  - not a list → error;
  - more than 5 → `too_many_sources` on the list itself, with no element errors (DRF's
    `ListField` would check the elements first);
  - otherwise `validate_sources`.

  DRF keeps the Django error's dict and codes. On the wire it becomes `{"sources": ["…"]}` or
  `{"sources": {"1": ["…"]}}`. The codes are not on the wire: the Part 0 handler sends messages
  only for validation errors, and stays unchanged. Tests read the codes with `get_codes()`. §4c's
  wording is corrected.
- **`PostCreateSerializer`:**
  - `content`: DRF's `CharField` trims and refuses NUL and surrogates. 1–500 code points. Messages
    "Write something first." and "Keep it to 500 characters."
  - `post_type`: a required choice ("Choose Opinion or Fact.").
  - `sources`: refused on an opinion ("Only fact posts can have sources.").
  - `is_emergency`: optional boolean.
  - Undeclared fields (`status`, `author`, `created_at`, `confidence_score`) are ignored.
- **`PostSerializer`**: exactly the 24 keys of the §9 object.
  - `author` uses `UserSummarySerializer`.
  - `sources` is `[{value, kind}]`.
  - `emergency_active` comes from one `now` in the serializer context.
  - `confidence_score` is `"94.00"` only for `verified_*` with `verdict_source=pipeline`, else null.
  - The counts are 0 and the `*_by_me` flags false.
  - `is_mine` = `user.is_authenticated and post.author_id == user.pk`.
  - `can_appeal` is false and `appeal_status` null.
  - Nothing else leaks: no `flagged_reason`, pipeline fields, `report_count` or moderation fields.
- **`FactQuotaSerializer`**: `{limit, used, remaining, window_hours: 24, next_slot_at}`.
  Part 11C adds `emergency`.

**`apps/posts/exceptions.py`**: `APIException` subclasses, so the core handler shapes them as
`{detail, code}`. DRF adds `Retry-After` for any exception with a `wait` attribute
(`rest_framework/views.py`, `exception_handler`).

| Exception | Status | Code | Notes |
|---|---|---|---|
| `EmergencyUnavailableError` | 400 | `emergency_unavailable` | |
| `FactQuotaExceededError` | 429 | `fact_quota_exceeded` | `wait = max(1, ceil(seconds))`. Not a `Throttled` subclass, which would append "Expected available in…". Detail: "You've used your {limit} fact posts for the last 24 hours. You can post another fact at {time UTC}." |
| `FactPostsPausedError` | 403 | `fact_posts_paused` | |

**`apps/posts/pagination.py` (`FeedPagination`).**
- It subclasses the core pagination with `ordering = ("-created_at", "-id")`, and answers
  `{pinned: [], pinned_total: 0, results, next_cursor}`.
- **It validates the cursor position:** `parse_datetime` must return a time-zone-aware value, else
  404 `not_found`.
  - Found in review: a crafted `p=garbage` cursor reaches `created_at__lt='garbage'`, and Django's
    `ValidationError` becomes a 500.
- DRF filters on the first key and counts ties with an offset, so equal timestamps neither repeat
  nor vanish.
  - The exception is a whole page sharing one timestamp, where DRF falls back to a plain offset.
    That can't happen with microsecond timestamps, but tests must give posts distinct times.

**`apps/posts/views.py`** (`APIView`s with `never_cache`):
- **`PostListView`** at `/api/v1/posts/`:
  - **`get_permissions()`:** `AllowAny` for GET; `IsAuthenticated` and `IsEmailVerified` for POST.
  - **`get_throttles()`:** `ScopedRateThrottle` (`throttle_scope="post_create"`) for POST only.
    DRF runs throttles on every method, so without this, reading the feed would use up the posting
    allowance.
  - **Check order** (DRF's `initial`): authentication, then permissions (401 or 403), then the
    throttle (429 `throttled`), then validation (400), then the service (400, 403 or 429). So 401
    and 403 don't use the throttle, but 400s and quota refusals do. §3 says so.
  - **GET:** `Post.objects.visible().for_list()`, paginated by `FeedPagination`. Items are
    `{kind: "post", post, reposted_by: null, activity_at: post.created_at}`.
  - **POST:** validates, calls `create_post(now=now)` and maps the domain errors. Answers 201 with
    `PostSerializer`.
- **`FactQuotaView`** at `/api/v1/me/fact-quota/`: `IsAuthenticated`.
- **Query counts:** an anonymous GET is 1 query and an authenticated one is 2 (the user, then the
  page). DRF's cursor pagination runs no `COUNT`.

### Admin (`apps/posts/admin.py`)
Read-only until Part 10.
- `has_add_permission`, `has_change_permission` and `has_delete_permission` return False.
- List: excerpt, type, status, author, created and deleted dates.
- `list_select_related=("author",)` and `show_full_result_count=False`.
- Filters on type and status; search on content and `author__username`.

## Frontend

New files go in `src/features/posts/` unless noted. Tests sit next to them.

### Characters and sources
- **Code-point counting:** `src/lib/format.ts` gets `countCharacters(text)` =
  `Array.from(text).length`. `components/ui/Textarea.tsx` uses it for the counter and the
  over-limit state, with no `maxLength` attribute.
- **`sources.ts`** mirrors the server's algorithm (same constants and steps):
  - `normalizeSource(raw)` returns `{ok, value, kind}` or `{ok: false, message}`.
  - `checkSourceRows(rows)` returns:
    - an error per row (including "Same as source 1");
    - the list to send, with empty rows dropped;
    - a map from sent index to row, so the server's `sources.1` lands on the right row.
  - `sourceLabel()`: a URL shows its host, a DOI shows `doi.org/<doi>`.
  - `sourceHref()`: a DOI links to `https://doi.org/<doi>`; a value that doesn't start with
    `http(s)://` gets no link, as defence in depth.
- **Shared test vectors** live in one file, `backend/apps/posts/tests/source_vectors.json`. Pytest
  loads it, and Vitest reads it with `fs.readFileSync` (as `brand-guard.test.ts` reads files), so
  the two can't drift apart.
- **`SourceLink.tsx`** is the one-line row under a fact claim, in b1's drawer style:
  - container `rounded-lg border border-outline-variant/30 bg-surface-container-low`, with the
    `link` glyph in `text-outline`;
  - the first source's label as a link: `target="_blank"`, `rel="nofollow ugc noopener
    noreferrer"`, `truncate`, `title` = the full value, and an sr-only "(opens in a new tab)";
  - then "+N more" as plain text. Part 5 makes it a link.

### Cards and feed
- **`PostCard.tsx`:**
  - new optional `sources` prop; `SourceLink` appears under a fact claim that has sources;
  - the blank-name rule;
  - the 390 px header fix.

  **`PostCardSkeleton.tsx`** is the loading card, and **`post-card-props.ts`** has
  `toPostCardProps(post)`.
- **API calls:** `posts-api.ts` has `createPost`, `fetchRecentFeed(cursor?, signal?)` and
  `fetchFactQuota`, all through `api.*` (never `token: false`). `lib/api/types.ts` gets `FactQuota`
  and `CreatePostBody`.
- **`useCursorFeed.ts`** (generic; Part 6 reuses it):
  - it waits until the session leaves `loading`, otherwise the first request goes out without a
    token;
  - it reloads from the top when `user?.id` changes;
  - posts added by the composer are kept apart from the loaded pages, and the hook renders
    `dedupeById([...prepended, ...pages])`, so a post made while page 1 loads survives;
  - a second Load more is ignored while one runs;
  - a 404 on a cursor resets the feed;
  - the first page and Load more have separate errors.
- **`FeedList.tsx`:**
  - three skeleton cards while loading;
  - an error `Alert` with "Try again";
  - `EmptyState` ("No posts yet", glyph `forum`);
  - the cards;
  - `LoadMore` with `endLabel="You're caught up."` (b1's end-of-feed line);
  - a failed Load more keeps the list and shows an inline error.

### Composer
**`ComposerProvider.tsx`** (`useComposer`) **owns the draft and the request**:
- It holds the open state, the draft, the submit and the `onPosted` subscribers.
- `Modal` always lets Esc close it, and the relay can take up to 70 s. If someone closes the modal
  while a post is sending, the provider still finishes:
  - on success: toast, notify subscribers, clear the draft;
  - on failure: keep the draft and show an error toast.
- It clears the draft when `user?.id` changes.
- `open()` for an unverified user shows Part 2's toast. For an anonymous one it goes to
  `/login?next=<path>`.

**`ComposerModal.tsx`** is b2. The emergency toggle stays out until 11C.
- **Text:** `Textarea variant="bare" maxCount={500}`, label "Post text", `data-autofocus`.
- **Post type:** a `SegmentedControl` with Opinion (`format_quote`) and Fact (`fact_check`).
  Nothing is chosen at first, with the hint "Choose one to continue".
- **`SourceFields.tsx`, Fact only:**
  - "Source (URL or DOI) (optional)" with the "DOI preferred" hint (`check_circle`,
    `text-secondary`);
  - one `TextField mono leadingIcon="link"` row to start;
  - "Add another source" (ghost, `add`) until there are 5 rows;
  - an icon button "Remove source N" on rows 2–5; focus moves sensibly after a removal;
  - each row is checked on blur and on submit.
- **Footer:**
  - The quota line (`quota.ts`) comes from `GET /api/v1/me/fact-quota/`. It is fetched when the
    modal opens and again after a fact post or a quota error. It reads:
    - normally: "7/10 fact posts left";
    - at 0: "0/10 fact posts left · next at 14:05" (local time), in the error tone;
    - at limit 0: "Fact posts are paused right now";
    - hidden if the fetch fails (the server still decides).
  - Cancel (ghost) and Submit (`loading` while posting).
- **Submit:**
  - it validates everything and focuses the first problem;
  - empty rows are dropped, keeping order;
  - the body is `{content, post_type, sources}`.
- **Unverified:** a warning `Alert` ("Verify your email to post…") and the form disabled.
- **Errors** (copy in `messages.ts`; the composer checks the code before the status, because the
  auth `bannerMessage` turns every 429 into generic text):
  - **Field errors** appear under their fields: `content`, `post_type`, `sources`, and
    `sources.N` on its row.
  - **Banner errors:**
    - `fact_quota_exceeded`, and the quota reloads;
    - `fact_posts_paused`;
    - `throttled`, with `retryAfter`;
    - `email_unverified`, which reloads `/me` and shows the verify state;
    - `backend_waking`: "…If it doesn't appear in Recent, try again.";
    - `network_error`;
    - anything else.

**`(app)/layout.tsx`:**
- It becomes `<ComposerProvider><Shell/></ComposerProvider>`.
- The inner `Shell` passes `onNewPost` to `AppShell`, which stays presentational.
- This closes a 0C follow-up.

### `/home`
- **`app/(app)/home/page.tsx`** stays a thin server file. Its metadata title stays "Home"
  (`e2e/smoke.spec.ts` expects "Home · Rumor Zero"). It renders **`HomeFeed.tsx`** (client).
- **`HomeFeed.tsx`:**
  - a `max-w-reading` page with an sr-only `<h1>Home</h1>`;
  - `Tabs` with one tab, "Recent" (Following is Part 6);
  - **`ComposerTrigger.tsx`**, which replaces b1's inline composer: the `edit_note` tile and a
    placeholder-style button, "What do you want to say?";
  - `FeedList`;
  - it subscribes to `onPosted` and adds the new post to the top.
- **`ComposerTrigger.tsx`** follows the entry-point rule above. A verified user opens the
  composer; while the session loads, it shows a skeleton.

### E2E
- **`e2e/helpers.ts`** gets `signUpVerified(page, prefix)`:
  1. `signUp(..., {stay: true})`;
  2. `waitForEmailLink()` and go to the link;
  3. wait for "Your email is verified";
  4. go to `/home`.
- **New `e2e/posts.spec.ts`:**
  1. **Fact post with two sources:**
     - Sign up verified, then open New post from the rail at 1280 px.
     - Enter text with a unique marker and choose Fact.
     - Fill row 1 with `doi:10.1000/rz<id>`, click "Add another source", fill row 2 with
       `https://example.org/<id>`, and submit.
     - The card holding the marker shows "CHECKING FACTS…" and `doi.org/10.1000/rz<id>` with
       "+1 more".
     - Reload the page and check the same again.
  2. **Opinion:** the card shows the OPINION chip, italic text and no source line.
- Assertions are scoped to the card that holds the marker: tests run fully in parallel and the feed
  is global. Never assert "10" in the quota line: the E2E backend uses your `.env` seed.

## Tests

Every acceptance criterion (AC1–AC8 in task.md order) and every "Required tests" item maps to at
least one test.

**Backend** (`apps/posts/tests/`):
- **`factories.py`**: `PostFactory` with traits `fact`, `verified_pipeline`, `moderator_verdict`,
  `under_review`, `removed`, `deleted`; the author is verified.
- **`conftest.py`** has:
  - `verified_user`;
  - `auth_client(user)`, using `access_token_for` imported from the accounts conftest, as other
    tests already do;
  - `fact_limit(n)`, which **saves** `PlatformSettings` and so clears the cache. The seed comes from
    your `.env`, so tests must pin it; `.update()` would skip clearing the cache.

  `run_together` moves from `test_tokens.py` into `apps/accounts/tests/conftest.py`.
- Service tests pass `now=`. API tests place earlier posts at `timezone.now() − Δ`, because the
  `clock` fixture moves only `time.time`.
- **`test_models.py`** (AC6):
  - one `IntegrityError` test per check, asserting `e.value.__cause__.diag.constraint_name`:
    - an opinion that is `verified_true`, `verified_false` or `pending`;
    - a fact that is `published`;
    - an opinion with sources;
    - 6 sources;
    - an empty source (`[""]`) and a NULL source;
    - an emergency opinion;
    - an expiry without `is_emergency`, and the reverse;
    - content `""` and 501 characters;
    - confidence −1 and 100.01;
    - an unknown enum value;
  - valid combinations pass, and 500 emoji pass;
  - every index exists (introspection).
- **`test_validators.py`** (AC7), driven by `source_vectors.json`:
  - **Accepted and normalised:**
    - case in scheme and host;
    - `:80`/`:443` dropped, `:8080` kept;
    - an empty path becomes `/`;
    - query and fragment kept;
    - a non-ASCII path is percent-encoded.
  - **IDN:**
    - `faß.de` → `xn--fa-hia.de`;
    - `bücher.example`;
    - full-width letters;
    - an uppercase `XN--` label;
    - underscores;
    - `ab--cd`.
  - **DOIs:** `doi:`, `DOI: `, `https://doi.org/` and `http://dx.doi.org/` all give the bare
    `10.1000/xyz`; a doi.org URL with a query stays a URL.
  - **Rejected:**
    - `javascript:`, `data:`, `ftp:`, `https:example.com`, no scheme;
    - `user:pw@` and `user@`;
    - `127.0.0.1`, `127.1`, `0x7f.1`, `2130706433`, `[::1]`;
    - `localhost`, `a.localhost`, full-width `localhost`;
    - a dotless host, `a..b`, a trailing dot, `-a.com`, a 64-character label, a fake `xn--` label;
    - `%` in the host, `\`, inner whitespace, a control character, U+202E, a lone surrogate;
    - a bad port;
    - over 500 characters after punycode;
    - the DOIs `10.12/x` and `10.12345/`, Unicode digits, a Kelvin sign, `doi:abc`.
  - **Idempotency**, and `source_kind`.
  - **List rules:**
    - 0 and 5 sources pass;
    - 6 gives only `too_many_sources` (`get_codes`);
    - a duplicate across kinds (`doi:` against `doi.org`), DOI case, and `HTTPS://Example.com`
      against `https://example.com/` → `duplicate_source` on the later index;
    - several bad indexes at once;
    - order kept;
    - non-string elements.
- **`test_emergency.py`**: the `is_active_emergency` truth table, including expiry at the exact
  second.
- **`test_services.py`** (AC1, AC4):
  - status by type; `created_at == now`; sources stored in order;
  - an opinion with sources is refused; an emergency is refused even with room left;
  - the quota:
    - the 10th fact post passes and the 11th raises with the right `next_slot_at`;
    - the window boundary: exactly 24 h no longer counts, 24 h − 1 µs does;
    - deleted and removed posts count; opinions and other users' posts don't;
    - the kill switch;
    - a lowered limit gives the right `next_slot_at`;
  - "FOR UPDATE" appears in the SQL for `accounts_user` (`CaptureQueriesContext`);
  - **threaded**, `transaction=True`, with the settings cache warmed in the main thread: at 9/10,
    exactly one of two simultaneous fact posts succeeds. A control run without the lock lets both
    through.
- **`test_api_create.py`** (AC1–AC4, AC7):
  - **201 responses:** an opinion and a fact, with exactly the 24 keys and the defaults.
  - **Auth:** anonymous → 401; unverified → 403 `email_unverified`, with no row (AC2).
  - **Validation:** a missing or unknown type, empty, whitespace-only and 501-code-point content →
    400 on the field (AC3). The wire shapes `{"sources": {"1": […]}}` and `{"sources": […]}`. An
    opinion with sources → 400.
  - **Business errors:**
    - `is_emergency: true` → 400 `emergency_unavailable`;
    - the 11th fact post → 429 `fact_quota_exceeded` with `Retry-After` (AC4);
    - paused → 403 `fact_posts_paused`.
  - **Throttle:** 30 real POSTs, then 429 `throttled`. A run of 40 GETs first doesn't use it up.
  - **Mass assignment:** the ignored fields are ignored.
- **`test_api_feed.py`** (AC5):
  - The anonymous shape: `pinned: []`, `pinned_total: 0`, the item shape.
  - Order: newest first, ties broken by id.
  - Removed and deleted posts are left out; every other status is included.
  - The `confidence_score` rule and `is_mine` for each viewer.
  - **Cursor stability:** 45 posts with distinct times; after page 1, 5 newer posts arrive; pages 2
    and 3 give exactly the original 45 with no repeats. A post removed between pages skips nothing
    else. 3 equal timestamps across a `page_size=2` boundary neither repeat nor go missing.
  - A bad cursor and a crafted `p=garbage` or naive position → 404.
  - `Cache-Control` has `no-store`.
  - **Query count:** the same for 5 and 20 posts with 5 sources each; 1 anonymous and 2
    authenticated.
- **`test_api_quota.py`**: 401 when anonymous; the shape and the counts before and after posting.
- **`test_no_network.py`** (AC8):
  - `socket.socket.connect`, `socket.create_connection`, `socket.getaddrinfo`,
    `urllib.request.urlopen` and `requests.Session.request` are patched to record and raise; a fact
    post with URL, IDN and DOI sources → 201, and nothing was called (psycopg uses libpq's own
    sockets);
  - plus a static check: no `apps/posts/*.py` file imports `urllib.request`, `requests`, `httpx`,
    `socket` or `http.client`.
- **`test_admin.py`**: the model is registered, the changelist renders, and add, change and delete
  are refused.

**Frontend** (Vitest + RTL):
- **`format.test.ts`**, **`Textarea.test.tsx`**: an emoji counts as 1.
- **`sources.test.ts`** (AC7, client side): the shared vectors, duplicates, the index map, labels
  and hrefs.
- **`SourceLink.test.tsx`:**
  - the host or `doi.org/…` label;
  - "+N more" only with 2 or more sources;
  - the exact `rel` and `target`;
  - a DOI's href;
  - no link for a non-http value.
- **`PostCard.test.tsx`** (AC1; the existing variant tests stay): the source line on facts with
  sources only (none on opinions or the tombstone); the blank name. **`post-card-props.test.ts`**.
- **`useCursorFeed.test.ts`**, **`FeedList.test.tsx`** (AC5):
  - waits for the session;
  - Load more sends the cursor and appends; the end label shows when `next_cursor` is null;
  - a double click loads once;
  - a prepend survives page 1 arriving, and a prepended post is not repeated;
  - error then retry;
  - a cursor 404 resets the feed;
  - a reload when the user changes;
  - the skeleton and empty states.
- **`ComposerModal.test.tsx`** (AC2–AC4, AC7):
  - **Blocked before any API call:** no type, empty, whitespace-only, 501 emoji. The errors show,
    and the first invalid control gets focus.
  - **Source rows:**
    - shown only for Fact;
    - add up to 5 rows, then the button disappears; remove only on extra rows;
    - an empty middle row is dropped and order kept;
    - "Same as source 1", the invalid-row messages and the "DOI preferred" hint;
    - the server's `sources.1` lands on row 3.
  - **Quota line:** at 7, at 0 with the time, and paused.
  - **Error responses:**
    - a 429 `fact_quota_exceeded` reloads the quota (AC4);
    - an unverified user or a 403 → the verify state (AC2);
    - `throttled`, `backend_waking` and network messages.
  - The submitting state.
- **`ComposerProvider.test.tsx`:**
  - success → toast and subscribers notified;
  - the draft is kept after closing, and cleared after success and when the user changes;
  - closing during a send still delivers the result.
- **`ComposerTrigger.test.tsx`**, **`HomeFeed.test.tsx`**: the three trigger states; a new post is
  added at the top.
- **`app/(app)/layout.test.tsx`**: New post opens the dialog from the rail and from the phone tab.

**E2E:** `posts.spec.ts` (AC1, plus the required E2E). The existing 15 tests must still pass.

## Files expected to change
- **New, backend:** `apps/posts/` (`apps.py`, `models.py`, `emergency.py`, `validators.py`,
  `services.py`, `exceptions.py`, `serializers.py`, `pagination.py`, `views.py`, `urls.py`,
  `admin.py`, `migrations/0001_initial.py`, `tests/` with the files above and
  `source_vectors.json`).
- **Changed, backend:** `rumor_zero/settings.py`, `rumor_zero/urls.py`, `requirements.txt`,
  `apps/accounts/serializers.py` (`UserSummarySerializer`), `apps/accounts/tests/conftest.py` and
  `test_tokens.py` (`run_together` moves), `backend/.env.example` (the `FACT_POSTS_PER_DAY` comment
  says "per rolling 24 h").
- **New, frontend** (`features/posts/`): `sources.ts`, `SourceLink.tsx`, `PostCardSkeleton.tsx`,
  `post-card-props.ts`, `posts-api.ts`, `useCursorFeed.ts`, `FeedList.tsx`, `quota.ts`,
  `messages.ts`, `SourceFields.tsx`, `ComposerModal.tsx`, `ComposerProvider.tsx`,
  `ComposerTrigger.tsx`, `HomeFeed.tsx`, plus tests. Also `e2e/posts.spec.ts`.
- **Changed, frontend:** `lib/format.ts`, `components/ui/Textarea.tsx`, `features/posts/PostCard.tsx`,
  `lib/api/types.ts`, `app/(app)/layout.tsx`, `app/(app)/home/page.tsx`, `e2e/helpers.ts`, and
  their tests.
- **Docs:**
  - **ARCHITECTURE:**
    - §2: the Recent index, the index names, the `author` index note, the home of
      `is_active_emergency`.
    - §3: the quota is a rolling 24 h window that counts deleted and removed posts;
      `post_create` applies to POST only and counts refused attempts.
    - §4: where `is_active_emergency` lives.
    - §4c: the normalisation algorithm, `idna` UTS #46, the host rules, and that the error codes
      exist only inside the server.
    - §9: the POST body and the 201, the fact-quota payload, the feed order and the cursor 404,
      `emergency_unavailable`, `fact_quota_exceeded`, `fact_posts_paused`.
    - §10: `ComposerProvider`, `HomeFeed`, `useCursorFeed`, code-point counting, the blank-name
      rule.
  - **ANALYSIS:** D7 and the b-3 quota row ("rolling 24 h", your decision of 2026-10-08).
  - **SETUP:** an `idna` row in B1.
  - **ENV_GUIDE:** the meaning of `FACT_POSTS_PER_DAY`.
  - **STRUCTURE:** the posts files and the `routing.py` note.
  - **`task.md`:** both status spots and the deviations: insert on success, the quota wording, the
    403 when paused.
  - **HANDOFF.**
  - **MEMORY**, for durable facts:
    - a combined GET+POST view needs `get_permissions`/`get_throttles`;
    - the DRF cursor position must be validated, and a page of equal timestamps falls back to a
      plain offset;
    - the throttle `timer` and rates are bound at import;
    - `idna` 3.20 checks ASCII labels strictly, and `transitional` is ignored;
    - the platform-settings seed comes from your `.env`.
  - **`docs/test-command.md`:** a `### Part 4` section in **both** guides (Linux first; PowerShell
    sends JSON through files). Steps:
    1. migrate;
    2. sign up and verify through the file inbox;
    3. a 403 for an unverified post (`curl`);
    4. an opinion and a fact with two sources (201 bodies);
    5. a per-index source error and a `javascript:` source;
    6. `GET /api/v1/me/fact-quota/`;
    7. `GET /api/v1/posts/` and its cursor;
    8. a constraint demo in the shell, rolled back;
    9. the browser: composer, quota line, feed, Load more.

## Ordered steps
1. **Setup.**
   - The plan is already saved here (2026-10-08). Set HANDOFF to "Part 4 in progress".
   - Check that `git status` shows only what HANDOFF lists (or a clean tree once you have committed
     the plan) and that `docker compose ps` shows both containers up.
2. **App and settings.** The settings, the `idna` pin, `startapp posts` with a `tests/` package, the
   URLs, then `pip install -r requirements-dev.txt`.
3. **Model.**
   1. The model, then `makemigrations posts` and ruff.
   2. `sqlmigrate` review (a stop condition).
   3. `migrate`.
   4. `test_models.py`.
4. **Validators.**
   - `validators.py`, `source_vectors.json` and `test_validators.py`.
   - `emergency.py` and its test.
5. **Services.** Move `run_together`, then write `services.py` and `test_services.py`, including
   the race test.
6. **API.**
   1. `UserSummarySerializer`, the exceptions, serializers, pagination, views, URLs and admin.
   2. The API, no-network and admin tests.
   3. The full backend suite, ruff, `makemigrations --check` and `check`.
7. **Frontend**, testing each piece as it is written:
   1. `countCharacters` and `Textarea`.
   2. `sources.ts` (using the shared vectors).
   3. `SourceLink`.
   4. `PostCard`, its skeleton and the mapper.
   5. `posts-api.ts` and the types.
   6. `useCursorFeed` and `FeedList`.
   7. `quota.ts`, `messages.ts`, `SourceFields`, `ComposerModal` and `ComposerProvider`.
   8. The layout wiring.
   9. `ComposerTrigger`, `HomeFeed` and the route.
8. **E2E.** The helper and `posts.spec.ts`. Run E2E in dev mode, then
   `NEXT_PUBLIC_GOOGLE_CLIENT_ID= npm run build` and `CI=1 npm run test:e2e`.
9. **Browser check** against Stitch b1 and b2 at 1280 and 390 px, with 0 px horizontal overflow and
   the composer at 390 px.
10. **Docs.** Update the docs listed above, and run the new test-command section's Linux blocks
    exactly as written. Update `task.md` and HANDOFF, then stop.

## Validation (exact commands; record the results in HANDOFF)
- **Backend** (`backend/`, venv active, containers up):
  - `python -m pytest`
  - `ruff check .`
  - `ruff format --check .`
  - `python manage.py makemigrations --check --dry-run`
  - `python manage.py check`
- **Frontend** (`frontend/`):
  - `npm run lint`
  - `npm run lint:tokens`
  - `npm run typecheck`
  - `npm run format:check`
  - `npm test`
  - `npm run build`
  - `npm run test:e2e`
  - `NEXT_PUBLIC_GOOGLE_CLIENT_ID= npm run build`, then `CI=1 npm run test:e2e`
- **Manual:** the new section's Linux blocks, run as written, and screenshots next to Stitch b1 and
  b2.

## Stop conditions (stop, record in HANDOFF, ask)
- `sqlmigrate` shows a constraint that compiles differently from the rules above.
- A schema change beyond §2 plus the Recent index looks necessary.
- A change to Parts 0–3 beyond these is needed:
  - `Textarea.tsx` and `format.ts`;
  - `(app)/layout.tsx`;
  - `UserSummarySerializer`;
  - moving `run_together`;
  - the two apps added to settings.
- A dependency, service or env variable other than the `idna` pin seems needed.
- `idna` and the client mirror disagree on a shared vector, and neither can be fixed without
  changing a rule above.
- Anything would touch `design/`, a real env file, or a git command that changes state.
- A required test, lint, type check, `makemigrations --check` or build still fails and the fix
  would change a decision above.

## Non-goals (later parts)
- Post detail, delete and status polling (Part 5).
- The Following tab and profiles (6).
- Likes, comments and real counts (7).
- Reposts and bookmarks (7B).
- Reports (8).
- The pipeline and its inline kick (9): fact posts stay `pending`.
- Moderation actions in the admin (10).
- Appeals (11).
- Emergency posts and the pinned list (11C).
- `search_vector` (12).
- Caching Recent, refreshing the feed automatically, infinite scroll.
- A DOI title lookup (an ANALYSIS f-3 follow-up).

## Follow-ups to record (not in this part)
- **Part 16:** an idempotency key for `POST /api/v1/posts/`. A relay timeout (503
  `backend_waking`) after Django has already saved the post means a retry creates a duplicate. The
  composer's message mentions it.
- **Part 16:** the core `CursorPagination` lets any crafted position reach the filter. Part 4
  guards `FeedPagination`; other lists that use the core class need the same guard.
- **Part 9:** `routing.py` imports `is_active_emergency` from `apps/posts/emergency.py`.
- **Part 11C:** the emergency toggle in the composer, the `emergency` block in fact-quota, and
  `pinned`.
