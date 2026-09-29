# Rumor Zero: Getting and generating every environment value

Order:
- **Part 1** covers everything you need for **local development**.
- **Part 2** covers values that only exist **at deployment** (Parts 17–18 of `task.md`).

Every variable in `backend/.env.example` and `frontend/.env.example` appears below. UI paths were checked on 2026-09-29; dashboards change, so if a button has moved, search the page for the setting's name.

> **Ground rules**
> - **Never paste a secret into a chat with Claude** (or anyone else). Paste secrets only into your local `.env` files or a provider's dashboard. Claude Code is configured so it can't read `backend/.env`, `frontend/.env.local` or `.dev.vars`.
> - Local and production secrets are **always different values**. Never reuse a local secret in production.
> - Wherever a dashboard asks for an app, project or sender **name**, type **`Rumor Zero`**. Where it asks for a URL-bearing **slug**, use `rumor-zero` (or the fallbacks in §2.0).

---

## Part 1: Local development

### 1.1 Create your local env files

From the repo root in PowerShell:

```powershell
Copy-Item backend\.env.example backend\.env
Copy-Item frontend\.env.example frontend\.env.local
```

Open both in VS Code (`code backend\.env frontend\.env.local`) and work through 1.2–1.8.

### 1.2 Generate local secrets: `DJANGO_SECRET_KEY`, `JWT_SIGNING_KEY`, `PROXY_SHARED_SECRET`, `INTERNAL_CRON_SECRET`

These are just long random strings. Run this once per secret (Python must be installed, SETUP.md A2):

```powershell
py -3.13 -c "import secrets; print(secrets.token_urlsafe(50))"
```

Each run prints a new value of about 67 URL-safe characters. Copy each one into the file as `KEY=value`.

| Variable | Where it goes | Note |
|---|---|---|
| `DJANGO_SECRET_KEY` | `backend/.env` | After Part 0A you can also use Django's generator: `python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"`. Either is fine. |
| `JWT_SIGNING_KEY` | `backend/.env` | Must differ from `DJANGO_SECRET_KEY` |
| `PROXY_SHARED_SECRET` | **both** `backend/.env` **and** `frontend/.env.local` | Must be **identical** in both files, or the API relay's client-IP header is ignored. Throttling still works in dev, but tests for it fail. |
| `INTERNAL_CRON_SECRET` | `backend/.env` | Used by `/api/internal/tick/` and `/api/health/deep/` |

Gotcha: don't wrap these values in quotes, and don't leave trailing spaces.

### 1.3 Values you keep exactly as in the example (local)

| Variable | Local value | Why |
|---|---|---|
| `DJANGO_DEBUG` | `True` | Local only |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | `http://localhost:8000,http://127.0.0.1:8000` | For the Django Admin login form |
| `ADMIN_URL_PATH` | `admin/` | Local admin at <http://localhost:8000/admin/> |
| `FRONTEND_ORIGIN` | `http://localhost:3000` | `npm run dev` default |
| `AUTH_COOKIE_SECURE` | `False` | Localhost is plain http |
| `JWT_ACCESS_TOKEN_MINUTES` / `JWT_REFRESH_TOKEN_DAYS` | `15` / `14` | Guide §4.6 |
| `EMAIL_PROVIDER` | `console` | Verification and reset emails are **printed in the `runserver` terminal**. Copy the link from there. |
| `DEFAULT_FROM_EMAIL` | `"Rumor Zero <no-reply@example.com>"` | Only shows in the printed email |
| `BREVO_API_KEY` | *(empty)* | Not used locally |
| `REPORT_THRESHOLD` … `FEED_CACHE_SECONDS` | defaults | Guide §6.2, §7.2, §9.2; ANALYSIS D7 |
| `PIPELINE_BACKEND` / `PIPELINE_INLINE_KICK` | `stub` / `True` | Built-in fake pipeline |
| `PIPELINE_URL` / `PIPELINE_API_KEY` | *(empty)* | Reserved for the future real pipeline |
| `SENTRY_DSN` | *(empty)* | Sentry off locally |
| `SENTRY_ENVIRONMENT` / `SENTRY_TRACES_SAMPLE_RATE` | `local` / `0.0` | |
| frontend `BACKEND_ORIGIN` | `http://localhost:8000` | Django `runserver` |
| frontend `NEXT_PUBLIC_SITE_URL` | `http://localhost:3000` | |

