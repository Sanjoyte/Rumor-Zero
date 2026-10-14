# Plan: Part 11B, Credibility score

- **Status:** APPROVED by the user (Sanjoy Rozario) on 2026-10-13, together with the eight decisions and the defaults
  below; drafted 2026-10-13 by Claude (Opus 5.5). Saved here and linked from HANDOFF at approval, so step 0 only needs to
  verify the workspace and record the baselines. Not implemented yet.
- **Implement with:** Opus 5.5 · high (task.md).
- **Evidence (all read-only):**
  - Docs: HANDOFF, MEMORY (Parts 7B to 11), `task.md` Parts 11 / 11B / 11C / 11D, ARCHITECTURE §2/§3/§4/§4a/§8/§9/§10,
    ANALYSIS f-5 and f-6, STRUCTURE.
  - Backend code: `apps/moderation/{services,rules,models,admin,roles}.py`, `apps/posts/services.py`,
    `apps/pipeline/routing.py`, `apps/reports/services.py`, `apps/social/{models,services,serializers,views}.py`,
    `apps/accounts/{models,admin}.py`, `apps/core/pagination.py`, `conftest.py`.
  - allauth's `set_password` (it does a full `user.save()`).
  - Frontend: `ProfileHeader`, `UserRow`, `lib/api/types.ts`, `e2e/helpers.ts`.
  - Stitch c1 (meta row) and c3 (row chip), DESIGN.md (teal and the `verified` seal mean a verified fact).
- **Design review:** a Plan-agent review of this draft ran **before** approval. Its findings are folded in and marked
  "(review)".

## Context

Part 11B adds the public **credibility score** (D5, ANALYSIS f-5, ARCHITECTURE §4a). It is a 0–100 number per account,
starting at 50, driven only by fact-check and moderation outcomes:

- It is stored as an **append-only ledger** (`ReputationEvent`) plus a denormalised `users.reputation_score` and
  `reputation_sample`.
- It is **exactly reversible**: overturned appeals, restores and re-labels append `reversal` rows.
- It is auditable with `recompute_reputation --check`.
- It is shown as **"Credibility 72"** or **"New"** (fewer than 3 counted events) in the profile header and in
  follower/following rows, and **never on post cards**.

Part 11B also adds two read endpoints for 11D's charts, and the admin views of the ledger.

**Dependency check (2026-10-13).** Part 11B depends on **7B** (Done 2026-10-10), **10** (Done 2026-10-13) and **11** (Done
2026-10-13). Their chains are Done: 9, 8, 7, 6, 5, 4, 3, 2, 1, 0C, 0A/0B/0D. Open but not blocking: Part 3 criterion 4
(the real-Google check) and CI for Parts 2 to 11 (not reported yet).

**Workspace:** HEAD is `71c5e14` ("Part 11: Appeals & removed-post tombstones") and the tree is clean. HANDOFF still says
Part 11 is uncommitted; step 0 corrects it.

**Already in place:**
- `users.reputation_score` (default 50, check 0–100) and `reputation_sample` (check ≥ 0), from 0A.
- `social.serializers.reputation_block` already returns `{score, sample}` on the profile and on user rows (`score` is
  null below 3).
- The Part 10/11 moderation services have one choke point, `_perform`, that holds the post lock.
- `posts.services.record_pipeline_result` writes labels.
- `Repost.status_at_repost` is recorded.
- `/how-it-works` exists as a Part 15 placeholder.

## Your decisions (2026-10-13)

1. **A removal adds to the label; it doesn't replace it.** The label's event (`fact_true` / `fact_false` /
   `emergency_false`) stays, and `post_removed` (N+2) is added. A removed FALSE post costs N+1 and N+2. **Restore**
   reverses only the removal's events (author, reposters, and the report credit that removal earned).
2. **The public `recent` list shows own-post events only:** `fact_true`, `fact_false`, `emergency_false`,
   `post_removed`, each with `reversed`. Repost events, report credits and reversal rows never appear there.
3. **Moderators and up can read the whole ledger** in Django Admin. This needs a new permission,
   `reputation.view_reputationevent`, granted to the Moderators group by migration `moderation.0005`.
