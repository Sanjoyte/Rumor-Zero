# Part 14: Account settings, data export, account deletion

**Status:** approved by the user on 2026-10-21 (planned by Claude, Opus 5.5). **Implemented 2026-10-21** (Claude, Sonnet 5.5); see HANDOFF and task.md for the validation and the deviations.

## Context

Part 14 lets a signed-in person:
- edit their profile (display name, username, bio);
- change their password;
- download everything stored about them as JSON;
- delete their account (guide §16 GDPR/CCPA note, ANALYSIS b-1 c2 subset).

`/settings` is a placeholder today (`frontend/src/app/(app)/settings/page.tsx`), and the backend has only `GET /api/v1/me/`. Earlier parts left these obligations for Part 14:
- Part 1: deleting an account deletes its sessions.
- Part 3: the "Signed in with Google" status, renaming a username, and the password-changed and Google-connected emails.
- Part 8: never decrement `report_count`.
- Part 11B: never lock a user before their posts; the ledger cascades.
- Part 11D: mount `CredibilityPanel defaultOpen`.
- Part 12: the export skips `search_vector`.
- Part 13: delete the notifications the account acted in; decide whether notifications are exported.

**Dependencies:** 6, 7, 7B, 11B and 11D are all `[x] Done`, both in the task.md table and in each part's status line. HEAD is `4f2d818` ("Implemented Part 13") and the tree is clean. HANDOFF still says Part 13 is uncommitted, so step 0 corrects it.

## User decisions (2026-10-20)

1. **Staff can't delete themselves.** `DELETE /me` answers **403 `staff_account`** for moderators, senior moderators and superusers. It gives the same answer for any account that wrote Django admin log entries, which mirrors `UserAdmin.get_deleted_objects`: `LogEntry.user` cascades, so the admin history would vanish. The UI says to ask an admin to remove the role first.
2. **The export includes the notifications you received.** Each item has type, outcome, post/comment id, the actor's public username (or null), the read flag and the time.
3. **Username changes are limited by a throttle only.** There is no cooldown and no migration. An old `/u/<name>` becomes a 404 and the old name is free for others.
4. **Two new emails:** "password changed" (after `POST /me/password/`) and "Google connected" (when a Google sign-in links to an existing account).

## Defaults this plan adopts (approve or change at review)

- **`GET /me` gains `bio` and `public_score`.** `public_score` comes from `reputation.scoring.public_score(score, sample)`, and both values are columns on the user row, so the query count stays at 2. The settings form prefills from it, and `CredibilityPanel` gets `publicScore` from it. `PATCH` answers with the same shape.
- **`PATCH /me` needs a verified email** (`IsEmailVerified`). Bio and names are public content, and "unverified = read-only" (§7).
  - Password change, export and delete need only a login.
- **Throttles:** four new user-scoped `ScopedRateThrottle` scopes, which makes 17 in all:

  | Scope | Rate |
  |---|---|
  | `profile_update` | 30/hour |
  | `password_change` | 10/hour |
  | `data_export` | 10/hour |
  | `account_delete` | 10/hour |

  An Argon2 hash costs about 100 MiB, so the wrong-password paths must stay throttled.
- **Sessions on delete:** the current token session (from `request.auth["sid"]`) is deleted, and the response also expires `rz_refresh`/`rz_session` (`cookies.delete_auth_cookies`; the relay forwards `Set-Cookie`). Every other session is dead immediately, because refresh goes through `get_user` and the user row is gone. Its row is purged by `clearsessions` (Part 17).
  - There is no O(all sessions) sweep. This matches Part 2's "no eager sweep" for resets.