### 1.4 `DATABASE_URL` and `REDIS_URL` (local)

Part 0A creates `compose.yaml` with user `rumor_zero`, password `rumor_zero` and database `rumor_zero` on port 5432, plus Redis on 6379. The example values already match:

```
DATABASE_URL=postgres://rumor_zero:rumor_zero@localhost:5432/rumor_zero
REDIS_URL=redis://localhost:6379/0
```

Start them with `docker compose up -d` from the repo root (after Part 0A). Check with `docker compose ps`: both should show `running (healthy)`.

- **No Docker?** Install PostgreSQL 18 natively (SETUP.md A4). Then, in *SQL Shell (psql)* as `postgres`:
  ```sql
  CREATE ROLE rumor_zero LOGIN PASSWORD 'rumor_zero' CREATEDB;
  CREATE DATABASE rumor_zero OWNER rumor_zero;
  ```
  `CREATEDB` is needed because pytest creates a `test_rumor_zero` database. Set `REDIS_URL=` (empty).
- **Gotcha:** if port 5432 is already used by another Postgres, change the compose port mapping to `5433:5432` and use `localhost:5433` in the URL.

### 1.5 Turnstile keys (local): `TURNSTILE_SECRET_KEY`, `NEXT_PUBLIC_TURNSTILE_SITE_KEY`

Keep Cloudflare's **official test keys**, which are already in the examples. No account is needed. They work on `localhost` and always pass:

| Purpose | Site key (frontend) | Secret key (backend) |
|---|---|---|
| Always pass (default) | `1x00000000000000000000AA` | `1x0000000000000000000000000000000AA` |
| Always fail (to test the error UI) | `2x00000000000000000000AB` | `2x0000000000000000000000000000000AA` |
| "Token already spent" | — | `3x0000000000000000000000000000000AA` |

Source: <https://developers.cloudflare.com/turnstile/troubleshooting/testing/>

### 1.6 Google sign-in: `GOOGLE_OAUTH_CLIENT_ID` + `NEXT_PUBLIC_GOOGLE_CLIENT_ID` (needed from Part 3)

Free. No billing account is needed; if Google offers to set one up, choose skip or cancel.

1. Go to <https://console.cloud.google.com/> and sign in with your Google account.
2. **Create the project.** Click the project picker in the top bar → **New project**.
   - **Project name:** `Rumor Zero`
   - **Location:** "No organization" is fine.
   - Click **Create**, then select the new project in the picker.
