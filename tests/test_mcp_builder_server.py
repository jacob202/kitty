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


@pytest.fixture()
def server(monkeypatch: pytest.MonkeyPatch):
    FastMCPStub.instances.clear()
    fastmcp_mod = types.ModuleType("mcp.server.fastmcp")
    fastmcp_mod.FastMCP = FastMCPStub  # type: ignore[attr-defined]
    server_mod = types.ModuleType("mcp.server")
    monkeypatch.setitem(sys.modules, "mcp.server", server_mod)
    monkeypatch.setitem(sys.modules, "mcp.server.fastmcp", fastmcp_mod)
    sys.modules.pop("mcp.builder.server", None)
    return importlib.import_module("mcp.builder.server")


def test_server_registers_only_high_level_builder_tools(server) -> None:
    instance = FastMCPStub.instances[-1]

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


def test_main_defaults_to_stdio(server, monkeypatch: pytest.MonkeyPatch) -> None:
    instance = FastMCPStub.instances[-1]
    monkeypatch.delenv("KITTYBUILDER_MCP_TRANSPORT", raising=False)

    server.main()

    assert instance.run_calls[-1] == (("stdio",), {})


def test_streamable_http_binds_loopback_by_default(
    server, monkeypatch: pytest.MonkeyPatch
) -> None:
    instance = FastMCPStub.instances[-1]
    monkeypatch.setenv("KITTYBUILDER_MCP_TRANSPORT", "streamable-http")
    monkeypatch.delenv("KITTYBUILDER_MCP_HOST", raising=False)
    monkeypatch.setenv("KITTYBUILDER_MCP_PORT", "8765")

    server.main()

    args, kwargs = instance.run_calls[-1]
    assert args == ("streamable-http",)
    assert kwargs["host"] == "127.0.0.1"
    assert kwargs["port"] == 8765
    assert kwargs["json_response"] is True
    assert kwargs["stateless_http"] is True


def test_public_http_bind_requires_explicit_opt_in(server, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KITTYBUILDER_MCP_TRANSPORT", "streamable-http")
    monkeypatch.setenv("KITTYBUILDER_MCP_HOST", "0.0.0.0")
    monkeypatch.delenv("KITTYBUILDER_MCP_ALLOW_PUBLIC_BIND", raising=False)

    with pytest.raises(RuntimeError, match="public MCP bind"):
        server.main()
