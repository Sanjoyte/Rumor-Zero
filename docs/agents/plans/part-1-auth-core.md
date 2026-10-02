# Plan: Part 1, Auth core (sign up, log in, tokens, log out)

- **Status:** APPROVED by the user on 2026-10-02, together with the decisions and deviations
  below. Not started: no code has been written. The 0C dependency is satisfied.
- **Drafted:** 2026-10-01 by Claude (Opus 5.5), with a separate adversarial review pass whose
  findings are folded in. **Implement with:** Opus 5.5 · high (task.md).
- **Evidence:** allauth 65.19.5 behaviour was read in the installed source under
  `backend/.venv/Lib/site-packages/allauth/` (files named below). Turnstile was checked against
  Cloudflare's docs on 2026-10-01.

## Context

Part 1 turns the 0C skeleton into real accounts:
- email + username + password sign-up, protected by Turnstile; log in by email;
- a 15-minute access token kept only in memory, and a 14-day refresh token in the httpOnly
  `rz_refresh` cookie, which the browser gets through the relay (single origin, ANALYSIS d);
- log out, which revokes the refresh token;
- unverified accounts are read-only (`IsEmailVerified`, 403 `email_unverified`).

Afterwards every later part can rely on `request.user` (DRF, Bearer JWT) and `useAuth()`.

## Dependency gate

- **Satisfied (verified 2026-10-02).** When planning started, task.md still showed 0C
  `[~] In progress (awaiting first CI run)`. Since then:
  - the first CI run's OpenNext failure was fixed (`60cfffc`, a missing `esbuild`);
  - CI passed all three jobs on `60cfffc` (user-reported; `gh` isn't installed and the repo is
    private);
  - 0C was closed in `d92f070`. task.md shows `[x] Done (2026-10-01)` in both places.
- The `esbuild` devDependency added by that fix doesn't touch this plan.

## User decisions (2026-10-01)

1. **Superusers count as verified.** `createsuperuser` sets `is_email_verified=True` and creates
   a verified primary allauth `EmailAddress`. A data migration does the same for superusers that
   already exist (your local one from 0A).
2. **Turnstile fails closed.** If siteverify can't be reached, or rejects our secret, sign-up is
   refused with "We couldn't run the bot check. Try again in a minute."
3. **Hint cookie.** A non-secret `rz_session=1` cookie (JS-readable, `Path=/`) is set and
   cleared together with `rz_refresh`. On load the frontend calls refresh only when the hint is
   present, so anonymous visitors cost no request and see the logged-out shell at once.

## allauth facts that shape the design (65.19.5 source)

1. **Paths** (slash-less) under `path("api/auth/", include("allauth.headless.urls"))`:
   `/api/auth/app/v1/auth/login`, `…/auth/signup`, `…/tokens/refresh`.
   - Also mounted: `config`, `auth/session`, `auth/reauthenticate`, `auth/code/confirm`,
     `auth/email/verify[/resend]`, `auth/password/request|reset`, `account/email`,
     `account/password/change` and the phone endpoints.
   - Sources: `headless/urls.py`, `headless/account/urls.py`, `headless/tokens/urls.py`.
2. **App views are `csrf_exempt` and parse the body as JSON whatever its Content-Type**
   (`headless/internal/decorators.py`, `restkit/views.py`). A cross-site
   `<form enctype="text/plain">` can post valid JSON to `auth/login` (login CSRF).
3. **Login and signup responses carry three secrets in `meta`:** `access_token`, `refresh_token`
   and `session_token` (`restkit/response.py`).
   - The session token is the raw Django session key (`jwt/strategy.py`).
   - It works as `X-Session-Token` against the public backend.
   - For staff it would also work as a Django Admin `sessionid`.
4. **Refresh** takes `{"refresh_token"}` and answers with the new pair in **`data`**, not
   `meta` (`tokens/response.py`). A bad or rotated token gives a bare `{"status":400}`.
5. **Refresh-token state lives in the session** (jti → exp, `jwt/internal.py`).
   - Rotation removes the old jti at once, with no row lock and no grace period.
   - So a response lost after Django commits (a reload, the relay timing out, a dropped network)
     leaves the browser holding a dead cookie. The user is logged out.
   - Two concurrent saves of one session overwrite each other.
   - Django's DB session `save()` raises `UpdateError` if the row was deleted meanwhile.
6. **Access tokens are validated statelessly** (stateful validation is off by default). After
   logout an access token still works for DRF until it expires (≤ 15 min).
7. **`JWTTokenAuthentication` skips DRF's `is_active` check** and returns a lazy user: a
   deleted user's live token → `DoesNotExist` (500).
8. **Login and signup return 409 when the request is already authenticated** (a valid Bearer
   token counts) (`headless/account/views.py`).
