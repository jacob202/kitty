# Agent Handoff Template

Use this template at the end of every agent session.
Copy the block below into `docs/AGENT_COORDINATION.md` under the
Recent Handoffs section, fill in the blanks, and remove the `[ ]` markers.

```markdown
### YYYY-MM-DD HH:MM {agent_id} session

**Lane**: [lane ID]

**Workspace**: [absolute path used for this work]

**Branch**: [git branch or `detached` / `n/a`]

**Blocked**: [yes — why | no]

**Legacy context** (optional): [paths or searches under `/Users/jacobbrizinski/Projects/kitty` used before creating or renaming files]

**Done**:
- [bullet list of what was accomplished]

**Files changed**: [list files created/modified/deleted]

**Allowed by**: [spec/intake/user request that authorized these files]

**Tests**: [test results; include command run and pass/fail count]

**Sync state**: [legacy only | migrated only | synced legacy to migrated | read-only]

**Outstanding**:
- [open questions, blocking items, known risks]

**Feedback for other agents**:
- `to: {agent_id} | about: {file/feature} | {observation} | evidence: {test result or file:line}`
- (add more as needed — these get promoted to the Feedback Queue)

**Next suggested action**: [what the next agent should do]
```
---

## Example (filled)

```markdown
### 2026-04-30 opencode session

**Lane**: `sync-gate`

**Workspace**: `/Users/jacobbrizinski/Projects/kitty`

**Branch**: `main`

**Blocked**: no

**Legacy context** (optional): `docs/`, `specs/`, `CURRENT_FOCUS.md` in legacy checkout

**Done**:
- Synced default_web_chat_mode from legacy to migrated workspace
- Ran Phase 4 merge gate: PASS (354 tests, route smoke green)
- Changed default web chat mode from balanced to fast

**Files changed**: `src/api/shared.py`, `tests/test_default_web_chat_mode.py`

**Allowed by**: Phase 4 merge-gate/default web chat mode worker scope

**Tests**: `pytest tests/` → 354 passed, 2 warnings

**Sync state**: synced legacy to migrated

**Outstanding**: None

**Feedback for other agents**:
- `to: codex | about: src/api/shared.py | default_web_chat_mode now returns "fast" when unset — make sure new socket/chat code respects this | evidence: tests/test_default_web_chat_mode.py:11`

**Next suggested action**: Sync to migrated workspace, commit in legacy repo
```
---

## Rules

1. **Always leave a handoff.** No silent session exits.
2. **Name the lane and workspace.** Future agents need to know whether the work touched legacy git, migrated runtime, or both.
3. **Legacy context before create.** When you added or renamed files, say what you checked under `/Users/jacobbrizinski/Projects/kitty` first (or mark N/A if session was read-only on migrated-only paths).
4. **Be specific.** "Fixed a bug" is useless. "Fixed NPE in `src/api/shared.py:150` when `KITTY_WEB_DEFAULT_MODE` is empty string" is useful.
5. **Include authorization and test evidence.** Name the spec/intake/user request and the exact validation command.
6. **Record sync state.** If legacy and migrated workspaces differ, say that plainly.
7. **Name agents in feedback.** Use their registered ID from the Agent Registry.
8. **Keep outstanding items actionable.** "Something might be broken" is noise. "Route `/api/brief` returns 500 when `CURRENT_FOCUS.md` is missing - need error handling" is actionable.
