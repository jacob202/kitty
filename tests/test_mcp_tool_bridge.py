from __future__ import annotations

import asyncio
import json

import pytest

from gateway import mcp_tool_bridge as bridge


class FakeProcess:
    def __init__(
        self,
        *,
        stdout: bytes = b'{"jsonrpc":"2.0","id":1,"result":{"ok":true}}',
        stderr: bytes = b"",
        returncode: int | None = 0,
        hang: bool = False,
    ) -> None:
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode
        self.hang = hang
        self.terminated = False
        self.killed = False
        self.waited = 0
        self.input: bytes | None = None

    async def communicate(self, payload: bytes) -> tuple[bytes, bytes]:
        self.input = payload
        if self.hang:
            await asyncio.Event().wait()
        return self.stdout, self.stderr

    def terminate(self) -> None:
        self.terminated = True

    def kill(self) -> None:
        self.killed = True

    async def wait(self) -> int:
        self.waited += 1
        self.returncode = -15 if self.terminated and not self.killed else -9
        return self.returncode


@pytest.fixture(autouse=True)
def _clear_breakers() -> None:
    bridge.reset_circuit_breakers()


def _server(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "name": "demo",
        "command": "/bin/demo-mcp",
        "args": [],
        "tools": [{"name": "lookup"}],
    }
    value.update(overrides)
    return value


@pytest.mark.asyncio
async def test_timeout_reaps_child_before_returning_error(monkeypatch: pytest.MonkeyPatch) -> None:
    proc = FakeProcess(returncode=None, hang=True)
    monkeypatch.setattr(bridge, "list_servers", lambda: [_server(timeout_seconds=0.01)])
    monkeypatch.setattr(asyncio, "create_subprocess_exec", lambda *args, **kwargs: asyncio.sleep(0, result=proc))

    result = await bridge.invoke("demo", "lookup", {"q": "x"})

    assert result["code"] == "timeout"
    assert proc.terminated is True
    assert proc.waited >= 1


@pytest.mark.asyncio
async def test_cancellation_reaps_child_and_propagates_cancel(monkeypatch: pytest.MonkeyPatch) -> None:
    started = asyncio.Event()

    class StartedProcess(FakeProcess):
        async def communicate(self, payload: bytes) -> tuple[bytes, bytes]:
            self.input = payload
            started.set()
            await asyncio.Event().wait()
            raise AssertionError("unreachable")

    proc = StartedProcess(returncode=None, hang=True)
    monkeypatch.setattr(bridge, "list_servers", lambda: [_server(timeout_seconds=10)])

    async def spawn(*args, **kwargs):
        return proc

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)

    task = asyncio.create_task(bridge.invoke("demo", "lookup"))
    await asyncio.wait_for(started.wait(), timeout=1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert proc.terminated is True
    assert proc.waited >= 1


@pytest.mark.asyncio
async def test_repeated_failures_open_circuit_without_spawning_again(monkeypatch: pytest.MonkeyPatch) -> None:
    spawned = 0

    async def spawn(*args, **kwargs):
        nonlocal spawned
        spawned += 1
        return FakeProcess(stderr=b"down", returncode=2)

    monkeypatch.setattr(bridge, "list_servers", lambda: [_server()])
    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    monkeypatch.setattr(bridge, "CIRCUIT_FAILURE_THRESHOLD", 2)

    first = await bridge.invoke("demo", "lookup")
    second = await bridge.invoke("demo", "lookup")
    blocked = await bridge.invoke("demo", "lookup")

    assert "error" in first and "error" in second
    assert blocked["code"] == "circuit_open"
    assert spawned == 2
    snapshot = bridge.tool_health_snapshot()
    assert snapshot["state"] == "degraded"
    assert snapshot["open_circuits"][0]["tool"] == "lookup"


@pytest.mark.asyncio
async def test_cooldown_allows_one_probe_and_success_closes_circuit(monkeypatch: pytest.MonkeyPatch) -> None:
    now = 100.0
    outcomes = [
        FakeProcess(stderr=b"fail-1", returncode=2),
        FakeProcess(stderr=b"fail-2", returncode=2),
        FakeProcess(returncode=0),
    ]

    async def spawn(*args, **kwargs):
        return outcomes.pop(0)

    monkeypatch.setattr(bridge, "list_servers", lambda: [_server()])
    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    monkeypatch.setattr(bridge, "CIRCUIT_FAILURE_THRESHOLD", 2)
    monkeypatch.setattr(bridge, "CIRCUIT_COOLDOWN_SECONDS", 30.0)
    monkeypatch.setattr(bridge, "_monotonic", lambda: now)

    await bridge.invoke("demo", "lookup")
    await bridge.invoke("demo", "lookup")
    assert (await bridge.invoke("demo", "lookup"))["code"] == "circuit_open"

    now = 131.0
    recovered = await bridge.invoke("demo", "lookup")

    assert recovered == {"ok": True}
    assert bridge.tool_health_snapshot()["open_circuits"] == []


@pytest.mark.asyncio
async def test_tool_specific_timeout_overrides_server_default(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[float] = []
    proc = FakeProcess(returncode=0)
    monkeypatch.setattr(
        bridge,
        "list_servers",
        lambda: [_server(timeout_seconds=9, tool_timeouts={"lookup": 2.5})],
    )
    monkeypatch.setattr(asyncio, "create_subprocess_exec", lambda *args, **kwargs: asyncio.sleep(0, result=proc))
    monkeypatch.setattr(bridge, "_communicate", _capturing_communicate(seen))

    result = await bridge.invoke("demo", "lookup")

    assert result == {"ok": True}
    assert seen == [2.5]


def _capturing_communicate(seen: list[float]):
    async def run(proc: FakeProcess, payload: bytes, *, timeout: float):
        seen.append(timeout)
        return await proc.communicate(payload)

    return run


@pytest.mark.asyncio
async def test_invalid_timeout_configuration_fails_before_spawn(monkeypatch: pytest.MonkeyPatch) -> None:
    spawned = False

    async def spawn(*args, **kwargs):
        nonlocal spawned
        spawned = True
        return FakeProcess()

    monkeypatch.setattr(bridge, "list_servers", lambda: [_server(timeout_seconds=-1)])
    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)

    result = await bridge.invoke("demo", "lookup")

    assert result["code"] == "invalid_configuration"
    assert spawned is False


def test_config_server_preserves_timeout_policy(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    config = tmp_path / ".mcp.json"
    config.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "demo": {
                        "command": "/bin/demo",
                        "timeout_seconds": 12,
                        "tool_timeouts": {"lookup": 3},
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("gateway.paths.PROJECT_ROOT", tmp_path)
    monkeypatch.setattr("gateway.plugin_registry.get_enabled_mcp_servers", lambda: [])

    servers = bridge.list_servers()

    assert servers[0]["timeout_seconds"] == 12
    assert servers[0]["tool_timeouts"] == {"lookup": 3}
