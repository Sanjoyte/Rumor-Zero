# Rumor Zero: Setup (dependencies and accounts)

Target machine (detected 2026-09-29): **Windows 11 Pro x64, Windows PowerShell 5.1**, with winget.
Every command below is for **PowerShell**. Open it with *Start → "Terminal"* (or "Windows PowerShell").
After each install, **close and reopen the terminal** so `PATH` updates.

All versions and limits were checked on 2026-09-29. Sources are at the bottom.

---

## Part A: System tools you install yourself

| Tool | Minimum | Recommended | Status on your machine |
|---|---|---|---|
| Git | 2.40 | latest | ✅ installed (2.56) |
| Python | 3.12 | **3.13.x** (3.13.15 on winget today) | ❌ not installed (only the Store stub) |
| Node.js | 22.12 | **24 LTS** (24.19.0 on winget today) | ❌ not installed |
| Docker Desktop (with Compose v2+) | engine 24 | current | ✅ installed (engine 29.7.2, Compose 5.4.0, WSL2 backend running) |
| PowerShell script execution | `RemoteSigned` for CurrentUser | — | check below |
| k6 (load testing, **Part 16 only**) | 1.0 | 2.x (2.2.0 on winget) | optional now |
| GitHub CLI `gh` | — | — | optional, never required |

### A1. Git (already installed)

Verify:

```powershell
git --version        # expect: git version 2.56.x or newer
```

You run every git command yourself. Claude Code is blocked from state-changing git commands by
`.claude/settings.json`; Codex is blocked by `.codex/rules/default.rules`. The shared prohibition in
`AGENTS.md` still applies if a tool surface cannot enforce those files.

### A2. Python 3.13

**Why 3.13 and not 3.14?** Django 5.2 LTS supports both, but several dependencies don't list 3.14 yet. Render's default is 3.14, so the repo pins 3.13 explicitly.

1. Turn off the Microsoft Store stub, which currently hijacks `python`: *Settings → Apps → Advanced app settings → App execution aliases* → switch **off** "python.exe" and "python3.exe" (App Installer).
2. Install:

   ```powershell
   winget install --exact --id Python.Python.3.13
   ```

3. Close and reopen the terminal, then verify:

   ```powershell
   py -3.13 --version   # expect: Python 3.13.x  (py = the Python launcher that the installer adds)
   python --version     # expect: Python 3.13.x
   pip --version        # expect: pip 2x.x from ...Python313...
   ```

   If `python` still opens the Store or says "not found", the alias from step 1 is still on, or the terminal wasn't reopened.

### A3. Node.js 24 LTS

⚠ **Node 26 becomes the LTS on 2026-10-28.** After that date the winget "LTS" package will install 26. The project pins **24** (Vitest 5 supports Node ^22.12 / ^24; wrangler needs ≥22), so pin the version:

```powershell
winget show --id OpenJS.NodeJS.LTS --versions          # pick the highest 24.x.y listed
winget install --exact --id OpenJS.NodeJS.LTS --version 24.19.0
```

Verify (in a new terminal):

```powershell
node -v    # expect: v24.x.x
npm -v     # expect: 11.x or newer
```

If winget no longer lists a 24.x build, download the **v24 LTS Windows Installer (.msi)** from <https://nodejs.org/en/download> instead.

### A4. Docker Desktop (already installed)

