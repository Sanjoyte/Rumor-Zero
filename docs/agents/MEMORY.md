# Rumor Zero: durable agent memory

This file stores verified, durable context that a later Claude Code or Codex session would not
reliably infer from the codebase. It is not a progress log. Product and technical decisions belong
in `docs/ARCHITECTURE.md`; D-decision reasoning belongs in `docs/ANALYSIS.md`; part status belongs
in `task.md`; transient continuation state belongs in `HANDOFF.md`.

## Maintenance rules

- Add only verified facts or user-approved decisions that are likely to affect later parts.
- Include the date, affected part(s), evidence/source and consequence.
- Update an existing entry instead of adding a contradictory duplicate.
- Remove or mark an entry superseded when its canonical source changes.
- Never store secrets, credentials, personal tokens, raw env values, guesses or chat transcripts.

## Entries

### 2026-09-30 — Dual-agent continuity

- **Applies to:** all parts.
- **Decision:** Claude Code and Codex work sequentially in one checkout. `AGENTS.md` is their shared
  instruction source; `HANDOFF.md` holds live state; approved plans live under `plans/`.
- **Consequence:** either agent may maintain shared docs and continue the other's work, but they
  must not edit the same checkout concurrently. A user starts the incoming agent; cross-vendor
  takeover is not automatic.
- **Evidence:** user request and the repository-level dual-agent setup added on this date.

### 2026-09-30 — Git for Windows line endings corrupt text-looking binaries

- **Applies to:** all parts that add binary files (0D brand assets, fonts, PDFs).
- **Fact:** Git for Windows' system config (`C:\Program Files\Git\etc\gitconfig`) sets
  `core.autocrlf = true`. The ReportLab PDF in `docs/` (ASCII85 + Flate, no NUL bytes) passes git's
  text heuristic, so checkout inserted 1,911 CRs (554,315 → 556,226 bytes) and broke its xref
  offsets. The committed blob was intact.
- **Consequence:** the root `.gitattributes` marks binary types explicitly. Add every new binary
  extension there; never rely on git's text guess. `text=auto` uses the same heuristic.
- **Evidence:** `git ls-files --eol` showed `i/lf w/crlf attr/`; the blob's `startxref` pointed at
  `xref`, but the working copy's didn't. The repaired file hashes to the HEAD blob.

### 2026-09-30 — `localhost` stalls on Windows unless the container also listens on `::1`

- **Applies to:** every part that connects to local Postgres/Redis (all backend parts, Playwright in
  0C); anyone changing `compose.yaml` port bindings or `DATABASE_URL`/`REDIS_URL`.
- **Fact:** on this Windows setup `localhost` resolves to `['::1', '127.0.0.1']`. With the ports bound
  only to `127.0.0.1`, psycopg/libpq stalled on the `::1` attempt (8 s with `connect_timeout=8`, no
  visible end without one), so `manage.py makemigrations`/`migrate` looked hung. A raw socket to
  `::1` was refused after ~2 s, and `127.0.0.1` connected instantly.
- **Consequence:** `compose.yaml` binds both `127.0.0.1` and `[::1]` (still loopback-only). Keep both.
  If a Django command hangs on the DB, test with a socket/`connect_timeout` before suspecting the code.
- **Evidence:** socket and psycopg probes; after adding `[::1]` the `localhost` connect took 0.04 s.
- **Also (2026-10-03, Part 1):** when Docker Desktop restarts (sleep, update), our two containers stop (`Exited (255)`) while other projects' containers with restart policies come back. `pytest` then hangs silently on the first DB test. Check `docker compose ps` first and `docker compose up -d`.

### 2026-09-30 — sentry-sdk 2.71.0 default scrubbing is narrow

- **Applies to:** 0A (Sentry init), 17 (deploy), any sentry-sdk upgrade.
- **Fact:** with `send_default_pii=False`, only Authorization, Proxy-Authorization, Cookie,
  Set-Cookie, X-Forwarded-For, X-Real-IP and X-Api-Key are stripped (`SENSITIVE_ENV_KEYS`). The
  default `EventScrubber` matches **exact** lowercase keys. Request bodies ≤ 10 KB
  (`max_request_body_size="medium"`) and frame locals (`include_local_variables=True`) are sent by
  default. The newer `data_collection` option (substring matching) is opt-in only.
- **Consequence:** the ARCHITECTURE §12 Sentry settings are required. Re-check these defaults
  whenever the sentry-sdk version changes.
- **Evidence:** sentry-python tag 2.71.0: `sentry_sdk/integrations/_wsgi_common.py`,
  `sentry_sdk/scrubber.py`, `sentry_sdk/consts.py`, `sentry_sdk/utils.py`.


### 2026-10-01 — Claude Code's Bash tool mangles long and backslash-heavy heredocs

- **Applies to:** every part when Claude writes files through Bash (regexes, Windows paths, large components).
- **Fact:** in a heredoc, a doubled backslash arrives as a single one even when the delimiter is quoted (`<<'EOF'`), and a command body of roughly 8 KB or more can fail to parse with `unexpected EOF while looking for matching` a quote. A regex written with an escaped backslash in a character class then fails at runtime, or worse, a pattern built in a template string silently loses its escapes.
- **Consequence:** write regex-heavy or large files with the Write tool, or in several small Bash calls. In JavaScript prefer `String.raw` and `\x5c` for a literal backslash. Single-backslash escapes (`\n`, `\d`, `“`) survive fine in a heredoc.
- **Evidence:** `od -c` on a heredoc-written file during Part 0B (`lint-tokens.mjs` first failed with "Unterminated group").

### 2026-10-01 — Visual checks of the UI work headlessly with Edge on this machine

- **Applies to:** 0C and every UI part (the acceptance criteria ask for Stitch side-by-side checks).
- **Fact:** `C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe --headless=new --disable-gpu --hide-scrollbars --force-device-scale-factor=1 --window-size=1280,<height> --virtual-time-budget=15000 --screenshot=<abs path>.png <url>` renders the dev server or a Stitch `code.html` (`file:///` works; the Tailwind CDN needs network). Tall windows (11500 px) work; crop with `System.Drawing` in PowerShell. To click, focus or press keys, start Edge with `--remote-debugging-port=<n>` and drive it from a Node 24 script using the global `WebSocket` and the DevTools protocol (`Runtime.evaluate`, `Input.dispatchKeyEvent`, `Page.captureScreenshot`). Keep such scripts and images in the scratchpad, not the repo.
- **Consequence:** this caught two bugs unit tests could not: an avatar image that failed before hydration, and modal initial focus.
- **Evidence:** Part 0B verification; Stitch b2, d1 and a2 were screenshotted the same way for comparison.
- **Limit (2026-10-01, Part 0C):** headless Edge does not shrink the layout viewport below roughly 500 px, so a `--window-size=390,…` shot shows a clipped desktop-ish page, not the phone layout. For phone widths use Playwright (installed since 0C) with `browser.newPage({ viewport: { width: 390, height: 844 } })` from a scratchpad script that `require`s `frontend/node_modules/@playwright/test`. Measured that way, the 0C shell has no horizontal overflow at 390 px.

### 2026-10-01 — Agents can't read CI results here; the user reports them

- **Applies to:** every part whose acceptance needs a green CI run (0C, 16, 17, 18) or a GitHub check.
- **Fact:** the GitHub CLI (`gh`) is not installed on this machine (Git Bash: `gh: command not found`). The repository `Sanjoyte/Rumor-Zero` is private, so `WebFetch` of its Actions pages returns 404. The user reads results in the Actions tab and reports them, or pastes a screenshot of the failing log; that is how the first 0C failure arrived.
- **Consequence:** don't plan on `gh run list/view`. Ask the user for the run result, and record it in HANDOFF as user-reported. Reproduce Linux-only failures in Docker (next entry) before asking for another push. If the user installs `gh` later, read-only `gh run …` calls are allowed (`gh api` is denied in `.claude/settings.json`).
- **Evidence:** Part 0C, 2026-10-01: CI on `6e83866` failed (screenshot), and CI on `60cfffc` passed (user report).

### 2026-10-01 — Check Linux-only CI steps in Docker before asking the user to push

- **Applies to:** 0C, 17, 18, and any change to the frontend lockfile, OpenNext/wrangler/vite versions or Linux-only CI steps.
- **Fact:** `npx opennextjs-cloudflare build` can't be run on Windows (and must never run on a tree with a real `.env.local`: it copies `.env*` into the bundle). The Windows-side checks therefore missed that `@opennextjs/cloudflare` 1.20.7 imports an undeclared `esbuild`, and the first CI run failed (fix and removal condition: SETUP B3, `esbuild` row). Docker's Linux engine on this machine reproduces the CI frontend job exactly:
  1. Pack only what CI checks out: `git ls-files -co --exclude-standard` (tracked + new, never ignored files such as `.env.local`), keep the paths that exist, and `tar --force-local -cf <scratchpad>/ci-src.tar -T <list>`. GNU tar reads `C:` as a remote host without `--force-local`.
  2. Run `docker run --rm -e CI=true -v "<scratchpad>:/in:ro" node:24-bookworm-slim bash /in/ci-frontend.sh` from PowerShell. The script extracts into the container's own filesystem, then runs the job's steps (`npm ci`, lint, typecheck, lint:tokens, format:check, test, `npx opennextjs-cloudflare build`).
- **Consequence:** never bind-mount `frontend/` itself into the container. A run takes about 10 minutes (`npm ci` ≈ 6 min over the container network). The image matched CI's Node 24.21.0 / npm 11.19.0.
- **Evidence:** the Part 0C fix run passed every step ("OpenNext build complete", `.open-next/worker.js` written, exit 0).

### 2026-10-01 — Stopping a background `next dev` can orphan Next and workerd

- **Applies to:** every part where Claude runs `npm run dev` / `npx next dev` as a background task on Windows.
- **Fact:** stopping the background task ended only the Git Bash/npm wrapper. The `next dev` Node process kept running (with its `workerd.exe` children from `initOpenNextCloudflareForDev()`), stopped listening on its port, and blocked the next `next dev` with "Another next dev server is already running … PID n".
- **Consequence:** after stopping a dev server, list leftovers (`Get-CimInstance Win32_Process` filtered on `next dev` / `next\dist\bin` / `workerd.exe`), check they are the ones you started, and end them with `taskkill /PID <id> /T /F`. Confirm ports 3000/8000 are free before handing over. Playwright's own `webServer` processes are cleaned up correctly.
- **Evidence:** Part 0C verification (PIDs 11316 and 3956 plus two workerd children).

### 2026-10-03 — django-allauth 65.19.5 headless: what the auth design depends on