9. **Rate limits** (`account/app_settings.py`, `account/adapter.py`):
   - `login_failed` = `10/m/ip,5/300s/key`. The key is `host:email`, so per account.
   - It is counted *before* the password check. A full IP bucket blocks even a correct password.
   - A lockout answers **400 `too_many_login_attempts`**, not 429.
   - `signup` = `20/m/ip` and answers 429.
   - The IP is `REMOTE_ADDR`, which `ClientIPMiddleware` sets.
10. **Signup** takes `email`, `username`, `password`.
    - A duplicate email is a field error, because verification is optional
      (`flows/manage_email.py`).
    - Optional verification sends the email and still logs the user in (`account/stages.py`).
    - A failed email send is not caught, so it gives a 500 after the user row is saved.
11. **Headless-only mode raises `ImproperlyConfigured`** when sending the verification email
    unless `HEADLESS_FRONTEND_URLS["account_confirm_email"]` is set
    (`core/internal/httpkit.py`).
12. **The username uniqueness check doesn't fold NFKC:** an exact match on the lowercased value.
    So a collision found only after NFKC folding would hit the DB unique constraint.
13. **Refresh goes through Django's `get_user`.** It rejects inactive users and checks the
    session auth hash, so a password change ends every refresh token (useful for Part 2).
14. **`sid` is encrypted with a key derived from `DJANGO_SECRET_KEY`.** Rotating that key logs
    everyone out.
15. **allauth's backend alone handles Django Admin login.** It accepts `username=<email>` and
    falls back to `User.email` (`account/auth_backends.py`, `internal/userkit.py`). Pairing it
    with `ModelBackend` would hash a wrong password twice: Argon2 uses 100 MiB per hash, and Render
    has 512 MB.

## Deviations from task.md / ARCHITECTURE (approving this plan approves these)

All are written into ARCHITECTURE §2/§3/§7/§9/§10/§12 and ANALYSIS c-18/d in this part (hard
rule 7).

1. **CSRF guard on every unsafe `/api/auth/` request**, not only refresh and logout. The rule is
   `Origin == FRONTEND_ORIGIN` and `X-Requested-With: rumor-zero`, else 403 `csrf_failed` (fact 2).
2. **Stripping:**
   - `meta.session_token`, `meta.refresh_token` and `data.refresh_token` are removed from every
     `/api/auth/` response (facts 3–4).
   - Every body under `/api/auth/` becomes JSON. A non-JSON or unparsable body, such as Django's
     DEBUG 500 page, which prints cookies, is replaced by `{"status": <code>}`.
3. **Endpoint allow-list.** Under `/api/auth/app/`, only `POST auth/login`, `POST auth/signup`
   and `POST tokens/refresh` answer; everything else is 404. Parts 2 and 3 add their own.
4. **Turnstile is checked before allauth runs** (the §7 "pre-check on that endpoint"). Django
   validates all form fields together, so a form-level check would still answer "email taken" to
   a bot. With the pre-check, a request without a solved Turnstile learns nothing.
5. **A race-safe refresh strategy** `apps.accounts.tokens.RumorZeroJWTTokenStrategy` (fact 5):
   - the session row is locked (`select_for_update`) for the whole refresh;
   - a rotated token stays valid for a **60 s grace period** instead of dying at once;
   - a deleted session (`UpdateError`) is a plain 400.

   Rotation stays on, as §7 says.
6. **The hint cookie** `rz_session` (user decision 3). §7's "refresh on load" becomes "refresh on
   load when the hint is present".
7. **Sessions:**
   - The token session's lifetime is set at login by the adapter
     (`set_expiry(JWT_REFRESH_TOKEN_DAYS)`), so it slides with each refresh. `SESSION_COOKIE_AGE`
     (admin sessions) is unchanged.
   - Only allauth's authentication backend is used (fact 15).
   - Logging in again revokes the session behind any older `rz_refresh` cookie the browser sends.
8. **Hardening in the middleware:**
   - Login, signup and refresh drop incoming `Authorization` and `X-Session-Token` headers
     (fact 8).
   - Refresh and logout reject a request carrying two `rz_refresh` cookies.
   - Refresh without the cookie gets 401 without touching the DB.
   - A rejected refresh (400/401/410) deletes both cookies; a 5xx keeps them.
9. **`HEADLESS_FRONTEND_URLS` moves into Part 1** (task.md lists it in Part 2), because of
   fact 11. **`ACCOUNT_EMAIL_SUBJECT_PREFIX = "[Rumor Zero] "`**, so subjects don't show the
   backend host.
10. **Signup survives an email failure:** `AccountAdapter.send_mail` logs only the exception class
    (fact 10). Part 2 adds Resend.
