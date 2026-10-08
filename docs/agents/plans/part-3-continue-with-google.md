# Plan: Part 3, Continue with Google

- **Status:** APPROVED by the user (Sanjoy Rozario) on 2026-10-08, together with the decisions
  below. **IMPLEMENTED 2026-10-08** (Claude, Sonnet 5.5). Deviations: see `task.md` Part 3 and
  `docs/agents/HANDOFF.md` (no `context` prop on `GoogleButton`, a `googleClientId` prop on the forms).
- **Drafted:** 2026-10-07/08 by Claude (Opus 5.5). A separate review pass checked it against the
  code, and its findings are folded in. **Implement with:** Sonnet 5.5 · medium (task.md).
- **Evidence:**
  - allauth 65.19.5 and PyJWT 2.15.1 behaviour, read in the installed source under
    `backend/.venv/lib/python3.13/site-packages/`;
  - the HS256 TypeError, reproduced with PyJWT;
  - Google's GIS JS reference, FedCM migration guide and ID-token verification guide (checked
    2026-10-07).

## Context

`task.md` Part 3 adds one-click Google sign-in and sign-up. The browser gets an ID token from
Google Identity Services (GIS). allauth checks it at `POST /api/auth/app/v1/auth/provider/token`,
then either creates the user or logs in the existing one.

**Dependencies.**
- Part 3 depends only on Part 1, which is Done (2026-10-03, CI green).
- Part 2 is also Done. You committed it as `36fdb66`; its CI result hasn't been reported yet.
- The tree is clean on `main`.
- Both client-ID variables already exist in the example files and in your local env files. I did
  not read their values.

**What allauth 65.19.5's source showed** (verified by reading it; these facts shape the design):
1. **A pending social sign-up returns 401 and can't be finished.** It needs `meta.session_token`,
   which our middleware strips. So a sign-up must never pend. It only pends when Google's email is
   missing or unverified, and we reject both up front.
2. **`provider/token` has no rate limit,** and every call fetches Google's certificates over the
   network.
3. **Two forged-token shapes cause a 500, not a 400:** a JWT header without `kid` (KeyError), and
   `alg: HS256` checked against the RSA key (TypeError; reproduced with PyJWT 2.15.1).
4. **`email_confirmed` never fires for Google emails,** so `users.is_email_verified` would stay
   False.
5. **Linking to an unverified address (`wipe_password`) doesn't mark the address verified.** It does
   make the password unusable. That password change ends other sessions at their next refresh,
   because our refresh calls `get_user`, which checks the session auth hash.
6. **allauth's username generator would turn most names into `user1234`,** because
   `^[a-z0-9_]{3,30}$` rejects `.` and `-`, and `user` is reserved.
7. **Email matching doesn't skip inactive users.** It links them, and may wipe their password,
   before `perform_login` refuses them.
8. **Order inside a login:** lookup → our `pre_social_login` → `wipe_password` → `connect()` (fires
   `social_account_added`) → `perform_login`. Marking the address verified before the wipe would
   skip the wipe.
9. **Setup requirements:** the app is configured in settings with an empty secret.
   `allauth.socialaccount` and `…providers.google` must both be installed. A database `SocialApp` row
   for the same provider would cause `MultipleObjectsReturned`, a 500.
10. **No leeway for clock differences:** PyJWT rejects `iat` in the future, and allauth passes no
    leeway. A server clock that runs behind Google's gives occasional 400s.
11. **A `UserFactory` / `create_user` account has no `EmailAddress` row.** `wipe_password` treats it
    as unverified.

**Your decisions (2026-10-07):**
- **Unverified local account plus a Google sign-in:** link the accounts. The password becomes
  unusable, the address is marked verified, and other sessions end at their next refresh. Verified
  accounts always link.
- **Only addresses Google vouches for link to an existing account:** `@gmail.com`, or tokens with an
  `hd` claim (Google Workspace). This follows Google's ID-token guidance. Other addresses that match
  an existing account get a 400 asking for a password login. New Google sign-ups still work with any
  verified address.