- **Applies to:** Parts 1–3, 14, 16, and every django-allauth upgrade.
- **Facts (read in the installed source, `allauth/headless/…`):**
  - App-client views are `csrf_exempt` and parse the body as JSON whatever the Content-Type (`restkit/views.py`), so login CSRF via `<form enctype="text/plain">` is possible without our Origin + header guard.
  - Login/signup bodies carry `meta.access_token`, `meta.refresh_token` and `meta.session_token` (the raw Django session key; `restkit/response.py`); refresh answers in `data`. A bad refresh token is a bare `{"status":400}`.
  - Refresh-token state lives in the session (`jwt/internal.py`, jti → exp); stock rotation deletes the used jti without a lock. Our `apps/accounts/tokens.py`, `cookies.revoke_refresh_token_session()` and logout call those internal helpers (`decode_token`, `validate_refresh_token`, `create_*_token`, `session_key_from_sid`).
  - `JWTTokenAuthentication` returns a lazy user and skips `is_active` (a deleted user's token raised DoesNotExist → 500); our `JWTAuthentication` fixes that.
  - `login_failed` (`10/m/ip,5/300s/key`) is consumed before the password check and answers 400 `too_many_login_attempts`, not 429. `signup` is 20/min per IP (429).
  - A failed email send during signup is not caught by allauth (500 after the user is saved); our adapter catches it. Headless-only mode raises `ImproperlyConfigured` when sending the verification email without `HEADLESS_FRONTEND_URLS`.
- **Consequence:** after any allauth upgrade, re-read those files and run `apps/accounts/tests/` (the strategy, cookie, middleware and concurrency tests pin the behaviour) before changing the pin.
- **Evidence:** Part 1 plan (facts 1–15) and implementation; the control test in `test_tokens.py` shows allauth's stock strategy losing a tab's token.

### 2026-10-06 — Development moves to Linux; docs carry both OSes; how the Linux check was done

- **Applies to:** every part that adds or changes a command in `docs/SETUP.md`, `docs/ENV_GUIDE.md`,
  `docs/test-command.md` or `AGENTS.md`; anyone verifying install steps from this Windows PC.
- **Fact:** from 2026-10-06 the user works on a Linux PC (Ubuntu/Debian/Mint, bash); the Windows 11 PC
  stays documented. Those three docs hold **both** versions, Linux first: a `**Linux (bash):**` block
  above the `**Windows (PowerShell):**` block, or one `**Linux and Windows (same commands):**` bash
  block when the text is identical. Expected output and prose are shared. The MEMORY entries below that
  mention PowerShell, Edge or `taskkill` are Windows-only.
- **Consequence:** a new test-command step or setup command needs both versions (`bash -n` the Linux
  one). The Linux commands were checked by running them verbatim in a fresh container (below), not
  only by reading them.
- **Method (reusable):** pack `git ls-files -co --exclude-standard` into a tar; start `postgres:18` and
  `redis:8-alpine`, then an `ubuntu:24.04` container with `--network container:<postgres>` so
  `localhost:5432/6379` behave as in the guide; run the SETUP/ENV_GUIDE blocks and the test-command
  blocks **extracted from the docs by script**, not retyped. A bare `ubuntu:24.04` has no `sudo`,
  `python3`, `curl`, `pkill` or `ss` (install them as harness setup; a real Ubuntu desktop has them).
- **Gotchas:** Git Bash rewrites a path argument like `/root/p0.sh` in `docker exec` into
  `C:/Program Files/Git/root/p0.sh`; set `MSYS_NO_PATHCONV=1` and pass `docker cp` sources through
  `cygpath -w`. Docker can't run inside that container, so `docker compose up -d`, the Docker Engine
  install and IPv6 `[::1]` publishing were not exercised (SETUP has an uncommitted
  `compose.override.yaml` workaround, git-ignored).
- **Evidence:** results and numbers in HANDOFF "Validation of the Linux clean-room run (2026-10-06)".

### 2026-10-03 — Windows PowerShell 5.1 strips the quotes in JSON passed to native programs

- **Applies to:** `docs/test-command.md` and any PowerShell instructions that send JSON with `curl.exe`.
- **Fact:** in Windows PowerShell 5.1 (5.1.26100), `curl.exe --data '{"email": "x@example.test", "password": "pw"}'` reaches the server with its inner quotes stripped, so allauth answers a bare `{"status": 400}` (unparsable JSON). Writing the JSON to a file with `Set-Content -Encoding ascii` and sending `--data-binary "@$env:TEMP\rz-login.json"` gives the real answer (`email_password_mismatch`). Header pairs can be splatted: `$h = '-H', 'Origin: …'`, then `curl.exe @h …`.
- **Consequence:** test-command steps use the file form. The Part 1 section's commands were run that way and their output recorded.
- **Evidence:** Part 1 test-command run, 2026-10-03.

### 2026-10-07 — django-allauth 65.19.5 in link mode: what the email flows depend on

- **Applies to:** Parts 2, 3, 14, 16, and every django-allauth upgrade.
- **Facts (read in the installed source, then pinned by `apps/accounts/tests/`):**
  - `POST auth/email/verify` with nobody logged in answers **401** on success (and sends `email_confirmed`); `AuthApiMiddleware` turns it into 200 and always drops `Authorization`/`X-Session-Token`, so a stale Bearer can't become a 410 either. Expired, used and forged keys all give 400 `invalid_or_expired_key`.
  - The verification key (`signing.dumps(EmailAddress.pk, salt="account")`) has two `:` and `activate_url` sends them as `%3A`. Next 16 re-encodes every route param, so the page decodes once (`email-key.ts`) and then matches a strict pattern. A non-Latin-1 character in a header value makes `fetch` throw, which reads as "network error".
  - The documented `auth/email/verify/resend` is the **code-mode** view (always 409 with links), so resend is our own `POST /api/v1/me/verification-email/`. It calls `send_verification_email_for_user()`, an internal allauth function: re-check it on upgrades.
  - **Rate limits are keyed by action and "per" type only** (`core/internal/ratelimit.py`, `get_cache_key`). `"1/60s/key,10/1d/key"` therefore shares one list and the minute rate prunes what the day rate needs (a simulation let 20 of 20 through). Daily caps are separate actions (`confirm_email_daily`, `reset_password_daily`), and `ACCOUNT_RATE_LIMITS` entries merge over allauth's defaults. `ACCOUNT_EMAIL_CONFIRMATION_COOLDOWN` (default 3 min) only feeds the default `confirm_email` rate, which our explicit entry overrides.
  - `AccountAdapter.add_message()` returns early only for headless-marked requests. With `django.contrib.messages` installed it would set a `messages` cookie on the frontend origin, so our adapter makes it a no-op.
  - `allauth` precedes `apps.accounts` in `INSTALLED_APPS`, so templates inside our app are shadowed: ours live in `backend/templates/account/email/`. allauth's `base_message.txt` prints the request host (`django.contrib.sites` isn't installed), hence "Hello from localhost:8000!" until we replaced it.
  - A reset key is single use (its hash covers the password, `last_login` and the user's emails) and its expiry reads `PasswordResetTokenGenerator._now()` (a naive `datetime.now()`), not `time.time()`. A successful reset issues tokens like a login.
  - `GET auth/password/reset` (key in `X-Password-Reset-Key`) answers `data.user` with the account's email and username to anyone holding a valid key. The frontend ignores it; the key is already a password-reset secret.
- **Testing gotcha:** the shared `clock` fixture moves `time.time()` (allauth's rate limits, Django's signed keys), but PyJWT checks `iat` against the real clock. Mint access tokens **before** moving the clock, or the API answers 401 ("iat in the future").
- **Evidence:** Part 2 plan and implementation; `test_email_verification.py`, `test_resend_verification.py`, `test_password_reset.py`, `test_emails.py`.

### 2026-10-07 — allauth defers `jwt` and `cryptography`: two first sign-ins on a cold server could answer 500

- **Applies to:** every part that runs the backend under concurrency (E2E, Render with threaded gunicorn), and any allauth upgrade.
- **Fact:** allauth imports `jwt` and `cryptography` lazily (`core/internal/deferred.py`), on the first token it makes. Several simultaneous first sign-ins (Playwright's 6 workers against a freshly started `runserver`) imported them from different threads and one saw a half-built package: `AttributeError: cannot access submodule 'ciphers' of module 'cryptography.hazmat.primitives' (most likely due to a circular import)`, a 500 on `/auth/signup`. It looked like a flaky test: the failing run's own sign-up screen said "Something went wrong. Try again." and `[WebServer]` lines in the Playwright output held the traceback.
- **Consequence:** `AccountsConfig.ready()` imports `TOKEN_LIBRARIES` at startup; `test_startup.py` checks it in a fresh interpreter. Five cold-start E2E runs in a row passed afterwards (3 of the 4 cold starts before the fix had failed). When an E2E sign-up shows a generic error, read the `[WebServer]` traceback before suspecting the test.
- **Evidence:** `e2e-*.log` captured from three cold-start runs; `ready()` + `test_startup.py`.

### 2026-10-07 — Tooling gotchas on this Linux PC (Claude Code)

- **Applies to:** every part where Claude starts and stops servers or reads Stitch files.
- **Facts:**
  - `pkill -f "<pattern>"` inside a Bash call also matches the call's own shell (the pattern is in its command line) and ends it with exit 144. Find the PID with `ss -ltnp | grep -E ':(3000|8000)\b'` and `kill <pid>`, or use a pattern the command line doesn't contain.
  - `sed` is denied by `.claude/settings.json`; read Stitch `code.html` files with the Read tool (offset and limit).
  - Playwright treats an `aria-disabled="true"` button as "not enabled": use `click({ force: true })` when a test means a person's click on it.
  - An `ApiError`/mock typing trap: spreading a `Partial<AuthApi>` into the mocks in `features/auth/test-helpers.tsx` widened them to plain functions; `testSession()` now returns `MockedAuthApi` so tests can call `api.fetchMe.mockResolvedValue`.
  - **Shell state doesn't persist between Bash calls, and `anaconda3/bin` is first on `PATH`:** a call without `source backend/.venv/bin/activate` runs anaconda's `ruff` (a different version: it flagged UP038 in untouched files and reformatted three files) and has no `allauth`. Activate the venv in **every** call that runs `ruff`, `python` or `pytest` (Part 7B).
  - A mutation script that matches source text must be re-checked after `prettier --write`: it joins and splits lines, so a pattern written before formatting can silently stop matching (the harness skips with a message instead of asserting).
- **Evidence:** Part 2 implementation session.

### 2026-10-08 — django-allauth 65.19.5 social login (Google ID token): what Part 3 depends on

- **Applies to:** Parts 3, 14 (connect, disconnect, Settings), 16, and every django-allauth upgrade.
- **Facts (read in the installed source, then pinned by `apps/accounts/tests/test_google_login.py`):**
  - **A pending social sign-up can't be finished here.** `auth/provider/token` answers **401** with `data.flows` `provider_signup` and needs `meta.session_token` as `X-Session-Token`, which `AuthApiMiddleware` strips and the relay doesn't forward. So a sign-up must never pend: it pends only when the Google email is missing, unverified or already taken, and `SocialAccountAdapter.pre_social_login` refuses the first and email-matching catches the last. `SOCIALACCOUNT_AUTO_SIGNUP` stays True.
  - **No rate limit of its own, a network call every time.** `ProviderTokenView` has none, and `jwtkit.fetch_key` GETs Google's certificates on every call (no cache). We consume the `login` bucket in the middleware.
  - **Two forged-token shapes are 500s, not 400s:** a header without `kid` (`KeyError` at `jwtkit.py:57`, outside the `PyJWTError` catch) and `alg: HS256` against Google's RSA key (`TypeError`; reproduced with PyJWT 2.15.1). `apps/accounts/google.py` rejects both before allauth.
  - **`email_confirmed` never fires for Google emails** (only `verify_email` and the admin send it), so `users.is_email_verified` needs our own `social_account_added` receiver. That signal fires inside `SocialLogin.connect()`, **after** `wipe_password` (order: lookup → `pre_social_login` → `wipe_password` → `connect` → `perform_login`); marking the address verified earlier would skip the wipe. `sociallogin._did_authenticate_by_email` is set only by the email-match path (never in `__init__`: read it with `getattr`).
  - **`wipe_password` treats a missing `EmailAddress` row as unverified.** `create_user` and the admin make no row, so a first Google sign-in on such an account wipes its password (and a staff account would lose Admin access: hence the staff refusal).
  - **Email matching doesn't skip inactive users or non-Gmail addresses.** It links them (and may wipe the password) before `perform_login` refuses an inactive user, and it trusts `email_verified` alone. Google says it is authoritative only for `@gmail.com` and tokens with `hd`, hence the adapter's checks.
  - **PyJWT checks `iat` with no leeway and allauth passes none:** a server clock behind Google's gives occasional 400 `invalid_token`. `exp`, `iss`, `aud` and `jti` (one use, in the shared cache: per process when `REDIS_URL` is blank) are checked by `jwtkit.verify_and_decode`.
  - **A `SocialApp` database row for `google` next to the settings app makes two apps match: `MultipleObjectsReturned`, a 500.** The admin models `SocialApp` and `SocialToken` are unregistered for that reason. `allauth.socialaccount` also adds `auth/provider/signup`, `auth/provider/redirect` and `account/providers` (all 404 through our allow-list).
  - **allauth's username generator** (`generate_unique_username([first, last, email, username, "user"])`) would give most people `user1234`, because our pattern rejects `.` and `-` and `user` is reserved; `save_user` sets ours first. `SocialAccount.extra_data` otherwise stores the whole token payload; `populate_user` trims it.
  - **`wipe_password` ends other sessions only with `allauth.usersessions`** (not installed). Other refresh tokens die at their next refresh instead, because the session auth hash changed (`get_user`).
  - **`jwtkit` imports `cryptography.x509` lazily:** `TOKEN_LIBRARIES` preloads it (the same cold-start race as Part 2).
- **Frontend facts:**
  - Google's real button is an iframe that GIS sizes 10 px wider than the `width` option (410×44 at the 400 px maximum); the card's padding absorbs it and the page doesn't overflow.
  - With an unknown client ID the script still loads and calls `renderButton`, then logs `[GSI_LOGGER]: The given client ID is not found` and draws a 0×0 iframe.
  - Closing the popup raises no event; clicking the button with the real ID opens `accounts.google.com/v3/signin/identifier`.
  - `NEXT_PUBLIC_*` is inlined at build time: `NEXT_PUBLIC_GOOGLE_CLIENT_ID= npm run build` bakes in "no Google" (CI's `.env.example` copy does the same). `next dev` honours an *empty* process-env value over `.env.local`; PowerShell can't set one (`$env:X = ""` deletes the variable), so the Windows guide uses `python -c` / `node -e` to start a program with an empty value.
- **Testing:** the `google` fixture in `apps/accounts/tests/conftest.py` signs real RS256 ID tokens and serves `{kid: certificate}` through a fake `get_requests_session`, so allauth's own checks run unpatched; the root `conftest._hermetic` pins a test client ID and forbids network. A test for an account that must *link* needs a verified `EmailAddress` row (`UserFactory` makes none).
- **Evidence:** Part 3 plan and implementation; `test_google_login.py`, `test_middleware.py`, `docs/test-command.md` Part 3 (curl and browser runs, 2026-10-08).

### 2026-10-08 — DRF and Django facts that Part 4's posts API depends on

- **Applies to:** Parts 5–8, 11C, 12 (any list or write view), 16, and every DRF or Django upgrade.
- **Facts (read in the installed source, then pinned by `apps/posts/tests/`):**
  - **A view with a public GET and a protected POST needs `get_permissions()` and `get_throttles()` by method.** DRF runs throttles on *every* request (`APIView.initial`), and `ScopedRateThrottle` never looks at the method, so reading the feed would use up `post_create`. Order is authentication → permissions → throttle → validation: a 401 or 403 never counts, a 400 does.
  - **`SimpleRateThrottle.timer` and `THROTTLE_RATES` are bound when the module loads.** The `clock` fixture (`time.time` only, and too late) and `settings.REST_FRAMEWORK` overrides can't move or change them: a throttle test makes the real number of requests (30 POSTs).
  - **A crafted cursor is a 500.** DRF's `CursorPagination` passes the cursor's position straight into `created_at__lt=…`; Django's `ValidationError` isn't mapped by the core handler. `FeedPagination.decode_cursor` parses it (`parse_datetime`, must be time-zone aware) and answers 404. Any new list that uses the core `CursorPagination` needs the same guard (Part 16 follow-up).
  - **Cursor ties:** DRF filters on the first ordering key and counts equal values with an offset (use `("-created_at", "-id")`). When a *whole page* shares one timestamp it falls back to a plain `OFFSET`, so a post inserted meanwhile can repeat. Microsecond timestamps make that impossible in production; tests must give every post its own `created_at`.
  - **A custom `APIException` with a `wait` attribute gets `Retry-After` for free** (`rest_framework/views.py`, `exception_handler`). `Throttled` would append "Expected available in N seconds."; a plain `APIException` subclass doesn't. Validation errors reach the wire as messages only (no `code`), so a code the client must branch on has to be an `APIException`.
  - **DRF's `ListField` checks every element before its length rule,** so six sources with one bad element would give a per-index error instead of "too many". `SourcesField` is a plain `Field` raising a Django `ValidationError` dict, which DRF keeps (`get_error_detail`), giving `{"sources": {"1": ["…"]}}`.
  - **`ArrayField(CharField(max_length=n))` can't refuse a long element:** Django writes `%s::varchar(n)[]` and an explicit cast truncates silently (a literal INSERT raises "value too long"). The validator is the only guard. `sources__len` compiles to `coalesce(array_length(sources, 1), 0)`, so `[]` is 0; `~Q(sources__contains=[""])` doesn't catch a NULL element, hence the extra `array_position(sources, NULL) IS NULL` check.
  - **Postgres `trim()` strips spaces only,** so a `char_length(trim(content))` check would disagree with the serializer: the DB checks `Length("content")` (code points) and the serializer rejects blank text.
  - **The platform-settings seed comes from the developer's own `backend/.env`** (`PLATFORM_SETTINGS_SEED`), so a test must pin `fact_posts_per_day` (the `fact_limit` fixture **saves** the row: `.update()` skips the cache invalidation, and a `transaction=True` test flushes the row, so it heals with `get_or_create`). The E2E backend uses that seed too: E2E tests compare the allowance before and after, never "10".
- **Evidence:** Part 4 plan (review pass) and `apps/posts/tests/` (mutation-checked: removing each rule makes a test fail).

### 2026-10-08 — Source links: why the client doesn't use `new URL()`, and how `idna` 3.20 behaves

- **Applies to:** Parts 4, 5 (SourceList), 16, 12 (search), any code that validates a user-supplied link.
- **Facts:**
  - **The browser's URL parser repairs input instead of refusing it:** `https://good.com\evil.com` has host `good.com`, `https://exa%6dple.com/` becomes `example.com`, `https:example.com` and `https:///example.com` parse, `127.1` and `0x7f.1` read as `127.0.0.1`, and `xn--zzzz.example` is accepted unchecked. The server must not use it as the algorithm, and the page must not either (it would say "valid" and the server "400"). Both sides run one algorithm (RFC 3986 appendix-B split, ASCII-only trim, forbidden-character categories, own label rules) against the shared `source_vectors.json`; `new URL()` is used only to punycode a non-ASCII host. Only the server can check that an `xn--` label is a real A-label.
  - **JS and Python differ on small things that matter:** `trim()` vs `strip()` (U+FEFF, U+001C–001F, U+0085), `\d` (Unicode digits in Python), `$` (a trailing newline in Python), and case-insensitive matching (`httpſ://` matches `https` and U+212A matches `k` in Python unless `re.ASCII`). Use `[0-9]`, `fullmatch`, ASCII-only flags and trim `" \t\r\n"` only.
  - **`idna` 3.20:** `transitional` is deprecated and ignored (always non-transitional, so `faß.de` → `xn--fa-hia.de`, the browsers' answer); `idna.encode` also checks *ASCII* labels and rejects `_` and `ab--cd` (browsers accept both, e.g. `r3---sn-x.googlevideo.com`), so ASCII hosts are lower-cased and checked by our own label rule and only non-ASCII hosts go through it.
- **Evidence:** the Part 4 plan's review, Node 24's `URL`, `apps/posts/tests/test_validators.py` and `sources.test.ts` (172 shared cases).

### 2026-10-08 — Frontend facts from Part 4 (React 19 lint, focus, the draft)

- **Applies to:** every part that adds forms, modals or hooks.
- **Facts:**
  - **`eslint-config-next`'s React rules refuse ref writes and reads during render** (`react-hooks/refs`): keep "the latest options" in a ref assigned inside an effect, and derive anything rendered from props or state; a reset on a prop change uses the "adjust state while rendering" pattern (`if (owner !== userId) { setOwner(userId); …reset… }`), not an effect.
  - **`TextField`'s props don't include `ref`** (TypeScript rejects it; checked for `TextField` only). To focus a field, give it an `id` and use `document.getElementById`; a "pending focus" ref read in an effect handles a row that doesn't exist yet.
  - **`cn()` has no tailwind-merge:** don't override a variant's padding (`px-space-sm` on a ghost `Button` that has `px-space-md`): which wins is CSS order.
  - **A `fieldset disabled` is the cheap way to lock a whole form** (textarea, inputs, the segmented control and add/remove buttons all disable natively) while the modal's × stays usable. A modal can be closed mid-request (Esc, ×), so the provider, not the modal, owns the request.
  - **Playwright won't click an `aria-disabled` button** without `force: true` (already noted in Part 2); in unit tests, closing a modal with `{Escape}` while a button is disabled sends the key to `body`, not the dialog: click ×.
- **Evidence:** Part 4 implementation (`ComposerProvider.tsx`, `useCursorFeed.ts`, `ComposerModal.tsx`).

### 2026-10-09 — Next 16.3.8 metadata and DRF facts that Part 5's post page depends on

- **Applies to:** Parts 5, 6 (`/u/[username]` metadata), 12, 15, 18, and every Next or DRF upgrade.
- **Facts (read in the installed source, then pinned by tests):**
  - **A page-level `openGraph` or `twitter` replaces the parent's whole object** (`next/dist/lib/metadata/resolve-metadata.js`, `mergeMetadata`: `newResolvedMetadata.openGraph = resolveOpenGraph(metadata.openGraph…)`), and the root's file-convention share image is merged only at the root segment (`mergeStaticMetadata`). A page that sets `openGraph` without `images` loses `og:image`, `siteName` and `type`; OG and Twitter titles also get **no** title template. `post-metadata.ts` sets them all, and names `/opengraph-image.png` and `/twitter-image.png`, which `brand-guard.test.ts` normally forbids outside the brand files (the two metadata files are allow-listed). Any later page with its own `openGraph` (profiles in Part 6) needs the same.
  - `next dev` and `next start` answer `curl /p/<id>` with the tags in the HTML (title, `og:*`, `twitter:*`, canonical, `robots`), so the crawler check is a plain `curl | grep`.
  - **A public DRF GET still authenticates a Bearer token it is given:** `JWTAuthentication` makes a stale token a 401 even under `AllowAny`. The page client refreshes and retries; `PostStatusView` sets `authentication_classes = []` (it never needs the user) and the poller sends `token: false`.
  - **A `<uuid:pk>` URL converter answers Django's HTML 404** (URL resolution fails before DRF's handler). Routes take `<str:post_id>` and the view parses it with `uuid.UUID`; the literal `posts/status/` route must come first.
  - `Post.updated_at` is `auto_now`: `save(update_fields=[...])` must list `"updated_at"` or it isn't bumped. `delete_post` re-reads the row with `select_for_update().not_deleted()` inside `atomic()`, so two simultaneous deletes give one success and one `PostNotFound` (test: `run_together`, `transaction=True`).
  - A throttle test for `status_poll` makes the real 120 requests (rates are bound at import, see the Part 4 entry); it takes about 1 s.
- **Evidence:** Part 5 plan and implementation; `test_api_detail.py`, `test_api_delete.py`, `test_api_status.py`, `post-metadata.test.ts`, `e2e/post-detail.spec.ts`.

### 2026-10-09 — Frontend facts from Part 5 (StrictMode, polling, the E2E status flip)

- **Applies to:** every part with a client effect that fetches (Parts 6, 7, 13), and every E2E test that needs a status change.
- **Facts:**
  - **StrictMode runs effect → cleanup → effect on mount in `next dev`.** A cleanup that aborts the request, plus an "already fetched" marker set *before* the request finishes, leaves the page without data: the author never got `is_mine` (and so no Delete button) when arriving from a card. Mark a viewer as fetched in the success handler. The bug only shows when the page mounts after the session settled (a client navigation): a unit test must mount `PostDetail` behind a `useAuth().status === "authenticated"` gate inside `<StrictMode>`; the mutation of the fix fails it. The E2E suite found it first.
  - `react-hooks/set-state-in-effect` (eslint-config-next) refuses `setState` in an effect body: put "go to loading and refetch" in the `retry` callback, not in an effect on a counter.
  - **Polling results are an overlay** (`status-overlay.ts`), not edits to `useCursorFeed`'s pages: the feed keeps owning its pages, and a reload can't resurrect an older status. `useStatusPolling` filters its own ids (settled or vanished ones drop out), so consumers pass the posts *loaded* as pending without a circular dependency.
  - The visible-time budget uses `document.visibilityState` through `vi.spyOn(document, "visibilityState", "get")` in tests and `act(() => vi.advanceTimersByTimeAsync(…))` for timers.
  - **The E2E status flip** (`e2e/helpers.ts` `setPostState`) runs `manage.py shell -c` with `backend/.venv` against the database the E2E backend uses (the same env: `REDIS_URL=""`, `EMAIL_PROVIDER=file`). A fact needs `verdict_source`, `pipeline_verdict` and `confidence_score` set with `status='verified_true'` to satisfy the database checks. A reused (not Playwright-started) `runserver` must also use `EMAIL_PROVIDER=file`, or `signUpVerified` can't read the mail.
  - A `VerdictBlock` for a removed post rendered an empty card (its `explain()` has no text for `removed`): found only by looking at the author's page, now `null` and tested.
- **Evidence:** Part 5 implementation (`usePostDetail.ts`, `useStatusPolling.ts`, `PostDetail.test.tsx`, `e2e/post-detail.spec.ts`).

### 2026-10-09 — Backend facts from Part 6 (follows, the Following feed and its cache)

- **Applies to:** Parts 7, 7B, 11B, 12, 13, 14 (anything that reads people, follows or the Following feed), and every DRF or Django upgrade.
- **Facts (read in the installed source or measured, then pinned by `apps/social/tests/`):**
  - **A username from a URL can crash the database:** a NUL byte (`%00`) in `username=…` makes Postgres raise `DataError`, a 500 that no cursor or 404 handler catches. `social.services.lookup_name` normalises (NFKC, trim, lower-case, at most 64 characters) and then `fullmatch`es `[a-z0-9_]{3,30}` **before** any query; use it (or `find_active_user`) for every lookup by username. `username__iexact` would not use the unique index; the stored names are always lowercase, so an exact match is the cheap case-insensitive lookup.
  - **DRF's `CursorPagination` accepts `.values()` rows** (`_get_position_from_instance` handles dicts), which is what lets the Following feed page through `values("id", "created_at")` and cache just the ids. The cursor check lives in `apps/core/pagination.TimestampCursorMixin` (before `CursorPagination` in the bases); `FeedPagination` and `UserListPagination` use it. A cursor that base64-decodes to no `p=` (for example `!!!`, whose invalid characters DRF's decoder ignores) is simply the first page, not a 404; a crafted position is a 404.
  - **`Follow.objects.get_or_create` is the race-safe follow:** two simultaneous requests give one row and no error (Django catches the `IntegrityError` and reads the row back; `test_services.py` runs two threads).
  - **The cache holds only ids:** `social:following-feed:v1:<user_id>` → `{"ids": [...], "next": token|None}`, written only for a first page asked without `cursor` and `page_size`; `following_page` re-checks the stored shape (a malformed value is a miss) and `load_posts` drops ids that are no longer `visible()`. The key is deleted now and again `on_commit` (the PlatformSettings pattern) by `follow`, `unfollow` and `create_post`; `delete_post` needs nothing (hydration filters). A concurrent read can still refill the cache with the old ids between the delete and the commit; the TTL bounds it. LocMem uses `time.time()`, so the shared `clock` fixture ages cache entries in tests.
  - **The Following query plan** (`EXPLAIN ANALYZE`, 20,000 posts, 401 users, 200 follows, rolled back): Postgres scans `posts_recent_idx` newest first and filters on `author_id = me OR author_id = ANY(hashed subplan of follows)`: 0.07 ms with 200 follows, 0.3 ms (2,206 rows filtered) with 3 quiet follows. It degrades only when someone follows a few very quiet accounts in a very large table; the ids cache hides most of it. If it ever bites, materialise the followed ids and use `author_id = ANY(...)` against `posts_author_created_idx`.
  - `verified` and `false` counters are correlated `COUNT` subqueries annotated onto the user query (one query for the whole profile, 1 anonymous and 2 signed in); `_by_status` must stay the helper they use (an earlier edit left it unused and a mutation check caught the missing test).
- **Evidence:** Part 6 plan, `apps/social/tests/` (160 tests, 26 mutation checks all caught), the EXPLAIN run recorded in HANDOFF.

### 2026-10-09 — Frontend and E2E facts from Part 6

- **Applies to:** every E2E test that signs people up, every part with a hover or toggle button, and any page with its own `openGraph`.
- **Facts:**
  - **The E2E suite is bounded by allauth's sign-up limit (20 a minute per address) and by Argon2 time.** The suite already made about 16 sign-ups; adding 7 more in `social.spec.ts` broke it (sign-ups stuck on `/signup`). The file is now `describe.configure({ mode: "serial" })` with **two people created once** in `beforeAll` and shared by the tests, which leave the follow as they found it. `signUp` in `e2e/helpers.ts` waits up to 30 s for `/verify-email`: with six workers hashing passwords at once the 5 s default flaked (a disabled "Create account" button in the failure's page snapshot means the request is still in flight, not refused). That flake predates Part 6 (1 of 5 runs without the new spec). Budget new E2E sign-ups against the 20.
  - **A hover label must not remove the visible one from the accessible name.** `FollowButton` first used `hidden group-hover:inline` for "Unfollow": after a click the pointer is still over the button, the "Following" span became `display: none` and the name fell back to the `title`. Both words now share one grid cell and only opacity changes (the width is fixed too). Test with `getByRole("button", { name: "Following" })` *after* a click.
  - **`useCursorFeed` reads `fetchPage` through a ref and does not refetch when it changes:** remount (`key={username:filter}`) or change `resetKey`. A closure over `username`/`filter` is fine inside a remounted component.
  - **A card's claim is wrapped in curly quotes:** `getByText("Post a")` never matches; use a regex ending in `\u201D`.
  - **The brand guard allows the share-image file names only in `features/posts/post-metadata.ts`** (and its test). `profile-metadata.ts` imports `OG_IMAGES` and `TWITTER_IMAGES` from there, and its test must not write the names (assert `width`/`height` and the array length).
  - A "same tick" double click needs `act(() => { button.click(); button.click(); })` to test a single-flight ref (`userEvent.dblClick` re-renders between the clicks and the disabled button alone passes the test).
  - **A page with its own `openGraph` for a profile uses `type: "profile"`;** `curl /u/<name>` shows `og:type` `profile`, the canonical link, and (for an unknown name) `noindex`.
- **Evidence:** Part 6 implementation (`FollowButton.tsx`, `ProfilePosts.tsx`, `e2e/social.spec.ts`, `e2e/helpers.ts`); five full E2E runs and two CI-mode runs passed after the fixes.


### 2026-10-10 — Backend facts from Part 7 (likes, comments and their counts)

- **Applies to:** Parts 7B, 8, 10, 11B, 11D, 13, 14, 16, and every DRF or Django upgrade.
- **Facts (read in the installed source, measured, or pinned by `apps/social/tests/`):**
  - **One choke point for the counts:** `PostQuerySet.for_list(viewer)` calls `social.engagement.with_engagement`, which adds `like_count`, `comment_count` (and, for a signed-in viewer, `liked_by_me`) as correlated subqueries, so a list stays 1 query anonymous and 2 signed in. `posts` depends on `social` only through that function-local import (the models point the other way). `PostSerializer` reads the three attributes **strictly**, so a new list that forgets `for_list(viewer)` raises instead of showing zeros; the 201 answer of a new post calls `engagement_defaults`. 7B adds the repost and bookmark counts in the same place.
  - **`User.save` sets `is_staff` from `role`** (`is_staff = is_superuser or role != USER`): a test user made with `UserFactory(is_staff=True)` is silently *not* staff and the admin redirects to the login, so a "this staff member can't hide" test passes for the wrong reason. Make moderators with `UserFactory(role=Role.MODERATOR)` (it has no model permissions until Part 10; grant `Permission` rows in the test).
  - **A read-only `ModelAdmin` can still carry actions:** all three `has_*_permission` return False, the actions use `@admin.action(permissions=["hide"])` and a custom `has_hide_permission(request)` that asks `request.user.has_perm("social.change_comment")`. Django calls `log_change` for none of it: `CommentAdmin` writes the `LogEntry` itself (`self.log_change(request, comment, "Hidden")`), because `moderation_actions` (Part 10) has no comment kind.
  - **The partial index is used for both the list and the count.** Django compiles `is_hidden=False` as `NOT "is_hidden"` in a filter and in an index `condition`, so the planner proves the predicate. `EXPLAIN` (a rolled-back transaction: 300 users, 2,000 posts, 40,000 comments, 30,000 likes): the first page is an index-only scan of `comments_post_visible_idx`, the count a bitmap scan of it and the like count a bitmap scan of `likes_post_created_idx`. A count costs about one index entry per comment on the post, so a post with many thousands of likes would want a stored counter (Part 16). 11D's daily comment counts must use the same predicate as the index.
  - **Comments are a soft delete** (`deleted_at`, user decision 2026-10-10), so a deleted comment still counts as "a comment" for anything that reads the table directly. **Part 8** must decide whether `counts_toward_threshold` ("≥1 post or comment") counts one; the principle used for posts and the fact quota ("deleting undoes nothing") says it does.
  - **A removed post answers 404 to a like or a comment, its author included, but a like can still be taken back from it** (`unlike` only needs a post that isn't deleted); a hidden comment answers 404 to its own author's delete. `delete_comment` re-reads the row with `select_for_update(of=("self",))` and the visibility filters, so two simultaneous deletes give one 204 and one 404 (the race test fails without the lock).
  - **The ascending cursor works with `TimestampCursorMixin`** unchanged (`ordering = ("created_at", "id")`): only the position's format is checked, so a crafted one is still a 404. A comment that arrives between two pages is neither skipped nor repeated.
  - The like limit test makes the real 300 + 1 requests (about 1 s); the comment limit 60 + 1. Rates are bound at import (Part 4 entry), so a test can't lower them.
- **Evidence:** Part 7 plan and implementation; 23 backend mutation checks (every one caught), the EXPLAIN run in HANDOFF.

### 2026-10-10 — Frontend facts from Part 7 (accessible names, focus, tests)

- **Applies to:** every part with icon-plus-count buttons or a form that locks while sending.
- **Facts:**
  - **The accessible-name algorithm (dom-accessibility-api, and browsers for inline boxes) joins adjacent inline `<span>`s with no space:** `<span>Like </span><span>3</span>` reads "Like3", and the trailing space is trimmed. Put the whole name in one `sr-only` span (`{`Like ${count}`}`) and mark the visible word and count `aria-hidden`; `aria-pressed` carries on/off so the name stays stable.
  - **React keeps a textarea's `defaultValue` in sync, so the typed text is in the DOM as text:** Playwright's `getByText("my comment")` matches the textarea itself the moment you `fill` it and a "wait for the comment to appear" returns at once. Wait on `getByRole("article").filter({ hasText })` instead.
  - **A disabled `fieldset` drops the focus of the field inside it, and `focus()` in `finally` runs while the DOM is still disabled** (the state change hasn't rendered). Set a ref and refocus in an effect that runs when `sending` turns false (`CommentComposer`).
  - `useCursorFeed` has `append` (kept apart, rendered after the pages, de-duplicated so a later page's copy wins its place) and `remove(key)` (dropped until the next fresh load, which already omits it); both are cleared with `prepend` when the signed-in user changes.
  - **`FeedList` now needs the auth and toast providers** (each card carries a `LikeButton`). Tests use `renderWithSessionAndToast` from `features/posts/test-helpers` (it keeps the providers on `rerender`); `ComposerProvider` would need `next/navigation`.
  - An aborted request (StrictMode, a closed tab) shows as `[WebServer] API relay: backend unavailable (ResponseAborted)` in the Playwright log: noise, not a failure.
  - The new E2E tests join the serial describe in `social.spec.ts` and reuse its two accounts, so Part 7 adds no sign-up to the suite's budget of 20 a minute.
- **Evidence:** Part 7 implementation (`LikeButton.tsx`, `CommentComposer.tsx`, `useCursorFeed.ts`, `e2e/social.spec.ts`); 34 frontend mutation checks (32 caught at once; the other two were equivalent and led to removing dead code).

### 2026-10-10 — Backend facts from Part 7B (the mixed timeline, reposts, bookmarks)

- **Applies to:** Parts 8, 11B, 11D, 12, 13, 14, 16, and every DRF or Django upgrade.
- **Facts (read in the installed source, measured, or pinned by `apps/social/tests/`):**
  - **DRF's cursor can't page a union:** Django refuses `filter()` after `union()`, so `apps/social/timeline.py` filters each side "after the cursor", slices it, `union(all=True)`s the sliced `values_list` querysets and orders the union by the four columns (Django 5.2 compiles that to `(SELECT … ORDER BY … LIMIT n) UNION ALL (SELECT … LIMIT n) ORDER BY 1 DESC, 2 DESC, … LIMIT n`). The sort key, token and page rule are in ARCHITECTURE §9; do not reach for `CursorPagination` on a mixed list.
  - **A bare `created_at < t OR (created_at = t AND id < x)` is not an index condition** (found by the design review, pinned by a test that reads the SQL): each side carries a redundant `created_at <= t`, which makes the post side an ordered scan of `posts_recent_idx` at any depth. Without it a deep page scans from the newest post.
  - **The reposts side is a sequential scan and a top-N sort** (`EXPLAIN`, rolled-back transaction, 300,000 reposts, 200 follows): about 11 to 18 ms, and a variant with a separate `IN`-subquery branch plus a "my reposts" branch took about the same, so it was not built. If it ever bites (Part 16), the lever is a bounded per-followed-user read, not another index. The bookmark page is an index nested loop (0.07 ms at 5,000 bookmarks).
  - **The cursor token carries the time as an integer of microseconds** (`isoformat()` drops `.000000` and offsets vary), is decoded strictly (exactly four parts, canonical UUIDs, a post item has the zero reposter, re-encoding must reproduce the token) and every failure is a 404. Python's `UUID` order, Postgres `uuid` order and lowercase-hex string order agree, so the key filters built in Python match the database.
  - **The once-per-page rule has a proof-sized window:** read `2 × size + 1` rows, keep the first row of each post up to `size`, consume the hidden rows; the first row is always kept, so every page advances (60 reposts of one post in a row give a one-item page). The brute-force test compares real walks with a reference written independently of `take_page` (150 seeded walks, ties everywhere, with and without changes between pages).
  - **Hydration decides the query count:** an empty `__in` or pair list makes no query, so a page of only posts costs one query less than a page with a repost (Following 3 / 2 against 4 / 3; profile 3 / 4). Constant-query tests must seed both kinds. Reposts are re-read as `Q(user_id=…, post_id=…)` pairs (the unique index), not `user_id__in × post_id__in` (up to size² rows), and matched on the pair **and** `created_at`.
  - **`select_for_update(no_key=True, of=("self",))` is the right lock for a repost:** it serialises with status writes and with other reposts of the post but not with the `FOR KEY SHARE` locks that likes, comments and bookmark inserts take on a busy post. A test holds a plain `FOR UPDATE` in another transaction and shows the repost waits and records the status at commit.
  - **Two mutation survivors were equivalent or dead code, not missing tests:** `get_or_create` in `services.repost` is redundant next to the row lock plus the existing-repost check (mutating both together is caught by the race test), and `has_module_permission` on `BookmarkAdmin` was redundant because Django leaves a model with no view/add/change/delete permission off the admin index (`get_model_perms`), so it was removed.
  - **Bookmarks and likes have equal rates (300/h), so a wrong `throttle_scope` is invisible to a single-bucket test:** `test_bookmarks_have_their_own_allowance_not_the_like_one` uses up one and does the other.
  - **The repost refusals count against the allowance** (a 409 passes the throttle first); a 401 or 403 never does (permissions run before throttles).
- **Evidence:** Part 7B plan and implementation; `test_timeline.py`, `test_timeline_db.py`, `test_api_feed_reposts.py`; 38 backend mutation checks (every one caught after the two fixes above); the `EXPLAIN` runs in HANDOFF.

### 2026-10-10 — Frontend and E2E facts from Part 7B

- **Applies to:** every list that mixes kinds of item, every icon-plus-word button, and E2E tests that need a third person.
- **Facts:**
  - **The visible word must be inside the button's accessible name** (label-in-name): the post page shows "Repost" beside the glyph and the name is "Repost 3" ("Reposts" would not be contained in it). Same for "Like" and "Comments".
  - **A disabled (`aria-disabled`) button has no `aria-pressed`** by design (only the working states carry it), so an E2E test of a refusal asserts the title, the toast and that a reload still shows the old count, not `aria-pressed="false"`.
  - **`visibleItems` is the one place that decides what a list shows:** a post item the poll found deleted is dropped, and a post that already appeared higher up is shown once (a later repeat as the original, as a second repost, or as a stub). It runs before rendering, so the keys stay `feedItemKey` (`repost:<reposter>:<post>`); an empty result with `hasMore` shows Load more, not the empty state (a cached Following page can come back empty with a next cursor).
  - **A repost is rendered from the original's `Post`:** `FeedCard` applies the polled status to it, so a repost of a pending fact turns VERIFIED by itself (`pendingPostIds` includes originals of reposts, each id once); a repost whose original is polled `removed`, found `gone` or sent as `{id, unavailable}` becomes `UnavailablePostCard`.
  - **Hint ids come from `useId`:** a module constant (`like-hint`) repeated in every unverified card of a feed; the repost button's hint is per button, and `LikeButton` was fixed the same way (`FollowButton` still has the constant: follow-up).
  - **E2E for "a third person's post" needs no sign-up:** `seedPost()` in `e2e/helpers.ts` runs `manage.py shell` to create a verified user and a post (a fact starts `pending`, so `setPostState` can flip it to `verified_true`, `verified_false` or `removed`). The suite is still at 16 of allauth's 20 sign-ups a minute.
  - **Playwright's `getByRole("article").filter({ hasText })` is the safe way to find a card;** a repost card's text includes "Reposted by", so filter on the original's marker text, and match the stub with "This post is no longer available".
  - The scripted browser check (headless Chromium, 1280 and 390 px) found nothing the unit tests missed this time; the screenshots are the evidence for the layout (a repost's header line, the right-aligned bookmark, the dimmed disabled repost).
- **Evidence:** Part 7B implementation (`RepostButton.tsx`, `FeedList.tsx`, `feed-items.ts`, `e2e/social.spec.ts`); 31 frontend mutation checks (one survivor, the zero clamp, now tested).


### 2026-10-10 — Backend facts from Part 8 (reports, the threshold, `apps/pipeline`)

- **Applies to:** Parts 9, 10, 11, 11B, 11C, 13, 14, 16, and every DRF or Django upgrade.
- **Facts (read in the installed source, measured, or pinned by `apps/reports/tests/` and `apps/pipeline/tests/`):**
  - **`apps/pipeline` exists from Part 8** (made with `startapp`; only `routing.py` so far, no models or migrations). `posts.services` imports `routing`; `routing` imports only `posts.models`, so there is no cycle. `is_active_emergency` stays in `apps/posts/emergency.py` (the serializer reads it) and Part 11C's routing imports it. Part 9 added `contract.py`, `clients.py`, `processor.py`, the management command and `apply_pipeline_result`/`apply_pipeline_failure`; it never holds the post row lock across the pipeline call (claim, call, apply).
  - **The lock is `FOR NO KEY UPDATE` on the post, taken before anything else** (`reports.services.file_report`): it serialises reports with each other and with status writes, not with the `FOR KEY SHARE` of like, comment and bookmark inserts (a test shows a like isn't blocked). The duplicate check (`exists()` after the lock) is race-free, so there is no `IntegrityError` catch (it would be dead code, as `get_or_create` was in 7B). Postgres re-evaluates the locking query's WHERE after a wait, so a report that waited for a delete or removal gets no row (404, no report written).
  - **The window count has no upper bound** (`created_at >= now - window` only): `now` is taken before the lock wait, so a report that waited can carry a `now` older than a row that has committed since, and that row must still count (a test places one in the future).
  - **Foreign keys are `DEFERRABLE INITIALLY DEFERRED`** (`sqlmigrate reports 0001`): the `KEY SHARE` lock on the reporter's `users` row is taken at COMMIT, after the post lock. Keep the order post first, then users (sorted) in Part 11B's services.
  - **The lock race test** (`apps/reports/tests/test_races.py`): a holder takes `NO KEY UPDATE` on the post, three counting reports are already committed (threshold 5) and two reports wait behind it; after the release the post must be under review with `report_count == 5`. Without the service's lock both would count four and each would write `report_count = 4`, so removing the lock fails it every time. `run_together` asserts that no thread raised, so each task returns a marker for the domain errors.
  - **`reports_resolution_consistent`:** `open` exactly while `resolved_at` is null. Part 10's Dismiss and the moderator actions must set `resolved_at` (and `resolved_by`) with `status` in one write, or the database refuses it. **Done in Part 10:** `reports.services.resolve_open_reports` is the one `UPDATE`.
  - **`report_count` is a lifetime counter**: deleting a reporter cascades their rows but not the count or the post's review state; Part 14 must not decrement it.
  - **`record_report` returns True only when the post entered review** (a pipeline-to-both merge is not entering); Part 13 notifies the author from there, in the same transaction. `file_report` returns the `Report`.
  - ~~A decisive late pipeline FALSE on a reported post sets `pre_review_status = verified_false`…~~ **Resolved in Part 9** (user decision 2026-10-11): a late decisive FALSE makes the reason `both` and stores no label, so the repost refusal can't reveal it (ANALYSIS c-41).
  - ~~Part 9's processor selects `status='pending'` only…~~ **Resolved in Part 9:** the queue also takes `under_review` + `flagged_reason='reports'` + `pre_review_status='pending'` (not "no `pipeline_checked_at`", which would re-select a post the pipeline gave up on forever; see the Part 9 entry).
  - **Test gotchas:** a fresh `UserFactory` account is 0 h old, so its report doesn't count unless the test ages it (`aged_user(now=…)`) or gives it content; the settings seed comes from the developer's `.env`, so `report_settings` pins threshold, window and minimum age and **saves** the row (autouse in `apps/reports/tests`); seeding report rows through the factory must also set `Post.report_count`; building an `auth_client` inside a `django_assert_num_queries` block counts the token-minting queries (6 instead of 2: build it first).
- **Evidence:** Part 8 plan and implementation; 46 backend mutation checks (every one caught).

### 2026-10-10 — Frontend and E2E facts from Part 8

- **Applies to:** every button that hides on "your own post", every modal with a locked form, and E2E tests that seed other people's activity.
- **Facts:**
  - **A server field error arrives while the form is still locked**, so `focus()` in the `catch` does nothing (the Part 7 trap again, now for a modal): `ReportModal` stores the target in a ref and an effect on `sending` focuses it once the fieldset is enabled.
  - **`Modal` returns focus only from the dialog's `close` event**, so a modal that is unmounted on close loses it: `ReportButton` builds the modal on the first click and keeps it, and the flag stays **one `<button>`** across "Report" and "You reported this" (a test pins the identity and the focus).
  - **The test session's user is `u-1`, which is also `makePost`'s default author**, so a button that hides on `user.id === post.author.id` disappears in any test that doesn't give the post another author (`BO` from `features/posts/test-helpers`). While the session is loading `user` is null: only the server's `is_mine` can hide the button then.
  - **Playwright's `getByRole(…, { name: "Report" })` matches a substring case-insensitively**: it also matches "You reported this", and `/report/i` matches a claim whose marker text contains "report". Keep that word out of E2E markers and use `exact: true` where both states can exist.
  - **`seedReports(postId)`** (`e2e/helpers.ts`) files `threshold − 1` reports by aged seeded users through `reports.services.file_report` in `manage.py shell`, reading the threshold and minimum age from the platform settings (the E2E backend uses the developer's seed). No sign-up is used (the suite is still at 16 of allauth's 20 a minute). A fresh test account's own report counts only if it has taken part, so the test posts an opinion first.
  - A card renders the flag for every post that isn't yours, so a feed shows up to 20 closed flags and **no** dialogs until one is clicked.
- **Evidence:** Part 8 implementation (`ReportModal.tsx`, `ReportButton.tsx`, `e2e/social.spec.ts`); frontend mutation checks (see HANDOFF).

### 2026-10-11 — Backend facts from Part 9 (the pipeline queue, the kick, the tick)

- **Applies to:** Parts 10, 11, 11B, 11C, 13, 16, 17, and any change to `apps/pipeline` or `posts.services`.
- **Facts (read in the installed source, measured, or pinned by `apps/pipeline/tests/` and `apps/posts/tests/test_services_pipeline.py`):**
  - **The queue predicate is one rule in two forms:** `routing.awaiting_check_q()` (the queue) and `routing.is_awaiting_check(post)` (the apply guard) must stay identical; `test_queue.py` compares them over every state the database checks allow (bulk-created). A change to one without the other either loops a post forever or lets a stale answer overwrite a finished check.
  - **The claim token is `pipeline_attempts`:** the claim adds 1 and the apply drops the answer if the row's count moved (a lease ran out and a newer claim took the post). Moderator actions (Part 10) and Restore (Part 11) must not touch `pipeline_attempts`, or an in-flight answer is dropped. A Restore to `pending` puts the post back in the queue with its count; one already at 5 is given up again at once (Part 11 decides whether Restore resets it).
  - **`transaction.atomic(durable=True)`** guards the claim and both writes: called inside any caller's transaction they raise `RuntimeError`. pytest-django's `db` test transaction is exempt (Django marks test-case atomics `_from_testcase`), but a test's own `transaction.atomic()` is not, which is how the durability tests work. In a `db` test the claim's row lock lasts until the test ends (a savepoint release keeps row locks), so every test with a second thread must be `transaction=True`.
  - **An exception escaping an `on_commit` callback after the commit becomes the request's 500** (no `ATOMIC_REQUESTS`; `create_post`'s own `atomic()` is the outermost block), so the kick's callback catches everything (`posts.services._kick_pipeline`). `on_commit(robust=True)` with a `functools.partial` would log `func.__qualname__`, which a partial lacks: use a closure.
  - **The Django management commands and `manage.py shell` print the app's INFO logs to stdout** (the root logger is INFO on stdout), so `process_pending` shows one `Pipeline: post <id> -> <outcome>` line per post before its summary; a shell snippet that needs one value uses `| tail -1`.
  - **Local databases collect pending facts from E2E runs** (the E2E backend never checks posts by itself), so the first `process_pending` on a developer's machine may report dozens of posts.
  - **Sentry:** with the default integrations (`LoggingIntegration`, `ThreadingIntegration`), `logger.error` in the kick thread is a Sentry event; the processor logs ERROR only when it gives up on a post.
- **Evidence:** Part 9 plan (with its pre-approval design review) and implementation; 36 backend mutation checks, every one caught.

### 2026-10-11 — E2E facts from Part 9

- **Applies to:** every E2E test that makes a fact post or needs a verdict (Parts 10, 11, 11C, 13).
- **Facts:**
  - **The E2E backend runs with `PIPELINE_INLINE_KICK=False` and `PIPELINE_BACKEND=stub`** (`playwright.config.ts`, and `shellEnv` in `e2e/helpers.ts`): three tests expect a new fact to stay CHECKING FACTS… after a reload or in a second tab. A `runserver` reused for E2E must be started the same way, or those tests fail.
  - **To get a real verdict, run the pipeline for one post only:** `processPost(id)` (`process_post` through `manage.py shell`). A sweep (`process_pending`, the tick) would also check the pending posts of tests running in parallel (and of earlier runs). It returns the status and the developer's `confidence_threshold` (the E2E backend reads the developer's own PlatformSettings; the stub gives `#true` 95).
  - A composer post's card shows CHECKING FACTS… until Part 5's first poll (10 s), even when the verdict exists a few milliseconds after the commit: wait up to 30 s for the badge.
- **Evidence:** Part 9 implementation (`e2e/post-detail.spec.ts`, the converted live-badge test); the suite in dev and CI mode.

### 2026-10-12 — Backend facts from Part 10 (Django Admin as the moderation panel)

- **Applies to:** Parts 11, 11B, 11C, 13, 14, 14B, 16, and every Django upgrade.
- **Facts (read in Django 5.2.17's admin source, then pinned by `apps/moderation/tests/` and `apps/accounts/tests/test_admin_roles.py`):**
  - **Django admin's own checks are weaker than the rules we need:** `get_deleted_objects` puts a model in `perms_needed` when the user lacks delete permission on it, so a user who has posts can never be deleted while `PostAdmin` is read-only (our `UserAdmin.get_deleted_objects` returns a summary and asks for no permission on the cascade); `delete_selected` only calls `has_delete_permission(request)` with no object, so it must be removed for non-superusers; `user_change_password` checks only change permission; a read-only `password` field prints the hash (seniors' `get_fieldsets` drops it); `history_view` needs only view permission (`HistoryNeedsLog`); `LogEntry.user` is `CASCADE`, so deleting an account erases the log entries it wrote (such an account is protected: suspend it instead).
  - **An action's queryset is the filtered changelist** (`cl.get_queryset`), and `select_across=1` makes `response_action` ignore the posted ids and re-run the whole filtered queryset: the confirmation page posts the evaluated, capped ids, and the apply step re-filters by them. `response_action` also does `queryset.filter(pk__in=<raw strings>)`, so one malformed id is a `ValidationError` 500: `PostAdmin.response_action` drops non-UUIDs first. Actions run outside any transaction (each service opens its own `atomic()` per post).
  - **A button for an action can't sit inside the page's `<form id="post_form">`** (nested forms are dropped): it goes in `{% block object-tools-items %}`, which Django renders before that form. `{% change_form_object_tools %}` renders with the whole context, so `templates/admin/change_form_object_tools.html` can test `perms`.
  - **`PostAdmin.has_change_permission` must stay False even though moderators hold `posts.change_post`** (it gates the actions): otherwise the page grows a Save that writes the whole row outside the services.
  - **A data migration that grants permissions must create the permission rows itself** (on a fresh database `post_migrate` hasn't run): `create_permissions(app_config, apps=apps)` with `app_config.models_module = True` (`AppConfigStub` has no such attribute: read it with `getattr`) and restore it. It carries its own frozen lists and depends on the latest migration of every app it names; `roles.py` holds the live lists and `test_roles.py` fails when they differ.
  - **A `transaction=True` test flushes the groups' permissions** (`post_migrate` re-creates the permission rows, not the assignments): tests that depend on them use the root `role_groups` fixture. pytest-django runs ordinary `db` tests first, so the test database's groups are the migration's own until a flush.
  - **A moderator's `created_at` must be taken after the row lock is held** (`services._perform`): with `now` taken before a lock wait, two actions at once wrote rows whose timestamps ran backwards (the race test `test_two_different_actions_at_once…` caught it).
  - **A Dismiss or Remove needs a `pre_review_status` the post could return to** (`published` for an opinion; `pending`, `verified_true` or `verified_false` for a fact), or a database check fails in the middle of a batch: `rules.refusal` says `no_prior_status`. Factories build under-review posts without it, so the rules tests cover `None` and every status.
  - **`posts.review_started_at` is set exactly while a post is under review** (`posts_post_review_started_consistent`): any code or test that saves `status='under_review'` needs it (`PostFactory` fills it; a `bulk_create` or `.update()` must too), and anything that leaves review must clear it. Moderators and Restore (Part 11) must not touch `pipeline_attempts` (Part 9's claim token).
  - **Test helpers that set a field don't let the caller override it** (`pipeline.tests.conftest.reported_fact` fixes `flagged_reason`; `under_review()` in the race tests fixes `status`): build the post with `fact(...)`/`PostFactory(...)` when a test needs another value.
  - **A `list_display` name that is also a reverse relation is found first as a field** (`opts.get_field` includes reverse relations): a column method called `reports` was shown and sorted as the relation `Post.reports`, so `o=<column>` silently did nothing. The column is `report_total`. The changelist's `o` parameter counts columns from 0 with `action_checkbox` as column 0, and `ModelAdmin.get_list_display` doesn't include it.
  - `startapp` writes `name = "moderation"` and a `tests.py` and `views.py`: fix `apps.py` to `apps.moderation` and delete the two files (a `tests/` package replaces `tests.py`).
- **Evidence:** Part 10 plan (with its pre-approval design review) and implementation; 47 backend mutation checks, every one caught (one was equivalent dead code, removed: the lock query's `.not_deleted()`).

### 2026-10-13 — Backend facts from Part 11 (appeals, Restore, the queue's removed posts)

- **Applies to:** Parts 11B, 11C, 13, 14, 16, and every Django or DRF upgrade.
- **Facts (read in the installed source or pinned by `apps/moderation/tests/`):**
  - **One appeal per post for life is a `OneToOneField`** (a unique `ForeignKey` is Django warning W342); the reverse accessor is `post.appeal`, and reading it for a post with none raises `RelatedObjectDoesNotExist`, **which is an `AttributeError`**, so `getattr(post, "appeal", None)` is the idiom (the admin's `open_appeal_of`). With `list_select_related = ("author", "appeal")` the changelist stays a constant number of queries.
  - **The rules take the open appeal as a required keyword** (`refusal(act, post, moderator, *, appeal)`, `transition(…, appeal=…)`): with a default, a call site that forgets it would silently hide Restore and skip the original-moderator rule. Whether an action resolves an appeal comes from the `appeal` passed, never from `flagged_reason == "appeal"` (a flagged post with no row, from a factory or a test, must not crash). The caller finds the appeal (`services.open_appeal`, `admin.open_appeal_of`); the pure module never queries.
  - **A removed post with an open appeal has `review_started_at` null** (Part 10's check: set exactly while under review), so the queue's "in the queue since" is an expression, `Case(When(status=removed, appeal__status=open, then=F("appeal__created_at")), default=F("review_started_at"))`. Used as the `ordering` **expression** (not an `F`) it skips admin check E033 (`_check_ordering_item` reduces an `F` to a field name and looks it up), and `admin.display(ordering=<expression>)` makes the column sortable. The changelist's `o=` still counts the checkbox as column 0 (the Waiting column is 7).
  - **`original_moderator` of a label appeal is the moderator of the latest `marked_false` row, and only when `verdict_source=moderator`:** `post.moderated_by` is whoever *last touched* the post (a Dismiss of reports on the FALSE post would make the dismisser the labeller), and a pipeline FALSE has no one to avoid. A test with an old `marked_false` row on a pipeline-FALSE post pins it.
  - **The appeal row lock in `_perform` was dead code:** every writer of an appeal (`file_appeal`, `_perform`) takes the post's `FOR NO KEY UPDATE` first, so the mutation "no appeal lock" survived the whole suite; it was removed (as Part 10's `.not_deleted()`). The post lock is what serialises two Restores, a Restore and a Keep removed, and an appeal against a Mark FALSE (`test_races.py`, run 10 times in a row).
  - **A DRF view with `throttle_scope` throttles every method**, because `APIView.initial` runs before the handler is looked up: a `GET` on a POST-only view would use up the allowance and then answer 405. `AppealView.get_throttles()` returns the throttle for POST only (a test makes 8 GETs, then an appeal).
  - **The 201 of an appeal is re-read with `Post.objects.not_deleted().for_list(user)`, not `visible()`**, which drops the removed post a removal appeal is about.
  - **`for_list` now chains two annotation helpers** (`with_engagement`, `moderation.queries.with_appeal_fields`), so `PostSerializer` reads five more attributes strictly; a test that serializes a bare post must call `appeal_defaults(engagement_defaults(post))`. The removal reason is a `Case(When(author=viewer, status=removed, then=Coalesce(Subquery(latest removed row's public_note), "")))`: Postgres runs the subquery only for such a row. List query counts did not change (tests seed appeals and removal rows on 20 posts).
  - **A restore of a `pending` fact the pipeline already checked** (`pipeline_checked_at` set or `pipeline_attempts ≥ MAX_ATTEMPTS`, `routing.pipeline_had_its_say`) goes to `under_review` for the pipeline through `routing.enter_review` (so the clock starts), not back to `pending` (which would check it twice). A restore to `pending` is kicked after the commit through `posts.services.kick_pipeline_after_commit`, only for the `restored` kind (Dismiss back to `pending` was never kicked and still isn't).
  - **Test traps:** the pipeline test helper `claimed()` writes `review_started_at` and so is only valid for a post under review (a pending fact needs `pipeline_attempts` and `pipeline_next_attempt_at` set directly); `AppealFactory(removal=True)` makes the removed post, and a trait can't be combined with `post__…` overrides that contradict it; `test_races.py` threads need `transaction=True` and `run_together` asserts no thread raised, so each task returns a marker for the domain errors.
- **Evidence:** Part 11 plan (with its pre-approval design review) and implementation; the backend mutation checks (see HANDOFF).

### 2026-10-13 — Frontend and E2E facts from Part 11

- **Applies to:** every part that adds a button to a card or the post page (11B to 14), and every E2E test that needs a logged-in author without a sign-up.
- **Facts:**
  - **`Tombstone` is its own file with no `"use client"`**, imported by both `PostCard` (whose guard renders it for any removed post, so no caller can show a removed post's words or action bar) and `RemovedPostCard` (a client component: the author variant holds the appeal state). `RemovedPostCard` keeps the post a request returned (`filed`) and shows it while the server's copy still says `appeal_status: null`, because `FeedCard` builds a new post object on every poll from the old data (`can_appeal` still true); once the server's copy knows the status it wins.
  - **`AppealButton` calls `useAuth()` before it can decide to render nothing**, so any tree that can reach it needs the `AuthProvider` (the `/dev/ui` gallery has none: its author-variant examples use `can_appeal: false`, which is also why `RemovedPostCard` renders the button only when `can_appeal` is true).
  - **The detail page renders `AppealOutcome` beside `VerdictBlock`, not inside it:** a published opinion's block is one neutral line, so a restored opinion's outcome would never show. A removed post has its own branch in `PostDetail` (`RemovedPostCard layout="page"` with the author row and Delete in its footer, then `SourceList` and `DeletePostModal`); it has no action bar, verdict or discussion.
  - **`getByRole("textbox")` on the post page matches the comment box too**: name the appeal's box ("Why should we look again?"). A badge's visible text starts with its glyph name (`cancel FALSE 90%`), so an E2E `getByText(/^FALSE/)` finds nothing: match the whole label (`"FALSE 90%"`, `"VERIFIED · REVIEWED"`).
  - **E2E without a sign-up:** `seedAuthor()` (`e2e/helpers.ts`) makes a verified user with the shared password and the verified `EmailAddress` row `create_superuser` also makes, and `logIn(page, account)` uses the real form (Turnstile guards sign-up only; log-in is 30 a minute per IP). `moderate(postId, action, reason)` creates a **fresh moderator on every call** and runs the service, so the different-moderator rule never trips between two decisions in one test. The suite is still at 16 of allauth's 20 sign-ups a minute.
- **Evidence:** Part 11 implementation (`RemovedPostCard.tsx`, `Tombstone.tsx`, `features/appeals/`, `e2e/appeals.spec.ts`); the frontend mutation checks (see HANDOFF).

### 2026-10-13 — A mutation harness rewrites source files in place: nothing else may run meanwhile

- **Applies to:** every part that runs mutation checks (a script that edits a module, runs tests, and restores it).
- **Fact:** while Part 11's backend harness ran (about 18 minutes), three things went wrong that looked like product bugs: (1) a dev server started during it imported a **mutated** `views.py` and kept it, so removal appeals answered 500 until the server was restarted (the traceback prints the *current* file's line, which made the code look right); (2) a second `pytest` on the same `test_rumor_zero` database deadlocked with the harness's and "errored" 2,962 tests; (3) an edit to `services.py` made while a mutation of that file was applied was overwritten when the harness restored its copy. The harness also runs `pytest -x` per mutation, so a background `pytest` loop that outlives its caller (`kill` it) keeps the test database open: terminate its sessions and `drop database test_rumor_zero` before the next run.
- **Consequence:** while a harness runs, edit nothing it touches, start no server, and run no other pytest. Check `ps aux | grep -E 'mutate|pytest'` before trusting a surprising failure. A mutation pattern written before `ruff format` or `prettier` can silently stop matching (the harness prints `NOT-APPLIED`): re-read the formatted line. Re-run the survivors alone afterwards.
- **Evidence:** Part 11 verification (the 500 reproduced only against the long-running server, never with `APIClient`; restarting it fixed it).

### 2026-10-14 — Backend facts from Part 11B (the credibility ledger and its locks)

- **Applies to:** Parts 11C, 11D, 12, 13, 14, 16, and any code that changes a post's status or a user row.
- **Facts (measured or pinned by `apps/reputation/tests/`):**
  - **Lock order:** the post first (`FOR NO KEY UPDATE`, the caller's), then every affected user **sorted by id with `FOR NO KEY UPDATE`**, never a plain `FOR UPDATE`: the foreign keys are deferred, so a moderator's audit row and `moderated_by` take `KEY SHARE` on users' rows **at commit**; with a plain `FOR UPDATE`, two moderators deciding each other's posts at once deadlocked (Postgres "deadlock detected", `test_races.py` shows it). Never lock a user and then a post (Part 14's account deletion must keep this); one `settle_post` per transaction; 11C's `emergency_blocked_until` write must happen inside or after `settle_post`'s user locks.
  - **Postgres refuses an aggregate with `FOR UPDATE`**, so the users' lock and the totals (`Sum`, `Count`, `Max`) are two queries; the totals and the reporter cap are read **after** the lock (two decisions at once would otherwise both see room for one more credit).
  - **Every status change to `verified_*` or `removed`, and every one out of `removed`, must settle the post.** Today that is `moderation.services._perform` (every action but Escalate) and `posts.services.record_pipeline_result` (`labelled` only). `record_report`, `file_appeal`, a pipeline failure and `delete_post` move a post only into or within states that change nothing (a review freezes the score), so they don't. A new status writer in 11C must call `settle_post`, or `pending_changes(post)` is non-empty (the sequence tests check it after every step).
  - **A full `User.save()` writes every loaded field except `reputation_score` and `reputation_sample`** (allauth's `set_password`, `account/utils.py` and the admin form save whole rows and would write back a score read earlier). An explicit `update_fields` is still taken at its word, and `.update()` and `bulk_update` are untouched: tests set scores with those, never with `user.reputation_score = …; user.save()` (silently not written).
  - **The reverse one-to-one `reversed_by` raises when there is none, even under `select_related`**: "is this row reversed?" is the `Exists` annotation `reputation.serializers.is_reversed()`; a filter `reversed_by__isnull=True` (a LEFT JOIN, at most one match because `reverses` is unique) is fine in querysets and aggregates.
  - **Times are strictly increasing per person** (`max(now, last + 1 µs)`), so a writer that waited for a lock can stamp a row a little after its own `now`. The reporter cap's window uses the caller's `now`.
  - **`migrate reputation zero` drops the ledger but leaves `users.reputation_*` as they were**: after re-applying, run `python manage.py recompute_reputation` (the dev database had no rows when Part 11B rolled it back).
  - **E2E and manual shortcuts that write `Post.status` directly** (`setPostState` in `e2e/helpers.ts`, a shell `.update()`) bypass the ledger: a test about credibility must go through `processPost` / `seedCheckedFacts` or `moderate()`.
  - **Test traps:** a `TabularInline` prints each row's `str()` as well as its columns (count `<p>Label</p>`, not the label), and the appeal inline has a `kind` column too; `.first()` on an unordered queryset of uuid rows picks one at random (a flaky test until it filtered on `reverses__kind`); a mutation suite that runs only fast test files can miss what only the sequence tests catch (two survivors, now pinned by direct service tests).
- **Evidence:** Part 11B plan and implementation; 42 backend mutation checks (41 caught; the 42nd, settling on `updated_review`, is equivalent because `settle_post` reads the public status), the threaded tests 10 runs in a row.

### 2026-10-20 — Backend facts from Part 11C (emergency posts, the block, the pinned lists)

- **Applies to:** Parts 13, 14, 14B, 16, 17, and any race test or admin change on accounts.
- **Facts (measured or pinned by `apps/moderation/tests/` and `apps/posts/tests/`):**
  - **`users.emergency_blocked_until` is derived:** it always equals `rules.standing_block_end` of the account's `emergency_blocked` / `emergency_unblocked` rows, recomputed under the account's `FOR NO KEY UPDATE` lock by `moderation.services` only (`.update()`; a full `User.save()` skips it, like the score). The rows are **strictly increasing per account** (`max(now, last + 1 µs)`): without it, an Unblock that committed first with a later time than a waiting Mark FALSE made the new block read as lifted (`test_races_emergency.py` shows the race with the rule switched off). Part 14's account deletion nulls the rows' `subject_user` and `post`; Part 14B's avatar rows use `subject_user` too, and `standing_block_end` only reads the two block kinds.
  - **Forcing an interleaving in a race test:** hold a row lock in the test thread, start the other transaction in a thread, poll `SELECT count(*) FROM pg_locks WHERE NOT granted` until it waits, then commit what must come first (`wait_until_someone_waits_for_a_lock` in `test_races_emergency.py`). Deterministic, unlike barriers.
  - **An inline on `UserAdmin` breaks the account form's POST** for anyone who can change it: Django validates every inline formset's management form, even a read-only inline's, so a plain form POST (the existing admin tests, a script) gets a 200 with errors. The block history is a read-only *field* (`emergency_blocks`, shown only with the permission) instead.
  - **A view-only changelist still offers custom-permission actions:** moderators (only `accounts.view_user`) see and run Block / Unblock on the account list; `verify_email` (needs change) stays hidden.
  - **The root conftest is importable as module `conftest`** (pytest's default prepend import mode puts `backend/` on the path): the app conftests import `pin_emergency_settings`, which pins the six emergency settings only for tests that use the database (`django_db` marker or the `db`/`transactional_db` fixture), so pure test modules stay pure.
  - **The random walks' coverage is fragile to the walk's shape:** a fifth post and a Block step made `repost_false` (a plain fact reposted while undecided, then labelled FALSE) rare; `COVERAGE_SEEDS` went from 12 to 32. Longer walks didn't help (posts settle early). Re-check it whenever a walk gains posts or steps.
  - **A Restore inside the 24 hours re-pins an emergency** (Remove doesn't demote, and "active" is computed): intended (user-approved default), and the pinned lists and the processor follow it with no code.
  - **The machine can reboot mid-session:** Postgres and Redis then come back stopped, and every DB test errors at setup with "connection refused" (not a failure of the code); `docker compose up -d` brings them back with the data.
- **Evidence:** Part 11C plan and implementation; 52 backend mutation checks, all caught; the threaded tests 10 runs in a row.

### 2026-10-20 — Frontend, E2E and tooling facts from Part 11C

- **Applies to:** every part with a sessionStorage/localStorage convenience, an E2E text match, a switch, or servers started from Claude's background Bash.
- **Facts:**
  - **Storage that renders must go through `useSyncExternalStore`** with a `null` server snapshot (no hydration mismatch, no ref read or `setState` in an effect, the React 19 lint rules), a module-level listener set (same-tab writes fire no `storage` event), try/catch on every access and an in-memory fallback (`pinned-collapse.ts`). Write only on a click: `auth.spec.ts` checks storage is empty.
  - **`useStatusPolling` treats an id missing from the answer as deleted** (`gone`): a test mock must return every polled id that is still pending, or that card vanishes.
  - **Playwright's `getByText("EMERGENCY")` is a case-insensitive substring match:** it also finds a claim containing "emergency" and the note "Posted as an emergency…". Keep the word out of E2E markers; the switch is a visually hidden input, so use `check({ force: true })`.
  - **An E2E test that makes a lasting effect must start its cleanup as soon as the effect exists:** a failure before the `try` left a pinned emergency in the developer's Recent feed (demoted by hand). The spec now takes the post id first and demotes in `finally`, ignoring a refusal.
  - **A background `cd dir && npx next dev` can run in the wrong directory:** it fetched a stray `next@16.4.2` into the npx cache and ran from `backend/` ("Couldn't find any pages or app directory"; nothing was written). Start it as `bash -c 'cd …/frontend && exec ./node_modules/.bin/next dev -p 3000'`.
  - **A frontend can ship before its backend** (Workers and Render deploy separately): the composer reads `quota.emergency?.allowed`, so an older answer without the block reads as "not allowed" instead of crashing the render.
- **Evidence:** Part 11C implementation; 30 frontend mutation checks (two survivors became tests: a reopened allowance must not bring the toggle back on, and a 403 turns it off even when the refreshed allowance still says yes); E2E 43 in dev and CI mode.

### 2026-10-20 — Backend and frontend facts from Part 11D (stats, trend, charts)

- **Applies to:** Parts 12, 14, 16 (any grouped count by day, any chart, any E2E or guide step that reads a text alternative).
- **Facts (measured, then pinned by tests):**
  - **A `UNION ALL` of three `values_list(Value("likes", output_field=CharField()), "day", "n")` querysets works in Django 5.2 with psycopg** with no cast on the label: the stats endpoint is 2 queries (the post, then the union) whatever the activity. `TruncDate("created_at", tzinfo=UTC)` groups by UTC day regardless of `TIME_ZONE`, and `.distinct("day")` after `.order_by("day", "-created_at")` is the "last row of each day" (an annotation name is accepted by `distinct`).
  - **`get_platform_settings()` is cached for 60 s per process, so a cold read is one more query:** a test that pins a query count must call it once first (the stats test does).
  - **A like or repost taken back is a hard delete**, so a daily bucket only ever shows surviving rows; comments use `shown_comments()` (the partial index's predicate).
  - **A moderator verdict's time is not `moderated_at`** (every Demote, Dismiss and Escalate overwrites it): read the latest `verified`/`marked_false` audit row whose `to_status` equals the post's current status (`moderation/queries.with_verdict_time`).
  - **Children of `role="img"` are presentational:** a chart's hidden `<table>` must be a **sibling** of the image element, inside a `figure`. That table repeats every number and its caption, so a Playwright or testing-library `getByText` (case-insensitive substring, strict mode) finds two elements: match the visible one with a selector (`p`) or `exact: true`.
  - **`a ?? default` swallows an intended `null` in a test helper** (`props.publicScore ?? 62` made "hidden" impossible to test): use `"key" in props`.
  - **The dev server's inline kick checks a new fact within about 0.03 s**, so a guide or E2E step can't show a fact "still being checked" from a normal post (use an opinion, `#unsure` for review, or leave the kick off as the E2E backend does).
  - **A mutation script's list must include every test file that can catch the mutation** (`posts-api.test.ts` was missing from the frontend list and "stats sends the token" looked like a survivor).
- **Evidence:** Part 11D plan and implementation; 27 backend and 43 frontend mutation checks, all caught.


### 2026-10-20 — Backend, frontend and tooling facts from Part 12 (search)

- **Applies to:** Parts 14, 16, 17, and anything that adds a generated column, a ranked list, an `or` query or a prop-changing test.
- **Facts (measured, then pinned by tests):**
  - **`GeneratedField(SearchVector("content", config="english"), db_persist=True)` works as written:** `sqlmigrate` shows `GENERATED ALWAYS AS (to_tsvector('english'::regconfig, COALESCE("content", ''))) STORED`, `makemigrations --check` stays clean, `migrate posts 0002` and a re-apply work, `bulk_create` and `create` read it back through `RETURNING`, and an `UPDATE … SET search_vector` is refused by Postgres. `PostQuerySet.for_list` defers it, so no list pulls a tsvector per post. A stored generated column **rewrites the table** and the GIN build blocks writes: fine before launch, so Part 17's `migrate` runs it once.
  - **Rank with `F("search_vector")`, never the string:** `SearchRank("search_vector", q)` wraps the string in `SearchVector` and re-parses the stored vector's text with the default configuration. A guard test asserts `to_tsvector(COALESCE(` is **not** in the SQL and `@@` is.
  - **The planner picks `posts_search_idx` only on a big enough table:** with 200 rows it chose the partial Recent index even with `enable_seqscan = off`; with 3,000 rows the EXPLAIN test passes; at 10,000 rows and no setting changed it still chose a sequential scan; at **100,000 rows it chose the GIN index (bitmap scan, about 4 ms for a rare two-word query)**. A test that asserts an index in a plan needs a table of a few thousand rows, an `ANALYZE` and (in a rolled-back transaction) `SET LOCAL enable_seqscan = off`.
  - **Websearch `or` binds looser than the implicit "and":** `tag walking or bridge` is `(tag & walking) | bridge`. A guide step or test that scopes a search with a marker word must put the marker on both sides. A query with no positive term (`-foo`, `or`) is `!'foo'`, which walks the whole GIN index and matches nearly every post, so the view answers an empty 200 without a query.
  - **`ScopedRateThrottle` keys on the user once signed in:** a per-IP limit for everyone is `apps/core/throttles.IPScopedRateThrottle` (keys on `get_ident`, the address `ClientIPMiddleware` set). Local requests all come from 127.0.0.1, so **steps that make many searches share one bucket** (60 a minute): a second run of the guide's steps 5 to 9 inside a minute gives 429s. The guide's rate-limit step uses `X-Forwarded-For: <made-up address>` (the dev server trusts the right-most entry) for a fresh bucket.
  - **A ranked list's cursor is a bounded offset** (`core.pagination.paginate_offset`: 20 a page, 5 pages, `next_cursor` the next page number as a string, anything else a 404 `Invalid cursor`). Django's `QueryDict.get` returns the **last** value of a repeated key (the frontend parser reads the first); the client only sends one.
  - **Ruff rewrites `"a b c".split()` string constants into list literals** (`--fix`, the SIM905 rule) and then formats them one item per line: build a word list from a tuple or a concatenated string instead.
  - **An exact-username `CASE` branch is redundant:** the query is a prefix of every other username match, so A to Z already puts the exact one first. A mutation check found the dead branch; the order test needs a display-name match whose username sorts *before* the prefix matches to tell the tiers apart.
  - **Frontend:** `renderWithComposer(…).rerender` drops the providers (a test that changes the address must use `renderWithSessionAndToast`, whose `rerender` keeps them); `next/form` renders in tests without a router; the production E2E (`CI=1`) serves `.next`, so **run `npm run build` first or it tests the old pages** (it showed six failures against the stale placeholder `/search`); in dev each tab or chip change makes **two** search requests (StrictMode), the first load one; `lightStem` must give `agree` and `agreed` one stem (a final `ee` loses both letters); a mutation script that replaces the first occurrence of a class name can hit a comment (`not-italic` was in the docblock): anchor it on neighbouring classes.
  - **The Bash tool's working directory moves with `cd` in earlier calls**: use absolute paths for every command. A `source file | tail` runs in a subshell, so functions it defines are lost: don't pipe a sourced block.
  - **A full `pytest` run failed once on `test_a_link_lasts_exactly_24_hours`** (`apps/accounts/tests/test_email_verification.py`: the link answered 400 at "exactly 24 hours"), then passed alone and in the next full run: a second-boundary flake of Django's signed key, not related to Part 12.
- **Evidence:** Part 12 plan and implementation; 38 backend and 55 frontend mutation checks; `EXPLAIN ANALYZE` on 100,000 rolled-back rows; the `docs/test-command.md` Part 12 run.

### 2026-10-20 — Backend, frontend and E2E facts from Part 13 (notifications)

- **Applies to:** Parts 14, 16, 17, and anything that adds a write service that tells someone something, a shell link with a count, or a polling provider.
- **Facts (measured, then pinned by tests):**
  - **`bulk_create([obj], ignore_conflicts=True)` is the race-safe dedupe against partial unique indexes** (`ON CONFLICT DO NOTHING` arbitrates against them; a client-set UUID needs no read-back; CHECK violations still raise; it opens a savepoint-free atomic, so an `atomic(durable=True)` caller stays valid). `notify()` never opens a transaction and raises outside one; pytest-django's `db` tests are always inside one, so the "raises outside a transaction" test needs `transaction=True`.
  - **The unread-count query has to filter `is_read=False`** (Django compiles it as `NOT "is_read"`, the partial index's predicate); `EXPLAIN` with `SET LOCAL enable_seqscan = off` on a small table picks `notifications_unread_idx`.
  - **Every status writer that tells the author is called inside the transaction that changes the post** (`record_pipeline_result`/`_failure` after `settle_post`, `file_report` from `record_report`'s return value, `moderation._perform` through `_notify_author`). `_perform` must read `post.pre_review_status` **before** `rules.transition` (it clears the review fields): a verdict is sent only when the label changes.
  - **A like, follow and comment service had no `atomic`** (one autocommit statement each); they now wrap the write and the item in one block (`follow`, `like`, `add_comment`). The admin's Hide is a changelist action outside any transaction: it wraps each comment in `atomic()`.
  - **After an actor's account is deleted (SET_NULL) an item stays as "Someone liked your post" / "Someone followed you" with no link.** Part 14's deletion should delete the notifications whose `actor` is the account (the `notifications_actor_idx` partial index is there for it), not rely on SET_NULL, and must not lock the user before their posts (MEMORY, Part 11B). Posts the account authored take their items with them (CASCADE).
  - **Chrome's accessible-name computation puts a space before a separate `sr-only` span** ("Notifications , 3 unread") where jsdom joins them ("Notifications, 3 unread"); a Playwright `getByRole(..., {name: "Notifications, 2 unread"})` failed on it. Give the link one `aria-label` (`ShellLink` takes `label`). Only a real-browser run catches this.
  - **A provider that polls needs a version counter:** a poll that started before a local `set`/`adjust` must be dropped when it lands, or a slow stale answer undoes a mark-read and looks like an "arrival". The first answer is never an arrival; an arrival is a **rise** over a known count.
  - **`useCursorFeed.prepend` keeps the prepended copy over a loaded page's copy** (the memo dedupes in the order prepended, pages, appended), so re-prepending the whole fresh first page (oldest first) both adds the new items and refreshes the shown ones; filtering to "unseen only" was dead code (a mutation check found it).
  - **`FollowButton` renders nothing while the session loads**: a test that finds it needs `findByRole`. The `/dev/ui` test now renders inside an `AuthProvider` (the notification specimen has a Follow back button).
  - **React StrictMode in `next dev` makes the first unread-count request twice** (requests at 0, 0, 30, 60 s over 65 s; production: 0, 30, 60). With the tab hidden: none; coming back visible: one at once (measured in headless Chromium by redefining `document.visibilityState` and dispatching `visibilitychange`).
  - **Seed scripts that call the real services create notification rows for throwaway accounts** (the E2E helpers' `moderate`, `processPost` and a guide's moderator actions): harmless, the admin list just shows them.
  - **A subset run can fail `test_the_search_query_uses_the_gin_index`** (`pytest apps/moderation apps/social apps/posts apps/reports apps/pipeline apps/core`: the planner took another plan after those tests): it passes alone and in the full suite (alone three times, the full suite three times). Not related to Part 13.
- **Left for later parts:** an idle cutoff for the 30 s poll of a visible but untouched tab (Part 16/17: each poll is a Worker request and keeps Render and Neon awake), retention (nothing is pruned), a notice to a post's reposters, Part 14's export decision (nothing from this table is exported yet) and deletion order.
- **Evidence:** Part 13 plan and implementation; 47 backend and 51 frontend mutation checks; E2E 53 in dev and CI mode; `docs/test-command.md` Part 13 run against live Django and headless Chromium.
