"""MCP Tool Bridge — runtime MCP server discovery and tool invocation.

Discovers MCP servers from plugin registry, connects to them, and exposes
tools for invocation by the LLM or API.

Public API:
  list_servers() -> list[dict]       List configured MCP servers
  list_tools(server_name) -> list    List tools on a server
  invoke(server_name, tool_name, args) -> dict
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

logger = logging.getLogger("kitty.mcp_tool_bridge")

# For now, MCP servers are defined in config. Full MCP protocol support
# (stdio/SSE transport) is a future upgrade. This module reads server
# configs and exposes tool metadata for the LLM.


def list_servers() -> list[dict]:
    """List all configured MCP servers from plugins and config."""
    servers = []

    # From plugin registry
    try:
        from gateway.plugin_registry import get_enabled_mcp_servers
        servers.extend(get_enabled_mcp_servers())
    except Exception:
        logger.exception("failed to load MCP servers from plugin registry")

    # From .mcp.json config
    try:
        from gateway.paths import PROJECT_ROOT
        mcp_config = PROJECT_ROOT / ".mcp.json"
        if mcp_config.exists():
            config = json.loads(mcp_config.read_text())
            for name, server in config.get("mcpServers", {}).items():
                servers.append({
                    "name": name,
                    "command": server.get("command", ""),
                    "args": server.get("args", []),
                    "env": server.get("env", {}),
                    "source": "config",
                })
    except Exception as e:
        logger.warning("Failed to read .mcp.json: %s", e)

    return servers


def list_tools(server_name: str) -> list[dict]:
    """List tools available on an MCP server. Stub for now — returns from config."""
    # Full MCP protocol tool listing requires connecting to the server.
    # For now, return known tool schemas from plugin definitions.
    try:
        from gateway.plugin_registry import get_enabled_mcp_servers
        servers = get_enabled_mcp_servers()
        for server in servers:
            if server.get("name") == server_name:
                return server.get("tools", [])
    except Exception:
        logger.exception("failed to list MCP tools for %s", server_name)
    return []


async def invoke(
    server_name: str,
    tool_name: str,
    arguments: Optional[dict] = None,
) -> dict:
    """Invoke an MCP tool. Returns the tool's response.

    Currently supports filesystem and memory MCP servers via subprocess.
    Full MCP protocol integration is a future upgrade.
    """
    servers = list_servers()
    server = next((s for s in servers if s.get("name") == server_name), None)
    if not server:
        return {"error": f"MCP server not found: {server_name}"}

    command = server.get("command", "")
    if not command:
        return {"error": f"No command configured for server: {server_name}"}

    try:
        # Build MCP tool invocation payload
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments or {},
            },
            "id": 1,
        }

        proc = await asyncio.create_subprocess_exec(
            command,
            *server.get("args", []),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(json.dumps(payload).encode()),
            timeout=120,
        )

        if proc.returncode != 0:
            return {"error": stderr.decode()[:500]}

        response = json.loads(stdout.decode())
        if "error" in response:
            return {"error": response["error"]}
        return response.get("result", {})

    except asyncio.TimeoutError:
        return {"error": "MCP tool invocation timed out"}
    except Exception as e:
        logger.error("MCP invoke failed: %s", e)
        return {"error": str(e)}


def get_tool_schema_for_llm() -> list[dict]:
    """Return a list of available MCP tools formatted for LLM tool use."""
    tools = []
    servers = list_servers()
    for server in servers:
        for tool in server.get("tools", []):
            tools.append({
                "name": f"mcp__{server['name']}__{tool.get('name', '')}",
                "description": tool.get("description", f"MCP tool from {server['name']}"),
                "parameters": tool.get("parameters", {}),
            })
    return tools
