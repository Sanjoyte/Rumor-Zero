# Rumor Zero: live handoff

Update this file at meaningful checkpoints and before switching between Claude Code and Codex.
Keep it concise and factual. The incoming agent must verify it against the current files and
read-only git output.

## Active work

- **Part:** **Part 11B (Credibility score) is done** (2026-10-19), **uncommitted**: you review the diff and commit.
  Parts 0A, 0B, 0D, 0C, 1, 2, 3, 4, 5, 6, 7, 7B, 8, 9, 10, 11 and 11B are done (Part 11 committed as `71c5e14`, Part 10 as `582905b`).
  Part 1 CI is green (user-reported 2026-10-06); **Part 2, 3, 4, 5, 6, 7, 7B, 8, 9, 10, 11 and 11B CI have not been reported yet.**
  - **Part 3 acceptance criterion 4 is still pending you:** the real-Google sign-in check
    (`docs/test-command.md` Part 3, steps 7 and 8). It doesn't block anything.
  - **Part 17 has a launch blocker from Part 9** (your decision 2026-10-11): decide how production gets verdicts
    before deploying; the stub lets an author self-label with `#true`, and from Part 11B that feeds the public score.
- **Machine:** the **Linux PC** (Ubuntu/Debian/Mint, bash). `backend/.venv` and
  `frontend/node_modules` exist there.
- **Owner:** none (Claude stopped after Part 11B, as asked).
- **Phase:** Part 11B implemented and validated on top of HEAD `b3df8eb` ("Planning for Part 11B"). No server is running;
  the Docker containers are up. The dev database is migrated (`reputation 0001`, `moderation 0005`).
- **Next action:** **you** review and commit Part 11B (and push, so CI runs). Then plan Part 11C, 11D or 12 (all three
  depend on 11B) in a fresh session.
- **Approved plan (implemented):**
  [`docs/agents/plans/part-11B-credibility-score.md`](plans/part-11B-credibility-score.md) (approved 2026-10-13,
  implemented 2026-10-14 to 2026-10-19)
