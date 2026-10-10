# Plan: Part 9, Fact-check pipeline stub + routing

- **Status:** APPROVED by the user (Sanjoy Rozario) on 2026-10-11, together with the two decisions and the defaults
  below. Saved here and linked from `HANDOFF.md`. Not implemented yet. Drafted 2026-10-10/11 by Claude (Opus 5.5).
  Step 0's "save the plan" is done; its HANDOFF and workspace checks still run at the start of implementation.
- **Implement with:** Opus 5.5 · high (task.md).
- **Evidence (read-only):**
  - Docs: HANDOFF, MEMORY, `task.md` Part 9 (+ the Part 8 record), ARCHITECTURE §1–§4b, §6, §9–§13, ANALYSIS c-3, c-5,
    c-6, c-21, c-27 and c-40, STRUCTURE, ENV_GUIDE (§2.12 and the Render start command), `backend/.env.example`, and the
    Part 8 plan's appendix (A1/A2).
  - Code: the files cited below.
  - Two Explore passes: frontend verdict copy, polling and the E2E suite; backend test helpers.
  - A Plan-agent design review, run **before** approval this time. Its findings are folded in below, marked "(review)".

## Context

Part 9 gives fact posts a verdict. It builds:
- a fixed pipeline contract;
- a deterministic stub;
- the routing of a result into the post's status (ARCHITECTURE §4, ANALYSIS c-3);
- a database-backed queue that runs without Celery or a worker (c-21). It has three triggers: an inline kick after the
  post commits, an hourly secret-protected tick, and a management command for local dev.

The VERIFIED, FALSE and UNDER REVIEW badges built in Parts 4–5 then show real states.

**Dependency check (2026-10-10).** Part 9 depends only on **Part 8** (`[x] Done (2026-10-10)`). Its whole chain is
Done: 5, 4, 1, 0C and 0A/0B/0D, plus 2, 3, 6, 7 and 7B. Still open but not blocking: Part 3 criterion 4 (the
real-Google check), and CI for Parts 2 to 8, which hasn't been reported yet.

**Workspace:**
- HEAD is `0d8c331` ("Implemented Part 8…") and the tree is clean.
- Docker Postgres and Redis are healthy, and ports 3000 and 8000 are free.
- HANDOFF still calls Part 8 "uncommitted" (the user has committed it); step 0 fixes that text.

**Already in place:**
- **Post columns and index (Part 4):** `Post` has every pipeline column. The partial index `posts_pending_queue_idx`
  covers `(-is_emergency, created_at) WHERE fact AND pending AND deleted_at IS NULL`.
- **The `apps/pipeline/` app (Part 8, made with `startapp`):** it holds only `apps.py` and `routing.py`. `routing.py`
  has `merge_flag`, `enter_review` and `apply_report_threshold`, covered by 45 tests. `posts.services.record_report`
  is the model to follow: the service owns the write, and the pure function decides.
- **Env vars without settings:** `backend/.env.example` and ENV_GUIDE already list `PIPELINE_BACKEND=stub`,
  `PIPELINE_INLINE_KICK=True`, `PIPELINE_URL` and `PIPELINE_API_KEY`, but **`settings.py` reads none of them**.
- **Cron secret:** `INTERNAL_CRON_SECRET` is required at startup. `DeepHealthView` already checks `X-RZ-Cron-Secret`
  with `hmac.compare_digest` (`apps/core/views.py:50-73`), and Sentry already scrubs the header.
- **Confidence threshold:** `PlatformSettings.confidence_threshold` (0–100, seeded at 85), read through
  `get_platform_settings()`, which has a 60 s cache.
- **Outbound HTTP:** `apps/accounts/turnstile.py` uses the standard library "so no HTTP client dependency is added".
  The root `conftest._hermetic` blocks its network access.
- **Time limits:** production runs `gunicorn --workers 2 --threads 4 --timeout 60`, and gthread never kills a long
  request (review). cron-job.org gives the tick 30 s.
