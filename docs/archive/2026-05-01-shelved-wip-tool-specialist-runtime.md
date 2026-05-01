# Shelved WIP — Unified Tool Runtime + Specialist Adapter (2026-05-01)

**Grep tag:** `SHELVED-WIP-2026-05-01`  
**Status:** Removed from working tree to restore **green `pytest tests/`** (~399 passed). **Not lost conceptually** — this file is the recovery map.  
**Related plan (still in repo):** `docs/plans/2026-04-30-unified-tool-runtime.md` (Candidate A / `arch-001`).

---

## 1. What happened (plain language)

A partial refactor tried to:

1. Introduce a **`ToolRuntime`** (`src/tools/runtime.py`) with `ToolDefinition`, `ToolContext`, `ToolResult`, permission checks, async execution (`pytest` used `@pytest.mark.anyio`).
2. Wire **`get_tool_manager().runtime`** into a new **registry** shape: instead of twelve concrete `BaseSpecialist` subclasses in `SPECIALISTS`, the dict held **`SpecialistRuntimeAdapter`** instances built from **`get_specialist_definitions()`** (`src/core/specialists/definitions.py`).
3. Add **adapters** under `src/core/adapters/` (e.g. inference/memory) and **`safe_file_tools`**, plus **`specialist_runtime.py`** / **`specialist_adapter.py`**.

That work was **never committed** (only local + untracked files). It broke the suite in two ways:

- **`tests/test_specialists_coverage.py`** patches `src.core.specialist_framework.query_knowledge_base` and `src.space_kitty.llm_client.call_llm` and calls **`specialist.query(...)`** on each registry value. The adapter path did not satisfy those assumptions → **all twelve parametrized tests failed**.
- **`tests/test_tool_runtime.py`** and **`tests/test_specialist_runtime.py`** used **asyncio via anyio**. In a **full** `pytest tests/` run, many suites share process state; several tests hit **`RuntimeError: Runner is closed`** (event loop / runner lifecycle), so those files were not safe to keep on disk until the async harness is fixed (fixture scope, `anyio_backend`, or sync-only tests).

**Resolution (2026-05-01):** All **tracked** edits were **`git checkout --`** to the last good commit. All **untracked** files listed below were **deleted**. The **Candidate A markdown plan** was **committed** as `docs/plans/2026-04-30-unified-tool-runtime.md` so the design intent stays in git.

---

## 2. File manifest (removed — was untracked unless noted)

| Path | Role (short) |
|------|----------------|
| `src/tools/runtime.py` | `ToolRuntime`, `ToolDefinition`, executors, batch async |
| `src/core/specialist_runtime.py` | Specialist-side runtime (orchestration) |
| `src/core/specialist_adapter.py` | `SpecialistRuntimeAdapter` — legacy `query()` façade over definitions + tool runtime |
| `src/core/specialists/definitions.py` | `get_specialist_definitions()` — data-driven specialist definitions |
| `src/core/specialists/registry.py` | **Modified** (reverted): was changed to build `SPECIALISTS` from adapters + `_tool_runtime` |
| `src/tools/tool_manager.py` | **Modified** (reverted): had grown to expose `.runtime` |
| `src/api/swarm_routes.py` | **Modified** (reverted): unrelated WIP in same session |
| `src/tools/implementations/safe_file_tools.py` | Safe file ops for tools |
| `src/core/adapters/inference.py` | Inference adapter |
| `src/core/adapters/memory.py` | Memory adapter |
| `tests/test_tool_runtime.py` | Unit tests for `ToolRuntime` (`@pytest.mark.anyio`) |
| `tests/test_specialist_runtime.py` | Specialist runtime flow tests (`@pytest.mark.anyio`) |
| `.wip_tests_backup/` | Empty leftover folder from an earlier merge-gate experiment |

**Also reverted (tracked, no longer dirty):**  
`KITTY_CONTEXT.md`, `docs/AGENT_COORDINATION.md` (minor edits in same WIP window).

---

## 3. Registry WIP shape (reconstructed from diff — for reimplementation)

The shelved `registry.py` looked conceptually like this (pseudocode — **do not paste as-is**):

```python
# Pseudocode only — files were deleted; verify against BaseSpecialist before reuse.
from src.core.specialists.definitions import get_specialist_definitions
from src.core.specialist_adapter import SpecialistRuntimeAdapter
from src.tools.tool_manager import get_tool_manager

DEFINITIONS = {d.name: d for d in get_specialist_definitions()}
_tool_runtime = get_tool_manager().runtime

SPECIALISTS = {
    name: SpecialistRuntimeAdapter(defn, _tool_runtime)
    for name, defn in DEFINITIONS.items()
}
```

**Why tests broke:** `SpecialistRuntimeAdapter.query()` must either subclass **`BaseSpecialist`** and call the same internal hooks the coverage tests patch, or **coverage tests** must be rewritten to mock at the adapter boundary. Until one of those is true, do not replace the concrete `SPECIALISTS` dict.

---

## 4. Tool runtime tests (reconstructed notes)

`tests/test_tool_runtime.py` (deleted) roughly contained:

- `@pytest.mark.anyio` async tests: tool not found, permission denied, sync/async function executors, recursion limit for `kind="specialist"`, batch execution.
- **Failure mode:** `RuntimeError: Runner is closed` when entire `tests/` ran — typical fix is dedicated **`@pytest.fixture` scope**, forcing **`anyio_backend = "asyncio"`** consistently, or **`pytest.mark.asyncio`** with **`asyncio_mode = auto`** in `pytest.ini`, or **sync tests** for the runtime first.

**Recommendation:** Reintroduce **one** `tests/test_tool_runtime_sync.py` with **no async** until the runtime API is stable, then add async with isolated event loop fixtures.

---

## 5. What to do next (no permission needed — process only)

1. **Treat recovery as spec-first:** Open or extend **`specs/`** for “Tool Runtime phase 1” and “Specialist adapter” **before** touching `registry.py` again (`docs/DECISIONS.md` D-0003 / D-0007).
2. **Keep `SPECIALISTS` as concrete classes** until `tests/test_specialists_coverage.py` has an explicit adapter branch or adapters inherit `BaseSpecialist` properly.
3. **Follow the committed plan:** `docs/plans/2026-04-30-unified-tool-runtime.md` — implementation steps and acceptance criteria are already written.
4. **Broader architecture index:** `docs/plans/gemini-architecture-priorities-2026-04-30.md` (`GEMINI-ARCH-PRIORITIES`) — sequencing Candidate A → B.
5. **After any future merge:** run **`venv/bin/python -m pytest tests/ -q`** (pre-commit does this). Sync migrated tree when you touch runtime files (`scripts/copy_workspace_separation.py --execute`).

---

## 6. Binary / provenance note

The deleted files existed **only on disk** in this workspace; **git never recorded their blobs**. This markdown is the **authoritative inventory** of what was removed and why. If another machine had copies, they could be merged manually — otherwise **rebuild from this doc + the Candidate A plan**.

---

*Written: 2026-05-01 (cursor). Tag: **SHELVED-WIP-2026-05-01**.*