- **No linking to staff accounts by email:** moderators and superusers get "Staff accounts log in
  with their password." Someone who linked Google before becoming staff keeps signing in through the
  existing link.
- **Username** comes from Google's **first name** (`given_name`), not the email local part. This
  changes ANALYSIS c-29 and b-2.
- **Display name** stays **blank.** Nothing from the Google profile becomes public.

**Decided without asking** (stated so you can change them now):
- **The button is Google's own rendered button,** as `task.md` says. GIS only returns an ID token
  from its own button or One Tap, so Stitch's custom "G" button can't be kept (this changes the
  ANALYSIS GoogleButton row; `design/` is read-only and untouched).
  - Options: `theme: "outline"`, `size: "large"`, `text: "continue_with"`, `shape: "rectangular"`,
    `logo_alignment: "center"`, `locale: "en"`, width = card width clamped to 200–400 px.
  - This also means no raw hex in `src/`.
- **A closed popup produces no event,** because GIS gives no close callback for its button. The page
  just stays as it was. Recorded as a deviation from "errors for a closed popup".
- **Rate limit:** `provider/token` consumes allauth's existing `login` bucket (30/min per IP, shared
  with password logins) and answers 429 when it is full.
- **`/me` becomes two queries,** because `google_connected` is now a real `exists()`. ARCHITECTURE §9
  is updated.
- **Keep only `sub`, `email`, `email_verified` and `hd` from the token** in
  `SocialAccount.extra_data`. Google's name and picture URL are not stored.
- **Admin:** `SocialApp` and `SocialToken` are unregistered, because the app is configured in settings
  and tokens aren't stored. `SocialAccount` stays registered.

## Backend

### Settings (`backend/rumor_zero/settings.py`, `env_helpers.py`)
- `GOOGLE_OAUTH_CLIENT_ID = google_client_id(env)`, a new helper.
  - Blank means Google is disabled. There's no production "required" guard, because the task says
    "disabled cleanly when empty".
  - When set, the value must have no whitespace, end with `.apps.googleusercontent.com`, and be at
    most 200 characters. Otherwise `ImproperlyConfigured` names the variable, never the value.
- Add `"allauth.socialaccount"` and `"allauth.socialaccount.providers.google"` to `INSTALLED_APPS`,
  after `allauth.headless`.
- New settings:
  ```python
  SOCIALACCOUNT_ADAPTER = "apps.accounts.adapter.SocialAccountAdapter"
  SOCIALACCOUNT_PROVIDERS = {"google": {
      "APPS": [{"client_id": GOOGLE_OAUTH_CLIENT_ID, "secret": "", "key": ""}] if GOOGLE_OAUTH_CLIENT_ID else [],
      "VERIFIED_EMAIL": False}}               # use Google's own email_verified claim
  SOCIALACCOUNT_EMAIL_AUTHENTICATION = True
  SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True
  SOCIALACCOUNT_AUTO_SIGNUP = True            # pinned
  SOCIALACCOUNT_STORE_TOKENS = False          # pinned
  SOCIALACCOUNT_REQUESTS_TIMEOUT = 5          # pinned (fetching Google's certificates)
  ```
- `ACCOUNT_EMAIL_NOTIFICATIONS` stays False, so no "account connected" email is sent (follow-up).
- allauth's `socialaccount` migrations run on `migrate`. We add none of our own, so
  `makemigrations --check` stays clean.

### Middleware (`apps/accounts/middleware.py`) and a new `apps/accounts/google.py`
- Add `PROVIDER_TOKEN_PATH = _APP + "auth/provider/token"` to `ALLAUTH_ENDPOINTS` (`{"POST"}`) and to
  `_ISSUING_ENDPOINTS`, but not to `_COOKIE_ENDPOINTS`, same as login. That gives it everything the
  existing endpoints get:
  - a stale `Bearer` or `X-Session-Token` is dropped;
  - the CSRF guard applies;
  - the session behind an old `rz_refresh` is revoked;
  - the cookies are set;
  - the body is turned into JSON and stripped of secrets.

  allauth's other new paths (`auth/provider/signup`, `auth/provider/redirect`, `account/providers`)
  stay 404.
