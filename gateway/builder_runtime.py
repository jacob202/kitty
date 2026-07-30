"""Canonical Builder runtime snapshot with worker-session awareness.

Extends ``builder_status.build_status_snapshot()`` with live worker-session
and git-state projections. Every field is derived from existing queue, attempt,
run, and event authorities — no second database, no mutable UI-owned state.

KB-BRAIN-02: provides the read model that KB-BRAIN-03 (live events) and
KB-BRAIN-04 (cockpit) consume.
"""

from __future__ import annotations

import logging
import os
import sqlite3
import subprocess as _subprocess
import time
from pathlib import Path
from typing import Any

from gateway import builder_status
from gateway.builder_worker_session import WorkerState

logger = logging.getLogger("kitty.builder_runtime")

WORKER_STATE_MAP: dict[str, str] = {
    "starting": WorkerState.STARTING,
    "running": WorkerState.RUNNING,
    "idle": WorkerState.IDLE,
    "completed": WorkerState.COMPLETED,
    "cancelled": WorkerState.CANCELLED,
    "failed": WorkerState.FAILED,
    "disposed": WorkerState.DISPOSED,
}

SCHEMA_VERSION = 1


def build_runtime_snapshot(
    *,
    db_path: Path | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Produce an enhanced snapshot with worker-session and git state.

    Returns the same shape as ``build_status_snapshot`` with an additional
    ``worker_sessions`` key and enriched per-packet ``git_state`` and
    ``worker_session`` fields.

    Worker session state is inferred from the run table (PID, heartbeat,
    exit_code) and the task's lease. It does not require a live WorkerSession
    instance — it is a read-only projection usable by the runtime manifest
    and cockpit.
    """
    base = builder_status.build_status_snapshot(db_path=db_path)
    base["schema_version"] = max(base.get("schema_version", 0), SCHEMA_VERSION)

    root = Path(repo_root or Path.cwd()).resolve()
    git_state = _git_state(root)

    # Build a lookup of runs that are potentially alive.
    conn = _connect(db_path)
    try:
        active_runs = _fetch_active_runs(conn)
    finally:
        conn.close()

    for initiative in base.get("initiatives", []):
        for packet in initiative.get("packets", []):
            task_id = packet.get("task_id", "")
            run = packet.get("run") or {}

            # -- git state ---------------------------------------------------
            packet["git_state"] = {
                "branch": run.get("branch") or git_state.get("branch"),
                "worktree": run.get("worktree") or "",
                "head_sha": run.get("head_sha") or run.get("start_sha") or "",
                "dirty": _packet_dirty(task_id, root, run),
                "changed_paths": _safe_list(packet.get("changed_paths")),
                "base_sha": packet.get("base_sha") or "",
            }

            # Remove flat changed_paths if present — now under git_state.
            if "changed_paths" in packet:
                packet["git_state"]["changed_paths"] = _safe_list(
                    packet.pop("changed_paths")
                )

            # -- worker session ----------------------------------------------
            run_state = run.get("state", "")
            pid = run.get("pid")
            heartbeat = run.get("last_heartbeat_at")
            exit_code = run.get("exit_code")
            worker_state = _infer_worker_state(run_state, pid, exit_code, heartbeat)

            packet["worker_session"] = {
                "session_id": run.get("id", ""),
                "backend": "shell",
                "state": worker_state,
                "connected": worker_state in (WorkerState.RUNNING, WorkerState.IDLE),
                "model": run.get("model") or packet.get("model"),
                "provider": run.get("provider") or packet.get("provider"),
                "last_activity": _safe_isoformat(heartbeat),
                "pid": pid,
                "exit_code": exit_code,
                "started_at": run.get("started_at"),
            }

            # -- active runs enrichment --------------------------------------
            active = active_runs.get(task_id) if task_id else None
            if active:
                packet["worker_session"]["model"] = (
                    active.get("model") or packet["worker_session"]["model"]
                )
                packet["worker_session"]["provider"] = (
                    active.get("provider") or packet["worker_session"]["provider"]
                )

    base["worker_sessions"] = {
        "total": len(active_runs),
        "connected": sum(
            1 for r in active_runs.values()
            if r.get("state") in ("starting", "running")
        ),
    }
    base["generated_at"] = time.time()
    return base


def _connect(db_path: Path | None) -> sqlite3.Connection:
    path = Path(db_path) if db_path else Path("data/kittybuilder/builder_queue.db")
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def _fetch_active_runs(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    """Return runs whose state suggests the worker may still be alive."""
    try:
        rows = conn.execute(
            """
            SELECT task_id, id, state, model, provider, pid, last_heartbeat_at,
                   started_at
            FROM runs
            WHERE state IN ('starting', 'running')
            ORDER BY started_at DESC
            """
        ).fetchall()
    except sqlite3.OperationalError:
        return {}
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        task_id = str(row["task_id"])
        if task_id not in result:
            result[task_id] = {
                "id": str(row["id"]),
                "state": str(row["state"]),
                "model": row["model"],
                "provider": row["provider"],
                "pid": row["pid"],
                "last_heartbeat_at": row["last_heartbeat_at"],
                "started_at": row["started_at"],
            }
    return result


def _git_state(root: Path) -> dict[str, str | bool | int]:
    """Return canonical git state for the repository root."""
    try:
        branch = _subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout.strip()
    except Exception:
        branch = ""

    try:
        head = _subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout.strip()
    except Exception:
        head = ""

    try:
        status = _subprocess.run(
            ["git", "status", "--porcelain=v1", "--untracked-files=all"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=5,
        )
        dirty = bool(status.stdout.strip())
        changed_paths = len([l for l in status.stdout.splitlines() if l.strip()])
    except Exception:
        dirty = False
        changed_paths = 0

    return {
        "branch": branch,
        "head_sha": head,
        "dirty": dirty,
        "changed_paths": changed_paths,
    }


def _infer_worker_state(
    run_state: str,
    pid: int | None,
    exit_code: int | None,
    heartbeat: Any,
) -> str:
    """Infer WorkerState from run metadata without a live session."""
    if not run_state:
        return WorkerState.DISPOSED

    if run_state == "starting":
        return WorkerState.STARTING
    if run_state == "running":
        if pid is not None and _pid_alive(pid):
            return WorkerState.RUNNING
        return WorkerState.FAILED  # died without recording exit
    if run_state in ("exited", "completed"):
        return WorkerState.COMPLETED if exit_code == 0 else WorkerState.FAILED
    if run_state in ("cancelled", "cancel_requested"):
        return WorkerState.CANCELLED
    if run_state == "failed":
        return WorkerState.FAILED
    return WorkerState.DISPOSED


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _packet_dirty(
    task_id: str,
    root: Path,
    run: dict[str, Any],
) -> bool:
    """Check if a packet's worktree has uncommitted changes."""
    worktree = run.get("worktree")
    if not worktree:
        return False
    wt_path = Path(worktree)
    if not wt_path.is_dir():
        return False
    try:
        result = _subprocess.run(
            ["git", "status", "--porcelain=v1", "--untracked-files=all"],
            cwd=wt_path,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return bool(result.stdout.strip())
    except Exception:
        return False


def _safe_isoformat(value: Any) -> str | None:
    """Try to convert a value to an ISO timestamp string, or return None."""
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            pass
    return str(value) if value else None


def _safe_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in value]
    return []
