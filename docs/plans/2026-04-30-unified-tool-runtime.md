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
- [ ] `ToolRuntime` is the single source of truth for all tool registrations.
- [ ] Permission enforcement is consistent across all tool types.
- [ ] Recursive specialist calls are depth-gated.
- [ ] All existing tools are reachable through the new interface.
