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