3. **Set up the consent screen.** Open the menu (☰) → **Google Auth Platform** (or go to <https://console.cloud.google.com/auth/overview>) → **Get started**.
   - **App name:** `Rumor Zero`
   - **User support email:** your email → **Next**
   - **Audience:** **External** → **Next**
   - **Contact information:** your email → **Next** → tick the policy agreement → **Continue** → **Create**
4. **Scopes.** Leave **Data Access** alone. The default `openid`, `email` and `profile` scopes are non-sensitive and are all we need.
5. **Create the OAuth client.** Go to **Clients** → **Create client**.
   - **Application type:** **Web application**
   - **Name:** `Rumor Zero web`
   - **Authorized JavaScript origins:** add `http://localhost` **and** `http://localhost:3000` (exactly, no trailing slash)
   - **Authorized redirect URIs:** leave **empty**. We use the Google Identity Services button, which returns an ID token directly with no redirect.
   - Click **Create**.
6. The dialog shows a **Client ID** (`…apps.googleusercontent.com`) and a **Client secret**. Copy **only the Client ID**:
   - `backend/.env` → `GOOGLE_OAUTH_CLIENT_ID=<client id>`
   - `frontend/.env.local` → `NEXT_PUBLIC_GOOGLE_CLIENT_ID=<same client id>`
   
   The **secret is not needed** by this flow. Don't save it anywhere. Client IDs are public by design, so the `NEXT_PUBLIC_` one is safe.
7. **Testing mode.** The app starts in "Testing". With only the basic scopes, sign-in works for any Google account, but if Google blocks an account, add it under **Audience → Test users** (up to 100).
   - Gotcha: new or changed origins can take from a few minutes to a few hours to start working.

### 1.7 Finished local files: checklist

- [ ] `backend/.env`: 4 generated secrets filled in, everything else as the example
- [ ] `frontend/.env.local`: `PROXY_SHARED_SECRET` identical to the backend's
- [ ] From Part 3: both Google client ID variables filled in
- [ ] Nothing from `.env`/`.env.local` pasted into chat, and neither file committed (`git status` should never list them)

---

## Part 2: Deployment-only values (Parts 17–18)

Do the sections in this order: later services need URLs from earlier ones.

### 2.0 Choose your public names first (URLs must be globally unique)

| What | First choice | Fallbacks if taken | Becomes |
|---|---|---|---|
| Render web service name | `rumor-zero-api` | `rumorzero-api`, `rumor-zero-app-api`, `rumor-zero-backend` | `https://<name>.onrender.com`. If the name is taken, Render may silently append a random suffix (e.g. `rumor-zero-api-x7k2`). **Use the URL Render actually shows.** |
| Cloudflare account **subdomain** (one per account, globally unique) | `rumor-zero` | `rumorzero`, `rumor-zero-app`, `rumor-zero-social` | `<subdomain>.workers.dev` |
| Worker name (unique only inside your account) | `rumor-zero` | — | Frontend URL = `https://rumor-zero.<subdomain>.workers.dev` |
| *(not used)* Cloudflare Pages project | `rumor-zero` | same fallbacks | `https://<name>.pages.dev`. Pages now serves static sites only (ANALYSIS c-23). Listed so you know the name rule is the same. |

Write down your two final URLs. Below they're called **`<FRONTEND>`** (e.g. `https://rumor-zero.rumor-zero.workers.dev`) and **`<BACKEND>`** (e.g. `https://rumor-zero-api.onrender.com`). Then update the "Deployed URLs" rows in `docs/ARCHITECTURE.md §0`.

⚠ Changing the Cloudflare subdomain later changes `<FRONTEND>`. You'd then have to update `FRONTEND_ORIGIN`, `NEXT_PUBLIC_SITE_URL`, the Google origins and the Turnstile hostname.

### 2.1 Generate production secrets (new values, never the local ones)

Run `py -3.13 -c "import secrets; print(secrets.token_urlsafe(50))"` four times. Keep the results in a password manager until you've entered them in the dashboards:

- `DJANGO_SECRET_KEY` (Render)
- `JWT_SIGNING_KEY` (Render)
- `PROXY_SHARED_SECRET` (Render **and** Cloudflare Worker secret, identical)
- `INTERNAL_CRON_SECRET` (Render, GitHub Actions secret, cron-job.org header)

Also pick `ADMIN_URL_PATH`: run `py -3.13 -c "import secrets; print('mod-' + secrets.token_hex(6) + '/')"` (for example `mod-3f9a1c2b7d4e/`). The moderation panel will live at `<BACKEND>/<that path>`.

### 2.2 Neon → `DATABASE_URL`

1. <https://neon.com> → **Sign up** (GitHub, Google or email). No card.
2. **Create project:**
   - **Project name:** `Rumor Zero`
   - **Postgres version:** 18 (default)
   - **Cloud:** AWS
   - **Region:** nearest your users, and **the same region you'll pick on Render and Upstash**. For example AWS *Asia Pacific (Singapore)* ↔ Render *Singapore*; *US East (N. Virginia)* ↔ Render *Virginia*; *Europe (Frankfurt)* ↔ Render *Frankfurt*.
   - If the dialog lets you name the database, use `rumor_zero`.
3. If the database is called `neondb`: go to **Databases** → **New database** → name `rumor_zero`, owner = the default role → **Create**.
4. Project dashboard → **Connect** button:
   - **Branch:** `production`/`main`
   - **Database:** `rumor_zero`
   - **Role:** the owner role
   - **Connection pooling: OFF.** Use the *direct* URL: we run one long-lived server, and the pooled endpoint (PgBouncer transaction mode) breaks some Django features.
5. Copy the string. It looks like `postgresql://<role>:<password>@ep-xxxx-xxxx.<region>.aws.neon.tech/rumor_zero?sslmode=require&channel_binding=require`. Keep it for Render (§2.6) as `DATABASE_URL`.

**Free-tier gotchas:**
- 0.5 GB storage per project. Over the limit, writes fail.
- 100 CU-hours/month. That's ~400 h at the minimum size; when it runs out, compute is suspended until next month.
- Scales to zero after 5 min without queries, so the first query afterwards adds a short delay.
- **Anything that queries the DB more often than every 5 min keeps it awake and burns the allowance.** That's why the 5-min keep-alive hits `/api/health/`, which never touches the DB.
- Resetting the role password (Roles → Reset) changes the URL, so update Render afterwards.

### 2.3 Upstash → `REDIS_URL`

1. <https://console.upstash.com> → sign up. No card: **don't** add one, because adding a card switches you to pay-as-you-go.
2. **Redis** → **Create Database**:
   - **Name:** `Rumor Zero` (if spaces are rejected, `rumor-zero`)
   - **Type:** Regional
   - **Region:** same as Neon/Render
   - **Eviction:** **on**. It's only a cache and rate-limit store, so dropping old keys beats erroring when full.
   - Click **Create**.
3. Open the database → **Connect** section. In the **TCP / redis-cli** tab, copy the URL of the form `rediss://default:<password>@<name>.upstash.io:6379`. Note the double "s", for TLS. Keep it for Render as `REDIS_URL`.

**Gotchas:**
- 256 MB, 500K commands/month (~16K/day). Only writes, throttled endpoints and the feed cache use Redis; polling endpoints don't.
- A database idle for ~30 days is **archived**. The daily GitHub "deep health" ping (§2.10) prevents this.
- TLS is always on. The code sets `protocol=2` for redis-py 8 compatibility.

### 2.4 Brevo → `EMAIL_PROVIDER`, `BREVO_API_KEY`, `DEFAULT_FROM_EMAIL`

(Why not Resend: it needs a domain you own. See ANALYSIS D2 / c-22.)

1. <https://www.brevo.com> → **Sign up free**. Confirm your email and fill in the profile; for the company or brand name, use `Rumor Zero`.
2. **Sender:** account menu (top right) → **Senders, Domains & Dedicated IPs** → **Senders** → **Add a sender**.
   - **From name:** `Rumor Zero`
   - **From email:** an address you control (e.g. your Gmail)
   - Brevo emails a 6-digit code; enter it.
3. **API key:** account menu → **SMTP & API** → **API Keys** → **Generate a new API key**.
   - **Name:** `rumor-zero-render`
   - Copy the key (starts with `xkeysib-`). **It's shown only once.**
4. Render values (§2.6):
   - `EMAIL_PROVIDER=brevo`
   - `BREVO_API_KEY=<key>`
   - `DEFAULT_FROM_EMAIL=Rumor Zero <the-verified-address>`

**Gotchas:**
- 300 emails/day free.
- A free-mail sender (gmail.com, outlook.com…) can't be domain-authenticated. Brevo may rewrite the visible From to a Brevo shared address, and some inboxes will file mail as spam. **After deploying, sign up once with a Gmail and once with an Outlook address and check that the emails arrive.**
- Brevo sometimes asks new accounts to complete activation before sending transactional email; follow its prompt.
- Never use SMTP settings: Render free blocks SMTP ports.

### 2.5 Sentry → `SENTRY_DSN`, `SENTRY_ENVIRONMENT`, `SENTRY_TRACES_SAMPLE_RATE`

1. <https://sentry.io/signup/>. **Organization name:** `Rumor Zero`. It starts a 14-day Business trial and then drops to the free Developer plan automatically. No card.
2. **Projects** → **Create project** → platform **Django** → **Project name:** `rumor-zero-api` → **Create**.
3. Copy the **DSN** (`https://<key>@o<id>.ingest.<region>.sentry.io/<id>`). You can find it later under **Settings → Projects → rumor-zero-api → Client Keys (DSN)**.
4. Render values:
   - `SENTRY_DSN=<dsn>`
   - `SENTRY_ENVIRONMENT=production`
   - `SENTRY_TRACES_SAMPLE_RATE=0.0` (raise to `0.1` if you want performance traces)

**Gotchas:** 5K errors/month, 1 user. Code never sends passwords or tokens (`send_default_pii=False`).

### 2.6 Render → the backend service and all backend variables

1. <https://render.com> → **Get Started** → sign up **with GitHub**. **Workspace name:** `Rumor Zero`. If you're asked for a card, stop: the free tier officially doesn't need one.
2. **New** → **Web Service** → connect GitHub → grant access to **only** the `rumor-zero` repo → select it.
   (Part 17 may give you a `render.yaml` Blueprint instead: **New → Blueprint** fills in steps 3–5 for you.)
3. Settings:

   | Field | Value |
   |---|---|
   | Name | `rumor-zero-api` (§2.0) |
   | Region | same as Neon |
   | Branch | `main` |
   | Root Directory | `backend` |
   | Runtime / Language | Python 3 |
   | Build Command | `pip install -r requirements.txt && python manage.py collectstatic --no-input && python manage.py migrate --no-input` |
   | Start Command | `gunicorn rumor_zero.wsgi:application --workers 2 --threads 4 --timeout 60 --bind 0.0.0.0:$PORT` |
   | Instance Type | **Free** |
   | Health Check Path (Advanced) | `/api/health/` |

4. **Environment** → **Add Environment Variable** for each row:

   | Variable | Production value |
   |---|---|
   | `PYTHON_VERSION` | your exact local version, e.g. `3.13.15` (`python --version`) |
   | `DJANGO_SECRET_KEY` | from §2.1 |
   | `DJANGO_DEBUG` | `False` |
   | `DJANGO_ALLOWED_HOSTS` | the host of `<BACKEND>`, e.g. `rumor-zero-api.onrender.com` |
   | `DJANGO_CSRF_TRUSTED_ORIGINS` | `<BACKEND>`, e.g. `https://rumor-zero-api.onrender.com` |
   | `ADMIN_URL_PATH` | from §2.1 |
   | `DATABASE_URL` | Neon, §2.2 |
   | `REDIS_URL` | Upstash, §2.3 |
   | `FRONTEND_ORIGIN` | `<FRONTEND>` |
   | `PROXY_SHARED_SECRET` | from §2.1 |
   | `AUTH_COOKIE_SECURE` | `True` |
   | `JWT_SIGNING_KEY` | from §2.1 |
   | `JWT_ACCESS_TOKEN_MINUTES` / `JWT_REFRESH_TOKEN_DAYS` | `15` / `14` |
   | `TURNSTILE_SECRET_KEY` | §2.8 (set after the widget exists) |
   | `GOOGLE_OAUTH_CLIENT_ID` | §1.6 (same client) |
   | `EMAIL_PROVIDER` / `BREVO_API_KEY` / `DEFAULT_FROM_EMAIL` | §2.4 |
   | `REPORT_THRESHOLD` … `FEED_CACHE_SECONDS` | defaults (only initial values) |
   | `PIPELINE_BACKEND` / `PIPELINE_INLINE_KICK` | `stub` / `True` |
   | `INTERNAL_CRON_SECRET` | from §2.1 |
   | `SENTRY_DSN` / `SENTRY_ENVIRONMENT` / `SENTRY_TRACES_SAMPLE_RATE` | §2.5 |
   | `WEB_CONCURRENCY` | `2` (read by gunicorn; matches `--workers`) |

5. **Settings → Build & Deploy → Auto-Deploy:** **After CI Checks Pass**. This needs the CI workflow from Part 0C; Render won't deploy if zero checks run.
6. **Create the first admin (superuser).** Render's free tier has no shell, so run it **from your PC against Neon**, in a fresh PowerShell window inside `backend/` with the venv active:

   ```powershell
   $env:DATABASE_URL = Read-Host "Paste the Neon DATABASE_URL (not shown in chat)"
   python manage.py createsuperuser
   Remove-Item Env:DATABASE_URL
   ```

   The process environment variable overrides `backend/.env` for this window only. Then log in at `<BACKEND>/<ADMIN_URL_PATH>` and give yourself `role = senior_moderator` (Part 10 explains roles).

**Gotchas:**
- The free instance sleeps after 15 min without traffic and takes about 1 min to wake. UptimeRobot (§2.11) prevents this.
- The filesystem is ephemeral (fine: we store nothing on disk).
- 750 instance-hours/month per workspace covers exactly one always-on service.
- 500 build minutes/month.
- **No outbound SMTP.**

### 2.7 Cloudflare → Worker, `BACKEND_ORIGIN`, `PROXY_SHARED_SECRET`, and the `NEXT_PUBLIC_*` build variables

1. <https://dash.cloudflare.com/sign-up>, then confirm your email. No card and no domain are needed.
2. **Account subdomain:** **Workers & Pages** (left nav). The subdomain is shown on the right as `<something>.workers.dev` → **Change** → enter your choice from §2.0 (`rumor-zero`, or a fallback) → confirm.
3. **Create the Worker from Git (Workers Builds):** **Workers & Pages** → **Create** → **Import a repository** → connect GitHub (only the `rumor-zero` repo) → select it.

   | Field | Value |
   |---|---|
   | Project / Worker name | `rumor-zero` (must equal `"name"` in `frontend/wrangler.jsonc`) |
   | Root directory | `frontend` |
   | Build command | `npx @opennextjs/cloudflare build` |
   | Deploy command | `npx @opennextjs/cloudflare deploy` |
   | Build variables (Advanced) | `NEXT_PUBLIC_SITE_URL=<FRONTEND>` · `NEXT_PUBLIC_GOOGLE_CLIENT_ID=<client id>` · `NEXT_PUBLIC_TURNSTILE_SITE_KEY=<site key from §2.8>` (use the test key `1x00000000000000000000AA` for the very first build if the widget isn't created yet, then rebuild) · `NODE_VERSION=24` (only if `.nvmrc` isn't picked up) |

4. **Runtime values:**
   - `BACKEND_ORIGIN=<BACKEND>` goes in `frontend/wrangler.jsonc` under `"vars"` (committed; it's not a secret). **Don't** add it in the dashboard: `wrangler deploy` overwrites dashboard plain-text variables with the ones in `wrangler.jsonc`.
   - `PROXY_SHARED_SECRET`: Worker → **Settings** → **Variables and Secrets** → **Add** → Type **Secret** → name `PROXY_SHARED_SECRET` → value from §2.1 → **Deploy**. Secrets survive `wrangler deploy`.
5. Every change to a `NEXT_PUBLIC_*` value needs a **new build**: Worker → **Deployments** → **Retry build** (or push a commit).

**Gotchas:**
- 100,000 Worker requests/day on free; every API call through the relay counts.
- 10 ms CPU per request.
- 3,000 build minutes/month.
- Preview deployments get other hostnames (`<version>-rumor-zero.<subdomain>.workers.dev`) that won't match the Google and Turnstile settings. Test auth on the production URL only.

### 2.8 Turnstile (production) → `NEXT_PUBLIC_TURNSTILE_SITE_KEY` + `TURNSTILE_SECRET_KEY`

1. Cloudflare dashboard → **Turnstile** (left nav; search "Turnstile" if you don't see it) → **Add widget**:
   - **Widget name:** `Rumor Zero`
   - **Hostname management → Add hostname:** the exact host of `<FRONTEND>`, e.g. `rumor-zero.rumor-zero.workers.dev`. No wildcards, and never a bare `workers.dev`. Don't add `localhost`; locally you use the test keys.
   - **Widget mode:** *Managed*
   - **Pre-clearance:** No
   - Click **Create**.
2. Copy the **Site Key** into the Workers Builds build variable `NEXT_PUBLIC_TURNSTILE_SITE_KEY` and **rebuild** (§2.7 step 5).
3. Copy the **Secret Key** into Render as `TURNSTILE_SECRET_KEY` (Render redeploys when you save).

**Gotchas:** free and unlimited, 10 hostnames per widget. A key mismatch shows as "invalid-input-secret" or a failed signup in the backend logs.

### 2.9 Google sign-in (production): update the same OAuth client

1. <https://console.cloud.google.com/auth/clients> (project `Rumor Zero`) → **Rumor Zero web** → **Authorized JavaScript origins** → **Add URI** → `<FRONTEND>` (no trailing slash) → **Save**. Keep the localhost entries.
2. **Branding:**
   - **App home page:** `<FRONTEND>/`
   - **Privacy policy:** `<FRONTEND>/privacy`
   - **Terms of service:** `<FRONTEND>/terms`
   
   These pages exist from Part 15 and **are required** before publishing. Under **Authorized domains**, add the registrable domain `<subdomain>.workers.dev` (e.g. `rumor-zero.workers.dev`) → **Save**.
3. **Audience** → **Publish app** → confirm → status **In production**. With only the basic scopes, no Google verification is needed. Unverified apps show no logo on the consent screen, which is fine.
4. No new variable: `GOOGLE_OAUTH_CLIENT_ID` / `NEXT_PUBLIC_GOOGLE_CLIENT_ID` stay the same client ID.

### 2.10 GitHub → Actions secret and variable for the daily deep-health workflow

Repo on github.com → **Settings** → **Secrets and variables** → **Actions**:

- **Secrets** tab → **New repository secret** → name `INTERNAL_CRON_SECRET` → value from §2.1.
- **Variables** tab → **New repository variable** → name `BACKEND_ORIGIN` → `<BACKEND>`.

CI itself needs **no** secrets (it uses the test values from the `.env.example` files).

Gotcha: in a public repo, scheduled workflows are disabled after 60 days without commits. GitHub emails you, and you can re-enable the workflow in the **Actions** tab.

### 2.11 UptimeRobot: 5-min keep-alive and uptime alerts (no variables)

1. <https://uptimerobot.com> → **Sign up** (free).
2. **Add New Monitor**:
   - **Type:** HTTP(s)
   - **Friendly name:** `Rumor Zero API`
   - **URL:** `<BACKEND>/api/health/`
   - **Interval:** 5 minutes
   - **Alert contacts:** your email
   - Click **Create**.
3. Optional second monitor: `Rumor Zero web` → `<FRONTEND>/`.

Gotcha: never point it at `/api/health/deep/` or any page that queries the database (Neon compute hours, §2.2).

### 2.12 cron-job.org: hourly pipeline sweeper (uses `INTERNAL_CRON_SECRET`)

1. <https://console.cron-job.org/signup> → confirm your email → **Create cronjob**:
   - **Title:** `Rumor Zero pipeline sweeper`
   - **URL:** `<BACKEND>/api/internal/tick/`
   - **Schedule:** every hour, at an off-peak minute (e.g. minute 7)
   - **Advanced → Request method:** POST
   - **Headers:** add `X-RZ-Cron-Secret` = the production `INTERNAL_CRON_SECRET`
   - **Timeout:** 30 s
   - **Notifications:** email on failure
   - Click **Save**.
2. Use **Test run**. The response should be `200` with JSON such as `{"processed": 0}`.

Gotchas: 30 s timeout (the endpoint processes a small batch and returns quickly). cron-job.org disables a job after more than 25 consecutive failures.

### 2.13 If a secret leaks, or when rotating

| Secret | Rotate by | Side effect |
|---|---|---|
| `DJANGO_SECRET_KEY` | new value in Render | Admin sessions and pending email/reset links become invalid |
| `JWT_SIGNING_KEY` | new value in Render | Every user is logged out once |
| `PROXY_SHARED_SECRET` | change Render **and** the Cloudflare secret together | Until both match, all users share one IP for rate limiting |
| `INTERNAL_CRON_SECRET` | Render + GitHub secret + cron-job.org header | Scheduled calls fail until all three match |
| `BREVO_API_KEY` | Brevo → API Keys → delete + generate → Render | none |
| Neon password | Neon → Roles → Reset → new `DATABASE_URL` in Render | Brief reconnect |
| Upstash password | Upstash → database → Reset password → new `REDIS_URL` | Cache is cold |
| `SENTRY_DSN` | Sentry → Client Keys → new key / revoke | none |

If a secret was ever **committed to git**, rotate it **first**, then clean history. A committed secret must be treated as public even after deletion (guide §15.2).

---

## Master table: every variable and where it lives

| Variable | Local file | Production home | Section |
|---|---|---|---|
| `DJANGO_SECRET_KEY` | backend/.env | Render | 1.2 / 2.1 |
| `DJANGO_DEBUG` | backend/.env | Render | 1.3 / 2.6 |
| `DJANGO_ALLOWED_HOSTS` | backend/.env | Render | 1.3 / 2.6 |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | backend/.env | Render | 1.3 / 2.6 |
| `ADMIN_URL_PATH` | backend/.env | Render | 1.3 / 2.1 |
| `DATABASE_URL` | backend/.env | Render | 1.4 / 2.2 |
| `REDIS_URL` | backend/.env | Render | 1.4 / 2.3 |
| `FRONTEND_ORIGIN` | backend/.env | Render | 1.3 / 2.6 |
| `PROXY_SHARED_SECRET` | backend/.env **and** frontend/.env.local | Render **and** Worker Secret | 1.2 / 2.1 / 2.7 |
| `AUTH_COOKIE_SECURE` | backend/.env | Render | 1.3 / 2.6 |
| `JWT_SIGNING_KEY` | backend/.env | Render | 1.2 / 2.1 |
| `JWT_ACCESS_TOKEN_MINUTES`, `JWT_REFRESH_TOKEN_DAYS` | backend/.env | Render | 1.3 / 2.6 |
| `TURNSTILE_SECRET_KEY` | backend/.env | Render | 1.5 / 2.8 |
| `GOOGLE_OAUTH_CLIENT_ID` | backend/.env | Render | 1.6 / 2.9 |
| `EMAIL_PROVIDER`, `DEFAULT_FROM_EMAIL`, `BREVO_API_KEY` | backend/.env | Render | 1.3 / 2.4 |
| `REPORT_THRESHOLD`, `REPORT_WINDOW_HOURS`, `REPORT_MIN_ACCOUNT_AGE_HOURS`, `CONFIDENCE_THRESHOLD`, `FACT_POSTS_PER_DAY`, `FEED_CACHE_SECONDS` | backend/.env | Render (initial values; then Django Admin) | 1.3 |
| `PIPELINE_BACKEND`, `PIPELINE_INLINE_KICK`, `PIPELINE_URL`, `PIPELINE_API_KEY` | backend/.env | Render | 1.3 |
| `INTERNAL_CRON_SECRET` | backend/.env | Render + GitHub secret + cron-job.org header | 1.2 / 2.1 / 2.10 / 2.12 |
| `SENTRY_DSN`, `SENTRY_ENVIRONMENT`, `SENTRY_TRACES_SAMPLE_RATE` | backend/.env | Render | 1.3 / 2.5 |
| `PYTHON_VERSION`, `WEB_CONCURRENCY` | (none) | Render only | 2.6 |
| `BACKEND_ORIGIN` | frontend/.env.local | `frontend/wrangler.jsonc` `vars` (+ GitHub variable for keepalive) | 1.3 / 2.7 / 2.10 |
| `NEXT_PUBLIC_SITE_URL` | frontend/.env.local | Workers Builds build variable | 1.3 / 2.7 |
| `NEXT_PUBLIC_TURNSTILE_SITE_KEY` | frontend/.env.local | Workers Builds build variable | 1.5 / 2.8 |
| `NEXT_PUBLIC_GOOGLE_CLIENT_ID` | frontend/.env.local | Workers Builds build variable | 1.6 / 2.7 |
| `NODE_VERSION` | (none) | Workers Builds build variable (optional) | 2.7 |