- In `_before`:
  - If `GOOGLE_OAUTH_CLIENT_ID` is blank, answer **404 `not_found`**, the same as an unlisted path.
  - After the CSRF check, run `ratelimit.consume(request, action="login")`. A full bucket answers 429
    `{"status":429}`.
  - Then `google.check_provider_token_request(body)`, a pure function. The body is read like the
    Turnstile pre-check reads it, catching `ValueError` and `RequestDataTooBig`. It answers 400
    `invalid_token` (param `token`, in allauth's envelope with allauth's message) unless:
    - `provider == "google"` and `process == "login"` (`connect` is out of scope);
    - `token` is a dict and `token.client_id == settings.GOOGLE_OAUTH_CLIENT_ID`;
    - `token.id_token` is a string of at most 4096 characters;
    - `jwt.get_unverified_header(id_token)` parses, its `alg` is `"RS256"`, and its `kid` is a
      non-empty string of at most 200 characters.

    A body that can't be parsed, or isn't a dict, gets the same 400. These checks remove both 500s
    (fact 3).
  - A `client_id` mismatch also logs a warning that names `GOOGLE_OAUTH_CLIENT_ID` /
    `NEXT_PUBLIC_GOOGLE_CLIENT_ID`, never the values.
- allauth keeps doing everything else: the signature, the `aud`/`iss`/`exp`/`iat` checks and the
  `jti` replay check.

### Social adapter (`apps/accounts/adapter.py`, new `SocialAccountAdapter`)
- **`populate_user`** (this runs before the lookup):
  - call `super()`;
  - trim `sociallogin.account.extra_data` to `sub`, `email`, `email_verified` and `hd`;
  - keep Google's `given_name` on the in-memory `SocialLogin` so `save_user` can use it.
