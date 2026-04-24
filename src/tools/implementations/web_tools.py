"""BaseTool wrappers for web search tools."""

from __future__ import annotations

from typing import Any

from src.tools.base import BaseTool, ToolResult

__all__ = ["WebSearchTool", "DeepSearchTool"]


class WebSearchTool(BaseTool):
    """Wrapper for web search functionality."""

    @property
    def name(self) -> str:
        return "web_search"

    @property
    def command(self) -> str:
        return "/web"

    @property
    def description(self) -> str:
        return "Search the web for information."

    def execute(self, **kwargs: Any) -> ToolResult:
        query = kwargs.get("query") or " ".join(str(v) for v in kwargs.values())
        if not query:
            return ToolResult(ok=False, tool=self.name, args=kwargs, error="No search query provided")
        try:
            from src.tools.web_search import WebSearch
            import os

            ws = WebSearch(api_key=os.environ.get("TAVILY_API_KEY", ""))
            result = ws.search(query)
            return ToolResult(ok=True, tool=self.name, args=kwargs, result={"output": str(result)})
        except Exception as e:
            return ToolResult(ok=False, tool=self.name, args=kwargs, error=str(e))


class DeepSearchTool(BaseTool):
    """Wrapper for deep web search with scraping support."""

    @property
    def name(self) -> str:
        return "deep_search"

    @property
    def command(self) -> str:
        return "/deepsearch"

    @property
    def description(self) -> str:
        return "Deep web search that scrapes and summarizes results."

    def execute(self, **kwargs: Any) -> ToolResult:
        query = kwargs.get("query") or " ".join(str(v) for v in kwargs.values())
        if not query:
            return ToolResult(ok=False, tool=self.name, args=kwargs, error="No search query provided")
        try:
            from src.tools.deep_search import deep_search
            from tavily import TavilyClient
            import os

            api_key = os.environ.get("TAVILY_API_KEY", "")
            client = TavilyClient(api_key=api_key) if api_key else None
            result = deep_search(query, tavily_client=client, max_results=kwargs.get("max_results", 5), scrape=kwargs.get("scrape", True))
            return ToolResult(ok=True, tool=self.name, args=kwargs, result={"output": str(result)})
        except Exception as e:
            return ToolResult(ok=False, tool=self.name, args=kwargs, error=str(e))
