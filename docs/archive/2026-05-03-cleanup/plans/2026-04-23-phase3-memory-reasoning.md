# Phase 3: Memory + Reasoning Productization
**Date:** 2026-04-23  
**Goal:** Productize the memory and reasoning systems that already exist in Kitty so they become inspectable, controllable, and safer to use.  
**Depends on:** Phase 2 capability platform (registry, telemetry, explain mode)  
**Primary test command:** `/opt/homebrew/bin/python3.12 -m pytest tests/test_memory_product.py tests/test_reasoning_surface.py -q`

---

## Current State

The repo already has substantial memory and reasoning infrastructure:

- `src/core/context_manager.py` builds unified context from:
  - Honcho
  - `CorrectionMemory`
  - journal/pattern systems
- `src/memory/correction_memory.py` already supports:
  - correction retrieval
  - correction stats
  - recent snapshots
  - snapshot capture
- `src/space_kitty/reasoning_layer.py` already supports:
  - multi-step reasoning traces
  - persisted trace files in `data/reasoning_traces`
  - real-time thinking emission hooks
- `src/api/reasoning_routes.py` already exists, but currently assumes `current_app.supervisor.orchestrator.reasoning`, which is not aligned with the current web app shape
- `src/api/memory_routes.py` already exposes journal/library/feedback endpoints, but not a user-facing “what Kitty remembers” product surface

That means **Phase 3 must not create a second parallel memory engine or a second parallel reasoning trace system**.

In particular:

- Do **not** create a new `reasoning_trace.py` abstraction that duplicates `ReasoningLayer`
- Do **not** build the user-facing memory surface as a thin wrapper around a hypothetical MCP-memory client first
- Do **not** anchor new context assembly work in `supervisor.py`; the live path is `ContextManager`

Build on the existing in-repo systems first. MCP memory can remain a secondary signal, not the primary product abstraction.

---

## What Phase 3 Still Needs

`docs/TASKS.md` says Phase 3 still needs:

1. user-visible memory controls
2. session vs project vs durable memory scope
3. readable reasoning explanation surface
4. typed, budgeted context assembly
5. correction lifecycle management

Phase 3 should deliver those directly on top of:

- `ContextManager`
- `CorrectionMemory`
- `ReasoningLayer`
- existing Flask blueprints

---

## Task 1: User-Facing Memory Surface

**Files**
- Create: `src/api/memory_product_routes.py`
- Modify: `src/api/__init__.py`
- Modify: `web.py`
- Create or extend: `tests/test_memory_product.py`

### Required routes

Add a dedicated product-facing memory blueprint with these public routes:

- `GET /api/memory`
- `POST /api/memory/forget`
- `POST /api/memory/pin`

Use a separate blueprint instead of overloading `memory_routes.py`, because the existing memory routes are mostly journal/library plumbing rather than user-facing controls.

### Route behavior

`GET /api/memory`

- returns a normalized view of what Kitty currently remembers
- must include:
  - `corrections`
  - `snapshots`
  - `summary`
- response shape:

```json
{
  "ok": true,
  "corrections": [
    {
      "id": 12,
      "text": "Use python3.12 for this repo",
      "category": "general",
      "scope": "durable",
      "why": "Saved correction from prior interaction"
    }
  ],
  "snapshots": [
    {
      "timestamp": "...",
      "scope": "session",
      "why": "Recent context snapshot",
      "topics": ["voice input"]
    }
  ],
  "summary": {
    "correction_count": 3,
    "snapshot_count": 2
  }
}
```

Defaults:

- corrections are treated as `durable`
- recent snapshots are treated as `session`
- if later project-scoped storage exists, the schema must already allow `project`

`POST /api/memory/forget`

- request body: `{"kind": "correction" | "snapshot", "id": ...}`
- correction deletion must be implemented for real against the corrections DB
- snapshot deletion may return a structured `501` if the underlying storage cannot delete individual snapshots safely yet
- missing ids must not produce `500`

`POST /api/memory/pin`

- request body: `{"kind": "correction" | "snapshot", "id": ..., "scope": "project" | "durable"}`
- this phase only needs real scope-promotion for corrections if the underlying storage supports it cleanly
- if snapshots cannot be promoted safely yet, return a structured `501`, not fake success

### Important constraints

- Do not pretend that MCP memory is the same thing as Kitty’s user-visible memory model
- The product surface should be assembled from `CorrectionMemory` and snapshot retrieval first
- It is acceptable for some operations to return “not yet supported” as long as they are explicit and non-breaking

### Tests to add first

- `GET /api/memory` returns `200` with `corrections`, `snapshots`, and `summary`
- each returned item has `scope` and `why`
- forgetting a missing correction does not 500
- pinning with an invalid scope returns `400`
- unsupported snapshot mutation returns structured non-500 response

---

## Task 2: Typed, Budgeted Context Assembly

**Files**
- Create: `src/core/context_budget.py`
- Modify: `src/core/context_manager.py`
- Extend: `tests/test_reasoning_surface.py`

### Required changes

Introduce a small typed budget layer and wire it into `ContextManager.build_unified_context()`.

