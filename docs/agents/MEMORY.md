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
