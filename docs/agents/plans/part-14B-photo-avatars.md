# Part 14B: Photo avatars

**Status:** approved by the user on 2026-10-21 (planned by Claude, Opus 5.5). **Implemented 2026-10-21 (Claude, Sonnet 5.5).**
The plan is saved here and linked from HANDOFF, so step 0's saving and linking are already done; its HANDOFF correction
(Part 14 committed as `bd59f97`) was also made at approval.

**As built, two differences from this text** (details in `task.md` Part 14B, ANALYSIS c-49 and ARCHITECTURE §4e):
- **WebP is capped at 12 MP** (user decision at the step 1 stop-and-ask gate): Pillow 13's only WebP decoder is the animation
  decoder, about 16 bytes a pixel, so a 25 MP WebP peaked at about 390 MB. JPEG and PNG keep 25 MP.
- **The centre square is flattened and shrunk in horizontal bands**, not by `reduce()` of the whole image (decoding item 7
  below): `reduce()` copies a whole RGBA image first, 194 MB on the plan's own 25 MP RGBA PNG and 314 MB on a 300 x 83,000
  panorama. Bands: 112 MB and 103 MB. No documented limit changed.

## Context

Users get an optional profile photo (D5, ANALYSIS f-7, ARCHITECTURE §4e). Initials stay the fallback everywhere.
- The upload is decoded and re-encoded by Pillow, so nothing of the original file survives except resized pixels.
- Only two WebP sizes are stored, in Postgres; no new service.
- Moderators can remove a photo and block uploads.

**Dependencies:** Part 14 is `[x] Done (2026-10-21)` in both places in task.md and committed as `bd59f97`. Its own
dependencies (6, 7, 7B, 11B, 11D) and 0C (the relay) are Done. HEAD is `bd59f97` and the tree is clean. HANDOFF still
says Part 14 is uncommitted, so step 0 corrects it. Open but not blocking: Part 3 criterion 4, CI for Parts 2–14,
the Part 17 stub launch blocker.

**What already exists (verified in the code):**
- `users.avatar_version` and `avatar_uploads_blocked` (`accounts.0001`).
- `accounts.serializers.avatar_url(user, size=96)`, used by every user payload. Every list uses a full
  `select_related` user, and the notifications `.only()` already lists `actor__avatar_version`, so `avatar_url`
  costs no extra query anywhere.
- The `avatar_upload` 5/day throttle scope (one of the 17).
- The `avatar_removed` and `avatar_blocked` kinds, already in the `moderation_action_valid` check.
- `ModerationAction.subject_user`.
- The relay (`src/lib/api/relay.ts`):
  - accepts PUT and buffers bodies up to 6 MB (413 `payload_too_large` above that);
  - forwards `If-None-Match` and `If-Modified-Since`;
  - passes back `cache-control`, `etag`, `content-disposition`, `x-content-type-options` and
    `content-security-policy`;
  - answers a 304 with no body;
  - streams binary bodies unread.

  **No relay change is needed.**
- `<Avatar src>` with `onError` and the pre-hydration fallback, already passed `avatar_url` at every spot: sidebar
  card and dock, top bar, mobile header, post cards, the post page's author row, comments, user rows and people
  search, notifications, and the profile header.
- `apiFetch` already sends `FormData` raw.

**Missing:**
- Pillow, the `Avatar` model and the processing.
- The endpoints, a multipart parser on that view, ETag/304 handling and the CSP header.
- The admin actions.
- The uploader, browser-side image code and upload progress.

## User decisions (2026-10-21)

1. **Pillow 13.0.0, not 12.3.x.** 12.3.0 never got a patch release. 13.0.0 (2026-10-16, cp313 wheels for Linux and
   Windows) fixes a critical JPEG decoder overflow, an unbounded Exif loop and decompression-bomb bypasses. SETUP B1 is
   updated under AGENTS rule 10.
2. **Block photo uploads also removes the current photo.** It logs `avatar_removed` and then `avatar_blocked`, 1 µs
   apart. A new **Allow photo uploads** action lifts the block and logs a new kind, `avatar_unblocked` (mirrors
   Block/Unblock emergency posting).
3. **The browser accepts originals up to 20 MB** and shrinks them before uploading. The server's 5 MB / 25 MP /
   128 px limits still guard direct API uploads.
