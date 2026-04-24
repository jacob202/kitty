"""ToolManager central lookup for all tool execution."""

from __future__ import annotations

from typing import Any

from src.tools.base import BaseTool, ToolResult


class ToolManager:
    _instance: ToolManager | None = None

    def __init__(self) -> None:
        # Import implementations to trigger _register_all()
        import src.tools.implementations  # noqa: F401

    def get_tool_by_name(self, name: str) -> type[BaseTool] | None:
        return BaseTool.get_tool(name)

    def get_tool_by_command(self, command: str) -> type[BaseTool] | None:
        return BaseTool.get_tool_by_command(command)

    def execute(self, name: str, **kwargs: Any) -> ToolResult:
        cls = self.get_tool_by_name(name)
        if cls is None:
            return ToolResult(ok=False, tool=name, args=kwargs, error=f"Unknown tool: {name}")
        return cls().execute(**kwargs)

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


def get_tool_manager() -> ToolManager:
    if ToolManager._instance is None:
        ToolManager._instance = ToolManager()
    return ToolManager._instance