Used only for local **PostgreSQL 18** (matching Neon's default) and **Redis 8**, via a `compose.yaml` created in Part 0A. Verify:

```powershell
docker version --format "client={{.Client.Version}} server={{.Server.Version}}"   # both must print a version
docker compose version                                                            # expect: v2+ (you have v5.4.0)
```

If `server=` is empty, start Docker Desktop from the Start menu and wait for "Engine running".

- **License:** Docker Desktop is free for personal use, education, non-commercial open source and small businesses (<250 employees **and** <US$10M revenue). If your organisation is bigger, use the fallback below.
- **Fallback without Docker:** `winget install --exact --id PostgreSQL.PostgreSQL.18` (installs a Windows service; remember the password you set). Leave `REDIS_URL` empty and the backend uses an in-memory cache locally.

### A5. Allow PowerShell to run the Python virtual-env activation script

```powershell
Get-ExecutionPolicy -Scope CurrentUser                                   # if it says Restricted or Undefined:
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned     # answer Y
Get-ExecutionPolicy -Scope CurrentUser                                   # expect: RemoteSigned
```

(`RemoteSigned` lets local scripts like `.venv\Scripts\Activate.ps1` run; downloaded scripts still need a signature.)

### A6. k6: only needed for Part 16 (load test)

```powershell
winget install --exact --id GrafanaLabs.k6
k6 version     # expect: k6 v2.x
```

### A7. Optional tools

- **VS Code extensions:** Python, Pylance, Ruff, ESLint, Tailwind CSS IntelliSense, Playwright Test.
- **WSL Ubuntu:** only if you want to run the Cloudflare/OpenNext build locally. OpenNext doesn't guarantee Windows support, so production builds run on Linux: GitHub Actions CI and Cloudflare Workers Builds. You never need to build it locally; `npm run dev` works natively on Windows.
- **Not needed:** gunicorn doesn't run on Windows. Locally you use Django's `runserver`; gunicorn only runs on Render.

---

## Part B: Project packages (installed later, in Part 0, **not now**)

Versions are the latest stable releases as of 2026-09-29. Part 0 re-checks patch numbers and pins exact versions in the lock/requirements files.

### B1. Backend: `backend/requirements.txt` (runtime)

| Package | Version | Purpose |
|---|---|---|
| `Django` | 5.2.17 (**5.2 LTS**, supported to Apr 2028) | Web framework, ORM, migrations, and the admin that is our moderation panel |
| `djangorestframework` | 3.18.1 | JSON REST API (serializers, views, throttling) |
| `django-allauth[headless,socialaccount]` | 65.19.5 | Signup, login, email verification, password reset, Google sign-in, JWT tokens (headless mode) |
| `argon2-cffi` | 25.1.0 | Argon2id password hashing (guide §4.2) |
| `psycopg[binary]` | 3.3.6 | PostgreSQL driver (psycopg 3) |
| `django-environ` | 0.14.0 | Reads settings from environment / `.env`, parses `DATABASE_URL` |
| `redis` | 8.1.0 | Client for Django's built-in Redis cache (feed cache, throttles). Set `protocol=2` for Upstash. |
| `whitenoise` | 6.12.0 | Serves the admin's static files on Render |
| `gunicorn` | 26.2.0 | Production WSGI server on Render (not used on Windows) |
| `django-anymail[brevo]` | 15.2 | Sends email through Brevo's HTTPS API. Switchable to Resend later. |
| `sentry-sdk[django]` | 2.71.0 | Error tracking, active only when `SENTRY_DSN` is set |
| `Pillow` | 12.3.x (12.3.0 released 2026-07-01; the next quarterly release is due 2026-10-15) | **Added in Part 14B.** Decodes, validates and re-encodes profile photos to WebP, dropping EXIF/GPS. Prebuilt wheels for Windows and Linux (Render), with WebP support built in. |

### B2. Backend: `backend/requirements-dev.txt` (dev and test only)

| Package | Version | Purpose |
|---|---|---|
| `pytest` | 9.1.1 | Test runner |
| `pytest-django` | 4.14.0 | Django integration for pytest (test DB, `client`, `django_assert_num_queries`) |
| `pytest-cov` | 7.1.0 | Coverage report |
| `factory-boy` | 3.3.3 | Test data factories |
| `ruff` | 0.16.9 | Linter + formatter (replaces flake8/black/isort) |

### Deliberately **not** used

| Package | Why |
|---|---|
| `djangorestframework-simplejwt` | Replaced by allauth's JWT strategy (ANALYSIS D1). Its home organisation, Jazzband, is winding down. |
| `dj-rest-auth` | Maintenance risk |
| `django-ratelimit` | Unmaintained since 2023. allauth + DRF throttles are used instead. |
| `django-cors-headers` | Not needed, because the browser talks to one origin (ANALYSIS d) |
| `django-redis` | Django's built-in `RedisCache` is enough |
| Celery | Not needed: the queue is a DB table (guide §5.4) |
| `pillow-heif` | HEIC photos aren't accepted (iPhones convert to JPEG when the file input only accepts JPEG/PNG/WebP) |
| Object storage / image services (R2, Cloudflare Images, Supabase Storage, Cloudinary) | Profile photos are stored in Postgres (ANALYSIS f-7). R2 needs a payment method, and Cloudflare Images storage is paid. |

### B3. Frontend: `frontend/package.json`

| Package | Version | Purpose |
|---|---|---|
| `next` | **16.3.8** installed in 0B (keep 16.3.x, ≥ 16.3.7, which carries the 2026-09-30 security fixes) | React framework, App Router, SSR. `next.config.ts` sets `agentRules: false` (see below) |
| `react`, `react-dom` | 19.2.8 | UI library |
| `typescript` | ^5 (**not** 7.x) | Types |
| `@types/node` | 24.19.0 | Node types. Must be 24.x for Vitest 5; the template ships ^20. |
| `@types/react`, `@types/react-dom` | from template | React types |
| `tailwindcss`, `@tailwindcss/postcss` | 4.3.3 | Styling. Stitch tokens become a v4 `@theme`. |
| `@tailwindcss/forms` | 0.5.11 (**used**, decided in 0B) | Form-control reset with `strategy: "class"`: the primitives add `form-input`, `form-checkbox`, `form-radio`, `form-select` and `form-textarea` themselves. Stitch used the global reset. |
| `material-symbols` | 0.47.5 | Self-hosted Material Symbols Outlined icon font (Stitch icon set) |
| `eslint`, `eslint-config-next` | ^9, same as `next` | Linting. `next lint` is removed in Next 16, so the script runs `eslint`. |
| `prettier` (+ `prettier-plugin-tailwindcss`) | 3.9.9 (+ 0.8.1) | Formatting, and sorts Tailwind classes |
| `@opennextjs/cloudflare` | 1.20.7 | Adapter that builds Next.js for Cloudflare Workers |
| `wrangler` (dev) | 4.143.0 | Cloudflare CLI used by the adapter (needs Node ≥22) |
| `vitest` | 5.0.3 | Unit/component test runner |
| `@vitejs/plugin-react` | 6.1.1 | React support for Vitest |
| `jsdom` | 30.1.1 | Browser-like test DOM. `vite-tsconfig-paths` is **not** used: `vitest.config.mts` aliases `@` to `src` directly. |
| `@testing-library/react`, `@testing-library/dom`, `@testing-library/user-event`, `@testing-library/jest-dom` | RTL 16.3.3, dom 10.4.2, user-event 14.6.7, jest-dom 7.0.1 | Component testing |
| `@playwright/test` | 1.63.0 | End-to-end tests. Browsers are installed by `npx playwright install chromium`. |
| `sharp` (dev) | 0.35.5 (exact pin) | **Added in Part 0D** (2026-10-01). Renders `design/logo.svg` into the favicon, app icons, share image and email/admin logos (`npm run brand:build`). Prebuilt Windows x64 binaries. Used only by `frontend/scripts/brand/`, never by app code or the Worker bundle. |

**Scaffolding notes (verified in Part 0B, 2026-10-01):**
- `create-next-app` 16.3.8 has no `--turbopack` option any more (Turbopack is the default). Part 0B ran it with `--ts --tailwind --eslint --app --src-dir --import-alias "@/*" --use-npm --empty --no-react-compiler --no-agents-md --disable-git --skip-install --yes` in a scratch folder and copied the result into `frontend/`, because it refuses a folder that holds `.env.example` or `.env.local`.
- `--no-agents-md` is not enough: Next 16.3.x also writes `frontend/AGENTS.md` and `CLAUDE.md` on every `next dev`. `agentRules: false` in `next.config.ts` turns that off.
- Behind this machine's network a first `npm install` can fail with `ERR_SSL_CIPHER_OPERATION_FAILED`. `npm cache verify` and a retry fixed it; do not disable TLS checks.

**Not used in the frontend (on purpose):**
- chart libraries (Chart.js, Recharts, d3): the charts are token-built HTML/SVG (Part 11D)
- `next/image` optimisation: on Cloudflare Workers it needs a Cloudflare Images binding, and the logo and photos are already pre-sized, so plain `<img>` is used
- SVG optimisers (SVGO): the logo SVG is only checked and cropped, not rewritten

**Loaded at runtime, not from npm:**
- Google Identity Services: `https://accounts.google.com/gsi/client`
- Cloudflare Turnstile: `https://challenges.cloudflare.com/turnstile/v0/api.js`

These are required third-party widgets, loaded only on the auth pages.

**Fonts:** Inter, JetBrains Mono and Newsreader via `next/font/google`, which self-hosts them at build time. It doesn't carry Material Symbols, which is why the npm package above is used.

### B4. Local containers (`compose.yaml`, created in Part 0A)

| Image | Purpose |
|---|---|
| `postgres:18` | Local database, same major version as Neon's default. ⚠ The Postgres 18 image mounts its volume at `/var/lib/postgresql`, not `/var/lib/postgresql/data`. |
| `redis:8-alpine` | Local cache and throttle store. Optional. |

---

## Part C: Free accounts to create

**None of these should ask for a credit card.** If one does, stop and do not enter it. Tell the
active agent, and it will suggest an alternative.

| # | Service | What it's for | When needed | Plan / free limits (2026-09-29) |
|---|---|---|---|---|
| 1 | **GitHub** | Code hosting, CI (GitHub Actions), Dependabot | **At your first push**, because CI runs there (Part 0C). Not for local dev. | Public repo: unlimited Actions minutes. Private: 2,000 min/month, each job rounded up to 1 min. |
| 2 | **Google Cloud** (OAuth client) | "Continue with Google" | **Needed for local development from Part 3.** It also works with `http://localhost` | Free, no billing account needed for OAuth |
| 3 | **Cloudflare** | Turnstile (bot check) + Workers (frontend hosting) + Workers Builds | Only needed at deployment. Local dev uses Turnstile's official test keys. | Workers Free: 100k requests/day, 10 ms CPU/request, 3,000 build min/month. Turnstile: unlimited. No card. |
| 4 | **Neon** | Production PostgreSQL | Only needed at deployment (local uses Docker) | 0.5 GB, 100 CU-hours/month, scale-to-zero after 5 min, Postgres 18. No card. |
| 5 | **Upstash** | Production Redis | Only needed at deployment | 256 MB, 500K commands/month; archived after ~30 days idle. No card. |
| 6 | **Render** | Backend hosting (Django) | Only needed at deployment | 750 instance-h/month, 512 MB, sleeps after 15 min idle, **no SMTP**, no free workers/cron, 500 build min/month. Officially no card. Some users report a card prompt; if you get one, stop. |
| 7 | **Brevo** | Production transactional email (verification, reset) | Only needed at deployment. Locally, emails print in the terminal. | 300 emails/day, HTTPS API, no card |
| 8 | **Sentry** | Error tracking | Only needed at deployment | Developer plan: 5K errors/month, 1 user. Starts with a 14-day trial, then free. |
| 9 | **UptimeRobot** | Keep-alive ping every 5 min + downtime alerts | Only needed at deployment | 50 monitors, 5-min interval, commercial use allowed |
| 10 | **cron-job.org** | Hourly call to the pipeline sweeper | Only needed at deployment | Free, custom methods/headers, 30 s timeout |

Step-by-step setup for each account, and which values to copy, is in `docs/ENV_GUIDE.md`.

The Stitch-only features added on 2026-09-29 need **no new account**:
- emergency posts, credibility score, reposts, bookmarks, source/DOI and charts are all Django + Postgres;
- profile photos are stored in Postgres (ANALYSIS f-7);
- the logo is a file in the repo.

**Things that would cost money (avoided):**
- **A custom domain.** Needed only for Resend, for "pretty" URLs, and realistically for showing a logo on Google's consent screen (brand verification checks domain ownership, ENV_GUIDE §2.9). The free alternatives are in ANALYSIS c-22 and d.
- **Cloudflare R2.** Enabling it means completing an "R2 subscription" checkout with a payment method, even for the free tier (re-checked 2026-09-29). Not used: profile photos live in Postgres, and the OpenNext cache stays on the default, not R2.
- **Cloudflare Images storage.** $5 per 100,000 stored images. Not used.
- **Vercel Hobby.** Free, but non-commercial use only.

**Free but not used (would be new services):**
- **Supabase Storage:** 1 GB, no card, but free projects pause after 7 days without activity.
- **Cloudinary:** 25 credits/month, no card.

They're listed only as fallbacks if profile photos ever outgrow Neon's 0.5 GB. You'd be asked before either is added.

---

## Sources (checked 2026-09-29)

- Django releases: <https://www.djangoproject.com/download/>, <https://pypi.org/project/Django/>
- DRF: <https://pypi.org/project/djangorestframework/>
- allauth headless + JWT: <https://docs.allauth.org/en/latest/headless/token-strategies/jwt-tokens.html>, <https://docs.allauth.org/en/latest/release-notes/recent.html>
- simplejwt / Jazzband wind-down: <https://pypi.org/project/djangorestframework-simplejwt/>, <https://jazzband.co/news/2026/03/14/wind-down-plan>
- Render: <https://render.com/docs/free>, <https://render.com/docs/python-version>, <https://render.com/changelog/free-web-services-will-no-longer-allow-outbound-traffic-to-smtp-ports>, <https://render.com/docs/deploys>
- Neon: <https://neon.com/pricing>, <https://neon.com/docs/changelog/2026-06-05>, <https://neon.com/docs/connect/connection-pooling>
- Upstash: <https://upstash.com/docs/redis/overall/pricing>, <https://upstash.com/docs/redis/help/faq>
- Next.js: <https://nextjs.org/blog/next-16>, <https://nextjs.org/docs/app/api-reference/cli/create-next-app>, <https://nextjs.org/docs/app/guides/testing>
- Node.js releases: <https://github.com/nodejs/Release>
- Cloudflare + Next.js: <https://developers.cloudflare.com/workers/framework-guides/web-apps/nextjs/>, <https://opennext.js.org/cloudflare>, <https://developers.cloudflare.com/workers/platform/limits/>, <https://developers.cloudflare.com/changelog/post/2026-09-04-increased-worker-size-limit/>
- Tailwind v4: <https://tailwindcss.com/docs/functions-and-directives>
- Turnstile: <https://developers.cloudflare.com/turnstile/plans/>, <https://developers.cloudflare.com/turnstile/troubleshooting/testing/>
- Resend: <https://resend.com/docs/knowledge-base/403-error-resend-dev-domain>
- Brevo: <https://www.brevo.com/features/email-api/>
- Sentry: <https://sentry.io/pricing/>
- GitHub Actions billing and schedules: <https://docs.github.com/en/billing/concepts/product-billing/github-actions>, <https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows>
- UptimeRobot: <https://uptimerobot.com/pricing/>; cron-job.org: <https://cron-job.org/en/faq/>
- Google OAuth: <https://support.google.com/cloud/answer/15549049>, <https://developers.google.com/identity/gsi/web/guides/get-google-api-clientid>
- Public Suffix List: <https://publicsuffix.org/list/public_suffix_list.dat>
- Pillow: <https://pillow.readthedocs.io/en/stable/releasenotes/index.html>; sharp: <https://www.npmjs.com/package/sharp>, <https://sharp.pixelplumbing.com/install/>
- Cloudflare R2 (subscription checkout): <https://developers.cloudflare.com/r2/get-started/>, <https://community.cloudflare.com/t/why-using-r2-free-tier-involves-giving-card-info/945179>; Cloudflare Images: <https://developers.cloudflare.com/images/pricing>
- Supabase pausing: <https://supabase.com/docs/guides/platform/free-project-pausing>; Cloudinary free plan: <https://cloudinary.com/documentation/developer_onboarding_faq_free_plan>
- Next.js icon and OG file conventions: <https://nextjs.org/docs/app/api-reference/file-conventions/metadata/app-icons>
- create-next-app folder check: <https://github.com/vercel/next.js/blob/canary/packages/create-next-app/helpers/is-folder-empty.ts>
