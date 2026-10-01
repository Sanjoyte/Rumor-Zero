# Plan: Part 0C, App shell, API relay, API client, CI

- **Status:** DONE 2026-10-01. Implemented by Claude (Opus 5.5) and validated locally. CI went green
  on `60cfffc`, after one fix: an `esbuild` devDependency for OpenNext (task.md 0C). Approved by the user on
  2026-10-01 together with the deviations below. Small extra deviations made while implementing are
  listed under Part 0C in `task.md` (e.g. the top-bar search keeps b1's compact input instead of
  `TextField`). The steps below are kept as the record of what was approved.
- **Drafted:** 2026-10-01 by Claude (Opus 5.5), with a separate design-review pass. **Implement
  with:** Sonnet 5.5 · high (task.md).
- **Depends on:** 0A, 0B and 0D, all `[x] Done` in both task.md status locations. The git tree was
  clean at planning time (`bd05636`).

## Context

0C builds four things:
- **The API relay.** The browser calls `/api/*` on the frontend origin, and the relay forwards it to
  Django. This is the core of the free single-origin topology (ANALYSIS d).
- **The base API client and auth skeleton.** Part 1 completes them.
- **The three page layouts.** The app shell, the auth card and the marketing nav/footer, with
  `<Logo/>` in every brand spot (ARCHITECTURE §14).
- **CI.** Backend, frontend and E2E jobs, including the OpenNext build on Linux.

After 0C, every later part can call `/api/...` and render inside a layout.

## User decisions (asked 2026-10-01)

1. **Logged-out app shell: reduced nav.**
   - Shown: Home and Search, with Log in / Sign up where the user card goes. The top bar shows a Log in
     link instead of the avatar.
   - Hidden: Notifications, Profile, Bookmarks, New post, Moderation and Settings.
2. **Phones (<768 px): top bar plus a 5-tab bottom bar.**
   - Top bar: `<Logo size="sm"/>` and the avatar (or Log in).
   - Bottom bar: Home, Search, New post, Notifications and Profile.
   - The avatar opens an account sheet with Bookmarks, Settings and Moderation (staff only). Part 1 adds
     Log out.
   - Logged out, the bottom bar has Home, Search and Log in.
3. **Marketing links go only to pages that exist.**
   - Nav: How it works, Log in, Sign up.
   - Footer: How verification works, Privacy, Terms, "© 2026 Rumor Zero".
   - About, Community Guidelines, Press and Contact are dropped. ANALYSIS a.3 is updated to match.

## Deviations from task.md / ANALYSIS d (approving this plan approves these)

Each one is recorded in ARCHITECTURE §1 and ANALYSIS d in this part (hard rule 7).

- **Request bodies are buffered, not streamed** (task.md says "streams bodies, `duplex:'half'`").
  - Django's runserver/WSGI reads `CONTENT_LENGTH`, so a chunked body arrives empty.
  - On Workers, OpenNext's converter already buffers the body (`await event.arrayBuffer()`), so
    streaming gains nothing there.
  - A wrong manual length makes Node's fetch throw.
  - How it works:
    - A `Content-Length` above 6 MB gets 413 `payload_too_large`. 6 MB covers 14B's 5 MB photo limit.
    - Otherwise the relay reads `await request.arrayBuffer()`, rechecks the size, and sends the bytes.
      The runtime sets `Content-Length` itself.
  - `duplex` is no longer needed.
- **`Location` is rewritten, not dropped.** With `redirect:'manual'`, a 3xx comes back with its real
  `Location`.
  - If it points at the backend origin under `/api/`, the relay passes it as a relative path.
  - Anything else is removed.
  - So a stray Django `APPEND_SLASH` redirect goes back through the relay, and the backend origin
    never leaks.
- **`User-Agent` is forwarded** (added to the request allow-list), so Django logs and allauth see the
  browser rather than "node".
