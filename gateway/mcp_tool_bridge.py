"""MCP Tool Bridge — runtime discovery and bounded tool invocation.

This module deliberately owns only the transport/lifecycle seam. Kitty's
standing authorization policy remains in :mod:`gateway.action_grants`.
Circuit state is process-local load-shedding state, not durable product truth.
"""
from __future__ import annotations

import asyncio
import json
import logging
import math
import time
from dataclasses import dataclass
from threading import Lock
from typing import Any, Optional

logger = logging.getLogger("kitty.mcp_tool_bridge")

DEFAULT_TOOL_TIMEOUT_SECONDS = 120.0
MAX_TOOL_TIMEOUT_SECONDS = 300.0
PROCESS_REAP_GRACE_SECONDS = 1.0
CIRCUIT_FAILURE_THRESHOLD = 3
CIRCUIT_COOLDOWN_SECONDS = 30.0


@dataclass
class _CircuitState:
    consecutive_failures: int = 0
    opened_at: float | None = None
    probe_in_flight: bool = False
    last_error: str = ""


_CIRCUITS: dict[tuple[str, str], _CircuitState] = {}
_CIRCUIT_LOCK = Lock()
_monotonic = time.monotonic


def reset_circuit_breakers() -> None:
    """Clear ephemeral cutoff state. Primarily a deterministic test/operator seam."""
    with _CIRCUIT_LOCK:
        _CIRCUITS.clear()


def list_servers() -> list[dict]:
    """List all configured MCP servers from plugins and repo config."""
    servers: list[dict] = []

    try:
        from gateway.plugin_registry import get_enabled_mcp_servers

        servers.extend(get_enabled_mcp_servers())
    except Exception:
        logger.exception("failed to load MCP servers from plugin registry")

    try:
        from gateway.paths import PROJECT_ROOT

        mcp_config = PROJECT_ROOT / ".mcp.json"
        if mcp_config.exists():
            config = json.loads(mcp_config.read_text())
            for name, server in config.get("mcpServers", {}).items():
                servers.append(
                    {
                        "name": name,
                        "command": server.get("command", ""),
                        "args": server.get("args", []),
                        "env": server.get("env", {}),
                        "timeout_seconds": server.get("timeout_seconds"),
                        "tool_timeouts": server.get("tool_timeouts"),
                        "source": "config",
                    }
                )
    except Exception as exc:
        logger.warning("Failed to read .mcp.json: %s", exc)

    return servers


def list_tools(server_name: str) -> list[dict]:
    """List tools available on an MCP server from registered definitions."""
    try:
        from gateway.plugin_registry import get_enabled_mcp_servers

        servers = get_enabled_mcp_servers()
        for server in servers:
            if server.get("name") == server_name:
                return server.get("tools", [])
    except Exception:
        logger.exception("failed to list MCP tools for %s", server_name)
    return []


def _validated_timeout(value: object, *, label: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or float(value) <= 0
        or float(value) > MAX_TOOL_TIMEOUT_SECONDS
    ):
        raise ValueError(
            f"{label} must be a finite positive number <= {MAX_TOOL_TIMEOUT_SECONDS:g}"
        )
    return float(value)


def _tool_timeout(server: dict[str, Any], tool_name: str) -> float:
    per_tool = server.get("tool_timeouts")
    if per_tool is not None:
        if not isinstance(per_tool, dict):
            raise ValueError("tool_timeouts must be an object")
        if tool_name in per_tool:
            return _validated_timeout(
                per_tool[tool_name], label=f"tool timeout for {tool_name!r}"
            )
    server_timeout = server.get("timeout_seconds")
    if server_timeout is not None:
        return _validated_timeout(server_timeout, label="server timeout_seconds")
    return DEFAULT_TOOL_TIMEOUT_SECONDS


def _before_call(key: tuple[str, str]) -> tuple[bool, float]:
    """Return whether a call may start and, when blocked, retry-after seconds."""
    now = _monotonic()
    with _CIRCUIT_LOCK:
        state = _CIRCUITS.get(key)
        if state is None or state.opened_at is None:
            return True, 0.0
        remaining = CIRCUIT_COOLDOWN_SECONDS - (now - state.opened_at)
        if remaining > 0:
            return False, remaining
        if state.probe_in_flight:
            return False, 0.0
        state.probe_in_flight = True
        return True, 0.0


def _record_success(key: tuple[str, str]) -> None:
    with _CIRCUIT_LOCK:
        _CIRCUITS.pop(key, None)


def _release_probe(key: tuple[str, str]) -> None:
    """Release a half-open probe after caller cancellation without blaming the tool."""
    with _CIRCUIT_LOCK:
        state = _CIRCUITS.get(key)
        if state is not None:
            state.probe_in_flight = False


def _record_failure(key: tuple[str, str], message: str) -> None:
    now = _monotonic()
    with _CIRCUIT_LOCK:
        state = _CIRCUITS.setdefault(key, _CircuitState())
        was_probe = state.probe_in_flight
        state.probe_in_flight = False
        state.consecutive_failures += 1
        state.last_error = message[:500]
        if was_probe or state.consecutive_failures >= CIRCUIT_FAILURE_THRESHOLD:
            state.opened_at = now