4. **The badge is neutral:** grey `on-surface-variant` text, "Credibility 72" or "Credibility: New". In rows it's a
   neutral chip (c3's neutral chip classes) plus "· 84 verified". No teal and no `verified` seal, which DESIGN.md
   reserves for verified facts.
5. **Report credit only when the decision changed the post.**
   - Mark FALSE credits reporters only if the post wasn't already FALSE before the review
     (`pre_review_status ≠ verified_false`). So reports on a pipeline-FALSE post, or reports filed during a label
     appeal, earn nothing.
   - Remove always credits.
6. **A reversed FALSE reverses the reporters' credit too.** When the label becomes TRUE, the `report_upheld` rows
   earned by a Mark FALSE are reversed. This mirrors task.md's Restore rule.
7. **No backfill.** The ledger starts empty. Nothing is deployed, so only dev data is affected: old test accounts stay
   "New", and the next moderator action on an old post records its missing events, dated that day.
8. **No self-credit.** The deciding moderator's own report earns nothing from their decision. Other people's reports
   still do.

## Scope

**In:**
- New app `apps/reputation`: model, migration, `scoring.py`, `services.py`, views/urls/serializers, admin, the
  `recompute_reputation` command, tests.
- Hooks in `moderation.services._perform` and `posts.services.record_pipeline_result`.
- `reports.services.resolve_open_reports` returns the reporters.
- `rules.Effect.credits_reporters`.
- `User.save` never writes the score fields on a full save.
- User rows gain `counts.verified`.
- Permission migration `moderation.0005`.
- Admin: the ledger list, a post-page inline, and a credibility field on `UserAdmin`.
- Frontend: `CredibilityBadge` in `ProfileHeader` and `UserRow`.
- One E2E test.
- Docs.

**Not in 11B:**
- The ring, trend and history UI (11D; the endpoints are built here).
- The emergency gate and the automatic `emergency_false` on an emergency Mark FALSE (11C; the weight itself is built
  here).
- People search (12), notifications (13), export (14).
- The `/how-it-works#credibility` text (Part 15).

## Design

### Data model: `apps/reputation/models.py`, migration `reputation.0001_initial`

`ReputationEvent` per ARCHITECTURE §2:

| Field | Type and rules |
|---|---|
| `id` | uuid |
| `user` | FK CASCADE, `related_name="reputation_events"`, `db_index=False` (the composite index below covers it) |
| `kind` | `EventKind` TextChoices: the 10 kinds, with plain-language labels |
| `positive`, `negative` | `Decimal(6,2)` |
| `post` | FK SET_NULL null, `related_name="reputation_events"` (indexed: `settle_post` reads by post) |
| `moderation_action` | FK SET_NULL null, `related_name="+"`, `db_index=False` |
| `reverses` | `OneToOneField("self", CASCADE, null, related_name="reversed_by")`; the unique index means a row can be reversed once |
| `score_after` | smallint |
| `created_at` | `default=timezone.now` |

**Checks:**
- `reputation_event_kind_valid`
- `reputation_event_weights_sign`: a reversal has both weights ≤ 0; every other kind has both ≥ 0.
- `reputation_event_reverses_iff_reversal`
- `reputation_event_score_after_range`: 0–100.

**Index:** `repevent_user_created_idx (user, created_at)`.

**Append-only in code:** `save()` of an existing row and `delete()` raise, as `ModerationAction` does. Account deletion
cascades through the collector. A post's hard delete only nulls the link: SET_NULL is a queryset `update()`, so §2's
"never updated" gets that footnote (review).

### `apps/reputation/scoring.py` (pure: no database, no clock)

**Constants:**
- `WEIGHTS`: the §4a table as Decimals.
- Role groups: `AUTHOR_KINDS` (= own-post kinds, which count toward `sample`), `REPOSTER_KINDS`, `REPORT_UPHELD`.
- `REPOST_COUNTED = (pending, under_review)`.
- `PUBLIC_AFTER = 3`. This moves here from `social.serializers.MIN_PUBLIC_SAMPLE`.
- `REPORT_CREDIT_CAP = 4`, `REPORT_CREDIT_WINDOW = 30 days`.

**`score(p, n)`:** exact half-up rounding in integer quarter units. With `P4 = 4p`, `N4 = 4n` and
`D = 40 + P4 + N4`, the score is `(200·(20+P4) + D) // (2D)`.
- Python's `round` is banker's rounding: (0, 30) gives 12 where half-up gives 13 (review).
- It raises on negative sums or weights that aren't multiples of 0.25.
- ARCHITECTURE's `round` becomes "half up".

**Slots:** every row belongs to one of two slots.
- **LABEL:**
  - author `fact_true` / `fact_false` / `emergency_false`;
  - reposter `repost_true` / `repost_false` / `repost_emergency_false`;
  - `report_upheld` rows whose `moderation_action.action` is `marked_false`.
- **REMOVAL:** author `post_removed`, reposter `repost_removed`, `report_upheld` rows whose action is `removed`.

**`desired(status, is_emergency)`:**
- LABEL is TRUE when the status is `verified_true`, and FALSE or EMERGENCY_FALSE (from `is_emergency`) when it is
  `verified_false`. **Any other status leaves LABEL as it is (KEEP).**
  - **Reviews freeze the score:** entering review changes nothing.
  - A pipeline late TRUE held in `pre_review_status` stays private until it becomes public.
  - A removed post keeps its label events (decision 1).
- REMOVAL is REMOVED exactly when the status is `removed`, and NONE otherwise.

**`changes(state, rows, *, reposters, reporters)`** returns `Changes(reverse=[row], add=[(user_id, kind)])`. It is the
whole reconciliation, table-tested.

For each slot whose desired value is not KEEP:
- **Reverse** every un-reversed row whose kind no longer matches:
  - for author and reposter rows, the kind must equal the desired kind for their role;
  - a `report_upheld` row matches only a negative outcome (FALSE / EMERGENCY_FALSE for LABEL, REMOVED for
    REMOVAL).
- **Add** the missing rows:
  - **The author** gets one.
  - **Eligible reposters:** anyone with a current repost whose `status_at_repost` is in `REPOST_COUNTED`, plus anyone
    who already holds an un-reversed reposter row in this slot.
    - So a reposter who undid their repost after the verdict keeps their row (stickiness), and on a re-label gets the
      new kind, which is "what it would have been" (review).
    - Someone who undid before any verdict gets nothing.
  - **Reporters:** only those the caller passes, in the action's slot (Mark FALSE → LABEL, Remove → REMOVAL).

### `apps/reputation/services.py`: the only writer of the ledger and of `users.reputation_*`

**`settle_post(post, *, now, action=None, credited_reporters=())`**
- It raises `RuntimeError` unless it runs inside an atomic block.
- The caller already holds the post's `FOR NO KEY UPDATE` lock.

Steps:
1. Read the post's un-reversed, non-reversal rows (one query: id, user, kind, weights, `moderation_action__action`).
   Read the qualifying reposts only when a slot can add rows (status `verified_*` or `removed`; one query).
2. Run `scoring.changes`. **Nothing to do → return** without locking anyone. That makes it idempotent: re-running a
   verdict, Keep removed or a re-sent result writes nothing.
3. Lock every affected user with `select_for_update(no_key=True).order_by("pk")`.
   - **NO KEY UPDATE, not plain FOR UPDATE** (review). `_perform`'s inserts take `KEY SHARE` on the moderator's user
     row at commit (deferred foreign keys). A plain FOR UPDATE on a user who is also a moderator elsewhere could
     deadlock.
   - Postgres sorts before it takes row locks, so the lock order is the uuid order.
   - ARCHITECTURE §4a and task.md, which say plain `select_for_update()`, are corrected.
4. **Only after that lock**, apply the reporter cap (review: before the lock, two Mark FALSEs could both see 3).
   - Count each reporter's un-reversed `report_upheld` rows with `created_at > now − 30 days`.
   - At 4: no row.
5. Run one grouped aggregate over the affected users: `Sum(positive)`, `Sum(negative)`, the count of un-reversed
   own-post rows, and `Max(created_at)`. Postgres refuses aggregates with `FOR UPDATE`, so the lock and the aggregate
   are separate queries.
6. Build each user's rows in order, reversals first, then additions.
   - A reversal row is `kind=reversal`, negated weights, `reverses=<row>`, `post`, and `moderation_action=action`.
   - New rows carry `post` and `moderation_action`.
   - Running sums give each row's `score_after`.
   - **`created_at = max(now, that user's last created_at + 1 µs)`**, so each user's ledger is strictly ordered in the
     order rows were written. Two writers for one author can commit with their `now` values out of order, and 11D's
     trend reads the last `score_after` of each day; this also means the cursor never sees ties.
7. `bulk_create` the rows. `bulk_update` `reputation_score` and `reputation_sample` on the locked user objects
   (`batch_size` 500). `bulk_update` skips `User.save`'s group sync. Return the new rows.

Also a read-only `pending_changes(post)` (the same reads, no lock or write) for tests and for the sequence test's
ledger-matches-state check.

**`User.save` hardening (`apps/accounts/models.py`, review).**
- The problem: a save of an existing row **without** `update_fields` writes every column. Examples are allauth's
  `set_password` (`user.save()`), `account/utils.py`, and the admin form. That would write back a score read earlier
  in the request.
- The fix: such a save now writes every *loaded* concrete field **except** `reputation_score` and `reputation_sample`.
  The access/group-sync logic is unchanged and is computed first. Inserts still write the defaults.
- Only `bulk_update` (the service) and `recompute_reputation` change those two columns.

### The hooks (explicit, same transaction, after the post's lock)

**`rules.py` (pure):** `Effect` gains `credits_reporters`.
- True for **Remove**.
- True for **Mark FALSE** when `pre_review_status ≠ verified_false`, read **before** `_leave_review` (decision 5).
- False for every other action.

**`reports.services.resolve_open_reports`** returns the actioned reports' reporter ids.
- It reads `values_list("reporter_id")` under the post lock, then runs the same single `UPDATE`.
- New reports can't arrive meanwhile, because `file_report` locks the post first.
- Nothing reads today's count.

**`moderation.services._perform`:** after `ModerationAction.objects.create(...)`, and for **every act except
Escalate**, it calls:
```python
settle_post(post, now=now, action=entry, credited_reporters=reporters)
```
where `reporters` is the ids returned by `resolve_open_reports`, minus `moderator.pk` (decision 8), when
`effect.credits_reporters`; otherwise it is empty.

What each action writes:
- **Mark verified:** TRUE; on a re-label, reverses the FALSE rows and the label credits.
- **Mark FALSE:** FALSE plus credits.
- **Dismiss:** returning to `verified_true` after a late TRUE records `fact_true` now, at its first public moment;
  any other Dismiss writes nothing.
- **Remove:** `post_removed`, `repost_removed` and credits; the label is kept.
- **Restore:** reverses the REMOVAL slot; to `verified_*` it may also add label rows that were never public.
- **Keep removed:** nothing, except it heals pre-11B data.

**`posts.services.record_pipeline_result`:** `settle_post(post, now=now)` only when the outcome is `LABELLED`.
- `ENTERED_REVIEW` / `UPDATED_REVIEW` write nothing, so the late TRUE stays private.
- It runs inside the existing `durable=True` block.

`file_appeal`, `record_report`, `delete_post`, `repost` and `unrepost` never touch the ledger. Deleting a post keeps
its events, and so does undoing a repost after the verdict.

**Lock rules (go into MEMORY):**
- Always lock the post first, then the users, sorted, `NO KEY UPDATE`.
- Never lock a user and then a post. Part 14's account deletion must keep this order.
- One `settle_post` per transaction.
- 11C's `emergency_blocked_until` write must happen inside or after `settle_post`'s user locks.

### API (`apps/reputation/{views,urls,serializers}.py`; `path("api/", include("apps.reputation.urls"))`)

**`GET /api/v1/users/{username}/reputation/`**
- Access: `AllowAny`, **`authentication_classes = []`** (like `PostStatusView`: the answer never depends on the viewer,
  so a stale token isn't a 401), `never_cache`, no throttle.
- Lookup through `social.services.lookup_name`; an unknown, inactive or malformed name is a 404.
- **2 queries:** the user with three count annotations, then the recent rows.
- Response:
  ```json
  {"score": 72 | null, "sample": 23, "verified": 20, "false": 3, "removed": 1,
   "recent": [{"kind", "label", "post_id", "created_at", "reversed"}]}
  ```
- `verified`, `false` and `removed` are **status-based, deleted posts included**: the same rule as the profile header's
  counters, so the two never disagree.
- `recent`: the last 10 rows of own-post kinds, newest first. `reversed` comes from an `Exists`, not from reading
  `reversed_by` (a missing reverse one-to-one raises even under `select_related`; review). `post_id` is null when the
  post was deleted.

**`GET /api/v1/me/reputation/events/`**
- Access: `IsAuthenticated`, `never_cache`.
- Pagination: `ReputationEventPagination(TimestampCursorMixin, CursorPagination)`, ordering `("-created_at", "-id")`,
  20 per page (50 max). A crafted cursor is a 404.
- **2 queries:** the user, then the page (joins `post`, `post__appeal`, `reverses`).
- Row (11 keys): `{id, kind, label, positive, negative, score_after, created_at, post_id, reverses, reversed, appeal}`.
  - `positive` and `negative` are decimal strings, like `confidence_score`.
  - A reversal's label is "Reversed: <original label>".
  - `appeal` is set only on the caller's **own-post negative, un-reversed** rows: `{"status": open|upheld|overturned|null,
    "can_appeal": bool}`, with `can_appeal` true when the post is `verified_false` or `removed`, not deleted, and has no
    appeal (the same rule as the post object's). Every other row has `null`, because repost rows have no appeal of
    their own.
  - Includes reversal rows.

**User rows** (followers/following) gain `counts: {"verified": n}`, for c3's "· 84 verified":
- one correlated subquery, the profile's definition, deleted posts included;
- 9 keys;
- the query count is unchanged.

The profile keeps its shape; its `reputation` block is now live data.

### Admin

**`ReputationEventAdmin`** (`apps/reputation/admin.py`), read-only (no add, change or delete):
- columns: time, user, kind, P / N, `score_after`, post link, reversed (an `Exists` annotation);
- filters: kind, created; search by username;
- `list_select_related`, `show_full_result_count = False`;
- the detail page shows `moderation_action` and `reverses`;
- viewable with `reputation.view_reputationevent`.

**Moderators and up (decision 3):**
- Migration `moderation.0005_reputation_permission` uses 0004's frozen lists plus the new permission, created with the
  Part 10 `create_permissions` pattern. It depends on `reputation.0001`.
- `roles.MODERATOR_PERMISSIONS` gains the permission.
- `test_roles.py` points at 0005.

**`PostAdmin`** gains a `ReputationInline` ("Credibility events": time, user, kind, P / N, score after;
`select_related("user")`).

**`UserAdmin`:**
- a read-only **Credibility** field replaces the two raw fields in "Account state": "72 · 23 counted events · View
  events" when public, or "New (2 counted events, score 55)";
- the link is the ledger changelist filtered with `?user__id__exact=<id>`.

### `python manage.py recompute_reputation [--user <username>] [--check]`

- It works in chunks of 500 users (one user with `--user`). Each chunk runs in a transaction that locks the chunk with
  `NO KEY UPDATE` (sorted) **in both modes**, so a live write can't show a false difference.
- The expected score and sample come from the grouped aggregate. A user with no rows expects (50, 0).
- **Without `--check`:** it `bulk_update`s the users that differ and prints "Recomputed N users: M changed."
- **With `--check`:** it writes nothing and fails (`CommandError`, non-zero exit) on any difference, listing username,
  stored and expected values. It also replays each user's rows in `(created_at, id)` order and fails on any of these:
  - a `score_after` that disagrees with the running sums;
  - a non-increasing `created_at`;
  - a reversal whose original belongs to another user, is itself a reversal, or doesn't exactly negate it.
- An unknown `--user` is a `CommandError`.

### Frontend

**`src/features/reputation/CredibilityBadge.tsx`** (a Server-Component-safe presentational component):
- `variant="header"`:
  - in `ProfileHeader`'s meta row after "· 42 posts": "Credibility 72", or "Credibility: New" with
    `title`/sr-only text "A score shows once 3 of their posts have been checked or removed.";
  - then a "How this is calculated" link to `/how-it-works#credibility` (`prefetch={false}`).
- `variant="row"`:
  - in `UserRow` on its own line (`pl-12`, outside the profile link, so the link's name stays short);
  - a neutral chip (`rounded-lg border border-outline-variant/30 bg-surface-container text-on-surface-variant
    font-label-badge text-label-badge`) reading "Credibility 72" or "New", then "· 84 verified" (`formatCount`);
  - no link in rows: 20 identical "How this is calculated" links would be noise.
- No teal, no seal (decision 4).

**Types and test data:** `types.ts`'s `UserRowData` gains `counts: { verified: number }`, and the social test helpers
follow.

**Never on cards:** `PostCard` and `FeedList` tests assert that no "Credibility" text renders.

### E2E (`frontend/e2e/credibility.spec.ts`, no sign-up)

- A new helper, `seedCheckedFacts(username, n)`, creates `n` `#true` facts for a seeded author and runs `process_post`
  on each, through the real services.
- A visitor opens the author's profile:
  - with 2 checked facts it shows "Credibility: New";
  - after a third it shows "Credibility 62" (`score(3, 0)` = 61.5 → 62).

## Defaults where the docs are silent (approved with the plan)

1. **One reconciling `settle_post` instead of task.md's four functions** (`record_post_outcome`, `record_removal`,
   `record_report_upheld`, `reverse_post_events`).
   - Every caller is one line.
   - Re-labels and restores can't forget a reversal.
   - Idempotence comes by construction.
   - Recorded as a deviation.
2. Reviews freeze the score; a late TRUE records nothing until it is public (e.g. at Dismiss).
3. The repost timing rule is literal: `status_at_repost` `under_review` counts, so a Dismiss back to TRUE credits the
   reposts made during that review, and a Mark FALSE penalises them. The reposter eligibility rule is above.
4. Credit for every open report a credited action resolves, whether or not it counted toward the threshold. The cap
   counts un-reversed credits from the last 30 days; at the cap, no row.
5. Strictly increasing `created_at` per user; exact half-up rounding.
6. The public endpoint has no authentication. Its counts are status-based and `post_id` is null for deleted posts.
7. The events row shape and the `appeal` block above.
8. User rows get `counts.verified`.
9. The "How this is calculated" link sits in the profile header only. The `#credibility` anchor arrives with Part 15's
   page.
10. Escalate never settles.
11. Pre-11B posts are healed by their next action (decision 7).
12. The deciding moderator's **repost** events still apply to them (a penalty they can't dodge; a possible +0.25
    gain is listed for Part 16).