- **`next.config.ts` gets `skipTrailingSlashRedirect: true`.**
  - By default Next 308-redirects `/api/health/` to `/api/health` (the built-in `/:path+/` rule in
    `next/dist/lib/load-custom-routes.js`). Django `APPEND_SLASH` sends it back, so it loops.
  - OpenNext already exempts `/api/` and honours the flag; the problem only appears in
    `next dev`/`next start`.
  - One `redirects()` rule keeps page URLs canonical:
    `{ source: "/:path((?!api/).+)/", destination: "/:path", permanent: true }`. An E2E test covers it.
- **One OpenNext build step in CI.** `npx opennextjs-cloudflare build` runs `next build` itself, so it
  covers both of task.md's "`next build`" and "OpenNext build" items. `--skipNextBuild` needs
  standalone output, so it isn't paired with a plain build.
- **`not-found.tsx`, `error.tsx` and `global-error.tsx` are basic now.** ARCHITECTURE §14 places the
  404/500 logos in 0C; Part 15 polishes the pages. STRUCTURE.md is updated to match.
- **ANALYSIS c-35** says "Part 0C adds a CPU check to the deploy smoke test". 0C has no deploy; Part 18
  checks Worker CPU errors. The doc is reworded (hard rule 10).

## Relay design (`src/lib/api/relay.ts`)

The route file `src/app/api/[...path]/route.ts` only exports GET, HEAD, POST, PUT, PATCH, DELETE and
OPTIONS from `createRelay()`; route files may export nothing else. No `runtime='edge'`. `force-dynamic`
isn't needed, because route handlers are dynamic and `cacheComponents` is off.

1. **Configuration** is read on every request from `process.env` (OpenNext fills it from wrangler vars
   and secrets).
   - `BACKEND_ORIGIN` must be an `https:` URL; `http:` is allowed only for loopback hosts, so the secret
     never travels in clear. `PROXY_SHARED_SECRET` must be non-empty.
   - Otherwise the relay returns 500 `{"code":"relay_misconfigured"}` and logs only the variable name.
2. **Target URL.**
   - Take `pathname` and `search` from `new URL(request.url)`. Next has already resolved `..`, `%2e%2e`
     and `\`, and keeps the trailing slash.
   - Reject `%2F`, `%5C` and `%00` (any case) with 400.
   - Build the target as `origin + pathname + search`, parse it, then require the same origin and a
     path starting with `/api/`. Otherwise 404.
3. **Request headers.**
   - Allow-list: `accept`, `authorization`, `content-type`, `cookie`, `origin`, `x-requested-with`,
     `if-none-match`, `if-modified-since`, `user-agent`.
   - Then add `x-rz-proxy-secret`, and `x-rz-client-ip` from `cf-connecting-ip`, else the right-most
     `x-forwarded-for` entry.
   - The IP gets a charset/length check (Django re-parses it); with no usable IP the header is left out.
   - Never forwarded: `Host`, hop-by-hop headers, `x-forwarded-*`, `content-length`, or anything the
     client sent as `x-rz-*`.
   - Local dev only: Next sets XFF with `??=` (`base-server.js:612`), so a client can spoof it there.
     This is documented.
4. **Body.** GET and HEAD send none. Other methods are buffered as described in the deviations.
5. **Fetch.**
   - Call `globalThis.fetch` at call time, with `redirect:'manual'` and `cache:'no-store'`.
   - The signal combines `request.signal` with an AbortController driven by a 70 s `setTimeout`. The
     timer is **cleared once headers arrive**, so a long response such as the Part 14 export is not cut
     off.
   - Headers are built outside the `try`, so a bad header is a 500, not a "waking" 503.
6. **Errors.** Only a failure of `fetch()` before headers arrive returns 503
   `{"detail":"The server is waking up. Try again in a minute.","code":"backend_waking"}`, with
   `Cache-Control: no-store` and `Retry-After: 30`. An upstream 502/503/504 whose body isn't JSON (a
   Render error page) is mapped to the same JSON.
7. **Response.**
   - Status passes through. Anything outside 200–599 becomes 502, because `new Response` throws on 101.
   - 204, 205, 304 and HEAD responses get a null body.
   - Response allow-list: `content-type`, `cache-control`, `etag`, `last-modified`,
     `content-disposition`, `x-content-type-options`, `content-security-policy`, `retry-after`.
   - `content-length` is copied only when the upstream has no `content-encoding`. Node and workerd
     decode transparently; tested: gzip reported 31 bytes for an 11-byte decoded body.
   - Each `getSetCookie()` entry is appended separately.
   - `Location` follows the rewrite rule above.
8. Also in `next.config.ts`: `poweredByHeader: false`.

## API client, types, auth skeleton

- **`src/lib/api/client.ts`**
  - Base: `baseFor(kind)` returns `"/api"` for every call type (ANALYSIS d escape hatch).
  - Paths must start with `/` and not `//`.
  - Helpers `api.get/post/put/patch/del`, sending JSON with `Accept` + `Content-Type`.
  - Always sends `X-Requested-With: rumor-zero`, plus a Bearer token from a registered getter.
  - `ApiError {status, code, detail, fieldErrors, retryAfter}`, built by a pure `normalizeError()` that
    handles:
    - DRF `{detail, code}`
    - DRF field errors, including nested ones and `non_field_errors`
    - allauth `{status, errors:[{code,param,message}]}`
    - allauth's 401 `{status, data:{flows}, meta}`, which has no `errors`
    - `backend_waking`, non-JSON bodies, network failures, and 429 `Retry-After`
  - 401 hook `setUnauthorizedHandler(() => Promise<boolean>)`:
    - single-flight: concurrent 401s share one call
    - retries the request once if the hook returns true, and never loops
    - skipped for `/auth/` paths
