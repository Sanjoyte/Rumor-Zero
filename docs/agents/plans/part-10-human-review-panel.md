# Plan: Part 10, Human review panel (Django Admin)

- **Status:** IMPLEMENTED 2026-10-13 (uncommitted at the time of writing). APPROVED by the user (Sanjoy Rozario) on
  2026-10-11, together with the six decisions and the defaults below; drafted 2026-10-11 by Claude (Opus 5.5) and built
  by Claude (Sonnet 5.5). Deviations from the plan are listed in `task.md` Part 10 ("Built differently from the plan").
- **Implement with:** Sonnet 5.5 · high (task.md).
- **Evidence (read-only):**
  - Docs: HANDOFF, MEMORY, `task.md` Part 10 and the Part 8/9 records (their Part 10 notes), the Part 11/11B/11C
    scopes, ARCHITECTURE §2/§3/§4/§4a/§4b/§5/§8/§9/§11/§14, ANALYSIS (c-5…c-13, b-2, d2 rows), STRUCTURE, and guide
    §3.4 and §8 (PDF; it adds that roles are "two Django Groups with different model-level permissions").
  - Code: every `admin.py`, `accounts/models.py` (role → group sync), `core/models.py`, `posts/{models,services}.py`,
    `pipeline/routing.py`, `reports/{models,services}.py`, the admin tests, and Django 5.2.17's admin source.
  - One Explore pass (the frontend Moderation link, `admin_url`, admin test patterns, templates, group creation).
  - A Plan-agent design review of this draft, run **before** approval and checked against Django 5.2.17's source.
    Its findings are folded in below and marked "(review)".

## Context

Part 10 turns Django Admin into the moderation panel of guide §8. It builds:
- two roles (Moderators, Senior moderators) as Django groups with model permissions;
- the review queue on `PostAdmin`;
- five moderator actions (Mark verified, Mark FALSE, Dismiss reports, Remove, Escalate). They run as bulk actions
  with a confirmation form, and each one goes through `moderation.services` and writes the audit trail;
- an append-only audit trail (`moderation_actions`);
- seniors-only editing of roles and platform settings, both logged;
- the branded admin header.

**Dependency check (2026-10-11).** Part 10 depends only on **Part 9** (`[x] Done (2026-10-11)`). Its whole chain
is Done: 8, 5, 4, 1, 0C and 0A/0B/0D, plus 2, 3, 6, 7 and 7B. Still open but not blocking: Part 3 criterion 4 (the
real-Google check), and CI for Parts 2 to 9, which hasn't been reported yet.

**Workspace:** HEAD is `4da6514` ("Implemented Part 9…"). The tree is clean, and HANDOFF matches it except that it
still calls Part 9 uncommitted. Step 0 fixes that text.

**Already in place:**
- **Roles and staff flag (0A):** `User.role` is the source of truth. `User.save` sets `is_staff` and syncs the
  cumulative groups "Moderators" / "Senior moderators", creating them with `get_or_create`. **No group has a
  permission yet**, and no migration creates them.
- **The Moderation link (0C):** done and tested. `/api/v1/me/` gives staff `admin_url`. `moderationItem()` adds
  "Moderation" (`fact_check`, new tab, `rel="noopener noreferrer"`) to the rail footer and the phone sheet. Only one
  test is missing: in `AppShell.test`, the phone sheet hiding the link from non-staff.
- **The admin logo (0D):** `apps/core/static/core/brand/logo-admin.png` (64 px tall, on the `#283044` plate) exists,
  and nothing uses it yet.
