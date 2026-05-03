# Layer 0 Control Plane

Last updated: 2026-05-02

Purpose: one map for the instructions that govern agent work. This file does not replace the launch design doc; it tells agents which local instructions are current, which are stale, and what must be inventoried before Layer 0 cleanup starts.

## Current Boundary

- Canonical runnable checkout: `/Users/jacobbrizinski/Projects/kitty`
- Not runnable for this work: `/Users/jacobbrizinski/Documents/Kitty`
- Retired/stale path unless explicitly recreated: `/Users/jacobbrizinski/Projects/kitty-system/kitty-app`
- Current product target: B launch for technical friends running their own local copy.
- Current system target: Layer 0 cleanup and config convergence before Layer 1 product execution.
- Project-manager surface: `kittybuilder` owns session start, dirty-tree awareness, and CTO handoff preparation.

## Authority Order

When instructions conflict, use this order:

1. Jacob's latest live instruction.
2. `AGENTS.md`.
3. `CLAUDE.md`.
4. This file.
5. `CURRENT_FOCUS.md`.
6. `TASKS.md`.
7. `docs/DECISIONS.md`.
8. The approved active spec for the current task.
9. `docs/AGENT_COORDINATION.md`, only for lane coordination.
10. Older handoffs, summaries, archives, and imported notes.

If an older file says `kitty-system/kitty-app` is active, treat that claim as stale unless Jacob explicitly reopens the migration lane.

## Active Layer 0 Sequence

1. Start the session through KittyBuilder: `python3 scripts/kitty_builder.py --brief` or `bash scripts/start-session.sh`.
2. Inventory instruction-bearing markdown, MCP servers, plugins, skills, scripts, and model/client configs.
3. Patch stale instruction sources so agents read one reality.
4. Cut MCP servers to the launch set: kanban, telegram, vault, drawthings.
5. Cut or park plugins to the launch set: commit-commands, code-review, superpowers, feature-dev.
6. Reconcile skills from actual disk inventory, not stale counts in the design doc.
7. Converge model and CLI configs; no client reinstalls unless a client is proven broken after config cleanup.
8. Implement `scripts/dorothy_bridge.py` only after KittyBuilder, CTO, Dorothy/Kanban, and Telegram roles are verified.
9. Run the Layer 0 validation gate before starting Layer 1 onboarding work.

## Layer 0 Roles

- Jacob: product owner; gives vision, yes/no/redirect, and demo feedback.
- CTO agent: architecture, review, technical decisions, merge judgment.
- KittyBuilder: project manager/workbench; starts sessions, reads the control plane, inventories dirty state, prepares CTO handoffs, and tracks approved work.
- Dorothy: board, vault, and Telegram notification layer.
- Bridge daemon: later automation that moves approved cards into builder/pipeline execution.

## Required Inventory Before Deleting Anything

Write or update `docs/audits/layer0-instruction-inventory-2026-05-01.md` with:

- Markdown files that can steer agents, classified as authoritative, active reference, stale needs patch, archive only, vendor/tool docs, or data/staging.
- MCP servers from `~/.claude/mcp.json`.
- Claude plugins from `~/.claude/plugins/installed_plugins.json`.
- Skill roots and counts from `.claude/skills`, `.agents/skills`, `~/.claude/skills`, and `~/.agents/skills`.
- Scripts under `scripts/`.
- Config files that affect model routing or agent behavior.

Deletion, archive, or disable work starts only after this inventory names the exact target and rollback path.

## Layer 0 Ready Gate

Layer 0 is ready when all are true:

- `venv/bin/python -m pytest tests/ -q --tb=short` passes.
- `docs/LAYER0_CONTROL_PLANE.md` and `docs/audits/layer0-instruction-inventory-2026-05-01.md` are current.
- No active instruction file claims `kitty-system/kitty-app` is the active runtime.
- MCP server list matches the approved launch set or has a documented exception.
- Plugin list matches the approved launch set or has a documented exception.
- Skills are reconciled from actual disk inventory with keep/cut/reactivate lists.
- Config files contain no literal secrets and each CLI can report help/version from the repo.
- A real or dry-run Dorothy/Kanban task can move through the intended Layer 0 flow with evidence.
