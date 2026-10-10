# Plan: Part 8, Reporting & threshold

- **Status:** APPROVED by the user (Sanjoy Rozario) on 2026-10-10, together with the three decisions and the
  defaults below. Saved here and linked from `HANDOFF.md`. **IMPLEMENTED 2026-10-10** (Claude, Sonnet 5.5), as
  written. Deviations: see `task.md` Part 8 and `docs/agents/HANDOFF.md` (none of substance: the focus after a
  server field error moved into an effect, `ReportButton` also hides on the session user's id, and the appendix's
  items A1 and A2 were **not adopted**; A2 is recorded for Part 9). Drafted 2026-10-10 by Claude (Opus 5.5).
- **Implement with:** Sonnet 5.5 · high (task.md).
- **Evidence (read-only):** HANDOFF, MEMORY, `task.md` Part 8 (+ the Part 7/7B records), ARCHITECTURE
  §2/§3/§4/§4d/§5/§8/§9/§10, ANALYSIS (b-5, c-2, c-3, c-5, the d1 and ActionBar rows), STRUCTURE, DESIGN.md, Stitch
  d1/b1/b3, the 7B plan, two Explore passes (backend patterns; frontend primitives, buttons, E2E). A Plan-agent review
  of the locking and routing design was still running when the plan was approved, so **none of its findings are in
  this plan**. The lock choice, the duplicate check, the deadlock reasoning and the deterministic race tests below
  were worked out directly against the code (`social.services.repost`, `delete_post`, the 7B lock-wait test).

## Context

Part 8 lets a verified user report a post once, and sends a post to human review when enough **counting** reports
arrive inside a time window, while the post stays visible (guide §6; ARCHITECTURE §5; ANALYSIS c-2). It also creates
the pure routing functions (`merge_flag`, `enter_review`, `apply_report_threshold`) that Parts 9, 10, 11 and 11C build
on, so their behaviour must match the §4 table exactly.

**Dependency check (2026-10-10).** Part 8 depends only on **Part 5** (`[x] Done (2026-10-09)` in the summary table and
its section); its chain (4, 1, 0C, 0A/0B/0D, plus 2 and 3) is Done, and so are 6, 7 and 7B. Open, not blocking: Part 3
criterion 4 (the real-Google check) and CI for Parts 2 to 7B. **Workspace:** HEAD `416fcae` ("Implemented Part 7B…"),
tree clean; Docker Postgres + Redis up and healthy. HANDOFF still calls 7B "uncommitted" (the user committed it): step 0 fixes that text.

**Already in place:** `Post.report_count`, `flagged_reason`, `pre_review_status` (Part 4), the four report settings
in `PlatformSettings` (0A), the `report` 10/h throttle rate (`settings.py:184`, pinned by `test_settings.py`),
`"reported_by_me": False` hard-coded in `PostSerializer` (`apps/posts/serializers.py:137`), `Post.reported_by_me` in
the frontend type (`lib/api/types.ts:58`), the `RadioCardGroup` primitive built for d1 (`components/ui/RadioCard.tsx`),
`Modal`'s `footerTone="plain"` (made for this modal), a dev-gallery mock of the modal with the b-5 reason labels
(`features/dev/StitchSections.tsx:126-295`), and a client test for the `already_reported` 409 (`client.test.ts:160`).