13. Acceptance criterion 2 is read as "returns the author and every reposter to exactly the score they would have had
    with the final outcome alone". Tests compare against control users whose posts went straight to the final state.

## Files

**New (backend):** `apps/reputation/`
- `apps.py` (`name = "apps.reputation"`), `models.py`, `scoring.py`, `services.py`, `serializers.py`, `views.py`,
  `urls.py`, `admin.py`;
- `migrations/0001_initial.py`, `management/commands/recompute_reputation.py`;
- `tests/`: `factories`, `test_models`, `test_scoring`, `test_services`, `test_races`, `test_sequences`,
  `test_recompute`, `test_api_reputation`, `test_api_events`, `test_admin_reputation`.
- Also `apps/moderation/migrations/0005_reputation_permission.py` and `apps/accounts/tests/test_user_save.py`.

**Changed (backend):**
- `rumor_zero/{settings,urls}.py`;
- `apps/moderation/{rules,services,admin,roles}.py`;
- `apps/posts/services.py`; `apps/reports/services.py`;
- `apps/social/{serializers,views}.py`;
- `apps/accounts/{models,admin}.py`.

**Existing tests changed on purpose (review):**
- `posts/tests/test_services_pipeline.py:164` (count `FOR NO KEY UPDATE` on `posts_post` only);
- `social/tests/test_api_lists.py` (`ROW_KEYS` + `counts`);
- `moderation/tests/test_rules.py` (`credits_reporters`), `test_roles.py`;
- the admin post-page constant-query tests (`test_admin_queue.py`, `test_admin_appeals.py`: seed ledger rows);
- the accounts admin fieldset tests;
- `reports/tests/test_no_network.py` (also scans `apps/reputation`).

