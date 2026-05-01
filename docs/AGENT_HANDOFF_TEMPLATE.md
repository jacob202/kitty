# Agent Handoff Template

Use this template at the end of every agent session.
Copy the block below into `docs/AGENT_COORDINATION.md` under the
Recent Handoffs section, fill in the blanks, and remove the `[ ]` markers.

```markdown
### YYYY-MM-DD HH:MM {agent_id} session

**Done**:
- [bullet list of what was accomplished]

**Files changed**: [list files created/modified/deleted]

**Tests**: [test results — command run, pass/fail count]

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

**Done**:
- Synced default_web_chat_mode from legacy to migrated workspace
- Ran Phase 4 merge gate: PASS (354 tests, route smoke green)
- Changed default web chat mode from balanced to fast

**Files changed**: `src/api/shared.py`, `tests/test_default_web_chat_mode.py`

**Tests**: `pytest tests/` → 354 passed, 2 warnings

**Outstanding**: None

**Feedback for other agents**:
- `to: codex | about: src/api/shared.py | default_web_chat_mode now returns "fast" when unset — make sure new socket/chat code respects this | evidence: tests/test_default_web_chat_mode.py:11`

**Next suggested action**: Sync to migrated workspace, commit in legacy repo
```
---

## Rules

1. **Always leave a handoff.** No silent session exits.
2. **Be specific.** "Fixed a bug" is useless. "Fixed NPE in `src/api/shared.py:150` when `KITTY_WEB_DEFAULT_MODE` is empty string" is useful.
3. **Include test evidence.** What command did you run and what passed?
4. **Name agents in feedback.** Use their registered ID from the Agent Registry.
5. **Keep outstanding items actionable.** "Something might be broken" is noise. "Route `/api/brief` returns 500 when `CURRENT_FOCUS.md` is missing — need error handling" is actionable.
