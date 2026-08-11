"""Typed operator command functions for cockpit controls (KB-BRAIN-05).

Every command:
- Accepts explicit actor, reason, and optional expected_version for optimism
- Returns a structured result with ok/error/audit_event_id
- Calls canonical gateway/Builder APIs — never bypasses the queue fencing
- Emits builder events for cockpit real-time updates
"""

from __future__ import annotations

import json
import logging
import shlex
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from gateway.builder_events import builder_events
from gateway.builder_initiative import (
    InitiativeNotFoundError,
    pause_initiative,
    resume_initiative,
)
from gateway.builder_queue import TaskNotFoundError as QueueTaskNotFoundError
from gateway.builder_queue import operator_cancel_task as _operator_cancel_task
from gateway.builder_queue_leases import operator_release_task
from gateway.models.builder import BuilderCommandRequest

REPO_ROOT = Path(__file__).resolve().parent.parent
KITTY_CLI = REPO_ROOT / "kitty"

logger = logging.getLogger("kitty.builder_commands")


class OperatorCommandError(ValueError):
    """An operator command could not complete (blocked, missing data, stale lease)."""


@dataclass
class CommandResult:
    ok: bool
    action: str
    task_id: str | None = None
    error: str | None = None
    detail: str | None = None
    event_id: int | None = None
    evidence: dict[str, Any] = field(default_factory=dict)


_COMMAND_ARGUMENTS: dict[str, frozenset[str]] = {
    "requeue": frozenset({"task_id", "actor", "reason"}),
    "cancel": frozenset({"task_id", "actor", "reason"}),
    "pause": frozenset({"initiative_id", "actor", "reason"}),
    "resume": frozenset({"initiative_id", "actor"}),
    "run_validation": frozenset({"task_id", "actor", "reason"}),
    "publish": frozenset({"task_id", "actor", "reason"}),
    "recover_stale": frozenset({"actor", "expected_version"}),
    "reconcile_merges": frozenset({"actor"}),
}


def dispatch_operator_command(request: BuilderCommandRequest) -> CommandResult:
    """Dispatch one validated Builder command through the canonical registry.

    The API routes used reflection to discover each handler's arguments. That
    made the boundary depend on private function signatures and silently
    discarded ``packet_id`` even though the UI sent it. Keep the accepted
    fields explicit here so command contracts are auditable and testable.
    """
    handler = COMMAND_HANDLERS.get(request.action)
    if handler is None:
        return CommandResult(
            ok=False,
            action=request.action,
            error=f"unknown action: {request.action}",
            evidence={"available": sorted(COMMAND_HANDLERS)},
        )

    task_id = request.task_id or request.packet_id
    values: dict[str, Any] = {
        "task_id": task_id,
        "initiative_id": request.initiative_id,
        "actor": request.actor or "cockpit-operator",
        "reason": request.reason,
        "expected_version": request.expected_version,
    }
    kwargs = {
        name: value
        for name, value in values.items()
        if name in _COMMAND_ARGUMENTS[request.action] and value is not None
    }
    return handler(**kwargs)


def command_result_payload(result: CommandResult) -> dict[str, Any]:
    """Serialize the shared command result for HTTP and compatibility adapters."""
    payload: dict[str, Any] = {
        "ok": result.ok,
        "action": result.action,
        "task_id": result.task_id,
        "error": result.error,
        "detail": result.detail,
        "event_id": result.event_id,
        "evidence": result.evidence,
    }
    available = result.evidence.get("available")
    if available is not None:
        payload["available"] = available
    return payload


def _emit_event(event_type: str, payload: dict[str, Any]) -> None:
    """Emit a queue event into the builder event stream for cockpit visibility."""
    builder_events.emit_queue_event(
        {"type": event_type, "payload": payload},
        task_id=payload.get("task_id", ""),
        packet_id=payload.get("packet_id", payload.get("task_id", "")),
    )