**New (frontend):** `src/features/reputation/CredibilityBadge.tsx` + test, `e2e/credibility.spec.ts`.

**Changed (frontend):**
- `lib/api/types.ts`;
- `features/social/{ProfileHeader,UserRow,test-helpers}` + their tests;
- `features/posts` card tests (no badge);
- `e2e/helpers.ts`.

**Docs:**
- ARCHITECTURE:
  - §2: the table's details, the SET_NULL footnote, `User.save`;
  - §3: half-up;
  - §4: the hooks;
  - §4a: decisions 1, 5, 6, 8 and defaults 2–5, NO KEY UPDATE;
  - §8: ledger access, the inline, the `UserAdmin` field, 0005;
  - §9: both payloads and the row's `counts`;
  - §10: the badge.
- ANALYSIS: a c-44 entry, and an f-5 note.
- STRUCTURE.
- MEMORY: lock rules, `User.save`, reverse one-to-one, no aggregate with `FOR UPDATE`, monotonic times.
- `task.md`: criteria, deviations, both status spots, notes in 11C/11D/12/14/16.
- `docs/test-command.md`: a "Part 11B" section in **both** guides.
- HANDOFF.

## Steps (each ends green before the next)

0. (Plan saving and HANDOFF link done at approval.) Verify the workspace against HANDOFF: `git status`, `git diff`,
   `docker compose ps`. Then record the baselines: `pytest` (2965 expected) and `npm test` (1692 expected).
