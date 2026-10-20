# Plan: Part 11C, Emergency posts

- **Status:** APPROVED by the user (Sanjoy Rozario) on 2026-10-20, together with the four decisions and the defaults
  below; drafted 2026-10-19 by Claude (Opus 5.5). Saved here and linked from HANDOFF at approval, so step 0 only needs to
  verify the workspace and record the baselines. **Implemented** 2026-10-20 by Claude (Opus 5.5); what was built
  differently is in `task.md` Part 11C ("Decisions and deviations") and the validation in HANDOFF.
- **Implement with:** Opus 5.5 · high (task.md).
- **Evidence (all read-only):** HANDOFF, MEMORY, `task.md` 11B/11C/11D/13, ARCHITECTURE §2/§3/§4/§4a/§4b/§6/§8/§9/§10,
  ANALYSIS f-1, STRUCTURE; backend `posts/{emergency,services,views,serializers,models,pagination}.py`,
  `pipeline/{routing,processor}.py`, `moderation/{rules,services,admin,models,roles,forms}.py` and the confirm template,
  `reputation/{services,scoring}.py`, `social/{feed,views,timeline,serializers}.py`, `accounts/{admin,models}.py`,
  `reports/services.py`, `core/{models,services,pagination,exceptions}.py`, the test conftests; Django 5.2.17's `Now()`;
  one Explore agent for the frontend (composer, feeds, cards, detail, gallery, E2E helpers) and Stitch b1/b2/c1/d2 +
  DESIGN.md.
- **Design review:** a Plan-agent review of this draft ran **before** approval. Its findings are folded in and marked
  "(review)". It found no lock cycle, and confirmed `Now()` → `STATEMENT_TIMESTAMP()`, the `Window` count with
  `for_list()`, view-only moderators running custom-permission actions, and that a `verified_false` post is never an
  active emergency.

## Context

Part 11C turns the `is_emergency` flag (columns since Part 4) into the feature of D5 / ANALYSIS f-1 / ARCHITECTURE §4b:
a fact post its author marks as an emergency is **pinned at the top of feeds for 24 h**, **checked first**, **shown in
violet**, and guarded: eligibility gates, 1 per 24 h, a lower report threshold, **no automatic FALSE while active** (a
moderator decides), and a FALSE emergency costs N + 3 and blocks emergency posting. Moderators get **Demote emergency**,
**Block / Unblock emergency posting** and an emergency filter; the queue and the pipeline take active emergencies first.
"Active" is always computed at read time (`is_active_emergency`); no job runs.

**Dependency check (2026-10-19).** 11C depends on **9** (Done 2026-10-11), **10** (Done 2026-10-13) and **11B** (Done
2026-10-19); their chains (8, 7B, 7, 6, 5, 4, 3, 2, 1, 0C, 0A/0B/0D, 11) are Done. Open but not blocking: Part 3
criterion 4, CI for Parts 2 to 11B (not reported), the Part 17 stub launch blocker.

**Workspace:** HEAD `9d7edce` ("Part 11B: Credibility score"), clean tree. HANDOFF said 11B was uncommitted; that line
was corrected when this plan was saved (2026-10-20).

