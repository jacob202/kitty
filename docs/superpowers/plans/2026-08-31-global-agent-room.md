# Global Agent Room Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship GAR-CORE-01: one durable global agent room usable from Gateway, `kitty room`, and identity-pinned MCP clients.

**Architecture:** Extend the existing Gateway-owned `agent_workspace` store rather than introducing another collaboration database. Add one receipt table for per-participant delivery state; keep Builder and issue #490 as the existing execution/ownership authorities.

**Tech Stack:** Python 3.12+, SQLite, FastAPI/Pydantic, argparse, FastMCP v1, pytest.

**Spec:** `docs/superpowers/specs/2026-08-31-global-agent-room-design.md`

## Global Constraints

- Canonical room id is exactly `workspace_global`.
- Canonical MCP agent identities are exactly `chatgpt`, `claude`, `codex`, and `kitty`; Jacob remains a user sender.
- Existing ad-hoc workspaces and scripted four-agent turns remain compatible.
- No second queue, scheduler, lease system, task board, event bus, or execution state machine.
- Reads never silently mark messages seen; receipt state is explicit and monotonic.
- Keep existing message kinds and the 12,000-character message limit.
- No frontend files are part of GAR-CORE-01.
- No paid model invocation or public network exposure is authorized by this work.

---### Task 1: Global Room Domain + Receipts

**Files:**
- Create: `gateway/migrations/052_agent_workspace_receipts.sql`
- Modify: `gateway/agent_workspace.py`
- Create/Test: `tests/test_agent_room_global.py`

**Interfaces:**
- Produces: `ensure_global_workspace()`, `list_inbox(participant_id, unread_only=False, limit=100)`, `list_thread(message_id, limit=100)`, `record_receipt(message_id, participant_id, state)`, and bounded global-participant helpers.
- Reuses: `append_message()` as the only message insertion path.

- [ ] **Step 1: Write failing tests** for stable/idempotent room creation, canonical roster, direct+broadcast inbox filtering, join-time cutoff, self-message exclusion, explicit unread behavior, monotonic receipts across a fresh DB connection, thread traversal, unknown participant/message rejection, and cross-room parent rejection.
- [ ] **Step 2: Verify RED** with `PYTHONPATH=. /Users/jacobbrizinnski/Projects/kitty/venv/bin/python -m pytest tests/test_agent_room_global.py -q`; failures must be missing global-room APIs/schema rather than syntax errors.
- [ ] **Step 3: Add migration** creating `agent_workspace_message_receipts(message_id TEXT REFERENCES agent_workspace_messages(id), participant_id TEXT NOT NULL, seen_at REAL, acknowledged_at REAL, PRIMARY KEY(message_id, participant_id))` plus an inbox-oriented index.
- [ ] **Step 4: Implement minimal domain code**: fixed room + roster ensure under one transaction, participant validation/join-time lookup, inbox query with receipt projection, root/descendant thread resolution, and monotonic explicit receipt writes.
- [ ] **Step 5: Verify GREEN** by rerunning `tests/test_agent_room_global.py` and the pre-existing four agent-workspace test files.
- [ ] **Step 6: Commit** domain/migration/tests as `feat(agent-room): add global room protocol`.

---### Task 2: Gateway Global-Room API

**Files:**
- Modify: `gateway/routes/agent_workspace.py`
- Modify/Test: `tests/test_agent_workspace_routes.py`

**Interfaces:**
- Consumes: Task 1 global-room domain primitives and existing `append_message()`.
- Produces: thin `/agent-room/global` ensure/get/recent/post/inbox/thread/receipt HTTP contracts.

- [ ] **Step 1: Add failing route tests** proving ensure/get share one stable room, direct posts validate sender/recipient, inbox reads do not mutate receipts, thread reads return the root/replies, and receipt mutation exposes the committed monotonic state.
- [ ] **Step 2: Verify RED** with `PYTHONPATH=. /Users/jacobbrizinnski/Projects/kitty/venv/bin/python -m pytest tests/test_agent_workspace_routes.py -q`; new endpoint calls must fail with 404 before implementation.
- [ ] **Step 3: Add Pydantic request models** for direct messages and receipt state with the existing content/message-kind bounds.
- [ ] **Step 4: Add thin routes** that call Task 1/domain operations and translate `AgentWorkspaceError` to truthful 4xx responses without embedding collaboration logic in handlers.
- [ ] **Step 5: Verify GREEN** with the route tests plus all agent-workspace domain tests.
- [ ] **Step 6: Commit** as `feat(agent-room): expose global room api`.

---

### Task 3: Universal `kitty room` CLI