- **Password change keeps this device signed in.** Under a `select_for_update` lock on its `django_session` row (the same lock refresh takes, so a concurrent refresh can't overwrite it), the current token session gets the new `HASH_SESSION_KEY`. Every other session ends at its next refresh. The UI says so.
- **The admin's account delete uses the same core routine.** It locks the posts, then the account, then deletes the notifications whose actor is the account, then deletes the account. Otherwise a senior's delete would still leave "Someone liked your post" items. The admin's protections are unchanged.
- **After deletion** the browser goes to `/home` (public) with the toast "Your account has been deleted."

## Backend

### Files

**Changed:**
- `apps/accounts/{views,serializers,services,urls,signals,admin}.py`
- `apps/notifications/services.py`: add `discard_for_actor(user_id)`.
- `rumor_zero/settings.py`: the four throttle scopes.
- `apps/core/tests/test_settings.py`: 17 scopes, test renamed.
- `apps/accounts/tests/test_me.py`: the new fields.

**New:**
- `apps/accounts/deletion.py`: the deletion core.
- `apps/accounts/export.py`: the export builder.
- Templates in `templates/account/email/`: `password_changed_{subject.txt,message.txt,message.html}` and `google_connected_{subject.txt,message.txt,message.html}`.
- Tests in `apps/accounts/tests/`: `test_profile_update.py`, `test_password_change.py`, `test_export.py`, `test_account_delete.py`, `test_account_delete_races.py`, plus additions to `test_emails.py` and `test_admin.py`.

There are no migrations, no new dependency and no new variable.

### Endpoints (all `never_cache`, `IsAuthenticated`)

**1. `PATCH /api/v1/me/`** (`MeView.patch`, throttle `profile_update`, plus `IsEmailVerified`)
- Accepts any of `display_name`, `username`, `bio`. Other keys (`email`, `role`, …) are ignored, and a test pins that.
- **Input normalisation:**
  - `username` goes through `normalize_username` and then `validate_username`.
  - `display_name` is trimmed, at most 50 code points, with no control characters or line breaks.
  - `bio` is trimmed, `\r\n` becomes `\n`, and it is at most 280 code points.
- **Errors:** a field that fails validation gives a 400 field error. A username already taken gives `{"username": ["That username is taken."]}`; two renames racing for the same name raise an `IntegrityError`, which is caught and answered with the same 400.
- **Write:** `accounts.services.update_profile(user, changes)` saves with explicit `update_fields` (only the changed fields), so it never writes `is_email_verified` or the service-owned fields.
- Answers 200 with `MeSerializer`.

**2. `POST /api/v1/me/password/`** (throttle `password_change`): `{current_password, new_password}`
- An unusable password (Google-only) gives **409 `password_not_set`**: "Use Forgot password to set one."
- A wrong current password gives 400 `{"current_password": [...]}`.
- `validate_password(new, user)` errors go to `new_password`.
- Then `set_password` and `save(update_fields=["password"])`, the current session's hash is re-stamped under the session-row lock, and the email is sent on commit.
- Answers 204.

**3. `GET /api/v1/me/export/`** (throttle `data_export`)
- Answers 200 JSON with `Content-Disposition: attachment; filename="rumor-zero-<username>-<YYYY-MM-DD>.json"`.
- `export.build_export(user, now)` makes **one query per section, a fixed count whatever the volume**. Each section selects its columns explicitly with `.values()`/`.only()`, so `search_vector` and `pipeline_result` can never appear.
- **Shape:** `{format: "rumor-zero-export", version: 1, exported_at, account, posts, comments, likes, following, followers, bookmarks, reposts, reports, appeals, credibility_history, notifications}`.

| Section | Contents |
|---|---|
| `account` | id, username, display_name, bio, email, is_email_verified, role, created_at, has_usable_password, google_connected, `credibility {score, sample, public_score}` |
| `posts` | All of yours, **soft-deleted and removed ones included**: id, post_type, content, sources, is_emergency, emergency times, status, the shown confidence and verdict source (reuse `posts.serializers.shown_confidence` / `shown_verdict_source`), verdict_note, the removal reason (the author-facing `public_note` of the latest `removed` row, as `for_list` does), created_at, deleted_at |
| `comments` | Yours, deleted and hidden included: id, post_id, content, created_at, deleted_at, hidden |
| `likes` | post_id, created_at |
| `bookmarks` | post_id, created_at |
| `reposts` | post_id, status_at_repost, created_at |
| `following` / `followers` | user id, public username, created_at |
| `reports` | Yours: id, post_id, reason, details, status, created_at, resolved_at (**never** `counts_toward_threshold` or `resolved_by`) |
| `appeals` | id, post_id, kind, reason, status, created_at, resolved_at (**never** the moderators) |
| `credibility_history` | Every ledger row, reversals included: the `event_data` keys minus `appeal` (id, kind, label, positive, negative, score_after, created_at, post_id, reverses, reversed) |
| `notifications` | id, type, outcome, post_id, comment_id, actor username or null, is_read, created_at |

- **Never included:** another person's email, role or credibility; a moderator's identity; `notes`; `flagged_reason`; `report_count`; the pipeline internals.

**4. `DELETE /api/v1/me/`** (throttle `account_delete`)
- **Body:**
  - With a usable password: `{password}`. A wrong one gives 400 `{"password": [...]}`.
  - Otherwise: `{username}`, which must equal the current username after normalising, else 400 `{"username": [...]}`.
- Staff, or an account that wrote admin log entries, gets **403 `staff_account`**.
- Then `deletion.delete_account(user, session_key=<from sid>)`, which answers 204 and sets cookie-expiry headers.

### `apps/accounts/deletion.py` (the lock order is the point)

```
delete_account(user, *, session_key=None):   # caller has NOT locked anything
  with transaction.atomic():
    1. Post.objects.select_for_update().filter(author=user).order_by("pk")  # ALL posts first (plain FOR UPDATE, as delete_post)
    2. User.objects.select_for_update().filter(pk=user.pk) → gone? return (idempotent)
    3. notifications.services.discard_for_actor(user.pk)                     # new, uses notifications_actor_idx
    4. Session.objects.filter(session_key=session_key).delete()  (if given)
    5. User.objects.filter(pk=user.pk).delete()                              # Collector: CASCADE/SET_NULL per §2
```

- This keeps the order "post, then user" (`settle_post`'s order).
- `report_count` and others' review state are untouched.
- `ModerationAction` rows keep their `post_snapshot`, with post, subject and moderator SET_NULL.
- Other people's ledger rows about your posts get `post` SET_NULL.
- allauth's `EmailAddress` and `SocialAccount` rows cascade.
- **Residual race:** a post created during the deletion and settled at that same instant could deadlock. Postgres aborts one transaction, and the client sees an error and can retry. This is documented and accepted.
- **Admin path:** `UserAdmin.delete_model` and `delete_queryset` call `deletion.delete_account(obj)` (no session, no staff rule; the admin's own protections still apply first).

### Emails (via `get_adapter().send_mail`, on commit, errors swallowed as today)

Both follow the §7 template rules (txt plus HTML on the base layout, lines under 998 characters, links on `FRONTEND_ORIGIN`).

- **`password_changed`:** "Your password was changed. Other devices were signed out. Not you? Reset it: `<FRONTEND>/forgot-password`."
- **`google_connected`:** sent from the `social_account_added` receiver. That signal fires only when Google links to an existing account; a Google sign-up fires `user_signed_up`.
  - Text: "Continue with Google is now connected to your account. Not you? …"
  - When the link wiped the password, it adds a line saying the old password no longer works.
  - §7 line 729 ("no account connected email") gets updated.

## Frontend

### Files

**New, in `src/features/settings/`:**
- `SettingsPage.tsx`
- `ProfileForm.tsx`
- `AccountSection.tsx`
- `ChangePasswordModal.tsx`
- `DataExportCard.tsx`
- `DeleteAccountModal.tsx`
- `settings-api.ts`
- `messages.ts`
- a `*.test.tsx` beside each

**New elsewhere:** `e2e/settings.spec.ts`.

**Changed:**
- `app/(app)/settings/page.tsx`: thin, renders `SettingsPage`.
- `lib/api/types.ts`: `Me` gets `bio` and `public_score`.
- `lib/auth/session.ts` and `AuthProvider.tsx`: `endSession()`, i.e. become anonymous plus broadcast `logout` without the POST, used after a 204 delete.
- `app/(app)/layout.tsx` (AppFrame): the deleted-account exit goes to `/home`, not `/login?next=/settings`, mirroring the `loggingOut` ref.
- `features/auth/test-helpers.tsx`: `ME` gets the new fields.

### Page (Stitch c2 classes)

- **Header:** eyebrow, `h1` "Settings", and a lede. Below it, an anchor tab nav (Profile · Account · Credibility · Your data) linking to the section ids.
- **Sections:** each has a "SECTION 0N" eyebrow, an `h2` and a description.

1. **Profile:** `ProfileForm`.
   - Display name, username and bio in two columns, with the bio in a `Textarea variant="filled" maxCount={280}`.
   - The username hint reuses `useUsernameAvailability`, skipped while the value equals the current name.
   - The c2 save bar (Cancel resets, Save submits) shows only when the form is dirty.
   - On success: `reloadMe()` (updates the shell and broadcasts to other tabs) and the toast "Profile saved."
   - A 400 puts field errors on the fields and focuses the first one.
2. **Account:** a card with divided rows.
   - The email in `font-label-code` with the c2 Verified chip, or "Not verified" with a link to `/verify-email`.
   - The password row:
     - With a usable password: "Change password" opens `ChangePasswordModal`. It has current, new and confirm fields (`PasswordField`, client-side mismatch check). On success, the toast "Password changed. Your other devices are signed out."
     - Without one: "Signed in with Google. To also log in with a password, use Forgot password." with a link.
   - A "Google sign-in connected" row when `google_connected`.
3. **Credibility:** `<CredibilityPanel publicScore={user.public_score} defaultOpen />`.
4. **Your data:** `DataExportCard`.
   - Its "Download your data (JSON)" button calls `api.get` on `/v1/me/export/`.
   - Then `Blob`, `URL.createObjectURL` and an `<a download>` with the same filename, followed by a revoke.
   - It shows a loading state; a 429 or network failure gives a toast.
5. **Danger zone:** `DangerZone` + `DangerAction` "Delete account" opens `DeleteAccountModal`, modelled on `DeletePostModal`.
   - It confirms with a `PasswordField` or, for Google-only accounts, with "Type your username"; the button is disabled until it matches.
   - It lists what goes and what stays: "Moderation records keep a copy of removed posts".
   - On 204: `endSession()`, `router.replace("/home")`, and the toast.
   - Staff see an explanation instead of the button.

No raw hex, no default palette, only `rounded-lg`/`rounded-full`, and plain text everywhere.

## Steps (in order)

0. Save this plan as `docs/agents/plans/part-14-account-settings-export-deletion.md`; correct HANDOFF (Part 13 committed as `4f2d818`; Part 14 in progress, with a plan link). Measure the baselines (`pytest`, `npm test`).
1. Backend: `discard_for_actor`, then `deletion.py`, the admin hook and their tests (cascade, audit retention, lock-order race test with `settle_post` using the existing `threading.Barrier` pattern from `apps/reputation/tests/test_races.py`).
2. Backend: `MeSerializer` fields, then PATCH, password, export and DELETE with their throttles; the settings scope test; tests.
3. Backend: the two emails, their templates and `test_emails.py` additions; `ruff check . ; ruff format --check .`; `makemigrations --check --dry-run` (expect no changes).
4. Frontend: types, session `endSession`, the settings feature and its tests, the route, and AppFrame's exit path.
5. E2E `settings.spec.ts`:
   - `seedAuthor` → `logIn` → `/settings`.
   - Edit the display name, username and bio, then check the rail and `/u/<new>`, and that `/u/<old>` is a 404.
   - Change the password.
   - Export: `waitForEvent("download")` and parse the JSON (it contains the seeded post, no `search_vector`).
   - Delete: confirm with the password, land on `/home` anonymous, and fail a login with the old credentials.
6. Docs:
   - ARCHITECTURE §2 (notifications: deleted with their actor's account), §3 (17 throttle scopes), §7 (password change, sessions on delete, the two emails), §8 (the admin delete path), §9 (the four endpoints and the `/me` fields), §10 (`/settings`).
   - ANALYSIS c-48 (Part 14 decisions), STRUCTURE (`features/settings`, `deletion.py`, `export.py`), the `docs/test-command.md` Part 14 section (Linux and PowerShell), MEMORY (durable facts only), task.md (criteria, status in both places, deviations), HANDOFF (validation and the next action).

## Verification

- `cd backend && pytest` (all of it; it was 4073 before), `ruff check . ; ruff format --check .`, `python manage.py makemigrations --check --dry-run`.
- `cd frontend && npm run lint ; npm run typecheck ; npm test ; npm run test:e2e ; npm run build`.
- **Key assertions:**

  | Area | Must hold |
  |---|---|
  | Export | Contains each section; another user's email and any `search_vector` or `pipeline_result` key are absent; a fixed query count |
  | Deletion | Removes the user, posts, comments, likes, follows, bookmarks, reposts, reports, appeals, ledger rows, `EmailAddress`, `SocialAccount` and the actor's notifications; keeps `ModerationAction` with `post_snapshot`; leaves `report_count` unchanged; another device's refresh then fails; the response expires the cookies |
  | Staff | 403 for moderators and for log-entry writers |
  | Password | A wrong current password gives 400; Google-only gives 409; this session still refreshes while another does not; the email is sent |
  | PATCH | A taken username and a reserved one give 400; email and role can't be changed; the service-owned fields are untouched |

- Headless Chromium screenshots at 1280, 1024 and 390 px (0 px horizontal overflow).

## Stop conditions

- Stop and ask if:
  - any required test, lint or type check can't be made green;
  - a migration turns out to be needed;
  - allauth's internals for the session hash or `sid` differ from what is described;
  - the deletion race test shows a deadlock outside the documented residual case.
- Out of scope (follow-ups): profile photos (14B); a sweep of orphaned sessions (Part 17 `clearsessions`); a suspended account's content visibility (Part 16); the username-rename race in sign-up (Part 16).