Create:

- `ContextSlot` enum
- `ContextBudget` class

Slots for this phase:

- `IDENTITY`
- `CORRECTIONS`
- `PROJECT`
- `RECENT`
- `EPHEMERAL`

Rules:

- lower-numbered slots are higher priority
- total budget is enforced by character count in this phase
- lower-priority slots are truncated or dropped first
- empty slots should not generate empty section noise

### Wiring

Do not wire this into `supervisor.py`.

Instead:

- update `ContextManager.build_unified_context()` to build slot content first
- feed that content through `ContextBudget`
- return the assembled, budgeted context string

This keeps the existing orchestration path intact while replacing additive prompt stuffing with a typed budget.

### Tests to add first

- total char limit is enforced
- higher-priority slots survive tight budgets
- empty slots do not create noisy separators
- `ContextManager.build_unified_context()` still returns a string and now respects budget logic

---

## Task 3: Reasoning Explanation Surface

**Files**
- Modify: `src/api/reasoning_routes.py`
- Modify: `src/space_kitty/reasoning_layer.py` only if a small helper is missing
- Extend: `tests/test_reasoning_surface.py`

### Required changes

Do not create a new trace collector.

Use `ReasoningLayer` as the source of truth.

Add a lightweight explanation route:

- `GET /api/reasoning/last`

Behavior:

- return the most recent reasoning trace in a translated, UI-safe shape
- if no trace exists, return `200` with `{"trace": null, "note": "..."}`
- do not expose raw internal-only metadata fields unless they are already safe and comprehensible

Expected response shape:

```json
{
  "trace": {
    "id": "abcd1234",
    "query": "How do I fix this?",
    "steps": [
      {
        "type": "observe",
        "content": "Domain: hardware",
        "confidence": 0.9
      }
    ],
    "conclusion": "..."
  }
}
```

### Routing fix

`src/api/reasoning_routes.py` currently assumes `current_app.supervisor.orchestrator.reasoning`.

That is not the web app’s live shape.

Update the routes to use the real app wiring:

- prefer `current_app.orchestrator`
- only fall back to supervisor-attached orchestrator if present

If `ReasoningLayer` is missing helper methods like “get latest trace,” add small helpers to `ReasoningLayer` rather than inventing a new abstraction.

### Tests to add first

- recording a reasoning trace makes `GET /api/reasoning/last` return `200`
- empty state returns `200` with `trace: null`
- the route works with the current `create_app()` wiring, not only with a fake supervisor

---

## Task 4: Correction Lifecycle Controls

**Files**
- Modify: `src/memory/correction_memory.py`
- Modify: `src/api/memory_product_routes.py`
- Extend: `tests/test_memory_product.py`

### Required changes

Add only the minimum lifecycle features needed for the product surface:

- list corrections with category and last-applied metadata
- delete correction by id
- optionally update correction scope if cleanly representable

Do not attempt a full long-term schema redesign in this phase.

If scope is added to corrections storage:

- prefer a backward-compatible migration
- default old rows to `durable`

If scope is too invasive for this pass:

- keep scope as derived presentation for now
- document the limitation inline in the route behavior

### Tests to add first

- correction list includes metadata users can understand
- delete by id works for existing rows
- delete for missing row is non-fatal
- scope field is stable in serialized responses even if storage is still derived

---

## Implementation Notes

- Keep the product surface honest; explicit “not yet supported” is better than fake mutability
- Use existing blueprints and app wiring patterns
- Avoid direct dependence on external MCP server APIs for primary product behavior
- Keep reasoning explanation compact and translated, not a raw debug dump
- Do not add frontend UI in this phase beyond what tests need; the goal is backend/product surface readiness

---

## Acceptance Criteria

- [ ] `GET /api/memory` returns normalized memory data with `scope` and `why`
- [ ] `POST /api/memory/forget` and `POST /api/memory/pin` never fail with a generic `500` for normal missing/unsupported cases
- [ ] `ContextBudget` exists and is wired into `ContextManager.build_unified_context()`
- [ ] `GET /api/reasoning/last` returns a readable latest trace or a null-trace empty state
- [ ] reasoning routes use the current app/orchestrator wiring correctly
- [ ] no duplicate memory engine or duplicate reasoning trace system is introduced
- [ ] All tests pass:
  - `/opt/homebrew/bin/python3.12 -m pytest tests/test_memory_product.py tests/test_reasoning_surface.py -q`
  - `/opt/homebrew/bin/python3.12 -m pytest tests/test_capability_pruning.py tests/test_web_chat_phase1.py tests/test_voice_routes.py tests/test_voice_ui_template.py tests/test_voice_transcriber.py -q`

---

## Suggested Commit

```bash
git add src/core/context_budget.py src/api/memory_product_routes.py src/api/reasoning_routes.py src/core/context_manager.py src/memory/correction_memory.py tests/test_memory_product.py tests/test_reasoning_surface.py docs/plans/2026-04-23-phase3-memory-reasoning.md
git commit -m "feat: productize memory and reasoning surfaces"
```