- **`pre_social_login`** runs after the lookup and before any link, wipe or save. Each refusal
  raises a single-message `ValidationError`, which the view turns into a 400 with that code and no
  `param`. No session or cookie is left behind. The checks, in order:
  1. No verified Google email → `google_email_unverified` ("Your Google account's email address
     isn't verified.").
  2. `sociallogin.is_existing` and the matched user is inactive → `account_inactive` ("This account
     can't sign in."). This stops linking and wiping on disabled accounts (fact 7).
  3. Matched by email (`getattr(sociallogin, "_did_authenticate_by_email", None)`) and the user is
     staff → `staff_password_login` ("Staff accounts log in with their password.").
  4. Matched by email, the address is not `@gmail.com`, and there's no `hd` claim →
     `google_link_requires_password` ("An account with this email already exists. Log in with your
     password.").

  A login that matches an existing Google link by `uid` skips checks 3 and 4.
- **`save_user`** (new users only):
  - set `user.username = generate_username(given_name)` and `user.is_email_verified = True`;
  - then `super()`, which sets an unusable password, keeps our username, saves the user, and creates
    the verified primary `EmailAddress`;
  - `display_name` stays blank.

### Username generator (new `apps/accounts/usernames.py`)
`generate_username(given_name, *, is_taken=<db exists>, rng=secrets.SystemRandom())`:
1. Normalise the name: NFKD, drop non-ASCII, lowercase, and turn every run of characters outside
   `[a-z0-9]` into `_`. Then cut it to 20 characters, and only after that strip `_` from both ends.
2. If the slug has 3+ characters, isn't reserved and is free, use it.
3. If the slug has 1+ characters and isn't reserved, use `{slug}_{4 random digits}`, with up to 10
   tries.
4. Otherwise (empty, non-Latin or reserved names) use `member_{6 random [a-z0-9]}`, with up to 10
   tries, then `member_{uuid4 hex[:12]}`.

Every result matches `USERNAME_PATTERN` and is never reserved. Some given names, such as Bengali
ones, always end up as `member_…`; that's by design. Two simultaneous sign-ups with the same new
username or email would hit an IntegrityError (500). That's rare and accepted (follow-up).

### Linking an existing account (`signals.py` + `services.py`)
- A receiver on allauth's `social_account_added`:
  - reads `getattr(sociallogin, "_did_authenticate_by_email", None)` and does nothing when it is
    None;
  - otherwise calls the new `services.mark_email_verified_by_google(user, email)`.
- That service:
  - marks the user's `EmailAddress` for that address verified, creating a primary row if there is
    none;
  - runs `update(is_email_verified=True)` where `email__iexact` matches;
  - also sets the in-memory `user.is_email_verified = True`, so a later save can't undo it.
- It runs inside `connect()`, after `wipe_password` (fact 8). So an unverified address still loses
  its password, and other sessions end at their next refresh.
- An access token issued earlier still works for up to 15 min (documented, as with logout).

### `/me`, startup and admin
- `MeSerializer.get_google_connected` →
  `SocialAccount.objects.filter(user=user, provider="google").exists()`.
- Two tests change from 1 to 2 queries: `test_me.py::test_the_fields_for_an_ordinary_user` and
  `test_authentication.py::test_a_valid_token_is_one_query` (renamed). ARCHITECTURE §9 line 809 is
  updated.
- `apps.py` `TOKEN_LIBRARIES` gains `"cryptography.x509"` and `"cryptography.hazmat.backends"`.
  `jwtkit` loads them lazily, which reopens the same cold-start race fixed in Part 2.
- `admin.py`: `admin.site.unregister(SocialApp)` and `admin.site.unregister(SocialToken)`, with a
  comment explaining why.

## Frontend

- **`src/lib/google-identity.ts`** (follows the pattern of `src/lib/turnstile.ts`):
  - `GSI_SCRIPT_URL = "https://accounts.google.com/gsi/client"`, plus minimal `google.accounts.id`
    types;
  - a singleton `loadGoogleIdentity()` that drops a failed script so a later attempt can succeed;
  - `initializeGoogleIdentity(clientId, handler)` calls `initialize({client_id, callback,
    ux_mode:"popup"})` **once per page** (GIS keeps only the last call) and routes the callback
    through a module-level handler that each mount replaces;
  - `resetGoogleIdentityForTests()`.
- **`src/lib/auth/auth-api.ts`:**
  - add `AUTH_PATHS.providerToken = "/auth/app/v1/auth/provider/token"`;
  - add a standalone `googleLogin(idToken, clientId)` that posts `{provider:"google",
    process:"login", token:{client_id, id_token}}` with `{ token: false }` and returns
    `accessTokenFrom(meta.access_token)`.
- **`src/features/auth/GoogleButton.tsx`** (`"use client"`):
  - Props: `context`, `dividerLabel`, `disabled`, `onError(message)`, `onAttempt()`, and an optional
    `clientId` for tests (otherwise `process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID`).
  - With an empty client ID it renders `null`, which hides both the button and the divider.
  - Otherwise it renders a container (`min-h-10`, full width) and `<Divider label={dividerLabel} />`
    below it.
  - The effect clears the container before `renderButton`, so StrictMode's double run doesn't draw
    two buttons. It passes the options above plus `click_listener` → `onAttempt`.
  - `busy`, `disabled`, `onError` and `onAttempt` live in refs that update on every render, because
    GIS keeps the first callback.
  - When a credential arrives and the button is neither busy nor disabled, it:
    1. shows "Signing in with Google…" (`role="status"`);
    2. calls `googleLogin`, then `signInWithToken(token)`;
    3. lets `useRedirectWhenLoggedIn` send the user to `safeNextPath(next) ?? /home`. A Google
       sign-up never goes to `/verify-email`, because it's already verified.
  - A failure calls `onError(googleErrorMessage(error))`. If the script fails to load, it shows an
    inline alert instead.
- **`messages.ts`:**
  - New messages: `googleFailed` ("Google sign-in didn't work. Try again."), `googleUnverified`,
    `accountInactive`, `staffPasswordLogin`, `googleLinkRequiresPassword` and `googleUnavailable`
    ("Google sign-in couldn't load. Check your connection, or use email.").
  - A new `googleErrorMessage(error)` maps the error codes above to those messages, and falls back to
    `bannerMessage` for 429, 503, network and CSRF errors.
- **`LoginForm`:** `<GoogleButton context="signin" dividerLabel="or log in with email" …/>` goes
  between the error banner and the form (as in a3).
- **`SignupForm`:** `<GoogleButton context="signup" dividerLabel="or continue with email" disabled={loading} …/>`
  goes between the banners and the form (as in a2).
- **In both forms:**
  - Google errors use the existing banner `Alert`, and `onAttempt` clears it.
  - The "Google waits for Part 3" comments are removed.
  - a3's uppercase code-font divider becomes the shared `Divider` (a2's style). Recorded as a
    deviation.
- **`playwright.config.ts`:** the webServer envs pin `NEXT_PUBLIC_GOOGLE_CLIENT_ID: ""` and
  `GOOGLE_OAUTH_CLIENT_ID: ""`, so local E2E never loads GIS from Google. CI's env is already blank.
- **No CSP or COOP exists today.** Part 16's CSP must allow GIS (`script-src`/`style-src`/
  `frame-src`/`connect-src` `https://accounts.google.com/gsi/`). COOP must stay unset or be
  `same-origin-allow-popups`. This goes in ARCHITECTURE §12 and the HANDOFF follow-ups.

## Files expected to change

- **Backend:**
  - **New files:**
    - `apps/accounts/google.py`;
    - `apps/accounts/usernames.py`;
    - `apps/accounts/tests/test_google_login.py`;
    - `apps/accounts/tests/test_usernames.py`.
  - **Changed source:**
    - `rumor_zero/settings.py`;
    - `rumor_zero/env_helpers.py`;
    - `apps/accounts/` `middleware.py`, `adapter.py`, `signals.py`, `services.py`,
      `serializers.py`, `apps.py` and `admin.py`.
  - **Changed tests and config:**
    - `conftest.py` (root);
    - `apps/accounts/tests/` `conftest.py`, `test_middleware.py`, `test_me.py`,
      `test_authentication.py`, `test_startup.py` and `test_admin.py`;
    - `apps/core/tests/test_settings.py`;
    - `backend/.env.example` (comments only).
- **Frontend:**
  - **New files:**
    - `src/lib/google-identity.ts` (+ test);
    - `src/features/auth/GoogleButton.tsx` (+ test).
  - **Changed files:**
    - `src/lib/auth/auth-api.ts` (+ test);
    - `src/features/auth/` `messages.ts`, `LoginForm.tsx`, `SignupForm.tsx` and their tests;
    - `playwright.config.ts`;
    - `frontend/.env.example` (comments only).
- **Docs:**
  - `docs/ARCHITECTURE.md` (§2, §3, §7, §9, §10, §12);
  - `docs/ANALYSIS.md` (c-29, b-2, the GoogleButton row);
  - `docs/STRUCTURE.md`;
  - `docs/ENV_GUIDE.md` (§1.6, §1.7);
  - `docs/test-command.md` (Part 3 in both guides);
  - `docs/agents/MEMORY.md`;
  - `docs/agents/HANDOFF.md`;
  - `task.md`.
- **No new dependency, env variable or migration of our own.** allauth's `socialaccount` migrations
  run on `migrate`.

## Non-goals

- `process: "connect"`: linking Google from Settings, and disconnecting it.
- One Tap, `auto_select` and the FedCM button.
- The Settings "Signed in with Google" status (Part 14).
- Username rename (Part 14).
- Notification emails.
- CSP and COOP headers (Part 16).
- Caching Google's certificates (Part 16).
- An E2E test against real Google.

## Ordered steps

1. (Done when the plan was approved: it was saved here and linked from HANDOFF.) When you start, set
   HANDOFF to "Part 3 in progress".
2. Backend: settings, the env helper and `INSTALLED_APPS`. Run `python manage.py migrate` locally.
   `makemigrations --check --dry-run` must stay clean.
3. `usernames.py` and its tests.
4. `google.py` (the request pre-check) and the middleware wiring: allow-list, issuing set, 404 when
   disabled, `login` rate limit and the mismatch warning.
5. `SocialAccountAdapter`, then the signal receiver and service, `/me`, `TOKEN_LIBRARIES` and the
   admin unregistering.
6. Backend tests (listed below), then `ruff check --fix . ; ruff format .`.
7. Frontend: `google-identity.ts`, `googleLogin`, `GoogleButton`, the messages, both forms, the
   Playwright env, and their tests.
8. Docs:
   - **ARCHITECTURE:**
     - §2: `is_email_verified` is true for Google sign-ups and for linked accounts;
     - §3: the provider-token rate limit;
     - §7: settings, the endpoint row, the allow-list sentence, the Google flow row, the linking rules
       (authoritative email, staff, inactive, wipe), the pre-check, the data that's kept, and the
       clock-skew note;
     - §9: `/me` takes two queries and returns `google_connected`;
     - §10: `GoogleButton`;
     - §12: CSP and COOP for GIS.
   - **ANALYSIS:** c-29 and b-2 (username from the first name; your decision of 2026-10-07), and the
     `GoogleButton` row.
   - **Smaller docs:**
     - the STRUCTURE markers;
     - ENV_GUIDE §1.6 and §1.7: wording only, no new variable, plus a clock-sync tip;
     - the comments in both `.env.example` files;
     - `docs/test-command.md`: a Part 3 section in both guides (Linux and Windows);
     - MEMORY: facts 1–11.
   - `task.md` (criteria, deviations, both status spots) and HANDOFF.
9. Run the full validation, then stop.

## Tests

**Backend.** Google is mocked with no network access:
- The root `conftest._hermetic` pins `GOOGLE_OAUTH_CLIENT_ID` and `SOCIALACCOUNT_PROVIDERS` to a test
  client ID. It also replaces `DefaultSocialAccountAdapter.get_requests_session` with one that
  refuses network access.
- A `google` fixture in `tests/conftest.py` creates an RSA key and a self-signed certificate and
  serves `{kid: pem}` through that fake session. It signs real RS256 ID tokens, so allauth's own
  `aud`, `iss`, `exp`, signature and `jti` checks run unpatched.

`test_google_login.py`:
- **New user.** 200, with both cookies set and no secrets in the body. The user has:
  - a username generated from `given_name`;
  - `is_email_verified` set, and a verified primary `EmailAddress`;
  - an unusable password and a blank display name;
  - a `SocialAccount` whose `extra_data` keeps only the four claims;
  - `/me.google_connected` = true.
- **Existing verified `@gmail.com` user** (the test creates a verified `EmailAddress`): the **same**
  account, and the password still works.
- **Existing unverified user:** the same account. The password is now unusable, the email is
  verified, and the old `rz_refresh` returns 400 at its next refresh.
- **Workspace (`hd`) address:** links.
- **Non-authoritative address that matches an existing user:** 400 `google_link_requires_password`,
  with no link and no wipe. The same address as a **new** user signs up fine.
- **Staff match by email:** 400 `staff_password_login`.
- **Staff user who already has a Google link:** logs in.
- **Inactive match:** 400 `account_inactive`, with no link and no wipe.
- **Returning user** (`uid` match, even with a changed Google email): logs in.
- **Tokens rejected with 400:**
  - wrong `aud`, expired token, wrong `iss`, `iat` in the future;
  - forged (signed with another key), unknown `kid`, replayed `jti`;
  - `alg` HS256 or `none`, or no `kid`;
  - a malformed token, or a failure while fetching the certificates.
- **400 `google_email_unverified`:** `email_verified=false`, or no email at all. No user is created.
- **Malformed requests:** a `client_id` mismatch (logged without the value), the wrong provider,
  `process: "connect"` or a missing token → 400.
- **Disabled** (blank client ID) → 404.
- **Stale credentials:** a stale Bearer token is ignored, and logging in again revokes the old
  cookie's session.
- **Rate limit:** the 31st attempt within a minute → 429.

Other backend test files:
- **`test_usernames.py`:**
  - each rule: "Ada", a taken name, "José", "Mary-Jane", a long name, "Admin", "Al", "李", an empty
    name, and the trailing-`_` cut;
  - every output matches the pattern and is never reserved;
  - when every candidate is taken, the fallback is `member_…`;
  - a seeded `rng` gives deterministic results.
- **Updates to existing tests:**
  - `test_middleware`: `UNSAFE_ENDPOINTS` and the CSRF matrix; the new allauth paths in
    `test_only_the_allow_listed_endpoints_answer`; 404 when disabled.
  - `test_me` and `test_authentication`: two queries, and `google_connected` true/false.
  - `test_startup`, `test_admin`.
  - `apps/core/tests/test_settings.py`: the client-ID guard, with `production_env` including the
    variable.

**Frontend.** Simulated GIS callbacks are wrapped in `act()`.
- **`google-identity.test.ts`:** only one script tag; load, error and a retry after an error;
  `initialize` runs once.
- **`GoogleButton.test.tsx`:**
  - hidden without a client ID; the button and divider show with one;
  - `renderButton` gets the options above, and a remount doesn't draw a second button;
  - a credential goes to the API with the right body, then to `signInWithToken`, while the busy
    state shows; duplicate credentials, and credentials arriving while `disabled`, are ignored;
  - each error maps to its message, the load-failure alert shows, and `click_listener` clears the
    error.
- **`auth-api.test.ts`:** `googleLogin` uses the right path, body and headers, and sends no Bearer
  token.
- **`LoginForm.test.tsx` and `SignupForm.test.tsx`:** the "no Google text" assertions become "hidden
  without a client ID" and "shown with one". A Google sign-up does not go to `/verify-email`.

**E2E:** none for real Google (task.md). The existing suite must still pass with the button hidden.

## Validation (exact commands; record the results in HANDOFF)

- **Backend** (`backend/`, venv active, `docker compose up -d`): `python -m pytest`, `ruff check .`,
  `ruff format --check .`, `python manage.py makemigrations --check --dry-run`,
  `python manage.py check`.
- **Frontend** (`frontend/`): `npm run lint`, `lint:tokens`, `typecheck`, `format:check`, `npm test`,
  `npm run build`, `npm run test:e2e`.
- **curl against `runserver`** (record in test-command.md):
  - 404 when disabled (`GOOGLE_OAUTH_CLIENT_ID=` set in the process env);
  - 403 without `Origin` or the `X-Requested-With` header;
  - 400 for a garbage token and for an HS256 token;
  - 429 after 30 attempts.
- **Browser** (Playwright script, at 1280 and 390 px):
  - with a fake `window.google`, the button and divider sit next to Stitch a2/a3;
  - with a blank env the button is hidden;
  - 0 px horizontal overflow.
- **Manual, by you** (acceptance criterion 4; needs a real Google account), on
  `http://localhost:3000` with your client ID:
  - a new Google user ends up on `/home`, verified, with a generated username;
  - the Gmail address of an existing password account signs into that same account;
  - a closed popup changes nothing.

  If you get 400 `invalid_token`, check the clock sync (`timedatectl`). The steps go in
  test-command.md.

## Stop conditions

- **Stop and ask if:**
  - allauth behaves differently from facts 1–11 at runtime;
  - a new dependency or service seems to be needed;
  - GIS can't render inside the card without breaking the 390 px layout;
  - a fix would touch another part's scope.
- **The part is done** when:
  - every required test and check passes;
  - the docs and `task.md` are updated;
  - HANDOFF records the results.

  Criterion 4 stays "pending your manual check" until you report it.

## Follow-ups (not in this part)

- **Part 14:**
  - Settings shows "Signed in with Google";
  - usernames can be renamed;
  - a "Google connected" email and a password-changed email;
  - Google-only users set a password via Forgot password.
- **Part 16:**
  - CSP and COOP for GIS;
  - cache Google's certificates (each sign-in fetches them now);
  - handle IntegrityError races (username or email) with a retry or a 409.
- **Part 10:** a read-only `SocialAccount` admin for moderators.
