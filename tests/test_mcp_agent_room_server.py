from __future__ import annotations

import importlib
import sys
import types

import pytest

from gateway import agent_workspace


class FastMCPStub:
    instances: list["FastMCPStub"] = []

    def __init__(self, name: str, *args, **kwargs) -> None:
        self.name = name
        self.kwargs = kwargs
        self.tools: dict[str, object] = {}
        self.run_calls: list[tuple[tuple, dict]] = []
        self.__class__.instances.append(self)

    def tool(self, *args, **kwargs):
        def decorator(func):
            self.tools[func.__name__] = func
            return func

        return decorator

    def run(self, *args, **kwargs) -> None:
        self.run_calls.append((args, kwargs))


def _load_server(monkeypatch: pytest.MonkeyPatch, identity: str = "claude"):
    FastMCPStub.instances.clear()
    fastmcp_mod = types.ModuleType("mcp.server.fastmcp")
    fastmcp_mod.FastMCP = FastMCPStub  # type: ignore[attr-defined]
    server_mod = types.ModuleType("mcp.server")
    monkeypatch.setitem(sys.modules, "mcp.server", server_mod)
    monkeypatch.setitem(sys.modules, "mcp.server.fastmcp", fastmcp_mod)
    monkeypatch.setenv("KITTY_AGENT_ROOM_IDENTITY", identity)
    sys.modules.pop("mcp.agent_room.server", None)
    return importlib.import_module("mcp.agent_room.server")


@pytest.fixture
def room_db(monkeypatch: pytest.MonkeyPatch, tmp_path):
    db_file = tmp_path / "kitty" / "kitty.db"
    monkeypatch.setattr(agent_workspace, "WORKSPACE_DB_FILE", db_file)
    agent_workspace.init_db()
    return db_file


def test_server_registers_exact_room_tools_and_pins_identity(monkeypatch, room_db):
    server = _load_server(monkeypatch, "claude")
    instance = FastMCPStub.instances[-1]

    assert server.mcp is instance
    assert instance.name == "kitty-agent-room"
    assert server.CLIENT_IDENTITY == "claude"
    assert set(instance.tools) == {
        "room_status", "room_recent", "room_inbox", "room_thread",
        "room_post", "room_reply", "room_ack",
    }


def test_room_tools_share_domain_truth_without_sender_override(monkeypatch, room_db):
    root = agent_workspace.post_global_message(
        sender_id="chatgpt", recipient_id="claude",
        content="Review this protocol.", message_kind="handoff",
    )
    server = _load_server(monkeypatch, "claude")

    inbox = server.room_inbox(unread_only=True)
    assert [item["id"] for item in inbox] == [root["id"]]

    reply = server.room_reply(
        root["id"], "Looks good.", recipient_id="chatgpt", message_kind="review"
    )
    assert reply["sender_id"] == "claude"
    assert reply["parent_message_id"] == root["id"]

    receipt = server.room_ack(root["id"])
    assert receipt["participant_id"] == "claude"
    assert receipt["receipt_state"] == "acknowledged"
    assert server.room_inbox(unread_only=True) == []

    thread = server.room_thread(reply["id"])
    assert [item["id"] for item in thread] == [root["id"], reply["id"]]


def test_unknown_identity_fails_closed(monkeypatch: pytest.MonkeyPatch, room_db):
    with pytest.raises(agent_workspace.AgentWorkspaceError, match="unknown global participant"):
        _load_server(monkeypatch, "imaginary")


def test_main_defaults_to_stdio(monkeypatch: pytest.MonkeyPatch, room_db):
    monkeypatch.delenv("KITTY_AGENT_ROOM_MCP_TRANSPORT", raising=False)
    server = _load_server(monkeypatch)
    instance = FastMCPStub.instances[-1]

    server.main()

    assert instance.run_calls[-1] == (("stdio",), {})


def test_streamable_http_refuses_public_bind(monkeypatch: pytest.MonkeyPatch, room_db):
    monkeypatch.setenv("KITTY_AGENT_ROOM_MCP_TRANSPORT", "streamable-http")
    monkeypatch.setenv("KITTY_AGENT_ROOM_MCP_HOST", "0.0.0.0")
    server = _load_server(monkeypatch)
    instance = FastMCPStub.instances[-1]

    with pytest.raises(RuntimeError, match="public MCP bind"):
        server.main()

    assert instance.run_calls == []