11. **Our own DRF authentication class:** a missing or inactive user gets 401 (fact 7).
12. **Startup guards** (fail by variable name, never by value):
    - `JWT_SIGNING_KEY` must be ≥ 32 characters (PyJWT warns below 32 bytes for HS256) and
      different from `DJANGO_SECRET_KEY`;
    - `FRONTEND_ORIGIN` must be a bare origin, and https when `DEBUG` is off;
    - with `DEBUG` off, `AUTH_COOKIE_SECURE` must be True and `EMAIL_PROVIDER` must be `brevo`.
      Console and file would put verification links in logs or on disk.
13. **`backend/.env.example`:** the `JWT_SIGNING_KEY` placeholder grows from 30 to ≥ 32
    characters. If your own `backend/.env` has a shorter value, Django will refuse to start and name
    the variable; make a new one with ENV_GUIDE §1.2.
14. **Frontend:**
    - the client gains `token: false`: login, signup, refresh and logout never send a Bearer
      token;
    - the login form maps `too_many_login_attempts` (400) to the rate-limit message;
    - login and logout are broadcast to other tabs.

## Backend design

### Settings (`rumor_zero/settings.py`; helpers in `rumor_zero/env_helpers.py`)
Every variable already exists in `.env.example` and ENV_GUIDE; none is new.

- **Variables:**
  - `FRONTEND_ORIGIN` (required, normalised)
  - `AUTH_COOKIE_SECURE` (bool, default True)
  - `JWT_SIGNING_KEY` (required)
  - `JWT_ACCESS_TOKEN_MINUTES` (15, range 1–60) and `JWT_REFRESH_TOKEN_DAYS` (14, range 1–90)
  - `TURNSTILE_SECRET_KEY` (required)
  - `EMAIL_PROVIDER` (`console` | `brevo` | `file`)
  - `BREVO_API_KEY` (required for brevo)
  - `DEFAULT_FROM_EMAIL`
  - One derived constant: `REFRESH_TOKEN_SECONDS`.
- **`INSTALLED_APPS`** += `allauth`, `allauth.account`, `allauth.headless`, `anymail`.
  `allauth.socialaccount` waits for Part 3.
- **`MIDDLEWARE`:** `allauth.account.middleware.AccountMiddleware`, then
  `apps.accounts.middleware.AuthApiMiddleware`, right after `AuthenticationMiddleware`.
- **`AUTHENTICATION_BACKENDS`** = `["allauth.account.auth_backends.AuthenticationBackend"]`.
- **allauth:**
  - `ACCOUNT_ADAPTER = "apps.accounts.adapter.AccountAdapter"`
  - `ACCOUNT_LOGIN_METHODS={"email"}`
  - `ACCOUNT_SIGNUP_FIELDS=["email*","username*","password1*"]`
  - `ACCOUNT_EMAIL_VERIFICATION="optional"`
  - `ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS=1`
  - `ACCOUNT_LOGIN_ON_PASSWORD_RESET=True`
  - `ACCOUNT_PRESERVE_USERNAME_CASING=False`
  - `ACCOUNT_EMAIL_SUBJECT_PREFIX`
  - The default rate limits (fact 9), now written into ARCHITECTURE §3.
- **headless:**
  - `HEADLESS_ONLY=True`, `HEADLESS_CLIENTS=("app",)`
  - `HEADLESS_TOKEN_STRATEGY="apps.accounts.tokens.RumorZeroJWTTokenStrategy"`
  - `HEADLESS_JWT_ALGORITHM="HS256"`, `HEADLESS_JWT_PRIVATE_KEY=JWT_SIGNING_KEY`
  - both lifetimes in seconds
  - rotation on; `HEADLESS_JWT_STATEFUL_VALIDATION_ENABLED=False`, set explicitly (fact 6)
  - `HEADLESS_FRONTEND_URLS` for `account_confirm_email` (`/verify-email/{key}`),
    `account_reset_password_from_key` (`/reset-password/{key}`), `account_reset_password`
    (`/forgot-password`) and `account_signup` (`/signup`), all on `FRONTEND_ORIGIN`.
