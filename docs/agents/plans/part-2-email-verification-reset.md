# Plan: Part 2, Email verification & password reset

- **Status:** APPROVED by the user (Sanjoy Rozario) on 2026-10-07, together with the decisions
  below. **IMPLEMENTED 2026-10-07** (Claude, Sonnet 5.5). Deviations: see `task.md` Part 2 and
  `docs/agents/HANDOFF.md` (the `ready()` preload of allauth's deferred libraries, the tinted waiting
  Resend button, "Forgot password?" in a3's options row, `e2e/helpers.ts`).
- **Drafted:** 2026-10-06/07 by Claude (Opus 5.5), with a separate review pass against the code
  whose findings are folded in. **Implement with:** Sonnet 5.5 · high (task.md).
- **Evidence:** allauth 65.19.5 and Django 5.2 behaviour read in the installed source under
  `backend/.venv/lib/python3.13/site-packages/`; Next 16.3.8 param handling read in
  `frontend/node_modules/next/dist/`.

## Context

Part 1 shipped sign-up/login/refresh/logout and stores `is_email_verified` but never sets it:
- the allauth verify and reset endpoints are 404 behind `AuthApiMiddleware`'s allow-list;
- nothing listens to `email_confirmed`;
- the emails are allauth's defaults ("Hello from localhost:8000!");
- there are no a4/a5/a6 pages.

Part 2 completes guide §4.3: link verification (24 h), resend, and forgot/reset password with no
account enumeration. It also adds branded emails and an E2E mailbox.

**Dependencies:** Part 2 depends only on Part 1 = `[x] Done (2026-10-03)`; its chain (0A, 0B, 0D,
0C) is Done. Workspace: HEAD `353ee19`, clean, in sync with `origin/main`.

## Decisions

**User (2026-10-06):**
1. **Sign-up lands on `/verify-email`** (a4), not `/home`.
   - "Continue browsing read-only" → `safeNextPath(next) ?? /home`.
   - This replaces ARCHITECTURE §7's "→ /home with the banner".
2. **New post is `aria-disabled` for unverified users** (rail and bottom tab).
   - The button stays focusable.
   - A click shows a toast: "Verify your email to post. Check your inbox, or resend the link from
     the banner."
   - It becomes active once the user is verified.
3. **Email limits.**
   - Verification email cooldown: 1 per 60 s per address (matches the countdown). Plus a daily cap
     of 10 resends per address.
   - Reset requests: allauth's per-minute limits, plus 10/day per address and 50/day per IP.
4. **Unknown addresses get no email:** `ACCOUNT_EMAIL_UNKNOWN_ACCOUNTS = False`.
   - The HTTP answer stays identical.
   - A small timing difference is accepted: sign-up already reveals taken emails, behind Turnstile.

**Technical (mine; review at approval):**

5. **Daily caps are separate allauth actions.**
   - allauth keys a rate's history only by action and "per" type (`core/internal/ratelimit.py`
     `get_cache_key`). So `"1/60s/key,10/1d/key"` shares one list, and the minute rate prunes what
     the day rate needs. A simulation let 20 of 20 resends through.
   - `ACCOUNT_RATE_LIMITS` therefore gains:
     - `"confirm_email": "1/60s/key"` and `"confirm_email_daily": "10/1d/key"`
     - `"reset_password": "20/m/ip,5/m/key"` and `"reset_password_daily": "50/1d/ip,10/1d/key"`
     - `"reset_password_from_key": "20/m/ip"` (pinned)
   - allauth merges extra keys, and `allauth.core.ratelimit.consume` reads them.
   - Rule for later parts: never repeat a "per" type inside one action.
6. **Resend is our own endpoint:** `POST /api/v1/me/verification-email/` (DRF, `IsAuthenticated`).
   - Answers: 204 sent · 409 `already_verified` · 429 `verification_email_throttled`.
   - Why not the documented `auth/email/verify/resend`: it is allauth's code-mode view and always
     answers 409 with links.
   - Why not the link alternative `PUT account/email`: it exposes the whole email-management view,
     answers a bare 403 when throttled, mails a dead link for an already-verified address, and as an
     `/auth/` call gets no 401 refresh.
