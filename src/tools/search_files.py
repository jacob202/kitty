"""Search files tool."""

from src.tools import tool_registry
from src.tools.base import BaseTool, ToolResult


class SearchFilesTool(BaseTool):
    """Tool for searching file content."""

    @property
    def name(self) -> str:
        return "search_files"

    @property
    def command(self) -> str:
        return "/search"

    @property
    def description(self) -> str:
        return "Search for a pattern within files in a directory."

    def execute(self, query: str, path: str = ".") -> ToolResult:
        registry = tool_registry.get_registry()
        registry_result = registry.search_files(query=query, path=path)

        return ToolResult(
            ok=registry_result.ok,
            tool=self.name,
            args=registry_result.args,
            result=registry_result.result,
            error=registry_result.error,
            denied=registry_result.denied,
        )