- **Previous plans:**
  - [`part-11-appeals-removed-tombstones.md`](plans/part-11-appeals-removed-tombstones.md), implemented 2026-10-13
    (committed as `71c5e14`);
  - [`part-10-human-review-panel.md`](plans/part-10-human-review-panel.md), implemented 2026-10-13 (committed as
    `582905b`);
  - [`part-9-pipeline-stub-routing.md`](plans/part-9-pipeline-stub-routing.md), implemented 2026-10-11 (committed as
    `4da6514`);
  - [`part-8-reporting-threshold.md`](plans/part-8-reporting-threshold.md), implemented 2026-10-10 (committed as
    `0d8c331`; its appendix A2 is resolved by Part 9's decision 1);
  - [`part-7b-bookmarks-reposts.md`](plans/part-7b-bookmarks-reposts.md), implemented 2026-10-10 (committed as `416fcae`);
  - [`part-7-likes-comments.md`](plans/part-7-likes-comments.md), implemented 2026-10-10 (committed as `c562e70`);
  - [`part-6-profiles-follows-following-feed.md`](plans/part-6-profiles-follows-following-feed.md),
    implemented 2026-10-09 (committed as `15c1d8a`);
  - [`part-5-post-detail-sharing-deletion-polling.md`](plans/part-5-post-detail-sharing-deletion-polling.md),
    implemented 2026-10-09 (committed as `b5b8089`);
  - [`part-4-posts-composer-recent-feed.md`](plans/part-4-posts-composer-recent-feed.md),
    implemented 2026-10-09;
  - [`part-3-continue-with-google.md`](plans/part-3-continue-with-google.md), implemented
    2026-10-08;
  - [`part-2-email-verification-reset.md`](plans/part-2-email-verification-reset.md), implemented
    2026-10-07;
  - [`chore-linux-machine-switch.md`](plans/chore-linux-machine-switch.md), done 2026-10-06;
  - [`part-1-auth-core.md`](plans/part-1-auth-core.md), done 2026-10-03.
- **Last updated:** 2026-10-19 by Claude (Opus 5.5), Part 11B done.

## Completed checkpoints

- 2026-10-14 to 2026-10-19 (Claude, Opus 5.5): **Part 11B implemented** (uncommitted). Started from HEAD `b3df8eb` ("Planning
  for Part 11B", committed by you), a clean tree that matched this file (it still said the plan was uncommitted). Baselines
  measured first: `pytest` 2965 passed, `npm test` 1692 passed. The machine restarted mid-way (2026-10-19): the Docker
  containers had stopped and the scratchpad was cleared; I started the containers again (`docker compose up -d`), nothing
  in the repository was lost, and the interrupted guide run had written nothing (no `part11b-` accounts).
  - **Backend** (`backend/`):
    - New app `apps/reputation/`: `models.py` (`ReputationEvent`, append-only, four named checks,
      `repevent_user_created_idx`; admin names "Credibility" / "credibility events"), `scoring.py` (pure: weights, `score`
      half up in quarter units, slots, `desired`, `changes`), `services.py` (`settle_post`, `pending_changes`, `totals_for`;
      users locked sorted with `FOR NO KEY UPDATE` after the post, the cap and totals read after the lock, strictly
      increasing times), `serializers.py` / `views.py` / `urls.py` (the two endpoints), `admin.py` (`ReputationEventAdmin`,
      `ReputationInline`, `events_url`), `management/commands/recompute_reputation.py`, `migrations/0001_initial.py`,
      `tests/` (conftest, factories and 9 files: scoring, models, services, races, sequences, recompute, two API, admin).
    - Also new: `moderation/migrations/0005_reputation_permission.py`, `accounts/tests/test_user_save.py`.
    - Changed: `accounts/models.py` (a full save skips the two score columns), `accounts/admin.py` (the Credibility
      field), `moderation/{rules,services,admin,roles}.py` (`Effect.credits_reporters`, `settle_post` in `_perform`, the
      inline, the permission), `posts/services.py` (`settle_post` on `labelled`), `reports/services.py`
      (`resolve_open_reports` returns the reporters), `social/{serializers,views}.py` (`verified_count`, rows' `counts`,
      `public_score`), `rumor_zero/{settings,urls}.py`.
    - Existing tests changed on purpose: `moderation/tests/{test_rules,test_roles,test_admin_queue,test_admin_appeals}.py`,
      `posts/tests/test_services_pipeline.py` (counts the post's lock only), `social/tests/test_api_lists.py` (row keys,
      `counts.verified`), `reports/tests/test_no_network.py` (also scans `apps/reputation`).
  - **Frontend** (`frontend/`): new `src/features/reputation/CredibilityBadge.tsx` (+ test); changed `ProfileHeader`,
    `UserRow`, `lib/api/types.ts` (`UserRowData.counts`), `features/social/test-helpers.tsx` and the tests of
    `ProfileHeader`, `UserRow`, `PostCard`, `FeedList` (never on cards); `e2e/credibility.spec.ts` and `seedCheckedFacts`
    in `e2e/helpers.ts`.
  - **Docs:** ARCHITECTURE §2/§3/§4/§4a/§8/§9/§10, ANALYSIS c-44 (and f-5, the component row), STRUCTURE, MEMORY (one
    Part 11B entry), `task.md` (criteria, decisions and deviations, both status spots, notes in 11C, 11D, 12, 14 and 16),
    the plan's status line, and `docs/test-command.md`: a "Part 11B" section in **both** guides (10 steps each) and one
    entry in its intro line; nothing else touched.
  - Two migrations (`reputation.0001_initial`, `moderation.0005_reputation_permission`), no new dependency, service or env
    variable; `design/` untouched. **I did not read `backend/.env` or `frontend/.env.local`** (Django read them itself;
    one shell printed only whether `ADMIN_URL_PATH` is the default, as a yes/no). The dev database was migrated, rolled
    back to `moderation 0004` / `reputation zero` and applied again; every `part11b-` account I made was deleted.
  - **User decisions and defaults** are in `task.md` Part 11B and the plan.
  - **Validation (all green):**
    - Backend: `ruff check .` (All checks passed!), `ruff format --check .` (268 files already formatted),
      `makemigrations --check --dry-run` (No changes detected), `manage.py check` (no issues), `pytest` **3400 passed**
      (2965 before), `pytest apps/reputation` 405 passed, the threaded tests (`reputation/test_races.py`,
      `moderation/test_races.py`, `test_pipeline_interplay.py`, 35 tests) 10 runs in a row, `recompute_reputation --check`
      on the dev database ("Checked 1356 accounts: every stored score matches the ledger.").
    - **42 backend mutation checks**, 41 caught; the 42nd (settling on `updated_review`) is equivalent: `settle_post` reads
      the public status, which is still `under_review`. Three first-run survivors were missing tests, now added (the
      sample counting reversed rows, reversed rows reconciled again, an `appeal` block on a FALSE repost row). The
      deadlock test fails with a plain `FOR UPDATE` ("deadlock detected"), and the two "without the user lock" tests
      show the races the lock prevents. **11 frontend mutation checks**, all caught.
    - Frontend: `npm run lint`, `lint:tokens`, `typecheck`, `format:check` clean; `npm test` **1711 passed** (124 files;
      1692 before); `NEXT_PUBLIC_GOOGLE_CLIENT_ID= npm run build` OK; `npm run test:e2e` **41 passed** in dev mode and with
      `CI=1` (40 before), run again after the last change.
  - **Test-command notes:**
    - The section is `### Part 11B` inside each guide (the brief said `## Part <ID>`; the file's parts are `###`
      sections inside its two `##` guides, as Parts 3 to 11 did), in the same step shape as the other parts.
    - The file has **no comment marker** at its bottom (as in Parts 3 to 11): it ends with the last bullet of the
      Windows Part 11B section. (The brief asked to keep one; there is none to keep.)
    - The Linux blocks of steps 3 to 7 and 10 were **extracted from the finished doc by script and run verbatim** against
      live Django (the developer's own settings); their output was diffed with the doc's expected blocks (run id, token
      prefixes and counts normalised): **all six matched** (step 10 after removing a stray blank line from the recorded
      output). The browser steps 8 and 9 were checked with a headless-Chromium script at 1280 and 390 px (21 checks,
      screenshots looked at), not by a person. The **PowerShell blocks were not run** (no PowerShell here): they mirror
      Part 11's helpers (`Mk`, `Send`, `Fetch`) plus `Login` and `Rep`.
  - **Found and fixed on the way** (details in MEMORY and `task.md`): the reporter-credit guard let a TRUE outcome through
    (caught by the scoring tests); a removal credit can't survive a post that isn't removed, so a test's assumption was
    wrong; an admin inline also prints each row's `str()`; a test picking `.first()` of uuid rows was flaky until it
    filtered; the admin's "View events" check needed to wait for the navigation; the admin listed the ledger as
    "Reputation events" until the model and app got the UI's name, "Credibility".

- 2026-10-13 (Claude, Opus 5.5): **Part 11B planned and approved.** The plan is linked above.
  - **Starting point:** HEAD `71c5e14` ("Part 11: Appeals & removed-post tombstones", committed by the user), a clean
    tree. (The older text of this file said Part 11 was uncommitted; the user committed it in between.)
  - **Dependency check:** Part 11B depends on 7B (Done 2026-10-10), 10 and 11 (Done 2026-10-13); their chains (9, 8, 7,
    6, 5, 4, 3, 2, 1, 0C, 0A/0B/0D) are Done. Open but not blocking: Part 3 criterion 4, and CI for Parts 2 to 11.
  - **Research:** read-only only: direct reads of the docs (task.md, ARCHITECTURE §2/§3/§4/§4a/§8/§9/§10, ANALYSIS f-5/f-6,
    STRUCTURE, MEMORY), the moderation, posts, pipeline, reports, social and accounts code, allauth's `set_password`, the
    frontend profile header and user row, Stitch c1/c3 and DESIGN.md; a Plan-agent design review that finished
    **before** approval (its findings are in the plan, marked "(review)").
  - **Changed this session:** only the new plan file and this file. No code, no setup command, no `task.md` edit, no
    env file read, `design/` untouched.
  - **User decisions (2026-10-13):** a removal adds to the label's event (Restore reverses only the removal's events);
    the public `recent` list shows own-post events only; moderators and up can read the whole ledger in the admin
    (permission migration `moderation.0005`); the badge is neutral (no teal, no `verified` seal); Mark FALSE credits
    reporters only when the post wasn't already FALSE (Remove always credits); a reversed FALSE also reverses the
    reporters' credit; no backfill; the deciding moderator's own report earns nothing.
  - **Found during planning** (all handled in the plan): allauth's `set_password` does a full `user.save()`, which would
    write back a stale score (`User.save` will skip the two reputation fields); user locks must be `FOR NO KEY UPDATE`,
    not plain `FOR UPDATE` (the moderator's deferred FK `KEY SHARE` at commit could deadlock); the reporter cap must be
    read after the user lock; Python's `round` is banker's rounding (exact half-up in integer quarters instead);
    `posts/tests/test_services_pipeline.py:164` pins one `FOR NO KEY UPDATE`; `social/tests/test_api_lists.py` pins the
    row keys; `/how-it-works` is a placeholder without a `#credibility` anchor (Part 15).

- 2026-10-13 (Claude, Sonnet 5.5): **Part 11 implemented** (uncommitted). Started from HEAD `fec011f` ("Plan Part 11", committed by
  you), a clean tree that matched this file. `docker compose ps` showed **no containers running**: I started them
  (`docker compose up -d`).
  - **Backend** (`backend/`):
    - New in `apps/moderation/`: `Appeal` (OneToOne with `Post`, `AppealKind`, `AppealStatus`, the `ModerationAction.appeal` link,
      the `kept_removed` kind), migrations `0003_appeal` and `0004_appeal_permission` (its own frozen lists; the reverse returns to
      Part 10's), `exceptions.py`, `serializers.py`, `views.py` (`AppealView`: POST only, the `appeal` throttle for POST only),
      `urls.py`, `queries.py` (`with_appeal_fields`, `appeal_defaults`), and five new test files (`test_appeal_models`,
      `test_services_appeals`, `test_api_appeal`, `test_appeal_fields`, `test_admin_appeals`; `AppealFactory` in `factories.py`).
    - Changed: `rules.py` (`Restore`, `Keep removed`, the open appeal as a required keyword, `resolves_appeal`, the first-decision
      rule), `services.py` (`file_appeal`, `restore_post`, `keep_removed`, the appeal resolved in `_perform`, the after-commit kick for a
      restore to `pending`), `admin.py` (the queue holds removal appeals, `AppealFilter`, `AppealInline`, `AppealAdmin`, the two actions, the
      "in the queue since" expression), `models.py`, `roles.py`; `pipeline/routing.py` (`pipeline_had_its_say`), `posts/{models,
      serializers,views,services}.py` (`for_list` chains `with_appeal_fields`, 24 keys, `kick_pipeline_after_commit`),
      `social/{views,feed}.py` (the owner's profile lists their removed posts), `rumor_zero/urls.py`.
    - Existing tests changed on purpose: `test_rules` (rewritten), `test_models`, `test_roles`, `test_permissions`, `test_races`,
      `test_pipeline_interplay`, `test_admin_queue` (a resolved appeal on the busy post), `pipeline/test_routing`, the post-key
      tests (`test_api_create`, `test_api_detail`), `reports/test_reported_by_me`, `social/test_engagement_counts`,
      `social/test_api_user_posts`.
  - **Frontend** (`frontend/`): new `src/features/appeals/` (`AppealButton`, `AppealModal`, `AppealOutcome`, `appeals-api.ts`,
    `messages.ts` + tests), `posts/RemovedPostCard.tsx` + `Tombstone.tsx` (+ test); changed `PostDetail` (a removed post is its own
    branch; the button in the verdict card; the outcome beside it), `VerdictBlock` (a `footer` slot), `FeedList`, `PostCard` (the guard
    renders `Tombstone`), `types.ts` (`removal_reason`), `test-helpers`, `features/dev/StitchSections.tsx` (the author variants);
    `e2e/appeals.spec.ts` and `e2e/helpers.ts` (`seedAuthor`, `logIn`, `moderate`).
  - **Docs:** ARCHITECTURE §2/§4/§8/§9/§10, ANALYSIS c-43 (and the b-2 rows), STRUCTURE, MEMORY (three Part 11 entries), `task.md` (criteria,
    decisions, deviations, both status spots, notes in 11B and 13), the plan's status line, and `docs/test-command.md`: a "Part 11"
    section in **both** guides (12 steps each) and one number in its intro line; nothing else touched. The file has no comment marker
    at the bottom (none was ever there), so none was kept or added.
  - Two migrations, no new dependency, service or env variable; `design/` untouched. **I did not read `backend/.env` or
    `frontend/.env.local`** (Django and the apps read them themselves; the guide never prints a secret). The dev database was migrated,
    rolled back to `moderation 0002` and applied again, and every `part11-` account and test post I made was deleted (the audit rows
    stay with a blank moderator and post, as the log keeps its history).
  - **User decisions and defaults** are in `task.md` Part 11 and the plan.
  - **Validation (all green):**
    - Backend: `ruff check .` (All checks passed!), `ruff format --check .` (240 files already formatted), `makemigrations --check
      --dry-run` (No changes detected), `manage.py check` (no issues), `pytest` **2965 passed** (2709 baseline measured first); `pytest
      apps/moderation` 559 passed; the threaded tests (`test_races.py`, `test_pipeline_interplay.py`, 30 tests) 10 runs in a row.
    - **35 backend mutation checks**, every one caught after the fixes: no post lock, no duplicate check, any status appealable, a
      label appeal that doesn't enter review, a removal appeal that changes the status, `original_moderator` from `moderated_by`
      or for a pipeline FALSE, the audit row without the appeal link or `resolved_by`, the kick on every `pending`, the first-decision
      rule gone / applied to seniors / superusers / Escalate, Restore always to `pending` / never to review / keeping
      `pre_removal_status` or `escalated_at`, Keep removed leaving the flag, Remove not closing a label appeal, Mark verified
      upholding, Escalate on any removed post, Restore without the prior-status check, the queue without removal appeals, the removal
      reason from the oldest row / shown to others (query and serializer each alone), `appeal_status` and `can_appeal` leaking, the
      profile showing removed posts to everyone, the throttle on GET, the 201 re-read with `visible()`. Survivors that were real: the
      reason's two independent guards and the visitor's profile pages (tests added); equivalent: the appeal row lock and the explicit
      Escalate exemption (removed as dead code).
    - Frontend: `npm run lint`, `lint:tokens`, `typecheck`, `format:check` clean; `npm test` **1692 passed** (123 files; 1588 before);
      `NEXT_PUBLIC_GOOGLE_CLIENT_ID= npm run build` OK; `npm run test:e2e` **40 passed** in dev mode and with `CI=1` (38 before).
      **24 frontend mutation checks**, every one caught (after adding a test for an empty row under the verdict and making the modal
      single-flight with a ref).
    - `docs/test-command.md` Part 11, Linux: the blocks of steps 3, 4, 5, 6, 9 and 12 were **extracted from the doc by script and run
      verbatim** against live Django (outputs diffed with the doc: steps 4 to 6 identical; ids and times differ); steps 7, 8, 10 and 11
      ran in headless Chromium with scripted logins (the queue, the filter, the buttons per moderator, a Restore with its
      confirmation, a Mark verified, the dialogs, the post page, the profile card, a visitor, a 390 px phone with no horizontal
      overflow; screenshots looked at). The PowerShell blocks were written but **not run** (no PowerShell here).
  - **Found and fixed on the way** (details in MEMORY and `task.md`): a DRF view throttles every method (so a GET would have used up the
    allowance); the profile's key page needed to be built from what the viewer may see; two redundant checks; and an operational trap:
    a mutation harness left running while I started a dev server and edited files produced a false 500, a deadlocked `pytest` and a
    clobbered edit (MEMORY has the rule).

- 2026-10-13 (Claude, Opus 5.5): **Part 11 planned and approved.** The plan is linked above.
  - **Starting point:** HEAD `582905b` ("Implemented Part 10…", committed by the user), a clean tree. (The older text of
    this file said Part 10 was uncommitted; the user committed it in between.)
  - **Dependency check:** Part 11 depends only on Part 10 (Done 2026-10-13); its chain (9, 8, 5, 4, 1, 0C, 0A/0B/0D,
    plus 2, 3, 6, 7, 7B) is Done. Open but not blocking: Part 3 criterion 4, and CI for Parts 2 to 10.
  - **Research:** read-only only: direct reads of the docs and the moderation, posts, pipeline, reports and social
    code; one Explore agent (the frontend, Stitch b3/c1, E2E helpers); a Plan-agent design review that finished
    **before** approval (its findings are in the plan, marked "(review)").
  - **Changed this session:** only the new plan file and this file. No code, no setup command, no `task.md` edit, no
    env file read, `design/` untouched.
  - **User decisions (2026-10-13):** Restore of an already-checked fact goes to the review queue; Keep removed writes a
    new audit kind `kept_removed`; the removal reason is a new author-only key `removal_reason` (24 keys); your own
    profile lists your removed posts; Remove during an open label appeal closes it as `upheld`; Restore and Keep
    removed take internal notes only. Details and the approved defaults are in the plan.

- 2026-10-13 (Claude, Sonnet 5.5): **Part 10 implemented** (uncommitted). Started from HEAD `a573db4` ("added readme", after
  `a1062e7` "Plan part 10", both committed by you), a clean tree that matched this file (it still said the plan was
  uncommitted). `docker compose ps` showed **no containers running**: I started them (`docker compose up -d`).
  - **Backend** (`backend/`):
    - New app `apps/moderation/`: `models.py` (`ModerationAction`, append-only, all ten kinds, `public_note`),
      `rules.py` (pure: `refusal`, `transition`, `Act`, `Effect`), `services.py` (`mark_verified`, `mark_false`,
      `dismiss_reports`, `remove_post`, `escalate`), `roles.py` (the two groups' lists, `sync_role_groups`), `forms.py`,
      `admin.py` (`PostAdmin` = the review queue, `QueueFilter`, two inlines, the five actions with a confirmation page,
      `ModerationActionAdmin`, `LogEntryAdmin`), `templates/moderation/admin/{confirm_action,post_change_form,post_change_list}.html`,
      migrations `0001_initial` and `0002_role_groups` (its own frozen permission lists), `tests/` (conftest + 13 files).
    - New: `posts/migrations/0002_review_started_at.py`, `core/admin_mixins.py` (`HistoryNeedsLog`),
      `templates/admin/{base_site,change_form_object_tools}.html`, tests `accounts/tests/test_admin_roles.py`,
      `core/tests/test_admin_{settings,header}.py`.
    - Changed: `posts/models.py` (`review_started_at`, its check, the queue index), `posts/services.py` (field lists),
      `posts/admin.py` (now one comment), `pipeline/routing.py` (`enter_review(post, reason, now)`), `reports/services.py`
      (`resolve_open_reports`), `accounts/admin.py` (the senior rules, the delete summary, change messages with values, Mark
      email verified), `accounts/services.py` (`verify_email_by_staff`; the Google helper shares its body), `core/admin.py`
      (seniors-only settings with old → new values, the site header), `social/admin.py` (History mixin),
      `rumor_zero/settings.py`, root `conftest.py` (`role_groups`).
    - Existing tests changed on purpose: the three admin tests that assumed no moderator permissions, the factory (fills
      `review_started_at`), `test_routing`, `test_queue`, `test_processor` (the real `dismiss_reports`), the repost test,
      `test_models`, `test_api_delete`; `posts/tests/test_admin.py` was **removed** (moved into the moderation tests).
  - **Frontend** (`frontend/`): no production change. One test in `AppShell.test.tsx` (the phone account sheet has no
    Moderation entry for non-staff).
  - **Docs:** ARCHITECTURE §2/§4/§8, ANALYSIS c-42, STRUCTURE, MEMORY (a Part 10 entry; one Part 8 bullet marked done),
    `task.md` (criteria, decisions, deviations, both status spots, notes in Parts 2, 11, 11B and 11C), the plan's status
    line, and `docs/test-command.md`: a "Part 10" section in **both** guides (15 steps each) and one number in its intro
    line; nothing else touched (the original file is unchanged apart from my two insertions and that line).
  - Three migrations (`posts.0002`, `moderation.0001`, `moderation.0002`), no new dependency, service or env variable;
    `design/` untouched. **I did not read `backend/.env` or `frontend/.env.local`**: Django read `ADMIN_URL_PATH` itself
    (`python manage.py shell -c …` into a shell variable that was never printed or written; my scripts masked it in every
    output). The dev database was migrated (including a rollback with `migrate posts 0001` and a re-apply, with posts
    under review in it), and all `part10-` accounts, posts, reports, log rows and audit rows I made were deleted.
  - **User decisions and defaults** are in `task.md` Part 10 and the plan.
  - **Validation (all green):**
    - Backend: `ruff check .` (All checks passed!), `ruff format --check .` (228 files already formatted),
      `makemigrations --check --dry-run` (No changes detected), `manage.py check` (no issues), `pytest` **2709 passed**
      (2359 after Part 9; baseline measured first). The Part 10 set: `pytest apps/moderation
      apps/accounts/tests/test_admin_roles.py apps/core/tests/test_admin_settings.py apps/core/tests/test_admin_header.py`
      348 passed. The threaded tests (`test_races.py`, `test_pipeline_interplay.py`) ran 10 times in a row without a failure.
    - **47 backend mutation checks**, every one caught (the first run had two survivors: one was equivalent dead code, the
      lock query's `.not_deleted()`, removed; the other was a bad mutation that hit a comment): no row lock, no re-check
      under the lock, the clock before the lock, a report resolved without `resolved_at`, every report (not only open) or
      none, a service saving `pipeline_attempts`, Dismiss `both` restoring the status, Remove storing `under_review`, the
      own-post rule and the superuser exemption gone, the deleted-post refusal gone, `no_prior_status` gone (both ways), a
      kept escalation or clock after review, the clock not started or restarted by a merge, Escalate outside review, the
      queue showing everything, a status filter that stays in the queue, the cap doubled, buttons without `?queue=all`,
      `select_across` trusted, verdicts offered in an opinions list, the history inline needing the log permission, the page
      editable, the History mixin empty, malformed ids not dropped, buttons not following the rules, no logo, each group
      permission and the migration's list, seniors touching superusers or themselves, the password page open, the bulk delete
      kept, no `get_deleted_objects` override, unprotected log authors, change messages without values, the password hash
      shown, Mark email verified unlogged or ignoring "can't change", the settings message and `has_add_permission`.
      Frontend: one mutation check (the phone sheet gaining Moderation) caught.
    - Frontend: `npm run lint`, `lint:tokens`, `typecheck`, `format:check` clean; `npm test` **1588 passed** (117 files);
      `NEXT_PUBLIC_GOOGLE_CLIENT_ID= npm run build` OK; `npm run test:e2e` **38 passed** (twice: before and after the last
      backend change; `CI=1` not run, since no page changed).
    - Browser (headless Chromium, 1280 px, a scripted walkthrough of steps 11 to 14, screenshots looked at): the header and
      logo, the index per role, the queue (columns, filters, search), a fact's and an opinion's page (buttons, grouped
      fields, the reports inline with the reporter's account age, the history inline), a bulk Mark FALSE with its
      confirmation page and messages, a button that returns to its page, the 403s on the logs, the senior's pages (only
      `role` and `is_active` editable, no password, History link), a settings edit with its History row (restored to 5), and
      the app's sidebar link (staff yes, an ordinary account no).
  - **Found and fixed on the way** (details in MEMORY and `task.md`):
    - `created_at` of an audit row must be taken after the lock (a race test showed rows out of order);
    - a column method named `reports` collided with the reverse relation (the column silently didn't sort);
    - Django's `response_action` turns one malformed id into a 500 (ids are filtered first);
    - the admin's History link and pages showed the admin log to moderators (hidden and refused);
    - `startapp` writes `name = "moderation"` and two files to delete; a `heredoc` with an unquoted delimiter in my own
      scripts expanded `$` in a Python string twice (a scratchpad-only problem);
    - the first mutation list's "buttons post to the queue only" matched a comment, not the template's form.
  - **Test-command notes:**
    - The section is `### Part 10` inside each guide (the brief said `## Part <ID>`; the file's parts are `###` sections
      inside its two `##` guides, as Parts 3 to 9 did).
    - The file has **no comment marker** at its bottom (as in Parts 3 to 9): it ends with the last bullet of the Windows
      Part 10 section. (The brief asked to keep one; there is none to keep.)
    - Part 10's terminal steps talk to the admin through a short helper program (`/tmp/part10_admin.py`, saved by step 3
      with a heredoc; on Windows `$env:TEMP\part10_admin.py` through a function `Padm`), shared by both guides, instead of
      many curl calls. A note of `-` means "empty" because PowerShell 5.1 drops empty arguments.
    - The 17 runnable Linux bash blocks were **extracted from the finished doc by script and run verbatim** against live
      Django (window 1 started as the steps say, `next dev` running for step 14); their output was diffed with the doc's
      expected-output blocks (uuids normalised): **all matched**, three times (the last from the doc inside
      `docs/test-command.md`). The cleanup block printed `(6, {'moderation.ModerationAction': 6})` and `(55, {'reports.Report':
      25, 'admin.LogEntry': 3, 'accounts.User_groups': 4, 'account.EmailAddress': 4, 'posts.Post': 8, 'accounts.User': 11})`
      after a bare run of steps 3 to 10. The browser steps 11 to 14 were checked with the headless script above, not by a
      person. The **PowerShell blocks were not run** (no PowerShell here): they are the bash twins translated, with
      `PYTHONUTF8` and the console encoding set for the helper's arrows.

- 2026-10-11 (Claude, Opus 5.5): **Part 10 planned and approved.** The plan is linked above.
  - **Starting point:** HEAD `4da6514` ("Implemented Part 9…", committed by the user), a clean tree. (The older text of
    this file said Part 9 was uncommitted; the user committed it in between.)
  - **Dependency check:** Part 10 depends only on Part 9 (Done 2026-10-11); its chain (8, 5, 4, 1, 0C, 0A/0B/0D, plus 2,
    3, 6, 7, 7B) is Done. Open but not blocking: Part 3 criterion 4, and CI for Parts 2 to 9.
  - **Research:** read-only only:
    - docs and code: ARCHITECTURE §2/§3/§4/§4a/§4b/§5/§8/§9/§11/§14, ANALYSIS, STRUCTURE, guide §3.4 and §8 (PDF text
      extracted to the scratchpad), every `admin.py`, and Django 5.2.17's admin source;
    - one Explore agent (the frontend Moderation link, `admin_url`, admin test patterns, templates, group creation);
    - a Plan-agent design review that finished **before** approval (its findings are in the plan, marked "(review)").
  - **Changed this session:** only the new plan file and this file. No code, no setup command, no `task.md` edit, no env
    file read, `design/` untouched.
  - **User decisions (2026-10-11):**
    - **Moderators see moderation history only per post** (an inline on the post page). The full `moderation_actions`
      list and Django's admin log are seniors-only.
    - **Seniors may change `role`, suspend (`is_active`) and delete accounts**; nothing else. Never superusers or
      themselves. Email, password, profile and `is_superuser` stay superuser-only.
    - **The removal reason for the author is a new `moderation_actions.public_note`** (verdict notes are copied there
      too). Remove never touches `Post.verdict_note`.
    - **Nobody acts on their own post, except a superuser.**
    - **A new `posts.review_started_at` column** gives the queue's "age in queue" (set on entering review, cleared when
      a moderator ends it, with a consistency check).
    - **"Mark email verified" (deferred from Part 2) is built now, seniors only**, as `verify_email_by_staff` (the name
      `mark_email_verified` is taken by Part 2's signal).
  - **Defaults approved with the plan** are in its "Defaults" section. Two change ARCHITECTURE: Escalate only works on
    posts under review (§4 said "any"), and an account that wrote admin log entries can't be deleted, only suspended.
    Others: account and settings changes go to Django's `LogEntry` with old → new values; act on eligible posts and skip
    the rest; at most 100 posts per action; actions refuse posts the author deleted; no E2E test.
  - **Found during planning** (all handled in the plan):
    - **Admin mechanics:** the admin can't delete a user with posts (`perms_needed`); the bulk delete checks no object;
      a read-only `password` field would show the hash; `user_change_password` only checks change permission;
      an action's queryset is the filtered changelist (buttons post to `?queue=all`); `select_across` re-runs the
      queryset at confirm; `LogEntry.user` cascades; History pages need only view permission; the delete page lists
      bookmarks by `str()`.
    - **Data and naming:** a Dismiss or Remove with a bad `pre_review_status` would break a database check; group
      permissions are wiped by `transaction=True` flushes; `mark_email_verified` already exists.
    - **Tests:** about 25 existing test files change on purpose (moderators gain group permissions, `under_review`
      posts need the new column).
    - **Frontend:** the Moderation link is already built in 0C.

- 2026-10-11 (Claude, Opus 5.5): **Part 9 implemented** (uncommitted). Started from HEAD `56f7f34` ("Plan Part 9",
  committed by the user), a clean tree that matched this file (it still said the plan was uncommitted); Docker healthy,
  ports 3000 and 8000 free.
  - **Backend** (`backend/`):
    - New in `apps/pipeline/`: `contract.py` (`PipelineRequest`, `PipelineResult`, `ContractError`), `clients.py`
      (`StubPipelineClient`, `HttpPipelineClient`, `PipelineError`, `get_client`), `processor.py` (`due_posts`,
      `claim_next`, `process_pending`, `process_post`, `start_kick`), `management/commands/process_pending.py`, and
      `tests/` (`conftest.py` + 10 new files: contract, stub, HTTP client, routing, queue, processor, races, kick,
      command, no-network).
    - Changed: `apps/pipeline/routing.py` (`awaiting_check_q`, `is_awaiting_check`, `backoff`, `MAX_ATTEMPTS`, `Outcome`,
      `apply_pipeline_result`, `apply_pipeline_failure`), `apps/posts/services.py` (`record_pipeline_result`,
      `record_pipeline_failure`, the kick in `create_post`), `apps/posts/serializers.py` (`shown_verdict_source`),
      `apps/core/{views,urls}.py` (`TickView`, the shared cron-secret check), `rumor_zero/{settings,env_helpers}.py`
      (`pipeline_config`, `flag`, the three settings), `conftest.py` (the pipeline pins, no-network opener, the
      kick-thread check), `.env.example` (comments only).
    - Tests also added or changed in `apps/core/tests/{test_tick,test_settings}.py`,
      `apps/posts/tests/{test_services_pipeline,test_api_status,test_api_detail}.py` and
      `apps/reports/tests/test_no_network.py` (`pipeline/clients.py` is the one module allowed to connect).
  - **Frontend** (`frontend/`): no production code change. `playwright.config.ts` and `e2e/helpers.ts` pin the stub and
    the kick off; new `processPost()`; `e2e/post-detail.spec.ts`'s live-badge test now runs the real pipeline (`#true` →
    VERIFIED 95%); 7 new unit tests in `VerdictBlock.test.tsx` and `post-display.test.ts`.
  - **Docs:** ARCHITECTURE §3/§4/§4d/§6/§9/§11, ANALYSIS c-41, STRUCTURE, ENV_GUIDE (the pipeline rows, the Render row's
    launch blocker, §2.12's note), MEMORY (2 entries; two Part 8 bullets marked resolved), `task.md` (criteria,
    decisions and deviations, both status spots, one note in Part 17), the plan's status line, and
    `docs/test-command.md`: a "Part 9" section in **both** guides (15 steps each) and one number in its intro line.
  - No migration, no new dependency, service or env variable; `design/` untouched. `backend/.env` was **read only** to
    take `INTERNAL_CRON_SECRET` into a shell variable for the tick check (`grep … | cut`, as `docs/test-command.md`
    Part 0A does, at your request); no value was printed or written anywhere. `frontend/.env.local` was used by
    `next dev` itself, not read.
  - **User decisions and defaults** are in `task.md` Part 9 and the plan.
  - **Validation (all green):**
    - Backend: `ruff check .` (All checks passed!), `ruff format --check .` (200 files already formatted),
      `makemigrations --check --dry-run` (No changes detected), `manage.py check` (no issues), `pytest` **2359 passed**
      (2066 after Part 8). The Part 9 set: `pytest apps/pipeline apps/core/tests/test_tick.py
      apps/posts/tests/test_services_pipeline.py` 312 passed. The threaded tests (`test_races.py`, `test_kick.py`) ran
      15 times in a row without a failure.
    - **36 backend mutation checks**, every one caught (the first run had one survivor, "a later failure keeps the
      first error", fixed with a test): no SKIP LOCKED, no lease, no token check, the queue or the guard without the
      reported branch or the `verdict_source` test, writes or claim not durable, a kick callback that can raise, the
      deadline stopping the first claim, the late FALSE stored as the label, `verdict_source` always public, redirects
      followed, no size cap, no total time limit, exhausted posts called again, the kick keeping its connection or its
      slot, a one-batch command, a kick that skips locked rows, never giving up, an uncapped backoff, a strict threshold,
      `get_client` always the stub, tags inside words, a tick without the secret, an exception's message stored, `bool`
      as a score, opinions kicked, plain http to any host, the claim loading every column, a result without its
      timestamp, a per-post error stopping the batch. Frontend: no production change, so no frontend mutation run.
    - Frontend: `npm run lint`, `lint:tokens`, `typecheck`, `format:check` clean; `npm test` **1587 passed** (117
      files); `NEXT_PUBLIC_GOOGLE_CLIENT_ID= npm run build` OK; `npm run test:e2e` **38 passed**, and `CI=1` 38 passed.
      The E2E backend logged no pipeline activity of its own (the kick is off there).
    - Live checks: `runserver` with the kick on checked each new fact 0.01–0.03 s after it was saved; with
      `PIPELINE_INLINE_KICK=False`, `process_pending` and the tick cleared the backlog (10 then 2 per tick, about 0.05 s
      for 10). The first `process_pending` on this database checked **116** pending facts left by earlier E2E runs.
    - Browser (headless Chromium, 30 checks, screenshots at 1280 and 390 px): each composer fact (`#true`, `#false`,
      `#unsure`) turned from CHECKING FACTS… into its badge 10.4 s after posting; the post pages show "Checked
      automatically · 95% / 92% confidence" and "Under review" with no %; 0 px overflow at 390 px; Django Admin (a
      throwaway superuser, deleted with the `part9-` accounts) shows the pipeline fields read-only.
  - **Found and fixed on the way:** the import guard of Part 8 (`apps/reports/tests/test_no_network.py`) now names
    `pipeline/clients.py` as the one exception; twice a test helper didn't let the caller override a field it set; SQL
    captured in a `db` test includes `SAVEPOINT` lines; the management command prints the app's INFO log lines (MEMORY).
  - **Test-command notes:**
    - The section is `### Part 9` inside each guide (the brief said `## Part <ID>`; the file's parts are `###`
      sections inside its two `##` guides, as Parts 3 to 8 did).
    - The file has **no comment marker** at its bottom (as in Parts 3 to 8): it ends with the last bullet of the
      Windows Part 9 section. (The brief asked to keep one; there is none to keep.)
    - The Linux bash blocks of steps 3 to 11 were **extracted from the finished doc by script and run verbatim**
      against live Django (window 1 restarted as the steps say, window 4's `--loop` in the background); their output
      was diffed against the doc's expected-output blocks (uuids, log times and seconds normalised): **all nine steps
      and window 4 matched**, twice. All 17 bash blocks pass `bash -n`. The cleanup command printed
      `(35, {'social.Repost': 1, 'account.EmailAddress': 4, 'posts.Post': 26, 'accounts.User': 4})` after each of two
      bare runs of steps 3 to 11. The browser steps 12 to 14 were checked with the headless script above, not by a
      person. The **PowerShell blocks were not run** (no PowerShell here).

- 2026-10-11 (Claude, Opus 5.5): **Part 9 planned and approved.** The plan is linked above.
  - **Starting point:** HEAD `0d8c331` ("Implemented Part 8…", committed by the user), a clean tree. (The older text of
    this file said Part 8 was uncommitted; the user committed it in between.) `docker compose ps`: Postgres and Redis up
    and healthy; ports 3000 and 8000 free.
  - **Dependency check:** Part 9 depends only on Part 8 (Done 2026-10-10); its chain (5, 4, 1, 0C, 0A/0B/0D, plus 2, 3,
    6, 7, 7B) is Done. Open but not blocking: Part 3 criterion 4, and CI for Parts 2 to 8.
  - **Research:** read-only only: two Explore agents (frontend verdict copy, polling and the E2E suite; backend test
    helpers), direct reads of ARCHITECTURE §1–§4b/§6/§9–§13, ANALYSIS, STRUCTURE, ENV_GUIDE, `.env.example` and the code
    the plan changes, and a Plan-agent design review that finished **before** approval (its findings are in the plan).
  - **Changed this session:** only the new plan file and this file. No code, no setup command, no `task.md` edit, no
    env file read, `design/` untouched.
  - **User decisions (2026-10-11):**
    - **A decisive FALSE that arrives while the post is already under review for reports goes to a moderator**
      (`flagged_reason` → `both`, `pre_review_status` stays `pending`); a late TRUE follows the docs. This closes Part 8's
      appendix A2 and changes one ARCHITECTURE §4 row.
    - **The stub in production is recorded as a launch blocker for Part 17** (any author can write `#true`; untagged
      facts get hash-chosen labels); the stub is built as §6 says.
  - **Defaults approved with the plan** are in its "Defaults" section: claim → call → apply with a 5-minute lease and a
    claim token (attempts counted at claim), one "awaiting a check" predicate for the queue and the apply guard,
    `durable=True`, SKIP LOCKED for the sweeper and a waiting claim for the kick, an exception-safe kick (≤ 4 threads per
    process), the tick's "first claim always, then a 25 s budget", `verdict_source` public only with `verified_*`, the
    stdlib HTTP client, the E2E backend with the kick off and one post processed by `processPost`, no migration.
  - **Found during planning** (all handled in the plan): `settings.py` reads no `PIPELINE_*` variable yet and nothing
    turns the kick off in tests; `apps/reports/tests/test_no_network.py` bans network imports in every
    `apps/pipeline/*.py` (the plan allows `clients.py` only); MEMORY's suggested selection for reported pending facts
    would loop on a given-up post (the plan uses `under_review` + `reports` + `pre_review_status='pending'`); three E2E
    tests break if the E2E backend checks facts inline; the review found that a second result could corrupt a finished
    post, that the tick would process 0 posts over HTTP, and that a kick failing after commit would be a 500.

- 2026-10-10 (Claude, Sonnet 5.5): **Part 8 implemented** (uncommitted). Started from HEAD `466c095` ("Plan Part 8", committed
  by the user), a clean tree that matched this file; Docker was already healthy, ports free. The `<ID>` in the brief was blank;
  Part 8 was the only approved, unimplemented plan and the recorded next action.
  - **Backend** (`backend/`):
    - New app `apps/reports/`: `models.py` (`Report`, five named checks, `reports_post_created_idx`), `services.py` (`file_report`,
      `counts_toward_threshold`, `counting_reports`), `serializers.py`, `exceptions.py` (`cannot_report_own`, `already_reported`),
      `views.py` (`ReportView`), `urls.py`, read-only `admin.py`, `migrations/0001_initial.py`, `tests/` (8 files, 137 tests).
    - New app `apps/pipeline/`: only `routing.py` (`merge_flag`, `enter_review`, `apply_report_threshold`) and `tests/test_routing.py` (45).
    - Changed: `rumor_zero/{settings,urls}.py`, `apps/posts/services.py` (`record_report`), `apps/posts/serializers.py` (strict
      `reported_by_me`), `apps/posts/emergency.py` (docstring), `apps/social/engagement.py` (`reported_by_me`),
      `apps/social/services.py` (a post under review after FALSE can't be reposted), and three social test files.
  - **Frontend** (`frontend/`):
    - New `src/features/reports/`: `ReportButton`, `ReportModal`, `reasons`, `reports-api`, `messages` and a test for each.
    - Changed: `features/social/PostActions` (the flag joins the card's right group and the post page's row),
      `features/posts/PostDetail` (a comment), their tests, `FeedList.test`, `e2e/{helpers,social.spec}.ts` (+2 tests,
      `seedReports`, one phone test now checks five actions).
  - **Docs:** ARCHITECTURE §2/§3/§4/§4d/§5/§8/§9/§10, ANALYSIS c-40 (+ two component rows), STRUCTURE, MEMORY (2 entries), `task.md`
    (criteria, deviations, both status spots), the plan's status line, and `docs/test-command.md`: a "Part 8" section in **both**
    guides (14 steps each) and one number in its intro line; nothing else touched.
  - One migration (`reports.0001_initial`), no new dependency, service or env variable; no env file was read or edited (the admin
    path for the browser check was read by Django itself and never printed); `design/` untouched.
  - **User decisions and defaults** are in `task.md` Part 8 and the plan. The plan's appendix (A1, A2) was **not adopted**: the
    approved plan was built as written; A2 is a Part 9 follow-up.
  - **Found and fixed on the way:** a server field error can't take focus while the fieldset is disabled (an effect now does it);
    the test session's user id equals `makePost`'s default author, which hid the flag in tests until the post got another author;
    the mutation run found three weak tests (a vacuous Escape test, an unasserted filled glyph, a pattern that didn't match), all
    fixed with tests; the test helper that seeds report rows must also set `Post.report_count`.
  - **Test-command notes:**
    - The section is `### Part 8` inside each guide.
    - The file has **no comment marker** at its bottom (as in Parts 3 to 7B): it ends with the last bullet of the Windows Part 8
      section. (The brief asked to keep one; there is none to keep.)
    - The Linux bash blocks of steps 3 to 9 were **extracted from the finished doc by script and run verbatim** against live Django;
      their output was diffed against the doc's expected-output blocks (uuids and seconds normalised): **all seven steps matched**,
      twice (the second run after the browser checks). The settings check printed `5 24 24`. The cleanup command printed
      `(62, {'social.Like': 1, 'social.Repost': 1, 'reports.Report': 22, 'account.EmailAddress': 9, 'posts.Post': 20,
      'accounts.User': 9})` after a bare run of steps 3 to 9. The browser steps 10 to 12 were checked row by row with headless
      Chromium scripts (screenshots at 1280 and 390 px, 38 checks) and Django Admin (step 13) with a scripted browser, plus the E2E
      suite, not by a person. The **PowerShell blocks were not run** (no PowerShell here).

- 2026-10-10 (Claude, Opus 5.5): **Part 8 planned and approved.** The plan is linked above.
  - **Starting point:** HEAD `416fcae` ("Implemented Part 7B…", committed by the user), a clean tree. (The older text of this
    file said Part 7B was uncommitted; the user committed it in between.) `docker compose ps`: Postgres and Redis up and healthy.
  - **Dependency check:** Part 8 depends only on Part 5 (Done 2026-10-09); its chain (4, 1, 0C, 0A/0B/0D, plus 2 and 3) is Done,
    and so are 6, 7 and 7B. Open but not blocking: Part 3 criterion 4, and CI for Parts 2 to 7B.
  - **Research:** read-only only: two Explore agents (backend patterns; frontend primitives, buttons, E2E), direct reads of
    ARCHITECTURE §2/§3/§4/§4d/§5/§8/§9/§10, ANALYSIS b-5/c-2/c-3/c-5, STRUCTURE, DESIGN.md, Stitch d1/b1/b3 and the code the plan
    changes. A Plan-agent design review finished **after** the user approved; its findings are the plan's appendix, not part of
    the approved plan.
  - **Changed this session:** only the new plan file and this file. No code, no setup command, no `task.md` edit, no env file
    read, `design/` untouched.
  - **User decisions (2026-10-10):**
    - **Report is a flag button** in the card's action bar (beside the bookmark, Stitch b1) and "Report" in the post page's
      action row (b3), not an overflow menu as `task.md` says (recorded as a deviation when the part is closed).
    - **A young account's report counts** if it has a post that isn't removed or a comment that isn't hidden; deleted posts and
      comments still count, moderated ones don't.
    - **FALSE posts follow the docs** (UNDER REVIEW at the threshold, `pre_review_status=verified_false`), **and a post under
      review after being FALSE can't be reposted** (409 `cannot_repost_false`; one condition in `social.services.repost`).
  - **Defaults approved with the plan** are in its "Design" and "Defaults" sections: `FOR NO KEY UPDATE` on the post, the check
    order (401, 403 `email_unverified`, 429, 404, 400, 404, 403 `cannot_report_own`, 409 `already_reported`), 201
    `{"reported": true}`, permanent reports, no preselected reason, `apps/pipeline` made with `startapp` now (only
    `routing.py`), `posts.services.record_report` as the status write, `reported_by_me` in `with_engagement`, read-only
    `ReportAdmin`, the emergency threshold left to 11C.
  - **Found during planning** (handled in the plan): `apps/pipeline` must come from `startapp` (`posts/emergency.py` says a bare
    folder would make Part 9's refuse); `RadioCardGroup` and `Modal`'s `footerTone="plain"` already exist for d1; `Modal` returns
    focus only from the dialog's `close` event, so the report modal is mounted on first open and kept; `pre_review_status` is
    never public, so the page can't pre-disable the new repost refusal (the existing rollback toast covers it); Part 9's processor
    selects only `pending` facts, so a pending fact that reports send to review would never be checked (Part 9 follow-up).

- 2026-10-10 (Claude, Sonnet 5.5): **Part 7B implemented** (uncommitted). Started from HEAD `753c3ff` ("Plan Part 7B",
  committed by the user), a clean tree that matched this file; Docker was already healthy, ports free.
  - **Backend** (`backend/`):
    - New: `apps/social/timeline.py` (the mixed feed's key, cursor token, per-page rule and union query),
      `migrations/0003_repost_bookmark.py`, and 10 test files (`test_models_repost_bookmark`, `test_services_repost_bookmark`,
      `test_timeline`, `test_timeline_db`, `test_api_repost`, `test_api_bookmark`, `test_api_bookmark_list`,
      `test_api_feed_reposts`, `test_api_user_posts_reposts`, `test_admin_repost_bookmark`).
    - Changed: `apps/social/{models,services,engagement,feed,views,urls,serializers,pagination,exceptions,admin}.py`
      (`Repost`, `Bookmark`; repost, unrepost, bookmark, unbookmark; the three counts in `with_engagement`; cache v2 and
      `load_entries`; `RepostView`, `BookmarkView`, `BookmarkListView`, the feed and profile views on the timeline;
      `BookmarkPagination`; the two 409 errors; `RepostAdmin` and the superuser-only `BookmarkAdmin`),
      `apps/posts/serializers.py` (strict reads of the three new fields; `feed_item(…, activity_at)`), and tests
      (`factories`, `test_feed_cache`, `test_services`, `test_api_user_posts`, `test_engagement_counts`, `test_no_network`).
  - **Frontend** (`frontend/`):
    - New: `features/social/{RepostButton,BookmarkButton,RepostHeader,UnavailablePostCard,repost-rules}`,
      `features/posts/feed-items.ts`, `features/bookmarks/BookmarkList.tsx` and a test for each.
    - Changed: `features/social/{PostActions,LikeButton,social-api,messages}`, `features/posts/{FeedList,PostCard,PostDetail,
      status-overlay,test-helpers}`, `app/(app)/bookmarks/page.tsx` (the placeholder is now the page), `e2e/{helpers,social.spec}.ts`
      (+4 tests, `seedPost`, a `verified_false` state), and their unit tests.
  - **Docs:** ARCHITECTURE §2/§3/§4d/§8/§9/§10, ANALYSIS c-39, STRUCTURE, MEMORY (2 entries and one bullet), `task.md` (criteria,
    deviations, both status spots), the plan's status line, and `docs/test-command.md`: a "Part 7B" section in **both** guides
    (19 steps each) and one number in its intro line; nothing else touched.
  - One migration (`social.0003_repost_bookmark`), no new dependency, service or env variable; no env file was read or edited;
    `design/` untouched.
  - **User decisions and defaults** are in `task.md` Part 7B and the plan.
  - **Found and fixed on the way:** a bare OR cursor filter can't use an index (a redundant `created_at <= t` per side; a test
    reads the SQL); `LikeButton` repeated one hint id per card (`useId`); the visible word must be in the button's name
    ("Repost"); a mutation survivor each side (the bookmark scope: equal rates; the zero clamp); a redundant admin override was
    removed; a system `ruff` ran when the venv wasn't activated (MEMORY).
  - **Test-command notes:**
    - The section is `### Part 7B` inside each guide.
    - The file has **no comment marker** at its bottom (as in Parts 3 to 7): it ends with the last bullet of the Windows
      Part 7B section. (The brief for this part asked to keep one; there is none to keep.)
    - The Linux bash blocks of steps 3 to 13 were **extracted from the finished doc by script and run verbatim** against live
      Django (and `next dev`); their output was diffed against the doc's expected-output blocks (uuids, numbers in names and
      `Retry-After` seconds normalised): **all eleven steps matched** (one expected line was fixed first: step 8's last line
      had an extra key). The cleanup command printed `(39, {'social.Like': 1, 'social.Repost': 7, 'social.Bookmark': 6,
      'social.Follow': 2, 'account.EmailAddress': 6, 'posts.Post': 11, 'accounts.User': 6})` after that run. The browser steps 14
      to 17 were checked with headless Chromium scripts (screenshots at 1280 and 390 px) and Django Admin (step 18) with a
      scripted browser, plus the E2E suite, not by a person. The **PowerShell blocks were not run** (no PowerShell here).

- 2026-10-10 (Claude, Opus 5.5): **Part 7B planned and approved.** The plan is linked above.
  - **Starting point:** HEAD `c562e70` ("Implemented Part 7: Likes & comments", committed by the user), a clean tree.
    (The older text of this file said Part 7 was uncommitted; the user committed it in between.) `docker compose ps`:
    Postgres and Redis up and healthy.
  - **Dependency check:** Part 7B depends on Parts 6 (Done 2026-10-09) and 7 (Done 2026-10-10); their chains (5, 4, 1,
    0C, 0A/0B/0D, plus 2 and 3) are Done. Open but not blocking: Part 3 criterion 4, and CI for Parts 2 to 7.
  - **Research:** read-only only: two Explore agents (the frontend feed/social code; Stitch a1/b1/b3/c1 + DESIGN.md),
    direct reads of the backend `social`/`posts`/`core` pagination and feed code and ARCHITECTURE §2/§3/§4a/§4d/§9/§10,
    a Plan-agent review of the feed cursor design (its findings are folded into the plan), and one read-only
    `manage.py shell` prototype that compiled and ran a `SELECT` (no write) to confirm Django 5.2.17 builds a `UNION
    ALL` of two ordered, sliced `values_list` querysets.
  - **Changed this session:** only the new plan file and this file. No code, no setup command, no `task.md` edit, no
    env file read, `design/` untouched.
  - **User decisions (2026-10-10):**
    - **`BookmarkAdmin` is superuser-only** (registered read-only; moderators never see bookmarks).
    - **A repost of a deleted or removed original can be taken back** (`DELETE …/repost/` is 204 whenever the post row
      exists; your own "no longer available" card has Undo repost).
    - **The page hides later repeats** of a post across Following-feed pages (the API keeps "once per page").
    - **Profile chips filter reposts by the original's type.**
  - **Defaults approved with the plan** are in its "Defaults" and "The mixed timeline" sections: the keyset timeline
    (key `(activity_at, kind, post id, reposter id)`, integer-microsecond token, per-page dedupe over a `2 × size + 1`
    window), cache v2 holding the full keys, the 201/200/204/404/409 codes and their order, `FOR NO KEY UPDATE` on
    repost, the bookmark list in the §9 envelope, query counts, the button states, `/bookmarks`.
  - **Found during planning** (all handled in the plan): DRF's cursor can't page a union; repost ids are bigint and post
    ids uuid (so no single "item id" column; recorded as a deviation from task.md's wording); a plain OR cursor filter
    can't use an index (a redundant `created_at <= t` is added); `FeedList` and `pendingPostIds` skip reposts today and
    tests pin that; `LikeButton` and `FollowButton` repeat a constant hint id in lists (the plan fixes `LikeButton`
    only); Stitch has no filled bookmark, "Reposted by" header, unavailable card or bookmarks page; the E2E suite uses
    16 of the 20 sign-ups a minute (7B seeds its third author through `manage.py shell`).

- 2026-10-10 (Claude, Sonnet 5.5): **Part 7 implemented** (uncommitted). Started from HEAD `3f8e174` ("Plan Part 7",
  committed by the user), a clean tree that matched this file; Docker was already healthy, ports free.
  - **Backend** (`backend/`):
    - New: `apps/social/engagement.py` (`with_engagement`, `engagement_defaults`, `count_subquery`),
      `migrations/0002_like_comment.py`, and 8 test files (`test_models_engagement`, `test_services_engagement`,
      `test_api_like`, `test_api_comments`, `test_api_comment_create`, `test_api_comment_delete`,
      `test_engagement_counts`, `test_admin_engagement`).
    - Changed: `apps/social/{models,services,views,urls,serializers,pagination,feed,admin}.py` (`Like`, `Comment`; like,
      comment and delete services; three views; `CommentPagination`; `load_posts(ids, viewer)`; `LikeAdmin`,
      `CommentAdmin` with Hide/Unhide), `apps/posts/{models,serializers,views}.py` (`for_list(viewer)`, strict counts,
      zeros on the 201, the shared `content_field()`), `apps/core/pagination.py` (docstring), tests
      (`social/tests/factories.py`, `test_no_network.py`, `core/tests/test_pagination.py`).
  - **Frontend** (`frontend/`):
    - New in `src/features/social/`: `LikeButton`, `CommentCountLink`, `PostActions`, `CommentSection`, `CommentComposer`,
      `CommentList`, `CommentItem`, `DeleteCommentModal`, `useComments` and a test for each (but the two thin ones).
    - Changed: `social-api` (+`messages`) and their tests, `social/test-helpers`, `lib/api/types.ts` (`Comment`),
      `features/posts/{PostCard,FeedList,PostDetail,useCursorFeed,test-helpers}` and their tests, `e2e/social.spec.ts`
      (+3 tests), `e2e/posts.spec.ts` (three links on a card).
  - **Docs:** ARCHITECTURE §2/§3/§8/§9/§10, ANALYSIS c-38, STRUCTURE, MEMORY (2 entries), `task.md` (criteria,
    deviations, both status spots), the plan's status line, and `docs/test-command.md`: a "Part 7" section in
    **both** guides (17 steps each) and one number in its intro line; nothing else touched.
  - One migration (`social.0002_like_comment`), no new dependency, service or env variable; no env file was read
    or edited; `design/` untouched.
  - **User decisions and defaults** are in `task.md` Part 7 and the plan: hidden comments Django Admin only; own
    comments soft-deleted (`deleted_at`); Hide **and Unhide**.
  - **Found and fixed on the way:** `User.save` derives `is_staff` from `role` (a "staff can't hide" test passed for the
    wrong reason); focus after posting needs an effect (a disabled fieldset drops it); adjacent inline spans make the
    accessible name "Like3"; two mutation checks showed dead code (a redundant status test and a like patch that
    nothing read), which was removed; a stray `verify_out.txt` and `verify_run.sh` from my own check script were
    written to the repo root and deleted.
  - **Test-command notes:**
    - The section is `### Part 7` inside each guide.
    - The file has **no comment marker** at its bottom (as in Parts 3 to 6): it ends with the last bullet of the
      Windows Part 7 section. (The brief for this part asked to keep one; there is none to keep.)
    - The Linux bash blocks of steps 3 to 12 were **extracted from the finished doc by script and run verbatim**
      against live Django and `next dev`; their output was diffed against the doc's expected-output blocks (ids,
      numbers in names and `Retry-After` seconds normalised): **all ten steps matched**. The cleanup command printed
      `(86, {'social.Like': 4, 'social.Comment': 64, 'social.Follow': 1, 'account.EmailAddress': 6, 'posts.Post': 5,
      'accounts.User': 6})` after each of two runs. The browser steps 13 to 16 were checked with headless Chromium
      scripts (screenshots at 1280 and 390 px) and Django Admin with a scripted browser, plus the E2E suite, not by a
      person.
- 2026-10-10 (Claude, Sonnet 5.5): **Part 7 planned and approved.** The plan is linked above.
  - **Starting point:** HEAD `15c1d8a` ("Implementation Part 6…", committed by the user), a clean tree. (The older
    text of this file said Part 6 was uncommitted; the user committed it in between.) `docker compose ps` showed
    **no containers running**.
  - **Dependency check:** Part 7 depends only on Part 5 (Done 2026-10-09); its chain 4 → 1 → 0C → 0A/0B/0D plus 2,
    3 and 6 is Done. Open but not blocking: Part 3 criterion 4, and CI for Parts 2 to 6.
  - **Research:** read-only only: two Explore agents (backend `apps/social` + `apps/posts`; frontend, Stitch
    a1/b1/b3, UI primitives, E2E) plus direct reads of ARCHITECTURE §2/§3/§8/§9/§10, ANALYSIS, STRUCTURE, DESIGN.md
    and the Part 6 plan.
  - **Changed this session:** only the new plan file and this file. No code, no setup command, no `task.md` edit,
    no env file read, `design/` untouched.
  - **User decisions (2026-10-10):**
    - **Hidden comments are Django Admin only:** the API and the page never return them to anyone, staff included,
      and they don't count in `comment_count`.
    - **Deleting your own comment is a soft delete** (new `deleted_at` column; changes ARCHITECTURE §2, which
      listed none).
    - **CommentAdmin gets Hide and Unhide actions** (task.md said only Hide).
  - **Defaults approved with the plan** are in the plan's "Defaults" section: like 201/200/204 and `{"liked": true}`;
    like and comment on a visible post only (deleted, removed or unknown is 404; pending and under review are
    allowed); unlike works on a removed post; comments oldest first on `(created_at, id)`, 5-key object, `comment`
    throttle on POST only; counts as correlated subqueries (`for_list(viewer)` is the single choke point, the
    serializer reads them strictly); one partial index for the visible comments; `LikeButton` mirrors
    `FollowButton` with local state; `PostCard` gets an `actions` slot; comments are client-fetched only; E2E tests
    join `social.spec.ts` (no new sign-ups).
  - **Found during planning** (all handled in the plan): the Following feed's `load_posts` takes no viewer;
    `moderation_actions` doesn't exist and has no comment kind, so Hide writes Django's admin `LogEntry`; no model
    permissions are granted to the Moderators group yet (Part 10), so Hide/Unhide are gated on
    `social.change_comment`; `useCursorFeed` has no append or remove; DESIGN.md's glyph list names neither
    `favorite` nor `chat_bubble` (read-only, not lint-enforced, so ANALYSIS records it); HANDOFF's "Part 6
    uncommitted" text was stale.

- 2026-10-09 (Claude, Sonnet 5.5): **Part 6 implemented** (uncommitted). Started from HEAD `a942dcb` ("plan part 6",
  committed by the user), a clean tree that matched this file (the plan file and this file were the only
  differences from `b5b8089`, now committed); Docker healthy, ports free.
  - **Backend** (`backend/`):
    - New app `apps/social/`: `models.py` (`Follow`, two named constraints, two composite indexes),
      `services.py` (`follow`, `unfollow`, `lookup_name`, `find_active_user`, `SelfFollow`), `feed.py` (the ids-only
      first-page cache, `bust_following_feed`, `following_page`, `load_posts`), `serializers.py` (profile and row
      objects, the counter annotations), `views.py` (profile, user posts, followers, following, follow, feed),
      `urls.py`, `pagination.py`, `exceptions.py` (`cannot_follow_self`), read-only `admin.py`,
      `migrations/0001_initial.py`, and `tests/` (11 files, 160 tests).
    - Changed: `rumor_zero/settings.py` (`apps.social`, `FEED_CACHE_SECONDS` 0 to 300), `rumor_zero/urls.py`,
      `apps/core/pagination.py` (`TimestampCursorMixin`), `apps/posts/pagination.py` (uses it; `envelope()`),
      `apps/posts/services.py` (`create_post` clears the author's cached feed), `backend/.env.example` (comment),
      `apps/core/tests/{test_pagination,test_settings}.py`.
  - **Frontend** (`frontend/`):
    - New `src/features/social/`: `social-api`, `messages`, `profile-metadata`, `useProfile`, `FollowButton`, `UserRow`,
      `ProfileHeader`, `ProfilePage`, `ProfilePosts`, `Connections`, `test-helpers` and a test for each;
      `src/app/(app)/u/[username]/{page,followers/page,following/page}.tsx`; `e2e/social.spec.ts`.
    - Changed: `lib/api/{types,server}.ts` (+tests), `lib/format.ts` (+`formatMonthYear`, `formatCount`),
      `features/posts/{HomeFeed,FeedList,PostCard,PostDetail,post-card-props,post-metadata}` and their tests,
      `e2e/{helpers,posts.spec}.ts`.
  - **Docs:** ARCHITECTURE §2/§3/§9/§10, ANALYSIS c-37, STRUCTURE, ENV_GUIDE (the three `FEED_CACHE_SECONDS` rows),
    MEMORY (2 entries), `task.md` (criteria, deviations, both status spots), the plan's status line, and
    `docs/test-command.md`: a "Part 6" section in **both** guides (15 steps each) and one number in its intro
    line; nothing else touched.
  - One migration (`social.0001_initial`), no new dependency, service or env variable (`FEED_CACHE_SECONDS` was in
    `.env.example` already); no env file was read or edited; `design/` untouched.
  - **User decisions and defaults** are in `task.md` Part 6 and the plan.
  - **Found and fixed on the way:** a NUL byte in a username was a 500 (`lookup_name`); the follow button's hover
    label dropped out of its accessible name; the E2E suite was over allauth's sign-up limit and its sign-up
    helper too impatient (MEMORY); mutation checks showed an unused counter helper and a missing "removed posts
    don't shorten a page" test.
  - **Test-command notes:**
    - The section is `### Part 6` inside each guide.
    - The file has **no comment marker** at its bottom (as in Parts 3 to 5): it ends with the last bullet of
      the Windows Part 6 section.
    - The Linux bash blocks of steps 3 to 10 were **extracted from the finished doc by script and run verbatim**
      against live Django and `next dev`; their output was diffed against the doc's expected-output blocks
      (ids, token prefixes and seconds normalised): **all steps matched**. The step 12 shell command and the
      cleanup were run from the doc too (`(22, {'posts.Post': 8, 'social.Follow': 4, 'account.EmailAddress': 5,
      'accounts.User': 5})` per run). The browser steps 11 to 14 were checked with headless Chromium scripts
      (screenshots at 1280 and 390 px) plus the E2E suite, not by a person; the admin page (step 11) by a
      Django-client test only.
- 2026-10-09 (Claude, Sonnet 5.5): **Part 6 planned and approved.** The plan is linked above.
  - **Starting point:** HEAD `b5b8089` ("Implementation Part 5…", committed by the user), a clean tree. (The
    older text of this file said Part 5 was uncommitted; the user committed it in between.)
  - **Dependency check:** Part 6 depends only on Part 4 (Done 2026-10-09); its chain 1 → 0C → 0A/0B/0D plus
    2, 3 and 5 is Done. Open but not blocking: Part 3 criterion 4, and CI for Parts 2 to 5.
  - **Research:** read-only only: two Explore agents (backend; frontend and Stitch c1/c3/b1) plus direct
    reads of ARCHITECTURE §2/§3/§9/§10, ANALYSIS, STRUCTURE, the Part 5 plan, `HomeFeed`,
    `FeedPagination`, `usePostDetail`, and DRF's cursor code in the installed source.
  - **Changed this session:** only the new plan file and this file. No code, no setup command, no
    `task.md` edit, no env file read, `design/` untouched.
  - **User decisions (2026-10-09):**
    - `/home` tabs are **Recent first and default, Following second**; Following is for signed-in users only
      and loads lazily; its empty state has an action that switches to Recent.
    - The per-user Following cache holds **only the ids of page 1**; posts are loaded fresh on each request
      (deleted or removed posts vanish at once; Part 7's `*_by_me` is never stale).
    - Profile counters `verified` and `FALSE` **include deleted posts** (not removed ones); `posts` counts
      only what the public can see.
    - The author's avatar and name on post cards and the post page **link to `/u/<username>`**.
  - **Defaults approved with the plan** are in the plan's "Defaults" section: lookup by
    `normalize_username` and unknown or inactive users are 404; the profile object (`counts`, `reputation`,
    `is_following`, `is_me`; one query anonymous, two signed in); follow is 201/200 and verified-only,
    unfollow is 204 and login-only, both throttled by `follow` 100/h; `FEED_CACHE_SECONDS` (0 to 300, 0 = off);
    a cursor-guard mixin moved into `apps/core/pagination.py`; two composite indexes on `follows`; the SSR and
    `/u/Ada` → `/u/ada` redirect; `FilterChips` All/Facts/Opinions; counters printed as "1,420".
  - **Found during planning** (all handled in the plan):
    - `FEED_CACHE_SECONDS` is only in `backend/.env.example`; no code reads it, and `ENV_GUIDE.md` wrongly files
      it with the admin-editable PlatformSettings seeds (lines ~111, 382, 562).
    - `task.md` says "no self-follow check", while ARCHITECTURE §2 and the acceptance criteria want a DB check
      and a 400: built per ARCHITECTURE; the `task.md` wording is fixed when the part is closed.
    - ARCHITECTURE §2 says `index(following)` for follows: replaced by two composite indexes
      (`following, created_at DESC, id DESC` and `follower, created_at DESC, id DESC`); §2 is updated in Part 6.
    - DRF's `CursorPagination` accepts `.values()` rows, which the ids-only cache relies on.
    - `useCursorFeed` doesn't refetch when `fetchPage` changes: a new filter or username needs a new
      `resetKey` or a remount.
    - Existing tests assert card link counts (`PostCard.test.tsx`, `e2e/posts.spec.ts`) and a single home tab
      (`HomeFeed.test.tsx`); they change on purpose.
    - A page-level `openGraph` replaces the root's whole object (MEMORY 2026-10-09), so `/u/[username]` sets
      its own images (reusing the descriptor in `post-metadata.ts`, which the brand guard already allows).

- 2026-10-09 (Claude, Sonnet 5.5): **Part 5 implemented** (uncommitted). Started from HEAD `f0e15d0`
  ("Plan Part 5", committed by the user), a clean tree that matched this file; Docker healthy, ports free.
  - **Backend** (`backend/`):
    - `apps/posts/`: `models.py` (`PostQuerySet.not_deleted()`), `serializers.py` (`shown_confidence`,
      `status_item`, the tombstone rule in `PostSerializer`), `services.py` (`delete_post`, `PostNotFound`,
      `NotPostAuthor`), `exceptions.py` (`NotAuthorError`), `views.py` (`PostDetailView`, `PostStatusView`),
      `urls.py`, `admin.py` ("By deleted at" filter).
    - `rumor_zero/settings.py` (`status_poll` 120/min).
    - Tests: new `test_api_detail.py` (33), `test_api_delete.py` (22), `test_api_status.py` (17); changed
      `test_models.py`, `test_no_network.py`, `apps/core/tests/test_settings.py` (eleven scopes).
    - No migration.
  - **Frontend** (`frontend/`):
    - New `src/app/(app)/p/[id]/page.tsx`; `src/lib/api/{backend-origin,server}.ts`; in
      `src/features/posts/`: `PostDetail`, `usePostDetail`, `VerdictBlock`, `SourceList`, `CopyLinkButton`,
      `DeletePostModal`, `post-metadata.ts`, `useStatusPolling`, `status-overlay.ts`, a test for each, and
      `posts-api.test.ts`; `e2e/post-detail.spec.ts`.
    - Changed: `PostCard`, `SourceLink` (links), `post-card-props.ts`, `FeedList`, `HomeFeed`
      (overlay, polling), `posts-api.ts`, `lib/api/{relay,types}.ts`, `lib/format.ts`
      (`formatFullDateTime`), `brand-guard.test.ts` (allow-list), `e2e/helpers.ts` (`setPostState`),
      `e2e/posts.spec.ts` (the opinion card now has one link) and the unit tests for those.
  - **Docs:**
    - ARCHITECTURE §3/§4/§9/§10, ANALYSIS b-2 "Removed", STRUCTURE, MEMORY (2 entries), `task.md`
      (criteria, deviations, both status spots), the plan's status line.
    - `docs/test-command.md`: a "Part 5" section in **both** guides (14 steps each) and one word in the
      intro list; nothing else touched.
  - No new service, dependency or env variable; no env file read or edited; `design/` untouched.
  - **User decisions and defaults** are in `task.md` Part 5 (tombstone = 23 keys blanked; `status_poll`).
  - **Deviations from the plan** (all in `task.md`): `useStatusPolling` filters its own ids; the origin
    rule moved to `backend-origin.ts`; the brand guard allow-lists `post-metadata.ts`; the admin filter is
    headed "By deleted at"; the redundant removed-confidence check was dropped.
  - **Found and fixed on the way:** StrictMode aborted the signed-in detail fetch and the "already
    fetched" marker was set too early (the author got no Delete button; found by E2E; the unit test
    reproduces it); an empty "Verdict" card on a removed post (found in a screenshot); a page-level
    `openGraph` drops the root's image (MEMORY).
  - **Test-command notes:**
    - The section is `### Part 5` inside each guide.
    - The file has **no comment marker** at its bottom (as in Parts 3 and 4): it ends with the last cleanup
      bullet of the Windows Part 5 section.
    - The Linux bash blocks of steps 3 to 9, 12 and the cleanup were **extracted from the doc by script and
      run verbatim** against live Django and `next dev`; the browser steps 11 to 13 were driven by headless
      Chromium scripts (screenshots at 1280 and 390 px), and steps 1 and 2 are the commands listed in
      "Validation of Part 5". The recorded cleanup line `(12, {'posts.Post': 6, …})` comes from a run that
      also made browser posts; a bare run of steps 3 to 9 printed `(9, {'posts.Post': 3, …})`.

- 2026-10-09 (Claude, Sonnet 5.5): **Part 5 planned and approved.** The plan is linked above.
  - **Starting point:** HEAD `2b1fb19` ("Implemented Part 4: posts composer and Recent feed",
    committed by the user), a clean tree. (The older text of this file said Part 4 was uncommitted;
    the user committed it in between.)
  - **Dependency check:** Part 5 depends only on Part 4 (Done 2026-10-09); its chain 1 → 0C → 0A/0B/0D
    plus 2 and 3 is Done. Open but not blocking: Part 3 criterion 4, and CI for Parts 2 to 4.
  - **Research:** read-only only (two Explore agents plus direct reads): the Part 4 posts backend and
    frontend, ARCHITECTURE/ANALYSIS, Stitch b3 and c1, Next 16.3.8's metadata merge code.
  - **Changed this session:** only the new plan file and this file. No code, no setup command, no
    `task.md` edit, no env file read.
  - **User decisions (2026-10-09):**
    - A removed post shows the public the **same 23 keys with `content`, `sources`, `verdict_note`
      (and, by default, `confidence_score` and `verdict_source`) blanked**; the author's name and the
      post time stay visible. The author sees the full post.
    - **A `status_poll` throttle is added now:** 120/min per client IP, on the public status endpoint.
  - **Defaults approved with the plan:** the detail, delete and status API shapes and codes (404 for
    deleted or malformed ids, 403 `not_author`, 204 on delete and 404 on a repeat, removed answers
    `removed` in the poll and deleted ids are omitted); polling covers `pending` only with a 10-minute
    budget counted in visible time (10 s × 1.5 up to 60 s); the claim text is a stretched card link
    with `prefetch={false}`; detail claim at `text-headline-md`; absolute UTC date; the SSR fallback and
    5 s timeout; the "Deleted by author" admin filter; all listed in the plan's "Defaults" section.
  - **Found during planning** (all handled in the plan):
    - `PostQuerySet.visible()` hides removed posts, so the detail needs `not_deleted()`.
    - `verdict_note` is ungated in `PostSerializer`.
    - A page-level `openGraph`/`twitter` replaces the root layout's whole object (Next 16.3.8
      `resolve-metadata.js:182-191`), so `/p/[id]` must set `type`, `siteName`, `images` and the
      title suffix itself.
    - A public GET with a stale Bearer is a 401.
    - A `<uuid:>` converter answers an HTML 404.
    - The existing tests assert cards have no link.
    - `useCursorFeed` has no patch action.

- 2026-10-09 (Claude, Sonnet 5.5): **Part 4 implemented** (uncommitted). Started from HEAD `b5fb841`
  ("Plan Part 4", committed by the user), a clean tree. (HANDOFF had said the plan was uncommitted; the
  user committed it in between. Nothing else differed.)
  - **Backend** (`backend/`):
    - New app `apps/posts/`: `models.py` (`Post` with every §2 column but `search_vector`, 17 named
      CheckConstraints, 6 indexes, `PostQuerySet.visible()/for_list()`), `validators.py`
      (`normalize_source`, `validate_sources`, `source_kind`), `emergency.py` (`is_active_emergency`),
      `services.py` (`create_post`, `fact_quota`, the three domain errors), `exceptions.py`,
      `serializers.py` (`SourcesField`, `PostCreateSerializer`, `PostSerializer`), `pagination.py`
      (`FeedPagination`), `views.py`, `urls.py`, `admin.py` (read-only), `migrations/0001_initial.py`,
      and `tests/` (9 files plus `source_vectors.json`).
    - Changed: `rumor_zero/settings.py` (+`django.contrib.postgres`, +`apps.posts`), `urls.py`,
      `requirements.txt` (+`idna==3.20`), `.env.example` (a comment), `apps/accounts/serializers.py`
      (+`user_summary`, `UserSummarySerializer`), `apps/accounts/tests/conftest.py` and `test_tokens.py`
      (`run_together` moved).
  - **Frontend** (`frontend/`):
    - New `src/features/posts/`: `sources.ts` (client mirror of the validator), `SourceLink`,
      `PostCardSkeleton`, `post-card-props.ts`, `posts-api.ts`, `useCursorFeed`, `FeedList`, `draft.ts`,
      `quota.ts`, `messages.ts`, `SourceFields`, `ComposerModal`, `ComposerProvider`, `ComposerTrigger`,
      `HomeFeed`, `test-helpers.tsx` and a test per piece; `e2e/posts.spec.ts`.
    - Changed: `PostCard.tsx` (sources row, blank-name rule, 390 px header), `Textarea.tsx` and
      `lib/format.ts` (`countCharacters`: code points), `lib/api/types.ts` (`FactQuota`, `CreatePostBody`),
      `app/(app)/layout.tsx` (the provider, `onNewPost`), `app/(app)/home/page.tsx` (`HomeFeed`),
      `e2e/helpers.ts` (`signUpVerified`, `marker`), `layout.test.tsx`, `PostCard.test.tsx`.
  - **Docs:**
    - ARCHITECTURE §2/§3/§4/§4c/§9/§10, ANALYSIS (D7 and the b-3 quota row), SETUP B1 (`idna`), STRUCTURE,
      ENV_GUIDE (one sentence), `backend/.env.example` (a comment), MEMORY (3 entries), `task.md`
      (criteria, deviations, both status spots), the plan's status line.
    - `docs/test-command.md`: a "Part 4" section in **both** guides (15 steps each) and one word in the
      intro list; nothing else touched.
  - No new service, no new env variable, no env file read or edited, `design/` untouched.
  - **Deviations from the plan** (all in `task.md`): 23 keys in the post object (not 24); the "too many
    sources" check lives in `validate_sources`; rows are focused by `id` (`TextField` has no `ref`); the
    submit button reads "Post" until a type is chosen; the footer wraps on a phone.
  - **Found and fixed on the way:** `varchar(500)[]` truncates a long source silently through Django's
    cast (the validator is the only guard); `sourceLabel()` rendered a blank row for a non-http value;
    two composer bugs a test caught (a server field error never showed the "fix the fields" notice; a
    "paused" banner wasn't announced); React 19 lint rules (`react-hooks/refs`) and a `cn()` class-order
    trap (MEMORY).
  - **Test-command notes:**
    - The section is `### Part 4` inside each guide.
    - The file has **no comment marker** at its bottom (Part 3's note said the same): it ends with the
      last cleanup bullet of the Windows Part 4 section.
    - The Linux bash blocks of steps 1, 2, 4 to 11 and 15 were **extracted from the doc by script and
      run verbatim** against live Django; steps 3, 12 to 14 are covered by the E2E and screenshot runs
      below. Step 15's output was recorded from a clean run (`(19, {...})`).
- 2026-10-08 (Claude, Opus 5.5): **Part 4 planned and approved.** The plan is linked above.
  - **Starting point:** HEAD `6cd67d0` ("Part 3: Continue with Google", committed by the user), a
    clean tree.
  - **Research:** read-only only. Django 5.2.17, DRF 3.18.1 and idna 3.20 read in the installed
    source; browser URL parsing checked with Node 24's `URL`. A separate design-review pass is
    folded into the plan.
  - **Changed this session:** only the new plan file and this file. No code, no setup command, no
    `task.md` edit, no env file read.
  - **User decisions (2026-10-08):**
    - The fact quota is a **rolling 24 h** window that counts deleted and removed fact posts.
    - **Pin `idna==3.20`** (already installed through requests/anymail) for UTS #46 host encoding.
    - "Optimistic insert" means **insert on success**: the composer waits for the 201, then the
      returned post goes to the top of Recent with no refetch.
    - Posting away from `/home`: **stay and show a toast**.
  - **Defaults approved with the plan:**
    - 429 `fact_quota_exceeded` + `Retry-After`; 403 `fact_posts_paused` at limit 0.
    - An extra partial index for Recent.
    - Code-point character counting.
    - A read-only posts admin until Part 10.
    - The composer keeps its draft when closed.
    - The other defaults listed in the plan's Context section.
  - **Found during planning** (all handled in the plan):
    - A crafted cursor position reaches the queryset filter and gives a 500.
    - DRF throttles also run on GET.
    - `idna` 3.20 ignores `transitional` and rejects `_` and `ab--cd` in ASCII labels.
    - The browser's `URL` parser turns `\` into `/` and decodes `%xx` in hosts.
    - The platform-settings seed comes from the developer's `.env`, so tests must pin
      `fact_posts_per_day`.

- 2026-10-08 (Claude, Sonnet 5.5): **Part 3 implemented** (uncommitted). Started from HEAD `5339e04`
  ("Plan Part 3", committed by the user), a clean tree that matched this file.
  - **Backend:**
    - `rumor_zero/settings.py` + `env_helpers.py`: `GOOGLE_OAUTH_CLIENT_ID` via `google_client_id(env)`
      (blank = disabled), `allauth.socialaccount` and the Google provider in `INSTALLED_APPS`, the
      `SOCIALACCOUNT_*` settings.
    - New `apps/accounts/google.py` (request pre-check), `usernames.py` (`generate_username`).
    - `middleware.py`: `PROVIDER_TOKEN_PATH` on the allow-list and the issuing set, 404 when
      disabled, the `login` rate bucket, the pre-check.
    - `adapter.py`: `SocialAccountAdapter` (`populate_user`, `pre_social_login`, `save_user`).
    - `signals.py` + `services.py`: `social_account_added` receiver and
      `mark_email_verified_by_google`.
    - `serializers.py`: real `google_connected`. `apps.py`: `TOKEN_LIBRARIES` += `cryptography.x509`,
      `cryptography.hazmat.backends`. `admin.py`: `SocialApp` and `SocialToken` unregistered.
    - Tests: new `test_google_login.py` (60), `test_usernames.py` (38); changed `conftest.py` (root:
      pinned test client ID, no Google network; `tests/`: the `google` fixture), `test_middleware`,
      `test_me`, `test_authentication`, `test_startup`, `test_admin`, `apps/core/tests/test_settings.py`.
    - allauth's six `socialaccount` migrations were applied to the local database; none of ours.
  - **Frontend:**
    - New `src/lib/google-identity.ts` and `src/features/auth/GoogleButton.tsx` (+ tests).
    - `lib/auth/auth-api.ts`: `googleLogin`, `AUTH_PATHS.providerToken`.
    - `features/auth/`: `messages.ts` (`googleErrorMessage`), `LoginForm` and `SignupForm` (the button
      and the "or" rule; optional `googleClientId` prop), `test-helpers.tsx` (`fakeGoogleIdentity`).
    - `playwright.config.ts`: both servers pinned to an empty Google client ID.
  - **Docs:**
    - ARCHITECTURE §2/§3/§7/§9/§10/§12, ANALYSIS (c-29, the b-2 row, the GoogleButton row), STRUCTURE,
      ENV_GUIDE §1.6 (a check step), both `.env.example` comments, MEMORY (a new allauth-social entry),
      `task.md` (criteria, deviations, both status spots), the plan's status line.
    - `docs/test-command.md`: new "Part 3" section in **both** guides (9 steps each) and one word in its
      intro list; nothing else touched.
  - No new dependency and no new env variable. No real env file was edited. `frontend/.env.local` was
    **used, not read**: the dev server read its Google client ID itself for the browser checks, and
    nothing was printed.
  - **Deviations from the plan (all in `task.md`):** `GoogleButton` has no `context` prop (Google's
    `context` only affects One Tap); the forms take a `googleClientId` prop for tests; a closed popup
    is "nothing happens" (Google gives no event).
  - **Test-command notes:**
    - The section is `### Part 3` inside each guide, as the file's other parts are (not `## Part 3`).
    - The file has **no comment marker** at its bottom: it ends with the last cleanup bullet of the
      Windows Part 2 section; the new section follows it.
    - The Linux blocks of steps 4 and 5 were extracted from the doc and run verbatim against live
      Django; the shell one-liners of steps 7 and 8 were run verbatim against a throwaway record in a
      transaction that rolled back.
- 2026-10-08 (Claude, Opus 5.5): **Part 3 planned and approved.** The plan is linked above.
  - **Starting point:** HEAD `36fdb66` ("Part 2: email verification and password reset", committed by
    the user), a clean tree.
  - **Research:** read-only only. allauth 65.19.5 and PyJWT 2.15.1 source, Google's GIS and ID-token
    docs, and a review pass against the code.
  - **Changed this session:** only the new plan file and this file. No code, no setup command, no
    `task.md` edit.
  - **User decisions (2026-10-07):**
    - Google links to an account whose email is unverified. The password is wiped, the email is
      marked verified, and other sessions end at their next refresh.
    - Only `@gmail.com` and `hd` (Workspace) addresses link to an existing account.
    - No linking by email to staff accounts.
    - The username comes from Google's first name, which changes ANALYSIS c-29.
    - The display name stays blank.
  - **Env files:** two research subagents touched the real env files without explicit authorisation.
    One reported only the lengths of the client IDs (both files hold one). The other ran a grep that
    matched `frontend/.env.local`, with values redacted. No value was printed or recorded.

- 2026-10-07 (Claude, Sonnet 5.5): **Part 2 implemented** (uncommitted). Started from HEAD `26ded31`
  ("Part 2 plan", committed by the user), a clean tree that matched this file.
  - **Backend:** `rumor_zero/settings.py` (limits `confirm_email` 1/60s, `confirm_email_daily`,
    `reset_password` pinned, `reset_password_daily`, `reset_password_from_key`;
    `ACCOUNT_EMAIL_UNKNOWN_ACCOUNTS=False`, `ACCOUNT_PREVENT_ENUMERATION=True`,
    `PASSWORD_RESET_TIMEOUT=86400`), `rumor_zero/sentry.py` (+`x-password-reset-key`);
    `apps/accounts/`: `middleware.py` (verify/request/reset on the allow-list, always-anonymous set,
    verify 401→200, reset daily cap), `adapter.py` (`add_message` no-op, email context), new
    `services.py` (`mark_email_verified`, `resend_verification_email`), `signals.py`, `apps.py`
    (receiver + preload of allauth's deferred `jwt`/`cryptography`), `views.py`+`urls.py`
    (`POST /api/v1/me/verification-email/`), `admin.py` (comment); `backend/templates/account/email/`
    (11 files: text + HTML, base layout, sign-up and verification variants, reset); 5 new test files
    (`test_email_verification`, `test_resend_verification`, `test_password_reset`, `test_emails`,
    `test_startup`) plus updated `test_middleware`, `test_tokens` (the `clock` fixture moved to
    `tests/conftest.py`), `test_settings`, `test_sentry`.
  - **Frontend:** `lib/auth/{auth-api,session,AuthProvider,next-path,email-key}.ts(x)`,
    `lib/api/relay.ts` (+`x-password-reset-key`), `features/auth/{useResendVerification,
    VerifyEmailPending,VerifyEmailStatus,ForgotPasswordForm,ResetPasswordForm}`, `LoginForm`
    ("Forgot password?"), `SignupForm` + `useRedirectWhenLoggedIn` (`/verify-email`), `messages.ts`,
    `components/shell/{AppShell,Sidebar,MobileNav,UnverifiedBanner,nav-items}` (New post gating,
    banner Resend), `app/(app)/layout.tsx`, the four route files under `app/(auth)/`, tests next to
    each; `e2e/{email-flows.spec.ts,helpers.ts,mailbox.ts}`, `e2e/auth.spec.ts`,
    `playwright.config.ts` (`EMAIL_PROVIDER=file`).
  - **Docs:** ARCHITECTURE §3/§7/§9/§10/§12/§14, `task.md` (criteria ticked, deviations, both status
    spots), STRUCTURE, ENV_GUIDE (one sentence), MEMORY (three entries), the plan's status line and
    `docs/test-command.md` (new "Part 2" section, 661 added lines, nothing else touched).
  - No new dependency and no new env variable. No real env file was edited or read for its values.
  - **Found and fixed on the way:** allauth defers `jwt` and `cryptography`; several simultaneous first
    sign-ins on a cold server raced inside the import and answered 500 (3 of 4 cold-start E2E runs
    failed before the fix, 5 of 5 passed after). `AccountsConfig.ready()` imports them; `test_startup.py`
    pins it. The bug predates Part 2.
  - **Deviations from the plan (all recorded in `task.md`):** "Forgot password?" sits in a3's options
    row, not the label row; the waiting Resend button is a plain tinted `<button>` (the `Button` variants
    can't be tinted without conflicting classes, and `cn` has no tailwind-merge); shared E2E helpers
    in `e2e/helpers.ts` (auth.spec imports them); `test_startup.py` and the `ready()` preload were not
    in the plan.
- 2026-10-07 (Claude, Opus 5.5): **Part 2 planned and approved** (plan linked above). Started from
  HEAD `353ee19` (the Linux chore, committed by the user), a clean tree in sync with `origin/main`.
  Read-only research only: allauth 65.19.5, Django 5.2 and Next 16.3.8 source, plus a review pass
  against the code. User decisions (2026-10-06):
  - sign-up lands on `/verify-email`;
  - New post is `aria-disabled` until the email is verified;
  - verification emails 1 per 60 s per address, plus 10 resends/day per address; reset requests keep
    allauth's per-minute limits, plus 10/day per address and 50/day per IP;
  - no email to unknown addresses (`ACCOUNT_EMAIL_UNKNOWN_ACCOUNTS = False`).

  Also recorded in the plan: the documented `auth/email/verify/resend` is code-mode only, so resend
  becomes our `POST /api/v1/me/verification-email/`; daily caps need separate allauth actions
  (rates sharing a "per" type share one history); reset links last 24 h.
- 2026-10-06 (Claude, Sonnet 5.5): **Linux machine-switch chore** (docs and comments only; no code,
  config, env or git change). Started from HEAD `d9d1358` (Part 1), a clean tree in sync with
  `origin/main`; CI green (user-reported).
  - **Dual docs, Linux first:** `docs/SETUP.md` (new "Part A (Linux)" with a clone-to-green-tests
    quick start, troubleshooting, A1–A7 for Ubuntu/Debian/Mint, and "Moving to another machine"),
    `docs/ENV_GUIDE.md` (Linux commands beside every PowerShell one, a one-command secret generator
    that prints nothing, new §1.9), `docs/test-command.md` (a bash block above each of the 51 original
    PowerShell blocks: 39 pairs plus 12 "same commands" blocks; the PowerShell blocks are unchanged),
    `AGENTS.md` (Commands block now bash-first, two-machine bullet), header comments of both
    `.env.example` files, and `.gitignore` (+`compose.override.yaml`, the local IPv6 workaround file
    in SETUP; one line beyond the plan).
  - **Left-behind audit:** everything git ignores is regenerable except `backend/.env` and
    `frontend/.env.local`, which hold only local values and are recreated from the examples (ENV_GUIDE
    §1.2 / §1.9). No CRLF in the index (28 tracked files have CRLF only in this Windows working copy),
    no case-only duplicate paths, no shell scripts, every generated brand asset tracked.
  - **Validation:** see "Validation of the Linux clean-room run (2026-10-06)".
- 2026-10-03 (Claude, Opus 5.5): **Part 1 implemented** (committed by the user as `d9d1358`).
  Started from HEAD `349dc96` (the plan + this file, committed by the user), whose workspace matched
  this file's previous state.
  - **Backend** (`backend/apps/accounts/`): `middleware.py` (AuthApiMiddleware: allow-list, CSRF
    guard on every unsafe `/api/auth/` request, header stripping, Turnstile pre-check, refresh-cookie
    injection, secret stripping, JSON bodies, `no-store`), `tokens.py` (row lock + 60 s grace),
    `cookies.py`, `turnstile.py` (stdlib, fails closed), `adapter.py`, `authentication.py`,
    `permissions.py`, `serializers.py`, `views.py` (logout, `/me`, username check), `urls.py`,
    `migrations/0002_verify_superuser_emails.py`, `models.py` (`create_superuser` verified);
    `rumor_zero/{settings,urls,env_helpers}.py` (allauth/headless/email settings, startup guards);
    `conftest.py` (fixed auth values, no network); 11 new test files + `tests/conftest.py`;
    `apps/core/tests/test_settings.py` (new variables, guards, helpers).
  - **Frontend:** `src/lib/auth/{session,auth-api,jwt,session-hint,next-path,route-guard}.ts`,
    `AuthProvider.tsx` (rewritten), `src/lib/turnstile.ts`, `src/lib/api/client.ts` (`token: false`),
    `src/features/auth/` (SignupForm, LoginForm, Turnstile, useUsernameAvailability,
    useRedirectWhenLoggedIn, messages, test-helpers), `src/components/shell/` (UnverifiedBanner,
    loading skeletons, Log out in AccountMenu), `src/app/(app)/layout.tsx` (guard + logout),
    `src/app/(auth)/{login,signup}/page.tsx`, `ui/Avatar.tsx` (initials skip a leading "@"),
    `features/dev/ShellPreview.tsx`, `e2e/auth.spec.ts`, `playwright.config.ts` (`REDIS_URL: ""`),
    `e2e/smoke.spec.ts` (comment), tests next to each file.
  - **Docs and config:** `task.md` (criteria, deviations, both status spots), ARCHITECTURE §0/§2/§3/
    §7 (rewritten)/§9/§10/§12, ANALYSIS c-18 and d, ENV_GUIDE §1.2/§1.3/§1.5/§2.13, STRUCTURE
    markers, MEMORY (allauth gotchas, PowerShell 5.1 JSON quoting, Docker-restart note),
    `docs/test-command.md` (Part 1 section, commands run by the agent), the plan's status line,
    `backend/.env.example` (JWT placeholder 30 → 40 characters, comments), root `.gitignore`
    (`backend/tmp/`).
  - No new dependency and no new env variable. No real env file was edited. `backend/.env` was
    read only through commands that print lengths or a yes/no, never values (it has a 67-character
    `JWT_SIGNING_KEY` different from `DJANGO_SECRET_KEY`, and Cloudflare's always-pass test secret).
  - The local database was migrated (allauth's `account` 0001–0009 and `accounts.0002`), which
    marked the local superuser verified. Test accounts from the checks remain (see test-command
    step 12).
- 2026-10-02 (Claude, Opus 5.5): **Part 1 planned and approved** (`349dc96`). allauth 65.19.5
  behaviour read in the installed source; Turnstile checked against Cloudflare's docs. User
  decisions: CLI superusers count as verified (plus a backfill migration); Turnstile fails closed; a
  non-secret `rz_session` hint cookie.
- 2026-10-01: **CI green, Part 0C done** (`d92f070`; run on `60cfffc`, user-reported). The 0C
  implementation is `6e83866` and the esbuild CI fix `60cfffc`; their validation details are in
  this file's history at `d92f070`.
- Dual-agent setup, the pre-0A correction pass, Parts 0A, 0B and 0D (0D = `b695f09`), the
  multi-source spec change (`bd05636`) and the 0C plan (`90857ec`), all committed by the user.

## Current workspace state

- HEAD is `fec011f` ("Plan Part 11", committed by the user). **Uncommitted:** the whole Part 11 implementation: 48 modified files
  (this file included) and 17 new paths (`git status --short`; `frontend/src/features/appeals/` is one of them).
- Docker (Postgres 18 + Redis) is up and healthy (I started it); both dev servers are stopped; ports 3000/8000 are free.
- The local database has `moderation.0003_appeal` and `0004_appeal_permission` applied. Every `part11-` account of the guide runs
  and the rollback checks (and their posts, appeals and reposts) were deleted; accounts from the E2E runs (`apl_*`, `apr_*` and the
  `mod_*` moderators `moderate()` makes, `fan_*`, `star_*`, `post_*`, `seed_*`, `rep_*`) and their data remain (Django Admin → Users deletes them).
- Ignored artifacts: `backend/tmp/mail/*.log`, `frontend/test-results/`, `frontend/playwright-report/`, and a production build in
  `frontend/.next/` (the last `npm run build` used an empty Google client ID). Scratch scripts, mutation harnesses and screenshots are
  in the session's scratchpad, not the repo.

## Validation of Part 8 (2026-10-10)

- **Backend** (`backend/`, venv, Postgres + Redis up), each exit 0:
  - `python -m pytest` → **2066 passed** (was 1875); `pytest apps/reports apps/pipeline` → **182 passed**: `apps/pipeline/tests/test_routing` 45,
    `apps/reports/tests/`: `test_models` 12, `test_counting` 23, `test_threshold` 36, `test_races` 6, `test_api_report` 44,
    `test_reported_by_me` 8, `test_admin` 6, `test_no_network` 2; the rest are in `apps/social/tests/` (the new repost refusal and the
    seventh strict attribute).
  - `ruff check .` → "All checks passed!"; `ruff format --check .` → "181 files already formatted".
  - `makemigrations --check --dry-run` → "No changes detected"; `manage.py check` → no issues; `sqlmigrate reports 0001` reviewed (the five
    checks, the unique pair, `reports_post_created_idx`, deferrable foreign keys).
  - **Mutation checks** (a rule removed by hand, a test must fail), **46, all caught on the first pass**: the row lock, the `visible`
    filter (removed and deleted), the own and duplicate checks, each counting branch and its exclusions (removed posts, hidden and
    deleted comments), the inclusive age and window edges, the window's missing upper bound, the `open` and counting filters, the
    stored `created_at` and counting flag, `report_count`, each `update_fields` entry, each `merge_flag` rule, the removed guard, `>=`,
    the "entered" return value, the throttle scope, the verified permission, 201, the other-needs-details and length rules, the
    invalid-reason message, `reported_by_me`, both directions of the new repost condition, both error codes and the admin permissions.
- **Frontend** (`frontend/`), each exit 0:
  - `npm run lint`, `lint:tokens`, `typecheck`, `format:check` clean; `npm test` → **117 files, 1580 tests passed** (was 113 / 1510): `ReportModal` 25,
    `ReportButton` 19, `reports-api` 2, `messages` 8, plus `PostActions`, `PostDetail` and `FeedList`.
  - `NEXT_PUBLIC_GOOGLE_CLIENT_ID= npm run build` lists the same routes as Part 7B (Part 8 adds none).
  - `npm run test:e2e` → **38 passed** in dev mode and `CI=1 npm run test:e2e` → **38 passed** against the production build (the 36 earlier
    tests and 2 new ones; one phone test now checks five actions).
  - **Mutation checks, 36, all caught** (32 on the first pass; three survivors were weak tests and were fixed, then re-run, plus one
    extra): no reason preselected, the reason, other-needs-details and length checks, trimming, the posted id, closing while sending, the
    locked fieldset, Cancel and the busy button, `already` and `gone` outcomes, the focus after a server error and on open, both error
    clears, the warning tone, the fact and opinion faces, the clamp, both own-post rules, the unverified block, the reported click, "gone
    is not reported", the lazily built dialog, the resync from the server, the visitor link, the stretched-link layer, the reported
    styling and filled glyph, the card and detail flags, and four `reportFailure` branches.
- **Live checks:** `curl` against Django for steps 3 to 9 of the guide (the blocks run verbatim from the doc, outputs matched); headless
  Chromium at 1280 and 390 px for the card, the dialog (empty, "Something else", success, the focus), the post page, a visitor, an
  unverified account and the phone (0 px of horizontal overflow on `/home`, in the open dialog and on a post page); Django Admin as a
  throwaway superuser (list, filters, search, the read-only detail page, add is 403), deleted afterwards.

## Validation of Part 7B (2026-10-10)

- **Backend** (`backend/`, venv, Postgres + Redis up), each exit 0:
  - `python -m pytest` → **1875 passed** (was 1485); `pytest apps/social` → **695 passed** (was 305): `test_models_repost_bookmark`
    16, `test_services_repost_bookmark` 37, `test_timeline` 63, `test_timeline_db` 140 (50 + 50 seeded walks against an independent
    reference, 30 more through the API with the cache on and off), `test_api_repost` 26, `test_api_bookmark` 17,
    `test_api_bookmark_list` 16, `test_api_feed_reposts` 32, `test_api_user_posts_reposts` 17, `test_admin_repost_bookmark` 6,
    `test_engagement_counts` 21 (+10), `test_no_network` 4 (+1); `test_feed_cache` and `test_services` were rewritten for v2.
  - `ruff check .` → "All checks passed!"; `ruff format --check .` → "154 files already formatted".
  - `makemigrations --check --dry-run` → "No changes detected"; `manage.py check` → no issues; `sqlmigrate social 0003` reviewed (both
    unique pairs, the `reposts_status_allowed` check, the three indexes with `DESC`).
  - **Mutation checks** (a rule removed by hand, a test must fail), **38 + 2 re-runs, all caught after two fixes**: the own and FALSE
    checks, their order, removed posts allowed, the row lock, the lock plus `get_or_create` (race), `status_at_repost`, unrepost on a
    deleted post, both cache busts, the bookmark verification rule, three throttle scopes, every branch of both cursor filters and
    the redundant `<=`, `take_page` (no dedupe, window, probe, the cursor row), the token (zero reposter, canonical form), the stub
    flag, the repost re-read and its time match, the cache shape check, the `post_type` join, the bookmark owner and removed filters,
    the viewer flags, the repost count, the admin gate, page size. Two survived the first pass: the bookmark throttle scope
    (both 300/h: now a test that one bucket doesn't use the other) and `has_module_permission` (dead: removed).
  - **EXPLAIN** (a rolled-back transaction): 300 users, 20,000 posts, 3,000 reposts, 50 follows: the post side is an index scan of
    `posts_recent_idx` at the first page and at a deep one, the reposts side a sequential scan and a top-N sort, the bookmark page
    `bookmarks_user_created_idx` + a primary-key lookup. At **300,000 reposts and 200 follows** the union took 11 to 18 ms; a variant
    with an `IN` branch plus a "my reposts" branch took about 11 ms, so it was not built (MEMORY).
- **Frontend** (`frontend/`), each exit 0: `npm run lint`, `lint:tokens`, `typecheck`, `format:check`; `npm test` → **113 files, 1510
  tests passed** (was 106 / 1410); `NEXT_PUBLIC_GOOGLE_CLIENT_ID= npm run build` (the same routes; `/bookmarks` is still `○`).
  - **Mutation checks**, **31 run, 30 caught at once**: no optimistic flip, no rollback, no toast, no single-flight, an unverified user
    able to repost, the blocked reason ignored, an undo blocked, a visitor button, `aria-pressed`, the name changing with the state,
    the bookmark needing a verified email, a bookmark count, an unfilled saved glyph, the constant hint id, each reason in
    `repostBlockedReason`, the blocked reason not passed, the bookmark on the wrong side or missing, the wrong post id, the header link
    and its `z-10`, Undo for everyone, Undo not removing the item or sending nothing, no failure toast, repeats not hidden, a gone
    post kept, no header, a polled-removed or gone original, the empty state while more can load, reposts not polled, an unavailable
    repost polled, `/bookmarks` asking before the session, its empty text, the two API paths, the own-post code, the header slot.
    The survivor (the zero clamp) got a test.
- **E2E:** `npm run test:e2e` → **36 passed** (dev mode; 32 old + 4 new), five runs in a row, and `CI=1 npm run test:e2e` after the build
  → 36 passed twice (against `next start`).
- **Manual, recorded in `docs/test-command.md` Part 7B** (the doc's Linux blocks of steps 3 to 13, extracted and run verbatim; the diff
  against the doc's expected output was empty after one fixed line): repost 201 → 200 → 204 and every refusal (401, 403, 404, 409
  own, 409 FALSE, the quiet 200 after a post turned FALSE, `status_at_repost`, undo on a removed and a deleted post), bookmarks 201 /
  200 / 204 (unverified allowed, own and FALSE allowed, 404 for removed and deleted), the counts and flags per viewer (no bookmark
  count anywhere), the Following feed with reposts (live label on a cache hit, a stub, an undone repost gone at once, a new repost
  after 31 s, once per page), profile lists and both chips, the bookmark list (only your own, removed and deleted dropped, a cursor,
  a crafted cursor 404, no route for another user's), a cursor walk while posts arrive, 100 + 1 reposts and 300 + 1 bookmarks with
  `Retry-After`, and the three `EXPLAIN` plans.
  - Headless Chromium (screenshots at 1280 and 390 px next to Stitch b1/b3): the repost header line, the four-action bar with the
    bookmark at the right, the stub card and a real Undo repost click, `/bookmarks` with its filled bookmarks, the post page's action
    row; **0 px horizontal overflow** on `/home`, the Following tab and `/bookmarks` at 390 px. Django Admin with a scripted browser:
    a superuser sees both read-only lists; a moderator holding every bookmark permission gets 403 and no "Bookmarks" entry.
- **Not run:**
  - **The Windows (PowerShell) blocks** of the new section (written from the Part 1 to 7 patterns; no PowerShell on this machine), and CI
    on GitHub (the user pushes).
  - A person at a keyboard: the browser steps were driven by scripts. A pixel comparison with Stitch b1/b3 (layout and classes compared
    by eye); a Workers CPU measurement of the feed (Part 18).
  - `npm run build` was run with an empty Google client ID as in CI; the OpenNext/Workers build was not (Linux CI does that).

## Validation of Part 7 (2026-10-10)

- **Backend** (`backend/`, venv, Postgres + Redis up), each exit 0:
  - `python -m pytest` → **1485 passed** (was 1336); `pytest apps/social` → **305 passed** (was 160): `test_models_engagement`
    13, `test_services_engagement` 26, `test_api_like` 21, `test_api_comments` 22, `test_api_comment_create` 25,
    `test_api_comment_delete` 13, `test_engagement_counts` 11, `test_admin_engagement` 13, `test_no_network` 3 (+1); the rest
    unchanged. `apps/core/tests/test_pagination.py` +4 (an ascending list under `TimestampCursorMixin`).
  - `ruff check .` → "All checks passed!"; `ruff format --check .` → "142 files already formatted".
  - `makemigrations --check --dry-run` → "No changes detected"; `manage.py check` → no issues; `sqlmigrate social 0002`
    reviewed (the check constraint, the unique pair, `comments_post_visible_idx` with `WHERE ("deleted_at" IS NULL AND NOT
    "is_hidden")`, `likes_post_created_idx`, the author index).
  - **Mutation checks** (a rule removed by hand, a test must fail), **23, all caught**: create instead of
    `get_or_create`, the visible-post filter letting removed and deleted through, unlike skipping the deleted check, no
    row lock on delete, hidden comments deletable, no author check, hidden and deleted comments counted, `liked_by_me`
    ignoring the viewer, hidden and deleted comments listed, a comment POST without the verified-email permission, no
    post visibility check on the list, the comment throttle on GET, the like throttle scope, newest-first order, `is_mine`
    always false, the content limit at 501, the Hide permission always true, the Following feed ignoring the viewer, no
    defaults on the 201, the detail ignoring the viewer.
  - **EXPLAIN** (a rolled-back transaction, 300 users, 2,000 posts, 40,000 comments, 30,000 likes): the comment list is an
    index-only scan of `comments_post_visible_idx`, the comment count a bitmap scan of it, the like count a bitmap scan of
    `likes_post_created_idx`; a Recent page of 20 annotated posts reads both indexes 20 times (MEMORY).
- **Frontend** (`frontend/`), each exit 0: `npm run lint`, `lint:tokens`, `typecheck`, `format:check`;
  `npm test` → **106 files, 1410 tests passed** (was 99 / 1320); `NEXT_PUBLIC_GOOGLE_CLIENT_ID= npm run build` (the same
  routes; `/home` still `○`).
  - **Mutation checks**, **34 run, 32 caught at once**: no optimistic flip, no rollback state or `onChange`, no
    single-flight, an unverified user able to like, an unfilled liked glyph, no `aria-pressed`, no re-sync with the server,
    the wrong failure toast, blank text allowed, UTF-16 counting, Cmd+Enter and Ctrl+Enter ignored, the draft not cleared
    or lost on failure, no single-flight in the composer, untrimmed text, an unverified composer not locked, Delete on
    everyone's comments, the count not raised or lowered, a deleted comment staying, a new comment not appended, fetching
    before the session is known, appended before the pages, removals ignored, a 404 shown as an error on delete, the
    wrong detail link, buttons below the stretched link, the wrong request body, the discussion on a removed post, the
    bar showing the wrong liked state. The two survivors were equivalent (a redundant `status` test in `LikeButton` and a
    like patch in `PostDetail` that nothing read): both were removed.
- **E2E:** `npm run test:e2e` → **32 passed** (dev mode; 29 old + 3 new), five runs in a row, and `CI=1 npm run test:e2e`
  after the build → 32 passed twice (against `next start`).
- **Manual, recorded in `docs/test-command.md` Part 7** (the doc's Linux blocks of steps 3 to 12, extracted and run
  verbatim; the diff against the doc's expected output was empty): likes (201 → 200, 401, 403 `email_unverified`, 404 for
  unknown, malformed, removed and deleted posts, 204 every time, unlike on a removed post), the counts on the post page and
  in Recent, profile posts and the Following feed (fresh on a cache hit), comments (201 with five keys, trimmed, 400 for
  blank and 501, 500 emoji accepted, 401/403/404), the list (oldest first, `is_mine`, a page of two and the cursor, a
  made-up cursor → 404, no list for a removed or deleted post), delete (401, 403 `not_author`, 204, 404, the row kept with
  `deleted_at`), hide and unhide (gone from list and count, also for its author), 300 + 1 likes and 60 + 1 comments with
  `Retry-After`, and the three EXPLAIN plans.
  - Headless Chromium (screenshots at 1280 and 390 px): the heart and the count on a card (flip, rollback tested in
    unit tests), the comment link, the post page's action row and discussion (post with Ctrl+Enter, delete with the
    dialog, blank and 501 errors), an unverified user (dimmed heart and its toast, a locked composer), a visitor (login
    links), **0 px horizontal overflow** on `/home`, on a post's page and with 300 characters typed at 390 px, and Django
    Admin (the Comments list with its filters and actions, no Add button, Hide and Unhide with their banners and the public
    list changing).
- **Not run:**
  - **The Windows (PowerShell) blocks** of the new section (written from the Part 1 to 6 patterns; no PowerShell on this
    machine), and CI on GitHub (the user pushes).
  - A person at a keyboard: the browser steps were driven by scripts. A pixel comparison with Stitch b1/b3 (layout and
    classes compared by eye); a Workers CPU measurement of `/p/[id]` with the discussion (Part 18; it is client-only).
  - `npm run build` was run with an empty Google client ID as in CI; the OpenNext/Workers build was not (Linux CI does that).

## Validation of Part 6 (2026-10-09)

- **Backend** (`backend/`, venv, Postgres + Redis up), each exit 0:
  - `python -m pytest` → **1336 passed** (was 1160); `pytest apps/social` → **160 passed**: `test_models` 6,
    `test_services` 18, `test_api_profile` 26, `test_api_follow` 23, `test_api_lists` 23, `test_api_user_posts` 19,
    `test_api_feed` 14, `test_feed_cache` 25, `test_admin` 4, `test_no_network` 2; `apps/core` → 138 passed
    (`TimestampCursorMixin` tests with a control, the `FEED_CACHE_SECONDS` settings tests).
  - `ruff check .` → "All checks passed!"; `ruff format --check .` → "132 files already formatted".
  - `makemigrations --check --dry-run` → "No changes detected"; `manage.py check` → no issues; `sqlmigrate social 0001`
    reviewed (both constraints, both indexes with `DESC`).
  - **Mutation checks** (a rule removed by hand, a test must fail), **26, all caught** (two survived the first pass
    and led to a fix and a test): the self-follow check, `get_or_create`, the inactive filters, the deleted and
    removed counter rules, the ids-only cache, the cache busts on follow, unfollow and post, the hydration and feed
    visibility filters, your own posts in the feed, both cursor guards, the verified-email permission, the throttle,
    the cache TTL and bypass, the `post_type` filter, the user-posts filter, `is_following`, `lookup_name`, the
    reputation threshold and the unfollow login.
  - **EXPLAIN** (a rolled-back transaction, 20,000 posts, 401 users, 200 follows): `posts_recent_idx` newest first
    with an author filter: 0.07 ms; for a user following 3 quiet accounts 0.3 ms (MEMORY).
- **Frontend** (`frontend/`), each exit 0: `npm run lint`, `lint:tokens`, `typecheck`, `format:check`;
  `npm test` → **99 files, 1320 tests passed** (was 91 / 1210); `NEXT_PUBLIC_GOOGLE_CLIENT_ID= npm run build`
  (routes: `ƒ /u/[username]`, `ƒ /u/[username]/followers` and `…/following` are new; `/home` still `○`).
  - **Mutation checks**, **44, all caught** (two survived the first pass: the single-flight ref and the "new post
    matches the filter" rule, now tested): optimistic flip, rollback state and toast, single-flight, server sync,
    the unverified and visitor branches, the login `next`, the early viewer mark (StrictMode), the count delta,
    `viewerReady`, anonymous refetch, the filter remount, `isMe`, the chip deselect, the own-profile prepend,
    the FALSE label, the list links, the viewer placeholder, Edit profile, the tab push, the own-row button, the bio
    line, the metadata images, `noindex`, type and canonical, `token: false`, the filter parameter, the lazy
    Following fetch, the visitor tab, the default tab, the prepend to Following, the polled tab, the See Recent
    action, the `empty` prop, the author link's `z-10`, its time outside, the props `href`, the detail link, the
    SSR headers and 404, and the UTC month.
- **E2E:** `npm run test:e2e` → **29 passed** (dev mode; 24 old + 5 new), five runs in a row after the fixes, and
  `CI=1 npm run test:e2e` after the build → 29 passed twice (against `next start`).
- **Manual, recorded in `docs/test-command.md` Part 6** (the doc's Linux blocks of steps 3 to 10, extracted and run
  verbatim; the diff against the doc's expected output was empty): profile as visitor and viewers (10 keys, the
  counters), upper case, 404s for unknown, short and NUL-byte names; follow 201 → 200, 401, 400
  `cannot_follow_self`, 404, 403 `email_unverified`, 204 twice; followers and following (flags, one-per-page cursor,
  a made-up cursor → 404), a person's posts with the type filter and its 400; the counters (2 verified, 1 FALSE,
  the deleted verified post still counted, `posts` 5 → 4); the Following feed (401 for a visitor, newest first,
  the cached value is ids only, your own post at once, a followed user's post only after 31 s, a deleted post
  gone at once); 99 × 200, 1 × 201, 1 × 429 with `Retry-After`; `/u/<name>` HTML (title, `og:*`, `twitter:*`,
  canonical, 307 for upper case, 404 for unknown and short names with `noindex`).
  - Headless Chromium (screenshots at 1280 and 390 px next to Stitch c1/c3/b1): the profile header and counters,
    the filter chips, the followers list, the Following tab; **0 px horizontal overflow** on the profile, the list
    and `/home` at 390 px.
- **Not run:**
  - **The Windows (PowerShell) blocks** of the new section (written from the Part 1 to 5 patterns), and CI on
    GitHub (the user pushes).
  - A person at a keyboard: the browser steps were driven by scripts. A pixel comparison with Stitch c1/c3/b1 (layout
    and classes compared by eye); the Django Admin pages in a real browser (a Django-client test covers the list,
    the search and the 403s); a Workers CPU measurement of `/u/[username]` (Part 18).
  - `npm run build` was run with an empty Google client ID as in CI; the OpenNext/Workers build was not (Linux
    CI does that).

## Validation of Part 5 (2026-10-09)

- **Backend** (`backend/`, venv, Postgres + Redis up), each exit 0:
  - `python -m pytest` → **1160 passed** (was 1087); `pytest apps/posts` → **456 passed** (was 383):
    `test_api_detail` 33, `test_api_delete` 22, `test_api_status` 17, `test_models` 70, `test_services` 24,
    `test_admin` 4, `test_no_network` 4.
  - `ruff check .` → "All checks passed!"; `ruff format --check .` → "106 files already formatted".
  - `makemigrations --check --dry-run` → "No changes detected"; `manage.py check` → no issues.
  - **Mutation checks** (a rule removed by hand, a test must fail), all caught: tombstone blanking
    (content, note), the author exemption, the author check on delete, the delete row lock, the
    `deleted_at` filter in the service, on the detail and on the status endpoint, the 50-id cap, the status
    endpoint's `authentication_classes = []`, its throttle, the delete permission. One survivor was an
    equivalent mutation (a redundant removed-confidence check) and was removed.
- **Frontend** (`frontend/`), each exit 0: `npm run lint`, `lint:tokens`, `typecheck`, `format:check`;
  `npm test` → **91 files, 1210 tests passed** (was 80 / 1089); `NEXT_PUBLIC_GOOGLE_CLIENT_ID= npm run build`
  (routes: `ƒ /p/[id]` is new; `/home` still `○`).
  - **Mutation checks**, all caught: the first delay, the visible-time budget, hidden-tab pause, restart for a
    new id, the 50-id cap, dropping gone and settled ids, abort on unmount, ignoring aborted answers, the
    overlay, hiding gone posts, the card link, the "+N more" link, the tombstone rule, the anonymous
    no-refetch, a 404 as deleted, the busy guard, the fact-allowance note, `token: false`, the OG images,
    the removed `noindex`, the copied origin, the SSR timeout, the SSR 404-versus-5xx split. The StrictMode
    test fails on the old `usePostDetail`.
- **E2E:** `npm run test:e2e` → **24 passed** (dev mode; 20 old + 4 new), and `CI=1 npm run test:e2e` after
  the build → 24 passed (against `next start`).
- **Manual, recorded in `docs/test-command.md` Part 5:**
  - curl against `runserver` and `next dev` (the doc's own blocks, run verbatim): detail as visitor, other
    user and author (23 keys); status (garbage token ignored, 400s for none, `nope` and 51 ids); delete
    (401, 403 `not_author`, 204, then 404; the row still in the database); a removed post (tombstone for
    visitor and other user, full for the author, `removed` in the poll, not in the feed); 120 × 200 then
    5 × 429 with `Retry-After`; `/p/<id>` HTML (title, `og:*`, `twitter:*`, canonical, the claim 8 times;
    404 for deleted and malformed ids; the removed post "Removed post" with `noindex` and none of its text).
  - Headless Chromium: the card's links (claim, DOI, "+1 more" → `#sources`), the page (heading, `FACT`,
    Verdict, Sources (2) as `01`/`02`, Copy link → clipboard = `http://localhost:3000/p/<id>`), the badge
    turning into `VERIFIED 94%` about 10 s after a shell status change, the delete dialog and its toast,
    the 404 page, the feed card turning into the tombstone about 10 s after a removal, the visitor's and
    the author's removed-post pages, **0 px horizontal overflow** at 390 px and the delete dialog (350 px
    wide) fitting.
- **Not run:**
  - **The Windows (PowerShell) blocks** of the new section (written from the Part 1 to 4 patterns), and CI on
    GitHub (the user pushes).
  - A person at a keyboard: the browser steps were driven by scripts. In particular a real **hidden tab**
    was not observed (the pause and the 10-minute stop are covered by fake-timer tests), and neither was
    DevTools' Network tab.
  - The admin pages in a real browser (a Django-client test covers the changelist, the new filter and a
    deleted row); a pixel comparison with Stitch b3 (layout and classes compared by eye); a Workers CPU
    measurement of `/p/[id]` (Part 18).

## Validation of Part 4 (2026-10-09)

- **Backend** (`backend/`, venv, Postgres + Redis up), each exit 0:
  - `python -m pytest` → **1087 passed** (was 704); `pytest apps/posts` → **383 passed**: `test_models`
    69, `test_validators` 195, `test_services` 24, `test_api_create` 41, `test_api_feed` 25,
    `test_api_quota` 7, `test_emergency` 14, `test_no_network` 4, `test_admin` 4.
  - `ruff check .` → "All checks passed!"; `ruff format --check .` → "103 files already formatted".
  - `makemigrations --check --dry-run` → "No changes detected"; `manage.py check` → no issues;
    `sqlmigrate posts 0001` reviewed (every constraint compiles as planned).
  - **Mutation checks** (a rule removed by hand, a test must fail), all caught: backend: the
    backslash, numeric-last-label, localhost, default-port, DOI-case, count, scheme and authority rules
    in the validator (two vectors were added after the first pass showed the `ſ` scheme and fake
    `xn--` labels surviving), throttle on GET, the verified-email permission, removed posts in the feed,
    the cursor guard, the quota boundary, `next_slot_at`, the row lock, emergency refusal, the paused
    limit, deleted posts in the quota, confidence shown for moderators. Frontend: the in-flight guard,
    de-duplication, stale responses, `enabled`, draft clearing (user change and success), the
    closed-during-send toast, sources sent for opinions, the server-row mapping, the verified lock,
    duplicate flagging, the backslash rule, the blank-name rule, the link `rel`, the code-point counter.
  - The race test has a **control run**: with the lock switched off both simultaneous fact posts get
    through (11 of 10), so it proves the lock.
- **Frontend** (`frontend/`), each exit 0: `npm run lint`, `lint:tokens`, `typecheck`, `format:check`;
  `npm test` → **80 files, 1089 tests passed** (was 67 / 747); `NEXT_PUBLIC_GOOGLE_CLIENT_ID= npm run
  build` (routes unchanged; `/home` still `○`).
- **E2E:** `npm run test:e2e` → **20 passed** (dev mode; 15 old + 5 new), and `CI=1 npm run test:e2e`
  after the build → 20 passed (against `next start`).
- **Manual, recorded in `docs/test-command.md` Part 4:**
  - curl against `runserver` (the doc's own blocks, run verbatim): unverified → 403, anonymous → 401,
    opinion and fact 201 with the normalised sources (punycode, port, case, `doi:` stripped), client
    `status`/`confidence_score` ignored, eight 400s with per-index source errors, the allowance
    (7 left, 10 used, 429 `fact_quota_exceeded` with `Retry-After`, `next_slot_at`), the feed and its
    cursor (404 for a hand-made one), six database rules named by constraint, the no-network test.
  - Browser (headless Chromium via a Playwright script, screenshots next to Stitch b1/b2 at 1280 and
    390 px): the Recent tab with its underline, the trigger card, a fact card with `doi.org/… ↗ +1 more`,
    an opinion card in italic, the composer empty, with errors, and with a bad source; **0 px
    horizontal overflow** on `/home` and with the composer open at 390 px. Polish that came out of it:
    the trigger's "New post" pill is hidden on phones (it truncated the placeholder), "Post type" stays on
    one line, the footer wraps (allowance above, buttons below), and the submit button reads "Post" until
    a type is chosen.
- **Not run:**
  - **The Windows (PowerShell) blocks** of the new section (written from the Part 1 to 3 patterns), and
    CI on GitHub (the user pushes).
  - A person at a keyboard: the browser steps were driven by scripts, not by hand.
  - A pixel comparison with Stitch: the layout, classes and states were compared by eye.
  - The admin pages in a real browser (covered by Django-client tests: changelist, search, add/change/
    delete refused, a view-only detail page).

## Validation of Part 3 (2026-10-08)

- **Backend** (`backend/`, venv, Postgres + Redis up), each exit 0:
  - `python -m pytest` → **704 passed** (was 577); the new files 60 + 38.
  - `ruff check .` → "All checks passed!"; `ruff format --check .` → "77 files already formatted".
  - `makemigrations --check --dry-run` → "No changes detected"; `manage.py check` → no issues;
    `manage.py migrate` applied `socialaccount.0001`–`0006`.
  - Mutation checks (rule removed by hand, the Google tests must fail): the Gmail/Workspace rule, the
    staff rule, the inactive rule, the unverified-email rule, the `alg` check, the `kid` length limit
    (after a test was added for it), the verify-on-link receiver and the new user's verified flag all
    made a test fail. The frontend loader and button were mutated the same way (busy guard, handler
    release, initialize-once, hidden without a client ID, clearing before render).
- **Frontend** (`frontend/`), each exit 0: `npm run lint`, `lint:tokens`, `typecheck`, `format:check`;
  `npm test` → **67 files, 747 tests passed** (was 65 / 708); `npm run build` (routes unchanged).
- **E2E:** `npm run test:e2e` → **15 passed** (dev mode), and `NEXT_PUBLIC_GOOGLE_CLIENT_ID= npm run
  build` then `CI=1 npm run test:e2e` → 15 passed (against `next start`).
- **Manual, recorded in `docs/test-command.md` Part 3:**
  - curl against `runserver` with `GOOGLE_OAUTH_CLIENT_ID=` set empty: the endpoint and allauth's
    other social paths answer 404.
  - With a made-up client ID: 403 without `Origin`/the header, 400 for a garbage token, an HS256
    token, a token with no `kid`, a wrong `client_id` and `process: "connect"`, 404 for a GET, 400
    for a forged RS256 token (really sent to Google for its certificates; the internet was
    reachable), the log warning names the variables and never the values, and 30 attempts then 429
    (another source address unaffected).
  - Browser (headless Chromium, Playwright): with the project's own client ID, Google's real button
    renders on `/login` and `/signup` (iframe 410×44 at 1280 px, 316×44 at 390 px), the "or" rule
    follows it, **0 px horizontal overflow**; with a made-up ID the script logs "The given client ID
    is not found"; clicking opens `accounts.google.com/v3/signin/identifier`, and after closing it the
    page, typed text and state are unchanged and no sign-in request was sent; with an empty ID the
    server-rendered pages have no "or" rule.
- **Not run:**
  - **A real Google sign-in** (criterion 4): needs a Google account. The new-user and linking paths
    are covered only by the automated tests with real RS256 tokens and a fake certificate.
  - **The Windows (PowerShell) blocks** of the new section, and CI on GitHub (the user pushes).
  - A pixel comparison with Stitch a2/a3: Google's iframe button replaces Stitch's custom one, so only
    the layout (button, rule, form) was compared.

## Validation of Part 2 (2026-10-07)

- **Backend** (`backend/`, venv, Postgres + Redis up), each exit 0:
  - `python -m pytest` → **577 passed** (was 440); `pytest apps/accounts` → 463 passed; the five new
    files 17 + 15 + 36 + 32 + 1.
  - `ruff check .` → "All checks passed!"; `ruff format --check .` → "73 files already formatted".
  - `makemigrations --check --dry-run` → "No changes detected" (no migration); `manage.py check` → no
    issues.
- **Frontend** (`frontend/`), each exit 0: `npm run lint`, `lint:tokens`, `typecheck`, `format:check`;
  `npm test` → **65 files, 708 tests passed** (was 59 / 562); `npm run build` (the route list has
  `○ /forgot-password`, `○ /verify-email`, `ƒ /reset-password/[key]`, `ƒ /verify-email/[key]`).
- **E2E:** `npm run test:e2e` → **15 passed** (11 old + 4 in `email-flows.spec.ts`), dev mode, including
  five cold-start runs in a row after the preload fix, and `CI=1` after `npm run build` (against
  `next start`) → 15 passed.
- **Manual, recorded in `docs/test-command.md` Part 2** (the Linux blocks of steps 3 to 7 and 9 were
  extracted from the doc by script and run verbatim against live Django; the output matched the doc):
  - curl against `runserver`: sign-up email (text + HTML, logo on `http://localhost:3000`, no backend
    host); resend 429 → (61 s) 204; verification 200 with no cookies, `/me` verified, the same link
    again and a forged key 400 `invalid_or_expired_key`, 403 without `Origin`/header, resend 409 once
    verified, allauth's own `auth/email/verify/resend` 404; forgot-password answers for an existing and
    an unknown address **identical** (status, headers, body; `diff`), one email only; 6th request a
    minute → 429; malformed → 400; key check GET 200/400; weak password 400 and the key survives; reset
    200 with both cookies and no refresh/session token in the body; **another browser's refresh → 400**,
    this one's → 200; the same link again 400; old password 400, new 200; a forged 25-hour-old
    verification key → 400.
  - `EMAIL_PROVIDER=file`: `From`, every `href`/`src` and every URL start with `http://localhost:3000`;
    the mail file is git-ignored.
  - Browser (headless Chromium via Playwright scripts, screenshots next to Stitch a4/a5/a6 at 1280 and
    390 px): sign-up → `/verify-email` with the countdown, banner + Resend, New post `aria-disabled`
    with the toast (rail and phone tab), the verified/already-verified/expired states, forgot
    idle/sent, reset weak/mismatch/expired; **0 px horizontal overflow** on every page at both widths.
    Two visual fixes came out of it (long emails broke mid-word with `break-all`; the waiting Resend
    button is now a4's tinted state).
- **Not run on this machine:** the **Windows (PowerShell) blocks** of the new test-command section
  (written from the Part 1 patterns: JSON through files, `curl.exe`, no `&&`), and CI on GitHub (the
  user pushes). The `ruff`/`pytest` checks used the venv's own tools.
- **One unexplained failure:** once, `pytest apps/accounts` printed `1 failed, 462 passed` while both
  dev servers and Redis were running and Docker was about to be wiped by the reboot. The same command
  then passed 17 times in a row (including 3 on a single CPU kept busy by a spinning loop), and the full
  suite passed right before and after. The failing test's name was not captured. If it ever recurs,
  run `pytest apps/accounts -q -x` and note the test.

## Validation of Part 1 (2026-10-03)

- **Backend** (`backend/`, venv, Postgres + Redis up), each exit 0:
  - `python -m pytest` → **440 passed** (was 200); `pytest apps/accounts` → 327 passed; no warnings.
    The same suite also passes with only `backend/.env.example`'s values in the process env (what
    CI uses), as does `manage.py check`.
  - `ruff check .` → "All checks passed!"; `ruff format --check .` → "66 files already formatted".
  - `makemigrations --check --dry-run` → "No changes detected"; `manage.py check` → no issues;
    `check --deploy` passes with a production-like env (`test_settings.py`).
  - The four concurrency tests (threads, separate connections) passed 5 runs in a row.
- **Frontend** (`frontend/`), each exit 0: `npm run lint`, `lint:tokens`, `typecheck`,
  `format:check`; `npm test` → **59 files, 562 tests passed** (was 51 / 412); `npm run build` →
  `/login` and `/signup` still `○`, `/api/[...path]` `ƒ`.
- **E2E:** `npm run test:e2e` → **11 passed** (8 smoke + 3 auth), with Playwright starting Django
  and `next dev`, and again in CI mode (`$env:CI="1"` after `npm run build`, against `next start`).
  Also passed reusing running servers.
- **Manual** (all recorded in `docs/test-command.md` Part 1):
  - curl against `runserver`: signup sets both cookies with the right flags, the body has only
    `access_token`; the console email links to `http://localhost:3000/verify-email/<key>`;
    refresh rotates, the old cookie works at once and fails after 61 s; 403 `csrf_failed` without
    `Origin` or `X-Requested-With` (refresh and logout); logout → 204 + both cookies deleted, the old
    cookie → 400, no cookie → 401; the access token still works until expiry (by design); an
    unlisted allauth endpoint → 404.
  - Through the relay: 10 failed logins → the 11th `too_many_login_attempts`; a direct call from
    `127.0.0.1` isn't blocked (per-address).
  - Browser (Playwright/Chromium scripts): screenshots of `/signup` and `/login` next to Stitch a2/a3
    at 1280 px (same card width; differences are the planned ones), 390 px with 0 px overflow; real
    sign-up with the test widget → `/home` + banner; cookies (`rz_refresh` host-only, HttpOnly, Lax,
    `/api/auth/`; `rz_session` readable), empty local/session storage, `document.cookie` =
    `rz_session=1`; field errors (email taken, username taken/reserved/invalid, common password);
    the always-fail Turnstile secret → the message under the widget and a reset; the rate-limit
    banner; `/settings` → `/login?next=%2Fsettings`; logout in one tab logs out the other; the
    loading placeholder; Log out at the end of the phone sheet.
- **CI on GitHub:** green for Part 1 (user-reported 2026-10-06), including the E2E job's Turnstile
  test-key sign-up.

## Validation of the Linux clean-room run (2026-10-06)

Goal: prove that a fresh Linux checkout plus the guides works. Method: pack
`git ls-files -co --exclude-standard` (what `git pull` brings, plus the uncommitted doc edits; no
real env file) into a tar, extract it into a fresh **Ubuntu 24.04 container** that shares its network
namespace with throwaway `postgres:18` and `redis:8-alpine` containers (so `localhost:5432/6379` is as
in the guide), then run the guides' Linux commands. Docker Desktop's Linux engine; all exit codes 0.

- **SETUP Part A (Linux):** A1 `apt install git`; A2 `apt-cache policy python3.13` (none on Ubuntu
  24.04), deadsnakes PPA, `python3.13` = **3.13.16**, `venv` works; A3 nvm **v0.40.8** →
  `nvm install 24` = **Node v24.21.0**, npm 11.19.0; A7 `jq`, `npx playwright install --with-deps
  chromium` (Chrome Headless Shell 153); A4: the Docker apt-repository block extracted verbatim from
  SETUP resolved (`docker-ce` 5:29.8.2, `docker-compose-plugin` 5.6.0 candidates); not installed.
- **ENV_GUIDE §1.2 one-command generator** (extracted verbatim from the doc): writes four 67-character
  values, `PROXY_SHARED_SECRET` identical in both files, `JWT_SIGNING_KEY` ≠ `DJANGO_SECRET_KEY`;
  nothing printed.
- **Backend:** `pip install -r requirements-dev.txt`, `migrate`, `createsuperuser --noinput`,
  `python -m pytest` → **440 passed**; `ruff check .` → "All checks passed!"; `ruff format --check .`
  → "66 files already formatted"; `makemigrations --check --dry-run` → "No changes detected";
  `manage.py check` → no issues.
- **Frontend:** `npm ci`; `lint`, `typecheck`, `lint:tokens`, `format:check` clean; `npm test` →
  **562 passed**; `npm run build` OK (route list as before, `/api/[...path]` `ƒ`).
- **E2E:** `npm run test:e2e` → **11 passed** (Django + `next dev` started by Playwright).
- **docs/test-command.md, Linux blocks run verbatim** (extracted by script) against live Django +
  `next dev`: Part 0A steps 3 and 4, Part 1 steps 1, 3, 4, 5 (including the 61 s refresh grace, the
  CSRF 403s, logout, 11 relay logins with the 11th `too_many_login_attempts`, and the final direct
  request from `--interface 127.0.0.2` → `email_password_mismatch`); Part 0B step 3; Part 0D steps 1, 3,
  4, 6, 7, 10, 11. Output matched the shared expected text each time. `npm run brand:build` on Linux
  reproduced every committed brand asset byte for byte (`git status` clean).
- **Syntax:** `bash -n` passes on all 51 bash blocks of `test-command.md`, all 14 of `SETUP.md`, all
  5 of `ENV_GUIDE.md` and the one in `AGENTS.md`. A script confirmed all 51 original PowerShell
  blocks survive unchanged (39 as the Windows twin, 12 as "same commands" bash blocks) and all 15
  expected-output blocks are identical.
- **Not provable here (listed in the guides as "if X fails, do Y"):** installing Docker Engine and the
  `docker` group on the real PC, `docker compose up -d` itself (sibling containers stood in for it;
  only the override file's syntax was checked with `docker compose config`), IPv6 `[::1]` publishing,
  GitHub SSH auth, Linux Mint and Debian specifics (Playwright, Python 3.13 packaging), and Windows
  Docker Desktop behaviour is unchanged.
- **FYI, not caused by this chore:** `npm audit` reports 5 high-severity advisories, all in one
  **dev-only** chain (`braces` → `micromatch` → `fast-glob` → `@next/eslint-plugin-next` →
  `eslint-config-next`); production dependencies: 0. The "449 packages / 0 vulnerabilities" text in
  `test-command.md` Part 0B/0D step 1 dates from Part 0B (the tree is 737 packages now).

## Next exact action

1. **User:** review the diff and the Part 11 section of `docs/test-command.md` (its Linux steps 3 to 6, 9 and 12 take about two
   minutes; steps 7, 8, 10 and 11 are in the browser and need both servers). Then commit, and push so CI runs; report the CI result
   (Part 2's to Part 11's jobs). Still open from Part 3: the real-Google check (`docs/test-command.md` Part 3, steps 7 and 8).
2. **Next part:** Part 11B (the credibility score), from `task.md` (it depends on 7B, 10 and 11, all done). Fresh session (`/clear`), first
   `git status` and `docker compose ps` (start the containers with `docker compose up -d` if they are down). Read the "From Part 10"
   and "From Part 11" notes in `task.md` Part 11B: the hooks go in `moderation.services` (`_perform` and `file_appeal`, same transaction,
   after the post's row lock) and in `reports.services.resolve_open_reports` (it must return the reporters for `report_upheld`).

## Blockers or user decisions

- None open.
- User decisions for Part 11 (2026-10-13), now in ARCHITECTURE §2/§4/§8/§9/§10 and ANALYSIS c-43: Restore of an already-checked fact goes to
  the review queue; Keep removed writes `kept_removed`; the removal reason reaches the author as `removal_reason` (24 keys); your own profile
  lists your removed posts; Remove during an open label appeal closes it `upheld`; Restore and Keep removed take internal notes only.
- (The Part 8 plan appendix's A1 and A2 were not adopted: A1 is not needed, A2 is a Part 9 follow-up.)
- User decisions for Part 8 (2026-10-10), now in ARCHITECTURE §4d/§5/§9/§10 and ANALYSIS c-40: the report action
  is a flag button (not an overflow menu); a young account's report counts with a non-removed post or a non-hidden comment
  (deleted ones count); FALSE posts go to review at the threshold as the docs say, and a post under review after being FALSE
  can't be reposted.
- User decisions for Part 7B (2026-10-10), now in ARCHITECTURE §4d/§8/§9/§10 and ANALYSIS c-39: `BookmarkAdmin` is
  superuser-only; a repost of a deleted or removed original can be undone (204, and Undo repost on your own unavailable card); the
  page hides later repeats of a post across the pages of a list; profile chips filter reposts by the original's type.
- User decisions for Part 7 (2026-10-10), now in ARCHITECTURE §2/§8/§9/§10 and ANALYSIS c-38: hidden comments are Django
  Admin only (not in the API for staff either); deleting your own comment is a soft delete (`deleted_at`); CommentAdmin
  has Hide **and Unhide**.
- User decisions for Part 6 (2026-10-09), now in ARCHITECTURE §3/§9/§10 and ANALYSIS c-37: Recent is the first
  and default `/home` tab, Following the second (signed-in only); the Following cache holds only ids; `verified`
  and `FALSE` counters include deleted posts (not removed ones); author names and avatars link to profiles.
- User decisions for Part 5 (2026-10-09), now in ARCHITECTURE §3/§9 and ANALYSIS b-2: a removed post's public
  view is the same 23 keys with the text, sources, note, confidence and verdict source blanked (the author
  sees it in full); the public status endpoint has a `status_poll` throttle of 120/min per client IP.
- User decisions for Part 5 (2026-10-09), to go into ARCHITECTURE §3/§9 when built: a removed post's
  public view is the same 23 keys with `content`, `sources`, `verdict_note`, `confidence_score` and
  `verdict_source` blanked (the author sees it in full); the public status endpoint gets a `status_poll`
  throttle of 120/min per client IP.
- User decisions for Part 4 (2026-10-08), now in ARCHITECTURE §3/§4c/§10 and ANALYSIS D7: the fact
  quota is a rolling 24 h window (deleted and removed posts count); `idna==3.20` is pinned; "optimistic
  insert" means insert on success; posting away from `/home` toasts.
- User decisions for Part 1 (2026-10-02), now in ARCHITECTURE §2/§7: superusers are verified
  (createsuperuser + backfill migration); Turnstile fails closed; the `rz_session=1` hint cookie.
- User decisions for 0C (2026-10-01), in ARCHITECTURE §10: the reduced logged-out shell; phones get a
  top bar plus five bottom tabs with an account sheet; marketing links only to existing pages.

## Follow-ups noted during Part 11 (still open)

- **11B:** reputation hooks in `file_appeal`'s outcomes and in `_perform` (see `task.md` 11B "From Part 11"); the negative ledger rows'
  appeal link. **13:** `appeal_resolved` from `_perform` (`task.md` 13). **14:** appeals in the export (already in its scope).
- **16:** whether a deleted post's open appeal should be closed (today it stays open and moderators refuse a deleted post); the `appeal` throttle
  (5 a day) with real usage; whether `Escalate` on a removal appeal should also show in a senior-only filter.
- **Admin polish:** the confirmation page doesn't say a Restore of a never-checked fact will be re-checked ("Removed → Pending"): fine today.
- **Tests that could be added if they bite:** `ProfilePosts` has no component test of its own (the owner's removed card is covered through
  `FeedList`, `RemovedPostCard` and the E2E test).

## Follow-ups noted during Part 8 (still open)

- **Part 9:** `apps/pipeline/` exists (only `routing.py`); add `contract.py`, `clients.py`, `processor.py`, `apply_pipeline_result` and
  `process_pending` to it. The processor selects `status='pending'` only, so a pending fact that reports sent to review would never be
  checked: also take under-review facts with `pre_review_status='pending'` and no `pipeline_checked_at`. A decisive late FALSE on a
  reported post sets `pre_review_status=verified_false` without the label ever being public, which `social.services.repost`'s new
  "under review after FALSE" refusal would reveal: narrow that condition or accept it. The processor must not hold the post row lock
  across its 20 s call (reports, reposts and deletes would wait behind it).
- **Part 10:** moderators get `reports.view_report` (and the `PostAdmin` inline); Dismiss and the other actions set `resolved_at` (and
  `resolved_by`) together with `status` (`reports_resolution_consistent`), and mark open reports `dismissed` or `actioned`; the queue
  orders by `report_count`.
- **Part 11:** a label appeal on a post under review whose `pre_review_status` is `verified_false` must not be allowed, or `merge_flag`
  (which raises for an appeal onto a post under review for the pipeline, reports or both) needs a rule for it.
- **Part 11B:** `report_upheld` reads `reports` (open at the moment a moderator removes or marks FALSE, at most 4 per reporter per 30
  days); keep the lock order post first, then users (sorted): foreign keys are deferrable, so their `KEY SHARE` locks are taken at commit.
- **Part 11C:** `apply_report_threshold` gets the `emergency_report_threshold` branch (`now` is already its parameter).
- **Part 13:** notify the post's author when `posts.services.record_report` returns True (it entered review), in the same transaction;
  `reports.services.file_report` is the single write path to hook into.
- **Part 14:** export and account deletion include reports (a deleted reporter's rows cascade but `report_count` and the post's review
  state stay).
- **Part 16:** the `report` rate (10/h) is a guess; the dev gallery has three copies of the reason list (`StitchSections`,
  `FormSections`, `reasons.ts`); `FollowButton`'s constant hint id (from Part 7B).
- **Known limits:** a report made in one list isn't copied into another mounted list showing the same post (every route change refetches);
  the post page shows "Report" for a moment and then "Reported" once the signed-in view lands, for someone who reported before.

## Follow-ups noted during Part 7B (still open)

- **Part 8:** the flag button joins the action bar's right group; decide whether a soft-deleted comment counts toward
  `counts_toward_threshold` (Part 7's follow-up). **Both settled in the Part 8 plan (2026-10-10).**
- **Part 10:** moderators get no permission on `social.Bookmark` (and never will: it is superuser-only); `social.view_repost` is theirs to
  grant if wanted. The Hide/Unhide permission is Part 7's.
- **Part 11B:** repost score events read `status_at_repost` (always one of `pending`, `published`, `verified_true`, `under_review`); an
  undone repost after the verdict doesn't undo the event; a re-label reverses the events of every reposter (`reposts` by post).
- **Part 11D:** daily repost counts use `reposts_post_created_idx`; comment counts must use the partial index's predicate (Part 7).
- **Part 13:** the `repost` notification hooks into `social.services.repost` (de-duplicated per (recipient, actor, type, post); no
  notification for your own repost; none when the repost already existed: the service returns `created`).
- **Part 14:** export and account deletion include bookmarks and reposts (both cascade); a deleted account's reposts leave other people's
  feeds on the next page load (hydration drops a repost whose user row is gone).
- **Part 16:** the `repost` and `bookmark` rates are guesses; the reposts side of the Following union is a sequential scan and a top-N sort
  (11 to 18 ms at 300,000 reposts and 200 follows); `FollowButton` still uses a constant hint id; a stored repost counter if a post reaches
  many thousands of reposts (like likes).
- **Known limits:** your new repost isn't inserted into an open list; a like, repost or bookmark made in one list isn't copied into
  another mounted list showing the same post (Recent and Following on `/home`); if the repost that won a page's once-per-page rule is
  undone, a follower's cached page has no item for that post until the TTL (30 s) ends; a bookmark you remove on `/bookmarks` stays until
  the next load.

## Follow-ups noted during Part 7 (still open)

- **Part 7B:** `repost_count`, `reposted_by_me` and `bookmarked_by_me` join `with_engagement` (`apps/social/engagement.py`;
  `PostSerializer` reads them strictly like the like counts, and `engagement_defaults` sets their zeros); `PostActions`
  gets the two buttons; the like button's local state means a repost made in one list isn't copied into another mounted
  list either (same limit, same repair: a refetch).
- **Part 8:** decide whether `counts_toward_threshold` ("≥1 post or comment") counts a soft-deleted comment (the
  principle used for posts and the fact quota says it does; MEMORY). **Settled 2026-10-10: it does (hidden ones don't).**
- **Part 10:** grant `social.change_comment` to the Moderators group (Hide/Unhide are already gated on it); the review
  queues skip deleted comments; `moderation_actions` has no comment kind, so Hide/Unhide stay in Django's admin log
  unless Part 10 adds one.
- **Part 11D:** daily comment counts use the predicate of `comments_post_visible_idx` (not hidden, not deleted).
- **Part 13:** `like` and `comment` notifications go in `social.services.like` / `add_comment` (the single write
  paths); a deleted or hidden comment must not notify; `like` is de-duplicated per (recipient, actor, post).
- **Part 14:** the data export includes comments (soft-deleted ones too?); account deletion cascades them (the author FK
  has its own index).
- **Part 16:** the `like` (300/h) and `comment` (60/h) rates are guesses; the counts are correlated subqueries (a stored
  counter if a post reaches many thousands of likes); the cursor guard for any list still on the bare core pagination.
- **Part 18:** a Workers CPU check of `/p/[id]` (the discussion is client-only, so the server side is unchanged).
- **Minor:** a comment you add while older pages are unloaded stays last until they load; comment drafts aren't kept
  across navigation; comments don't update live.

## Follow-ups noted during Part 6 (still open)

- **Part 7/7B:** counts and `*_by_me` go into `PostSerializer` (fresh, since the Following cache holds only ids);
  the action bar goes on `PostCard` and `PostDetail`; 7B makes the Following cursor `(activity_at, item id)`, busts
  your feed cache on repost, and `FeedList` starts rendering `repost` items (it skips them now).
- **Part 11B/11D:** `reputation` is already in the profile and row objects (`score: null` until 3 events); the
  header shows the credibility ring and a verified count then; the profile's `verified`/`false` counters and the
  ledger's must agree (both count deleted posts).
- **Part 12:** people search reuses `UserRow` and `FollowButton`. **Part 13:** a `follow` notification (the follow
  service is the one place to call it). **Part 14:** Edit profile (`/settings` is a placeholder), username
  rename. **Part 14B:** the profile should use the 256 px photo (`avatar_url` is the 96 px URL).
- **Part 16:** `follow` 100/h and `FEED_CACHE_SECONDS` 30 are guesses; Upstash command use (a Following first-page
  view costs one to three commands); the cursor guard for the other lists that use the core `CursorPagination`;
  the E2E suite is near allauth's 20 sign-ups a minute (MEMORY); consider the EXPLAIN note (MEMORY) if someone
  follows only quiet accounts in a large table.
- **Part 18:** Workers error 1102 on `/u/[username]` (same escape hatch as `/p/[id]`, ANALYSIS c-35); check
  `curl` of a deployed `/u/<name>` still shows the tags and that `/u/Ada` redirects.
- **Minor:** unfollowing inside your own Following list doesn't update the count in the tab above it; a signed-in
  visitor sees a skeleton where the Follow button goes until their own profile fetch lands; `Connections` pages are
  dynamic (`ƒ`) in the build although they read nothing on the server.

## Follow-ups noted during Part 5 (still open)

- **Part 6:** profile post lists reuse `useCursorFeed`, `FeedList` (pass `statusUpdates` and `gone`) and
  `useStatusPolling`; a profile page that sets `openGraph` must set its images too.
- **Part 7/7B:** counts and `*_by_me` (the post object already has the keys) and the action bar go on
  `PostDetail`; comments sit below the Sources list; `PostCard` has no action bar yet.
- **Part 10:** the review queue must skip posts with `deleted_at` set (the posts admin only filters them);
  the admin stays read-only and has no "deleted" column filter label other than Django's "By deleted at".
- **Part 11:** `RemovedPostCard` (public and author variants) replaces the detail page's basic tombstone and
  the author's warning note; the removal reason, `can_appeal`, `appeal_status` and the appeal button come
  with it; the `NotAuthorError` (403 `not_author`) is reusable for appeals.
- **Part 11C:** the page's "Posted as an emergency on …" note; `emergency_active` is computed once per
  request, so a page left open doesn't flip it (the poll doesn't carry it).
- **Part 16:** the `status_poll` rate (120/min) is a guess to revisit with real usage; polling and delete
  have no CSP impact; consider caching the SSR post read; the cursor guard for other lists (Part 4's item).
- **Part 18:** Workers error 1102 (10 ms CPU) on `/p/[id]`: if it bites, the metadata-only fallback or
  Workers Paid is the escape hatch (ANALYSIS c-35). Also confirm `AbortSignal.timeout` and `fetch` with
  `cache: "no-store"` behave in the OpenNext build, and that `curl` of a deployed `/p/<id>` still shows the tags.
- **Minor:** the author sees no Delete button until the signed-in fetch lands (the server render is the
  anonymous view); a first `next dev` compile of `/p/[id]` takes a few seconds.
- **Any Next upgrade:** re-read MEMORY "Next 16.3.8 metadata…" and run `post-metadata.test.ts` and
  `e2e/post-detail.spec.ts` (the `curl` tag checks).

## Follow-ups noted during Part 4 (still open)

- **Part 5 (all done in Part 5):** `/p/[id]` and the detail endpoints, "+N more" as a link, `SourceList`,
  the author's soft delete (the quota still counts the post, by design) and `useStatusPolling`.
- **Part 6/7B:** `useCursorFeed`, `FeedList` and `FeedPagination` are written to be reused (a second tab,
  profile lists); reposts are skipped in `FeedList` for now (`item.kind === "post"` only).
- **Part 9:** `routing.py` imports `is_active_emergency` from `apps/posts/emergency.py`; a fact post
  stays `pending` because nothing processes it yet. `create_post` has no inline kick.
- **Part 10:** the posts admin is read-only; the moderator actions go through `moderation.services`.
- **Part 11C:** the composer's emergency toggle (hidden), the `emergency` block of `fact-quota`, the
  `pinned` list (`FeedPagination` already answers `pinned: []`).
- **Part 12:** `search_vector` (a `GeneratedField` + GIN index) is the one `Post` column still missing.
- **Part 16:**
  - An **idempotency key** for `POST /api/v1/posts/`: a relay timeout (503 `backend_waking`) after Django
    saved the post makes a retry a duplicate. The composer's message says "If it doesn't show up in
    Recent in a minute, try again."
  - The core `CursorPagination` lets any crafted position reach a queryset filter (500); `FeedPagination`
    guards it, other lists that use the core class need the same.
  - CSP: nothing new (source links are plain `<a>`; the server never fetches them).
  - Toasts still render below an open `<dialog>` (0B follow-up); the composer shows its errors inline.
  - A source check that the page can't do: an `xn--` label that isn't a real A-label gets the server's 400
    on its row (accepted trade-off; a punycode library would close it).
- **Any django-allauth / DRF / `idna` upgrade:** re-read MEMORY "DRF and Django facts that Part 4's posts
  API depends on" and "Source links…", and run `apps/posts/tests/` and `sources.test.ts` (the shared
  vectors).

## Follow-ups noted during Part 3 (still open)

- **Part 14:**
  - Settings "Signed in with Google" and `process: "connect"` / disconnect.
  - Username rename (a Google user starts with `ada`, `ada_4821` or `member_xxxxxx`).
  - A "Google connected" email (`ACCOUNT_EMAIL_NOTIFICATIONS` is False) and a password-changed email.
  - Google-only users have no usable password: they set one with "Forgot password?".
  - Deleting an account must delete its `SocialAccount`.
- **Part 16:**
  - CSP and COOP for Google Identity Services (ARCHITECTURE §12): `https://accounts.google.com/gsi/`
    for script, style, frame and connect; COOP unset or `same-origin-allow-popups`.
  - Cache Google's certificates (allauth fetches them on every sign-in, 5 s timeout).
  - Two sign-ups racing for the same new username or email hit an `IntegrityError` (500): retry or 409.
  - `jti` replay protection uses the shared cache (per process when `REDIS_URL` is blank).
- **Part 10:** `SocialAccount` is registered in the admin; make it read-only for moderators.
- **Any django-allauth upgrade:** re-read the MEMORY entry "django-allauth 65.19.5 social login"
  (the `provider/token` view, `jwtkit`, `wipe_password`, the signal order) and run
  `apps/accounts/tests/test_google_login.py`.

## Follow-ups noted during Part 2 (still open)

- **Part 10:** an admin action "mark email verified" (logged); make the admin refuse sessions created by
  headless login (already listed for Part 10).
- **Part 14:** a password-changed notification email, with change password; marking the address verified
  on a reset (it proves the inbox) was not asked for and is not done.
- **Part 9/17:** `clearsessions` (already listed).
- **Part 16:**
  - `GET auth/password/reset` answers `data.user` (id, email, username) to anyone holding a valid key;
    the page ignores it. Consider stripping it in `AuthApiMiddleware`.
  - A provider failure on resend still answers 204 (the adapter swallows send errors, as at sign-up).
  - The verification email cooldown counts the sign-up email, and the banner's Resend has no countdown
    on first load, so a first click right after sign-up gets a 429 toast. Harmless; a signal from the
    sign-up response could pre-start it.
  - Brevo's free tier is 300 emails a day (§12): the per-address and per-IP caps bound a single
    abuser, not a crowd.
- **Any django-allauth upgrade:** re-check `send_verification_email_for_user`, `get_address_for_user`,
  the deferred-import preload (`TOKEN_LIBRARIES`) and the rate-limit key rule (MEMORY, 2026-10-07).

## Follow-ups noted during Part 1 (not done, per the part's scope)

- (Part 2 items done: the allow-list, the branded templates, "Forgot password?" on `/login`, Resend in
  `UnverifiedBanner`, the file mailbox, and reset ending other sessions.)
- (Done in Part 3: the allow-list, `google_connected`, and a social sign-up that never pends.) Original note: add `allauth.socialaccount` and `auth/provider/token` to the allow-list; make
  `google_connected` real. A *pending* social signup needs `X-Session-Token`, which the middleware
  strips and the relay doesn't forward: auto-signup must never pend, or add a short-lived flow cookie.
- (Part 4: `IsEmailVerified` is now used by `POST /api/v1/posts/`, and the posts calls never use
  `token: false`.)
- **Part 6/14:** sign-up sets no display name, so the rail's user card shows `@username` twice (name
  fallback + handle). Consider showing the handle once when the display name is blank.
- **Part 9/17:** run `clearsessions` periodically (expired token sessions pile up in Neon).
- **Part 10:** as defence in depth, make the admin refuse sessions created by headless login.
- **Part 14:** deleting an account must also delete its sessions.
- **Part 16:**
  - CSP for Turnstile (`challenges.cloudflare.com` script and frame).
  - Check what siteverify returns for `action`/`hostname` with the test keys, and add those checks if
    possible.
  - Brute-force protection for the Django Admin login; Argon2's 100 MiB per hash against Render's
    512 MB (worker count or `memory_cost`).
  - Two `rz_refresh` cookies make refresh **and logout** answer 400 (by plan). A stale duplicate
    with another path would block logout until it expires; revisit if it is ever seen.
  - E2E tests write accounts into the local dev database; consider a separate E2E database.
- **Part 17:** fail a deploy that uses a Turnstile test secret.
- **Visual (minor):** the shared `AuthLayout` card (0C) is `p-space-xl sm:p-11` with 44 px inputs;
  a3 used `px-space-xl pt-10 pb-9` and 40 px inputs. Accepted.

## Follow-ups noted during 0C (still open)

- (Part 1 items done: CSRF for refresh/logout and allauth views, `avatar_url` in `/me`, the 401
  refresh hook, `loading`, Log out.)
- (Part 4 items done: `onNewPost` is wired to the composer; `PostCard`'s header no longer wraps the
  author name at 390 px.)
- **Part 14B:** photo uploads rely on the relay's 6 MB body cap (`MAX_BODY_BYTES` in `relay.ts`).
- **Part 15:** polish `not-found`/`error`/`global-error` and the placeholder pages; `/how-it-works`,
  `/privacy` and `/terms` are placeholders.
- **Part 18:**
  - On Workers, confirm `/api/health/` through the relay (already in the production smoke test) and
    that `request.signal` doesn't abort early.
  - Never build the Worker from a checkout with a real `.env.local` (SETUP B3 note).
  - Replace `vars.BACKEND_ORIGIN` in `wrangler.jsonc`.
- **Dependency upkeep (Part 16 Dependabot, or any OpenNext upgrade):**
  - Remove the `esbuild` devDependency once an `@opennextjs/cloudflare` release declares `esbuild`
    itself (upstream #1339 / PR #1353). Then re-run the OpenNext build: in Docker first, then CI.
  - When bumping `wrangler`, keep `esbuild` on wrangler's own pin, so one copy is shared and it stays
    inside vite's peer range.
  - `npm audit` (2026-10-06): 5 high advisories in the dev-only `braces` → `micromatch` →
    `fast-glob` → `@next/eslint-plugin-next` → `eslint-config-next` chain; production dependencies
    clean. Let Dependabot (Part 16) or a deliberate `eslint-config-next` bump resolve it; don't run
    `npm audit fix --force` blindly.
  - `npm ci` on Linux warns that `eslint@9.39.5` is deprecated. Moving to a supported ESLint major is
    a separate, deliberate upgrade: check the flat config and `npm run lint`.
  - Any django-allauth upgrade: re-check the internals Part 1 depends on (MEMORY entry, 2026-10-03).
- **Minor:**
  - `<Logo/>` renders 47.86 px instead of 48 px tall at `lg` (preflight `img { height: auto }`).
  - The toast offset (`bottom-20` below 768 px) also applies on marketing pages, where there is no
    bottom bar.

## Follow-ups noted during 0D (still open)

- Part 2: email templates use `FRONTEND_ORIGIN/brand/email-logo.png` (320 px wide, shown at 160).
- Part 10: `templates/admin/base_site.html` uses the static `core/brand/logo-admin.png` (158x64).
  `collectstatic` must pick it up (Part 17 already lists collectstatic in the build).
- The `theme_color` of the web manifest is the dark plate colour; revisit if a light toolbar is
  preferred.
- If the logo is re-exported, check `markSelector` in `scripts/brand/brand.config.json` and compare
  the printed contrast table with ARCHITECTURE §14.

## Follow-ups noted during 0B (still open)

- Part 16: subset the 4 MB Material Symbols font to the glyphs actually used.
- Toasts render below an open `<dialog>` (top layer). If a toast must appear over a modal, move the
  toast region into a popover. Background scroll is also not locked while a modal is open.
- (Done in Part 1: `scorePassword` already rates anything under 8 characters as Weak, matching
  Django's minimum; the sign-up form also checks the 8-character minimum.)
- `PostCard` has no action bar or source line yet (Parts 4, 7, 7B) and no skeleton variant.

## Follow-ups noted during 0A (still open)

- Part 10: log old → new values for every PlatformSettings change; seniors-only editing; the senior
  group's extra permissions (the role → groups mapping is cumulative).
- (Done in Part 1: CLI superusers are verified with an allauth `EmailAddress`; the default
  authentication class is set, so an unauthenticated request now gets 401.)
- Part 17: fail deploys when `PROXY_SHARED_SECRET`/`INTERNAL_CRON_SECRET` is short or a
  `local-dev-only` placeholder; verify Render's health-check Host header against `ALLOWED_HOSTS`;
  `collectstatic` must run in the build (the manifest storage needs it when DEBUG is False).

## Handoff checklist (outgoing agent)

- [x] Stop editing before the incoming agent starts.
- [x] Record current owner, phase and approved plan.
- [x] Record files changed and any unrelated pre-existing modifications.
- [x] Record every validation command and its exact pass/fail result.
- [x] Record blockers, user decisions and the next exact action.
- [x] Promote only durable, non-duplicated knowledge to `MEMORY.md`.