def _server_configuration_error(server: dict[str, Any]) -> str | None:
    name = server.get("name")
    label = str(name or "<unnamed>")
    command = server.get("command")
    if not isinstance(command, str) or not command.strip():
        return f"{label}: command must be a non-empty string"
    args = server.get("args", [])
    if not isinstance(args, list) or not all(isinstance(arg, str) for arg in args):
        return f"{label}: args must be a list of strings"
    try:
        if server.get("timeout_seconds") is not None:
            _validated_timeout(server["timeout_seconds"], label="timeout_seconds")
        tool_timeouts = server.get("tool_timeouts")
        if tool_timeouts is not None:
            if not isinstance(tool_timeouts, dict):
                raise ValueError("tool_timeouts must be an object")
            for tool, value in tool_timeouts.items():
                if not isinstance(tool, str) or not tool.strip():
                    raise ValueError("tool_timeouts keys must be non-empty strings")
                _validated_timeout(value, label=f"tool timeout for {tool!r}")
    except ValueError as exc:
        return f"{label}: {exc}"
    return None


def tool_health_snapshot() -> dict[str, Any]:
    """Return configured/circuit health without pretending remote liveness was probed."""
    configured = list_servers()
    configuration_errors = [
        error for server in configured if (error := _server_configuration_error(server))
    ]
    now = _monotonic()
    open_circuits: list[dict[str, Any]] = []
    with _CIRCUIT_LOCK:
        for (server, tool), state in sorted(_CIRCUITS.items()):
            if state.opened_at is None:
                continue
            retry_after = max(
                0.0, CIRCUIT_COOLDOWN_SECONDS - (now - state.opened_at)
            )
            open_circuits.append(
                {
                    "server": server,
                    "tool": tool,
                    "consecutive_failures": state.consecutive_failures,
                    "retry_after_seconds": round(retry_after, 3),
                    "probe_due": retry_after <= 0 and not state.probe_in_flight,
                    "last_error": state.last_error,
                }
            )
    return {
        "state": "degraded" if open_circuits or configuration_errors else "available",
        "configured_servers": len(configured),
        "configuration_errors": configuration_errors,
        "open_circuits": open_circuits,
        "remote_health_probed": False,
    }


async def _communicate(
    proc: asyncio.subprocess.Process, payload: bytes, *, timeout: float
) -> tuple[bytes, bytes]:
    async with asyncio.timeout(timeout):
        return await proc.communicate(payload)


async def _reap_process(proc: asyncio.subprocess.Process) -> None:
    """Guarantee a spawned child is not left alive after interruption."""
    if proc.returncode is not None:
        return
    proc.terminate()
    try:
        async with asyncio.timeout(PROCESS_REAP_GRACE_SECONDS):
            await proc.wait()
            return
    except TimeoutError:
        proc.kill()
        await proc.wait()


def _error(message: str, *, code: str) -> dict[str, Any]:
    return {"error": message, "code": code}


async def invoke(
    server_name: str,
    tool_name: str,
    arguments: Optional[dict] = None,
) -> dict:
    """Invoke an MCP tool with bounded timeout, cleanup, and failure cutoff."""
    servers = list_servers()
    server = next((s for s in servers if s.get("name") == server_name), None)
    if not server:
        return _error(f"MCP server not found: {server_name}", code="server_not_found")

    configuration_error = _server_configuration_error(server)
    if configuration_error:
        return _error(configuration_error, code="invalid_configuration")
    command = server["command"]

    try:
        timeout = _tool_timeout(server, tool_name)
    except ValueError as exc:
        return _error(str(exc), code="invalid_configuration")

    key = (server_name, tool_name)
    allowed, retry_after = _before_call(key)
    if not allowed:
        return {
            **_error(
                f"MCP tool circuit is open for {server_name}/{tool_name}",
                code="circuit_open",
            ),
            "retry_after_seconds": round(retry_after, 3),
        }

    payload = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments or {}},
        "id": 1,
    }
    proc: asyncio.subprocess.Process | None = None
    try:
        proc = await asyncio.create_subprocess_exec(
            command,
            *server.get("args", []),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await _communicate(
            proc, json.dumps(payload).encode(), timeout=timeout
        )

        if proc.returncode != 0:
            message = stderr.decode(errors="replace")[:500] or (
                f"MCP server exited with code {proc.returncode}"
            )
            _record_failure(key, message)
            return _error(message, code="server_error")

        try:
            response = json.loads(stdout.decode())
        except (UnicodeError, json.JSONDecodeError) as exc:
            message = f"MCP server returned invalid JSON: {exc}"
            _record_failure(key, message)
            return _error(message, code="invalid_response")
        if not isinstance(response, dict):
            message = "MCP server returned a non-object response"
            _record_failure(key, message)
            return _error(message, code="invalid_response")
        if "error" in response:
            message = str(response["error"])
            _record_failure(key, message)
            return _error(message, code="tool_error")

        result = response.get("result", {})
        if not isinstance(result, dict):
            message = "MCP tool result must be an object"
            _record_failure(key, message)
            return _error(message, code="invalid_response")
        _record_success(key)
        return result
    except TimeoutError:
        if proc is not None:
            await _reap_process(proc)
        message = f"MCP tool invocation timed out after {timeout:g}s"
        _record_failure(key, message)
        return _error(message, code="timeout")
    except asyncio.CancelledError:
        if proc is not None:
            await _reap_process(proc)
        _release_probe(key)
        raise
    except Exception as exc:
        if proc is not None:
            await _reap_process(proc)
        logger.exception("MCP invoke failed: %s", exc)
        message = str(exc)
        _record_failure(key, message)
        return _error(message, code="transport_error")


def get_tool_schema_for_llm() -> list[dict]:
    """Return available MCP tools formatted for LLM tool use."""
    tools = []
    servers = list_servers()
    for server in servers:
        for tool in server.get("tools", []):
            tools.append(
                {
                    "name": f"mcp__{server['name']}__{tool.get('name', '')}",
                    "description": tool.get(
                        "description", f"MCP tool from {server['name']}"
                    ),
                    "parameters": tool.get("parameters", {}),
                }
            )
    return tools
