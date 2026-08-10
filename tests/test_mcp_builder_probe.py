from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

from mcp.builder import probe

REPO_ROOT = Path(__file__).parents[1]


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_listener(port: int, proc: subprocess.Popen[str]) -> None:
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            output = proc.stdout.read() if proc.stdout else ""
            pytest.fail(f"MCP server exited early ({proc.returncode}): {output}")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                return
        except OSError:
            time.sleep(0.05)
    pytest.fail("MCP server never opened its loopback listener")


@pytest.fixture()
def mcp_server():
    port = _free_port()
    env = os.environ.copy()
    env.update(
        PYTHONPATH=str(REPO_ROOT),
        KITTY_REPO_ROOT=str(REPO_ROOT),
        KITTYBUILDER_MCP_TRANSPORT="streamable-http",
        KITTYBUILDER_MCP_HOST="127.0.0.1",
        KITTYBUILDER_MCP_PORT=str(port),
    )
    proc = subprocess.Popen(
        [sys.executable, "-m", "mcp.builder.server"],
        cwd=REPO_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        _wait_for_listener(port, proc)
        yield f"http://127.0.0.1:{port}/mcp"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=3)


@pytest.mark.asyncio
async def test_probe_initializes_lists_governed_tools_and_calls_context(mcp_server):
    result = await probe.probe_protocol(mcp_server, call_context=True)

    assert result["initialized"] is True
    assert set(result["tools"]) == probe.EXPECTED_TOOLS
    assert probe.FORBIDDEN_TOOLS.isdisjoint(result["tools"])
    assert result["context"]["operation"] == "kitty_context"
    assert isinstance(result["context"]["ok"], bool)


def test_endpoint_url_uses_streamable_http_path():
    assert probe.endpoint_url("127.0.0.1", 8765) == "http://127.0.0.1:8765/mcp"