**Already in place (no schema change needed for posts or users):** `posts.is_emergency` / `emergency_expires_at` /
`emergency_demoted_at` with checks `posts_post_emergency_fact_only`, `posts_post_emergency_expiry` and the partial
indexes `posts_pending_queue_idx`, `posts_pinned_emerg_idx`; `users.emergency_blocked_until`; the six PlatformSettings
limits; `posts/emergency.py: is_active_emergency` and `emergency_active` on the post object; `ActionKind`
`emergency_demoted` / `emergency_blocked`; the admin's Emergency column and fieldset; the ledger's `emergency_false`
(N+3) and `repost_emergency_false`; frontend `Toggle tone="tertiary"`, `EmergencyBadge` (the task's "EmergencyChip"),
the violet stripe from `emergency_active`, `FeedResponse.pinned/pinned_total` (typed, dropped by every fetcher).

## Your decisions (2026-10-19)

1. **Block / Unblock emergency posting: moderators and up.** A new permission `moderation.block_emergency_posting`,
   granted to the Moderators group (seniors inherit it). Nobody but a superuser may block a superuser or themselves.
2. **How a block ends:** the automatic block from a FALSE emergency **lifts by itself when that FALSE label is
   overturned**, unless another block still stands (a manual block, or another FALSE emergency). A manual block lasts
   as long as the automatic one (`emergency_false_cooldown_days`, 30). A logged **Unblock emergency posting** lifts
   every block early.
3. **The pinned section's ×** collapses it into one line ("2 emergency posts pinned · Show"), remembered for the tab
   (sessionStorage, per feed) until a post that wasn't pinned before appears. Nothing becomes unreachable.
4. **The post object gains `emergency_demoted`** (true when a moderator ended the priority early: Demote, or Mark FALSE
   while active): 25 keys. The detail page uses it to say "Priority ended." or "Priority removed by a moderator."

## Scope

**In:** eligibility and creation; the fact-quota `emergency` block; the routing and report-threshold branches; the
processor order; pinned lists on Recent and Following and `GET /api/v1/posts/emergencies/`; `emergency_demoted`; the
Demote action, Mark FALSE's emergency effects, automatic block and lift, manual Block / Unblock; the admin filter and
ordering; migrations `moderation.0006` / `0007`; `User.save` protecting `emergency_blocked_until`; the composer
toggle, warning and confirmation; `PinnedEmergencies`; the detail-page note; the `/dev/ui` examples; one E2E spec;
docs and `docs/test-command.md` Part 11C (both guides).

**Not in 11C:** the `emergency_demoted` notification (Part 13; the hook point is recorded), the `/how-it-works`
emergency text (15), follower/email/push alerts (out of scope by f-1), search (12).

## Design

### 1. Data and migrations (`apps/moderation` only)

- `ActionKind.EMERGENCY_UNBLOCKED = ("emergency_unblocked", "Emergency posting unblocked")`; `moderation_action_valid`
  widened (as Part 11 did for `kept_removed`; the reverse fails once such a row exists).
- `ModerationAction.blocked_until` (timestamptz, null): the end of an `emergency_blocked` row's block. Check
  `moderation_action_blocked_until_kind`: set **iff** `action='emergency_blocked'`.
- `ModerationAction.Meta.permissions = [("block_emergency_posting", "Can block or unblock emergency posting")]`.
- **`moderation.0006_emergency_actions`** (schema: the kind, the column, the check, the permission option);
  **`moderation.0007_emergency_permission`** (data: its own frozen lists, `create_permissions` first as `0002` does,
  grants the permission to Moderators; the reverse returns to `0005`'s lists). `roles.MODERATOR_PERMISSIONS` gains it
  (`test_roles.py` pins the lists).
- No posts, users or reputation migration. **`User.save`**: a full save also skips `emergency_blocked_until` (the
  Part 11B rule for the score: allauth's `set_password` and the admin form save whole rows and would write back a
  block read earlier). It is written only with `.update()` by `moderation.services`.
- **An account's block rows are strictly increasing in time** (review): written under the account's lock with
  `created_at = max(now, the account's last block row + 1 µs)`, the ledger's rule. Without it, a manual Unblock that
  committed first but stamped a later time than a waiting Mark FALSE would make `standing_block_end` read the new
  automatic block as already lifted, and the column would end null.
- Invariant (review): a post-linked block row loses its `post` only through a hard delete of the post, which happens only
  with the account's deletion (then `subject_user` is nulled too); PostAdmin can't delete posts. So `post` null means a
  manual block for every living account.

### 2. Pure rules

**`apps/posts/emergency.py`** (stays pure):
- `active_emergency_q(now)`: the `Q` twin of `is_active_emergency` (one rule in two forms, Part 9's pattern; a test
  compares them over every state the checks allow).
- `EmergencyReason` (the six codes of §4b) and `refusal(user, *, quota, cfg, now) -> EmergencyRefusal(reason,
  next_allowed_at) | None`, first failing rule wins, in §4b's order:

| Reason | Fails when | `next_allowed_at` |
|---|---|---|
| `unverified` | `not user.is_email_verified` | null |
| `account_too_new` | `user.created_at > now − min_age_days` (exactly N days old passes) | `created_at + min_age_days` |
| `score_too_low` | stored `reputation_score < emergency_min_reputation` (public or not) | null |
| `blocked` | `emergency_blocked_until > now` (a block ending now is over) | `emergency_blocked_until` |
| `daily_limit` | emergencies in the rolling 24 h (deleted and removed ones count) ≥ `emergency_posts_per_day` | the (used − limit + 1)-th oldest + 24 h; **null when the limit is 0** (paused) |
| `fact_quota` | `quota.remaining == 0` | `quota.next_slot_at` (null when fact posts are paused) |

**`apps/pipeline/routing.py`:**
- `apply_pipeline_result`: `decisive = … and not (verdict == FALSE and is_active_emergency(post, now))`. A FALSE on a
  pending active emergency enters review (`pipeline`, `pre_review_status=pending`, `ENTERED_REVIEW`); a late FALSE
  already gives `both` for every post (Part 9).
- `apply_report_threshold`: `cfg.emergency_report_threshold` while active, else `cfg.report_threshold`.

**`apps/moderation/rules.py`:**
- `Act.DEMOTE_EMERGENCY`; `NOT_ACTIVE_EMERGENCY = Refusal("not_active_emergency", "not an active emergency")`.
  `refusal(act, post, moderator, *, appeal, now)`: **`now` becomes a required keyword** (as `appeal`); call sites: the
  admin's buttons and confirmation, `_perform`, `test_rules.py`, `test_sequences.py`. Demote's order: `deleted` →
  `own_post` → `not_active_emergency`, as **its own branch before the catch-all** "not under review" (review: that
  branch would refuse it everywhere); any status (a removed post is never active); it resolves nothing.
- `transition`: Mark FALSE on an active emergency also sets `emergency_demoted_at = now` (`Effect.demoted = True`).
  Demote sets it too: kind `emergency_demoted`, from = to = the status, no reports, no appeal. Mark verified, Dismiss,
  Remove and Escalate leave the priority alone (Remove hides it; a Restore inside the 24 h pins it again).
- **Account acts** (pure): `AccountAct.BLOCK_EMERGENCY` / `UNBLOCK_EMERGENCY`,
  `account_refusal(act, target, moderator, *, block_days, now)`: `superuser_account`, `own_account` (superusers
  exempt, as `UserAdmin._may_touch`), Block: `no_block_length` (0 days), `already_blocked` (the current block already
  ends at or after `now + block_days`); Unblock: `not_blocked`.
- `standing_block_end(rows)`: from an account's `emergency_blocked` / `emergency_unblocked` rows in time order, the
  **latest end (the max) among the blocks still standing**, or None. An unblock with no post lifts every earlier block;
  an unblock with post P lifts P's earlier blocks only. **`users.emergency_blocked_until` always equals this** (tested
  after every step of the random walks).

### 3. Creating an emergency (`posts.services.create_post`, `PostListView.post`)

- Serializer: `is_emergency` on an opinion → 400 `{"is_emergency": ["Only fact posts can be emergencies."]}`; the
  service raises the same `ValidationError`; the DB check is the last line. `EmergencyUnavailable` and 400
  `emergency_unavailable` go.
- `_lock_author` **returns the locked row** with fresh `created_at`, `is_email_verified`, `reputation_score`,
  `emergency_blocked_until`, so a block or a Mark FALSE that committed first is seen and two emergencies at once let one
  through. Its lock becomes **`FOR NO KEY UPDATE`** (review; Part 11B's rule for user locks): it still serialises two
  posts, a block and `settle_post`, but no longer makes every commit-time `KEY SHARE` on the author wait (ARCHITECTURE
  §3's "FOR UPDATE" is corrected). The fact-quota race test's patch (`lambda author: None`) must return the author.
  `fact_quota()` reads `(created_at, is_emergency)` in its one query (`FactQuota.emergency_times`).
- Emergency: `emergency.refusal(...)` → `EmergencyNotAllowed(reason, next_allowed_at)`; otherwise
  `is_emergency=True`, `emergency_expires_at = now + emergency_duration_hours`.
- The view answers **403** `{"detail": <plain words>, "code": "emergency_not_allowed", "reason", "next_allowed_at"}`
  as a hand-built `Response`: an `APIException` with a dict detail would turn a null `next_allowed_at` into "None".
  The order stays authentication → permissions (`email_unverified`) → throttle → validation → service.
- `GET /api/v1/me/fact-quota/` gains `"emergency": {"allowed", "reason", "next_allowed_at", "block_days"}`;
  `block_days` is the current `emergency_false_cooldown_days`, so the composer's consent sentence states the real
  length. Same queries as today (the user, the fact times).

### 4. Pipeline, processor, reports

- `processor.due_posts(now)` orders by `Case(When(active_emergency_q(now), then=1), default=0).desc()`, then
  `created_at`, `id` (an expired or demoted emergency waits its turn).
- `reports.file_report` already passes the locked post and `now` to `apply_report_threshold`: no change there.
- `record_pipeline_result`: after `settle_post` on `labelled`, `moderation.services.block_after_emergency_false(post,
  rows, now=now, moderator=None)` (a function-level import; `moderation.services` imports `posts.services`). Only an
  expired or demoted emergency can be labelled FALSE by the pipeline.

### 5. Moderation services (`apps/moderation/services.py`, the only writer of audit rows and of the block)

- `_perform`: passes `now` to `refusal`; `_SAVED_FIELDS` gains `emergency_demoted_at`. Demote still calls
  `settle_post` like every action but Escalate (it finds nothing: two reads, no lock), so ARCHITECTURE §4's rule stays
  true (review). After the action's audit row and `settle_post`:
  - Mark FALSE with `effect.demoted` → an `emergency_demoted` row (same moderator, `now + 1 µs`);
  - `block_after_emergency_false(...)` when `settle_post` wrote a new row with `kind == emergency_false` and
    `user_id == author` (a FALSE that changed the label: a re-sent verdict, an upheld label appeal or a Dismiss back to
    FALSE writes none, so it never blocks twice);
  - `lift_after_overturn(...)` when the post is an emergency, `settle_post` wrote reversal rows for the author, and
    `ReputationEvent.objects.filter(pk__in=<their reverses_id>, kind=EMERGENCY_FALSE).exists()` (review: a reversal row
    doesn't carry the reversed row's kind; one primary-key lookup, only on an overturn; a Restore reverses
    `post_removed` and must not lift). `settle_post` is unchanged.
- `block_after_emergency_false(post, rows, *, now, moderator)`: `emergency_false_cooldown_days` 0 → nothing. Lock the
  author `FOR NO KEY UPDATE` (post first, then user: `settle_post` already holds it, since it wrote the author's row);
  append `emergency_blocked` (post P, `subject_user` A, moderator or null, `blocked_until` = the row's time + days,
  notes "Automatic: the emergency post was labelled FALSE."); set the column to `standing_block_end(...)` with
  `.update()`. It runs inside the caller's transaction (the pipeline's is `durable=True`): it never opens a durable
  block and raises outside a transaction, as `settle_post` does (review).
- `lift_after_overturn(post, rows, *, now, moderator)`: under the author's lock, if P has a standing block, append
  `emergency_unblocked` (post P, the overturning moderator, notes "Automatic: the FALSE label was overturned.") and
  recompute the column.
- `block_emergency_posting(user_id, *, moderator, notes="", now=None)` and `unblock_emergency_posting(...)`: lock the
  account (no post is involved, so "never a user before a post" holds), take `now` **after** the lock, check
  `rules.account_refusal` under it → `ActionRefused`, append the row (post null), recompute. A manual block lasts
  `emergency_false_cooldown_days`.

### 6. Feeds and the emergencies endpoint

- **Recent** (`PostListView.get`, every page): `results` = `visible().exclude(active_emergency_q(now))`. The first page
  (the `cursor` parameter absent **or empty**, review) gets `pinned` = the 3 newest active emergencies (`-created_at`,
  `-id`) through `for_list(viewer)`, and `pinned_total` from a `Window(Count)` in the **same query**. One `now` for
  the filters and the serializer (`context["now"]`). Queries: first page 2 anonymous / 3 signed in (one more than
  today), later pages unchanged.
- **Following** (`social.feed`): pinnable = active emergencies by `followed ∪ me` (`following_emergencies(user, now)`).
  The posts side excludes active emergencies; the reposts side excludes reposts **of pinnable posts** (`post_id NOT IN`
  the pinnable ids, inside the same SQL; both columns are non-null). Reposts of other emergencies stay, with the chip
  ("reposts never pin"). The first page's `pinned` is computed on every first-page request (cache hits included); the
  cached keys were filtered when cached. **Accepted limit, recorded in §9** (review): an emergency that ends while a
  follower's first page is cached is in neither list until the TTL (30 s) ends. First page +1 query.
- **All pinnable posts leave `results`**, not only the 3 shown: `pinned_total` counts them and "Show all" lists them
  (§4b "pinned posts are left out of results").
- Profiles and bookmarks are unchanged (`pinned: []`; emergencies show inline with the chip).
- **`GET /api/v1/posts/emergencies/?feed=recent|following`** (default `recent`; `following` needs a login → 401; any
  other value → 400 `{"feed": [...]}`; `never_cache`): `{results: [Post], next_cursor}`, newest first, 20 a page up
  to 50 (`TimestampCursorMixin, CursorPagination`). The literal route sits before `posts/<str:post_id>/`. Queries:
  recent 1 / 2, following 2.
- `FeedPagination.envelope(results, next_cursor, *, pinned=(), pinned_total=0)`.

### 7. Post object

`emergency_demoted` = `emergency_demoted_at is not None` → **25 keys** (the key-pinning tests and fixtures change).
Tombstones keep it, as they keep `is_emergency`.

### 8. Admin

- `PostAdmin.ordering`: an **active-emergency-first** expression (Postgres `STATEMENT_TIMESTAMP()` via `Now()`) before
  `-report_count`, queue-since, `-created_at`; the Emergency column sorts by it.
- `EmergencyFilter` ("emergency": Active / Ended). Choosing it leaves the queue (`LEAVES_THE_QUEUE`), so a moderator can
  find an active emergency that isn't under review and demote it.
- `ACTIONS["demote_emergency"]`: "Demote emergency" (button and bulk action, internal notes only, offered only when
  `refusal` allows; dropped from an opinions-only list like the verdicts, review). The confirmation table gains an
  Emergency column; Mark FALSE's "after" cell adds "priority ends" for an active emergency and "author blocked N days"
  when it will block (an emergency not already FALSE before the review, and N > 0; review).
- `UserAdmin`: **Block emergency posting** and **Unblock emergency posting** (`permissions=["block_emergency"]` →
  `moderation.block_emergency_posting`), each with a confirmation page
  (`moderation/admin/confirm_account_action.html`: account, current block, new end, skipped with reasons, internal
  notes) calling the services. Like PostAdmin's actions they drop malformed ids first, post back the shown, capped ids
  and never trust `select_across` (review). A list filter "Emergency posting" (Blocked / Not blocked);
  `emergency_blocked_until` stays read-only.
- **An account's block history** (review: manual rows have no post, so no post page shows them, and the full log is
  seniors-only): a read-only inline on the account's page listing its `emergency_blocked` / `emergency_unblocked`
  rows (time, action, moderator, post link, until, notes), for holders of the new permission; the full log
  (`ModerationActionAdmin`) gains a `subject_user` column and search.

### 9. Frontend

- **Types:** `Post.emergency_demoted`; `FactQuota.emergency: {allowed, reason, next_allowed_at, block_days}`;
  `CreatePostBody.is_emergency?`; `FeedPage.head?: {pinned, pinnedTotal}`.
- **`lib/post-display.ts` `emergencyShown(post)`** = `emergency_active && status ∉ {verified_false, removed}`: the
  status poll doesn't carry `emergency_active`, but a FALSE always ends the priority, so a polled FALSE or removal ends
  the violet look at once. Used by `post-card-props.ts` and `PostDetail`.
- **`useCursorFeed`** gains an optional first-page `head` (kept on Load more, cleared on a reset); `fetchRecentFeed` /
  `fetchFollowingFeed` return it.
- **`features/posts/PinnedEmergencies.tsx`** (Stitch b1:123-148, copy rewritten under D8), **presentational with a
  card slot** (review: the `/dev/ui` test renders without an AuthProvider, and the feed's cards need one): `<section
  aria-labelledby>`, a `bolt` tile, "EMERGENCY POSTS" (`font-label-code text-tertiary uppercase`), "Pinned for a
  limited time and checked first.", up to 3 cards rendered by the caller (HomeFeed passes the feed's own `FeedCard`,
  exported from `FeedList.tsx`, so the overlay and the action bar work; the gallery passes plain `PostCard`s), "Show
  all (N)" when `pinnedTotal` > shown → `fetchEmergencies(feed)` in place (+ Load more), × → the one-line bar with
  **Show**. sessionStorage key `rz:pinned-collapsed:<feed>` holds the collapsed ids, written only on × (so
  `auth.spec.ts`'s empty-storage check holds), read through `useSyncExternalStore` with a null server snapshot and
  try/catch (no hydration mismatch, no ref read or effect `setState`, the MEMORY lint rules; review). A post the poll
  finds FALSE or removed leaves the section.
- **`HomeFeed`**: each tab's panel renders its own `PinnedEmergencies` above its `FeedList`; polling includes the shown
  pinned posts; a new emergency from the composer goes into the pinned section (both tabs), a normal post into the
  lists as today; `FeedList` takes `alreadyShown` (the pinned ids) so `visibleItems` hides a later repeat, and with
  pinned posts above an empty list its empty state reads "No other posts yet." (review).
- **Composer** (`draft.ts`, `ComposerModal.tsx`, `ComposerProvider.tsx`, `messages.ts`, new `features/posts/
  emergency-copy.ts` for the reason → words):
  - Fact only: b2's emergency row (copy rewritten: "Emergency" / "Pinned at the top of feeds and checked before other
    posts."), `Toggle tone="tertiary" label="Emergency post"`; disabled with the reason in plain words
    (`aria-describedby`) when `quota.emergency.allowed` is false, and until the quota has loaded.
  - On: b2's warning box (its classes; copy: "Use this only for urgent safety or public-health news.") and a
    required `Checkbox` with the task's sentence ("I understand emergency posts are checked first, and misuse lowers my
    credibility score and blocks emergency posting for 30 days.", the number from `block_days`, the clause dropped at
    0). Unticked at submit → "Tick the box to confirm." under it, focused and linked: `Checkbox` merges a caller's
    `aria-describedby` with its description's id instead of overwriting it (review).
  - The button reads **"Post emergency, will be checked"** (`bolt`, still `secondary`: DESIGN.md keeps primary actions
    blue): the shipped fact label is "Post fact, will be checked" with a comma (§10), so task.md's dash follows it
    (review; recorded as a deviation).
  - **`is_emergency: true` is sent only when the toggle is on and `quota.emergency.allowed`** (review: the draft
    outlives the modal, and a refetched quota can say no); a toggle the quota no longer allows is turned off while
    rendering (the "adjust state while rendering" pattern), never in an effect.
  - A 403 `emergency_not_allowed` → failure kind `emergency` showing the server's `detail` (review: `normalizeError`
    keeps only `detail` and `code` of such a body; the composer already shows the server's detail for
    `fact_quota_exceeded`); the quota is refreshed, so the toggle's hint shows the reason, and the toggle and tick turn
    off (the text is kept). Switching to Opinion turns both off. Success toast: "Posted. It's pinned while it's
    checked."
- **`PostDetail`**: `EmergencyNote` (neutral `text-on-surface-variant`, no violet) in the claim card under the author
  row, for `is_emergency && !emergencyShown && status ≠ removed`: "Posted as an emergency on Oct 19, 2026. Priority
  ended." or "… Priority removed by a moderator." (`emergency_demoted`). New `formatDate` (UTC) in `lib/format.ts`.
- **`/dev/ui`**: the composer mock gains the checkbox and the label; a `PinnedEmergencies` example, open and folded.

### 10. E2E (`frontend/e2e/emergency.spec.ts`, no sign-up)

A helper reads the developer's emergency settings through the shell (the E2E backend uses their PlatformSettings).

1. A fresh `seedAuthor` account: Fact → the toggle is disabled with "Your account is too new…" (skipped when the
   developer's minimum account age is 0; review).
2. The flow: `seedAuthor(prefix, { ageDays })` (new option, older than the developer's
   `emergency_min_account_age_days`; the test is **skipped with a message** when the developer's settings make an
   emergency impossible: emergency or fact posts at 0 a day, or a minimum score above 50). Log in, compose a `#false`
   fact, turn the toggle on, tick, post; /home Recent shows it in the pinned section with EMERGENCY; `processPost` →
   `under_review`; reload → still pinned, UNDER REVIEW; `moderate(id, "mark_false")` → reload → gone from the pinned
   section, and the list shows it FALSE · REVIEWED without the chip. A `finally` demotes it through the shell if a step
   failed, **ignoring a refusal** (already demoted or FALSE) so the real failure stays visible (review), so the
   developer's Recent feed isn't left with an active emergency. `ModeratorAction` gains `demote_emergency`.

## Defaults where the docs are silent (approved with the plan)

- **Any FALSE label on an emergency blocks** its author (a moderator's, or the pipeline's after expiry or demotion):
  §2 "set automatically after a FALSE emergency", f-1 "after one of your emergencies ends FALSE". The trigger is the
  new `emergency_false` ledger row, so it is idempotent. The −3 already works that way.
- Mark FALSE on an active emergency writes three audit rows (`marked_false`, `emergency_demoted`, `emergency_blocked`)
  1 µs apart, so the history reads in order; the ledger links to the `marked_false` row.
- Demote: moderators and up (`posts.change_post`, as every post action), not on your own post, internal notes only.
- One refusal code for an ineligible emergency (403 `emergency_not_allowed` + `reason`), including a full fact quota;
  a paused setting (0 a day) is its reason with a null `next_allowed_at` (copy "…are paused right now."). No seventh
  code.
- The daily limit counts deleted and removed emergencies (the fact quota's principle).
- **No "short shared cache" for Recent's pinned list** (§9 named one): it is one indexed query, and a cache of ids would
  still need a query to load the posts with the viewer's flags. Recorded as a deviation.
- The status poll is unchanged; the chip rule above covers a polled FALSE or removal. Expiry while a page is open
  shows on the next load (no client timer, no hydration risk).
- `block_days` is added to the fact-quota emergency block (the composer's consent text must not state a wrong length).
- Remove doesn't demote; a Restore within the window pins the post again (its removal was the mistake).
- The UserAdmin list filter, the confirmation pages and the `EmergencyNote` placement are as above.
- **Tests pin the six emergency settings** (review: the seed comes from the developer's `.env`): an
  `emergency_settings` fixture in the root `conftest.py` (saves the row, heals with `get_or_create`, like
  `fact_limit`), made autouse in the posts, pipeline, moderation, reputation, reports and social test packages.

## Files

**Backend:**
- New: `moderation/migrations/0006_emergency_actions.py`, `0007_emergency_permission.py`,
  `moderation/templates/moderation/admin/confirm_account_action.html`, `posts/pinned.py` (the pinned queries, the
  `Window` count), tests listed below.
- Changed: `posts/{emergency,services,views,serializers,exceptions,urls,pagination}.py`,
  `pipeline/{routing,processor}.py`, `moderation/{models,rules,services,admin,roles}.py`, `social/{feed,views}.py`,
  `accounts/{models,admin}.py`, `posts/tests/factories.py` (an `emergency` trait).
- Also changed: root `conftest.py` (`emergency_settings`) and the six app test conftests (autouse).
- Existing tests that change on purpose:
  - `posts/tests/{test_services,test_api_create,test_api_feed,test_api_quota,test_api_detail}.py`: the 11C refusal,
    `POST_KEYS` (25), the envelope, the quota body; the race test's `_lock_author` patch returns the author.
  - `pipeline/tests/test_routing.py` (its `post()` helper gains the emergency fields), `test_routing_pipeline.py` and
    `test_queue.py` (the "until 11C" tests).
  - `moderation/tests/test_rules.py` (`make_post`, `ALLOWED` and the oracle gain the emergency states and Demote; the
    oracle's catch-all "dismiss" branch must not swallow Demote; `now=` everywhere), `test_roles.py`, `test_models.py`,
    `test_admin_queue.py`.
  - `reputation/tests/test_services.py` (≈ lines 94-141), `test_api_events.py` (≈ 115-135) and `test_sequences.py`
    (`control_for` ≈ 333-349, the walk's emergency ≈ 161-170, the coverage test ≈ 366-379): they label an **active**
    emergency FALSE through the pipeline, which now enters review (review). They use an expired emergency or Mark FALSE,
    and the coverage test still reaches both emergency kinds.
  - `social/tests/{test_api_feed,test_api_feed_reposts}.py`, `accounts/tests/test_user_save.py`.
- Frontend tests that change on purpose: `PostDetail.test.tsx` (≈ 120-133 shows EMERGENCY on a `verified_false` post,
  a state that can't exist: it moves to `verified_true`, plus a test that FALSE hides it; review),
  `app/dev/ui/page.test.tsx` (the new gallery examples), the 25-key fixtures in `features/posts/test-helpers.tsx`,
  `components/ui/Checkbox.test.tsx` (the merged `aria-describedby`).

**Frontend:**
- New: `features/posts/{PinnedEmergencies,EmergencyNote}.tsx`, `features/posts/emergency-copy.ts`, their tests,
  `e2e/emergency.spec.ts`.
- Changed: `lib/api/types.ts`, `lib/post-display.ts`, `lib/format.ts`, `components/ui/Checkbox.tsx`,
  `features/posts/{useCursorFeed,posts-api,HomeFeed,FeedList,feed-items,post-card-props,PostDetail,ComposerModal,
  ComposerProvider,draft,messages,test-helpers}.ts(x)`, `features/social/social-api.ts`,
  `features/dev/StitchSections.tsx`, `e2e/helpers.ts`. No change to `lib/api/client.ts`.

**Docs:** ARCHITECTURE §2/§3/§4/§4b/§8/§9/§10, ANALYSIS c-45 (+ f-1 note), STRUCTURE, MEMORY, `task.md` (criteria,
decisions and deviations, both status spots, notes in 13/15/16/17), `docs/test-command.md` Part 11C (both guides),
HANDOFF, this plan's status line.

## Steps (each ends green before the next)

0. Verify the workspace (HEAD, clean tree, Docker up); baselines `pytest`, `npm test`, E2E count.
1. Pure rules + tests: `posts/emergency.py` (Q twin, eligibility), `routing` branches, `moderation/rules.py` (Demote,
   `now`, account acts, `standing_block_end`); update `test_rules` / `test_sequences` call sites.
2. Models + migrations 0006/0007 (`ruff` right after), `roles.py`, `User.save`; migrate, roll back to 0005, migrate.
3. Creation: serializer, `_lock_author`, `fact_quota`, `create_post`, the 403, the quota block; API + race tests.
4. Pipeline / processor / reports wiring + tests.
5. Moderation services: Demote, Mark FALSE effects, block / lift / manual block / unblock + service and race tests.
6. Feeds, `emergency_demoted`, the emergencies endpoint + query-count tests.
7. Admin: ordering, filter, Demote, UserAdmin Block / Unblock + admin tests.
8. Frontend: types, display rule, `useCursorFeed` head, fetchers, `PinnedEmergencies`, HomeFeed, composer, detail note,
   gallery + unit tests; lint, tokens, typecheck, format.
9. E2E spec + helpers; the whole suite in dev and `CI=1` mode.
10. Mutation checks (backend and frontend, nothing else running meanwhile, MEMORY's rule); docs; test-command Part 11C
    (Linux blocks run verbatim, PowerShell written); `task.md`, MEMORY, HANDOFF.

## Tests

- **Pure:** `test_emergency.py`: the Q twin over every state; the eligibility matrix (each reason, the order, each
  `next_allowed_at`, the inclusive edges: exactly N days old, score exactly 40, a block ending now, the 24 h window
  edge, the limit lowered, 0 = paused). `test_routing*.py`: every new §4 row with a controlled `now` (pending active
  FALSE → review; TRUE → label; weak → review; expired or demoted FALSE → label; a late FALSE on an active emergency
  under review for reports → `both`, explicitly (review); the report threshold active / expired / demoted / removed).
  `test_rules.py`: Demote's table over every state × emergency state; Mark FALSE demotes only when active; `now`
  required; account refusals; `standing_block_end` cases.
- **Services:** creation (expiry stored, each refusal, `unverified` through the service and the quota endpoint since
  the API's permission answers first, counts toward the fact quota, deleted and removed emergencies count, opinion
  refused by the service and by the DB check, the lock sees a block committed meanwhile); two emergencies at once → one
  (threaded); Mark FALSE on an active emergency → unpinned, blocked 30 days, 50 → 38, three audit rows,
  `pending_changes` empty; on an expired one → blocked, not demoted; an upheld label appeal → no second block; an
  overturned one → lifted, but kept when a manual block or another FALSE emergency still stands; **a Restore of a
  removed FALSE emergency doesn't lift** (review); the pipeline FALSE after expiry → blocked with a moderator-less row;
  cooldown 0 → no block; Demote; manual Block / Unblock (the max rule, refusals, rows, account rows strictly
  increasing). Threaded (`transaction=True`, 10 runs): **a Mark FALSE and a manual Unblock of its author at once → the
  block stands and the column equals `standing_block_end`** (review); a Block and an emergency post at once (the post is
  refused or made first); a Mark FALSE while the author posts (no deadlock).
- **Processor:** active emergencies before older pending posts; expired / demoted ones in normal order.
- **Reports:** 2 counting reports send an active emergency to review; after expiry it needs 5.
- **API:** create (201 body, 400, 403 per reason with `next_allowed_at`), the quota block per reason; Recent pinned (max
  3 newest, `pinned_total`, every pinnable post absent from every page of `results`, pinned only on the first page,
  23 h 59 min pinned / 24 h 01 min not by placing posts in time, demoted / removed / deleted / opinion never); Following
  (followed + me only, reposts of pinned posts left out, reposts of others kept, a cache hit still pins fresh); the
  emergencies endpoint (scopes, 401, 400, order, cursor); 25 keys; query counts for each list.
- **Admin:** active emergencies first; the filter leaves the queue; Demote offered only on active emergencies, its
  confirmation and row; Block / Unblock for a moderator, a senior and a superuser, refused on a superuser and yourself,
  non-staff 403, rows written; `test_roles` lists = migration 0007.
- **Sequences:** the random walks gain emergency posts, Demote and blocks; after every step `pending_changes` is empty
  and the block column equals `standing_block_end` of the account's rows.
- **Frontend:** `emergencyShown`, `formatDate`, `emergency-copy`, `useCursorFeed` head, `PinnedEmergencies` (≤ 3, Show
  all, ×, the bar, storage only on ×, re-opens on a new id, a polled FALSE leaves), `HomeFeed` (per tab; a new emergency
  goes to the section), `FeedList` (`alreadyShown`), composer states (Fact only, each disabled reason, warning,
  checkbox, label, unconfirmed error, payload, refusal turns it off), `EmergencyNote` (expired / demoted / none), the 25-key
  fixtures. E2E as §10.

## Verification

- Backend (venv in every call): `ruff check .`, `ruff format --check .`, `python manage.py makemigrations --check
  --dry-run`, `python manage.py check`, `pytest`; the threaded files 10 runs in a row; `recompute_reputation --check`
  on the dev database.
- Frontend: `npm run lint`, `lint:tokens`, `typecheck`, `format:check`, `npm test`,
  `NEXT_PUBLIC_GOOGLE_CLIENT_ID= npm run build`, `npm run test:e2e` (dev and `CI=1`).
- Headless Chromium at 1280 and 390 px: the composer states, the pinned section (open, folded, Show all), a card after
  Mark FALSE, the detail notes; Django Admin: the queue order, the filter, Demote, Block / Unblock pages.
- `docs/test-command.md` Part 11C: the Linux blocks extracted and run verbatim against live Django, output diffed.

## Stop conditions

- A change that would need a posts or users migration, a new dependency or service, or a `design/` edit: stop and ask.
- A test that shows the post → user lock order can't hold, or a deadlock in the race tests: stop and report.
- An existing test failing for a reason the plan doesn't name: stop and report rather than adjust it.
- Anything that touches the access-token storage rule or would write to storage before a click.

## Follow-ups to record (not done here)

- **Part 13:** notify `emergency_demoted` from `_perform` (Demote, and Mark FALSE when `effect.demoted`).
- **Part 15:** the `/how-it-works` emergency section.
- **Part 16:** the pinned query per first page and the Following reposts side's `NOT IN` under load;
  `posts_pending_queue_idx` no longer serves the processor's `Case` ordering (it still serves the filter); emergency
  abuse with real data.
- **Part 17:** with the stub in production, a late FALSE on an expired emergency also blocks its author (part of the
  existing launch blocker).
