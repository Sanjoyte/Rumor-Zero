# Rumor Zero: live handoff

Update this file at meaningful checkpoints and before switching between Claude Code and Codex.
Keep it concise and factual. The incoming agent must verify it against the current files and
read-only git output.

## Active work

- **Part:** none. The pre-0A correction pass is **done**; no `task.md` build part has started.
- **Owner:** none (idle)
- **Phase:** ready to plan Part 0A or 0B
- **Last approved plan:** `docs/agents/plans/part-pre0A-verified-fixes.md` (done 2026-09-30)
- **Last updated:** 2026-09-30 by Claude (pre-0A correction pass finished)

## Completed checkpoints

- Dual-agent setup (shared `AGENTS.md`, Claude/Codex adapters, memory, handoff, plans, Codex model
  matrix): committed by the user as `dbe02e6`.
- 2026-09-30 (Claude), pre-0A correction pass. It verified five reported issues and fixed them:
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

## Current workspace state

- Uncommitted: the files listed below.
- `git status` still shows the PDF as ` M`, although `git diff --quiet -- <pdf>` exits 0 and the
  bytes hash to the HEAD blob. The index still caches the old working-copy size (556,226), and git
  treats a size mismatch as a change without comparing content. **The user** runs
  `git add docs/fact-based-social-platform-architecture-guide.pdf`, which stages no new content
  (same blob), and the entry becomes clean.
- 25 tracked text files are still CRLF in the working tree from earlier checkouts; their index
  copies are LF. Git may warn "CRLF will be replaced by LF". This is harmless; do not normalize them
  as a separate change.
- No product implementation part has started. No dependencies were installed and no real env file
  was read.

## Validation

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

1. The user reviews the diff, runs `git add` on the PDF (see above) and commits.
2. The user chooses Part 0A or Part 0B and one agent.
3. The chosen agent reads `AGENTS.md`, this file, `MEMORY.md`, the selected `task.md` part and its
   relevant architecture/setup sections.
4. It creates a plan under `docs/agents/plans/`, asks the user to approve it, records itself as
   owner here, then implements only the approved part. The Part 0A planner should also take the
   follow-ups at the end of `part-pre0A-verified-fixes.md`.

## Blockers or user decisions

- None.

## Files changed for the current work (uncommitted)

- `.gitattributes` (new)
- `docs/fact-based-social-platform-architecture-guide.pdf` (working copy only; same blob as HEAD)
- `AGENTS.md`, `task.md`
- `docs/ARCHITECTURE.md`, `docs/ANALYSIS.md`, `docs/ENV_GUIDE.md`, `docs/STRUCTURE.md`
- `docs/agents/MEMORY.md`, `docs/agents/HANDOFF.md`
- `docs/agents/plans/part-pre0A-verified-fixes.md` (new)

## Handoff checklist (outgoing agent)

- [ ] Stop editing before the incoming agent starts.
- [ ] Record current owner, phase and approved plan.
- [ ] Record files changed and any unrelated pre-existing modifications.
- [ ] Record every validation command and its exact pass/fail result.
- [ ] Record blockers, user decisions and the next exact action.
- [ ] Promote only durable, non-duplicated knowledge to `MEMORY.md`.
