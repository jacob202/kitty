# Agent Coordination Board

Last updated: 2026-04-30

**Purpose**: Shared communication channel for all agents working on Kitty.
Read this at session start. Leave a handoff at session end.

Every agent is expected to:
1. Read this file at session start.
2. Claim an active lane before touching code.
3. Leave a handoff entry at session end (see template below).
4. Check the feedback queue for items addressed to you.
5. Resolve or escalate debates assigned to you.

---

## Agent Registry

| Agent ID | Name | Role | Primary Tool |
|----------|------|------|-------------|
| `opencode` | OpenCode CLI (Claude) | Head agent, architecture, final merge | Read/Write/Exec |
| `codex` | OpenAI Codex | Feature work, delegated builds | Read/Write/Exec |
| `cursor` | Cursor Composer | Frontend/UI, refactoring | Read/Write/Exec |

The head agent (`opencode`) holds:
- Final merge authority on deadlocked debates.
- Responsibility to prune stale entries and archive old threads.
- Authority to promote accumulated learnings into `docs/DECISIONS.md`.

---

## Active Lanes

Agents claim a lane before starting work. Only one agent per lane at a time.
Mark your lane `complete` when done.

| Lane ID | Agent | Started | Status | Description |
|---------|-------|---------|--------|-------------|
| _(none claimed)_ | | | | |

**Protocol**: To claim a lane, add a row above with timestamp. To release,
change status to `complete` and add a handoff entry.

---

## Completed Work Log

Recent completed lanes. Entries older than 14 days are archived.

<!-- ADD NEW ENTRIES ABOVE THIS LINE -->
<!-- Format: YYYY-MM-DD HH:MM | AGENT | LANE_ID | summary -->

| Date | Agent | Lane | Summary |
|------|-------|------|---------|
| 2026-04-30 | opencode | coordination | Built agent coordination protocol: AGENT_COORDINATION.md, AGENT_HANDOFF_TEMPLATE.md, spec |
| 2026-04-30 | opencode | sync-gate | Synced default_web_chat_mode to migrated workspace, ran Phase 4 merge gate (PASS), flipped default to fast |
| 2026-04-29 | opencode | gemini-review | Completed Gemini chat-log candidate review; propagated dispositions to DECISIONS, PARKED_FEATURES, USER_PREFS, OPEN_LOOPS |

---

## Inter-Agent Messages

Async messages between agents. Reply by adding a message referencing the
original ID.

**Rules**:
- Every message gets a unique `msg-YYYYMMDD-NN` ID.
- Reply by adding `re: msg-YYYYMMDD-NN` in the message body.
- Resolved threads move to the archive after 7 days.

### Open Messages

<!-- ADD NEW MESSAGES ABOVE THIS LINE -->

| ID | From | To | Date | Message |
|----|------|----|------|---------|
| _(no open messages)_ | | | | |

### Resolved Messages

<!-- MOVE resolved threads here with resolution noted -->

---

## Feedback Queue

Structured feedback from one agent to another. Not complaints — actionable
observations with evidence (test results, diff links, file:line references).

**State machine**: `open` → `acknowledged` → `applied` (or `disputed`)

| ID | From | To | Date | State | About | Feedback | Evidence |
|----|------|----|------|-------|-------|----------|----------|
| _(no feedback items)_ | | | | | | | |

---

## Debate Topics

When agents disagree on approach, implementation, or design. The debate
file is the resolution mechanism.

**State machine**: `open` → `contested` (counter-argument posted) → `resolved` (decision reached) → `learned` (insight extracted)

### Open Debates

| ID | Date | Topic | Proposer | Position A | Position B | State |
|----|------|-------|----------|------------|------------|-------|
| _(no open debates)_ | | | | | | |

### Resolved Debates

<!-- Format: debate details + resolution + who resolved + what was learned -->

---

## Learnings Log

Durable insights discovered by agents about the codebase, tooling, patterns,
or process. These accumulate across sessions. The head agent periodically
promotes verified learnings to `docs/DECISIONS.md`.

| ID | Date | Discovered By | Topic | Insight | Promoted? |
|----|------|--------------|-------|---------|-----------|
| L-001 | 2026-04-30 | opencode | copy-first workspace | Migrated workspace at `kitty-system/kitty-app` has no `.git`; sync is file-copy only. Legacy repo at `/Users/jacobbrizinski/Projects/kitty` is canonical git history. | no |
| L-002 | 2026-04-30 | opencode | pre-commit hook | The pre-commit hook in legacy repo runs full `pytest tests/` before allowing commit. All commits must pass 350+ tests. | no |
| L-003 | 2026-04-30 | opencode | merge gate | Phase 4 merge gate script (`scripts/run_phase4_merge_gate.sh`) requires a running server on specified port for route smoke. Server must be started first. | no |

---

## Agent-specific Notes

### For Codex
- Read `CURRENT_FOCUS.md` first — it defines what you CAN and CANNOT touch.
- Always sync changes to the migrated workspace at `kitty-system/kitty-app` after committing to legacy repo.
- Your commits in legacy repo have pre-commit hook running full test suite; expect a ~15s delay.
- Never touch `Icon\r` files, eval artifacts, or raw chat logs.

### For Cursor
- The frontend lives in `garage-ui/`. Backend is Flask in `src/api/`.
- Mobile testing: server binds IP, check `./kitty status` for phone URL.
- Design tokens are in `garage-ui/app/globals.css` (warm dark palette).
- Build before claiming done: `cd garage-ui && npm run build`.

---

## Handoff Protocol

Every agent session ends with a handoff entry in this section.
Use the template in `docs/AGENT_HANDOFF_TEMPLATE.md`.

### Recent Handoffs

<!-- ADD HANDOFFS ABOVE THIS LINE -->

### 2026-04-30 opencode session

**Done**:
- Wrote `specs/agent-coordination.spec.md`
- Created `docs/AGENT_COORDINATION.md` (this file)
- Created `docs/AGENT_HANDOFF_TEMPLATE.md`
- Updated `docs/FILE_GOVERNANCE.md` to register new control files

**Files changed**: `docs/FILE_GOVERNANCE.md` (modified), `docs/AGENT_COORDINATION.md` (new),
`docs/AGENT_HANDOFF_TEMPLATE.md` (new), `specs/agent-coordination.spec.md` (new)

**Tests**: Full suite `354 passed, 2 warnings` (from prior commit `8f219b5`)

**Outstanding**:
- Sync these new docs to `kitty-system/kitty-app` migrated workspace
- Commit legacy repo changes

**Feedback for other agents**: None yet — this is the first coordination entry.

**Next suggested action**: Start using this board. Claim a lane, work, leave a handoff.

---

## Archive

Older coordination entries are archived to `docs/archive/agent-coordination/`
when they exceed 14 days. The head agent handles pruning.
