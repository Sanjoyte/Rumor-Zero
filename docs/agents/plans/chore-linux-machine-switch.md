# Chore: move development to a Linux PC (dual Linux/Windows docs and a clean-clone check)

**Status:** approved 2026-10-06 by the user (Sanjoy Rozario); **implemented and validated the same
day**. Results: `docs/agents/HANDOFF.md` ("Validation of the Linux clean-room run"). Deviation from the
plan: one line added to `.gitignore` (`compose.override.yaml`, the local IPv6 workaround file); the
`MEMORY.md` entry was written because the run produced durable facts.
**Part:** none (a documentation chore between Part 1 and Part 2; no `task.md` part is touched).
**Dependencies:** Part 1 committed in `d9d1358`; CI green (user-reported, 2026-10-06).

## Scope and user decisions

- The user moves development from this Windows 11 PC to a Linux PC running **Ubuntu / Debian /
  Mint**. They want to `git pull`, follow `docs/SETUP.md` and `docs/ENV_GUIDE.md`, and have
  everything work.
- `docs/SETUP.md`, `docs/ENV_GUIDE.md` and `docs/test-command.md` get **both** a Linux and a Windows
  version, **Linux first**.
- At the end: check `.gitignore` and the working tree for anything important left behind, and give a
  green/not-green verdict.

## Audit result (read-only, before editing)

- `git status -sb` clean; `main...origin/main` with nothing ahead. Everything ignored by git is
  regenerable (`.venv`, `node_modules`, `.next`, `.wrangler`, caches, test output,
  `tsconfig.tsbuildinfo`, `next-env.d.ts`, `.coverage`) except `backend/.env` and
  `frontend/.env.local`, which hold only local-dev values (examples + ENV_GUIDE §1.2 recreate them).
- Tracked and present: both `.env.example`, `package-lock.json` (with the Linux binaries),
  `requirements*.txt`, `pyproject.toml`, `compose.yaml`, `.gitattributes`, `ci.yml`, `design/`,
  every generated brand asset, `docs/agents/**`, `.claude/settings.json`, `.codex/**`.
- No CRLF in the index, no case-only duplicate paths, no shell scripts or exec bits, no Claude
  auto-memory and no `.claude/settings.local.json`. `playwright.config.ts` already picks
  `.venv/bin/python` off Windows.

## Files expected to change (documentation and comments only)

`docs/SETUP.md`, `docs/ENV_GUIDE.md`, `docs/test-command.md`, `AGENTS.md` (Commands block and the
shell bullet), `backend/.env.example` and `frontend/.env.example` (header comments only),
`docs/agents/HANDOFF.md`, this plan, and `docs/agents/MEMORY.md` only for a durable Linux finding.

## Ordered steps

1. Save this plan (done). Check the Linux install commands against current primary documentation.
2. `SETUP.md`: Linux Part A (quick start, Git/SSH, Python 3.13, Node 24 via nvm, Docker Engine,
   extras), Windows Part A kept, "Moving to a new machine" section.
3. `ENV_GUIDE.md`: Linux commands above the PowerShell ones (§1.1, §1.2, §1.4, §1.5, §2.1, §2.6) and
   a new §1.9 "Using the files on another machine".
4. `test-command.md`: Linux (bash) block above every Windows (PowerShell) block (51 of them); shared
   prose and expected output.
5. `AGENTS.md` Commands block and shell bullet; `.env.example` header comments.
6. Validate: `bash -n` on every new bash block; a clean-room run in Docker's Linux engine from
   `git ls-files -co --exclude-standard`, following the Linux sections literally (backend 440
   tests, frontend 562 tests, build, dev servers + `/api/health/` through the relay, Part 0A step 3
   and Part 1 steps 3-5 against the live servers).
7. Refresh `docs/agents/HANDOFF.md` with the facts and the verdict.

## Non-goals and stop conditions

- No code, config, env or git changes. The user commits and pushes.
- Not provable here: apt/PPA/Docker-repo installs on the real Ubuntu, the `docker` group login,
  IPv6 `[::1]` binding, GitHub SSH auth, Playwright's system libraries. The guides say what to do
  if each fails and the verdict says so.
- Stop and report if the clean-room run exposes a code change, if a required env value is something
  the examples don't cover, or if Docker Desktop is unavailable.
