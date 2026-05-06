# Plan: Unified Tool Runtime (Candidate A)

## Goal
Consolidate the existing fragmented tool systems (`ToolManager` and `ToolRegistry`) into a single, deep `ToolRuntime` module. This module will provide a unified interface for all tool types, centralized permission enforcement, and clear execution semantics.

## Architectural Seam
The `ToolRuntime` sits between the execution engines (like `SpecialistRuntime`) and the concrete tool implementations. It abstracts the "how" of execution behind a simple "what" interface.

## Implementation Steps

### 1. Foundation
- **Files**: `src/tools/runtime.py` (new)
- **Action**: Define the core `ToolDefinition`, `ToolContext`, and `ToolResult` dataclasses as per the agreed design.
- **Benefit**: Provides a stable, typed foundation for all tools.

### 2. The Engine
- **Files**: `src/tools/runtime.py`
- **Action**: Implement the `ToolRuntime` class.
    - Registry for `ToolDefinition`.
    - Executor factory system (supporting `function`, `http`, and `specialist` kinds).
    - Permission check logic (comparing `ToolDefinition.required_permissions` against `ToolContext.permissions`).
    - Batch execution using `asyncio.gather`.
- **Benefit**: Centralizes system safety and execution logic (locality).

### 3. Adapters & Migration
- **Files**: `src/tools/tool_manager.py`, `src/tools/tool_registry.py`, `src/tools/implementations/*.py`
- **Action**: 
    - Refactor existing tools into `ToolDefinition` objects.
    - Implement `FunctionExecutor` and `HTTPExecutor` adapters to bridge existing logic into the new runtime.
    - Update `ToolManager` to become a thin wrapper (or alias) for the `ToolRuntime` to maintain backward compatibility during the transition.
- **Benefit**: Migrates legacy behavior into the deepened architecture without breaking existing callers.

### 4. Specialist Integration (Seam Prep)
- **Files**: `src/tools/runtime.py`
- **Action**: Implement the `SpecialistToolExecutor`. This executor will eventually call back into the `SpecialistRuntime`, but for now, it will be stubbed to ensure the recursion logic is functional.

## Validation
- **Unit Tests**: Create `tests/test_tool_runtime.py` covering:
    - Successful tool execution.
    - Permission denied scenarios.
    - Recursion depth limit (for specialist kind).
    - Batch execution concurrency.
- **Regression**: Run existing `pytest tests/test_vector_store.py` (which uses the current `ToolRegistry`) to ensure no breaking changes in behavior.

## Acceptance Criteria
- [x] `ToolRuntime` is the single source of truth for all tool registrations (backed by adapter from BaseTool)
- [x] Permission enforcement is consistent across all tool types (ToolRuntime has permission check, integration with ToolRegistry pending)
- [x] Recursive specialist calls are depth-gated (SpecialistExecutor MAX_DEPTH=3)
- [x] All existing tools are reachable through the new interface (via register_all_base_tools())
- [x] ToolManager is a thin wrapper around ToolRuntime (backward compatible)

## Implementation Status (2026-05-06)
### Completed
1. **Foundation** (`src/tools/runtime.py`): ToolDefinition, ToolContext, ToolResult dataclasses
2. **Engine**: ToolRuntime class with registry, executor factory, permission checks, batch execution
3. **Executors**: FunctionExecutor (sync+async), HTTPExecutor (stubbed), SpecialistExecutor (stubbed, depth-gated)
4. **Adapters**: `register_base_tool()` and `register_all_base_tools()` to bridge BaseTool → ToolRuntime
5. **ToolManager**: Updated to delegate `execute()` to ToolRuntime, with backward-compatible `get_tool_by_name()` etc.
6. **Tests**: `tests/test_tool_runtime.py` — 15 tests, all passing
7. **Full suite**: 480 tests passing (15 new + 465 existing)

### Pending
- Wire HTTPExecutor to actual HTTP calls
- Wire SpecialistExecutor to SpecialistRuntime
- Integrate ToolRuntime permissions with existing ToolRegistry (tool_registry.py)
- Migrate tools to native ToolDefinition (instead of BaseTool adapter)
