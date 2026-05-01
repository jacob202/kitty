# Spec: Agent Coordination Protocol

## Problem

Multiple AI agents (OpenCode/Claude, Codex, Cursor Composer) work on the same
codebase asynchronously. Without a shared coordination channel, agents risk
stepping on each other's work, losing context between sessions, and failing to
learn from each other's discoveries. The existing DELEGATION_BOARD.md handles
task assignment but has no inter-agent messaging, feedback, debate, or learning
accumulation.

## Proposed shape

A pair of coordination files in `docs/` that serve as the shared workspace
for all agents:

- `docs/AGENT_COORDINATION.md` — live board showing active lanes, inter-agent
  messages, feedback queue, open debates, and accumulated learnings.
- `docs/AGENT_HANDOFF_TEMPLATE.md` — structured template for each agent's
  session-end handoff entry.

Agents read the coordination file at session start, claim lanes explicitly,
and leave a timestamped handoff at session end. They gather context from the
legacy checkout `/Users/jacobbrizinski/Projects/kitty` before creating new artifacts
so naming and prior art stay aligned with canonical git. Feedback travels through
dedicated sections with acknowledgment states. Debates resolve into learnings
that accumulate in a durable log.

Head agent (OpenCode/Claude) holds merge rights: resolves deadlocked debates,
promotes learnings to DECISIONS.md, and prunes stale entries.

## Allowed files

- `specs/agent-coordination.spec.md` (this file)
- `docs/AGENT_COORDINATION.md` (new)
- `docs/AGENT_HANDOFF_TEMPLATE.md` (new)
- `docs/FILE_GOVERNANCE.md` (add new files to control file list)
- `scripts/check_agent_coordination.py` (control-file validator)
- `tests/test_check_agent_coordination.py` (validator unit tests)

## Forbidden files

- No runtime source
- No product test modifications
- No changes to `DELEGATION_BOARD.md`
- No changes to `CURRENT_FOCUS.md` or `TASKS.md`
- No broad implementation, cleanup, UI polish, MCP expansion, or migration path rewrites

## Validation

```bash
# Coordination files + stale-lane advisory (non-blocking warnings to stderr)
/opt/homebrew/bin/python3.12 scripts/check_agent_coordination.py

# Validator unit tests
/opt/homebrew/bin/python3.12 -m pytest tests/test_check_agent_coordination.py -q --tb=short

# File existence (also enforced by script above)
test -f docs/AGENT_COORDINATION.md
test -f docs/AGENT_HANDOFF_TEMPLATE.md

# No regressions
/opt/homebrew/bin/python3.12 -m pytest tests/ -q --tb=short

# Control gates
bash scripts/run_gates.sh
```

## Rollback

```bash
rm docs/AGENT_COORDINATION.md docs/AGENT_HANDOFF_TEMPLATE.md
git checkout -- docs/FILE_GOVERNANCE.md
```

## Risks

- Agents not trained on the protocol may skip reading the coordination file.
  Mitigation: references in AGENTS.md and CURRENT_FOCUS.md redirect to it.
- A lane row may be mistaken for authorization to edit runtime or UI files.
  Mitigation: the board now states that lane rows coordinate work only; specs,
  current focus, and file governance authorize edits.
- Agents may confuse the legacy git checkout with the migrated runtime
  workspace. Mitigation: handoffs require the workspace and sync state, and the
  board records both path roles.
- Coordination file can grow large. Mitigation: head agent prunes resolved/stale
  entries and archives to `docs/archive/agent-coordination/`.
- Agents could talk past each other with overlapping claims. Mitigation: explicit
  lane-claiming protocol with timestamps and ownership.

## Minimum safe version

Immediately — no runtime code changes, pure control-doc addition.
