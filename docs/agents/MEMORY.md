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

