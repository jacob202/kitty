"""Read-only operator status and ordered diagnostics for KittyBuilder MCP."""

from __future__ import annotations

import asyncio
import importlib.metadata
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from gateway import builder_status_readonly
from gateway.paths import BUILDER_QUEUE_DB

from . import probe, repo_tools

BOUNDARY_ORDER = (
    "checkout",
    "runtime",
    "process",
    "transport",
    "contract",
    "context",
    "builder",
    "repository",
    "github",
    "provider",
)


@dataclass(frozen=True)
class OperatorConfig:
    root: Path
    host: str
    port: int
    pid_file: Path
    log_file: Path

    @property
    def endpoint(self) -> str:
        return probe.endpoint_url(self.host, self.port)


def load_config() -> OperatorConfig:
    root = repo_tools.repo_root()
    host = os.environ.get("KITTYBUILDER_MCP_HOST", "127.0.0.1").strip()
    raw_port = os.environ.get("KITTYBUILDER_MCP_PORT", "8765").strip()
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise RuntimeError("KittyBuilder MCP host must be loopback")
    try:
        port = int(raw_port)
    except ValueError as exc:
        raise RuntimeError("KITTYBUILDER_MCP_PORT must be an integer") from exc
    if not 1 <= port <= 65535:
        raise RuntimeError("KITTYBUILDER_MCP_PORT must be between 1 and 65535")
    return OperatorConfig(
        root=root,
        host=host,
        port=port,
        pid_file=root / "logs" / ".run" / "mcp.pid",
        log_file=root / "logs" / "mcp.log",
    )


def _run_fixed(argv: list[str], *, cwd: Path | None = None, timeout: int = 5) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
        shell=False,
    )


def _listener_pids(port: int) -> list[int]:
    result = _run_fixed(["lsof", f"-tiTCP:{port}", "-sTCP:LISTEN"])
    if result.returncode not in {0, 1}:
        return []
    pids: list[int] = []
    for line in result.stdout.splitlines():
        try:
            pids.append(int(line.strip()))
        except ValueError:
            continue
    return pids


def _pid_command(pid: int) -> str:
    result = _run_fixed(["ps", "-p", str(pid), "-o", "command="])
    return result.stdout.strip() if result.returncode == 0 else ""


def _pid_cwd(pid: int) -> str | None:
    result = _run_fixed(["lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"])
    if result.returncode != 0:
        return None
    for line in result.stdout.splitlines():
        if line.startswith("n") and len(line) > 1:
            return line[1:]
    return None