- **`src/lib/api/types.ts`** (ARCHITECTURE §9): `UserSummary`, `Reputation`, `PostSource`, `Post`,
  `FeedItem`, `FeedResponse`, `CursorPage<T>`, `Me` (Part 1's field list) and the error-body shapes.
- **`src/lib/auth/`**
  - `token-store.ts`: memory only. Writes are a no-op on the server, so no token is shared between
    requests.
  - `refresh-lock.ts`: `navigator.locks.request('rz-refresh', fn)`, with an in-tab promise-chain
    fallback.
  - `AuthProvider.tsx` (client): `{status: 'loading'|'anonymous'|'authenticated', user: Me|null}`. It
    stays `anonymous` in 0C and registers the token getter and a 401 handler that returns false.
  - Mounted in `src/app/providers.tsx`. No `useSearchParams` there or in the shell, so pages stay static.

## Shell (`src/components/shell/`, class lists copied from Stitch)

- **Item list.** `nav-items.ts` lists the items for each variant, with
  `isActive(path, href) = path === href || path.startsWith(href + "/")`.
  - `aria-current="page"` comes from `usePathname()`.
  - Glyphs: `home`, `search`, `notifications`, `person`, `bookmark`, `edit_note` (New post),
    `fact_check` (Moderation), `settings`.
- **`Sidebar`** (one component; b1 L13–44)
  - Hidden below `md`, a `w-16` icon dock at `md`, the `w-64` rail at `xl`.
  - Labels use `sr-only xl:not-sr-only`, so the dock links keep their names.
  - Top: `<Logo size="md"/>` on the rail and `<Logo variant="mark"/>` on the dock, linking to `/home`.
  - Main nav: Home `/home`, Search `/search`, Notifications, Profile `/u/<username>`, Bookmarks, then
    the New post button (it does nothing until Part 4).
  - Footer: Moderation (only with `user.admin_url`; new tab), Settings, then the user card: `Avatar`,
    name, `@handle`, and a `more_horiz` menu with Profile and Settings (Log out arrives in Part 1).
  - Logged out: Home and Search, then Log in / Sign up buttons.
- **`TopBar`** (b1 L50–57; `md` and up; fixed `h-16`, `left-16 xl:left-64`)
  - A GET form to `/search` with `name="q"`, using `TextField` with `leadingIcon="search"`,
    `hideLabel` and the placeholder "Search posts and people".
  - On the right: an avatar link to the profile, or a Log in link. The Verification Ledger pill is
    removed (ANALYSIS b-3).
- **`MobileNav`** (below `md`)
  - A fixed top bar with `<Logo size="sm"/>` and the avatar button, which opens `AccountMenu`.
  - A fixed `h-16` bottom bar with the five tabs (or Home, Search, Log in). Labels stay visible.
- **`AccountMenu`** uses the native `popover` with explicit fixed positioning: a bottom sheet on
  mobile, anchored above the user card on the rail. Without that, a popover renders centred.
- **`AppShell`** (props `user: ShellUser | null`)
  - A skip link to `#main`.
  - `<main id="main">` with `pt-16`, `pl-16 xl:pl-64` and `pb-16 md:pb-0`.
  - Pages choose their own container (`max-w-reading` and so on).
  - `(app)/layout.tsx` is a thin client wrapper that passes `useAuth().user`.
- **`AuthLayout`**
  - The page and card come from **a2** (task.md): `min-h-screen` centred column, card
    `w-full max-w-form bg-surface-container-lowest rounded-lg border border-outline-variant/30
    shadow-sm p-space-xl sm:p-11`.
  - A centred `<Link href="/"><Logo size="lg"/></Link>` sits above the heading, in a3's brand-header
    spot.
  - No under-card taglines.
- **`MarketingNav` / `MarketingFooter`** (a1 L18–37 / L366–386)
  - Nav: sticky, `<Logo size="md"/>` linking to `/`, How it works (`hidden md:flex`), Log in, and a
    Sign up `buttonClasses` link.
  - Footer: `<Logo size="sm"/>`, the three links, "© 2026 Rumor Zero". No tagline, no edition label.
- **Toast region:** `bottom-space-lg` → `bottom-20 md:bottom-space-lg`, above the bottom bar.

## Routes

- **Marketing.** `src/app/page.tsx` is **deleted** and recreated as `(marketing)/page.tsx`; two
  `page.tsx` files for `/` would fail the build. `(marketing)/layout.tsx` adds the nav and footer.
  Placeholders: `how-it-works`, `privacy`, `terms`.
- **Auth.** `(auth)/layout.tsx` (AuthLayout), with `login` and `signup` placeholders.
- **App.** `(app)/layout.tsx`, with `home`, `search`, `notifications`, `bookmarks`, `settings` and
  `u/[username]` placeholders.
- **Error pages.** `src/app/not-found.tsx` renders in the root layout, so it has its own auth-card
  frame and Logo. `error.tsx` is a client component with Try again. `global-error.tsx` has its own
  `<html>`/`<body>` and imports `globals.css`.
- **`src/app/dev/shell/page.tsx`** follows the `/dev/ui` pattern (`notFound()` in production) and shows
  the logged-in shell with a sample user. `/dev/ui` links to it. No E2E test uses it, because CI runs
  `next start`.
- **Titles.** The root metadata gets `title: { template: "%s · Rumor Zero", default: "Rumor Zero" }`,
  and each placeholder sets its own title.
- **Types.** Don't use the generated `RouteContext`/`PageProps` helper types: CI runs `tsc` before
  building.

## OpenNext, Playwright, CI

- **Pins** (exact devDependencies, checked with `npm view` on 2026-10-01):
  - `@opennextjs/cloudflare` **1.20.7**. Peers: `next >=16.3.6` and `wrangler ^4.125`; `rclone.js` is
    optional and not installed. The CLI is `opennextjs-cloudflare`.
  - `wrangler` **4.145.0** (SETUP said 4.143.0; it needs Node ≥22).
  - `@playwright/test` **1.63.0**.
  - Why: this is the documented stack (SETUP, D10). All three are free and dev-only, and none ships
    in the app bundle.
  - After installing, check the lockfile has `@cloudflare/workerd-linux-64` and `@esbuild/linux-x64`.
- **`wrangler.jsonc`**
  - `name "rumor-zero"`, `main ".open-next/worker.js"`.
  - A current `compatibility_date` that wrangler accepts; it must be ≥ 2024-11-11 for
    `cache:'no-store'`.
  - `compatibility_flags` `["nodejs_compat", "global_fetch_strictly_public"]` (OpenNext template).
  - `assets {directory ".open-next/assets", binding "ASSETS"}`, plus any self-reference service binding
    the 1.20.7 template uses.
  - `vars.BACKEND_ORIGIN "https://rumor-zero-api.onrender.com"` (placeholder, finalised in Part 18).
  - `open-next.config.ts`: `defineCloudflareConfig()` (default cache, no R2).
- **`next.config.ts`** becomes a phase function. It calls `initOpenNextCloudflareForDev()` only for
  `PHASE_DEVELOPMENT_SERVER`, so `next build` stays clean. On Windows this starts workerd during
  `next dev`; expect a slower start and possibly a firewall prompt.
- **Scripts:** `test:e2e` (`playwright test`), and `preview`/`deploy`/`upload`/`cf-typegen`. The last
  four are Linux-only and never run on Windows. `build` stays `next build`; otherwise the OpenNext CLI
  would call itself.
- **Leak warning for SETUP.md.** The OpenNext build copies `.env`, `.env.local` and similar files into
  `.open-next/cloudflare/next-env.mjs`. Never run `preview`/`deploy`/`upload` from a checkout with a
  real `.env.local`. Workers Builds uses a clean checkout.
- **Ignore lists.** ESLint `globalIgnores` and `.prettierignore` gain `.open-next`, `.wrangler`,
  `playwright-report` and `test-results`; `tsconfig` excludes `.open-next` and `.wrangler`.
- **`playwright.config.ts`**
  - testDir `e2e`, chromium only, baseURL `http://localhost:3000`, trace on first retry, retries 1 in CI.
  - `webServer[0]` (Django):
    - `cwd: path.resolve(__dirname, "../backend")`.
    - An absolute venv Python built with `path.join` (`.venv\Scripts\python.exe` on win32,
      `.venv/bin/python` otherwise). CI creates the venv.
    - Runs `manage.py migrate --noinput && manage.py runserver 127.0.0.1:8000 --noreload`.
    - Readiness URL: `http://127.0.0.1:8000/api/health/`.
  - `webServer[1]` (Next):
    - `npm run dev` locally, `npm run start` in CI.
    - `env: { BACKEND_ORIGIN: "http://127.0.0.1:8000" }`; the process env beats `.env.local`.
    - Readiness URL: the relay's `/api/health/`, which proves both servers. Timeout 180 s.
  - `reuseExistingServer: !CI`.
  - Locally this needs `docker compose up -d` plus the user's existing env files. It is documented in
    test-command.md, along with the stale-server caveat.
- **`.github/workflows/ci.yml`**
  - Triggers: push to `main`, pull requests, manual dispatch. `permissions: contents: read`; superseded
    runs are cancelled.
  - Every job runs on `ubuntu-latest` with `timeout-minutes: 15` and no job `container:` (so the DB
    host stays `localhost`).
  - Actions at the current majors (the review found `checkout@v7`, `setup-node@v7`, `setup-python@v7`,
    `upload-artifact@v7`; re-check on GitHub's release pages with WebFetch, since `gh api` is denied).
    Record them in SETUP.md.
  - **backend**
    - setup-python 3.13 with pip cache (`backend/requirements*.txt`).
    - Services `postgres:18` (`rumor_zero`/`rumor_zero`/`rumor_zero`, health
      `pg_isready -U rumor_zero -d rumor_zero`, 5 s interval, 10 retries) and `redis:8-alpine`.
    - `cp .env.example .env`, then `ruff check .`, `ruff format --check .`,
      `makemigrations --check --dry-run` and `pytest`.
  - **frontend**
    - setup-node from `frontend/.nvmrc` with npm cache (`frontend/package-lock.json`), then `npm ci`.
    - lint, typecheck, lint:tokens, format:check, test, then `npx opennextjs-cloudflare build`.
    - No env file is created, so nothing is copied into the bundle.
  - **e2e**
    - The same services; venv + `pip install -r requirements-dev.txt`; `cp .env.example .env`.
    - Node and `npm ci`; `npx playwright install --with-deps chromium`.
    - `cp .env.example .env.local` (the frontend example's secret equals the backend's).
    - `npm run build`, then `npm run test:e2e` with `CI=true`.
    - On failure, upload `playwright-report/` and `test-results/` (`retention-days: 7`).
  - No PNG regenerate-and-diff check (0D note). Expect about 10–12 runner-minutes per push.

## Ordered steps

0. Save this plan to `docs/agents/plans/part-0C-app-shell-relay-ci.md`. Set task.md 0C to
   `[~] In progress` in both places and update HANDOFF "Active work".
1. **Install**
   - `npm install -D -E` the three pins, then `npx playwright install chromium`.
   - Check that the lockfile diff touches only these packages and has the Linux entries.
   - **Stop** on a peer conflict (no `--force` without asking).
2. **Configs**
   - `next.config.ts`, `wrangler.jsonc`, `open-next.config.ts`, the ignore lists and the scripts.
   - Run lint, typecheck, test and build.
   - Confirm `next dev` starts on Windows (**stop** if it doesn't).
   - Confirm OpenNext's matcher honours `skipTrailingSlashRedirect` (read it in `node_modules`).
3. **Relay**
   - Write the pure helpers and their unit tests (node env, mocked fetch).
   - Then the real-HTTP integration test, then `route.ts`.
   - Check against real Django: `curl.exe -i http://localhost:3000/api/health/` gives 200 with no
     redirect. With runserver stopped, it gives 503 `backend_waking` within seconds.
4. **Client, types and auth skeleton**, with their tests.
5. **Shell, route groups, error pages, `/dev/shell`, title template and Toast offset**, with render
   tests.
   - Then the brand guard and `lint:tokens` (no new allowlist entries).
   - Then headless-Edge screenshots at 1280, 1024 and 390, side by side with Stitch b1 at 1280
     (MEMORY recipe; files in the scratchpad).
6. **Playwright config and `smoke.spec.ts`**; they must pass locally.
7. **Echo-backend check** (scratchpad Node server; `next dev` started with a process-env
   `BACKEND_ORIGIN`, never by editing `.env.local`). It prints only header names and a
   secret-matches boolean. Confirm:
   - the IP and secret arrive
   - spoofed `X-RZ-*` headers from curl are replaced or dropped
   - two `Set-Cookie` headers reach curl
   - `If-None-Match` gives a 304 with `ETag`/`Cache-Control` unchanged
   - a POST body arrives intact with its length
8. **`ci.yml`.**
9. **Docs**
   - `task.md`: tick the criteria except "CI green after you push", add the deviations, set the status.
   - `HANDOFF.md`: validation and the next action, "user pushes; agent checks with `gh run list/view`".
   - `ARCHITECTURE.md`: §1 relay rules and deviations, §10 shell rules and logged-out nav, §11 CI jobs.
   - `ANALYSIS.md`: a.3, c-35, and d (buffering, Location, User-Agent, trailing slash).
   - `STRUCTURE.md`: ✅ markers and the not-found/error change.
   - `SETUP.md`: versions, action majors, the OpenNext `.env` leak warning, `npx playwright install
     chromium`.
   - `docs/test-command.md`: a Part 0C section.
   - `MEMORY.md`: only durable surprises.
10. **Stop.** Once the user pushes and CI is green, 0C is `[x] Done`. If CI fails, investigate and
    report; for a `build.test.ts` staleness failure on Linux, fix the measurement, never the test.

## Tests (required list, mapped)

- **Relay unit tests** (node env, mocked fetch):
  - request allow-list: conditional headers kept; `Host`, hop-by-hop, `x-forwarded-*`,
    `content-length` and client `X-RZ-*` dropped
  - secret injection; IP from `cf-connecting-ip`, else the right-most XFF; an invalid IP left out
  - response allow-list; every `Set-Cookie` copied
  - 304 with a null body plus `ETag`/`Cache-Control`; Location rewrite and drop
  - the gzip `content-length` rule
  - method and body passthrough; GET/HEAD send no body; 413 over the cap
  - path guard (`%2F`, `%5C`, `%00`, outside `/api/`); misconfiguration → 500 with no values in the
    output
  - status outside 200–599 → 502
  - upstream non-JSON 503 → `backend_waking`
- **Relay integration** (node env, real `http.createServer`, real fetch):
  - the body arrives with `Content-Length` and no `Transfer-Encoding`
  - two `Set-Cookie` headers survive; a 304 round trip
  - a gzip upstream gives a correct body
  - a refused port → 503
  - a hang before headers with a 200 ms timeout → 503
  - a slow body after headers is **not** cut off
- **Client:** `normalizeError` for every shape above; the helpers, Bearer and `X-Requested-With`; the
  single-flight 401 hook (one call, one retry, no loop, skipped for `/auth/`); `baseFor`.
- **Auth:**
  - the token store: memory only, never in local or session storage, a no-op on the server
  - the refresh lock: serialises calls with and without `navigator.locks`
  - the AuthProvider default
- **Shell render tests** (`usePathname` mocked; `css:false`, so classes are checked and real
  responsiveness is left to Playwright):
  - items for logged in and logged out; Moderation only with `admin_url`
  - `aria-current` on exact and nested paths, never on `/homepage` for `/home`
  - the responsive class contracts
  - Logo placements: rail `md`, dock mark, mobile `sm`, auth `lg`, marketing `md` and `sm`
  - the search form submits `GET /search?q=`; the footer line
  - AuthLayout and marketing renders
- **Existing guards** stay green with no new allowlist entries: `brand-guard.test.ts` and
  `lint:tokens`.
- **E2E `smoke.spec.ts`** (chromium):
  - `/` shows the Logo and "© 2026 Rumor Zero"
  - `GET /api/health/` through the relay gives `{"status":"ok"}`
  - `/home/` redirects to `/home`
  - `/home` at 1280 (rail, Home `aria-current`), 1024 (dock) and 390 (bottom bar)
  - `/login` shows the auth-card Logo
  - an unknown URL shows the 404 page with the Logo

## Verification (PowerShell; frontend commands in `frontend/`)

```powershell
docker compose up -d                       # repo root
npm run lint ; npm run lint:tokens ; npm run typecheck ; npm run format:check ; npm test
npm run build                              # /, /login, /signup static (○); /api/[...path] dynamic (ƒ)
npm run test:e2e                           # starts Django + Next
# backend (venv active, unchanged code): ruff check . ; ruff format --check . ; pytest
```

Then the manual checks in steps 3, 5 and 7. Record every command and its result in HANDOFF.

## Stop conditions

Stop and report rather than working around any of these:
- a peer-dependency conflict
- `next dev`, `next build` or vitest broken by the OpenNext setup on Windows
- `/api/.../` paths not preserved, or the body not reaching Django intact
- any brand-guard or `lint:tokens` rule needing to be loosened
- a CI failure in `build.test.ts` or the OpenNext build

Out of scope:
- auth flows, the unverified banner, route guards (Part 1)
- the composer (Part 4)
- landing content and polished 404/500 pages (Part 15)
- CSP (Part 16)
- deploy and the production smoke test (Part 18)

## Follow-ups to record in HANDOFF

- **Part 1.** Through the relay Django sees `Host` = backend and `Origin` = frontend, so any unsafe
  view that isn't CSRF-exempt fails Django's Origin check. Refresh/logout must be `csrf_exempt` and use
  the c-18 Origin + `X-Requested-With` checks. Also verify allauth headless views behave the same way.
- **Part 18.**
  - Confirm on Workers that `request.signal` doesn't abort early, and that `/api/health/` works through
    the relay (it's already in Part 18's smoke test).
- **Part 14B.** Photo uploads rely on the 6 MB body cap.