**Files:**
- Create: `gateway/agent_room_cli.py`
- Modify: `kitty`
- Create/Test: `tests/test_agent_room_cli.py`
- Modify/Test: `tests/test_kitty_launcher_runtime.py`

**Interfaces:**
- Consumes: Task 1 domain operations directly; it does not require the Gateway process.
- Produces: `ensure`, `status`, `recent`, `inbox`, `thread`, `post`, `reply`, `ack`, with concise text and JSON output.
- [ ] **Step 1: Add failing CLI tests** using a temporary Kitty DB to prove `post → inbox → reply → ack`, JSON output, sender-kind mapping (`jacob` user; canonical agents agent), and clear nonzero failures for invalid participants/messages.
- [ ] **Step 2: Add failing launcher wiring test** asserting `cmd_room` invokes `python -m gateway.agent_room_cli` and main dispatch includes `room)`.
- [ ] **Step 3: Verify RED** with the two focused test files; failures must be the absent CLI module/launcher command.
- [ ] **Step 4: Implement argparse CLI** with no service dependency, exact global-room domain calls, and durable IDs in mutation output.
- [ ] **Step 5: Wire `kitty room`** using the launcher's existing Python-resolution/PYTHONPATH pattern and add it to help text.
- [ ] **Step 6: Verify GREEN** with CLI/launcher tests, then perform a temporary-DB shell round trip through the actual `kitty room` launcher.
- [ ] **Step 7: Commit** as `feat(agent-room): add global room cli`.

---

### Task 4: Identity-Pinned Agent Room MCP + Global Registration

**Files:**
- Create: `mcp/agent_room/__init__.py`
- Create: `mcp/agent_room/server.py`
- Create/Test: `tests/test_mcp_agent_room_server.py`

**Interfaces:**
- Consumes: Task 1 global-room domain operations; sender identity comes only from `KITTY_AGENT_ROOM_IDENTITY`.
- Produces exactly seven tools: `room_status`, `room_recent`, `room_inbox`, `room_thread`, `room_post`, `room_reply`, `room_ack`.

- [ ] **Step 1: Add failing FastMCP-stub tests** proving exactly seven tools, canonical identity validation, sender pinning, stdio default, streamable-HTTP loopback-only behavior, and same-room message/receipt semantics.
- [ ] **Step 2: Verify RED** because `mcp.agent_room.server` does not exist.
- [ ] **Step 3: Implement minimal FastMCP server** following `mcp/builder/server.py`, with port 8766 default, identity-pinned post/reply/ack calls, and no execution/publication tools.
- [ ] **Step 4: Verify GREEN** with MCP tests plus the complete focused GAR-CORE test set and existing 20 workspace tests.
- [ ] **Step 5: Prove live stdio discovery** by starting the real server with a canonical identity and issuing MCP `tools/list`; record the seven returned tool names.
- [ ] **Step 6: Inspect actual CLI syntax** using `codex mcp --help` / add help / list and `claude mcp --help` / add help / list; do not guess flags.
- [ ] **Step 7: Register user-level clients** for Codex (`codex`) and Claude (`claude`) against this verified branch/worktree, then prove both via their supported `mcp list` output.- [ ] **Step 8: Perform cross-client protocol proof**: post as ChatGPT via `kitty room`, read/reply/ack in a fresh process configured with a second MCP identity, and read the reply through `kitty room`. If no real model invocation occurs, label model-to-model execution unverified rather than implying otherwise.
- [ ] **Step 9: Refresh `origin/main` and collision state**, merge fresh remote main into this branch only if needed, and rerun all focused verification after any integration delta.
- [ ] **Step 10: Commit** MCP/tests as `feat(agent-room): add identity-pinned mcp server` and commit any registration/runbook evidence separately if repository files are needed.

## Final Verification

Run from the isolated worktree with the canonical repo virtualenv:

```bash
PYTHONPATH=. /Users/jacobbrizinnski/Projects/kitty/venv/bin/python -m pytest \
  tests/test_agent_room_global.py \
  tests/test_agent_workspace.py tests/test_agent_workspace_atomic_completion.py \
  tests/test_agent_workspace_context_safety.py tests/test_agent_workspace_routes.py \
  tests/test_agent_room_cli.py tests/test_kitty_launcher_runtime.py \
  tests/test_mcp_agent_room_server.py -q

git diff --check
```

Then run repo-required focused lint/type checks for the touched Python paths, verify the live CLI/MCP round trip, and compare the final diff against the approved design. Do not claim GAR-UI-01, real model participation, Builder execution, or merge status from GAR-CORE-01 evidence.