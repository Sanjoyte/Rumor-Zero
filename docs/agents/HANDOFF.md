# Rumor Zero: live handoff

Update this file at meaningful checkpoints and before switching between Claude Code and Codex.
Keep it concise and factual. The incoming agent must verify it against the current files and
read-only git output.

## Active work

- **Part:** **6 (Profiles, follows, Following feed): planned and approved, not started.** Parts 0A, 0B,
  0D, 0C, 1, 2, 3, 4 and 5 are done (Part 5 was committed by the user as `b5b8089`). Part 1 CI is green
  (user-reported 2026-10-06); **Part 2, 3, 4 and 5 CI have not run yet.**
  - **Part 3 acceptance criterion 4 is still pending you:** the real-Google sign-in check
    (`docs/test-command.md` Part 3, steps 7 and 8). It doesn't block anything.
- **Machine:** the **Linux PC** (Ubuntu/Debian/Mint, bash). `backend/.venv` and
  `frontend/node_modules` exist there.
- **Owner:** none (Claude stopped after planning Part 6; no code written).
- **Phase:** plan approved and saved; implementation not started. Uncommitted: the new plan file and this
  file (the user reviews and commits).
- **Approved plan:**
  [`docs/agents/plans/part-6-profiles-follows-following-feed.md`](plans/part-6-profiles-follows-following-feed.md)
- **Previous plans:**
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
- **Last updated:** 2026-10-09 by Claude (Sonnet 5.5), Part 6 planning.

## Completed checkpoints

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

- HEAD is `b5b8089` ("Implementation Part 5: Post detail, sharing, deletion, status polling", committed by
  the user); the tree was clean when this session started. **Uncommitted:** only the new plan file
  `docs/agents/plans/part-6-profiles-follows-following-feed.md` and this file. No code was written.
- Docker, the dev servers and the ports were **not re-checked** in the Part 6 planning session (nothing was
  started or stopped). As last recorded after Part 5: Docker (Postgres 18 + Redis) up, no dev server, ports
  3000/8000 free. Run `docker compose up -d` before the first backend command.
- The local database has `posts.0001_initial` applied (Part 6 will add `social.0001_initial`). The guide's `part4-*` test accounts and their
  posts were deleted at the end; accounts from the E2E and screenshot runs (`post_*`, `opinion_*`, `invalid_*`,
  `unverified_*`, `phone_*`, `shot_*`, …) and their posts remain (Django Admin → Users deletes them).
- Ignored artifacts from the checks: `backend/tmp/mail/*.log`, `frontend/test-results/`,
  `frontend/playwright-report/`, and a production build in `frontend/.next/` made with an empty Google
  client ID (the last `npm run build` before the CI-mode E2E run).

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

1. **Implement Part 6 from the approved plan**
   ([`plans/part-6-profiles-follows-following-feed.md`](plans/part-6-profiles-follows-following-feed.md)).
   Fresh session (`/clear`); prompt: `Implement only the approved Part 6 plan, validate it, update task.md and
   HANDOFF.md, then stop.` Start with the plan's step 0: `git status` and `git diff` against this file (expect
   only the plan file and this file uncommitted), `docker compose up -d`, then set the phase above to
   "implementing". Step 1 is the backend app skeleton: `mkdir backend/apps/social`, then
   `python manage.py startapp social apps/social` and `ruff check --fix . ; ruff format .`. Recommended model:
   Sonnet 5.5 · medium (task.md).
2. **User, any time (not blocking Part 6):** commit the plan and this file; push so CI runs and report the
   result (Part 2's to Part 5's jobs have never run). Still open from Part 3: the real-Google check
   (`docs/test-command.md` Part 3, steps 7 and 8), and the Part 5 section of `docs/test-command.md` if you
   haven't walked it yet (Linux steps 3 to 9, about five minutes plus a minute's wait in step 8).

## Blockers or user decisions

- None open.
- User decisions for Part 6 (2026-10-09), **to go into ARCHITECTURE §9/§10 and ANALYSIS when built** (listed
  in the plan and in the Part 6 checkpoint above): Recent is the first and default `/home` tab, Following the
  second (signed-in only); the Following cache holds only ids; `verified` and `FALSE` counters include deleted
  posts; author names and avatars link to profiles.
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
