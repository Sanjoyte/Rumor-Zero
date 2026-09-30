# Rumor Zero: live handoff

Update this file at meaningful checkpoints and before switching between Claude Code and Codex.
Keep it concise and factual. The incoming agent must verify it against the current files and
read-only git output.

## Active work

- **Part:** 0A (Backend foundation). **Planned and approved; implementation not started.**
- **Owner:** none (idle until the user starts the implementing agent)
- **Phase:** ready to implement 0A
- **Last approved plan:** `docs/agents/plans/part-0A-backend-foundation.md` (approved 2026-09-30 by
  the user). The earlier `part-pre0A-verified-fixes.md` is done.
- **Last updated:** 2026-09-30 by Claude (Opus 5.5), Part 0A planning

## Completed checkpoints

- Dual-agent setup (shared `AGENTS.md`, Claude/Codex adapters, memory, handoff, plans, Codex model
  matrix): committed by the user as `dbe02e6`.
- 2026-09-30 (Claude), pre-0A correction pass, committed by the user as `c25d479`. It verified five
  reported issues and fixed them:
  1. The docs PDF's working copy was corrupted by `core.autocrlf=true` (the committed blob was
     intact). Added root `.gitattributes` (`* text=auto eol=lf` + `binary` types) and restored the
     working-copy bytes. They now hash to the HEAD blob `1008f7036a406f1ad098f9391cff59a85eb7d0a2`.
  2. `is_staff = is_superuser or role != user` (ARCHITECTURE §2, ANALYSIS c-10, task.md 0A).
  3. The Sentry init spec adds an `EventScrubber` denylist for the three `X-RZ-*` headers,
     `max_request_body_size="never"` and `include_local_variables=False` (task.md 0A,
     ARCHITECTURE §12, ENV_GUIDE §2.5).
  4. Generated code is normalised with `ruff check --fix . ; ruff format .` (AGENTS.md, task.md 0A).
  5. The `startapp` folder and `apps.<name>` steps (AGENTS.md, task.md 0A, STRUCTURE); hermetic
     tests and the CI env file from `.env.example` (task.md 0A/0C, ARCHITECTURE §11).

- 2026-09-30 (Claude), Part 0A planning. Read-only checks:
  - The 0A prerequisites (SETUP Part A, ENV_GUIDE §1.1–1.4) are met: Python 3.13.15, Docker engine
    29.7.2 running, Compose v5.4.0, `RemoteSigned`, `backend/.env` present (not read), ports
    5432/6379/8000 free.
  - Every SETUP B1/B2 pin is still the latest on PyPI.
  - User decisions: admin login by **email** (`USERNAME_FIELD="email"`) and an **exact-match**
    reserved-username list (full list in the plan).

## Current workspace state

- Tree was clean at `c25d479` when planning started. Uncommitted now: only the files listed below.
- 25 tracked text files are still CRLF in the working tree from earlier checkouts; their index
  copies are LF. Git may warn "CRLF will be replaced by LF". This is harmless; do not normalize them
  as a separate change.
- No product implementation part has started. No dependencies were installed, no containers were
  started and no real env file was read.

## Validation

Part 0A planning: application tests don't apply yet (nothing is scaffolded). `git diff --check`
exits 0.

Earlier, from the pre-0A correction pass:

- Passed: `git hash-object --no-filters <pdf>` equals `git rev-parse HEAD:<pdf>`
  (`1008f70…`); the size is 554,315 and `startxref` lands on `xref`.
- Passed: `git check-attr -a <pdf>` → `binary: set`, `text: unset`.
- Passed: `git diff --quiet -- <pdf>` → exit 0 (no content change).
- Passed: `git diff --check` → exit 0.
- Passed: `.gitattributes` has LF endings and no trailing whitespace.
- Passed: grep finds no `role != user` without the superuser clause, and no remaining "never sends
  passwords or tokens (`send_default_pii=False`)" claim (outside the plan, which quotes the old text).
- Not run: Django `startproject`/`startapp`/`makemigrations` + ruff. Issue 4 was verified against the
  Django 5.2 template sources, because nothing is scaffolded yet. Part 0A's `ruff format --check .`
  criterion exercises it.
- Application tests: not applicable (not scaffolded).

## Next exact action

1. The user reviews and (optionally) commits the plan and this file.
2. The user starts a fresh session with **Sonnet 5.5 · medium** (Claude) or **GPT-6.1 Sol · medium**
   (Codex) and prompts:
   `Implement only the approved Part 0A plan, validate it, update task.md and HANDOFF.md, then stop.`
3. The implementing agent reads `docs/agents/plans/part-0A-backend-foundation.md` and starts at its
   step 0. The pre-0A follow-ups (test `__init__.py`, migrations E501 ignore, secret variable
   naming) are already folded into that plan.

## Blockers or user decisions

- None open. The two 0A decisions are recorded in the plan.

## Files changed for the current work (uncommitted)

- `docs/agents/plans/part-0A-backend-foundation.md` (new, approved plan)
- `docs/agents/HANDOFF.md`

## Handoff checklist (outgoing agent)

- [ ] Stop editing before the incoming agent starts.
- [ ] Record current owner, phase and approved plan.
- [ ] Record files changed and any unrelated pre-existing modifications.
- [ ] Record every validation command and its exact pass/fail result.
- [ ] Record blockers, user decisions and the next exact action.
- [ ] Promote only durable, non-duplicated knowledge to `MEMORY.md`.
