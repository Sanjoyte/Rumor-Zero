# Rumor Zero: live handoff

Update this file at meaningful checkpoints and before switching between Claude Code and Codex.
Keep it concise and factual. The incoming agent must verify it against the current files and
read-only git output.

## Active work

- **Part:** none — dual-agent setup only; no `task.md` build part has started.
- **Owner:** none (idle)
- **Phase:** ready to plan
- **Approved plan:** none
- **Last updated:** 2026-09-30 by Claude (CLAUDE.md import fix)

## Completed checkpoints

- Added a shared instruction source and separate Claude/Codex adapters.
- Added Codex defaults and command rules matching the repository's no-git-mutations policy.
- Added durable memory, handoff and approved-plan locations.
- Added a per-part Codex model matrix to `task.md`.
- 2026-09-30 (Claude): replaced the prose pointer at the top of `CLAUDE.md` with an `@AGENTS.md`
  import. With both files present, Claude Code loads only `CLAUDE.md`, so the shared rules were
  not in Claude's context unless it chose to open `AGENTS.md`. The import loads them at startup
  and after `/compact`.

## Current workspace state

- The archive Codex inspected reported many tracked files as modified. Claude verified these were
  line-ending (CRLF/LF) differences only, with no content changes. Preserve them anyway; do not
  restore, reset or normalize unrelated files.
- No product implementation part has started.
- No dependencies were installed and no real env file was read.

## Validation

- Passed: `.claude/settings.json` parses as JSON; `.codex/config.toml` parses as TOML with the
  expected model and effort.
- Passed: all 27 `task.md` parts have exactly one Codex plan/implementation mapping in the same
  order.
- Passed: the new continuity files exist, are non-empty, have no trailing whitespace and are not
  ignored by Git; the edited tracked files pass `git diff --check`.
- Not run: `codex execpolicy check`, because Codex CLI is unavailable in the archive-inspection
  environment. The rules use the current documented `prefix_rule` format and must be checked on
  the user's first local Codex run.
- Application tests: not applicable; the repository has not been scaffolded yet.

## Next exact action

1. The user chooses Part 0A or Part 0B and one agent.
2. The chosen agent reads `AGENTS.md`, this file, `MEMORY.md`, the selected `task.md` part and its
   relevant architecture/setup sections.
3. It creates a plan under `docs/agents/plans/`, asks the user to approve it, records itself as
   owner here, then implements only the approved part.

## Blockers or user decisions

- None.

## Files changed for the current work

- `AGENTS.md`
- `CLAUDE.md`
- `.codex/config.toml`
- `.codex/rules/default.rules`
- `docs/agents/MEMORY.md`
- `docs/agents/HANDOFF.md`
- `docs/agents/plans/README.md`
- `task.md`
- agent-related wording in `docs/STRUCTURE.md`, `docs/SETUP.md`, `docs/ENV_GUIDE.md` and
  `docs/ARCHITECTURE.md`

## Handoff checklist (outgoing agent)

- [ ] Stop editing before the incoming agent starts.
- [ ] Record current owner, phase and approved plan.
- [ ] Record files changed and any unrelated pre-existing modifications.
- [ ] Record every validation command and its exact pass/fail result.
- [ ] Record blockers, user decisions and the next exact action.
- [ ] Promote only durable, non-duplicated knowledge to `MEMORY.md`.
