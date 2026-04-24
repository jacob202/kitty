# Phase 2: Capability Platform
**Date:** 2026-04-23  
**Goal:** Finish the capability platform by turning the existing Phase 1 inventory into a reusable routing surface with telemetry and an explain endpoint.  
**Depends on:** Phase 1 prune work already landed (`src/core/capabilities.py`, `/api/capabilities`, hidden internal APIs, smaller help/palette surface).  
**Primary test command:** `/opt/homebrew/bin/python3.12 -m pytest tests/test_capability_platform.py -q`

---

## Current State

Phase 1 already completed these pieces:

- `src/core/capabilities.py` exists and is the canonical inventory for:
  - command metadata
  - MCP policy
  - API visibility/tiering
- `/help` already uses `visible_help_commands()`
- command palette suggestions already use `command_palette_suggestions()`
- `/api/capabilities` already exists in `src/api/system_routes.py`
- experimental swarm and internal-only APIs are already hidden behind env flags in `web.py`

That means **Phase 2 must not re-implement or relocate those features** unless there is a concrete defect.

In particular:

- Do **not** create a new `capability_routes.py` unless `system_routes.py` becomes untenable
- Do **not** add `/api/capabilities` again
- Do **not** rewrite `/help` back into a separate hardcoded surface

---

## What Phase 2 Still Needs

`docs/TASKS.md` says Phase 2 still needs:

1. canonical capability metadata schema
2. clear tiers (`core`, `beta`, `internal`, `disabled`)
3. registry-driven routing/discovery
4. routing telemetry
5. dry-run / explain mode

Phase 1 partially covered items 1-3 for commands and API visibility. Phase 2 should finish them by making the registry more queryable, testable, and useful to the routing layer.

---

## Task 1: Complete the Capability Schema

**Files**
- Modify: `src/core/capabilities.py`
- Create or extend: `tests/test_capability_platform.py`

### Required changes

Extend the command capability model so the registry can be used by more than help text.

Add these fields to `CommandCapability`:

- `status: str = "keep"`
- `routing_tags: tuple[str, ...] = ()`

Rules:

- `tier` remains one of `core`, `beta`, `internal`, `disabled`
- `status` should be one of `keep`, `hide`, `remove`, `investigate`
- existing commands should be updated explicitly rather than relying on ambiguous defaults everywhere
- hidden-but-available commands should usually be `status="hide"`
- commands that should no longer be surfaced but still exist for compatibility should not be marked `remove` unless the implementation is actually gone

Add helpers:

- `all_command_capabilities() -> list[CommandCapability]`
- `find_command_capability(command_name: str) -> CommandCapability | None`
- `command_capability_snapshot() -> list[dict[str, object]]`

Behavior:

- `find_command_capability()` must support exact slash-command lookup using the leading token only
- `command_capability_snapshot()` should serialize all command metadata needed by UI/tests without exposing Python objects

### Tests to add first

- schema fields are present on returned command snapshots
- hidden commands still exist in the registry even when excluded from help
- `find_command_capability("/brief")` returns the matching capability
- `find_command_capability("/brief extra words")` still resolves correctly
- unknown commands return `None`

---

## Task 2: Add Routing Telemetry

**Files**
- Modify: `src/core/capabilities.py`
- Modify: `src/api/socket_handlers.py`
- Modify: `src/api/system_routes.py`
- Extend: `tests/test_capability_platform.py`

### Required changes

Add in-memory routing telemetry to the capability layer.

Implement:

- `record_invocation(command: str, *, outcome: str) -> None`
- `invocation_stats(command: str | None = None) -> dict`
- `reset_invocation_stats() -> None`

Allowed outcomes:

- `suggested`
- `selected`
- `auto-invoked`
- `succeeded`
- `failed`
- `canceled`
- `abandoned`

Behavior:

- invalid outcomes must raise `ValueError`
- counters must be thread-safe
- `reset_invocation_stats()` exists only to keep tests deterministic

### Wiring requirements

- `command_palette_search` should record `suggested` for the commands it returns
- the new explain endpoint from Task 3 should record `suggested` for the top result it returns
- do **not** invent fake success/failure events where no actual invocation happened yet

