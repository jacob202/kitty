"""ToolManager — thin wrapper around ToolRuntime for backward compatibility."""

from __future__ import annotations

from typing import Any

from src.tools.base import BaseTool, ToolResult
from src.tools.runtime import get_runtime, ToolRuntime, ToolContext


class ToolManager:
    _instance: ToolManager | None = None

    def __init__(self) -> None:
        # Import implementations to trigger _register_all()
        import src.tools.implementations  # noqa: F401
        self._rt = get_runtime()

    def get_tool_by_name(self, name: str) -> type[BaseTool] | None:
        # Check ToolRuntime first, fall back to BaseTool registry
        if self._rt.get(name):
            return BaseTool.get_tool(name)  # stil returns type for backward compat
        return BaseTool.get_tool(name)

    def get_tool_by_command(self, command: str) -> type[BaseTool] | None:
        return BaseTool.get_tool_by_command(command)

    def execute(self, name: str, **kwargs: Any) -> ToolResult:
        # Delegate to ToolRuntime
        ctx = ToolContext(permissions=set())
        import asyncio
        result = asyncio.run(self._rt.execute(name, kwargs, ctx))
        # Convert ToolRuntime's ToolResult to BaseTool's ToolResult for compatibility
        return ToolResult(
            ok=result.ok,
            tool=result.tool,
            args=result.args,
            result=result.result,
            error=result.error,
            denied=result.denied,
        )

    def execute_command(self, query: str) -> ToolResult | None:
        parts = query.strip().split(maxsplit=1)
        if not parts:
            return None
        command = parts[0]
        cls = self.get_tool_by_command(command)
        if cls is None:
            return None
        rest = parts[1] if len(parts) > 1 else ""
        return cls().execute(command=command, args=rest)

    def list_tools(self) -> dict[str, str]:
        return BaseTool.list_tools()

    @property
    def runtime(self) -> ToolRuntime:
        """Direct access to underlying ToolRuntime (for new code)."""
        return self._rt


def get_tool_manager() -> ToolManager:
    if ToolManager._instance is None:
        ToolManager._instance = ToolManager()
    return ToolManager._instance