7. **Verify always runs anonymous and is normalised.**
   - The middleware drops `Authorization`/`X-Session-Token`.
   - allauth's success-without-login **401** becomes `200 {"status":200}`.
   - Errors stay allauth's 400 (`invalid_or_expired_key`, `email_taken`).
   - A link never logs anyone in (`ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION` stays False).
8. **Reset key pre-check:** `GET auth/password/reset` with the `X-Password-Reset-Key` header is
   allow-listed and forwarded by the relay. A dead link then shows the expired state before the user
   types a password.
9. **Reset links last 24 h:** `PASSWORD_RESET_TIMEOUT = 86400` (Django's default is 3 days). This
   matches Stitch a5 ("Links expire in 24 hours") and the verification link.
10. **Other sessions after a reset.**
    - No eager sweep: DB sessions aren't indexed by user.
    - Every other refresh token fails on its next use, because Django's `get_user` flushes a
      session whose auth hash no longer matches. Verified through `RumorZeroJWTTokenStrategy`;
      `test_refresh_fails_once_the_password_changes` already pins it.
    - This browser's previous session is deleted by the middleware: reset joins
      `_ISSUING_ENDPOINTS`, which revokes the old cookie's session only when a new refresh token
      was issued.
    - As with logout (§7), an access token already issued stays valid for up to 15 min.
11. **Templates go in `backend/templates/account/email/`.** `allauth` precedes `apps.accounts` in
    `INSTALLED_APPS`, so app templates would be shadowed. allauth ships only `.txt`; we add `.html`.
12. **Pin `ACCOUNT_PREVENT_ENUMERATION = True`.** It is already the default, but no-enumeration
    depends on it: with False, the reset form raises `unknown_email`.

## allauth 65.19.5 / Next 16 facts this relies on (read in the installed source)

- **Verify key.**
  - Format: `signing.dumps(EmailAddress.pk, salt="account")` = `<b64>:<b62 ts>:<sig>`.
  - Checked with `max_age = EXPIRE_DAYS × 86400` and `verified=False`, so expired, used and forged
    keys all give `invalid_or_expired_key`.
  - `activate_url` percent-encodes `:` as `%3A`.
  - Next 16.3.8 re-encodes every route param (`get-dynamic-param.js` `getParamValue`). The page
    therefore always decodes once.
- **`POST auth/email/verify`** with no pending stage (none can exist once the headers are dropped):
  verifies, sends `email_confirmed(request, email_address)`, answers 401 when anonymous. No rate
  limit.
- **`POST auth/password/request`.**
  - Answers `200 {"status":200}` for existing, unknown, inactive and unverified addresses alike.
  - The rate key is the lowercased cleaned email; `ip` is `REMOTE_ADDR`.
- **Reset key.**
  - Format: `<uuid hex>-<ts>-<hash>`.
  - Single use: the hash covers the password, `last_login` and the user's emails.
  - Expiry is checked against `PasswordResetTokenGenerator._now()` (`datetime.now()`), not
    `time.time()`.
- **`GET auth/password/reset`** (header): 200 `{data.user}` or 400 `invalid_password_reset`. Not
  rate limited.
- **`POST auth/password/reset {key, password}`.**
  - Errors: 400 `invalid_password_reset` (param `key`), or validator codes (param `password`).
  - Success when called anonymously: 200 with `meta.access_token`, `refresh_token` and
    `session_token`.
  - The automatic login runs our `AccountAdapter.login`.
- **Resend from a DRF view.**
  - `send_verification_email_for_user(request._request, user)` works.
  - But it calls `adapter.add_message`, which returns early only for headless-marked requests. With
    `django.contrib.messages` installed, that would set a `messages` cookie on the frontend origin.
- **Templates.**
  - `email_confirmation_signup_*` `{% include %}` the `email_confirmation_*` ones.
  - Every allauth email extends `base_message.txt` through `block content` (directly or via
    `base_notification.txt`).
  - `<prefix>_message.html` becomes the HTML alternative when it exists.
  - `base_message.txt` prints the API Host, because `django.contrib.sites` isn't installed.

## Backend

**Settings** (`backend/rumor_zero/settings.py`):
- decision 5 limits;
- `ACCOUNT_EMAIL_UNKNOWN_ACCOUNTS = False`;
- `ACCOUNT_PREVENT_ENUMERATION = True`;
- `PASSWORD_RESET_TIMEOUT = 24 * 3600`.

No new env variable and no new dependency.

**Middleware** (`apps/accounts/middleware.py`):
- New constants `VERIFY_EMAIL_PATH`, `PASSWORD_REQUEST_PATH`, `PASSWORD_RESET_PATH`.
- `ALLAUTH_ENDPOINTS`: verify `{"POST"}`, request `{"POST"}`, reset `{"GET","POST"}`.
- **Always-anonymous set** (today's `_TOKEN_ENDPOINTS`, renamed): add verify, request and reset.
  - Move the header drop **above** the safe-method early return. Otherwise a GET carrying a stale
    Bearer gets allauth's 410.
- `_ISSUING_ENDPOINTS` += reset.
- **Reset daily cap.**
  - `_before`, `POST` request path: parse `email` from the JSON body. When it is a string, run a
    dry-run `consume(action="reset_password_daily", key=email.strip().lower())`. A full bucket →
    `error_response(429)`, the same shape as allauth's.
  - Skip the check when `email` is missing or not a string: a per-key rate with `key=None` raises,
    and allauth answers 400 anyway.
  - `_after`: consume for real only on a 200.
- **Verify normalisation.** In `_after`'s body block, right after `extract_tokens`: a `POST` to
  verify that got 401 → `status_code = 200`, body `{"status": 200}`. Mutate the response so other
  middleware's headers stay.
- CSRF on POST, secret stripping, setting the cookie from the body and `no-store` already apply.

**Adapter** (`apps/accounts/adapter.py`):
- `add_message()` does nothing. Headless-only shows no Django messages, and this stops the
  `messages` cookie.
- `send_mail` adds `frontend_origin` and `email_logo_url = FRONTEND_ORIGIN + "/brand/email-logo.png"`
  to the context, and keeps its failure handling.

**Services** (`apps/accounts/services.py`, new):
- `mark_email_verified(email_address)`: one query,
  `User.objects.filter(pk=email_address.user_id, email__iexact=email_address.email).update(is_email_verified=True)`.
- `resend_verification_email(request, user) -> "sent" | "already_verified" | "throttled"`, in order:
  1. If the flag is set, return "already_verified".
  2. If the user's `EmailAddress` is already verified, set the flag and return "already_verified".
     A link would be dead anyway.
  3. Dry-run `confirm_email_daily`.
  4. Call `send_verification_email_for_user()` (internal allauth API → MEMORY's re-check list). It
     returns False under the 60 s cooldown.
  5. On True, consume `confirm_email_daily`.

  The sign-up email doesn't count towards the daily cap.

**Signals** (`apps/accounts/signals.py`, new): an `email_confirmed` receiver calls
`mark_email_verified`. It is connected in `AccountsConfig.ready()`.

**Resend view** (`views.py`, `urls.py` → `v1/me/verification-email/`):
- A 429 uses our `{"detail","code"}` envelope with no `Retry-After`, because the bucket can be the
  minute one or the day one.
- Copy: "We sent one recently. Wait a little before asking again."

**Sentry** (`rumor_zero/sentry.py`): add `x-password-reset-key` to `EXTRA_DENYLIST`. An error
during the GET would otherwise send a live key.

**Templates** (`backend/templates/account/email/`):
- `.txt` files use `{% autoescape off %}`. `.html` files use `<!DOCTYPE html>` (no XHTML `xmlns`
  URL), table layout and inline styles, with every line under 998 characters (longer lines make
  Django quoted-printable-encode that part).
- `base_message.txt` keeps `block content`, so any unoverridden allauth email still renders, without
  the backend host.
- `base_message.html` layout:
  - the logo `<img src="{{ email_logo_url }}" alt="Rumor Zero" width="160">` in an
    `inverse-surface` `#283044` cell;
  - body on `#ffffff`, text `#131b2e`/`#3c4946`;
  - button `secondary` `#006398` on `#ffffff`.

  The hex values are copied from the Stitch tokens, because email clients can't read CSS variables.
- Verification:
  - `email_confirmation_subject.txt` "Verify your email" and `email_confirmation_message.{txt,html}`;
  - the `email_confirmation_signup_*` variants use "Welcome to Rumor Zero" wording.
- Reset: `password_reset_key_subject.txt` "Reset your password" and
  `password_reset_key_message.{txt,html}` (expires in 24 h; "If you didn't ask, ignore this email").
- Copy says only "Rumor Zero": no organisation names, no site domain. Every link uses
  `FRONTEND_ORIGIN`.

**Admin:** fix the `admin.py` comment. Part 2 adds no admin action; "mark email verified" becomes a
Part 10 follow-up.

## Frontend

**API** (`src/lib/auth/auth-api.ts`, standalone exports, **not** added to the `AuthApi` type, whose
three test fakes would break):
- `verifyEmail(key)`, `requestPasswordReset(email)`, `checkResetKey(key)` (GET with the header) and
  `resetPassword(key, password)` → access token. All use `token: false`.
- `resendVerificationEmail()` is a normal app call (Bearer, retried after a 401 refresh).

**Keys** (`src/lib/auth/email-key.ts`, new):
- Always decode the route param once, in `try/catch`.
- Then match a strict format: verify `^[A-Za-z0-9_:-]{1,300}$`, reset `^[0-9a-z-]{1,200}$`.
- A failure shows the invalid state without a request. A non-Latin-1 header value would otherwise
  make `fetch` throw, which reads as "network error".

**Session** (`session.ts`, `AuthProvider.tsx`):
- New public `signInWithToken(token)` wraps the private `signIn`, for reset. `acceptToken` is
  already a private name.
- Add `{type:"user-changed"}` to `AuthMessage`.
- Split `reloadMe()`: a private `loadMe()` that never posts, and the public `reloadMe()` =
  `loadMe()` + post.
- `onMessage` becomes an explicit `switch`: "user-changed" → `loadMe()` only while authenticated.
  This avoids an echo loop, and stops anonymous tabs treating it as "login".

**`next-path.ts`:** block `/reset-password` and `/verify-email/` (key-bearing) as `next` targets.
`/verify-email` itself stays allowed.

**`relay.ts`:** add `x-password-reset-key` to `REQUEST_HEADER_ALLOWLIST`.

**Hook** (`features/auth/useResendVerification.ts`):
- sends the request;
- runs the 60 s countdown (from mount when asked, after a send, and after a 429);
- writes an `aria-live` status;
- uses messages from `messages.ts`.

**Pages** (all in `(auth)`, AuthLayout card, thin route files). Key pages pass the raw param to a
client component and set `robots: {index:false}`.

- **`/verify-email` → `VerifyEmailPending` (a4).** Never redirected away.

  | Visitor | Shows |
  |---|---|
  | Signed in, unverified | "We sent a verification link to **{email}**"; info callout "Read-only for now: verify to post, comment and report"; Resend with a countdown starting at 60 s; spam hint; "Continue browsing read-only →"; footer "Links expire 24 hours after they're sent" |
  | Signed in, verified | "Your email is verified" + "Start posting" |
  | Anonymous | check-your-inbox copy + "Log in to resend" → `/login?next=/verify-email` |

- **`/verify-email/[key]` → `VerifyEmailStatus`.**
  - It waits for the session to leave `loading`, then **always** POSTs once per key. A ref guards
    against StrictMode's double effect.
  - States:

    | State | Shows |
    |---|---|
    | Verifying | "Verifying…" |
    | Verified | `reloadMe()`; "Start posting" → `/home` (anonymous: "Log in to start posting") |
    | 400, signed in and already verified | "Your email is already verified" |
    | Other 400 (expired or invalid) | "Send a new link": inline resend when signed in, anonymous → `/login?next=/verify-email` |

- **`/forgot-password` → `ForgotPasswordForm` (a5).**
  - **Idle** (email, "Send reset link →", "Back to log in") and **sent** are separate states.
  - Every 200 shows the same sent text: "If an account exists for {typed email}, we've sent a link
    to reset your password. It expires in 24 hours."
  - Errors: malformed email (field), 429, 503 waking, network.
- **`/reset-password/[key]` → `ResetPasswordForm` (a6).**
  - It starts in a checking state (skeleton).
  - The form has:
    - new password with `PasswordStrengthMeter`;
    - confirm field;
    - show/hide toggles;
    - "Use at least 8 characters";
    - a callout "This also signs you out on your other devices";
    - submit "Reset password & log in →".
  - States:
    - **mismatch**: error on the confirm field;
    - **weak**: the 8-character client check, plus server errors with param `password`;
    - **expired**: alert + "Request a new link" → `/forgot-password`;
    - **success**: `signInWithToken`, a toast "Password changed. You're logged in.", then `/home`.
- **Copy** follows ANALYSIS b/e. Drop:
  - the emblem tiles;
  - "Secured Node", "Protocol standard", audit IDs and fabricated emails;
  - the a4 state switcher and "Simulate link click".

  a6's "12 characters" becomes 8.

**Existing components:**
- **`LoginForm`:** a "Forgot password?" link (a3:93 classes) in the password label row.
- **`SignupForm` + `useRedirectWhenLoggedIn`:**
  - A `submitted` ref is set just before `await signup()` and cleared in `catch`.
  - The hook takes `{ skip }` and does nothing while it is set.
  - On success: `router.replace("/verify-email" + (safe ? "?next=" + encodeURIComponent(safe) : ""))`.
  - An already-signed-in visitor still goes to `next ?? /home`.
- **Shell stays presentational.** `AppShell.test` renders it without the Auth/Toast providers.
  - `(app)/layout.tsx`, which already uses `useAuth` and `useToast`, owns `useResendVerification`
    and the toasts.
  - It passes `AppShell` an `onNewPostBlocked` callback and resend props (`onResend`,
    `secondsLeft`, `busy`) for a presentational `UnverifiedBanner` with a Resend button.
  - `Sidebar`/`MobileNav` read `user.is_email_verified`, which `ShellUser` already has.
  - New post gets:
    - `aria-disabled`;
    - an `aria-describedby` hint with a separate id for the rail and the tab, since both are in the
      DOM;
    - `aria-disabled:cursor-not-allowed aria-disabled:opacity-60`, with the hover colour switched
      off (`lint:tokens` doesn't check opacity or cursor classes).

## Files expected to change

- **Backend, new:** `apps/accounts/{services,signals}.py`; `backend/templates/account/email/`
  (`base_message.{txt,html}`, `email_confirmation{,_signup}_{subject.txt,message.txt,message.html}`,
  `password_reset_key_{subject.txt,message.txt,message.html}`); `apps/accounts/tests/`
  `test_{email_verification,resend_verification,password_reset,emails}.py`.
- **Backend, changed:** `rumor_zero/{settings,sentry}.py`; `apps/accounts/{middleware,adapter,apps,
  views,urls,admin}.py`; `apps/accounts/tests/test_middleware.py` (+ `conftest.py` helpers as
  needed); `apps/core/tests/{test_settings,test_sentry}.py`.
- **Frontend, new:** `src/lib/auth/email-key.ts`; `src/features/auth/{useResendVerification.ts,
  VerifyEmailPending.tsx,VerifyEmailStatus.tsx,ForgotPasswordForm.tsx,ResetPasswordForm.tsx}`;
  `src/app/(auth)/{verify-email,verify-email/[key],forgot-password,reset-password/[key]}/page.tsx`;
  tests next to each; `e2e/{mailbox.ts,email-flows.spec.ts}`.
- **Frontend, changed:** `src/lib/auth/{auth-api,session,AuthProvider,next-path}.ts(x)`,
  `src/lib/api/relay.ts`, `src/features/auth/{LoginForm,SignupForm,useRedirectWhenLoggedIn,
  messages}.ts(x)`, `src/app/(app)/layout.tsx`, `src/components/shell/{AppShell,Sidebar,MobileNav,
  UnverifiedBanner}.tsx`, their tests, `e2e/auth.spec.ts`, `playwright.config.ts`.
- **Docs:** `docs/ARCHITECTURE.md`, `task.md`, `docs/STRUCTURE.md`, `docs/test-command.md`,
  `docs/agents/{MEMORY,HANDOFF}.md`.

## E2E and CI

- **`playwright.config.ts`:** the Django webServer env gets `EMAIL_PROVIDER: "file"`.
  - Playwright merges it over `process.env`, and `.env` never overrides process env.
  - The backend creates `backend/tmp/mail/` (git-ignored).
  - CI needs no workflow change.
  - Locally, a reused `runserver` must use `file` too. The helper's timeout message says so.
- **`e2e/mailbox.ts`** (new): poll `backend/tmp/mail/*.log` for up to 15 s. Match the `To:` line for
  the test's unique address, and take the first `http://localhost:3000/(verify-email|reset-password)/…`
  link from the plain-text part, which comes first and isn't encoded.
- **`e2e/auth.spec.ts`:** `signUp()` now expects `/verify-email`, then "Continue browsing read-only"
  → `/home` + banner.
- **`e2e/email-flows.spec.ts`** (new):
  1. Sign up → New post is `aria-disabled` → read the email → open the link → verified → "Start
     posting" → banner gone, New post enabled.
  2. Forgot password → sent → read the email → mismatch error → reset → `/home` logged in → log out
     → log in with the new password.

## Docs

- **ARCHITECTURE:**
  - §3: the limits, and the "never repeat a per type" rule;
  - §7: settings, the endpoint table (verify normalisation, resend), the allow-list, the flows (Sign
    up, Verify, Forgot/reset, Stay logged in), the reset session rule;
  - §9: index row 2 and the resend payload;
  - §10: banner Resend, New post gating, the new auth pages, blocked `next` prefixes, the relay
    header;
  - §12: Sentry denylist;
  - §14: email placement, and the note on hex values in emails.
- ANALYSIS: no D-decision changes.
- `task.md` Part 2: the endpoint line, criteria, deviations, both status spots.
- `STRUCTURE.md` markers.
- `docs/test-command.md`: a Part 2 section, Linux and Windows (`bash -n` the Linux blocks).
- **MEMORY:** allauth link-mode facts (verify 401 + normalisation, `%3A` + Next re-encoding,
  code-only resend, the shared rate-limit key, template shadowing, the Host in `base_message`,
  `add_message` cookie, deprecated cooldown setting).
- HANDOFF.

## Ordered steps

1. Save this plan to `docs/agents/plans/` and link it in HANDOFF (owner, phase).
2. **Backend settings, middleware, Sentry, and their tests.**
   - Update `test_middleware.py`: its 404 cases for verify/request become other unlisted paths
     (`auth/email/verify/resend`, `account/email`), and `UNSAFE_ENDPOINTS` grows.
   - Update `apps/core/tests/test_settings.py` and `test_sentry.py`.
3. Adapter, services, signals, resend view/URL, and tests.
4. Templates and email tests (including anymail's test backend).
5. Verify/reset API tests. Run `pytest`, `ruff check .`, `ruff format --check .`,
   `makemigrations --check --dry-run`.
6. Frontend lib (auth-api, email-key, session, next-path, relay) and unit tests.
7. **Frontend screens and shell.**
   - Hook, the four page components and their routes; LoginForm, SignupForm/hook, layout, shell and
     banner changes, with tests.
   - Run lint, lint:tokens, typecheck, format:check, `npm test`, `npm run build`.
8. Playwright config, mailbox helper and specs. `npm run test:e2e` in dev mode and in CI mode.
9. **Manual checks**, recorded in `test-command.md`:
   - curl;
   - browser at 1280 and 390 px against Stitch a4/a5/a6.
10. Docs, task.md, MEMORY, HANDOFF; then stop.

## Tests (required list → where)

**Backend** (`apps/accounts/tests/`; settings in `apps/core/tests/`):

- **`test_email_verification.py`**
  - The sign-up email link (`%3A`-encoded) → POST with the decoded key → 200.
  - `EmailAddress.verified` and `is_email_verified` are true; the IsEmailVerified test view now
    answers 201.
  - Reuse → 400. Forged key → 400.
  - Expiry: build the key with `signing.TimestampSigner.timestamp` patched, so it was signed
    86 401 s ago → 400; signed 86 399 s ago → 200.
  - A Bearer for another user is ignored. CSRF → 403.
  - The receiver ignores an address that differs from `user.email`.
- **`test_resend_verification.py`**
  - 204 + the non-sign-up template.
  - Within 60 s of sign-up → 429; at 61 s → 204 (clock fixture as in `test_tokens.py`).
  - The 11th resend in a day → 429.
  - Verified → 409, no email. Address verified but flag off → flag set + 409.
  - Anonymous → 401.
  - The response has no `Set-Cookie`.
- **`test_password_reset.py`**
  - Existing, unknown and inactive addresses get identical status **and bytes**; only the existing
    one gets an email.
  - A malformed email → 400 for all three.
  - 6th per minute for one address → 429; 11th per day for one address and 51st per day for one IP
    → 429; a 400 doesn't count.
  - GET key check → 200/400.
  - POST success: access token in the body, both cookies set, no refresh or session token in the
    body.
  - Another client's old refresh cookie → 400. This browser's previous session is deleted.
  - Key reuse → 400.
  - Expiry with `PasswordResetTokenGenerator._now` patched (naive `datetime`): +86 401 s → 400,
    +86 399 s → 200.
  - Weak password → param `password`. Bad key → param `key`. `Authorization` ignored on GET and
    POST.
- **`test_emails.py`**
  - Subject `[Rumor Zero] …`; From = `DEFAULT_FROM_EMAIL`.
  - Text plus HTML alternative.
  - Every `http(s)://` URL and every `href`/`src` starts with `FRONTEND_ORIGIN`; no backend host.
  - The logo `<img>` (alt, width 160) appears only in the HTML.
  - The same email through `anymail.backends.test.EmailBackend`: the Brevo configuration test.
- **Updated:** `test_middleware.py`, `apps/core/tests/test_settings.py` (limits, unknown accounts,
  prevent enumeration, reset timeout), `apps/core/tests/test_sentry.py`.

**Frontend:**
- Component tests for the four screens, every state above.
- Banner Resend and countdown (fake timers).
- New post gating (aria, hint, blocked callback) in the Sidebar, MobileNav and AppShell tests.
- LoginForm link; SignupForm → `/verify-email` with `next`, and an already-signed-in visitor →
  `next ?? /home` (update `SignupForm.test.tsx:127-140`).
- `email-key`, `next-path`.
- Session `signInWithToken`, and the two-tab "user-changed" test: one `/me` fetch, no echo.
- auth-api calls: URLs, headers, no Bearer.
- The relay forwards `x-password-reset-key`.

**E2E:** the two flows above, plus the updated Part 1 spec.

## Verification (definition of done)

- **Backend:** `cd backend`, then:
  - `python -m pytest` (all pass, more than 440 tests);
  - `ruff check .`;
  - `ruff format --check .`;
  - `python manage.py makemigrations --check --dry-run`;
  - `python manage.py check`.
- **Frontend:** `cd frontend`, then `npm run lint`, `lint:tokens`, `typecheck`, `format:check`,
  `npm test` and `npm run build`.
- **E2E:** `npm run test:e2e` (Playwright starts Django with `EMAIL_PROVIDER=file`), in dev mode and
  in CI mode.
- **Manual:**
  - The console email link verifies, and the banner disappears.
  - An expired link shows the expired state, and resend works.
  - Forgot-password answers are identical for an existing and an unknown address (diff of
    `curl -i`).
  - Reset logs you in, and another browser's refresh then fails.
  - Emails' From, every link and the logo point at `http://localhost:3000`.
- **CI:** green after the user pushes (user-reported).

## Stop conditions

- A required test, lint or type check still fails for a non-obvious reason after one fix attempt:
  record it in HANDOFF and stop.
- allauth or Next behaves differently from the facts above (for example verify isn't 401
  anonymous, reset issues no tokens, or the param arrives double-encoded): stop and re-plan; don't
  patch around it.
- Anything that needs a new dependency, service or env variable (including a time-mocking
  library): ask first.
- **Done** = criteria ticked, docs updated, HANDOFF has the commands and their results. Then stop;
  Part 3 isn't started.

## Out of scope / follow-ups

- Admin action "mark email verified" (Part 10, logged).
- Marking the email verified on password reset (it proves the inbox; not asked for).
- Password-changed notification email (Part 14, with change password).
- `clearsessions` (Part 9/17).
- A provider failure on resend still answers 204, because the adapter swallows send errors; sign-up
  behaves the same.
