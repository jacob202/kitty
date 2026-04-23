"""Read file tool."""

from src.tools import tool_registry
from src.tools.base import BaseTool, ToolResult


class ReadFileTool(BaseTool):
    """Tool for reading file content."""

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def command(self) -> str:
        return "/read"

    @property
    def description(self) -> str:
        return "Read the complete content of a specified file."

    def execute(self, path: str) -> ToolResult:
        registry = tool_registry.get_registry()
        registry_result = registry.read_file(path)

        return ToolResult(
            ok=registry_result.ok,
            tool=self.name,
            args=registry_result.args,
            result=registry_result.result,
            error=registry_result.error,
            denied=registry_result.denied,
        )
