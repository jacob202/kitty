"""List directory tool."""

from typing import Any

from src.tools import tool_registry
from src.tools.base import BaseTool, ToolResult


class ListDirectoryTool(BaseTool):
    """Tool for listing directory contents."""

    @property
    def name(self) -> str:
        return "list_directory"

    @property
    def command(self) -> str:
        return "/ls"

    @property
    def description(self) -> str:
        return "List files and subdirectories in a given path."

    def execute(self, **kwargs: Any) -> ToolResult:
        path = kwargs.get("path", ".")
        registry = tool_registry.get_registry()
        registry_result = registry.list_directory(path)

        # Map ToolRegistry.ToolResult to ToolManager.ToolResult
        return ToolResult(
            ok=registry_result.ok,
            tool=self.name,
            args=registry_result.args,
            result=registry_result.result,
            error=registry_result.error,
            denied=registry_result.denied,
        )
