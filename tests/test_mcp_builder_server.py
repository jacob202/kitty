from __future__ import annotations

import importlib
import sys
import types

import pytest


class FastMCPStub:
    instances: list["FastMCPStub"] = []

    def __init__(self, name: str, *args, **kwargs) -> None:
        self.name = name
        self.kwargs = kwargs
        self.tools: list[str] = []
        self.run_calls: list[tuple[tuple, dict]] = []
        self.__class__.instances.append(self)

    def tool(self, *args, **kwargs):
        def decorator(func):
            self.tools.append(func.__name__)
            return func

        return decorator

    def run(self, *args, **kwargs) -> None:
        self.run_calls.append((args, kwargs))


def _load_server(monkeypatch: pytest.MonkeyPatch):
    FastMCPStub.instances.clear()
    fastmcp_mod = types.ModuleType("mcp.server.fastmcp")
    fastmcp_mod.FastMCP = FastMCPStub  # type: ignore[attr-defined]
    server_mod = types.ModuleType("mcp.server")
    monkeypatch.setitem(sys.modules, "mcp.server", server_mod)
    monkeypatch.setitem(sys.modules, "mcp.server.fastmcp", fastmcp_mod)
    sys.modules.pop("mcp.builder.server", None)
    return importlib.import_module("mcp.builder.server")


def test_server_registers_only_high_level_builder_tools(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = _load_server(monkeypatch)
    instance = FastMCPStub.instances[-1]

    assert server.mcp is instance
    assert instance.name == "kittybuilder"
    assert set(instance.tools) == {
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
    forbidden = {"shell", "write_file", "git_push", "merge_pr", "sql"}
    assert forbidden.isdisjoint(instance.tools)
    assert instance.run_calls == []


def test_fastmcp_v1_http_settings_are_constructor_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KITTYBUILDER_MCP_HOST", "127.0.0.1")
    monkeypatch.setenv("KITTYBUILDER_MCP_PORT", "8765")

    _load_server(monkeypatch)
    instance = FastMCPStub.instances[-1]

    assert instance.kwargs["host"] == "127.0.0.1"
    assert instance.kwargs["port"] == 8765
    assert instance.kwargs["json_response"] is True
    assert instance.kwargs["stateless_http"] is True


def test_main_defaults_to_stdio(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KITTYBUILDER_MCP_TRANSPORT", raising=False)
    server = _load_server(monkeypatch)
    instance = FastMCPStub.instances[-1]

    server.main()

    assert instance.run_calls[-1] == (("stdio",), {})


def test_streamable_http_uses_v1_run_signature(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KITTYBUILDER_MCP_TRANSPORT", "streamable-http")
    monkeypatch.setenv("KITTYBUILDER_MCP_HOST", "127.0.0.1")
    monkeypatch.setenv("KITTYBUILDER_MCP_PORT", "8765")
    server = _load_server(monkeypatch)
    instance = FastMCPStub.instances[-1]

    server.main()

    assert instance.run_calls[-1] == (("streamable-http",), {})


def test_public_http_bind_is_refused_before_server_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KITTYBUILDER_MCP_TRANSPORT", "streamable-http")
    monkeypatch.setenv("KITTYBUILDER_MCP_HOST", "0.0.0.0")
    server = _load_server(monkeypatch)
    instance = FastMCPStub.instances[-1]

    with pytest.raises(RuntimeError, match="public MCP bind"):
        server.main()

    assert instance.run_calls == []


def test_invalid_http_port_fails_loudly_at_import(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KITTYBUILDER_MCP_PORT", "not-a-port")

    with pytest.raises(RuntimeError, match="KITTYBUILDER_MCP_PORT"):
        _load_server(monkeypatch)