### Tests to add first

- recording a valid outcome increments stats
- invalid outcomes raise
- reset clears state
- command palette search causes `suggested` counts to increase for returned commands

---

## Task 3: Add Dry-Run / Explain Mode

**Files**
- Modify: `src/api/system_routes.py`
- Extend: `tests/test_capability_platform.py`

### Route

Add:

- `POST /api/capabilities/explain`

Use `system_bp`. Do **not** create a new blueprint for this.

### Request body

```json
{
  "message": "I'm stuck on a bug"
}
```

### Response shape

```json
{
  "ok": true,
  "message": "I'm stuck on a bug",
  "suggested_command": "/stuck [task]",
  "description": "ADHD rescue: one next physical step",
  "tier": "core",
  "status": "keep",
  "reason": "Matched keywords in the message to capability routing tags",
  "all_suggestions": [
    {
      "command": "/stuck [task]",
      "description": "ADHD rescue: one next physical step"
    }
  ]
}
```

Fallback response when nothing matches:

```json
{
  "ok": true,
  "message": "…",
  "suggested_command": null,
  "description": null,
  "tier": null,
  "status": null,
  "reason": "No matching capability found",
  "all_suggestions": []
}
```

### Matching rules

- use `command_palette_suggestions(message, limit=3)`
- use `find_command_capability()` to enrich the top result with tier/status
- keep the reasoning string compact and deterministic
- this endpoint is public like `/api/capabilities`; do not gate it behind `KITTY_ENABLE_INTERNAL_API`

### Tests to add first

- successful explain request returns `200` with `suggested_command`, `reason`, `tier`, and `status`
- unmatched request returns `200` with `suggested_command: null`
- explain route increments `suggested` telemetry for the chosen command

---

## Task 4: Tighten Capability Snapshot

**Files**
- Modify: `src/core/capabilities.py`
- Modify: `src/api/system_routes.py`
- Extend: `tests/test_capability_platform.py`

### Required changes

`capability_snapshot()` should expose enough information for future UI work without requiring direct Python introspection.

Add these command-level fields under `commands`:

- `visible`
- `all`

Where:

- `visible` remains the current help-visible list
- `all` contains the serialized full command inventory including `tier`, `status`, `visible_in_help`, and `visible_in_palette`

Do not remove the existing summary counts.

### Tests to add first

- `/api/capabilities` returns both `commands.visible` and `commands.all`
- `commands.all` includes hidden/internal commands
- `commands.visible` excludes hidden help commands

---

## Implementation Notes

- Keep the capability logic centralized in `src/core/capabilities.py`
- Prefer small pure helpers over embedding ranking/lookup logic inside route files
- Do not couple capability telemetry to persistent storage in this phase
- Do not add frontend UI changes in this phase beyond what is necessary for tests
- Do not expand the MCP surface in this phase
- Do not revisit swarm enablement in this phase

---

## Acceptance Criteria

- [ ] `CommandCapability` supports explicit `status` and `routing_tags`
- [ ] `find_command_capability()` resolves commands reliably
- [ ] `record_invocation`, `invocation_stats`, and `reset_invocation_stats` exist and are tested
- [ ] `POST /api/capabilities/explain` returns a deterministic routing suggestion
- [ ] `/api/capabilities` includes both summary counts and full serialized command inventory
- [ ] `/help` and command palette continue to be registry-driven
- [ ] All tests pass:
  - `/opt/homebrew/bin/python3.12 -m pytest tests/test_capability_platform.py -q`
  - `/opt/homebrew/bin/python3.12 -m pytest tests/test_capability_pruning.py tests/test_web_chat_phase1.py tests/test_voice_routes.py tests/test_voice_ui_template.py tests/test_voice_transcriber.py -q`

---

## Suggested Commit

```bash
git add src/core/capabilities.py src/api/system_routes.py src/api/socket_handlers.py tests/test_capability_platform.py docs/plans/2026-04-23-phase2-capability-platform.md
git commit -m "feat: complete capability platform telemetry and explain mode"
```