1. Create `apps/reputation` with `startapp`: `mkdir` first, fix `apps.py`, delete `tests.py`. Register it in
   `INSTALLED_APPS`. Add the model and migration 0001, then `ruff check --fix . ; ruff format .`. Write the model tests.
2. `scoring.py` and its table tests.
3. `services.py` (`settle_post`, `pending_changes`), the `User.save` hardening, and service tests per event kind,
   reversal path, cap, self-credit and "changed" rule.
4. The hooks: `rules.Effect.credits_reporters`, `resolve_open_reports`, `_perform`, `record_pipeline_result`. Fix the
   existing tests that change on purpose.
5. Race tests (threaded, `transaction=True`, `run_together`, a barrier injected after the aggregate read): two verdicts
   for one author, and two credits for one reporter at the cap boundary. Each must fail with the lock helper switched
   off.
6. `recompute_reputation` with its tests, and the seeded random sequence test.
7. The two endpoints and the user-row `counts`, with tests.
8. Admin: `ReputationEventAdmin`, the inline, the `UserAdmin` field, migration 0005 and `roles.py`, with tests. Roll the
   migrations back to `moderation 0004` / `reputation zero` and apply them again.
9. Frontend: types, `CredibilityBadge`, `ProfileHeader`, `UserRow`, helpers, tests. Then lint, `lint:tokens`, typecheck,
   format.