- **Read-only admins today:** `PostAdmin`, `ReportAdmin`, `CommentAdmin` (Hide/Unhide gated on
  `social.change_comment`, logged in Django's `LogEntry`), and the superuser-only `BookmarkAdmin`.
  `PlatformSettingsAdmin` can be edited by any staff user who holds the model permission.
- **Report resolution:** the database check `reports_resolution_consistent` refuses a status change without
  `resolved_at` in the same write.

## Your decisions (2026-10-11)

1. **Moderators see past actions only per post.** Each post's admin page shows its moderation history inline. The
   full `moderation_actions` list is seniors-only, and so is Django's admin log.
2. **Seniors may also suspend accounts.** Besides `role` and deleting accounts, a senior can switch `is_active`.
   Email, password, profile fields and `is_superuser` stay superuser-only. Seniors can't edit, suspend or delete
   superuser accounts or their own account.
3. **The removal reason is stored on the action row.** Remove takes an optional "reason shown to the author", kept in
   a new `public_note` column on `moderation_actions`. The verdict actions copy their public note there too, so
   every public note is audited. `Post.verdict_note` is not touched by Remove, so Part 11's Restore needs no undo.
   Part 11 shows the author the `public_note` of the post's latest `removed` row.
4. **Nobody acts on their own post, except a superuser.** Every action skips the moderator's own posts and says why.
5. **"Age in queue" gets a column:** `posts.review_started_at`. It is set when a post enters review and cleared when a
   moderator ends the review. The queue shows it and sorts by it. This adds a small migration on `posts`.
6. **"Mark email verified" is built now, for seniors only.** It was deferred from Part 2. It is a `UserAdmin` action,
   logged in the admin log. (review) `accounts.services.mark_email_verified` already exists (Part 2's signal uses
   it), so the new service gets its own name, `verify_email_by_staff`.

## Scope

**In:**
- `posts.review_started_at`, set by `routing.enter_review`;
- `apps/moderation/`: `ModerationAction`, pure rules, services, admins, templates, the role-groups migration;
- `reports.services.resolve_open_reports`;
- the review queue (`PostAdmin`): filter, columns, ordering, inlines, actions, confirmation page, post-page buttons;
- the `ModerationAction` and `LogEntry` admins, both read-only and seniors-only;
- the `UserAdmin` rules (role, suspend, delete, Mark email verified) and the seniors-only `PlatformSettingsAdmin`,
  with old → new values in the log;
- the admin header;
- one frontend test;
- the docs.

**Not in Part 10:**
- **Later parts:** appeals, the `appeal` FK on `moderation_actions`, Restore and Keep removed, and the
  "removed with an open removal appeal" part of the queue (11); reputation hooks and the credibility inline (11B);
  the emergency filter, the "active emergencies first" ordering, Demote emergency and Block emergency posting (11C);
  notifications (13); photo actions (14B).
- **Not planned:** a custom moderator UI, new endpoints, new dependencies, services or env variables.

## What the research found (all handled below)

1. **Django admin can't delete a user who has posts, even for a superuser.** `get_deleted_objects` adds "post" to
   `perms_needed` because `PostAdmin.has_delete_permission` is False (`admin/utils.py:148`). "Seniors can delete
   users" therefore needs a `UserAdmin.get_deleted_objects` that allows the cascade.
2. **The bulk "Delete selected" checks no object.** `delete_selected` only calls `has_delete_permission(request)`, so
   a senior could bulk-delete a superuser. Non-superusers lose the bulk delete and delete one account at a time from
   its page, which checks the object.
3. **A read-only `password` field would show the hash to seniors.** Admin renders a read-only field's raw value.
   Non-superusers get no password field at all. `user_change_password` checks only
   `has_change_permission(request, user)` (`auth/admin.py:157`), so a senior could otherwise reset a moderator's
   password: it becomes superuser-only.
4. **An action's queryset is the filtered changelist** (`cl.get_queryset(request)`, `admin/options.py:2058`). With
   the queue as the default view, a button for a post outside the queue (Remove on a VERIFIED post) would select
   nothing. The buttons post to `changelist?queue=all`, and the confirmation form posts back to the same full path.
5. **Admin actions run outside any transaction** (only `list_editable` is wrapped), so each service opens its own
   `atomic()` block per post.
6. **Test flushes wipe the groups' permissions.** A `transaction=True` test flushes the database. post_migrate
   re-creates permission rows but not the group assignments. pytest-django runs `db` tests before transactional
   ones, and a `role_groups` fixture re-applies the sync, so the permission tests don't depend on order.
7. **Existing tests change on purpose:**
   - `UserFactory(role=MODERATOR)` users now inherit group permissions (for example `reports/tests/test_admin.py:65`,
     "no model permissions until Part 10", and the Hide/Unhide tests that expect a 403).
   - `posts/tests/test_admin.py` asserts a read-only admin with no actions.
   - About 20 test files create `under_review` posts directly. Most use `PostFactory`, which will fill
     `review_started_at` itself. The E2E helpers never set `under_review` (reports go through `file_report`).
   - (review) Four more:
     - `accounts/tests/test_admin.py:68` `Group.objects.create(name="Moderators")` (the group now exists: use
       `get_or_create`);
     - `social/tests/test_services_repost_bookmark.py:103-104` saves `under_review` without the column;
     - `pipeline/tests/test_processor.py:281-283` fakes a Dismiss by hand (switch it to the real `dismiss_reports`);
     - `posts/tests/test_models.py:155` and `:178` list the constraint and index names.
8. **`enter_review` has no `now`.** It gains one, which changes its three callers inside `routing.py` and their tests.
   The save field lists in `posts.services` (`record_report`, `_RESULT_FIELDS`, `_FAILURE_FIELDS`) gain
   `review_started_at`.
9. **(review) A Dismiss or Remove with a missing or wrong `pre_review_status` would break a database check.**
   - The column takes any status or NULL. These would fail: a NULL status, an opinion restored to `pending`
     (`posts_post_opinion_status`), and `under_review` restored without the column.
   - Each failure is an `IntegrityError`, a 500 in the middle of a batch.
   - Real flows always set the column through `enter_review`, but factories don't. So the rules refuse it
     (`no_prior_status`), and the rules matrix includes `pre_review_status` and `verdict_source`.
10. **(review) `PostAdmin.has_change_permission` must stay False,** even though moderators hold
    `posts.change_post`. Otherwise the page gains Save, and `save_model` writes the whole row with no lock and
    outside the services. A moderator's POST to the change URL is tested to be 403.
11. **(review) The post-page buttons can't go inside `<form id="post_form">`** (browsers drop nested forms). They go
    in `{% block object-tools-items %}`.
12. **(review) `select_across=1` makes `response_action` ignore the pks** and re-run the whole filtered queryset at
    confirm time (`options.py:1683-1685`). The confirmation page therefore posts the evaluated, capped pks and never
    echoes `select_across`.
13. **(review) A migration must not import lists that later parts edit:** a fresh `migrate` would then grant
    permissions on models that don't exist yet. Migration 0002 holds its own frozen literal lists and depends on the
    latest migration of every app it names (`admin`, `auth`, `contenttypes`, `accounts`, `core`, `posts`, `reports`,
    `social`, `moderation`).
14. **(review) Deleting a user deletes the admin log rows they wrote** (`LogEntry.user` is CASCADE,
    `admin/models.py:112`). An unchecked cascade would erase a former senior's role, suspension and settings records.
15. **(review) The delete confirmation page lists every cascaded row by `str()`,** including "x bookmarked y"
    (bookmarks are private, §4d) and comment text.
16. **(review) Per-object History pages need only view permission** (`history_view`), so moderators would read the
    admin log of users, settings and comments, against decision 1.
17. **(review) Escalating a post that isn't under review** (§4 says "any") leaves `escalated_at` set until a later
    review, which then looks escalated.
18. **(review) `UserAdmin.construct_change_message` also runs for a superuser's password change**
    (`AdminPasswordChangeForm`, which has no `instance`). The override falls back to Django's message.

## Design

### Data model

**`posts.review_started_at`** (timestamptz null), added by one migration, `posts.0002_review_started_at`:
- AddField.
- A backfill of existing `under_review` rows with `updated_at`. Only dev databases have any. `updated_at` makes the
  wait look shorter than it was, which is fine for dev data.
- The check `posts_post_review_started_consistent`, which holds exactly when either (status = under_review and the
  column is set) or (status ≠ under_review and the column is null).
- `posts_review_queue_idx` re-pointed from `created_at` to `review_started_at`, with the same `under_review`
  condition.
- (review) The backfill changes no FK column, so no deferred-trigger events block the check in the same
  transaction. If Postgres refuses anyway, split it into 0002/0003.
- `PostFactory` sets the column with a `LazyAttribute` (`created_at` when `under_review`).

**`moderation.ModerationAction`** (`moderation_actions`, migration `moderation.0001_initial`), per §2 plus
`public_note`:

| Field | Type | Notes |
|---|---|---|
| id | uuid PK | |
| post | FK posts SET_NULL null, `related_name="moderation_actions"` | |
| subject_user | FK users SET_NULL null | account-level actions (11C, 14B); null for post actions |
| post_snapshot | text, blank | the post's content at action time |
| moderator | FK users SET_NULL null, `related_name="+"` | |
| action | 10 choices (§2, all now) | `moderation_action_valid` |
| from_status, to_status | PostStatus choices, null | `…_from_status_valid`, `…_to_status_valid` |
| public_note | varchar(500), blank | **new (decision 3):** the verdict note, or the reason shown to the author |
| notes | text, blank | internal rationale |
| created_at | `default=timezone.now` | |

- Indexes: `modaction_post_created_idx` (post, -created_at) for the inline, and `modaction_created_idx` (-created_at)
  for the log. The FKs keep their own indexes.
- **Append-only:** `save()` refuses an existing row and `delete()` refuses. The admin is read-only. SET_NULL from a
  deleted post or user still works, because the collector updates without calling `save`.
- `appeal` (FK appeals) is **added by Part 11** together with the `Appeal` model. §2 says so.

### Routing (`apps/pipeline/routing.py`)

`enter_review(post, reason, now)`: entering review sets `review_started_at = now`, and a merge leaves it alone.
`apply_report_threshold`, `apply_pipeline_result` and `apply_pipeline_failure` pass their `now`.

### Rules (pure; `apps/moderation/rules.py`, no I/O)

`refusal(action, post, moderator) -> Refusal | None` checks in this order. Every refusal has a code and a text.

| Check | Applies to | Refusal |
|---|---|---|
| post deleted by its author (or gone by the time it is locked) | all | `deleted` "deleted by its author" |
| `post.author_id == moderator.pk` and not superuser | all | `own_post` "your own post" |
| opinion | Mark verified / FALSE | `opinion` "opinion: no verdict" |
| status ≠ under_review | Mark verified / FALSE, Dismiss, **Escalate** | `not_under_review` |
| flag not `reports` / `both` | Dismiss | `no_reports` "no reports to dismiss" |
| (review) under review, and `pre_review_status` isn't a status the post could return to (`published` for an opinion; `pending`, `verified_true` or `verified_false` for a fact) | Dismiss with flag `reports`, Remove | `no_prior_status` "no status to return to" |
| status = removed | Remove | `already_removed` |
| `escalated_at` set | Escalate | `already_escalated` |

Escalate is limited to posts under review (review, finding 17). This changes §4's "any → Escalate" row, and Part 11
adds removed posts with an open removal appeal.

Then `transition(action, post, *, now)` changes only these fields:

| Action | status | flagged_reason | pre_review_status | review_started_at | escalated_at | also | open reports → | row |
|---|---|---|---|---|---|---|---|---|
| Mark verified | `verified_true` | null | null | null | null | `verdict_source=moderator`, `verdict_note` = the public note (blank clears) | actioned | `verified` |
| Mark FALSE | `verified_false` | null | null | null | null | same | actioned | `marked_false` |
| Dismiss, flag `reports` | `pre_review_status` | null | null | null | null | — | dismissed | `dismissed_report` |
| Dismiss, flag `both` | stays `under_review` | `pipeline` | kept (`pending`) | kept | kept | — | dismissed | `dismissed_report` |
| Remove | `removed` | null | null | null | null | `pre_removal_status` = `pre_review_status` if it was under review, else the status | actioned | `removed` |
| Escalate | unchanged | | | | `now` | — | — | `escalated` |

Every action also sets `moderated_by`, `moderated_at` and `updated_at`. **None touches `pipeline_*`** (Part 9's
claim token) or `confidence_score`.

### Services (`apps/moderation/services.py`; the only other status writer)

`mark_verified`, `mark_false`, `remove_post` (each takes `public_note`), `dismiss_reports` and `escalate`. All of
them take `(post_id, *, moderator, notes="", now=None)` and return the `ModerationAction`. Each one, in one
`transaction.atomic()`:
1. Lock `Post.objects.not_deleted().select_for_update(no_key=True, of=("self",))`. This is the lock reports,
   reposts and the pipeline's apply use, so a report or a pipeline answer waits and then sees the new state.
2. Re-check `refusal` against the locked row. On a refusal it raises `ActionRefused(refusal)` and writes nothing.
   No row (the author deleted the post meanwhile) is the `deleted` refusal, not `DoesNotExist` (review).
3. Apply `transition`, then `save(update_fields=[…])`.
4. `reports.services.resolve_open_reports(post, status=…, moderator=…, now=…)`: one `UPDATE` of the post's
   open reports that sets `status`, `resolved_by` and `resolved_at` together. Report writes stay in `reports`.
5. Create the `ModerationAction`: `post_snapshot = content`, `from_status` and `to_status`, the notes.

A pipeline answer that arrives later is ignored (`verdict_source=moderator`, or no longer awaiting a check). After a
Dismiss back to `pending`, the check is still owed, and an in-flight answer with a matching token applies.

### Roles and permissions (data migration `moderation.0002_role_groups`)

- **The migration (review, finding 13):** it holds its **own frozen literal lists**. It creates the permission rows
  (`create_permissions` per app config, saving and restoring `models_module`), `get_or_create`s both groups and
  `set`s their permissions exactly. It depends on the latest migration of every app it names. Its reverse clears the
  two groups' permissions.
- **The current lists:** `apps/moderation/roles.py` holds `GROUP_PERMISSIONS` and `sync_role_groups()`, which runs
  against the live registry, where permission rows exist. A test asserts the database's groups equal `roles.py`, so
  a later part that edits the lists must add a migration with the new frozen lists.
- **Tests:** the `role_groups` fixture calls `sync_role_groups()`. It heals the groups after a `transaction=True`
  flush, which keeps the permission rows (post_migrate) but drops group assignments.

- **Moderators:** `posts.view_post`, `posts.change_post` (the actions, as `social.change_comment` gates Hide),
  `reports.view_report`, `social.view_comment`, `social.change_comment`, `accounts.view_user`,
  `core.view_platformsettings`.
- **Senior moderators (only the extras; seniors are in both groups):** `accounts.change_user`,
  `accounts.delete_user`, `core.change_platformsettings`, `moderation.view_moderationaction`, `admin.view_logentry`.

| Capability | Non-staff | Moderator | Senior | Superuser |
|---|---|---|---|---|
| Admin login | redirect to login | ✓ | ✓ | ✓ |
| Queue, post pages, history inline | — | ✓ | ✓ | ✓ |
| The five actions | — | ✓ (not own posts) | ✓ (not own posts) | ✓ (own posts too) |
| Reports list; comments with Hide/Unhide | — | ✓ | ✓ | ✓ |
| Users: view | — | ✓ | ✓ | ✓ |
| Users: `role`, `is_active`, Mark email verified | — | — | ✓ others; not superusers or self | ✓ |
| Users: delete | — | — | ✓ one at a time; not superusers or self | ✓ |
| Users: email, password, profile, `is_superuser` | — | — | — | ✓ |
| Platform settings | — | view | edit | ✓ |
| Full moderation log; admin log | — | — | ✓ | ✓ |
| Bookmarks, likes, follows, reposts | — | — | — | ✓ (unchanged) |

### The review queue (`PostAdmin`, moved to `apps/moderation/admin.py`, as STRUCTURE places it)

- **`QueueFilter`** ("Show"): the default is the **review queue**: `under_review` and not deleted by the author
  (Part 5's note, `task.md:727`). The other choice is **All posts**. Picking a Status also leaves the queue (review:
  otherwise "Status: removed" on top of the queue would always be empty). Part 11 adds removed posts with an open
  removal appeal.
- **Columns:** the claim (excerpt, linking to the post page), type, status, reason, **pipeline** ("FALSE 92%",
  "TRUE 95%", "Inconclusive 40%", "—": Part 9 asked to show the late verdict), reports (`report_count`, sortable),
  **waiting** (`timesince(review_started_at)`, sortable), **posted** (`created_at`, sortable; §8), escalated (✓),
  emergency (Active / Ended / —, computed with `is_active_emergency`), author.
- **Filters:** Show, flagged reason, type, status, Escalated (yes/no), "Deleted by author". The emergency filter
  belongs to 11C.
- **Order:** `-report_count`, then `review_started_at` ascending (longest waiting first, nulls last), then
  `-created_at`. 11C puts active emergencies first.
- **Search:** content and author username. `list_select_related=("author",)`, `defer("pipeline_result")`, and
  `show_full_result_count=False`.
- **Post page:** every field read-only (`has_change_permission` stays False for everyone, review finding 10),
  grouped as Post / Review / Pipeline / Emergency. The inlines are
  **reports** (time, reporter, the reporter's account age when reporting, reason, details, counts, status;
  `select_related("reporter")`) and **moderation history** (time, action, moderator, from → to, public note,
  notes; `select_related("moderator")`). The history inline is viewable with `posts.view_post`, so moderators
  see it without the full log (decision 1).
- **Action buttons on the post page** (`change_form_template`, in `{% block object-tools-items %}`, outside the
  main form, finding 11): one small form per action that is permitted **and** passes `refusal` for this post.
  - Each form posts `action`, `_selected_action` and a `_from_post` marker to `changelist?queue=all` (finding 4).
  - After the confirmation, the moderator returns to the post page, not the list.
  - An opinion therefore never offers Mark verified / FALSE. In the list, when it is filtered to opinions,
    `get_actions` drops those two as well.
- **Bulk actions** (`@admin.action(permissions=["moderate"])`, where `has_moderate_permission` is
  `has_perm("posts.change_post")`): "Mark verified", "Mark FALSE", "Dismiss reports", "Remove posts", "Escalate to
  senior". Django's own delete action is gone, because there is no delete permission.
  1. **First POST:** at most **100** posts (more is an error message, which covers "select all across pages").
     It renders `moderation/admin/confirm_action.html`: the posts that will change (claim, type, status → new
     status, reason, reports, pipeline) and the skipped ones with their refusal text. The form has **Public note**
     (verdict actions; ≤ 500 code points; shown with the label) or **Reason shown to the author** (Remove;
     ≤ 500), plus **Internal notes** (≤ 2,000) for every action. Hidden inputs carry `action`, `apply`, and
     `_selected_action` built from the **evaluated, capped** queryset. `select_across` is never echoed (finding
     12). The form posts back to `request.get_full_path()`.
  2. **Confirm:** the service runs per post in id order. The result is a success message ("Marked 3 posts
     verified.") and a warning for refusals found under the lock ("Skipped 2: 1 opinion, 1 not under review."),
     then the preserved changelist. A form error re-renders the page.

### Logs for the seniors

- **`ModerationActionAdmin`:** read-only. List: time, action, moderator, post (snapshot excerpt, linked when the
  post exists), from → to. Filters: action, time. Search: snapshot, moderator username. Viewing needs
  `moderation.view_moderationaction` (seniors and superusers).
- **`LogEntryAdmin` ("Admin log"):** read-only. List: time, user, object, action flag, message. Filters: content
  type, flag. It needs `admin.view_logentry` (seniors). It holds the account and settings changes that have no
  `moderation_actions` kind: role, suspension, Mark email verified, platform settings, and Hide/Unhide.
- **History pages** (review, finding 16): `history_view` of `UserAdmin`, `PlatformSettingsAdmin`, `CommentAdmin` and
  `PostAdmin` also requires `admin.view_logentry`, through a small shared mixin. Moderators get 403 there; the
  post's moderation history stays on its page as the inline.

### `UserAdmin` (`apps/accounts/admin.py`)

- **Non-superusers** see no `password` field (finding 3). All fields are read-only except `role` and `is_active`.
- `has_change_permission(obj)` and `has_delete_permission(obj)` add a rule: a non-superuser can't edit a superuser
  or themselves. Without change permission the page shows read-only.
- `user_change_password` is superuser-only. Non-superusers lose `delete_selected`.
- **`get_deleted_objects` override** (findings 1, 14, 15):
  - It needs no delete permission on the cascaded models. It **protects** the account's own admin log rows: an
    account that wrote `LogEntry` rows can't be deleted ("suspend it instead"). That keeps a former senior's role,
    suspension and settings records. `moderation_actions` rows survive anyway (SET_NULL).
  - The confirmation page shows a **summary** (the account, plus a count per model), never each cascaded row's text.
- **`construct_change_message`** writes values: "Role: moderator → senior moderator", "Active: yes → no". Other
  fields keep Django's default message, and a form without an `instance` (the password change, finding 18) falls back
  to it.
- **Action "Mark email verified"** (permission `change`, so seniors). The new
  `accounts.services.verify_email_by_staff(user)` reuses the body of `mark_email_verified_by_google` (moved into a
  shared helper). It verifies the `EmailAddress` matching `user.email`, creating it if missing, then calls the
  existing `mark_email_verified`. It skips accounts that are already verified and accounts the requester can't
  change, and writes a `LogEntry` "Marked email verified".
- **Suspension** = `is_active=False`. allauth refuses login, our `JWTAuthentication` refuses the access token, and a
  refresh fails. Tests pin all three. The account's content stays up (a moderator removes posts separately).

### `PlatformSettingsAdmin` (`apps/core/admin.py`)

- Editing needs `core.change_platformsettings` (seniors). Moderators get the page read-only.
- `has_add_permission` = model permission **and** no row yet.
- `construct_change_message` writes values ("Report threshold: 5 → 3; Confidence threshold: 85 → 90."), shown on
  the object's History page and in the admin log. `save_model` keeps `updated_by`.

### Admin header

- `backend/templates/admin/base_site.html`, copied from Django 5.2's own: the `branding` block shows
  `<img src="{% static 'core/brand/logo-admin.png' %}" alt="" height="32">` followed by `site_header` (decorative
  `alt`, because the name is written next to it, §14), and keeps the theme toggle for anonymous visitors.
- `apps/core/admin.py` sets `admin.site.site_header = site_title = "Rumor Zero moderation"` and
  `index_title = "Moderation"`. The login page shows the header too.

### Frontend

No production change: 0C built the link. Add the missing `AppShell.test` case: the phone sheet has no
"Moderation" for non-staff.

## Defaults where the docs are silent (approved with the plan)

- **Act on what is eligible, skip the rest.** A mixed selection changes the eligible posts and lists the skipped
  ones with reasons. One transaction per post, so one refusal never undoes another post.
- **Deleted posts:** every action refuses a post its author deleted. Such posts stay out of the queue, but they are
  reachable through "All posts" and "Deleted by author".
- **Leaving review clears `pre_review_status`, `review_started_at` and `escalated_at`** (Mark verified/FALSE,
  Dismiss to the old status, Remove), so a later review doesn't look escalated or old. The `escalated` row stays in
  the log.
- **Escalate only works on posts under review** (changes §4's "any"), and is refused on a post that is already
  escalated. Escalation never locks a post, so any moderator can still act.
- **An account that wrote admin log entries can't be deleted, only suspended,** so the admin log keeps its records
  (review, finding 14).
- **Mark verified sets open reports to `actioned`**, as §4 says (11B's `report_upheld` only counts Remove and Mark
  FALSE).
- **A blank public note clears `verdict_note`.** Notes are trimmed.
- **Role, suspension, settings and email verification are logged in Django's `LogEntry` with values**, not in
  `moderation_actions`, whose ten kinds stay as §2 lists them. Seniors read them in the Admin log and on each
  object's History page.
- **Moderators get no access to likes, follows, reposts or social accounts.** Bookmarks stay superuser-only.
- **The queue's emergency column** says Active / Ended / — ("ended" means expired or demoted; §8 said "expired").
- **The batch cap is 100 posts** per action, which equals the page size.
- **No E2E test** (none is required, and the admin is server-rendered). A scripted browser check covers the pages
  instead.

## Files

**New:**
- `backend/apps/moderation/` via `startapp` (create the folder first; `name = "apps.moderation"`): `models.py`,
  `rules.py`, `services.py`, `roles.py`, `admin.py` (PostAdmin, ModerationActionAdmin, LogEntryAdmin, the inlines,
  the filters), `forms.py` (the confirmation form), `migrations/0001_initial.py`, `migrations/0002_role_groups.py`,
  `templates/moderation/admin/{confirm_action,post_change_form}.html`, `tests/` (below).
- `backend/apps/posts/migrations/0002_review_started_at.py`.
- `backend/templates/admin/base_site.html`.

**Changed:**
- `rumor_zero/settings.py` (`apps.moderation` in `INSTALLED_APPS`).
- `apps/posts/models.py` (column and check), `apps/posts/admin.py` (emptied to a one-line pointer),
  `apps/posts/services.py` (`review_started_at` in the field lists; module docstring),
  `apps/posts/tests/factories.py`.
- `apps/pipeline/routing.py` (`enter_review(…, now)`).
- `apps/reports/services.py` (`resolve_open_reports`).
- `apps/accounts/admin.py`, `apps/accounts/services.py` (`verify_email_by_staff` and the shared helper).
- `apps/social/admin.py` (`CommentAdmin` gets the History mixin).
- `apps/core/admin.py`.
- Tests that change on purpose (finding 7).
- `frontend/src/components/shell/AppShell.test.tsx`.

**Docs:**
- ARCHITECTURE: §2 (`review_started_at`, `moderation_actions.public_note`, the `appeal` FK in Part 11, the indexes),
  §4 (the moderator rows' extra effects, the own-post and deleted-post rules), §8 (roles matrix, queue, actions,
  logs, suspension, Mark email verified, the header).
- ANALYSIS c-42 (the six decisions); STRUCTURE (moderation, templates).
- MEMORY: the admin facts behind findings 1 to 6.
- `task.md` Part 10: criteria, decisions, both status spots. Notes for 11, 11B and 11C (the `appeal` FK, the
  `public_note` reason, the escalation clearing).
- `docs/test-command.md`: a `### Part 10` section in **both** guides.
- HANDOFF.

## Steps (each ends green before the next)

0. **Checkpoint.** Save this plan to `docs/agents/plans/`, link it from HANDOFF, and fix HANDOFF's "Part 9
   uncommitted" text. Check `docker compose ps` and that ports 3000 and 8000 are free.
1. **`review_started_at`.** Add the column, backfill, check, routing `now`, field lists and factory. Run
   `ruff check --fix . ; ruff format .` on the new migrations. Fix tests until `pytest` is green.
2. **`apps/moderation` skeleton and `ModerationAction`.** `startapp`, the model, migration 0001, append-only guards,
   model tests.
3. **Rules and services.** `rules.py` (pure tests over every starting state), `resolve_open_reports`, the five
   services, and the service, race and pipeline-interplay tests.
4. **Roles.** `roles.py`, migration 0002, the `role_groups` fixture, the group tests. Update the existing admin tests
   that assumed no permissions.
5. **Queue admin.** Move `PostAdmin` and add the filter, columns, ordering, inlines, confirmation flow and
   post-page buttons, plus `ModerationActionAdmin` and `LogEntryAdmin`, with the admin tests and query counts.
6. **UserAdmin and PlatformSettingsAdmin.** Add the rules, the change messages and Mark email verified, with the
   permission-matrix tests and the suspension tests.
7. **Header and the frontend test.**
8. **Docs, test-command, full validation, mutation checks, browser check; `task.md` and HANDOFF.**

## Tests

- **`moderation/tests/test_models.py`:** the ten action kinds and the checks; `public_note` ≤ 500;
  append-only (`save` of an existing row and `delete` raise); deleting the post (account cascade) sets `post` null
  and keeps the snapshot.
- **`test_rules.py` (pure):** every action × every starting state the post checks allow (status × flag ×
  `pre_review_status` × `verdict_source` × type × deleted × own/superuser), compared with the two tables above,
  including `no_prior_status`.
- **`test_services.py`:** each service × each §4 starting state:
  - the resulting fields, and that `pipeline_attempts` and the other pipeline fields are unchanged;
  - reports: only the post's **open** ones change, with `resolved_by` and `resolved_at` set and other posts'
    reports untouched;
  - exactly one row, with from/to, snapshot, notes and `public_note`;
  - a refusal writes nothing (no row, `updated_at` unchanged);
  - dismissed reports stop counting: a new report after a dismissal doesn't re-cross the threshold on the old ones.
- **`test_races.py` (`transaction=True`):**
  - two moderators dismiss the same post at once: one row, one `ActionRefused`;
  - an action waiting behind a held `NO KEY UPDATE` sees the committed state;
  - a report waiting behind a Remove gets 404.
- **`test_pipeline_interplay.py`:** after Mark verified, a pipeline answer is ignored. After Dismiss to `pending`, a
  claimed answer applies (the token is untouched).
- **`test_roles.py`:** both groups hold exactly the declared permissions after `migrate`, and the sync is
  idempotent. A `moderator` has the moderator set; a `senior_moderator` has both sets.
- **`test_admin_queue.py`:**
  - the default view (deleted posts and non-review posts left out), All posts, columns, ordering, search, filters;
  - query count: the changelist with 100 posts uses the same number of queries as with 5;
  - the post page with 50 reports and 10 history rows is constant too.
- **`test_admin_actions.py`:**
  - each action through the client: confirmation page (changed and skipped lists), apply, messages, exactly one
    row per changed post;
  - opinions are skipped by Mark verified/FALSE, are absent from an opinion's page buttons, and the actions are
    dropped from the dropdown when filtered to opinions;
  - the 101-post cap, the note lengths, a button for a post outside the queue, and own posts (superuser exempt);
  - (review) `select_across=1` at confirm acts only on the posts shown, even after another post enters the queue;
  - a button's action returns to the post page;
  - a moderator's POST to the post's change URL is 403 and changes nothing;
  - the buttons render outside `post_form`.
- **`test_permissions.py`:** the matrix above through the admin client for non-staff, moderator, senior and
  superuser:
  - pages, actions, reports, Hide;
  - users: view, role, `is_active`, delete, the password page, a superuser's and one's own page, the bulk delete,
    no password field for seniors;
  - platform settings view and edit, both logs, bookmarks still superuser-only;
  - (review) History pages are 403 for moderators and open for seniors.
- **`accounts/tests`:**
  - role and suspension change messages with values; a superuser's password change still logs Django's message;
  - a suspended account can't log in, its access token is 401 and its refresh fails;
  - Mark email verified sets both flags, skips, is logged, and is seniors only; Google linking still behaves the
    same after the helper move;
  - deleting a user with posts works for a senior, keeps `moderation_actions` rows with a null moderator or post,
    and shows a summary page without bookmark or comment text;
  - deleting an account that wrote admin log entries is refused.
- **`core/tests`:** settings change messages with values; seniors only, including the six emergency limits.
- **Header:** the admin index and login pages contain the logo `src`, `alt=""` and "Rumor Zero moderation".
- **Updated:**
  - `pipeline/tests/test_routing.py` (`enter_review(now)`, `review_started_at` set on entering and kept on a merge);
  - `posts/tests/test_services_*` (the field lists) and `posts/tests/test_models.py` (constraint and index names);
  - `pipeline/tests/test_queue.py` (states include the new column);
  - `pipeline/tests/test_processor.py:281` (the real `dismiss_reports`);
  - `social/tests/test_services_repost_bookmark.py:103`;
  - `accounts/tests/test_admin.py:68` (`get_or_create`);
  - the Part 7/8 admin tests that assumed moderators hold no permission;
  - the old `posts/tests/test_admin.py` (moved into the moderation admin tests).
- **Frontend:** `AppShell.test.tsx`: no Moderation in the phone sheet for non-staff.

## Verification (end to end)

- **Backend:**
  - `ruff check .` and `ruff format --check .`;
  - `python manage.py makemigrations --check --dry-run` and `python manage.py check`;
  - `pytest`, the whole suite. The threaded tests run 10 times in a row.
- **Frontend:** `npm run lint`, `lint:tokens`, `typecheck`, `format:check`, `npm test`. `npm run test:e2e` runs once,
  to show nothing regressed (the E2E backend migrates the new tables).
- **Mutation checks (about 30, backend):**
  - the lock, the re-check under the lock, a report status written without `resolved_at`;
  - a service touching `pipeline_attempts`, Dismiss with `both` restoring the status, Remove storing the
    under-review status, the own-post rule, the superuser exemption, the deleted-post refusal;
  - the queue filter, the 100 cap, the `queue=all` button target;
  - each group permission, the superuser and self protections, the password page, the bulk delete, the
    `get_deleted_objects` override;
  - the change-message values, `has_add_permission`, `review_started_at` set and cleared, the check;
  - (review) the `no_prior_status` refusal, the never-echoed `select_across`, the History mixin, the protected
    `LogEntry` rows, the summary delete page, and `PostAdmin.has_change_permission` returning True.
- **Browser (headless Chromium, 1280 px):** log in as a throwaway moderator, a senior and a superuser (made in
  `manage.py shell` and deleted afterwards). Check:
  - the header and logo, and the queue with reports and a pipeline verdict;
  - a bulk action's confirmation page and the result message;
  - an opinion's page with no verdict buttons;
  - the history inline;
  - the senior's user page (only `role` and `is_active` editable, no password) and the settings History page;
  - the moderator getting 403 on the settings form and the logs.
- **`docs/test-command.md` Part 10:** the Linux bash blocks extracted by script and run verbatim against live Django,
  with their output diffed against the doc. The PowerShell blocks are written, not run.

## Stop conditions

- Stop and ask if a requirement here contradicts ARCHITECTURE §4 in a way the decisions above don't cover. Also stop
  if a change needs a new dependency, service or env variable, or if `design/` would need a change.
- Stop if the check on `review_started_at` can't be made to pass without changing E2E behaviour (report it instead of
  dropping the check).
- Stop when every required test, lint and type check is green and the docs, `task.md` and HANDOFF are updated. Do
  not start Part 11.

## Follow-ups to record (not done here)

- **11:**
  - the `appeal` FK, the queue's removed-with-appeal entries, and Escalate for them;
  - the author's view of `public_note` (the latest `removed` row);
  - Restore and Keep removed. Restore never touches `review_started_at`, because the post isn't under review.
    Removing a post that was under review for `pipeline` or `both` stores `pre_removal_status=pending`, so a Restore
    would put an already-checked post back in the pipeline queue: decide how Restore handles it.
- **11B:** reputation calls in the five services (`report_upheld` on Remove and Mark FALSE: `resolve_open_reports`
  will need to return the reporters), and the credibility inline.
- **11C:** the emergency filter and ordering, Mark FALSE's emergency effects, Demote emergency, Block emergency
  posting.
- **13:** notify the author on verdict, removal and review changes, in the same transaction.
- **14 or 16:** a suspended account's posts stay visible while its profile is a 404 (Part 6). Decide whether
  suspension hides content.
- **16:** whether moderators should see emails in the user list.
