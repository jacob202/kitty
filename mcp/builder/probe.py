"""Real Streamable-HTTP client probes for the KittyBuilder MCP bridge."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client

EXPECTED_TOOLS = frozenset(
    {
        "kitty_context",
        "repo_search",
        "repo_read",
        "save_design",
        "save_plan",
        "work_status",
        "work_result",
        "resume_context",
        "mission_prepare",
        "mission_approve",
        "execution_start",
        "execution_pause",
        "execution_resume",
        "execution_cancel",
        "publication_status",
        "publication_prepare",
    }
)
FORBIDDEN_TOOLS = frozenset({"shell", "write_file", "git_push", "merge_pr", "sql"})


class ProbeError(RuntimeError):
    """Raised when the MCP transport result cannot be trusted or decoded."""


def endpoint_url(host: str, port: int) -> str:
    return f"http://{host}:{port}/mcp"


@asynccontextmanager
async def open_session(endpoint: str) -> AsyncIterator[ClientSession]:
    async with streamable_http_client(endpoint) as (read_stream, write_stream, _session_id):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            yield session


def _structured_content(result: Any) -> dict[str, Any] | None:
    value = getattr(result, "structuredContent", None)
    if isinstance(value, dict):
        return value
    value = getattr(result, "structured_content", None)
    if isinstance(value, dict):
        return value
    return None


async def call_tool_json(
    session: ClientSession,
    name: str,
    arguments: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result = await session.call_tool(name, arguments or {})
    if bool(getattr(result, "isError", False)):
        raise ProbeError(f"MCP tool {name!r} returned a protocol/tool error")

    structured = _structured_content(result)
    if structured is not None:
        return structured

    content = list(getattr(result, "content", []) or [])
    text_blocks = [getattr(item, "text", None) for item in content if getattr(item, "type", None) == "text"]
    text_blocks = [text for text in text_blocks if isinstance(text, str)]
    if len(text_blocks) != 1:
        raise ProbeError(
            f"MCP tool {name!r} returned no structured object and {len(text_blocks)} text blocks"
        )
    try:
        decoded = json.loads(text_blocks[0])
    except json.JSONDecodeError as exc:
        raise ProbeError(f"MCP tool {name!r} returned non-JSON text") from exc
    if not isinstance(decoded, dict):
        raise ProbeError(f"MCP tool {name!r} returned JSON that is not an object")
    return decoded


async def probe_protocol(endpoint: str, *, call_context: bool = True) -> dict[str, Any]:
    async with open_session(endpoint) as session:
        listed = await session.list_tools()
        tools = sorted(tool.name for tool in listed.tools)
        context = await call_tool_json(session, "kitty_context") if call_context else None
        return {
            "initialized": True,
            "endpoint": endpoint,
            "tools": tools,
            "context": context,
        }
