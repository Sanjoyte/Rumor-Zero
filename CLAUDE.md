@AGENTS.md

# Claude Code entry point: Rumor Zero

The shared Claude Code + Codex rules are imported above from `AGENTS.md`. Obey them in full.
Before planning or editing, read `docs/agents/HANDOFF.md`, `docs/agents/MEMORY.md`, the named part
in `task.md`, the relevant architecture sections and the approved plan, exactly as `AGENTS.md`
directs.

Claude-specific behavior:

- `.claude/settings.json` enforces Claude Code permissions. Its restrictions do not replace the
  hard rules in `AGENTS.md`.
- Use Claude's plan mode for planning. Save the user-approved plan under `docs/agents/plans/`
  before implementation so Codex can take over without reconstructing it from chat.
- Before Claude stops, switches models, reaches a usage/context limit or hands work to Codex,
  update `docs/agents/HANDOFF.md` with the exact current state and next action.
- Claude Code's auto memory is local to this machine and invisible to Codex. Record durable
  project knowledge in `docs/agents/MEMORY.md`, not only in auto memory.
- Put shared rule changes in `AGENTS.md`. Edit this file only for Claude-specific startup or tool
  behavior; do not duplicate the shared instructions here.