def _run_kitty(args: list[str], *, timeout: int = 120) -> str:
    proc = subprocess.run(
        [str(KITTY_CLI), "builder", *args],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()[:400] or "no output"
        raise OperatorCommandError(
            f"`kitty builder {' '.join(args)}` exited {proc.returncode}: {detail}"
        )
    return (proc.stdout or "").strip()


def command_requeue(
    task_id: str,
    *,
    actor: str,
    reason: str = "operator requeue from cockpit",
) -> CommandResult:
    try:
        result = operator_release_task(task_id, reason=reason)
    except QueueTaskNotFoundError:
        return CommandResult(
            ok=False,
            action="requeue",
            task_id=task_id,
            error=f"task not found: {task_id}",
        )
    except Exception as exc:
        logger.warning("requeue %s failed: %s", task_id, exc)
        return CommandResult(
            ok=False,
            action="requeue",
            task_id=task_id,
            error=str(exc),
        )

    _emit_event(
        "command_completed",
        {
            "command": "requeue",
            "task_id": task_id,
            "actor": actor,
            "reason": reason,
        },
    )
    return CommandResult(
        ok=True,
        action="requeue",
        task_id=task_id,
        detail=f"task {task_id} requeued",
        evidence={"new_state": result.get("state")},
    )


def command_cancel(
    task_id: str,
    *,
    actor: str,
    reason: str = "operator cancel from cockpit",
) -> CommandResult:
    try:
        result = _operator_cancel_task(
            task_id,
            reason=reason,
            actor=actor,
        )
    except QueueTaskNotFoundError:
        return CommandResult(
            ok=False,
            action="cancel",
            task_id=task_id,
            error=f"task not found: {task_id}",
        )
    except Exception as exc:
        logger.warning("cancel %s failed: %s", task_id, exc)
        return CommandResult(
            ok=False,
            action="cancel",
            task_id=task_id,
            error=str(exc),
        )

    _emit_event(
        "command_completed",
        {
            "command": "cancel",
            "task_id": task_id,
            "actor": actor,
            "reason": reason,
        },
    )
    return CommandResult(
        ok=True,
        action="cancel",
        task_id=task_id,
        detail=f"task {task_id} cancelled",
        evidence={"new_state": result.get("state")},
    )


def command_pause(
    initiative_id: str,
    *,
    actor: str,
    reason: str = "operator pause from cockpit",
) -> CommandResult:
    try:
        pause_initiative(initiative_id, reason=reason)
    except InitiativeNotFoundError:
        return CommandResult(
            ok=False,
            action="pause",
            error=f"initiative not found: {initiative_id}",
        )
    except Exception as exc:
        logger.warning("pause %s failed: %s", initiative_id, exc)
        return CommandResult(ok=False, action="pause", error=str(exc))

    _emit_event(
        "command_completed",
        {
            "command": "pause",
            "initiative_id": initiative_id,
            "actor": actor,
            "reason": reason,
        },
    )
    return CommandResult(
        ok=True,
        action="pause",
        detail=f"initiative {initiative_id} paused",
    )


def command_resume(
    initiative_id: str,
    *,
    actor: str,
) -> CommandResult:
    try:
        resume_initiative(initiative_id)
    except InitiativeNotFoundError:
        return CommandResult(
            ok=False,
            action="resume",
            error=f"initiative not found: {initiative_id}",
        )
    except Exception as exc:
        logger.warning("resume %s failed: %s", initiative_id, exc)
        return CommandResult(ok=False, action="resume", error=str(exc))

    _emit_event(
        "command_completed",
        {
            "command": "resume",
            "initiative_id": initiative_id,
            "actor": actor,
        },
    )
    return CommandResult(
        ok=True,
        action="resume",
        detail=f"initiative {initiative_id} resumed",
    )


def command_run_validation(
    task_id: str,
    *,
    actor: str,
    reason: str = "operator validation from cockpit",
) -> CommandResult:
    try:
        out = _run_kitty(
            ["queue", "show", task_id, "--json"],
            timeout=30,
        )
        task = json.loads(out)
    except (json.JSONDecodeError, OperatorCommandError):
        return CommandResult(
            ok=False,
            action="run_validation",
            task_id=task_id,
            error=f"could not read task {task_id}",
        )

    acceptance = task.get("acceptance_criteria") or []
    if not acceptance:
        return CommandResult(
            ok=False,
            action="run_validation",
            task_id=task_id,
            error=(
                "task has no acceptance criteria; validation requires a declared stop condition"
            ),
        )

    try:
        current_dir = Path.cwd()
        for cmd_text in acceptance:
            if not cmd_text or not cmd_text.strip():
                continue
            args = shlex.split(cmd_text)
            proc = subprocess.run(
                args,
                cwd=str(current_dir),
                capture_output=True,
                text=True,
                timeout=300,
            )
            if proc.returncode != 0:
                return CommandResult(
                    ok=False,
                    action="run_validation",
                    task_id=task_id,
                    error=(f"validation failed: {cmd_text[:120]} exited {proc.returncode}"),
                    evidence={
                        "failed_command": cmd_text[:500],
                        "stderr": proc.stderr[:500],
                    },
                )
    except Exception as exc:
        return CommandResult(
            ok=False,
            action="run_validation",
            task_id=task_id,
            error=str(exc),
        )

    _emit_event(
        "command_completed",
        {
            "command": "run_validation",
            "task_id": task_id,
            "actor": actor,
        },
    )
    return CommandResult(
        ok=True,
        action="run_validation",
        task_id=task_id,
        detail="validation passed all acceptance criteria",
    )


def command_publish(
    task_id: str,
    *,
    actor: str,
    reason: str = "operator publish from cockpit",
    remote: str = "origin",
) -> CommandResult:
    try:
        out = _run_kitty(
            ["queue", "publish", task_id, "--remote", remote, "--json"],
            timeout=60,
        )
        details = json.loads(out)
    except (json.JSONDecodeError, OperatorCommandError) as exc:
        return CommandResult(
            ok=False,
            action="publish",
            task_id=task_id,
            error=str(exc),
        )

    _emit_event(
        "command_completed",
        {
            "command": "publish",
            "task_id": task_id,
            "actor": actor,
            "reason": reason,
        },
    )
    return CommandResult(
        ok=True,
        action="publish",
        task_id=task_id,
        detail=f"task {task_id} published",
        evidence=details if isinstance(details, dict) else {},
    )


def command_recover_stale(
    *,
    actor: str,
    expected_version: int | None = None,
) -> CommandResult:
    try:
        out = _run_kitty(["queue", "recover", "--json"], timeout=60)
        details = json.loads(out)
    except (json.JSONDecodeError, OperatorCommandError) as exc:
        return CommandResult(ok=False, action="recover_stale", error=str(exc))

    _emit_event(
        "command_completed",
        {
            "command": "recover_stale",
            "actor": actor,
        },
    )
    return CommandResult(
        ok=True,
        action="recover_stale",
        detail=f"recovered {details.get('total', 0)} stale task(s)",
        evidence=details,
    )


def command_reconcile_merges(
    *,
    actor: str,
) -> CommandResult:
    """Promote tasks whose merged PR is not reflected in task state to done.

    The supported recovery for a task cancelled (or left non-terminal) in error:
    re-evaluate it against ground truth — its linked PR merged — instead of
    mutating queue rows by hand.
    """
    try:
        out = _run_kitty(["queue", "reconcile-merges", "--json"], timeout=60)
        details = json.loads(out)
    except (json.JSONDecodeError, OperatorCommandError) as exc:
        return CommandResult(ok=False, action="reconcile_merges", error=str(exc))

    _emit_event(
        "command_completed",
        {
            "command": "reconcile_merges",
            "actor": actor,
        },
    )
    return CommandResult(
        ok=True,
        action="reconcile_merges",
        detail=f"promoted {len(details.get('promoted', []))} merged task(s) to done",
        evidence=details,
    )


COMMAND_HANDLERS: dict[str, Any] = {
    "requeue": command_requeue,
    "cancel": command_cancel,
    "pause": command_pause,
    "resume": command_resume,
    "run_validation": command_run_validation,
    "publish": command_publish,
    "recover_stale": command_recover_stale,
    "reconcile_merges": command_reconcile_merges,
}
