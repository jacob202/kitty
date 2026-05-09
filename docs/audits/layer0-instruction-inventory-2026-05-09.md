# Layer 0 Instruction Inventory
_Audited: 2026-05-09_

## MCP Servers (`~/.claude/mcp.json`)

| Name | Command | Status |
|------|---------|--------|
| `claude-mgr-telegram` | Dorothy.app `mcp-telegram/dist/bundle.js` | Active (binary exists) |
| `claude-mgr-kanban` | Dorothy.app `mcp-kanban/dist/bundle.js` | Active (binary exists) |
| `claude-mgr-vault` | Dorothy.app `mcp-vault/dist/bundle.js` | Active (binary exists) |
| `drawthings` | npx `mcp-drawthings@1.1.2` port 7859 | Conditional (requires DrawThings app running) |

**Dorothy.app also ships:** `mcp-orchestrator`, `mcp-socialdata`, `mcp-world`, `mcp-x` — available but not wired. MCP expansion is forbidden in current phase; leave unregistered.

**Dependency note:** `drawthings` fails silently if DrawThings.app is not running on localhost:7859.

---

## Installed Plugins (`~/.claude/plugins/installed_plugins.json`)

| Plugin | Version | Enabled | Notes |
|--------|---------|---------|-------|
| `superpowers` | 5.0.7 + git SHA | ✅ | Pinned — gold standard |
| `pyright-lsp` | 1.0.0 | ✅ | Pinned |
| `commit-commands` | unknown | ✅ | Registry has no semver; is latest available |
| `code-review` | unknown | ✅ | Registry has no semver; is latest available |
| `feature-dev` | unknown | ✅ | Registry has no semver; is latest available |
| `frontend-design` | unknown | ✅ | Registry has no semver; is latest available |
| `agent-sdk-dev` | unknown | ✅ | Enabled 2026-05-09; relevant — Kitty uses anthropic SDK |
| `security-guidance` | unknown | ❌ | Installed but disabled; re-evaluate when needed |
| `pr-review-toolkit` | unknown | ❌ | Installed but disabled; re-evaluate when needed |

---

## Skills Available in Session

### superpowers v5.0.7 (14 skills)
- `using-superpowers` — meta: how to use skills (loads at every session start)
- `brainstorming` — ideation before building
- `systematic-debugging` — bug investigation workflow
- `dispatching-parallel-agents` — parallel task delegation
- `executing-plans` — plan execution with checkpoints
- `finishing-a-development-branch` — integration decision guide
- `using-git-worktrees` — isolation for feature branches
- `test-driven-development` — TDD workflow
- `writing-plans` — multi-step planning pipeline
- `requesting-code-review` — post-implementation review trigger
- `receiving-code-review` — processing review feedback
- `writing-skills` — authoring new skills
- `verification-before-completion` — pre-commit verification
- `subagent-driven-development` — parallel implementation via subagents

### Other Enabled Plugins
- `commit-commands`: commit, commit-push-pr, clean_gone
- `code-review`: code-review
- `feature-dev`: feature-dev
- `frontend-design`: frontend-design
- `agent-sdk-dev`: claude-api (+ SDK-specific guidance)

---

## Settings (`~/.claude/settings.json`)
- `defaultMode: plan` — all sessions start in plan mode
- `skipAutoPermissionPrompt: true`
- `useAutoModeDuringPlan: false`
- Voice: enabled, hold-to-speak mode

---

## What Changed in This Audit Session (2026-05-09)
- `agent-sdk-dev` enabled (was disabled; Kitty imports anthropic SDK so this is relevant)
- This inventory document created (was missing; referenced in LAYER0_CONTROL_PLANE.md)
- 4 stale plugins confirmed latest via `claude plugin update` — "unknown" version is a registry metadata issue, not a local problem
