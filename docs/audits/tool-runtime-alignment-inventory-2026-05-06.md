# Tool Runtime Alignment Inventory — 2026-05-06

## Purpose
Inventory active tool surfaces before completing Phase 2C alignment. Identifies overlap, duplication, and migration-safe boundaries.

## Active Tool Surfaces (Entry Points)

### 1. `src/tools/base.py` — BaseTool abstract class
- **Role**: Abstract base for all tool implementations
- **Key exports**: `BaseTool`, `ToolResult`
- **Registry**: `BaseTool._registry` (dict[str, type[BaseTool]])
- **Used by**: `tool_manager.py`, `implementations/*.py`, `runtime.py` (adapter)

### 2. `src/tools/tool_manager.py` — ToolManager singleton
- **Role**: Central lookup + execution (now wraps ToolRuntime)
- **Key methods**: `get_tool_by_name()`, `get_tool_by_command()`, `execute()`, `execute_command()`
- **Now delegates**: `execute()` → `ToolRuntime.execute()`
- **Backward compat**: `get_tool_by_name()` still returns `type[BaseTool]`

### 3. `src/tools/tool_registry.py` — ToolRegistry (permissions)
- **Role**: Sandboxed tool registry with path restrictions + action logging
- **Tools**: `list_directory`, `read_file`, `search_files`
- **Permissions**: `ToolPermission` enum, `TOOL_PERMISSIONS` dict
- **Not yet integrated** with ToolRuntime permission system

### 4. `src/tools/runtime.py` — ToolRuntime (NEW, Phase 2C)
- **Role**: Unified tool runtime with executor factory
- **Key classes**: `ToolDefinition`, `ToolContext`, `ToolResult`, `ToolRuntime`
- **Executors**: `FunctionExecutor`, `HTTPExecutor` (stub), `SpecialistExecutor` (stub, depth-gated)
- **Adapter**: `register_base_tool()` bridges BaseTool → ToolRuntime
- **Status**: Implemented, 15 tests passing

### 5. `src/tools/kitty_tools.py` — KittyTools (OLD system)
- **Role**: Legacy tool framework with `ToolDefinition` (different from runtime.py)
- **Contains**: `KittyTools` class, `ToolDefinition` (old), dangerous command blocking
- **Status**: Still used by `src/core/specialist_framework.py`
- **Migration needed**: Replace with ToolRuntime native tools

### 6. `src/tools/implementations/*.py` — BaseTool Subclasses
- **Files**: `system_tools.py`, `code_tools.py`, `web_tools.py`, `macos_tools.py`, `media_tools.py`, `obd_tools.py`
- **Registration**: `implementations/__init__.py` → `BaseTool._registry`
- **Adapter**: `register_all_base_tools(rt)` in `runtime.py` auto-registers these

### 7. `src/core/agent_router.py` — Agent Router
- **Role**: Routes tool calls from agents
- **Uses**: `ToolManager` (line 52), falls back to `KittyTools` (line 58)
- **Migration needed**: Use ToolRuntime directly

### 8. `src/core/specialist_framework.py` — Specialist Framework
- **Role**: Executes specialist tools
- **Uses**: `KittyTools` (line 208-229)
- **Migration needed**: Use ToolRuntime with `SpecialistExecutor`

## Overlap / Duplication Points

| Issue | Location | Action Needed |
|-------|----------|---------------|
| Two `ToolDefinition` classes | `kitty_tools.py` vs `runtime.py` | Migrate to `runtime.py` version |
| Two `ToolResult` classes | `base.py` vs `runtime.py` | Keep `runtime.py` version, deprecate `base.py` |
| Two permission systems | `tool_registry.py` vs `runtime.py` | Integrate `ToolRuntime` permissions with `ToolRegistry` |
| ToolManager + ToolRuntime | `tool_manager.py` wraps `runtime.py` | Eventually deprecate ToolManager |

## Migration-Safe Boundaries

1. **BaseTool registry** (`base.py`): Keep alive until all subclasses migrated to `ToolDefinition`
2. **ToolManager** (`tool_manager.py`): Keep as backward-compat wrapper during transition
3. **ToolRegistry** (`tool_registry.py`): Keep for file-permission checks until integrated
4. **KittyTools** (`kitty_tools.py`): Keep until `agent_router.py` and `specialist_framework.py` migrated

## Next Steps (Remaining Phase 2C Tasks)

- [x] **2C-2**: Unified Runtime Facade (COMPLETED)
- [ ] **2C-3**: Permission Path Alignment (integrate `ToolRegistry` permissions into `ToolRuntime`)
- [ ] **2C-4**: Integration and Regression Gate (run full suite, update tracking docs)