10. The E2E spec and helper; the suite in dev and `CI=1`.
11. Mutation checks, with nothing else running meanwhile (MEMORY). Re-run the survivors alone.
12. Docs and `docs/test-command.md` (both guides). Extract the Linux blocks and run them verbatim; check the browser
    steps headlessly at 1280 and 390 px.
13. Final validation, `task.md` (both status spots), HANDOFF. Stop.

## Tests

**`test_scoring`:**
- every kind's weights;
- `score` at 50, 45, 55, 38, 62, and the half-way cases (0,30)→13 and (3,51)→13;
- refusals;
- `public_score`;
- `desired` over every status × `is_emergency`;
- `changes()` over every slot × desired value × row kind, plus reposter eligibility over every `status_at_repost`
  (with and without an existing row), and reporter slot by action.

**`test_models`:** each check, append-only `save`/`delete`, CASCADE with the user, SET_NULL on a hard-deleted post.

**`test_services`:**
- **Each kind in turn:**
  - `fact_true` from the pipeline and from a moderator;
  - `fact_false`; `emergency_false`;
  - `post_removed` for a fact and an opinion;
  - the four repost kinds; no event for a repost made after the verdict;
  - `report_upheld` via Mark FALSE and Remove;
  - no credit via Mark verified, Dismiss, Escalate or the pipeline.