4. **A real progress percentage:** `apiFetch` gains an `onUploadProgress` option. It swaps only the transport to
   XMLHttpRequest, so the token, the single-flight 401 refresh-and-retry and `normalizeError` stay one code path.

## Defaults this plan adopts (approve or change at review)

1. **Sizes:** `GET /me` and `GET /users/{username}/` give the **256** URL (the settings preview is 56 px and the
   profile header 80 px, crisp at 2×). Every list item gives **96**: post authors, comments, `reposted_by`, user rows,
   people search, notification actors.
2. **`GET /me` gains `avatar_uploads_blocked`** (12 keys), so the card can show the block before anyone picks a file.
3. **Endpoints:**
   - `PUT` → 200 with the `/me` object.
   - `DELETE` → 204, idempotent. It needs a login only: allowed while unverified or blocked, no throttle.
4. **Refusal codes.** All are `{"detail", "code"}` (an `APIException`; validation errors carry no code on the wire).
   - 403s, as permissions, which never count against 5/day:
     - `email_unverified`;
     - `photo_uploads_blocked` "A moderator turned off photo uploads for your account.".
   - 429 from the throttle.
   - 400s, which count:
     - `photo_missing`;
     - `photo_too_large` (over 5 MB);
     - `photo_unsupported` (not JPEG/PNG/WebP, animated, truncated, unreadable);
     - `photo_too_small`;
     - `photo_too_many_pixels`.
   - 503 `photo_busy` with `Retry-After: 5` (item 6).
5. **The original never touches disk:**
   - The view's only upload handler is an in-memory one capped at 5 MB. Django's default spools anything over 2.5 MB
     to a temp file.
   - A declared `Content-Length` over 5 MB + 64 KiB is refused before the body is read; a body that lies is cut off
     at the cap.
   - The handler must be set on `request._request.upload_handlers` before `request.data` is read.
   - Only the `file` field is read.
6. **One decode at a time, site-wide:**
   - The decode runs inside `pg_advisory_xact_lock(<constant>)` with `SET LOCAL lock_timeout = '10s'`; a timeout is
     503 `photo_busy`.
   - **Why:** Render runs 2 workers × 4 threads in 512 MB, and a 25 MP RGBA PNG decodes to about 100 MB. The lock is
     transaction-scoped, so it can never leak.
