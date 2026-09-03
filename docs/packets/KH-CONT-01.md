# KH-CONT-01 — GAR retrieves assignment-scoped continuity deterministically

**Initiative:** `kitty-hardening-gar-scoped-continuity-20260903-v1`
**Owner:** Builder after explicit operator activation
**Base authored against:** `70c15583a6afa4aac9a6f6eb11abf840afa377a4`
**Status:** authored only — not applied/queued/dispatched
**Source plan:** `docs/superpowers/plans/2026-09-01-global-agent-room-continuity-archival.md`

## What Jacob can do after this
Jacob can resume a specific Kitty assignment from `workspace_global` even after hundreds of unrelated room messages, without reading stale `.claude` checkpoints.

## Verified finding
GAR-first startup and `--skip-legacy-continuity` already exist on current main, and session-end already posts the final room handoff after continuity validation. The remaining archival plan still lacks assignment-scoped retrieval: `scope_key` is absent from current Agent Room message/domain/CLI/MCP code, so old but relevant handoffs can fall outside the global recent window.

## Objective
Implement only the still-missing scoped-retrieval prerequisite from `docs/superpowers/plans/2026-09-01-global-agent-room-continuity-archival.md`; do not redo already-landed GAR-first receipt or final-handoff ordering. Add nullable `scope_key` to Agent Room messages with an index on workspace/scope/time. Extend the existing room post/reply/recent/inbox interfaces and existing seven MCP tools with optional scope only—no eighth tool. Replies inherit the parent scope when omitted. Define evidence-derived keys (`github:pr:<n>`, `github:issue:490:<lane>`, `git:branch:<branch>`) and keep unscoped announcements null. Retrieval by scope must find relevant handoffs regardless of unrelated room volume. Do not encode owner, lease, task state, priority, or scheduler semantics into scope; GAR remains communication only. Preserve existing messages with NULL scope and current APIs when scope is omitted.

## Intended files / fence
- `gateway/`
- `mcp/agent_room/`
- `tests/`

Directory entries are deliberate because this packet may create the specifically named helper/migration/test described in the objective. The worker must still stay inside the narrow objective; a directory fence is not permission for opportunistic refactoring.

## Acceptance criteria
1. A scoped handoff remains retrievable after at least 150 unrelated global messages.
2. Existing unscoped room behavior and message rows remain backward compatible.
3. Post/reply/recent/inbox accept optional scope; a reply inherits its parent scope unless explicitly rejected by validation.
4. The MCP surface remains exactly the existing seven tools; only optional fields change.
5. Scope keys contain no task/lease/scheduler authority and do not become a second ownership system.
6. Indexes make scoped retrieval bounded without scanning the full room history.

## Verification
**Tier 1 — Builder mechanical.**
- `python -m pytest -q tests/test_agent_room_global.py tests/test_agent_room_cli.py tests/test_mcp_agent_room_server.py`
- `python -m ruff check gateway/agent_workspace.py gateway/routes/agent_workspace.py gateway/agent_room_cli.py mcp/agent_room/server.py tests/test_agent_room_global.py tests/test_agent_room_cli.py tests/test_mcp_agent_room_server.py`

**Tier 2.** CLI + MCP transport proof using the same canonical DB, including a handoff older than the normal recent window.
**Tier 3.** No product UI acceptance; an independent continuity reviewer must cold-start from a scoped handoff without reading `.claude/STATE.md` or `.claude/HANDOFF.md`.

## Stop condition
If scoped retrieval would require task ownership, leases, status transitions, or another execution queue in GAR, stop. Those remain #490/Builder authorities.

## Recovery / restartability
Additive nullable migration only. Existing unscoped messages remain readable. A failed migration must leave the prior schema usable and must not rewrite message content.

## Dedupe / ownership guard
Do not redo the already-landed `--skip-legacy-continuity` receipt path or final session-end GAR-post ordering. Before activation, re-read `workspace_global`, #490, and migration head.