- **Credit rules:**
  - the cap: the 4th credited, the 5th not; a row at 30 days + 1 µs; reversed rows free a slot; the cap read after the
    lock;
  - self-credit refused;
  - "changed" only: Mark FALSE on a label appeal, or on a pipeline-FALSE post sent to review by reports, credits
    nobody; a pending fact credits.
- **Reversals:**
  - a re-label TRUE → FALSE through a reports review;
  - an overturned label appeal (author, reposters, label credits);
  - Restore: the REMOVAL slot reversed and the label kept; a Restore to review and to pending;
  - Remove on a label appeal keeps `fact_false`.
- **Things that write nothing:** Keep removed, Mark FALSE on an appeal, Dismiss with `both`, a re-sent result.
- **Timing and privacy:**
  - a late TRUE stays private until Dismiss;
  - a repost undone before the verdict gets nothing; one undone after keeps its row; a re-label after an undo moves it
    to the new kind;
  - a deleted post keeps its events.
- **Bookkeeping:**
  - `sample` and the null below 3;
  - `score_after` and strictly increasing times when an older `now` is passed;
  - "exactly what it would have been" against control users.
- **Mechanics:** outside an atomic block it raises; the users are locked sorted with `FOR NO KEY UPDATE` on
  `accounts_user`; nothing is locked when there is nothing to do.

**`test_user_save`:**
- a stale instance's full save (`set_password`, the admin form) leaves the score alone;
- a role change still syncs the groups;
- a create writes 50/0.

**`test_races`:** two Mark FALSEs on two posts by one author at once must end at 42 with sample 2 (45 and 1 without
the lock); the cap boundary, also threaded. 10 runs in a row.

**`test_sequences`:**
- Seeded random walks (e.g. 40 seeds × 40 steps) through the real services: verdicts, reports, reposts and unreposts,
  appeals, Remove, Restore, Keep removed, deletes.
- After each walk:
  - `recompute_reputation --check` passes;
  - every user's score and sample equal an **independent** simulator of the rules;
  - `pending_changes` is empty for every post;
  - each author equals a control author whose posts went straight to the final (label, removal) pair.

**`test_recompute`:**
- a rebuild fixes tampered fields;
- `--check` passes when clean and fails on a tampered score, a tampered `score_after`, broken reversal pairing and
  out-of-order times;
- `--user`; an unknown user.

**`test_api_reputation` / `test_api_events`:**
- keys and shapes;
- null below 3;
- the counts, deleted posts included;
- `recent`: own-post kinds only, ≤ 10, newest first, `reversed`, no reversal / repost / report rows, `post_id` null when
  deleted;
- 404 for unknown, inactive and malformed names;
- `Cache-Control`;
- **2 queries** (constant over 1 and 30 rows);
- a stale Bearer token isn't a 401;
- events:
  - 401 when anonymous; only your own rows; reversals included;
  - cursor walk; a crafted cursor is 404;
  - `appeal` only on your own negative rows, with `can_appeal` equal to `PostSerializer`'s for the same post;
  - 2 queries.