- **Frontend copy and polling (Part 5):** `VerdictBlock.explain` already words each `verdict_source` ("Checked
  automatically · 95% confidence" / "Reviewed by a moderator"). The polling overlay carries `status`,
  `confidence_score` and `verdict_source` to both cards and the page.

## Your decisions (2026-10-11)

1. **A decisive FALSE that arrives while the post is already under review for reports goes to a moderator.** The
   post stays UNDER REVIEW and its reason becomes `both`. `pre_review_status` stays `pending`, so a moderator must
   mark the post FALSE or verified.
   - What this gives: no hidden FALSE label is ever stored, so nothing can reveal one, Part 8's repost refusal
     included (appendix A2). Dismiss reports can never turn a post FALSE on its own.
   - A late decisive **TRUE** still follows the docs: `pre_review_status=verified_true` and
     `verdict_source=pipeline`, and Dismiss restores VERIFIED.
   - This changes §4's row "under_review (reports), late decisive result". §4's emergency row 331 already used this
     rule; it is now the general rule.
2. **The stub in production is recorded as a launch blocker for Part 17; nothing changes now.** The stub is built
   exactly as §6 says. Before any deploy, Part 17 must decide how production gets verdicts: a real pipeline, or a mode
   that applies no automatic labels. With the stub, any author can write `#true` to get VERIFIED 95%, and about 15 % of
   untagged facts get a hash-chosen FALSE that would feed the public credibility score (11B). The blocker is recorded
   in ARCHITECTURE §6, `.env.example`, ENV_GUIDE, MEMORY and a one-line note in task.md Part 17.

## Scope

**In:**
- `apps/pipeline/{contract,clients,processor}.py`
- `routing.apply_pipeline_result` / `apply_pipeline_failure`, plus the "awaiting a check" predicate
- `posts.services.record_pipeline_result` / `record_pipeline_failure` (the status writes)
- the inline kick
- `manage.py process_pending`
- `POST /api/internal/tick/`
- the `PIPELINE_*` settings and their startup checks
- the `verdict_source` privacy rule
- the E2E changes, the tests and the docs

**Not in Part 9:**
- **Later parts:**
  - the emergency branch of `apply_pipeline_result`, and "active emergencies first" (11C; no emergency post exists
    before 11C);
  - notifications (13);
  - reputation events (11B);
  - moderator actions and the queue (10).
- **Not planned at all:**
  - a real pipeline service;
  - a migration;
  - any new dependency, service or env variable.

## What the research found (all handled below)

1. **The processor must not hold the post's row lock across the call, which can take 20 s** (MEMORY, Part 8). If it
   did, reports, reposts, deletes and moderator actions would queue behind it. Read literally, §6 would hold it.
   → A short **claim** with a **lease**, then the call outside any transaction, then a short **apply**.
2. **Reported pending facts must still be checked** (a Part 8 follow-up).
   - MEMORY's suggested condition, `pre_review_status='pending' AND pipeline_checked_at IS NULL`, would re-select a
     post the pipeline **gave up on** forever.
   - The exact condition is `under_review AND flagged_reason='reports' AND pre_review_status='pending'`. Every way a
     check can end changes either the flag or `pre_review_status`. The review confirmed this against every §4 row,
     Parts 10, 11 and 11C included.
3. **A second result can corrupt a finished post (review).** §4's pseudo-code writes the verdict fields before it
   checks the status, and `verdict_source` is still null after an inconclusive result or a give-up.
   - **How it happens:** a lease can run out mid-call. urllib's timeout applies to each socket operation, not to the
     whole call, and the DNS lookup has no timeout at all.
   - → One "awaiting a check" predicate, used both as the queue's `Q` and as the apply guard (in Python), plus a
     **claim token**: the `pipeline_attempts` value at claim time. A result whose token is stale is dropped.
4. **`verdict_source` is public on an under-review post.** A late TRUE on a reported post would tell everyone the
   pipeline had already decided. → It is public only when the status is `verified_*`, as `confidence_score` already is.
5. **Appendix A2** (a hidden FALSE revealed by the repost refusal) → closed by **Decision 1**. With finding 4 also
   fixed, the review found no other channel: profile counters, `status_at_repost`, the poll and the feeds.
6. **The tick has 30 s.** As drafted, it would process **0** posts on the HTTP backend: its 25 s budget minus a 25 s
   worst case left no room even for the first post (review).
   - → The **first claim is always allowed**, and the HTTP client enforces a total time limit.
   - With HTTP, the tick handles about 1–5 posts. The stub always handles 10.
7. **A kick that throws after the commit becomes a 500** on a post that is already saved (review). The client retries
   and creates a duplicate that uses up quota. → The callback catches everything itself.
8. **No HTTP dependency, but an existing guard to amend.** The client uses urllib, as Turnstile does.
   - `apps/reports/tests/test_no_network.py:51-63` refuses `urllib.request` and similar imports in **every** top-level
     `apps/pipeline/*.py`. → It names `pipeline/clients.py` as the one allowed module.
   - New tests pin that the client opens only `PIPELINE_URL`, and that processing a fact with sources through the stub
     touches no socket.
9. **Nothing turns the kick off in tests yet.** Two `transaction=True` tests create facts with on-commit callbacks
   running (`apps/posts/tests/test_services.py:241-259`). → `_hermetic` pins the kick off in the same step that adds
   the setting.
10. **The E2E backend must not check posts inline.**
    - Three tests expect a composer fact to stay CHECKING FACTS… after a reload or in a second tab:
      `e2e/posts.spec.ts:30`, and `e2e/post-detail.spec.ts:42` and `:143`.
    - A sweep is unsafe too. Parallel workers and earlier runs leave pending facts behind, and `social.spec.ts:294`
      needs its seeded fact to stay pending.
    - → The E2E servers and shell pin the kick off, and the E2E test processes **its own post only**.
11. **The copy per `verdict_source` already exists** (Part 5), and nothing in the UI reads `verdict_source` on an
    under-review post. → No production frontend change is planned.

## Design

### The "awaiting a check" predicate (`apps/pipeline/routing.py`)

- `awaiting_check_q()` (a `Q`) and `is_awaiting_check(post)` (its pure Python twin) are the **same** rule. A post
  qualifies if all of these hold:
  - it is a fact, with `deleted_at` null and `verdict_source` null;
  - it is either `pending`, or `under_review` with `flagged_reason='reports'` and `pre_review_status='pending'`.
- The queue uses `awaiting_check_q()` plus a "due" test (`pipeline_next_attempt_at` null or ≤ now). The apply guard
  uses `is_awaiting_check`. A table test proves that the two agree for every state §4 can produce.

### Contract (`apps/pipeline/contract.py`)

Frozen dataclasses, validated in `__post_init__`; a bad value raises `ContractError(ValueError)`.

- **`PipelineRequest(post_id: UUID, content: str, sources: tuple[str, ...] = ())`**
  - Content is 1–500 code points.
  - `sources` must be a tuple (a list is refused) of 0–5 non-empty strings of at most 500 characters each.
  - `for_post(post)` keeps the stored order, and `to_json()` produces `{post_id, content, sources}`.
- **`PipelineResult(verdict, confidence_score, raw_result)`**
  - `verdict` is exactly `"true"`, `"false"` or `"inconclusive"`.
  - The score may be a `Decimal`, an `int` or a numeric `str`. A `bool`, a float, NaN and infinity are all refused.
  - The range 0–100 is checked on the exact value, and the value is then quantized to 0.01 with `ROUND_HALF_UP`.
    Decisions compare the stored value.
  - `raw_result` must be a `dict`.
  - `from_json(payload)` needs an object with the three keys, ignores any others, and turns a JSON float into
    `Decimal(str(x))` first.

### Clients (`apps/pipeline/clients.py`)

`PipelineError(kind, detail)`:
- `kind` is one of `timeout`, `network`, `http_status`, `bad_response`, `contract` or `error`.
- `detail` is our own text, never a response body and never the key.
- Every client has a `max_seconds` attribute.

**`StubPipelineClient`** (`max_seconds = 0`) is deterministic and ignores `sources`.
- **Tags:** the leftmost of `#true` → (true, 95), `#false` → (false, 92) or `#unsure` → (inconclusive, 40) wins.
  - A tag matches case-insensitively and only as a whole tag (`#(true|false|unsure)\b`, ASCII), so "#True." counts and
    "#trueish" doesn't.
  - `raw_result` is `{"stub": true, "rule": "#true"}`, and so on.
- **No tag:** the SHA-256 of the UTF-8 content decides. Python's salted `hash()` is never used.
  - The confidence is `50 + (bytes 0–1) % 50`.
  - The verdict is `true` when byte 2 is even, else `false`.
  - `raw_result` is `{"stub": true, "rule": "hash"}`.

**`HttpPipelineClient(url, api_key, timeout=20)`** (`max_seconds = 20`) uses urllib.
- **The request:** `POST` the request's `to_json()` to `url` with the headers `Content-Type: application/json`,
  `Accept: application/json` and `Authorization: Bearer <key>`.
- **Redirects are not followed:** a 3xx counts as `http_status`.
- **Time:** sockets get a 10 s timeout per operation, and the body is read in chunks with a total limit of 20 s.
  The DNS lookup has no timeout (a known limit).
- **Size:** at most 64 KB of body is read; anything more is `bad_response`.
- **Error mapping:**

  | What happens | `kind` |
  |---|---|
  | `HTTPError` (including any 3xx) | `http_status` |
  | timeout, total or per operation | `timeout` |
  | `URLError` or `OSError` | `network` |
  | bad JSON, or a body that isn't an object | `bad_response` |
  | an invalid result | `contract` |

- The opener is injectable for tests.

**`get_client()`** reads `settings.PIPELINE_BACKEND` on every call.

### Routing (pure; `apps/pipeline/routing.py`)

```python
MAX_ATTEMPTS = 5
def backoff(attempts): ...                 # 2^attempts minutes, capped at 60 (§3)
def apply_pipeline_result(post, result, cfg, now) -> Outcome
def apply_pipeline_failure(post, error, now) -> Outcome
```

**`apply_pipeline_result`**
- If the post isn't awaiting a check, it returns `IGNORED` and writes nothing.
- Otherwise it first stores the result: `pipeline_verdict`, `confidence_score`, `pipeline_result = raw_result` and
  `pipeline_checked_at = now`, and it clears `pipeline_next_attempt_at`.
- A result is **decisive** when the verdict is true or false **and** `confidence ≥ cfg.confidence_threshold`.

| Post | Result | Effect | Returns |
|---|---|---|---|
| `pending` | decisive | gets the label, with `verdict_source=pipeline` | `LABELLED` |
| `pending` | not decisive | `enter_review(PIPELINE)` | `ENTERED_REVIEW` |
| `under_review` (reports) | decisive TRUE | `pre_review_status=verified_true`, `verdict_source=pipeline` | `UPDATED_REVIEW` |
| `under_review` (reports) | decisive FALSE, or not decisive | flag `both` (**Decision 1**) | `UPDATED_REVIEW` |

**`apply_pipeline_failure`** uses the same guard.
- It stores `pipeline_result = {"error": kind, "detail": …, "attempt": n}`.
- Below `MAX_ATTEMPTS`, it sets `pipeline_next_attempt_at = now + backoff(attempts)` and returns `RETRY`.
- At `MAX_ATTEMPTS` it gives up and clears the retry time. A `pending` post goes to review for the pipeline. A reported
  post's flag becomes `both`: this is a **new §4 row**, since row 325 covers only `pending`.

**Not built here:**
- §4's emergency clause (11C). `now` is already a parameter.
- A Part 8 A1 guard. Removed posts never reach `enter_review`: the predicate excludes them.

The outcomes are what Part 13 will hook its notifications onto: `LABELLED` (a verdict) and `ENTERED_REVIEW`.

### Status writes (`apps/posts/services.py`)

The two writes are `record_pipeline_result(post_id, result, *, claimed_attempts, now)` and
`record_pipeline_failure(post_id, error, *, claimed_attempts, now)`. Each runs in this order:

1. Open `transaction.atomic(durable=True)`, so it can never run inside an outer transaction (review). Test-case
   atomics are exempt from this check.
2. Lock the row with `not_deleted().select_for_update(no_key=True, of=("self",))`, the Part 8 lock.
3. Drop the result, and write nothing, in either of these cases:
   - the post was deleted in the meantime (it isn't found);
   - its `pipeline_attempts` no longer equals `claimed_attempts`, because a newer claim has taken over.
4. Otherwise call the routing function, then save only the fields it may change, plus `updated_at`.
5. Return the outcome, or `None` when the result was dropped.

`cfg` is `get_platform_settings()`.

### Processor (`apps/pipeline/processor.py`)

**Queue order:** `awaiting_check_q() & due`, ordered by `is_emergency DESC, created_at, id`. Part 11C will change the
first key to "active emergency".

**Claim** (`atomic(durable=True)`):
1. Take one post. The sweeper uses `FOR NO KEY UPDATE SKIP LOCKED`. The kick (`process_post(id)`) waits for the lock
   instead of skipping it, because a report holding the row for a few milliseconds must not push the post back to the
   hourly tick (review).
2. Increment `pipeline_attempts`; the new value is the claim token.
3. Set `pipeline_next_attempt_at = now + 5 min`. This is the **lease**.
4. A post whose `pipeline_attempts` already equals `MAX_ATTEMPTS` (every earlier claim died) is given up at once,
   without a call and without counting the claim again.

**Call:** outside any transaction. Building the request belongs to the call, so a bad row is just a failed attempt.
Any exception counts as a failure; an unexpected one becomes `kind="error"` with only its class name.

**Apply:** through the two `posts.services` functions above, with a fresh `now`.

**`pipeline_next_attempt_at` over a post's life:**
- **after a result or a give-up:** null;
- **after a failure:** the backoff time;
- **after an ignored, dropped or stale result:** left alone, so a newer lease is never overwritten.

**`process_pending(*, limit=10, now=None, client=None, deadline=None) -> int`**
- Repeats claim, call, apply up to `limit` times.
- The **first** claim always happens. Each later one happens only if `monotonic() + client.max_seconds ≤ deadline`.
- An error while handling one post is logged, and the batch moves on; the post's lease brings it back later. An error
  in the claim itself ends the batch.
- Returns the number of posts handled.

**`process_post(post_id, *, now=None, client=None) -> bool`:** the same steps for one post, used by the kick.

**Logging:**
- INFO for each outcome, with the post id only, never its content.
- WARNING for each failed attempt.
- ERROR for a give-up: one Sentry event per abandoned post.

### Inline kick

**Registration:** `create_post` registers an `on_commit` callback for a **fact** when `settings.PIPELINE_INLINE_KICK`
is on.
- The callback is a plain closure (not `functools.partial`, and not `robust=True`).
- It **catches every exception** itself (review).
- The import is function-local, to avoid a circular import.

**`start_kick(post_id)`:**
- Takes a non-blocking slot from `BoundedSemaphore(4)`, one per process. When all slots are busy it logs, starts
  nothing, and the tick handles the post later.
- Starts a daemon thread named `pipeline-kick` that runs `process_post`. In `finally` the thread releases its slot and
  calls `connections.close_all()`.
- Returns the thread, which tests join.

A post whose transaction rolls back queues nothing, and an opinion never triggers a kick.

### Tick (`apps/core/views.py` + `urls.py`, where STRUCTURE puts it)

`POST /api/internal/tick/` is an `_OpenView` with `never_cache`.
- **The secret:** `DeepHealthView` and the tick share one `X-RZ-Cron-Secret` check. A missing or wrong secret is
  **403 `permission_denied`**, and so is a non-ASCII one.
- **The work:** `process_pending(limit=10, deadline=monotonic() + 25)`, which answers **200 `{"processed": n}`**.
- GET answers 405.

### Command (`apps/pipeline/management/commands/process_pending.py`)

`python manage.py process_pending [--limit N] [--loop] [--interval S]`
- A single run **drains the backlog** in batches of `--limit` (1–100, default 10) until nothing is due, then prints
  "Processed N fact posts.".
- `--loop` repeats that every `--interval` seconds (at least 1, default 5) and runs `close_old_connections()` between
  batches. Ctrl+C ends it cleanly.

### Settings (`rumor_zero/settings.py`, `env_helpers.pipeline_config`)

- `PIPELINE_BACKEND` is `stub` or `http` (default `stub`); any other value fails by name.
- `PIPELINE_INLINE_KICK` is read with `env.bool` (default True).
- With `http` only:
  - `PIPELINE_URL` must be `https://`. Plain `http://` is allowed only to a loopback host, the relay's rule.
  - `PIPELINE_API_KEY` is required.
- Errors name the variable, never its value.
- The root `_hermetic` fixture pins `stub`, the kick off, a blank URL and key, and blocks the HTTP client's network.
  A separate autouse fixture fails a test that leaves a `pipeline-kick` thread alive (review).

### Serializer (finding 4)

One helper serves both `PostSerializer` and `status_item`. It returns `verdict_source` only for `verified_true` and
`verified_false`, and `null` otherwise, the author's own removed post included.

### Frontend and E2E

- **No production code change.** Unit tests pin the stub's real values:
  - `"95.00"` → VERIFIED 95% / "Checked automatically · 95% confidence";
  - `"92.00"` → FALSE 92%;
  - `under_review` with `verdict_source: null` → "Under review".
- **Servers and shell:** `playwright.config.ts` (the Django `env`) and `e2e/helpers.ts` (`shellEnv`) add
  `PIPELINE_INLINE_KICK: "False"` and `PIPELINE_BACKEND: "stub"`. The config's comment about a reused `runserver`
  gains the kick.
- **`processPost(postId)`:** runs `process_post(id)` through `manage.py shell -c` and prints the resulting status. It
  throws unless the status is `verified_true`, with a message that names `confidence_threshold`: the E2E backend uses
  the developer's own PlatformSettings, seeded at 85.
- **The Part 9 E2E is an existing test, rewritten.** `post-detail.spec.ts:143` ("a pending fact's badge turns into the
  verdict by itself") gets a `#true` claim, and `processPost(id)` replaces `setPostState`.
  - The card and the page in a second tab must show VERIFIED 95% and "Checked automatically · 95% confidence" through
    Part 5's polling.
  - There is no new sign-up; the suite stays at 16 of the 20 sign-ups allowed per minute.

## Defaults where the docs are silent (approved with the plan)

- **The queue:**
  - claim → call → apply, with the 5-minute lease and the claim token; the attempt is counted **at claim time** (a
    change from §6's "on error"), and stale results are dropped;
  - the single predicate, and "a post that has a verdict ignores results";
  - a post deleted mid-check has its result dropped. A post removed or decided by a moderator mid-check is ignored,
    with nothing written.
- **Locks:**
  - `durable=True` on the claim and the apply;
  - SKIP LOCKED for the sweeper; the kick waits for the lock.
- **The kick:** a daemon thread, at most 4 per process, exception-safe, and it closes its connections.
- **The tick:** the first claim is always allowed, then a 25 s budget (HTTP handles about 1–5 posts, the stub 10);
  403, 405, `{"processed": n}`; no throttle.
- **The command:** a single run drains the backlog; `--interval` defaults to 5 and `--limit` to 10.
- **The stub:** the leftmost tag wins, matched case-insensitively and as a whole tag; the hash rule gives only true or
  false at 50–99.
- **The contract:** `ROUND_HALF_UP`, with the range checked before quantizing.
- **The HTTP client:** stdlib, no redirects, 64 KB, 10 s per operation and 20 s in total.
- **Privacy:** `verdict_source` is public only with a `verified_*` status.
- **Logging:** the levels above.
- **Settings:** the checks above.
- **E2E:** the kick is off, and only the test's own post is processed.
- **No migration:** the existing partial index serves pending posts, and the reported branch is small and read through
  `posts_review_queue_idx`.
- **`test_no_network`:** names `clients.py` as the one allowed module.

## Files

**Backend, new:**
- `apps/pipeline/{contract,clients,processor}.py`
- `apps/pipeline/management/__init__.py`, `management/commands/__init__.py` and `commands/process_pending.py`
- tests in `apps/pipeline/tests/`: `test_contract`, `test_stub_client`, `test_http_client`, `test_routing_pipeline`,
  `test_queue` (predicate table, ordering), `test_processor`, `test_races` (`transaction=True`), `test_kick`,
  `test_command`, `test_no_network`
- `apps/core/tests/test_tick.py`

**Backend, changed:**
- `apps/pipeline/routing.py`
- `apps/posts/services.py` (the two writes, plus the kick registration in `create_post`)
- `apps/posts/serializers.py`
- `apps/core/{views,urls}.py`
- `rumor_zero/{settings,env_helpers}.py`
- `backend/conftest.py`
- `apps/reports/tests/test_no_network.py`
- `apps/core/tests/test_settings.py`
- any existing test that asserts `verdict_source` on an under-review or removed post (updated on purpose and listed in
  task.md)
- `backend/.env.example`: comments only

**Frontend:**
- `playwright.config.ts`
- `e2e/helpers.ts`
- `e2e/post-detail.spec.ts`
- `features/posts/VerdictBlock.test.tsx` and/or `lib/post-display.test.ts` (the stub values)

**Docs:**
- **ARCHITECTURE:**
  - §3: the pipeline constants, the lease and the tick budget;
  - §4: Decision 1's row, the give-up row for a reported post, the "awaiting a check" guard, a mid-check delete, and
    the note that row 331 is now the general rule;
  - §4d: the repost refusal can no longer reveal a hidden label;
  - §6: the processor rewritten (claim, lease, apply, token, predicate, triggers, stub and HTTP details), plus the
    production blocker;
  - §9: the tick, and the `verdict_source` rule;
  - §11: the hermetic pipeline pins.
- **ANALYSIS:** c-41 (the Part 9 decisions).
- **STRUCTURE:** the pipeline and core entries.
- **ENV_GUIDE:** the `PIPELINE_*` checks, the production warning, and §2.12's batch note.
- **MEMORY:** new entries.
- **task.md:**
  - Part 9: criteria, deviations, both status spots;
  - Part 17: one note pointing at Decision 2.
- **`docs/test-command.md`:** a Part 9 section in **both** guides, plus the intro list.
- **HANDOFF**, and the saved plan.

## Steps (each ends green before the next)

0. Save the plan to `docs/agents/plans/part-9-pipeline-stub-routing.md`, and update HANDOFF: Part 8 is committed, and
   Part 9 is in progress. Check that `git status` is clean and `docker compose ps` is healthy.
1. **Settings:** `pipeline_config`, the three settings, the `_hermetic` pins and the kick-thread fixture, plus the
   settings tests (subprocess pattern).
2. **Contract**, with its tests.
3. **Clients:** the stub and HTTP clients and their tests, and the `test_no_network` allow-list.
4. **Routing:** the predicate pair, `backoff`, both apply functions and `Outcome`. Tests: the full pipeline rows of the
   §4 table and the predicate agreement.
5. **Status writes:** the two `posts.services` writes and the serializer rule, with their tests. These include "a
   post that went pending → reports → late FALSE can be reposted" and "a publicly FALSE post that is reported still
   can't be".
6. **Processor**, with its tests, then the `transaction=True` race tests.
7. **Kick** in `create_post`, with its tests.
8. **Tick:** the view, the URL and the tests.
9. **Command**, with its tests.
10. **Frontend:** unit tests, then the E2E config, helper and the converted test. Run the full E2E suite.
11. **Docs:** everything in the Docs list. In the `test-command.md` steps, Linux blocks are bash-checked (`bash -n`),
    and the PowerShell blocks follow the file's existing patterns.
12. **Full validation**, mutation checks, the scripted-browser check, and an EXPLAIN of the claim query on seeded data
    in a rolled-back transaction. Update HANDOFF.

## Tests

**Contract:**
- the type, range and quantization matrix, with `bool` and float refused;
- a tuple, not a list, for `sources`;
- `from_json` with missing keys, extra keys and a non-object.

**Stub:**
- the three tags, the leftmost rule, case, whole tags only, and that sources are ignored;
- the hash rule pinned to fixed expected values for known strings, and determinism across calls;
- 1,000 random strings stay within 50–99.

**HTTP client** (fake opener):
- the URL, the method, the headers including Bearer, the JSON body with sources in order, and the timeouts;
- success;
- every error kind;
- redirects not followed, the 64 KB cap, and the total limit;
- the key never appears in an error or a log;
- the only URL opened is `PIPELINE_URL`.

**Routing** (pure, one test per row of the §4 table that concerns the pipeline):
- decisive true and false, the threshold boundary (at the threshold, and 0.01 below), and inconclusive at 99;
- late TRUE, late FALSE (Decision 1) and late low results on a reported post;
- removed, moderator-decided, already pipeline-labelled, opinion, appeal and `both` posts are all ignored;
- the failure path: retries 1–4 at 2, 4, 8 and 16 min, the give-up at 5 (pending → review, reported → `both`), and
  the cap at 60;
- idempotence;
- an emergency post is routed like any other until 11C.

**Queue:**
- the predicate table, Q against Python;
- due and not due;
- the order: emergency flag, then age, then id;
- after every outcome on a reported post, `process_pending(now=+1 day)` returns 0.

**Processor** (`db`):
- the claim increments the attempt count and sets the lease;
- give-up of a post that is already exhausted;
- events during the call, triggered by a fake client's `check()`:
  - the fifth counting report → the late-result rows;
  - `delete_post` → the result is dropped;
  - a direct moderator verdict → ignored;
  - a direct dismissal back to `pending` → the normal rows;
- a stale token is dropped and leaves the newer lease alone;
- "no overwrite": a pipeline-labelled post plus another result keeps every field and `updated_at`;
- one bad post doesn't stop the batch;
- `limit` and `deadline`;
- `process_post` only takes its own post, and only while it is due.

**Races** (`transaction=True`, using the `run_together`, `hold_the_row` and `start` patterns):
- **SKIP LOCKED:** the oldest post is held, and the sweep takes the second without waiting.
- **No lock across the call:** inside `check()`, a second thread's `select_for_update(nowait=True)` succeeds.
- **The kick waits:** behind a held row it waits rather than skips, and processes the post after the release.
- **Lease expiry:** the post is re-claimed at lease + 1 s, and the first, stale result is dropped.
- **Two processors:** each post is called exactly once.

**Kick:**
- the captured `on_commit` callbacks: one for a fact with the kick on, none for an opinion, none with the kick off,
  none on a rollback;
- a real thread that is joined: the post is labelled, and the thread's connection is closed;
- a failure to start, or inside the thread, is logged, never raised;
- the semaphore: when it is full, nothing starts.

**Tick:**
- 403 with no secret, a wrong one, an empty one and a non-ASCII one, and nothing is processed;
- GET is 405;
- the 200 shape;
- 10 of 12 posts in one tick, and the rest in a second;
- under 30 s for 10 posts with the stub;
- a fake client with `max_seconds=25` gives exactly 1;
- a stale Bearer header is ignored (no authentication).

**Command:**
- one run drains 12 posts;
- the output text;
- the limits on `--limit` and `--interval`;
- `--loop` with `sleep` patched to raise `KeyboardInterrupt`.

**Settings:**
- the defaults;
- a bad backend;
- `http` without a URL or key, with plain `http://` to a non-loopback host, and with an `https` URL;
- no error message quotes a value.

**Serializer:**
- `verdict_source` is null for `pending`, `under_review`, `published` and `removed` posts (the author's view included),
  and set for `verified_*`.

**No network:**
- the stub processes a fact with sources while the `blocked` fixture is active, and nothing is recorded;
- the amended import guard.

**Frontend:** the copy and badges for the stub's values.

**E2E:** the converted test, plus the whole suite.

**Mutation checks:** remove SKIP LOCKED, the lease, the token check, the predicate's second branch, the
`verdict_source` guard, `durable`, the callback's `try`, and the "first claim always" rule. Each must fail a test.

## Verification (end to end)

- **Backend** (activate the venv in every call):
  `ruff check . ; ruff format --check . ; python manage.py makemigrations --check --dry-run ; pytest`. No migration is
  expected.
- **Frontend:** `npm run lint ; npm run typecheck ; npm run lint:tokens ; npm run format:check ; npm test ; npm run
  test:e2e`, plus a run in CI mode.
- **By hand, with `runserver` on its defaults (kick on):**
  - a `#true` fact posted with curl turns `verified_true 95.00 pipeline` on the status endpoint within about a second;
  - `#false` → `verified_false 92.00`;
  - `#unsure` → `under_review` with nulls.
- **With the kick off:** facts stay `pending`. `process_pending` reports "Processed N" and clears them, and so do two
  ticks.
- **The tick:** 403 without the secret, and `{"processed": n}` with it. The secret is read from `backend/.env` and
  never printed.
- **In a browser:** a `#true` fact turns from CHECKING to VERIFIED 95% within about 10 s on the card and the page,
  checked at 1280 px and 390 px. Django Admin shows the pipeline fields read-only.
- The Linux blocks of `docs/test-command.md` Part 9 are extracted from the doc by script, run verbatim, and their
  output diffed against the doc, as in Parts 4–8. The PowerShell blocks are not run (there is no PowerShell here).

## Stop conditions

Stop and ask if:
- a migration seems needed;
- a race test is flaky;
- a pinned query count changes;
- a new dependency, service or env variable seems needed;
- the E2E suite would need more sign-ups, or a test other than the converted one breaks;
- `durable=True` conflicts with a real caller;
- anything requires touching Parts 10–11C beyond the follow-ups below.

## Follow-ups to record (not done here)

- **Part 17 (Decision 2):** production must not run the stub as it stands. It allows self-verification with `#true`
  and gives hash-chosen labels.
- **Part 10:** after a late FALSE, Dismiss leaves the post under review for the pipeline, and the moderator labels it.
  The queue should show the pipeline's verdict and confidence.
- **Part 11:** a Restore to `pending` puts the post back in the queue with its attempt count. A post that is already
  exhausted is then given up again at once. Decide whether Restore resets the count.
- **Part 11C:** the emergency branch, and "active emergency" as the queue's first key. §4's row 331 is now the general
  rule.
- **Part 11B:** the reputation hooks in `record_pipeline_result`.
- **Part 13:** notifications on `LABELLED` and `ENTERED_REVIEW`, in the same transaction.
- **When a real pipeline arrives:**
  - with the hourly tick, retries take hours and HTTP handles about 1–5 posts per tick;
  - DNS has no timeout;
  - close the database connection before a long call.
- **Frontend:** a new post's first status check comes after 10 s, even though the stub's verdict exists after about
  100 ms.
