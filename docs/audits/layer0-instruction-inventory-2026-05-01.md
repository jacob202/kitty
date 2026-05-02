# Layer 0 Instruction Inventory

Date: 2026-05-01

Purpose: evidence for the Layer 0 cleanup. This file inventories instruction sources and tool surfaces before any deletion or archive pass.

## Snapshot

- Markdown files under repo, excluding common dependency folders: 346.
- Project `.claude/skills`: 10 `SKILL.md` files.
- Project `.agents/skills`: 12 `SKILL.md` files.
- User `~/.claude/skills`: 10 `SKILL.md` files.
- User `~/.agents/skills`: 17 `SKILL.md` files.
- User Claude MCP servers: 8.
- User Claude plugins: 9.

Commands used:

```bash
find . -path './.git' -prune -o -path './node_modules' -prune -o -path './garage-ui/node_modules' -prune -o -path './venv' -prune -o -name '*.md' -print | wc -l
find .claude/skills -maxdepth 2 -name SKILL.md | wc -l
find .agents/skills -maxdepth 2 -name SKILL.md | wc -l
find ~/.claude/skills -maxdepth 2 -name SKILL.md | wc -l
find ~/.agents/skills -maxdepth 2 -name SKILL.md | wc -l
python3 -m json.tool ~/.claude/mcp.json
python3 -m json.tool ~/.claude/plugins/installed_plugins.json
```

## Authoritative

| File | Role | Notes |
|------|------|-------|
| `AGENTS.md` | Cross-agent repo rules | First read for Codex/delegated workers. Must point at this inventory/control plane. |
| `CLAUDE.md` | Claude Code project rules | Contains storage routing, model routing, workspace gotchas, handoff rules. |
| `docs/LAYER0_CONTROL_PLANE.md` | Layer 0 authority map | New control-plane manifest for this cleanup. |
| `CURRENT_FOCUS.md` | Current allowed/forbidden work | Already dirty before this pass; do not patch casually. |
| `TASKS.md` | Current done/next-action ledger | Already dirty before this pass; do not patch casually. |
| `docs/DECISIONS.md` | Durable decisions | Contains stale/superseded migration entries; needs a later decision cleanup. |

## Active Reference

| File | Role | Notes |
|------|------|-------|
| `docs/superpowers/specs/2026-05-01-kitty-launch-plan-design.md` | Strategic B-launch design | Accept as blueprint, not exact inventory. Skill/plugin counts must be verified from disk. |
| `docs/AGENT_COORDINATION.md` | Lane coordination | Coordinates work, does not authorize work. Older workspace text needed patching. |
| `docs/FILE_GOVERNANCE.md` | File edit boundaries | Must use canonical checkout path. |
| `docs/BUILDER_INTAKE.md` | Intake requirements | Must use canonical checkout path. |
| `docs/BUILDER_DIRECTIVE.md` | Builder invocation contract | Must use canonical checkout path. |
| `docs/PARKED_FEATURES.md` | Parked/not-current work | Physical split entry needed status update after consolidation. |
| `docs/GATES.md` | Control-layer gates | Reference for validation commands. |

## Stale Or Historical

| File | Issue | Treatment |
|------|-------|-----------|
| `KITTY_CONTEXT.md` | Claimed `kitty-system/kitty-app` active. | Patch to point at `docs/LAYER0_CONTROL_PLANE.md` and canonical checkout. |
| `SESSION_SUMMARY.md` | Contains older migration-lane instructions. | Historical only unless refreshed. |
| `docs/HANDOFF.md` | Contains old Gemini handoff and active migrated workspace instructions. | Add stale banner; do not use for current authority. |
| `docs/TASKS.md` | Older backlog separate from root `TASKS.md`. | Reference only. Root `TASKS.md` wins. |
| `docs/MARKET_READY_EXECUTION_PLAN_2026-04-30.md` | Pre-consolidation execution framing. | Reference only. |
| `docs/audits/operational-plan-20260430.md` | Phase A-D historical plan. | Reference only; not current control plane. |
| `.claude/HANDOFF-2026-05-01-*.md` | Handoff context. | Source evidence, not standing authority. |

## Vendor, Tool, Archive, Data

- `docs/archive/**`: archive only unless a current spec explicitly imports from it.
- `src/tools/lightrag/**`: vendor/tool docs, not Kitty instructions.
- `src/tools/superpowers/**`: tool docs, not Kitty repo authority.
- `data/staging/**`: ingested/source material, not agent instructions.
- `benchmarks/tasks/**`: benchmark prompts, not project control docs.
- `.pytest_cache/**`: generated cache docs, ignore.

## MCP Inventory

From `~/.claude/mcp.json`:

Status after cleanup: active config now has 4 MCP servers. Backup: `~/.claude/mcp.json.bak-2026-05-01-layer0`.

Keep target:

- `claude-mgr-kanban`
- `claude-mgr-telegram`
- `claude-mgr-vault`
- `drawthings`

Cut target:

- `claude-mgr-orchestrator`
- `dorothy-socialdata`
- `dorothy-x`
- `dorothy-world`

## Plugin Inventory

From `~/.claude/plugins/installed_plugins.json`:

Status after cleanup: active config now has 4 installed plugins. Backup: `~/.claude/plugins/installed_plugins.json.bak-2026-05-01-layer0`.

Keep target:

- `commit-commands@claude-plugins-official`
- `code-review@claude-plugins-official`
- `feature-dev@claude-plugins-official`
- `superpowers@claude-plugins-official`

Cut target:

- `security-guidance@claude-plugins-official`
- `pr-review-toolkit@claude-plugins-official`
- `agent-sdk-dev@claude-plugins-official`
- `pyright-lsp@claude-plugins-official`
- `frontend-design@claude-plugins-official`

## Skill Inventory Warning

The launch design doc says 43 skills total and 25 kept. Current disk counts do not directly match that because there are multiple skill roots:

- `.claude/skills`: project Claude skills.
- `.agents/skills`: project agent skills.
- `~/.claude/skills`: user Claude skills.
- `~/.agents/skills`: user agent skills.
- Codex plugin skills are loaded separately and are not represented by the Claude skill counts.

Do not cut skills by stale total count. Next step is a manifest that lists each skill by root, status, owner, and reactivation trigger.