**`test_admin_reputation`:**
- the list is read-only; filters and search;
- a moderator can view it and a non-staff user can't;
- the post inline, with a constant number of queries;
- the `UserAdmin` field and its link, as a moderator and as a senior.

**Frontend:**
- `CredibilityBadge`: the score, "New", the header link's `href`, the row's verified text, and neutral classes (no
  `text-primary`, no `verified` glyph);
- `ProfileHeader` and `UserRow` render it;
- cards never do.

**E2E:** the spec above.

**Mutation checks (about 30 backend, 8 frontend), each must be caught:**
- **Locks:** no user lock; plain `FOR UPDATE`; unsorted locks; the cap read before the lock.
- **Credit rules:**
  - the cap counting reversed rows; the window's off-by-one;
  - self-credit allowed;
  - credit when nothing changed;
  - label credits not reversed on TRUE; Restore not reversing removal credits; Restore reversing the label.
- **Repost rules:** the repost timing set widened; the eligibility-by-row dropped; stickiness dropped.
- **Slots and weights:** KEEP turned into a reversal; the emergency weights swapped.
- **Arithmetic and order:** banker's rounding; `sample` counting reversed rows; `score_after` not running; times not
  monotonic.
- **Hook placement:** settling on Escalate; no settle on Dismiss; settling on `UPDATED_REVIEW` (leaks the late TRUE).
- **API:** public `recent` with repost or report kinds; `post_id` shown for a deleted post; `appeal` on repost rows.
- **Fields and audit:** `User.save` writing the score; `--check` ignoring `score_after`; additions without the
  matching-row check (double counting).

## Verification (end to end)

- **Backend:** `source .venv/bin/activate` in every call, then:
  - `ruff check .`, `ruff format --check .`;
  - `python manage.py makemigrations --check --dry-run`, `python manage.py check`;
  - `pytest` (full), `pytest apps/reputation`;
  - the threaded tests 10× in a row;
  - `python manage.py recompute_reputation --check` on the dev database.
- **Migrations:** apply them, roll back to `moderation 0004` and `reputation zero`, then re-apply.
- **Frontend:**
  - `npm run lint`, `lint:tokens`, `typecheck`, `format:check`, `npm test`;
  - `NEXT_PUBLIC_GOOGLE_CLIENT_ID= npm run build`;
  - `npm run test:e2e` in dev and with `CI=1`.
- **`docs/test-command.md` Part 11B (Linux, run verbatim from the doc):**
  1. Seed an author.
  2. Post three `#true` facts and run `process_pending`.
  3. `curl` the profile: `reputation` goes from null to 62.
  4. `curl` the public reputation endpoint and `/me/reputation/events/` (with a login).
  5. A reported pending fact marked FALSE: the reporter's credit appears in the ledger.
  6. Remove, then Restore: the reversal rows appear and the score returns to its earlier value.
  7. `recompute_reputation --check` passes.
  8. In the browser: the profile header badge, a followers row's chip, Django Admin's ledger list, the post inline and
     the `UserAdmin` field, at 1280 and 390 px.

  The PowerShell twins are written but not run.

## Stop conditions

- A required test, lint or type check fails for a reason that isn't obvious: stop and record it in HANDOFF.
- A code path that changes `Post.status` but isn't listed above, or any status change this plan doesn't map to slot
  values: stop and ask.
- A deadlock or flake in the race tests: stop. Never retry it into green.
- Anything needing a new dependency, service or env variable: stop and ask (none is expected).

## Follow-ups to record (not done here)

- **11C:**
  - Mark FALSE on an emergency gives `emergency_false` automatically (the weight is built);
  - the `emergency_blocked_until` write goes inside or after `settle_post`'s user locks;
  - eligibility reads the stored score.
- **11D:**
  - the trend uses the last `score_after` per UTC day (times are strictly increasing per user);
  - `CredibilityPanel` reads the events endpoint and its `appeal` block;
  - the "Ask for another look" link goes on own-post rows only.
- **12:** people search reuses `user_row`'s `reputation` and `counts.verified`.
- **14:**
  - the export includes the ledger;
  - account deletion cascades it and must not lock the user before its posts.
- **15:** the `#credibility` text and anchor.
- **16:**
  - the per-write aggregate cost;
  - lock fan-out on a post with thousands of reposters;
  - a moderator deciding a post they reposted (+0.25);
  - re-check report-credit farming with real data.
- **17:** the stub in production feeds this public score (the existing launch blocker).