- **Email:**
  - console → Django's console backend;
  - brevo → `anymail.backends.brevo.EmailBackend` with `ANYMAIL={"BREVO_API_KEY": …}`;
  - file → `backend/tmp/mail/` (git-ignored; Part 2's E2E reads it).
- **`REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"]`** =
  `["apps.accounts.authentication.JWTAuthentication"]`.
- **`SESSION_ENGINE`** stays the database backend (the row lock and logout depend on it;
  recorded in §7).

### `apps/accounts/middleware.py`: `AuthApiMiddleware` (paths under `/api/auth/` only)

**Request phase, in order:**
1. **Allow-list:** a path under `/api/auth/app/` that isn't one of `ALLAUTH_ENDPOINTS`
   (path → allowed methods) → 404.
2. **CSRF guard** on every method except GET, HEAD and OPTIONS → 403 `csrf_failed`.
3. **Login, signup and refresh** drop `HTTP_AUTHORIZATION` and `HTTP_X_SESSION_TOKEN`.
4. **Signup pre-check:**
   - First, allauth's own `signup` limit in dry-run mode
     (`allauth.core.ratelimit.consume(request, action="signup", dry_run=True)`, the same IP
     bucket). If it's exhausted → our own JSON 429, and Cloudflare is not called.
   - `turnstile_token` missing, not a string, or over 2048 characters → 400 `turnstile_failed`
     (param `turnstile_token`). This counts against the signup limit.
   - `verify_turnstile()` FAILED → the same 400. UNAVAILABLE → 400 `turnstile_unavailable` (user
     decision 2). Both count.
   - OK → allauth runs and counts the attempt itself, so each attempt counts exactly once.
5. **Refresh injection:**
   - no cookie → 401 (and the hint is deleted);
   - two `rz_refresh` cookies → 400;
   - otherwise the body becomes `{"refresh_token": <cookie>}`. `request._body`, the stream,
     `CONTENT_TYPE` and `CONTENT_LENGTH` are all set, so a token sent in the body is never used.

**Response phase:**
- Streaming responses are skipped. Every other body is made JSON (deviation 2).
- The secrets are extracted with `cookies.extract_tokens()`. When a refresh token is found:
  - `rz_refresh` is set: `HttpOnly; SameSite=Lax; Path=/api/auth/; Max-Age=REFRESH_TOKEN_SECONDS;
    Secure=AUTH_COOKIE_SECURE`, no `Domain`;
  - `rz_session=1` is set the same way, but not HttpOnly and with `Path=/`;
  - on login or signup, the session behind an older incoming cookie is revoked.
- A refresh answered with 400, 401 or 410 deletes both cookies.
- `Cache-Control: no-store` is added.
- Our own error bodies use allauth's envelope `{"status", "errors":[{code, param?, message}]}`,
  which `normalizeError` already handles.

### Other backend modules
- **`tokens.py`: `RumorZeroJWTTokenStrategy(JWTTokenStrategy)`.** It overrides only
  `refresh_token()`:
  1. decode the token (`internal.decode_token`) and get its session key;
  2. inside `transaction.atomic()`, `select_for_update()` the `django_session` row (missing → None);
  3. `internal.validate_refresh_token()` (which reads the session inside the lock);
  4. issue the access token;
  5. cap the old jti's expiry at `now + 60 s` instead of removing it, and prune expired jtis;
  6. issue the new refresh token and `session.save()`;
  7. treat `UpdateError` as None.

  It reuses allauth's helpers in `headless/tokens/strategies/jwt/internal.py`. That is safe with
  the exact pin, and tests pin the behaviour.
- **`cookies.py`:** `set_auth_cookies`, `delete_auth_cookies`, `extract_tokens(body)` (pure),
  `count_cookie(header, name)`, `revoke_refresh_token_session(token)`. The last one decodes the
  token (signature and expiry only) and deletes that `django_session` row; it backs logout and
  re-login.
- **`turnstile.py`:** `verify_turnstile(token, remote_ip) -> OK | FAILED | UNAVAILABLE`.
  - stdlib `urllib.request`; no new dependency (`requests` is only a transitive one);
  - a form POST with `secret`, `response`, `remoteip` and an `idempotency_key`; 5 s timeout;
  - one retry with the same key on a network error or 5xx;
  - `invalid-input-secret`, `missing-input-secret` and `internal-error` → UNAVAILABLE, logged as an
    error that names the variable;
  - any other error code → FAILED;
  - the token and the secret are never logged.
- **`adapter.py`: `AccountAdapter`:**
  - `clean_username` normalises with `normalize_username` first (fact 12);
  - `login()` calls `request.session.set_expiry(REFRESH_TOKEN_SECONDS)`;
  - `send_mail()` catches `AnymailError`, `OSError` and `SMTPException` and logs only the class
    name and template prefix.
- **`authentication.py`:** `JWTAuthentication(JWTTokenAuthentication)` forces the user lookup.
  A missing or inactive user → `AuthenticationFailed`. Still one query.
- **`permissions.py`:** `IsEmailVerified` (`code = "email_unverified"`, a plain message). An
  anonymous request still gets 401.
- **`models.py`:** `create_superuser` also sets `is_email_verified=True` and creates the verified
  primary `EmailAddress`.
- **Migration** `accounts/0002_verify_superuser_emails.py` (depends on allauth's
  `account.0009_emailaddress_unique_primary_email`). It backfills existing superusers and its
  reverse does nothing. Run `ruff --fix` and `ruff format` on it straight after creating it.
- **`views.py`:**
  - **`logout_view`:** `POST /api/auth/logout/`, `csrf_exempt` (the middleware checks
    `Origin` and the header). It calls `revoke_refresh_token_session(cookie)` and always answers
    204 with both cookies deleted. It is idempotent.
  - **`MeView`:** `GET /api/v1/me/`, `IsAuthenticated`, `never_cache`, one query. Returns `id`,
    `username`, `display_name`, `email`, `is_email_verified`, `role`, `has_usable_password`,
    `google_connected` (false until Part 3) and `avatar_url` (from `avatar_version`, so null
    until 14B). Staff also get `admin_url`
    (`request.build_absolute_uri("/" + ADMIN_URL_PATH)`), the backend host that serves the admin.
  - **`UsernameAvailableView`:** `GET /api/v1/auth/username-available/?u=`. No authentication,
    `ScopedRateThrottle` scope `username_check` (30/min by IP), `never_cache`. It runs
    `normalize_username`, then `validate_username`, then checks existence, and answers
    `{"username", "available", "reason": null|"invalid"|"reserved"|"taken", "message"}`.
    A missing `u` → 400. More than 64 characters → `invalid`.
- **`urls.py`** + `rumor_zero/urls.py`: `api/auth/logout/` and `api/auth/` (allauth) come before
  `api/`; `api/v1/me/` and `api/v1/auth/username-available/`.

## Frontend design

### API client (`src/lib/api/client.ts`)
- New `RequestOptions.token?: false` sends the call without `Authorization`. Nothing else
  changes.

### Auth library (`src/lib/auth/`)
- **`auth-api.ts`:** the paths in one constant, plus `login`, `signup`, `refresh`, `logout` and
  `fetchMe`. Login and signup read `meta.access_token`; refresh reads `data.access_token`. Refresh
  and logout never take an AbortSignal: a cancelled refresh would strand a rotated token.
- **`jwt.ts`:** `tokenClaims(token)` reads `sub`, `iat` and `exp` from the unverified payload.
  The lifetime is measured from when the token arrived, so the client's clock doesn't matter.
- **`session-hint.ts`:** `hasSessionHint()` reads `rz_session` from `document.cookie`.
- **`session.ts`:** a framework-free session with injectable `fetch`, lock, clock, store and
  channel, so two "tabs" can be unit-tested as two sessions.
  - **Bootstrap** is one module-level promise, so React StrictMode can't run it twice. No hint →
    anonymous at once. Otherwise refresh, then `GET /api/v1/me/`.
  - **Refresh** is single-flight per tab. Only the refresh POST runs inside `withRefreshLock`,
    because Web Locks aren't re-entrant and `/me` or a retried call must never wait on it.
    Outcomes:
    - 400, 401, 403 or 410 → **invalid**: anonymous (a 403 also logs a `console.error`);
    - a network error or 5xx → **transient**: keep the current state and retry after 2 s, 5 s,
      15 s, then every 30 s while visible. The guard never redirects in this state.
  - **After a refresh:** if the token's `sub` differs from the current user's id (another
    account logged in through the shared cookie), reload `/me`.
  - **Schedule:** refresh at `max(lifetime / 2, lifetime − 60 s)`. On `visibilitychange` →
    visible, refresh now if one is due or pending.
  - **401 handler:** if a refresh finished in the last 10 s, just retry; otherwise refresh once.
  - **Login and signup:** POST with `token: false`, store the token, `/me`, then broadcast
    `login`. A tab that is anonymous re-runs bootstrap when it hears `login`.
  - **Logout:**
    - runs `POST /api/auth/logout/` inside the lock;
    - on 204: clear the token, timers and user, then broadcast `logout`;
    - on failure: throw and change nothing. The UI shows "Couldn't log out. Check your
      connection and try again."
  - The `BroadcastChannel("rz-auth")` is used only when available.
- **`AuthProvider.tsx`:** binds the session to `{status, user}` plus `login`, `signup`, `logout` and
  `reloadMe`. A token never goes to `localStorage`, `sessionStorage` or a JS cookie.
- **`next-path.ts`: `safeNextPath(raw)`:**
  - parse with `new URL(raw, location.origin)` and require the same origin;
  - reject a backslash or control character in the raw value, and a resulting path starting
    with `//`;
  - reject `/api/`, `/login` and `/signup`;
  - return path, query and hash, or null.

  This covers `/.//evil.com`-style dot segments.
- **`route-guard.ts`:** `PROTECTED_PREFIXES = ["/notifications", "/bookmarks", "/settings"]`.
  `/home`, `/search` and `/u/…` stay public (the 0C smoke tests visit `/home` logged out).

### Shell
- **`(app)/layout.tsx`** passes `user`, `status` and `onLogout`. On a protected path it shows a
  Skeleton while loading and calls `router.replace("/login?next=…")` when anonymous.
- **While loading,** the user card, Log in / Sign up and the avatar render same-size Skeletons
  (the rail keeps its 256 px width).
- **`AccountMenu`** gains optional actions rendered as buttons.
  - Log out goes last in the rail menu (Profile, Settings, Log out) and in the phone sheet
    (Bookmarks, Settings, Moderation, Log out).
  - After logout → `/login`. A failed logout shows an error toast.
  - The tests that pin the menu items are updated.
- **`UnverifiedBanner`** sits at the top of `<main>` while `user.is_email_verified` is false:
  `Alert tone="warning"` with "Verify your email to post, comment and report. Check your inbox
  for the link." (ANALYSIS b-2; Resend comes in Part 2). `ShellUser` gains `is_email_verified`.

### Pages (route files stay thin; screens in `src/features/auth/`)
Both pages stay prerendered. `?next=` is read from `window.location` at redirect time:
`useSearchParams` on a static page needs a Suspense boundary (Next 16 docs). A visitor who is
already logged in is sent on to `next` or `/home`.

- **`/signup` → `SignupForm`** (a2 classes and copy, with b-5's jargon removed):
  - **Fields:** Email, Username, Password + `PasswordStrengthMeter`.
  - **`useUsernameAvailability`:** 400 ms debounce; the format is checked client-side first;
    stale requests are aborted.
    - States: checking, "Available: @ada" (check icon, `primary`), taken, reserved, invalid.
    - A 429 or network error shows nothing; the server decides at submit.
  - **Turnstile:** the widget replaces a2's "Protected by Turnstile" callout.
  - **"Create account"** is disabled until Turnstile has a token. Below it: the Terms/Privacy note
    and "Already have an account? Log in".
  - **Errors:** each maps by `param` (`email`, `username`, `password`, `turnstile_token`) to its
    field; anything else goes in an `Alert`. After every failed submit the widget is reset,
    because a token works only once.
  - **Success** → `/home`, with the banner.
  - **0B follow-up closed:** `scorePassword` rates anything under 8 characters as Weak, which
    matches Django's minimum of 8.
- **`/login` → `LoginForm`** (a3 classes and copy):
  - **A dismissible `Alert`:**
    - `email_password_mismatch` → "That email and password don't match."
    - `too_many_login_attempts` or 429 → "Too many attempts. Try again in a few minutes."
    - 503 → the relay's waking message.
    - `csrf_failed` → "Something went wrong. Reload the page and try again."
  - **Below it:** Email, Password, "Log in →", and the "Don't have an account? Sign up" box.
  - **Dropped:** Remember me, the attempt counter, the rate-limit notice and the protocol footer.
    "Forgot password?" arrives with its page in Part 2.
  - **Success** → `safeNextPath(next) ?? "/home"`.
- The Google button and its divider stay unrendered until Part 3.

### Turnstile (`src/lib/turnstile.ts`, `src/features/auth/Turnstile.tsx`)
- **Loader** (no package): injects `https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit`
  once, from that exact URL (Cloudflare forbids proxying it).
- **Widget:** `turnstile.render(el, {sitekey, callback, "expired-callback", "error-callback",
  size: "flexible", action: "signup"})`. It is removed on unmount and reset when `resetKey`
  changes.
- **No site key** (empty `NEXT_PUBLIC_TURNSTILE_SITE_KEY`): the form shows "Sign-up is unavailable
  right now."

## Files

- **Backend, new:**
  - `apps/accounts/{middleware,tokens,cookies,turnstile,adapter,authentication,permissions,
    serializers,views,urls}.py`
  - `apps/accounts/migrations/0002_verify_superuser_emails.py`
  - tests `apps/accounts/tests/test_{auth_api,middleware,tokens,cookies,turnstile,
    username_available,me,permissions,authentication,rate_limits,superuser}.py`
- **Backend, changed:**
  - `rumor_zero/{settings,urls,env_helpers}.py`
  - `apps/accounts/models.py`
  - `conftest.py`: fixed test values for the JWT key, the Turnstile secret and `FRONTEND_ORIGIN`
  - `apps/core/tests/test_settings.py`: `production_env()` gains every newly read variable,
    including `EMAIL_PROVIDER=brevo`; the missing-variable list and leak check gain the new
    secrets; the new guards get tests
  - `apps/accounts/tests/test_admin.py`
  - `backend/.env.example`
  - root `.gitignore` (`backend/tmp/`)
- **Frontend, new** (each with a test):
  - `src/lib/auth/{session,auth-api,jwt,session-hint,next-path,route-guard}.ts`
  - `src/lib/turnstile.ts`
  - `src/features/auth/{SignupForm,LoginForm,Turnstile}.tsx` and `useUsernameAvailability.ts`
  - `src/components/shell/UnverifiedBanner.tsx`

  Plus `e2e/auth.spec.ts`.
- **Frontend, changed** (and their tests):
  - `src/lib/api/client.ts`, `src/lib/auth/AuthProvider.tsx`
  - `src/app/(app)/layout.tsx`, `src/app/(auth)/{login,signup}/page.tsx`
  - `src/components/shell/{AppShell,Sidebar,TopBar,MobileNav,AccountMenu,nav-items}`
  - `playwright.config.ts`: the Django server gets `REDIS_URL: ""`, so each run starts with
    empty in-memory rate limits
  - `e2e/smoke.spec.ts`: its comment

## Ordered steps

0. **Right after approval (no code yet). Done 2026-10-02:** this file was saved and HANDOFF
   points at it. Its next action reads "Implement Part 1 from the approved plan".

   **When implementation starts:** the 0C gate is already satisfied (see "Dependency gate"),
   so:
   - set Part 1 to `[~] In progress` in both task.md places;
   - update HANDOFF "Active work";
   - continue with step 1.
1. **Settings and guards,** `conftest`, `test_settings`, the superuser rule and its migration.
   Run `ruff`, `pytest` and `check --deploy`; `makemigrations --check` must be clean.
2. **Turnstile client, adapter, authentication, permission, token strategy, cookies, middleware,
   logout and URLs,** each with its tests (including the concurrency tests).
3. **`/me` and username-available,** with tests and query counts.
4. **Manual checks with `runserver` and curl:**
   - signup sets both cookies and its body has no secret;
   - the console shows the verification email with a `FRONTEND_ORIGIN` link;
   - refresh rotates the token, and the old token still works for 60 s;
   - logout revokes it;
   - a missing `Origin` or header gets 403.
5. **Frontend auth library and the client option,** with tests.
6. **AuthProvider, the shell changes and the guard,** with tests.
7. **Turnstile, the username hook, the forms and pages,** with tests.
8. **Visual check of `/signup` and `/login`** against Stitch a2/a3: headless Edge at 1280,
   Playwright at 390, no horizontal overflow (MEMORY recipe; files in the scratchpad).
9. **`e2e/auth.spec.ts`;** then the whole suite in dev mode and in CI mode.
10. **Through the relay:**
    - repeated failed logins from one IP → `too_many_login_attempts`;
    - DevTools shows the cookie flags and nothing in storage.
11. **Docs** (below).
12. **Stop.**

## Tests (task.md's required list, mapped and extended)

- **Backend:**
  - **API flows:**
    - signup: 200; both cookies; no `refresh_token` or `session_token` in any body (200, 400,
      409, 410, 429); the verification email is sent with a `FRONTEND_ORIGIN` link; 409 when
      already authenticated; the real `param` names;
    - login and refresh: rotation, plus the old token inside and after the 60 s grace;
    - logout: the session is deleted, the old token fails, it is idempotent;
    - re-login revokes the old session;
    - a signup whose email fails to send still succeeds.
  - **Cookie attributes** with Secure on and off, for both cookies.
  - **CSRF:**
    - missing or wrong `Origin`, `Origin: null`, another port or scheme, a missing or wrong
      `X-Requested-With` → 403 on refresh, logout, login and signup;
    - two `rz_refresh` cookies → 400.
  - **Allow-list:** `account/email`, `auth/session` and a GET of `auth/login` → 404.
  - **Concurrency** (`transaction=True`):
    - two refreshes of one token at once → both succeed, and both new tokens work;
    - a refresh racing a logout → no 500, and no token survives.
  - **Username availability:** case, NFKC, reserved, format, taken, the throttle.
  - **Turnstile (mocked):**
    - pass, fail, missing, oversize, outage, wrong secret;
    - a taken email with a bad token → only the Turnstile error;
    - an exhausted signup limit → 429 without calling Cloudflare.
  - **Argon2:** the project hashers restored, so the hash starts with `argon2$argon2id$`.
  - **Rate limiting:**
    - 10 failures from IP A with different emails → the 11th gets `too_many_login_attempts`;
    - IP B with a fresh email still gets `email_password_mismatch`;
    - the per-account limit tested on its own;
    - the signup limit → 429;
    - all through `X-RZ-Client-IP` + the secret.
  - **`/me`:** the fields; `admin_url` for staff only; one query; 401 when anonymous.
  - **`IsEmailVerified`:** 403 `email_unverified` on a test-only view; anonymous → 401.
  - **Authentication class:** a deleted or inactive user → 401.
  - **Superuser:** `createsuperuser` and the backfill → verified; admin login still works.
  - **Settings guards:** each fails by name and prints no value.
- **Frontend:**
  - **Forms:** validation, field errors by param, banner messages, loading, widget reset.
  - **Session/AuthProvider (fake timers):**
    - the schedule and the visibility catch-up;
    - transient versus invalid outcomes and the backoff;
    - one retry on 401, skipped when the token is fresh;
    - no deadlock when `/me` gets a 401;
    - the `sub` check;
    - the login/logout broadcasts; a failed logout changes nothing;
    - no hint → no request;
    - two sessions on a strictly rotating fake backend both survive under the lock, and a
      control run without the lock fails;
    - no storage writes.
  - **Smaller units:** the username hook (debounce, abort, states); the `safeNextPath` table
    (including dot segments and backslashes); `tokenClaims`; `token:false`; the Turnstile
    component with a fake `window.turnstile`.
  - **Shell:** the loading Skeletons, the banner, Log out in both menus, the guard redirect.
- **E2E (`auth.spec.ts`, unique emails, chromium):**
  - **Signup:** with the test Turnstile key → `/home` with the banner.
  - **Cookies:** `context.cookies()` shows `rz_refresh` HttpOnly, SameSite=Lax,
    `Path=/api/auth/`, host-only; `rz_session` is readable; no token in storage.
  - **Staying logged in:**
    - a reload keeps you logged in;
    - two tabs loading at once, then a reload of both → both still logged in;
    - **two tabs at token expiry:** with `context.clock`, move both past the scheduled refresh
      together, then reload both → both still logged in.
  - **Log out** → the logged-out shell; both cookies gone; the old cookie value → 400 on
    refresh; refresh without the header → 403.

## Verification (PowerShell)

```powershell
docker compose up -d                                   # repo root
# backend\ (venv active)
ruff check . ; ruff format --check . ; python manage.py makemigrations --check --dry-run ; pytest
# frontend\
npm run lint ; npm run lint:tokens ; npm run typecheck ; npm run format:check ; npm test
npm run build      # /login and /signup still prerendered (○)
npm run test:e2e   # dev mode; then CI mode: $env:CI="1"; npm run build; npm run test:e2e
```

Plus the manual checks in steps 4, 8 and 10. Every command and its result goes in HANDOFF.

## Docs to update (hard rules 5, 7, 10)

- `task.md`: criteria, deviations, status in both places.
- `ARCHITECTURE.md`:
  - §2: superusers are verified.
  - §3: the auth rate limits.
  - §7:
    - endpoints, cookies and secrets: the confirmed paths and the allow-list; the cookie `Max-Age`
      in seconds (it says days); the hint cookie; the three stripped secrets;
    - CSRF and Turnstile: the CSRF scope; the Turnstile pre-check;
    - tokens and sessions: the strategy with its lock and grace; stateless access tokens; sliding
      sessions; the DB session engine; logout and re-login revocation; one auth backend.
  - §9: the endpoint index; the `/me` and username-check shapes.
  - §10: the loading state, the guard, Log out.
  - §12: the CSRF row.
- `ANALYSIS.md`: c-18 and d.
- `ENV_GUIDE.md`:
  - §1.2: the JWT key needs ≥ 32 characters;
  - §1.3: `EMAIL_PROVIDER` gains `file`;
  - §2.13: rotating `DJANGO_SECRET_KEY` also logs everyone out.
- `backend/.env.example` (deviation 13).
- `STRUCTURE.md` markers; `docs/test-command.md` Part 1 section; `HANDOFF.md`.
- `MEMORY.md`:
  - the allauth gotchas (facts 2, 3, 5, 7, 9, 10);
  - the strategy, logout and re-login depend on allauth's JWT internals, so re-check them
    whenever allauth is upgraded.

## Stop conditions

Stop and report instead of working around:
- allauth behaves differently from the facts above;
- a new warning in `pytest` or `check --deploy` that would need a filter or a silenced check;
- the Turnstile test widget or siteverify can't be reached from CI;
- any change needed to the 0C relay, `lint:tokens` or the brand guard;
- a peer-dependency conflict (none expected: no new package).

**Out of scope:**
- the verification and reset pages, Resend, email templates, the `email_confirmed` signal
  (Part 2);
- Google (Part 3);
- the composer (Part 4);
- the settings page and changing your password (Part 14);
- CSP (Part 16).

## Follow-ups to record in HANDOFF

- **Part 2:**
  - add `auth/email/verify`, `auth/password/request`, `auth/password/reset` and its chosen resend
    endpoint to the allow-list (`auth/email/verify/resend` is allauth's code-flow resend);
  - add "Forgot password?" on `/login`;
  - the E2E mailbox is `backend/tmp/mail/`.
- **Part 3:**
  - add `allauth.socialaccount` and `auth/provider/token` to the allow-list, and make
    `google_connected` real;
  - a *pending* social signup needs `X-Session-Token`, which we strip and the relay doesn't
    forward. Auto-signup must never pend, or Part 3 adds a short-lived flow cookie.
- **Part 9/17:** run `clearsessions` periodically (expired token sessions pile up in Neon).
- **Part 10:** as defence in depth, make the admin refuse sessions created by headless login.
- **Part 14:** deleting an account must also delete its sessions.
- **Part 16:**
  - CSP for Turnstile;
  - check what siteverify returns for `action`/`hostname` with the test keys, and add those checks
    if possible;
  - brute-force protection for the Django Admin login;
  - Argon2's 100 MiB per hash against Render's 512 MB (worker count or `memory_cost`).
- **Part 17:** fail a deploy that uses a Turnstile test secret.
