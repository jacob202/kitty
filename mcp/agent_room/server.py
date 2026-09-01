"""FastMCP entry point for Kitty's canonical global agent room."""

from __future__ import annotations

import os

from gateway import agent_workspace
from mcp.server.fastmcp import FastMCP


def _client_identity() -> str:
    identity = os.environ.get("KITTY_AGENT_ROOM_IDENTITY", "").strip()
    if not identity:
        raise RuntimeError("KITTY_AGENT_ROOM_IDENTITY must name this MCP client")
    identity = agent_workspace.validate_global_participant(identity)
    if agent_workspace.global_sender_kind(identity) != "agent":
        allowed = ", ".join(agent["id"] for agent in agent_workspace.GLOBAL_AGENTS)
        raise agent_workspace.AgentWorkspaceError(
            f"MCP identity must be one of: {allowed}"
        )
    return identity


def _server_host() -> str:
    host = os.environ.get("KITTY_AGENT_ROOM_MCP_HOST", "127.0.0.1").strip()
    if not host:
        raise RuntimeError("KITTY_AGENT_ROOM_MCP_HOST must not be blank")
    return host


def _server_port() -> int:
    raw = os.environ.get("KITTY_AGENT_ROOM_MCP_PORT", "8766")
    try:
        port = int(raw)
    except ValueError as exc:
        raise RuntimeError("KITTY_AGENT_ROOM_MCP_PORT must be an integer") from exc
    if not 1 <= port <= 65535:
        raise RuntimeError("KITTY_AGENT_ROOM_MCP_PORT must be between 1 and 65535")
    return port


CLIENT_IDENTITY = _client_identity()
_HOST = _server_host()
_PORT = _server_port()

mcp = FastMCP(
    "kitty-agent-room",
    instructions=(
        "This server joins Kitty's one durable global collaboration room as the "
        f"fixed identity {CLIENT_IDENTITY!r}. Read the inbox/recent/thread before "
        "replying. Post/reply never changes Builder execution truth or #490 lane "
        "ownership. Acknowledgement means receipt only, never task completion."
    ),
    host=_HOST,
    port=_PORT,
    json_response=True,
    stateless_http=True,
)


def _status() -> dict:
    room = agent_workspace.ensure_global_workspace()
    return {
        "id": room["id"],
        "status": room["status"],
        "identity": CLIENT_IDENTITY,
        "participants": [agent["id"] for agent in room["agents"]],
    }


@mcp.tool()
def room_status() -> dict:
    """Return canonical room identity, participants, and this client's fixed identity."""
    return _status()


@mcp.tool()
def room_recent(limit: int = 100) -> list[dict]:
    """Read recent durable room messages without mutating receipt state."""
    agent_workspace.ensure_global_workspace()
    return agent_workspace.list_messages(agent_workspace.GLOBAL_WORKSPACE_ID, limit=limit)


@mcp.tool()
def room_inbox(unread_only: bool = False, limit: int = 100) -> list[dict]:
    """Read messages addressed to this configured client identity."""
    return agent_workspace.list_inbox(
        CLIENT_IDENTITY, unread_only=unread_only, limit=limit
    )


@mcp.tool()
def room_thread(message_id: str, limit: int = 100) -> list[dict]:
    """Read one message thread from its root through descendants."""
    return agent_workspace.list_thread(message_id, limit=limit)


@mcp.tool()
def room_post(
    content: str,
    recipient_id: str | None = None,
    message_kind: str = "status",
) -> dict:
    """Post as this configured client identity; sender identity is not overridable."""
    return agent_workspace.post_global_message(
        sender_id=CLIENT_IDENTITY,
        recipient_id=recipient_id,
        content=content,
        message_kind=message_kind,
    )


@mcp.tool()
def room_reply(
    message_id: str,
    content: str,
    recipient_id: str | None = None,
    message_kind: str = "status",
) -> dict:
    """Reply in-thread as this configured client identity."""
    return agent_workspace.post_global_message(
        sender_id=CLIENT_IDENTITY,
        recipient_id=recipient_id,
        content=content,
        message_kind=message_kind,
        parent_message_id=message_id,
    )


@mcp.tool()
def room_ack(message_id: str) -> dict:
    """Acknowledge receipt for this configured client identity."""
    return agent_workspace.record_receipt(
        message_id, CLIENT_IDENTITY, "acknowledged"
    )


def main() -> None:
    transport = os.environ.get(
        "KITTY_AGENT_ROOM_MCP_TRANSPORT", "stdio"
    ).strip().lower()
    if transport == "stdio":
        mcp.run("stdio")
        return
    if transport != "streamable-http":
        raise RuntimeError(
            "KITTY_AGENT_ROOM_MCP_TRANSPORT must be 'stdio' or 'streamable-http'"
        )
    if _HOST not in {"127.0.0.1", "localhost", "::1"}:
        raise RuntimeError(
            "public MCP bind is refused; keep the Agent Room on loopback"
        )
    mcp.run("streamable-http")


if __name__ == "__main__":
    main()
