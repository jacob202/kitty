"""MCP Client — Model Context Protocol integration for filesystem and git tools."""
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

class MCPManager:
    """
    Lightweight MCP client wrapper.
    Falls back gracefully if mcp package not installed.
    """
    def __init__(self):
        self._available = self._check_mcp()

    def _check_mcp(self) -> bool:
        try:
            import mcp  # type: ignore[import-untyped]  # noqa: F401
            return True
        except ImportError:
            logger.warning("mcp package not installed; MCPManager in stub mode")
            return False

    def _get_server_params(self, server_name: str):
        if not self._available:
            return None
        from mcp import StdioServerParameters  # type: ignore[import-untyped]
        servers = {
            "filesystem": StdioServerParameters(
                command="npx",
                args=["-y", "@modelcontextprotocol/server-filesystem",
                      str(Path.home() / "AgentCompany" / "data")]
            ),
            "git": StdioServerParameters(
                command="uvx",
                args=["mcp-server-git", "--repository", str(Path.cwd())]
            )
        }
        return servers.get(server_name)

    async def list_tools(self, server_name: str) -> list[dict]:
        if not self._available:
            return []
        from mcp import ClientSession
        from mcp.client.stdio import stdio_client
        params = self._get_server_params(server_name)
        if params is None:
            return []
        try:
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools = await session.list_tools()
                    return [{"name": t.name, "description": t.description}
                            for t in tools.tools]
        except Exception as e:
            logger.error(f"list_tools error: {e}")
            return []

    async def call_tool(self, server_name: str, tool_name: str,
                        arguments: dict[str, Any]) -> Any:
        if not self._available:
            return None
        from mcp import ClientSession
        from mcp.client.stdio import stdio_client
        params = self._get_server_params(server_name)
        if params is None:
            return None
        try:
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(tool_name, arguments=arguments)
                    return result.content
        except Exception as e:
            logger.error(f"call_tool error: {e}")
            return None