def process_status(config: OperatorConfig) -> dict[str, Any]:
    listeners = _listener_pids(config.port)
    if not config.pid_file.exists():
        if listeners:
            return {
                "state": "conflict",
                "pid": None,
                "alive": False,
                "owned": False,
                "listener_pids": listeners,
                "command": None,
                "cwd": None,
                "summary": "MCP port has a listener but no owned PID file.",
            }
        return {
            "state": "stopped",
            "pid": None,
            "alive": False,
            "owned": False,
            "listener_pids": [],
            "command": None,
            "cwd": None,
            "summary": "MCP server is stopped.",
        }

    try:
        pid = int(config.pid_file.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return {
            "state": "conflict",
            "pid": None,
            "alive": False,
            "owned": False,
            "listener_pids": listeners,
            "command": None,
            "cwd": None,
            "summary": "MCP PID file is unreadable or malformed.",
        }

    try:
        os.kill(pid, 0)
        alive = True
    except (ProcessLookupError, PermissionError):
        alive = False

    if not alive:
        return {
            "state": "stopped" if not listeners else "conflict",
            "pid": pid,
            "alive": False,
            "owned": False,
            "listener_pids": listeners,
            "command": None,
            "cwd": None,
            "summary": "MCP PID file is stale." if not listeners else "Stale MCP PID conflicts with a live listener.",
        }

    command = _pid_command(pid)
    cwd = _pid_cwd(pid)
    try:
        owned_cwd = cwd is not None and Path(cwd).resolve() == config.root.resolve()
    except OSError:
        owned_cwd = False
    owned = owned_cwd and "mcp.builder.server" in command
    if not owned:
        state = "conflict"
        summary = "Live PID is not the KittyBuilder MCP process owned by this worktree."
    elif pid not in listeners:
        state = "degraded"
        summary = "Owned MCP process is alive but not listening on the configured port."
    else:
        state = "running"
        summary = "Owned MCP process is running on the configured loopback listener."
    return {
        "state": state,
        "pid": pid,
        "alive": alive,
        "owned": owned,
        "listener_pids": listeners,
        "command": command,
        "cwd": cwd,
        "summary": summary,
    }


def _check(
    boundary: str,
    state: str,
    summary: str,
    *,
    evidence: dict[str, Any] | None = None,
    next_action: str | None = None,
    classification: str = "local",
    check_id: str | None = None,
) -> dict[str, Any]:
    return {
        "id": check_id or boundary,
        "boundary": boundary,
        "state": state,
        "summary": summary,
        "evidence": evidence or {},
        "next_action": next_action,
        "classification": classification,
    }


def _blocked(boundary: str, cause: str) -> dict[str, Any]:
    return _check(
        boundary,
        "blocked",
        f"Blocked by earlier {cause} failure.",
        classification="local",
    )


def _check_checkout(config: OperatorConfig) -> dict[str, Any]:
    try:
        result = _run_fixed(["git", "rev-parse", "--show-toplevel"], cwd=config.root)
    except (OSError, subprocess.SubprocessError) as exc:
        return _check(
            "checkout",
            "fail",
            f"Cannot inspect Kitty checkout: {type(exc).__name__}: {exc}",
            next_action="Run the command from the canonical Kitty Git checkout.",
        )
    if result.returncode != 0:
        return _check(
            "checkout",
            "fail",
            "Configured root is not an intelligible Git checkout.",
            evidence={"stderr": result.stderr.strip()[:300]},
            next_action="Run the command from the canonical Kitty Git checkout.",
        )
    actual = Path(result.stdout.strip()).resolve()
    if actual != config.root.resolve():
        return _check(
            "checkout",
            "fail",
            "Configured Kitty root does not equal the Git toplevel.",
            evidence={"expected": str(config.root), "actual": str(actual)},
            next_action="Use the exact Kitty worktree root and retry.",
        )
    return _check("checkout", "pass", "Canonical Git checkout resolved.", evidence={"root": str(actual)})


def _check_runtime(_config: OperatorConfig) -> dict[str, Any]:
    if sys.version_info < (3, 12):
        return _check(
            "runtime",
            "fail",
            f"Python {sys.version_info.major}.{sys.version_info.minor} is unsupported.",
            next_action="Run KittyBuilder MCP with Python 3.12 or newer.",
        )
    try:
        version = importlib.metadata.version("mcp")
        parts = version.split(".")
        major = int(parts[0])
        minor = int(parts[1]) if len(parts) > 1 else 0
        from mcp.client.streamable_http import streamable_http_client as _client  # noqa: F401
    except Exception as exc:  # dependency/import failures are heterogeneous
        return _check(
            "runtime",
            "fail",
            f"Supported MCP SDK is unavailable: {type(exc).__name__}: {exc}",
            next_action="Install with 'python3.12 -m pip install -r mcp/builder/requirements.txt'.",
        )
    if major != 1 or minor < 27:
        return _check(
            "runtime",
            "fail",
            f"MCP SDK {version} is outside supported >=1.27,<2.",
            evidence={"mcp_version": version},
            next_action="Install with 'python3.12 -m pip install -r mcp/builder/requirements.txt'.",
        )
    return _check(
        "runtime",
        "pass",
        "Python and MCP SDK satisfy the v1 contract.",
        evidence={"python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}", "mcp_version": version},
    )


def _check_process(config: OperatorConfig) -> dict[str, Any]:
    status = process_status(config)
    if status["state"] == "running":
        return _check("process", "pass", status["summary"], evidence=status)
    action = "Run 'kitty mcp up'." if status["state"] == "stopped" else "Resolve the MCP PID/listener ownership conflict before continuing."
    return _check("process", "fail", status["summary"], evidence=status, next_action=action)


def _builder_db_path() -> Path:
    return BUILDER_QUEUE_DB


def _check_builder(_config: OperatorConfig) -> dict[str, Any]:
    path = _builder_db_path()
    if not path.exists():
        return _check(
            "builder",
            "warn",
            "Builder durable database does not exist yet; no state was created by doctor.",
            evidence={"path": str(path)},
            next_action="Apply an explicitly approved Builder Mission before expecting durable work state.",
        )
    try:
        snapshot = builder_status_readonly.build_status_snapshot_readonly(db_path=path)
    except Exception as exc:  # read-only sqlite/integrity failures are heterogeneous
        return _check(
            "builder",
            "fail",
            f"Builder durable state cannot be read safely: {type(exc).__name__}: {exc}",
            evidence={"path": str(path)},
            next_action="Inspect the Builder database with the read-only Builder doctor/status path.",
        )
    return _check(
        "builder",
        "pass",
        "Builder durable state is readable without migration or mutation.",
        evidence={
            "path": str(path),
            "queue_total": (snapshot.get("queue") or {}).get("total"),
            "initiative_count": len(snapshot.get("initiatives") or []),
        },
    )


def _check_repository(config: OperatorConfig) -> dict[str, Any]:
    try:
        result = _run_fixed(["git", "worktree", "list", "--porcelain"], cwd=config.root)
    except (OSError, subprocess.SubprocessError) as exc:
        return _check("repository", "fail", f"Cannot inspect Git worktrees: {exc}", next_action="Repair the local Git checkout/worktree metadata.")
    kitty = config.root / "kitty"
    writable = os.access(config.root, os.W_OK | os.X_OK)
    if result.returncode != 0 or not kitty.is_file() or not os.access(kitty, os.X_OK) or not writable:
        return _check(
            "repository",
            "fail",
            "Repository execution prerequisites are incomplete.",
            evidence={"git_worktree_ok": result.returncode == 0, "kitty_executable": kitty.is_file() and os.access(kitty, os.X_OK), "root_writable": writable},
            next_action="Repair Git worktree metadata and Kitty checkout permissions.",
        )
    return _check("repository", "pass", "Git/worktree execution prerequisites are available.")


def _check_github(config: OperatorConfig, *, publication_required: bool = False) -> dict[str, Any]:
    gh = shutil.which("gh")
    fail_state = "fail" if publication_required else "warn"
    if not gh:
        return _check(
            "github",
            fail_state,
            "GitHub CLI is unavailable; local MCP operation remains independent.",
            next_action="Install/authenticate GitHub CLI before publication." if publication_required else None,
            classification="external",
        )
    try:
        result = _run_fixed([gh, "auth", "status"], cwd=config.root, timeout=5)
    except (OSError, subprocess.SubprocessError) as exc:
        return _check(
            "github",
            fail_state,
            f"GitHub authentication could not be checked: {type(exc).__name__}.",
            next_action="Run 'gh auth status' and repair GitHub authentication before publication." if publication_required else None,
            classification="external",
        )
    if result.returncode != 0:
        return _check(
            "github",
            fail_state,
            "GitHub CLI is present but not ready for publication.",
            next_action="Run 'gh auth status' and repair GitHub authentication before publication." if publication_required else None,
            classification="external",
        )
    return _check("github", "pass", "GitHub CLI authentication is ready.", classification="external")


def _check_provider(config: OperatorConfig) -> dict[str, Any]:
    worker = config.root / "scripts" / "kittybuilder_opencode_worker.sh"
    reviewer = config.root / "scripts" / "kittybuilder_opencode_reviewer.sh"
    opencode = shutil.which("opencode")
    ready = worker.is_file() and os.access(worker, os.X_OK) and reviewer.is_file() and os.access(reviewer, os.X_OK) and bool(opencode)
    if not ready:
        return _check(
            "provider",
            "warn",
            "A complete free OpenCode worker/reviewer route is unavailable; no paid fallback was attempted.",
            evidence={"worker": worker.is_file() and os.access(worker, os.X_OK), "reviewer": reviewer.is_file() and os.access(reviewer, os.X_OK), "opencode": bool(opencode)},
            next_action="Configure the free OpenCode worker/reviewer route before starting the proof.",
            classification="external",
        )
    return _check(
        "provider",
        "pass",
        "Free OpenCode worker/reviewer route is available.",
        evidence={"opencode": opencode},
        classification="external",
    )


def _summarize(checks: list[dict[str, Any]]) -> dict[str, Any]:
    failure = next((item for item in checks if item["state"] == "fail"), None)
    warnings = [item for item in checks if item["state"] in {"warn", "unknown"}]
    if failure:
        state = "unavailable"
        next_action = failure.get("next_action") or "Resolve the first failing boundary and rerun doctor."
    elif warnings:
        state = "degraded"
        next_action = next((item.get("next_action") for item in warnings if item.get("next_action")), None) or "Review the warnings before starting proof execution."
    else:
        state = "healthy"
        next_action = "Start or continue the approved KPROOF Mission."
    return {
        "ok": failure is None,
        "state": state,
        "first_failure": failure,
        "next_action": next_action,
    }


def status_report(config: OperatorConfig) -> dict[str, Any]:
    process = process_status(config)
    base: dict[str, Any] = {
        "operation": "mcp_status",
        "root": str(config.root),
        "transport": "streamable-http",
        "host": config.host,
        "port": config.port,
        "endpoint": config.endpoint,
        "process": process,
        "protocol": None,
        "builder": None,
    }
    if process["state"] != "running":
        state = "conflict" if process["state"] == "conflict" else ("degraded" if process["state"] == "degraded" else "stopped")
        base.update(ok=False, state=state, next_action="Run 'kitty mcp up'." if state == "stopped" else "Resolve the MCP process/listener ownership problem.")
        return base

    try:
        protocol = asyncio.run(probe.probe_protocol(config.endpoint, call_context=False))
        tools = set(protocol.get("tools") or [])
        contract_ok = tools == probe.EXPECTED_TOOLS and probe.FORBIDDEN_TOOLS.isdisjoint(tools)
        base["protocol"] = {"initialized": bool(protocol.get("initialized")), "tool_count": len(tools), "contract_ok": contract_ok}
    except Exception as exc:
        base["protocol"] = {"initialized": False, "error": f"{type(exc).__name__}: {exc}"}
        base.update(ok=False, state="unavailable", next_action="Run 'kitty mcp doctor' to identify the protocol failure.")
        return base

    path = _builder_db_path()
    if path.exists():
        try:
            snapshot = builder_status_readonly.build_status_snapshot_readonly(db_path=path)
            base["builder"] = {"available": True, "queue_total": (snapshot.get("queue") or {}).get("total")}
        except Exception as exc:
            base["builder"] = {"available": False, "error": f"{type(exc).__name__}: {exc}"}
    else:
        base["builder"] = {"available": False, "reason": "database_missing"}

    if not base["protocol"].get("contract_ok"):
        base.update(ok=False, state="unavailable", next_action="Run 'kitty mcp doctor' to inspect the MCP tool contract mismatch.")
    elif not base["builder"].get("available"):
        base.update(ok=True, state="degraded", next_action="Apply an approved Builder Mission when durable execution state is needed.")
    else:
        base.update(ok=True, state="healthy", next_action="Start or continue the approved KPROOF Mission.")
    return base


async def doctor_report(config: OperatorConfig, *, publication_required: bool = False) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    blocked_by: str | None = None
    protocol_result: dict[str, Any] | None = None

    for boundary in BOUNDARY_ORDER:
        if blocked_by is not None:
            checks.append(_blocked(boundary, blocked_by))
            continue

        if boundary == "checkout":
            check = _check_checkout(config)
        elif boundary == "runtime":
            check = _check_runtime(config)
        elif boundary == "process":
            check = _check_process(config)
        elif boundary == "transport":
            try:
                protocol_result = await probe.probe_protocol(config.endpoint, call_context=True)
            except Exception as exc:
                check = _check(
                    "transport",
                    "fail",
                    f"MCP initialize/session failed: {type(exc).__name__}: {exc}",
                    next_action="Inspect logs/mcp.log and restart with 'kitty mcp down && kitty mcp up'.",
                    check_id="transport.initialize",
                )
            else:
                check = _check("transport", "pass", "MCP client initialized over Streamable HTTP.", evidence={"endpoint": config.endpoint}, check_id="transport.initialize")
        elif boundary == "contract":
            tools = set((protocol_result or {}).get("tools") or [])
            missing = sorted(probe.EXPECTED_TOOLS - tools)
            forbidden = sorted(probe.FORBIDDEN_TOOLS & tools)
            extra = sorted(tools - probe.EXPECTED_TOOLS)
            if missing or forbidden or extra:
                check = _check(
                    "contract",
                    "fail",
                    "MCP tool surface differs from the governed v1 contract.",
                    evidence={"missing": missing, "forbidden": forbidden, "extra": extra},
                    next_action="Restore the reviewed v1 tool surface before dogfooding.",
                    check_id="contract.tools",
                )
            else:
                check = _check("contract", "pass", "Governed v1 MCP tool surface is exact.", evidence={"tool_count": len(tools)}, check_id="contract.tools")
        elif boundary == "context":
            context = (protocol_result or {}).get("context")
            if not isinstance(context, dict):
                check = _check("context", "fail", "kitty_context returned no structured receipt.", next_action="Repair the MCP context tool/serialization boundary.")
            elif context.get("ok") is False:
                check = _check("context", "warn", "kitty_context truthfully reports attention is required.", evidence={"state": context.get("state"), "error_code": context.get("error_code")}, next_action=context.get("next_action") or "Resolve the cold-start context attention state.")
            else:
                check = _check("context", "pass", "kitty_context returned a structured usable receipt.", evidence={"state": context.get("state")})
        elif boundary == "builder":
            check = _check_builder(config)
        elif boundary == "repository":
            check = _check_repository(config)
        elif boundary == "github":
            check = _check_github(config, publication_required=publication_required)
        elif boundary == "provider":
            check = _check_provider(config)
        else:  # pragma: no cover - BOUNDARY_ORDER is closed above
            raise AssertionError(boundary)

        checks.append(check)
        if check["state"] == "fail":
            blocked_by = boundary

    summary = _summarize(checks)
    return {
        "operation": "mcp_doctor",
        "root": str(config.root),
        "endpoint": config.endpoint,
        "checks": checks,
        **summary,
    }