**Your decisions (2026-10-10):**
1. **Report is a flag button**, as Stitch draws it, not an overflow menu (task.md's wording): a `flag` icon beside the
   bookmark on every card (b1's right-hand group) and "Report" in the post page's action row (b3). No menu component.
2. **What makes a young account's report count:** at least one post that isn't removed, or one comment that isn't
   hidden. Posts and comments the reporter **deleted still count** ("deleting undoes nothing"); content a moderator
   took down (removed posts, hidden comments) doesn't.
3. **FALSE posts follow the docs, and reposts are closed meanwhile:** at the threshold a FALSE post goes to
   UNDER REVIEW with `pre_review_status = verified_false` (Dismiss restores FALSE), and a post that is under review
   **after being FALSE** can't be reposted (409 `cannot_repost_false`). One condition is added to Part 7B's repost
   check.

## Scope

**In:** `reports.Report` + migration `reports.0001`; `POST /api/v1/posts/{id}/report/`; `apps/pipeline/` with
`routing.py`; `posts.services.record_report` (the status write); `reported_by_me` in `with_engagement`; read-only
`ReportAdmin`; the repost refusal of decision 3; `ReportButton`, `ReportModal` and the action bars; tests, E2E, docs.

**Not in Part 8:** the emergency threshold (11C adds `emergency_report_threshold` to `apply_report_threshold`, as
task.md says; no post can be an emergency before 11C), notifying the author (13), moderator actions, Dismiss and the
review queue (10), the `report_upheld` credit (11B), withdrawing a report, reporting comments or users (ANALYSIS
dropped them), any new dependency, service or env variable.

## What the research found (all handled below)

- **`apps/pipeline` must be made with `startapp` now.** `apps/posts/emergency.py:1-6` notes that a bare package
  folder would make Part 9's `startapp` refuse; task.md puts `routing.py` in Part 8. So Part 8 runs
  `startapp pipeline apps/pipeline`, keeps only what it uses, and adds it to `INSTALLED_APPS` (Part 9's management
  command needs that anyway). `emergency.py`'s docstring and STRUCTURE are updated.
- **Stitch and task.md disagree on placement** (decision 1). DESIGN.md's glyph list has `more_horiz` for overflow
  menus but no `flag`; b1/b3 use `flag`. Recorded in ANALYSIS like Part 7's `favorite`.
- **No public field tells the page that an under-review post was FALSE** (`pre_review_status` is never public, §9),
  so `repostBlockedReason` can't pre-disable that case: the button stays enabled, the server answers 409
  `cannot_repost_false`, and the existing rollback toast says "Posts labelled FALSE can't be reposted."
- **Report rows reference `reporter`, not `user`,** so `with_engagement`'s `mine()` helper takes the field name.
- **Fresh accounts are 0 h old** (`UserFactory`), below the 24 h minimum: tests set `created_at` in the past or give
  the reporter content. The settings seed comes from the developer's `.env`, so tests pin the four report settings
  with a fixture that **saves** the row (as `fact_limit` does) and E2E reads the threshold instead of assuming 5.
- **Part 9 follow-up found here:** §6's processor selects `status='pending'` only, so a pending fact that reports send
  to review before the pipeline runs would never be checked. Recorded for Part 9 (select `pipeline_checked_at IS NULL`
  facts under review with `pre_review_status='pending'` too, or similar); not changed here.

## Design

### Model (`apps/reports/models.py`, migration `0001_initial`)

`Report` per §2: uuid pk; `post` FK CASCADE (`db_index=False`: both composite indexes lead with `post`); `reporter` FK
users CASCADE (keeps its index: account deletion and export look reports up by reporter); `reason` (`ReportReason`:
`inaccurate`, `misleading`, `harassment`, `spam`, `other`, labels from b-5); `details` `CharField(500, blank)`;
`status` (`ReportStatus`: `open`, `dismissed`, `actioned`, default `open`); `counts_toward_threshold` bool (no
default: the service always decides); `resolved_by` FK users SET_NULL null; `resolved_at` null; `created_at`
`default=timezone.now` (tests place reports in time). Named constraints: `reports_pair_unique (post, reporter)`,
`reports_reason_valid`, `reports_status_valid`, `reports_other_needs_details` (not `other` with empty details),
`reports_resolution_consistent` (`open` ⇔ `resolved_at IS NULL`; Part 10 sets both). Index
`reports_post_created_idx (post, created_at)` (§2). `ruff check --fix . ; ruff format .` right after
`makemigrations`; review `sqlmigrate reports 0001`.

### Routing (`apps/pipeline/routing.py`, pure, no I/O)

- `merge_flag(existing, new)`: `None + x = x`; `x + x = x`; `pipeline + reports = both` (either order);
  `both + pipeline|reports = both`; `appeal + pipeline|reports = appeal`; `None|appeal + appeal = appeal`;
  `pipeline|reports|both + appeal` raises `ValueError` (appeals start only from `verified_false` or `removed`, never
  from a post already under review, so this is a bug signal); an unknown value raises `ValueError`.
- `enter_review(post, reason)`: exactly §4's pseudo-code (already under review → merge the flag; otherwise store
  `pre_review_status`, set `under_review` and the reason).
- `apply_report_threshold(post, counting_reports, cfg, now) -> bool`: if `post.status != removed` and
  `counting_reports >= cfg.report_threshold`, call `enter_review(post, REPORTS)`; returns True only when the post
  **entered** review (Part 13's "notify the author" hook). `now` is unused until 11C adds the emergency threshold.

### Service (`apps/reports/services.py`) and the status write (`apps/posts/services.py`)

`file_report(*, reporter, post_id, reason, details, now=None)` inside `transaction.atomic()`:
1. Lock the post: `Post.objects.visible().select_for_update(no_key=True, of=("self",))…first()`; none → `PostNotFound`
   (404). `FOR NO KEY UPDATE` serialises reports with each other and with status writes (deletes, moderator actions)
   but not with the `FOR KEY SHARE` that likes, comments and bookmark inserts take (the 7B lesson). A report that
   waited on a delete or removal re-checks the row and finds nothing (404).
2. Your own post → `CannotReportOwn` (403 `cannot_report_own`).
3. Already reported (any status, the pair is unique for life) → `AlreadyReported` (409 `already_reported`). The post
   lock serialises two reports by one person, so `exists()` after it is race-free; the unique constraint is the DB
   guard (no `IntegrityError` catch: it would be dead code).
4. `counts_toward_threshold(reporter, cfg, now)`: `reporter.created_at <= now − min_age` **or** an `exists()` of their
   posts excluding `removed` (deleted included; served by `posts_author_created_idx`) **or** of their comments with
   `is_hidden=False` (deleted included; the author FK index). Short-circuits in that order.
5. Insert the report (`created_at=now`).
6. `n` = the post's reports with `status='open'`, `counts_toward_threshold`, `created_at >= now − window` (inclusive,
   §5), the new one included.
7. `posts.services.record_report(post, counting_reports=n, cfg=cfg, now=now)`: `report_count += 1` (every report
   counts toward the lifetime counter), `routing.apply_report_threshold(…)`, `save(update_fields=["report_count",
   "status", "flagged_reason", "pre_review_status", "updated_at"])`; returns the "entered review" flag. Its docstring
   says the caller must hold the row lock inside `atomic()`. This keeps every `Post` write in `posts/services.py`.

`cfg = get_platform_settings()` once per call. Redis is never used for the count.

### API (`apps/reports/{views,serializers,urls,exceptions}.py`)

`POST /api/v1/posts/{id}/report/` `{reason, details?}`: `IsAuthenticated` + `IsEmailVerified`, `ScopedRateThrottle`
scope `report`, `never_cache`, POST only (GET is 405). Order: 401 → 403 `email_unverified` → 429 → malformed id 404 →
400 → service 404 / 403 `cannot_report_own` / 409 `already_reported` → **201 `{"reported": true}`**.
- 400 messages: missing or unknown reason → "Choose a reason."; `details` trimmed, over 500 code points → "Keep it to
  500 characters."; `other` with blank details → `{"details": ["Tell us what's wrong."]}`. Undeclared fields
  (`status`, `counts_toward_threshold`, `reporter`) are ignored.
- 409 message "You already reported this post."; 403 "You can't report your own post."
- The throttle counts every request that passed authentication and permissions (a 400, 404, 403 own or 409 included,
  as repost's 409); a 401 or `email_unverified` never counts. The 11th in an hour is 429 with `Retry-After`.
- Route in a new `apps/reports/urls.py`, included under `api/` in `rumor_zero/urls.py`.
- **Reuse:** `parse_post_id` (`apps/posts/views.py:36`), `IsEmailVerified` (`apps/accounts/permissions.py`),
  `get_platform_settings` (`apps/core/services.py`), the `RepostView` shape (`apps/social/views.py:293`); in tests
  `run_together` (`apps/accounts/tests/conftest.py:276`), `auth_client`/`verified_user`, `PostFactory`'s traits
  (`removed`, `deleted`, `under_review`, `fact`, `verified_pipeline`), `CommentFactory(hidden/deleted)`, and a
  `report_settings` fixture modelled on `fact_limit` (`apps/posts/tests/conftest.py:28`: it saves the row).

### `reported_by_me`

`with_engagement` gains `reported_by_me = Exists(Report.objects.filter(post=OuterRef("pk"), reporter=viewer))` for a
signed-in viewer, `Value(False)` otherwise (the unique pair's index serves it); `engagement_defaults` sets False;
`PostSerializer` reads it strictly. One more correlated subquery in the same SELECT, so every pinned query count stays
the same. The status endpoint and the comment list are untouched.

### Repost refusal (decision 3, `apps/social/services.py`)

After the "already reposted" check: refuse `status == verified_false` **or** (`status == under_review` and
`pre_review_status == verified_false`) with `CannotRepostFalse`; `.only(…)` gains `pre_review_status`. An existing
repost is still 200. Covers appeals too (Part 11's label appeal has the same shape).

### Admin

`ReportAdmin` read-only (no add, change or delete; the `RepostAdmin` pattern): list `post`, `reporter`, `reason`,
`status`, `counts_toward_threshold`, `created_at`; filters status, reason, counts, created; search reporter username;
`list_select_related`; newest first; `show_full_result_count = False`. Viewing needs `reports.view_report` (a
superuser today; Part 10 grants moderators and adds the PostAdmin inline).

### Frontend (`src/features/reports/`, the action bars)

- **Reuse, don't rebuild:** `ACTION_CLASSES` (`features/social/LikeButton.tsx:15`), `waitText`
  (`features/posts/messages.ts:19`), `loginRedirectFor` (`lib/auth/route-guard.ts:14`), `RadioCardGroup`, `Modal`
  (`footerTone="plain"`), `Textarea` (`maxCount`), `Alert`, `VerdictStripe`, `useToast`, `api` from `lib/api/client.ts`.
- `reasons.ts` (the five reasons: b-5 labels and the gallery mock's descriptions), `reports-api.ts`
  (`reportPost(id, {reason, details})`), `messages.ts` (`REPORT_MESSAGES`, `reportFailureMessage`).
- **`ReportButton`** (mirrors `LikeButton`'s states, `ACTION_CLASSES`, `useId` hint): session loading → inert
  look-alike; visitor → a link to `/login?next=/p/<id>` named "Report" with title "Log in to report"; **your own post
  → nothing** (also on your removed post); reported (`reported_by_me` or a local flag after success or 409) → filled
  `flag` in `secondary`, `aria-disabled`, name "You reported this", a click toasts "You already reported this post.";
  unverified → `aria-disabled` with the hint "Verify your email to report posts." and the Part 2 toast; otherwise
  opens the modal. Card: icon only (`sr-only` name, `title` "Report this post"); detail: the word "Report"
  ("Reported" when done) from `sm` up, inside the accessible name. State is seeded from props and re-synced with the
  "adjust state while rendering" pattern. The modal is mounted on the **first** open and then kept (a feed doesn't
  mount 20 dialogs up front, and `Modal` returns focus only from the dialog's `close` event, which an unmount would
  skip). The flag stays **one `<button>` element** across "Report" and "You reported this", so focus can return to it
  after a successful report (a test pins it).
- **`ReportModal`** (`Modal`, title "Report this post", eyebrow "Report", icon `flag`, `footerTone="plain"`): the post
  preview (d1's neutral-stripe card: name, `@handle`, the claim clamped to three lines, italic for opinions);
  `RadioCardGroup` "Why are you reporting this post?" with **no reason preselected** (d1 preselects the first; a default
  biases reports); a `Textarea` "Details" with `maxCount={500}` and the hint "Optional." / "Required for Something
  else."; an info `Alert` "What happens next": "When several people report a post, a moderator reviews it. The post
  stays visible meanwhile, and nothing is removed automatically."; footer `fingerprint` + "Reports are private. The
  author is never told who reported.", Cancel, **Submit report** (loading). The form sits in a `fieldset disabled`
  while sending; the modal can't be closed mid-request (as `DeletePostModal`). Submit checks everything, shows every
  problem and focuses the first (the reason error is a `<p role="alert">` under the group, as `ComposerModal` does for
  the post type, and focus goes to the first radio; `RadioCardGroup` itself is unchanged). Outcomes: 201 → close, toast "Report sent. Thank you.", `onReported`; 409
  `already_reported` → the same with "You already reported this post."; 403 `email_unverified` → stays open with a
  warning `Alert` "Verify your email to report."; 400 → errors on their fields; 404 → close and toast "This post is no
  longer available."; 429 → error `Alert` with `waitText`; network or 503 → error `Alert`, choices kept.
- **`PostActions`**: card right-hand group = bookmark + report (`gap-space-md`, b1); detail row = bookmark + Report.
  Its `post` type widens to include `author`, `content`, `post_type`, `reported_by_me`. Repost items report the
  original. `PostDetail` needs no new state (the button keeps its own; Part 7 showed a mirrored patch is dead code);
  its "8 adds report" comment is updated.

## Defaults where the docs are silent (approved with the plan)

The 201 body and codes above; the check order; `cannot_report_own` as a new 403 code; reports are permanent (no
DELETE); every visible status can be reported (pending, published, verified either way, under review); the reasons are
the same for facts and opinions; no reason preselected; the modal copy above; the `fingerprint` and `flag` glyphs;
`reports_resolution_consistent` and `reports_other_needs_details` as DB checks; the "entered review" return value;
no `IntegrityError` catch; the reporter's view doesn't change status until the next load (the answer doesn't reveal
whether the threshold was crossed); the throttle counting rule above.

## Files

- **Backend new:** `apps/reports/{__init__,apps,models,services,serializers,views,urls,admin,exceptions}.py`,
  `migrations/0001_initial.py`, `tests/{__init__,factories,conftest,test_models,test_services,test_counting,
  test_threshold,test_races,test_api_report,test_reported_by_me,test_admin,test_no_network}.py`;
  `apps/pipeline/{__init__,apps,routing}.py`, `tests/{__init__,test_routing}.py`.
- **Backend changed:** `rumor_zero/settings.py` (`INSTALLED_APPS`), `rumor_zero/urls.py`, `apps/posts/services.py`
  (`record_report`), `apps/posts/serializers.py` (strict `reported_by_me`), `apps/posts/emergency.py` (docstring),
  `apps/social/engagement.py`, `apps/social/services.py` (repost refusal), and tests:
  `social/tests/test_engagement_counts.py` (seventh strict attribute), `test_services_repost_bookmark.py` /
  `test_api_repost.py` (the new refusal), `posts/tests/test_api_create.py` (still false on create).
- **Frontend new:** `src/features/reports/{reasons,reports-api,messages}.ts`, `ReportButton.tsx`, `ReportModal.tsx`,
  a test for each.
- **Frontend changed:** `features/social/PostActions.tsx` (+ test; `PostActions.test.tsx:43` asserts the bar's
  second child *is* the bookmark button and changes on purpose: it becomes a group holding bookmark + report), `features/posts/PostDetail.tsx` (comment; + test
  for the button), `e2e/social.spec.ts` (+2 tests), `e2e/helpers.ts` (`seedReports`).
- **Docs:** ARCHITECTURE §2 (reports constraints and indexes), §3 (`report` throttle note), §4d (the new refusal),
  §5 (counting rule, order, codes), §8 (`ReportAdmin`), §9 (endpoint, `cannot_report_own`, counts paragraph), §10
  (`ReportButton`, `ReportModal`); ANALYSIS (a c-40 entry: decisions 1-3, the `flag` glyph, the ActionBar row);
  STRUCTURE; MEMORY (durable facts only); `task.md` (criteria, deviations, both status spots); this plan's status
  line; `docs/test-command.md` (a "Part 8" section in **both** guides and the intro line); HANDOFF.

## Steps (each ends green before the next)

0. Verify HEAD and a clean tree; `docker compose ps`; fix HANDOFF's stale 7B text; save this plan under
   `docs/agents/plans/part-8-reporting-threshold.md` and link it.
1. `startapp` both apps (folder first), `name = "apps.<name>"`, trim boilerplate, `INSTALLED_APPS`.
2. `routing.py` + `test_routing.py` (exhaustive tables, no DB).
3. `Report` model + migration (ruff-normalised) + `test_models.py`.
4. `posts.services.record_report`, `reports.services` + counting, threshold and race tests.
5. Serializer, view, URL, exceptions + `test_api_report.py` (codes, messages, throttle).
6. `reported_by_me` in `with_engagement` + serializer + tests; the repost refusal + tests.
7. `ReportAdmin` + `test_admin.py`; `test_no_network.py`. Backend full run, ruff, `makemigrations --check`.
8. Frontend: reasons, API, messages, `ReportModal`, `ReportButton`, `PostActions`, tests; lint, typecheck,
   lint:tokens, format:check, vitest.
9. E2E (`seedReports`, two tests), full E2E in dev and CI mode; `npm run build`.
10. Mutation checks (below), scripted-browser check at 1280 and 390 px (card bar, modal, phone), Django Admin.
11. Docs, `test-command.md` (Linux blocks extracted and run verbatim against live Django), `task.md`, HANDOFF.

## Tests

**Backend**
- `test_routing.py`: every `merge_flag` pair (5 existing × 3 new, plus bad values); `enter_review` from pending,
  published (opinion), verified_true, verified_false (each stores its `pre_review_status`) and from under review with
  each flag; `apply_report_threshold` below / at / above the threshold, threshold 1, removed ignored, under review
  (reports, both, appeal) unchanged, pipeline → both, the return value.
- `test_models.py`: each constraint (pair, reason, status, other-needs-details, resolution), defaults, CASCADE and
  SET_NULL.
- `test_counting.py`: age exactly at the minimum counts, a microsecond younger doesn't, minimum 0; young with a post
  (each non-removed status, deleted counts, removed and removed+deleted don't), with a comment (shown, deleted counts;
  hidden and hidden+deleted don't), with nothing; someone else's content doesn't help.
- `test_threshold.py` (time-controlled `now`): a report exactly `window` old counts, a microsecond older doesn't;
  dismissed, actioned and non-counting reports don't count; other posts' reports don't; each §4 report row (pending,
  published, verified_true, verified_false → under_review with the right `pre_review_status`; under review
  pipeline → both; reports/both/appeal unchanged); threshold − 1 leaves the post alone; `report_count` counts every
  report; `updated_at` moves; the post stays visible (detail 200, still in Recent).
- `test_races.py` (`transaction=True`, `run_together`; tasks catch the domain errors and return a marker, because
  `run_together` asserts no thread raised): the same person twice → one row, one `AlreadyReported`; six concurrent
  reporters from zero → `under_review` and `report_count == 6`; plus deterministic lock-wait tests in the 7B style
  (`threading.Event`, `assert not done.wait(0.5)`; template `social/tests/test_services_repost_bookmark.py:212`): another transaction holds the post with `FOR NO KEY UPDATE` and then deletes or
  removes it → the waiting report is 404; it holds the lock with `threshold − 2` counting reports committed while two
  reports wait → the post ends under review. (The holder must take `NO KEY UPDATE`, not plain `FOR UPDATE`: then,
  without the service's lock, both reports would insert and count `threshold − 1` before either commits and only
  block at the final UPDATE, so the mutation fails the test every time instead of sometimes.)
- `test_api_report.py`: 201 body; 401; 403 `email_unverified`; 404 malformed, unknown, deleted, removed (author
  too); 403 `cannot_report_own`; 409 `already_reported`; each 400 message, 500 emoji accepted, 501 refused, trimming,
  undeclared fields ignored; GET 405; `never_cache`; the 11th request in an hour is 429 with `Retry-After` (real
  requests, rates bound at import) and a 401/403 doesn't count.
- `test_reported_by_me.py`: true only for the reporter, false for visitors and others, in Recent, Following, profile,
  bookmarks and the detail; false on create; the existing constant-query tests still pass (they pin 1/2, 3/4 …).
- Social: the strict-attribute parametrisation gains `reported_by_me`; repost of an under-review-after-FALSE post is
  409, of an under-review-after-pending or -after-verified_true post is 201, an existing repost still 200.
- `test_admin.py`: read-only (no add/change/delete), list and detail pages for a superuser, a moderator without the
  permission gets 403.

**Frontend:** `ReportButton` (every state, the toasts, re-sync from props, the modal opens and returns focus);
`ReportModal` (five reasons, none preselected, each validation message and focus, counter, the locked form, every
outcome above); `reports-api`, `messages`; `PostActions` (flag in the card's right group, Report in the detail row,
none on your own post); `PostDetail` (Report for others, none for the owner or a tombstone).

**E2E** (`social.spec.ts`, the two shared accounts; no new sign-up):
1. Report flow: the fan posts an opinion (so a fresh account's report counts), `seedPost` makes a third person's post,
   `seedReports(id)` makes `threshold − 1` seeded verified users whose `created_at` is `min_age + 1 h` in the past
   and files their reports through `reports.services.file_report` (the threshold and minimum age are read in the
   shell from `get_platform_settings()`, because the E2E backend uses the developer's seed); the fan opens the post, the empty submit shows "Choose a reason.", "Something else"
   without details shows "Tell us what's wrong.", then a valid report toasts and the button reads "You reported
   this"; after a reload the badge is UNDER REVIEW, the claim is still shown and the button is still reported.
2. States: no flag on your own post; a visitor's flag is a link to `/login?next=…`.
3. The existing phone test ("a card with four actions and the bookmarks page fit a phone", `social.spec.ts:465`)
   becomes five actions: the flag is visible and the page still has no horizontal overflow at 390 px.

**Mutation checks** (a rule removed by hand, a test must fail): the row lock, the visible filter, own, duplicate,
each counting branch and its removed/hidden exclusions, the window edge (`>=`), `status='open'`, the
`counts_toward_threshold` filter, `report_count`, `update_fields` entries, each `merge_flag` rule, the removed guard,
the throttle scope, `reported_by_me`, the new repost condition; frontend: no preselection, the other-needs-details
check, own-post hiding, the reported state, the unverified state, focus.

## Verification (end to end)

- `cd backend && source .venv/bin/activate && python -m pytest` (all), `ruff check .`, `ruff format --check .`,
  `python manage.py makemigrations --check --dry-run`, `python manage.py check`, `sqlmigrate reports 0001`.
- `cd frontend && npm run lint && npm run typecheck && npm run lint:tokens && npm run format:check && npm test`,
  `npm run test:e2e` (dev and `CI=1`), `npm run build`.
- Live: `runserver` + `next dev`; curl the report codes; seed `threshold − 1` reports and watch the post turn UNDER
  REVIEW and stay in Recent; the modal at 1280 and 390 px; Django Admin's read-only Reports list.

## Stop conditions

Stop and ask if: a migration would alter an existing table; the lock design deadlocks or a race test is flaky; a
pinned query count changes; a new dependency, service or env variable seems needed; the E2E suite would need more
sign-ups; anything requires touching Parts 9 to 11C beyond the notes below.

## Follow-ups to record (not done here)

- Part 9: the processor must also check pending facts that reports sent to review (`pre_review_status='pending'`).
- Part 10: `PostAdmin` report inline, Dismiss (reports → `dismissed`, resolution fields), moderator permission on
  `ReportAdmin`, the queue's report-count ordering. 11B: `report_upheld`. 11C: the emergency threshold branch.
  13: notify the author when `record_report` returns True.
- Part 16: the `report` rate; the dev gallery's three copies of the reason list (`StitchSections`, `FormSections`,
  `reasons.ts`).

## Appendix: design-review findings received after approval (2026-10-10)

The Plan-agent review of the locking and routing design finished **after** the user approved this plan. Its findings
are recorded here and are **not part of the approved plan** until the user accepts them. The implementer reads this
appendix first and asks the user about items A1 and A2 before step 2; everything in B only confirms or sharpens what
the plan already says and needs no new decision.

**A. Would change the plan (ask the user):**
- **A1. `enter_review` refuses a removed post** (`ValueError`). The plan follows §4's pseudo-code (no guard; the guard
  is in `apply_report_threshold`). Both callers already guard it, so reaching it would be a bug.
- **A2. Decision 3 can leak a hidden pipeline verdict once Part 9 exists.** §4 (row "under_review (reports), pipeline
  result arrives late, decisive") sets `pre_review_status=verified_false` on a reported post whose FALSE label was
  never public; the new repost refusal would then answer "Posts labelled FALSE can't be reposted." and reveal it. In
  Part 8 alone `pre_review_status=verified_false` only comes from a post that was publicly FALSE, so nothing leaks
  yet. Either record it as a Part 9 follow-up (Part 9 narrows the condition), or change the condition now.

**B. Consistent with the plan (clarifications):**
- Keep `FOR NO KEY UPDATE`; the visibility re-check after a lock wait works (Postgres re-evaluates the WHERE of the
  locking statement), so keep the `visible()` filters **in the locking query** and add a "waited on a delete/remove →
  404, no Report row, `report_count` unchanged" test (template `social/tests/test_services_repost_bookmark.py:238`).
- No `IntegrityError` catch (dead code next to the lock); §5's sentence "the unique constraint turns a duplicate into
  409" is reworded to say the locked `exists()` check does, the constraint being the last-resort guard.
- No deadlock: Django creates Postgres FKs `DEFERRABLE INITIALLY DEFERRED`, so the `KEY SHARE` on the reporter's user
  row is taken at commit, after the post lock (always post, then user). Part 11B must keep that order.
- An alternative deterministic lock test: seams `_lock_post()` and `_counting_reports()`, a fixture that sleeps after
  the count, three counting reports seeded at threshold 5, two reporters via `run_together` → `under_review`,
  `report_count == 5`; the control (lock swapped for a plain read) ends `published` with `report_count == 4` (the
  Python `+= 1` also loses an update without the lock). Pattern: `apps/posts/tests/test_services.py:217-259`. Either
  this or the plan's `NO KEY UPDATE` holder test is fine.
- **Never add an upper bound** (`created_at <= now`) to the window count: `now` is taken before the lock wait, so a
  report that waited can have a `now` older than a row already committed.
- Don't `.only()` the locked post (at most `defer("pipeline_result")`): 11C's `is_active_emergency` would load the
  missing fields one query at a time.
- `apply_report_threshold` returns True only when the status **changed** (a pipeline → both merge is not "entered").
- `merge_flag` also raises for `new=None`; Part 11 must not allow a label appeal on a post under review whose
  `pre_review_status` is `verified_false`, or `merge_flag` needs a rule for it.
- Account age is `now - reporter.created_at` (checked first, no query); then two `LIMIT 1` queries.
- Extra boundary tests: `window_hours=1` (read from settings), the new report counts itself, a non-counting report
  still adds 1 to `report_count`.
- Repost refusal: `apps/social/services.py:181` gains `"pre_review_status"`, line 192 the new condition, after the
  existing-repost and own-post checks; `repost-rules.ts`'s doc comment and test note that the page can't see this case.
- `reported_by_me`: the pinned query counts (`test_engagement_counts.py:153-176`, `test_api_detail.py:159-167`,
  `test_api_feed.py:263`, the 7B list tests, `test_feed_cache.py`) stay; `POST_KEYS` already lists it; update the
  docstrings at `engagement.py:1-8` and `serializers.py:99-103`.
- Map DRF's `invalid_choice` and `null` on `reason` to "Choose a reason." too; the domain errors are `APIException`s
  (validation errors carry no `code`).
- §5's pre-check list puts "not the author" before "post visible": reword it to the plan's order (your own removed
  post is a 404, as with reposts). Also fix §4's "Part 9" wording next to `is_active_emergency` (`apps/pipeline` now
  exists).
- `ReportAdmin` is superuser-only in practice until Part 10 grants permissions.
- Deleting a reporter cascades their report, but `report_count` (lifetime) stays and the post stays under review:
  document in §2; Part 14 must not decrement it.
- More follow-ups: Part 9's processor must not hold the post lock across its 20 s HTTP call (reports, reposts and
  deletes would wait); Part 10's bulk dismiss/action sets `resolved_at` (and `resolved_by`) with `status`, or
  `reports_resolution_consistent` fails; Part 13 writes the notification in the same transaction when
  `record_report` returns True; `task.md` Part 8's "overflow menu" line is corrected when the part is closed
  (decision 1).
