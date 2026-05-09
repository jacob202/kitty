"""Tests for unified ToolRuntime (Phase 2C)."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Set

import pytest

from src.tools.runtime import (
    ToolKind,
    ToolDefinition,
    ToolContext,
    ToolResult,
    FunctionExecutor,
    HTTPExecutor,
    SpecialistExecutor,
    ToolRuntime,
    register_base_tool,
    get_runtime,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_context(permissions: Optional[Set[str]] = None, **meta) -> ToolContext:
    return ToolContext(
        permissions=permissions or set(),
        project_root=Path.cwd(),
        metadata=meta,
    )


def _simple_handler(**kwargs):
    return {"echo": kwargs}


async def _async_handler(**kwargs):
    return {"async_echo": kwargs}


# ---------------------------------------------------------------------------
# ToolDefinition
# ---------------------------------------------------------------------------

class TestToolDefinition:
    def test_basic_creation(self):
        td = ToolDefinition(name="test", description="A test tool", kind=ToolKind.FUNCTION)
        assert td.name == "test"
        assert td.kind == ToolKind.FUNCTION

    def test_with_handler(self):
        td = ToolDefinition(
            name="echo",
            description="Echo tool",
            kind=ToolKind.FUNCTION,
            handler=_simple_handler,
        )
        assert td.handler is _simple_handler


# ---------------------------------------------------------------------------
# FunctionExecutor
# ---------------------------------------------------------------------------

class TestFunctionExecutor:
    def test_sync_handler(self):
        td = ToolDefinition(name="echo", description="", kind=ToolKind.FUNCTION, handler=_simple_handler)
        ctx = _make_context()
        exec = FunctionExecutor()
        result = asyncio.run(exec.execute(td, {"msg": "hi"}, ctx))
        assert result.ok is True
        assert result.result == {"echo": {"msg": "hi"}}

    def test_async_handler(self):
        td = ToolDefinition(name="async_echo", description="", kind=ToolKind.FUNCTION, handler=_async_handler)
        ctx = _make_context()
        exec = FunctionExecutor()
        result = asyncio.run(exec.execute(td, {"msg": "hello"}, ctx))
        assert result.ok is True
        assert result.result == {"async_echo": {"msg": "hello"}}

    def test_no_handler(self):
        td = ToolDefinition(name="broken", description="", kind=ToolKind.FUNCTION, handler=None)
        ctx = _make_context()
        exec = FunctionExecutor()
        result = asyncio.run(exec.execute(td, {}, ctx))
        assert result.ok is False
        assert "No handler" in result.error


# ---------------------------------------------------------------------------
# SpecialistExecutor
# ---------------------------------------------------------------------------

class TestSpecialistExecutor:
    def test_depth_limit(self):
        td = ToolDefinition(name="spec", description="", kind=ToolKind.SPECIALIST)
        ctx = _make_context()
        ctx.metadata["specialist_depth"] = 3  # at limit
        exec = SpecialistExecutor()
        result = asyncio.run(exec.execute(td, {}, ctx))
        assert result.ok is False
        assert "depth limit" in result.error.lower()

    def test_within_depth(self):
        td = ToolDefinition(name="spec", description="", kind=ToolKind.SPECIALIST)
        ctx = _make_context()
        ctx.metadata["specialist_depth"] = 1
        exec = SpecialistExecutor()
        # Should not raise, will return "not yet wired" error but not depth error
        result = asyncio.run(exec.execute(td, {}, ctx))
        assert "depth limit" not in (result.error or "").lower()


# ---------------------------------------------------------------------------
# HTTPExecutor
# ---------------------------------------------------------------------------

class TestHTTPExecutor:
    def test_get_uses_httpx_without_blocking_contract(self, monkeypatch):
        captured = {}

        class DummyResponse:
            status_code = 200
            text = '{"ok": true}'

            def raise_for_status(self):
                return None

        class DummyClient:
            def __init__(self, timeout=None):
                captured["timeout"] = timeout

            async def __aenter__(self):
                captured["entered"] = True
                return self

            async def __aexit__(self, exc_type, exc, tb):
                captured["exited"] = True
                return False

            async def get(self, url, params=None, headers=None):
                captured["method"] = "GET"
                captured["url"] = url
                captured["params"] = params
                captured["headers"] = headers
                return DummyResponse()

        monkeypatch.setattr("httpx.AsyncClient", DummyClient)

        td = ToolDefinition(name="http", description="", kind=ToolKind.HTTP, http_endpoint="https://example.com/api")
        ctx = _make_context()
        result = asyncio.run(HTTPExecutor().execute(td, {"method": "GET", "params": {"q": "x"}, "headers": {"X-Test": "1"}, "timeout": 5}, ctx))

        assert result.ok is True
        assert result.result == {"status_code": 200, "body": '{"ok": true}'}
        assert captured["entered"] is True
        assert captured["exited"] is True
        assert captured["method"] == "GET"
        assert captured["url"] == "https://example.com/api"
        assert captured["params"] == {"q": "x"}
        assert captured["headers"] == {"X-Test": "1"}
        assert captured["timeout"] == 5


# ---------------------------------------------------------------------------
# ToolRuntime
# ---------------------------------------------------------------------------

class TestToolRuntime:
    def setup_method(self):
        self.rt = ToolRuntime()

    def test_register_and_get(self):
        td = ToolDefinition(name="my_tool", description="test", kind=ToolKind.FUNCTION, handler=_simple_handler)
        self.rt.register(td)
        assert self.rt.get("my_tool") is td
        assert self.rt.get("nonexistent") is None

    def test_list_tools(self):
        td1 = ToolDefinition(name="t1", description="Tool 1", kind=ToolKind.FUNCTION)
        td2 = ToolDefinition(name="t2", description="Tool 2", kind=ToolKind.SPECIALIST)
        self.rt.register(td1)
        self.rt.register(td2)
        tools = self.rt.list_tools()
        assert "t1" in tools
        assert "t2" in tools

    def test_execute_unknown_tool(self):
        ctx = _make_context()
        result = asyncio.run(self.rt.execute("nope", {}, ctx))
        assert result.ok is False
        assert "Unknown tool" in result.error

    def test_execute_permission_denied(self):
        td = ToolDefinition(
            name="secret",
            description="",
            kind=ToolKind.FUNCTION,
            handler=_simple_handler,
            required_permissions={"admin"},
        )
        self.rt.register(td)
        ctx = _make_context(permissions=set())  # no permissions
        result = asyncio.run(self.rt.execute("secret", {}, ctx))
        assert result.ok is False
        assert result.denied is True
        assert "Missing permissions" in result.error

    def test_execute_permission_granted(self):
        td = ToolDefinition(
            name="allowed",
            description="",
            kind=ToolKind.FUNCTION,
            handler=_simple_handler,
            required_permissions={"read"},
        )
        self.rt.register(td)
        ctx = _make_context(permissions={"read", "write"})
        result = asyncio.run(self.rt.execute("allowed", {"x": 1}, ctx))
        assert result.ok is True
        assert result.result == {"echo": {"x": 1}}

    def test_execute_permission_denied_registry_bridge_unavailable(self):
        """Test that when ToolRegistry is unavailable, only tool permissions are checked."""
        # Register a tool with NO required permissions
        td = ToolDefinition(
            name="read_file",
            description="Read file tool",
            kind=ToolKind.FUNCTION,
            handler=_simple_handler,
            required_permissions=set(),  # Explicitly no permissions required
        )
        self.rt.register(td)
        # Context with NO permissions
        ctx = _make_context(permissions=set())
        # Should succeed because tool requires no permissions
        result = asyncio.run(self.rt.execute("read_file", {"path": "/tmp/test"}, ctx))
        assert result.ok is True
        assert result.denied is False
        assert result.result == {"echo": {"path": "/tmp/test"}}

    def test_execute_no_executor(self):
        td = ToolDefinition(name="weird", description="", kind="weird_kind")  # type: ignore
        self.rt.register(td)
        ctx = _make_context()
        result = asyncio.run(self.rt.execute("weird", {}, ctx))
        assert result.ok is False
        assert "No executor" in result.error

    def test_execute_batch(self):
        td1 = ToolDefinition(name="echo1", description="", kind=ToolKind.FUNCTION, handler=_simple_handler)
        td2 = ToolDefinition(name="echo2", description="", kind=ToolKind.FUNCTION, handler=_simple_handler)
        self.rt.register(td1)
        self.rt.register(td2)
        ctx = _make_context()
        calls = [
            {"name": "echo1", "args": {"a": 1}},
            {"name": "echo2", "args": {"b": 2}},
        ]
        results = asyncio.run(self.rt.execute_batch(calls, ctx))
        assert len(results) == 2
        assert all(r.ok for r in results)

    def test_register_base_tool_invokes_execute_once(self):
        calls = {"count": 0}

        class DummyTool:
            name = "dummy_tool"
            description = "Dummy tool"
            command = "/dummy"

            def execute(self, **kwargs):
                calls["count"] += 1
                return ToolResult(ok=True, tool=self.name, args=kwargs, result={"ok": True})

        register_base_tool(self.rt, DummyTool)
        ctx = _make_context()
        result = asyncio.run(self.rt.execute("dummy_tool", {"value": 1}, ctx))

        assert result.ok is True
        assert result.result == {"ok": True}
        assert calls["count"] == 1


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------

class TestGetRuntime:
    def test_singleton(self):
        rt1 = get_runtime()
        rt2 = get_runtime()
        assert rt1 is rt2
