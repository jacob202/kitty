"""Unified Tool Runtime — consolidated tool execution with permissions."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Type

import httpx

from src.tools.base import ToolResult as BaseToolResult


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

class ToolKind(str, Enum):
    FUNCTION = "function"
    HTTP = "http"
    SPECIALIST = "specialist"


@dataclass
class ToolDefinition:
    name: str
    description: str
    kind: ToolKind
    handler: Optional[Callable] = None  # for FUNCTION kind
    http_endpoint: Optional[str] = None   # for HTTP kind
    specialist_name: Optional[str] = None  # for SPECIALIST kind
    required_permissions: Set[str] = field(default_factory=set)
    input_schema: Optional[Dict] = None


@dataclass
class ToolContext:
    permissions: Set[str]
    project_root: Path = field(default_factory=Path.cwd)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolResult:
    ok: bool
    tool: str
    args: Dict[str, Any]
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    denied: bool = False


# ---------------------------------------------------------------------------
# Executor base
# ---------------------------------------------------------------------------

class BaseExecutor:
    async def execute(self, tool: ToolDefinition, args: Dict[str, Any], context: ToolContext) -> ToolResult:
        raise NotImplementedError


class FunctionExecutor(BaseExecutor):
    """Execute a Python callable registered as handler."""

    async def execute(self, tool: ToolDefinition, args: Dict[str, Any], context: ToolContext) -> ToolResult:
        if tool.handler is None:
            return ToolResult(ok=False, tool=tool.name, args=args, error="No handler for FUNCTION tool")
        try:
            # Support both sync and async handlers
            result = tool.handler(**args)
            if asyncio.iscoroutine(result):
                result = await result
            if isinstance(result, BaseToolResult) or (
                is_dataclass(result) and all(hasattr(result, attr) for attr in ("ok", "tool", "args"))
            ):
                return ToolResult(
                    ok=result.ok,
                    tool=result.tool,
                    args=result.args,
                    result=result.result,
                    error=result.error,
                    denied=result.denied,
                )
            return ToolResult(ok=True, tool=tool.name, args=args, result=result)
        except Exception as e:
            return ToolResult(ok=False, tool=tool.name, args=args, error=str(e))


class HTTPExecutor(BaseExecutor):
    """Execute HTTP-based tools using httpx."""

    async def execute(self, tool: ToolDefinition, args: Dict[str, Any], context: ToolContext) -> ToolResult:
        if not tool.http_endpoint:
            return ToolResult(ok=False, tool=tool.name, args=args, error="No HTTP endpoint defined")
        try:
            method = args.get("method", "GET").upper()
            url = tool.http_endpoint
            params = args.get("params", {})
            headers = args.get("headers", {})
            timeout = args.get("timeout", 30)

            async with httpx.AsyncClient(timeout=timeout) as client:
                if method == "GET":
                    resp = await client.get(url, params=params, headers=headers)
                elif method == "POST":
                    data = args.get("data")
                    json_data = args.get("json")
                    resp = await client.post(url, params=params, data=data, json=json_data, headers=headers)
                else:
                    return ToolResult(ok=False, tool=tool.name, args=args, error=f"Unsupported method: {method}")

            resp.raise_for_status()
            return ToolResult(
                ok=True, tool=tool.name, args=args,
                result={"status_code": resp.status_code, "body": resp.text[:2000]}
            )
        except Exception as e:
            return ToolResult(ok=False, tool=tool.name, args=args, error=f"HTTP request failed: {e}")


class SpecialistExecutor(BaseExecutor):
    """Stub for specialist tool execution — recursion gated by depth limit."""

    MAX_DEPTH = 3

    async def execute(self, tool: ToolDefinition, args: Dict[str, Any], context: ToolContext) -> ToolResult:
        depth = context.metadata.get("specialist_depth", 0)
        if depth >= self.MAX_DEPTH:
            return ToolResult(
                ok=False, tool=tool.name, args=args,
                error=f"Specialist recursion depth limit ({self.MAX_DEPTH}) reached",
            )
        return ToolResult(
            ok=False, tool=tool.name, args=args,
            error="SpecialistExecutor not yet wired to SpecialistRuntime",
        )


# ---------------------------------------------------------------------------
# Tool Runtime
# ---------------------------------------------------------------------------

class ToolRuntime:
    def __init__(self) -> None:
        self._registry: Dict[str, ToolDefinition] = {}
        self._executors: Dict[ToolKind, BaseExecutor] = {
            ToolKind.FUNCTION: FunctionExecutor(),
            ToolKind.HTTP: HTTPExecutor(),
            ToolKind.SPECIALIST: SpecialistExecutor(),
        }

    # -- Registry --

    def register(self, tool: ToolDefinition) -> None:
        self._registry[tool.name] = tool

    def get(self, name: str) -> Optional[ToolDefinition]:
        return self._registry.get(name)

    def list_tools(self) -> Dict[str, str]:
        return {name: tool.description for name, tool in self._registry.items()}

    # -- Permission --

    def _check_permissions(self, tool: ToolDefinition, context: ToolContext) -> Optional[str]:
        # Check ToolDefinition permissions
        missing = tool.required_permissions - context.permissions
        if missing:
            return f"Missing permissions: {', '.join(sorted(missing))}"
        # Bridge: also check ToolRegistry permissions if available
        try:
            from src.tools import tool_registry
            registry = tool_registry.get_registry()
            reg_perms = registry.permissions_for(tool.name)
            missing_reg = reg_perms - context.permissions
            if missing_reg:
                return f"Missing registry permissions: {', '.join(sorted(p.value for p in missing_reg))}"
        except Exception as e:  # ToolRegistry not available, skip bridge check
                logging.getLogger(__name__).warning(f"Tool registry check failed: {e}")
        return None

    # -- Execution --

    async def execute(self, name: str, args: Dict[str, Any], context: ToolContext) -> ToolResult:
        tool = self.get(name)
        if tool is None:
            return ToolResult(ok=False, tool=name, args=args, error=f"Unknown tool: {name}")

        reason = self._check_permissions(tool, context)
        if reason:
            return ToolResult(ok=False, tool=name, args=args, denied=True, error=reason)

        executor = self._executors.get(tool.kind)
        if executor is None:
            return ToolResult(ok=False, tool=name, args=args, error=f"No executor for kind: {tool.kind}")

        return await executor.execute(tool, args, context)

    async def execute_batch(self, calls: List[Dict[str, Any]], context: ToolContext) -> List[ToolResult]:
        """Execute multiple tool calls concurrently."""
        tasks = [self.execute(c["name"], c.get("args", {}), context) for c in calls]
        return await asyncio.gather(*tasks)


# ---------------------------------------------------------------------------
# Adapter: register BaseTool subclasses into ToolRuntime
# ---------------------------------------------------------------------------

def _base_tool_handler_factory(cls: Type[Any]):
    """Create a handler that instantiates and executes a BaseTool subclass."""
    def handler(**kwargs):
        inst = cls()
        return inst.execute(**kwargs)
    return handler


def register_base_tool(rt: ToolRuntime, cls: Type[Any]) -> None:
    """Register a BaseTool subclass into the given ToolRuntime."""
    try:
        inst = cls()
    except Exception:
        return
    kind = ToolKind.FUNCTION
    handler = _base_tool_handler_factory(cls)
    td = ToolDefinition(
        name=inst.name,
        description=inst.description,
        kind=kind,
        handler=handler,
        required_permissions=set(),  # BaseTool doesn't have permission model yet
    )
    rt.register(td)


def register_all_base_tools(rt: ToolRuntime) -> None:
    """Register all currently-known BaseTool subclasses into ToolRuntime."""
    from src.tools.base import BaseTool
    for name, cls in BaseTool._registry.items():
        register_base_tool(rt, cls)


# ---------------------------------------------------------------------------
# Singleton accessor (for backward compatibility during transition)
# ---------------------------------------------------------------------------

_runtime: Optional[ToolRuntime] = None


def get_runtime() -> ToolRuntime:
    global _runtime
    if _runtime is None:
        _runtime = ToolRuntime()
        # Auto-register existing BaseTool subclasses
        register_all_base_tools(_runtime)
    return _runtime