7. **Decoding details (`apps/accounts/avatars.py`):**
   - `Image.open(fp, formats=("JPEG", "PNG", "WEBP"))`, so no other decoder ever parses the bytes, then check
     `im.format`.
   - Size and pixels are checked from the header: an explicit `w*h > 25_000_000` check, plus `MAX_IMAGE_PIXELS` at
     25 MP so a bomb over 2× already raises at open. Pillow only *warns* between 1× and 2×.
   - Refuse `is_animated` (APNG, animated WebP). An **MPO** (a multi-picture JPEG from some cameras) is accepted using
     its first frame.
   - JPEG: `draft("RGB", (256, 256))` before loading. PNG/WebP: `reduce()` by the largest factor that keeps the short
     side ≥ 256, and drop the full-size image at once.
   - Then: `exif_transpose`; transparency flattened onto white; RGB; centre square; LANCZOS to 256 and 96.
   - Each size is saved as WebP quality 80 from a **fresh image with empty `info`**, with no `exif`, `icc_profile` or
     `xmp` (Pillow 13's WebP encoder takes them only from save options).
   - Every decoder error is refused as `photo_unsupported`, never a 500. No colour conversion: browser-made uploads
     are already sRGB, and parsing untrusted ICC is more attack surface.
   - `version` = first 16 hex of SHA-256(`image_256`). Identical bytes give the same URL.
8. **`avatar_version` and `avatar_uploads_blocked` join `User.SERVICE_OWNED_FIELDS`.** A stale full `save()` (the admin
   form, allauth `set_password`) can't write back an old photo or lift a block. Writers use `.update()`.
9. **Admin:**
   - **Permissions:** a new permission `moderation.moderate_profile_photos` ("Can remove profile photos and block or
     allow photo uploads", on `ModerationAction.Meta`, like `block_emergency_posting`). It and `accounts.view_avatar`
     go to the Moderators group, so seniors get them through it.
   - **Refusals:** a non-superuser may not act on a superuser or on themselves (the existing rule), plus `no_photo`,
     `uploads_already_blocked` and `uploads_not_blocked`.
   - **Where the actions are:** AvatarAdmin has Remove photo and Block photo uploads. UserAdmin has all three (Remove,
     Block, Allow), so an account with no photo can still be blocked or allowed.
   - **Account page:** UserAdmin gains a "Photo uploads" filter and a read-only **Photo** field: the thumbnail,
     "Uploads blocked", and the account's `avatar_*` rows. It is a field, not an inline, because an inline breaks the
     account form's POST (MEMORY 11C).
   - **Thumbnails** are `<img>` tags pointing at the public 96 URL; the admin is on the backend host. The list
     `defer`s both bytea columns.
10. **A suspended account's photo is still served.** Its content stays up today; Part 16 decides suspension
    visibility.
11. **No notification on removal or block.** The nine notification types stay nine; the settings card shows the block.
12. **Browser flow:**
    - Every file is re-encoded in the browser (centre square, ≤ 1024 px, JPEG 0.9 on white), so GPS never leaves the
      device. The server redoes everything.
    - Two steps: choose a file → square preview → **Use this photo** / Cancel.
    - Cancel during the upload aborts it, then reloads `/me`.
    - Remove photo needs no confirmation modal.
13. **`<Avatar>` images get `loading="lazy" decoding="async"`.** Each photo is one Worker request per browser
    (§13), so off-screen avatars in a feed shouldn't load.
14. **Export:** `account.photo` = `{format: "webp", size: 256, data: <base64>}` or null, plus
    `account.photo_uploads_blocked`. One more query: 13 in `build_export`, 14 per request.

## Backend

### Files
- **New:**
  - `apps/accounts/avatars.py`: the processing, `save_photo` / `delete_photo` under the account lock, the upload
    handler, the decode gate.
  - Views in `apps/accounts/views.py`: `AvatarView` (PUT, DELETE) and `AvatarImageView` (GET, HEAD).
  - Migrations `accounts/migrations/0003_avatar.py`, `moderation/migrations/0008_photo_actions.py` (the
    `avatar_unblocked` kind, the widened check, the permission option) and `0009_photo_permissions.py` (frozen lists,
    as `0007`).
  - Tests in `apps/accounts/tests/`: `photo_fixtures.py` (generated in the test with Pillow), `test_avatar_processing.py`,
    `test_avatar_memory.py` (subprocess peak RSS, Linux only), `test_api_avatar_upload.py`, `test_api_avatar_serve.py`,
    `test_api_avatar_delete.py`, `test_avatar_urls.py`.
  - Tests in `apps/moderation/tests/`: `test_services_photos.py`, `test_admin_photos.py`.
- **Changed:**
  - `requirements.txt` (`Pillow==13.0.0`).
  - `accounts/{models,serializers,urls,admin,permissions,export}.py`.
  - `moderation/{models,rules,services,roles}.py`. `ModerationActionAdmin` lists the new kind with no change.
  - `moderation/templates/moderation/admin/confirm_account_action.html`: its headings become context values
    (`now_heading`, `after_heading`, `changelist_url`) instead of "Blocked until…".
  - Existing tests changed on purpose: `test_me.py` (12 keys, the 256 URL), `social/tests/test_api_profile.py` (256),
    `test_export.py` (photo, 14 queries), `test_account_delete.py` (the Avatar row is gone, the avatar audit rows stay
    with `subject_user` null), `test_user_save.py` (the two fields), `moderation/tests/{test_models,test_roles}.py`
    (13 kinds, `0009`).

### Endpoints
- **`PUT /api/v1/me/avatar/`**
  - **Setup:** `parser_classes = [MultiPartParser]`; permissions `IsAuthenticated`, `IsEmailVerified`, a new
    `PhotoUploadsAllowed`; throttle `avatar_upload` on PUT only; `never_cache`.
  - **Order:** Content-Length check → handler-capped parse → in one `atomic()`:
    1. take the gate;
    2. process;
    3. `User.select_for_update(no_key=True)`;
    4. re-check active, verified and not blocked under the lock (a Block that committed meanwhile wins: 403);
    5. `Avatar.update_or_create`;
    6. `User.objects.filter(pk).update(avatar_version=v)`.
  - Locks only the user (no posts), so it can't deadlock with `delete_account`, which locks posts and then the user.
- **`DELETE /api/v1/me/avatar/`:** `IsAuthenticated`, `never_cache`; `delete_photo` under the account lock → 204.
- **`GET|HEAD /api/v1/avatars/<str:user_id>/<str:name>`**
  - **Setup:** a DRF `APIView` returning an `HttpResponse`, so a 404 is the JSON `not_found`; `authentication_classes
    = []`, so a stale token is never a 401; `AllowAny`; no throttle; **not** `never_cache`. `name` must fullmatch
    `([0-9a-f]{16})-(96|256)\.webp`, and the id is parsed with `uuid.UUID` (MEMORY: a `<uuid:>` converter gives
    Django's HTML 404).
  - **One query:**
    - normally `Avatar…filter(user_id, version).values_list(<size column>).first()`;
    - when `If-None-Match` matches `"<version>-<size>"`, an `exists()` and a 304 that never loads the bytes.
  - A wrong version or size, or an unknown or malformed id, is a 404.
  - **Headers (on 200 and 304):** `Content-Type: image/webp`, `Cache-Control: public, max-age=31536000, immutable`,
    `ETag`, `X-Content-Type-Options: nosniff`, `Content-Security-Policy: default-src 'none'; sandbox`,
    `Content-Disposition: inline; filename="avatar.webp"`.

### Moderation
- `rules.AccountAct` gains `REMOVE_PHOTO`, `BLOCK_PHOTO_UPLOADS` and `ALLOW_PHOTO_UPLOADS`. `account_refusal` takes
  the photo state from the locked row.
- `services.remove_photo`, `block_photo_uploads` and `allow_photo_uploads`:
  - They go through `_account_action`. `_lock_account`'s `.only()` gains `avatar_version` and `avatar_uploads_blocked`.
  - Rows have `post=None`, `subject_user`, `post_snapshot=""`, no `blocked_until`.
  - They call `accounts.avatars.delete_photo` inside the transaction.
- `accounts/admin.py`:
  - `ACCOUNT_ACTIONS` entries carry their permission and their current/after describers.
  - `AvatarAdmin`:
    - **List:** thumbnail, account link, `bytes_total`, `updated_at`, ordered `-updated_at`; search by username.
    - **Permissions:** no add, change or delete (`delete_selected` removed).
    - **Actions:** Remove photo and Block photo uploads. An avatar's pk *is* the user id, so the shared confirmation
      flow is reused as it is.

## Frontend

### Files
- **New:**
  - `src/features/settings/AvatarUploader.tsx`, `photo-prep.ts` (pure, with injectable `decode`/canvas: jsdom has
    neither `createImageBitmap` nor canvas) and their tests.
  - `e2e/avatar.spec.ts`.
- **Changed:**
  - `src/lib/api/client.ts`: an `onUploadProgress` option.
    - **Transport:** XHR, wrapped into a real `Response`, so the rest of `apiFetch` is unchanged.
    - **Progress:** reports 0 to 1, and restarts on the one retry.
    - **Abort:** through `signal`.
  - `client.test.ts`: tests with a fake `XMLHttpRequest` covering progress, the token, the 401 retry, the error
    shape, abort and the network error.
  - `settings/{SettingsPage,settings-api,messages}.ts(x)`: the uploader goes before `ProfileForm` in section 01,
    outside its form and fieldset; `uploadAvatar` and `removeAvatar`; `photoErrorMessage`.
  - `lib/api/types.ts`: `Me.avatar_uploads_blocked`, plus doc comments on the sizes.
  - `components/ui/Avatar.tsx`: `loading="lazy" decoding="async"`.
  - `relay.test.ts`: a multipart boundary is passed through verbatim, and a 5 MB body goes through.
  - `ProfileHeader.test.tsx`: the misnamed photo test now really checks the photo.
  - The `Me` fixtures: `features/auth/test-helpers.tsx`, `layout.test.tsx`, `session.test.ts`,
    `settings/test-helpers.tsx`.
  - `e2e/helpers.ts`:
    - `makePhoto(path, {width, height, gps})` runs the backend venv's Python with Pillow;
    - `moderateAccount(username, act)` runs the moderation service with a fresh moderator, as `moderate()` does.

### The card (c2's avatar card classes, with the copy rewritten under D8)
- **Layout:** `p-space-md rounded-lg border border-outline-variant/30 bg-surface-container-lowest flex items-center
  gap-space-md`, then `<Avatar size={14} src={user.avatar_url}>`. The `h3` reads "Profile photo", with the line
  "JPEG, PNG or WebP, at least 128 × 128 pixels. We crop it to a square and remove location and camera data."
- **Idle:**
  - **Upload photo** / **Change photo**: a secondary `Button` that clicks a visually hidden
    `<input type="file" accept="image/jpeg,image/png,image/webp">`, whose value is reset after each choice.
  - **Remove photo**, when there is one.
- **Preparing:**
  - The browser checks run here, in order: MIME type, then size ≤ 20 MB, then whether `createImageBitmap(file,
    {imageOrientation: "from-image"})` can decode it, then that the short side is ≥ 128.
  - A failure shows the error in an `Alert` and keeps the old photo.
- **Preview:**
  - A square `rounded-lg` 96 px object-URL preview, revoked on change and on unmount.
  - **Use this photo** (primary) and **Cancel**.
- **Uploading:** `ProgressBar` with "Uploading… 42%", then "Saving…" at 100%; Cancel aborts.
- **Success:** a toast "Photo saved."; `reloadMe()` updates the rail, the top bar and the other tabs.
- **Blocked** (`avatar_uploads_blocked`): the notice and no Upload. **Unverified:** "Verify your email address to add a
  photo." with Upload disabled. Remove stays available in both.
- **Errors (`photoErrorMessage`):** each browser check, each server code, 413 `payload_too_large`, 429 with the wait,
  503 `photo_busy`/`backend_waking`, network.
- **Lint:** plain text, tokens only, no raw hex. The canvas fill uses a CSS keyword if `lint:tokens` flags a hex
  string.

## Steps (in order)

0. Save this plan as `docs/agents/plans/part-14B-photo-avatars.md`. Correct HANDOFF (Part 14 committed as `bd59f97`,
   Part 14B in progress, with the plan link). Measure the baselines: `pytest` 4205, `npm test` 2222, E2E 55. Activate
   `backend/.venv` in **every** call: anaconda's `python3` on PATH has PIL 12.0.0.
1. **Spike, the stop-and-ask gate.** `pip install Pillow==13.0.0` into the venv and add it to `requirements.txt`.
   - In a scratchpad script, confirm the following: `formats=`, `draft`, `reduce`, `exif_transpose`, `is_animated` on
     APNG and animated WebP, MPO detection, a WebP saved from a fresh image with no `EXIF`/`ICCP`/`XMP ` RIFF chunk,
     and a JPEG fixture with GPS EXIF + ICC + XMP.
   - Measure, in a subprocess, the peak RSS of processing a 25 MP RGBA PNG and a 24 MP JPEG.
2. Models and migrations:
   - the `Avatar` model (`0003_avatar`);
   - `SERVICE_OWNED_FIELDS`;
   - the `avatar_unblocked` kind and the permission (`moderation.0008`);
   - `0009` with frozen lists, and `roles.py`.

   Then `ruff check --fix . ; ruff format .` and `makemigrations --check`.
3. `avatars.py` and its processing, fixture and memory tests.
4. The PUT, DELETE and GET views, the `/me` fields, the 256 sizes and their tests (permissions, throttle, headers, 304,
   gate, lock re-check, races).
5. Moderation rules, services and admin (AvatarAdmin, UserAdmin, template) and their tests.
6. Export and deletion and their tests; the full `pytest`, `ruff`, `makemigrations --check`.
7. Frontend: client transport, types and fixtures, `photo-prep`, `AvatarUploader`, `SettingsPage`, messages,
   `Avatar`, the relay test; `npm run lint`, `lint:tokens`, `typecheck`, `format:check`, `npm test`.
8. E2E `avatar.spec.ts` (no sign-up; `seedAuthor` → `logIn`):
   1. Post an opinion.
   2. On `/settings`, upload a GPS JPEG; see the preview, then the progress, then the toast.
   3. The rail's `img` is the `-256.webp` URL and loads.
   4. On `/u/<name>` the card's `img` is `-96.webp`.
   5. `page.request` on that URL through port 3000: the headers, then `If-None-Match` → 304.
   6. `moderateAccount(…, "remove_photo")`, then reload → initials.
9. Docs:
   - **ARCHITECTURE:**
     - §2: the Avatar table as built, the service-owned fields, 13 kinds, the permission;
     - §3: the browser's 20 MB, the gate;
     - §4e: as built;
     - §8: the roles table, AvatarAdmin, the UserAdmin actions;
     - §9: the three endpoints, `/me` with 12 keys and 256, profile 256, the export photo and counts;
     - §10: `AvatarUploader`, `onUploadProgress`;
     - §12: the evidence column.
   - **ANALYSIS:** c-49 (the decisions above) and f-7 "as built".
   - **Other docs:**
     - SETUP B1 (Pillow 13.0.0 and why);
     - STRUCTURE;
     - MEMORY (durable facts only);
     - the `docs/test-command.md` Part 14B section, Linux and PowerShell, with "14B" in its intro line;
     - task.md (the criteria, both status spots, the deviations, notes for 16/17);
     - HANDOFF.

## Verification

- **Backend:** `cd backend && source .venv/bin/activate`, then:
  - `pytest` (all of it, 4205 before);
  - `ruff check . ; ruff format --check .`;
  - `python manage.py makemigrations --check --dry-run` and `manage.py check`;
  - the migrations applied, rolled back to `accounts 0002` / `moderation 0007`, and applied again.
- **Frontend:** `cd frontend`, then:
  - `npm run lint ; npm run lint:tokens ; npm run typecheck ; npm run format:check ; npm test`;
  - `NEXT_PUBLIC_GOOGLE_CLIENT_ID= npm run build`;
  - `npm run test:e2e` and `CI=1 npm run test:e2e` (build first).
- **Acceptance mapping:**

  | Criterion | Evidence |
  |---|---|
  | GPS JPEG → WebP with no EXIF/GPS/ICC/XMP | processing test parses the RIFF chunks directly (not through Pillow); orientation applied (a corner marker after an orientation-6 rotate); exact centre crop |
  | SVG, GIF, HEIC, PNG named `.jpg`, > 5 MB, > 25 MP bomb, < 128 px refused, small memory | one test per type, each with its code. **Bomb:** `load()` spied, never called. **> 5 MB:** the handler reads ≤ 5 MB + 64 KiB. Subprocess peak-RSS bounds (recorded in HANDOFF) |
  | Only WebP, no original stored | the row holds only WebP magic; `FILE_UPLOAD_TEMP_DIR` → `tmp_path` stays empty |
  | New photo → new URL, old → 404 | serve test |
  | Immutable, nosniff, CSP, 304 through the relay | serve tests; `relay.test.ts`; the E2E `page.request` |
  | Remove → initials at once; Block → 403 | service and admin tests (audit rows with `subject_user`); `avatar_url` null in every payload kind; the E2E reload |
  | Unverified → 403 `email_unverified` | API test; not counted against the throttle |

- **Mutation checks** (each must fail a test):
  - no `formats=`;
  - the pixel check after the load;
  - EXIF passed through;
  - no `exif_transpose`;
  - an off-centre crop;
  - no version check when serving;
  - a 304 without the version check;
  - no block re-check under the lock;
  - the fields missing from `SERVICE_OWNED_FIELDS`;
  - the throttle on DELETE;
  - the gate removed;
  - the export without the photo;
  - the admin loading the bytea;
  - the client sending the original instead of the re-encoded blob;
  - progress events ignored.
- **Visual:** headless Chromium at 1280, 1024 and 390 px: every state of the card, and the rail, cards, profile and
  notifications with photos. 0 px horizontal overflow; screenshots looked at.

## Stop conditions

- **Stop and ask if:**
  - Pillow 13.0.0 won't install from a wheel, or a spike call behaves differently from the above;
  - one worst-case decode (25 MP RGBA PNG) peaks more than about 200 MB of RSS above the baseline (the fix would be
    a lower pixel cap, which changes a documented limit);
  - any required test, lint or type check can't be made green;
  - the relay turns out to need a change;
  - an extra migration beyond the three listed is needed.
- **Out of scope (follow-ups):**
  - a user-facing "report photo" button (f-7);
  - colour management of ICC photos;
  - suspension hiding photos (Part 16);
  - a k6 avatar fetch (Part 16);
  - the CSP `img-src 'self'` (Part 16);
  - the production upload check (Part 18).
