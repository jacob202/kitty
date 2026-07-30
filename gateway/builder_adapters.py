"""Worker-session adapters for KittyBuilder.

``ShellWorkerSession`` wraps the existing subprocess-based ``run_worker``
from ``builder_runner`` as a ``WorkerSession`` implementation. It preserves
every earned behavior from ``scripts/kittybuilder_opencode_worker.sh`` while
exposing the backend-neutral contract.

``OpenCodeServerSession`` speaks HTTP to an OpenCode headless server,
implementing the same ``WorkerSession`` interface. It is the first
production adapter per KB-BRAIN-01's harvest decision.
"""

from __future__ import annotations

import logging
import os
import signal
import time
from pathlib import Path
from typing import Any

import httpx

from gateway.builder_worker_session import (
    ModelPolicy,
    SessionIdentity,
    WorkerEvent,
    WorkerEventType,
    WorkerSession,
    WorkerSessionError,
    WorkerSessionNotFoundError,
    WorkerSnapshot,
    WorkerState,
)

logger = logging.getLogger("kitty.builder_adapters")


# ---------------------------------------------------------------------------
# ShellWorkerSession — wraps the existing subprocess runner
# ---------------------------------------------------------------------------


class ShellWorkerSession(WorkerSession):
    """Delegate to the subprocess-based ``run_worker`` from ``builder_runner``.

    This adapter does not reimplement the free-model ladder, fingerprint
    checking, or commit-on-behalf logic — those live in
    ``scripts/kittybuilder_opencode_worker.sh``, which is the ``command``
    passed to ``run_worker``. The adapter surfaces the run's metadata through
    the ``WorkerSession`` contract so the loop and cockpit see a consistent
    shape regardless of backend.
    """

    def __init__(self, command: list[str], *, task_id: str = "") -> None:
        if not command:
            raise ValueError("command must be a non-empty list")
        self._command = list(command)
        self._task_id = task_id
        self._runs: dict[str, dict[str, Any]] = {}  # session_id → run dict
        self._pids: dict[str, int] = {}
        self._cancelled: set[str] = set()
        self._disposed: set[str] = set()

    # -- WorkerSession -------------------------------------------------------

    def start(
        self,
        worktree: Path,
        brief: str,
        model_policy: ModelPolicy | None = None,
        *,
        packet_id: str = "",
        attempt_id: str = "",
    ) -> SessionIdentity:
        from gateway.builder_runner import run_worker

        task_id = self._task_id
        run = run_worker(
            task_id,
            self._command,
            worker="shell-adapter",
            model=model_policy.model if model_policy else None,
            provider=model_policy.provider if model_policy else None,
            repo_root=worktree.parent,
        )
        session_id = str(run["id"])
        identity = SessionIdentity(session_id=session_id, backend="shell")
        self._runs[session_id] = run
        pid = run.get("pid")
        if pid is not None:
            self._pids[session_id] = int(pid)
        return identity

    def resume(self, identity: SessionIdentity) -> SessionIdentity:
        if identity.session_id not in self._runs:
            raise WorkerSessionNotFoundError(
                f"shell session {identity.session_id} not found — "
                "subprocess sessions cannot be resumed after disposal"
            )
        return identity

    def send_instruction(self, identity: SessionIdentity, text: str) -> None:
        # Subprocess workers receive a single prompt via stdin/args at
        # launch time. Sending follow-up instructions is not supported.
        logger.warning(
            "ShellWorkerSession does not support send_instruction for %s",
            identity.session_id,
        )

    def events(
        self,
        identity: SessionIdentity,
        *,
        cursor: int | None = None,
    ) -> list[WorkerEvent]:
        run = self._runs.get(identity.session_id)
        if run is None:
            raise WorkerSessionNotFoundError(
                f"shell session {identity.session_id} not found"
            )
        log_path_str = run.get("log_path")
        if not log_path_str:
            return []

        log_path = Path(log_path_str)
        if not log_path.is_file():
            return []

        events: list[WorkerEvent] = []
        seq = cursor or 0

        try:
            lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as exc:
            logger.warning("cannot read log for %s: %s", identity.session_id, exc)
            return []

        start_line = max(cursor or 0, 0)
        if start_line >= len(lines):
            return []

        for idx, line in enumerate(lines[start_line:], start=start_line):
            seq += 1
            events.append(
                WorkerEvent(
                    event_id=f"shell:{identity.session_id}:{idx}",
                    seq=seq,
                    timestamp=time.time(),
                    session_id=identity.session_id,
                    type=WorkerEventType.TEXT_DELTA,
                    data={"line": line, "line_no": idx},
                    raw_payload=line,
                )
            )

        # Terminal event derived from run outcome, not log content.
        outcome = run.get("final_report", {}).get("outcome", "")
        exit_code = run.get("exit_code")
        if exit_code is not None:
            seq += 1
            if outcome == "cancelled" or identity.session_id in self._cancelled:
                events.append(
                    WorkerEvent(
                        event_id=f"shell:{identity.session_id}:cancelled",
                        seq=seq,
                        timestamp=time.time(),
                        session_id=identity.session_id,
                        type=WorkerEventType.CANCELLED,
                        data={"reason": outcome if outcome == "cancelled" else "session cancelled"},
                    )
                )
            elif exit_code == 0:
                events.append(
                    WorkerEvent(
                        event_id=f"shell:{identity.session_id}:message_complete",
                        seq=seq,
                        timestamp=time.time(),
                        session_id=identity.session_id,
                        type=WorkerEventType.MESSAGE_COMPLETE,
                        data={"summary": run.get("final_report", {}).get("summary", "")},
                    )
                )
            else:
                events.append(
                    WorkerEvent(
                        event_id=f"shell:{identity.session_id}:error",
                        seq=seq,
                        timestamp=time.time(),
                        session_id=identity.session_id,
                        type=WorkerEventType.ERROR,
                        data={
                            "exit_code": exit_code,
                            "error": run.get("final_report", {}).get("error", ""),
                        },
                    )
                )

        if identity.session_id in self._disposed:
            seq += 1
            events.append(
                WorkerEvent(
                    event_id=f"shell:{identity.session_id}:disposed",
                    seq=seq,
                    timestamp=time.time(),
                    session_id=identity.session_id,
                    type=WorkerEventType.SESSION_ENDED,
                    data={},
                )
            )

        return events

    def snapshot(self, identity: SessionIdentity) -> WorkerSnapshot:
        run = self._runs.get(identity.session_id)
        if run is None:
            return WorkerSnapshot(
                session_id=identity.session_id,
                state=WorkerState.DISPOSED,
                error="session not found (already disposed or never started)",
            )

        outcome = run.get("final_report", {}).get("outcome", "")
        if identity.session_id in self._disposed:
            state = WorkerState.DISPOSED
        elif identity.session_id in self._cancelled:
            state = WorkerState.CANCELLED
        elif outcome == "cancelled":
            state = WorkerState.CANCELLED
        elif run.get("exit_code") is not None:
            state = (
                WorkerState.COMPLETED
                if run["exit_code"] == 0
                else WorkerState.FAILED
            )
        else:
            state = WorkerState.RUNNING

        report = run.get("final_report", {})
        return WorkerSnapshot(
            session_id=identity.session_id,
            packet_id=run.get("packet_id", ""),
            attempt_id=run.get("attempt_id", ""),
            state=state,
            model=report.get("model") or run.get("model"),
            provider=report.get("provider") or run.get("provider"),
            changed_paths=list(report.get("changed_paths", [])),
            scope_violations=list(report.get("scope_violations", [])),
            error=report.get("error"),
            metadata={
                "exit_code": run.get("exit_code"),
                "branch": report.get("branch"),
                "worktree": report.get("worktree"),
                "command": run.get("command"),
                "worker_started": report.get("worker_started"),
            },
        )

    def cancel(self, identity: SessionIdentity, *, reason: str = "") -> None:
        self._cancelled.add(identity.session_id)
        pid = self._pids.get(identity.session_id)
        if pid is None:
            return
        try:
            os.killpg(pid, signal.SIGTERM)
        except (ProcessLookupError, OSError) as exc:
            logger.debug(
                "ShellWorkerSession cancel for %s: process group %s: %s",
                identity.session_id,
                pid,
                exc,
            )

    def transcript(self, identity: SessionIdentity) -> Path | None:
        run = self._runs.get(identity.session_id)
        if run is None:
            return None
        log_path_str = run.get("log_path")
        if not log_path_str:
            return None
        path = Path(log_path_str)
        return path if path.is_file() else None

    def dispose(self, identity: SessionIdentity) -> None:
        self._disposed.add(identity.session_id)

    def is_alive(self, identity: SessionIdentity) -> bool:
        if identity.session_id in self._disposed:
            return False
        pid = self._pids.get(identity.session_id)
        if pid is None:
            return False
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


# ---------------------------------------------------------------------------
# OpenCodeServerSession — HTTP adapter for OpenCode headless server
# ---------------------------------------------------------------------------


class OpenCodeServerSession(WorkerSession):
    """Speak HTTP to an OpenCode headless server.

    The OpenCode server exposes session creation, instruction delivery,
    event streaming, and cancellation via HTTP. This adapter normalises
    those into the ``WorkerSession`` contract.

    Server API reference (pinned at OpenCode commit in the harvest):
      - POST /session         — create a new session
      - GET  /session/:id     — get session state
      - POST /session/:id/prompt  — send instruction
      - GET  /event           — event stream
      - POST /session/:id/cancel   — cancel session
      - DELETE /session/:id   — dispose
    """

    def __init__(
        self,
        base_url: str,
        *,
        api_key: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        headers: dict[str, str] = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self._client = httpx.Client(base_url=self._base_url, headers=headers, timeout=timeout)
        self._sessions: dict[str, dict[str, Any]] = {}
        self._event_buffers: dict[str, list[WorkerEvent]] = {}
        self._cancelled: set[str] = set()
        self._disposed: set[str] = set()

    # -- WorkerSession -------------------------------------------------------

    def start(
        self,
        worktree: Path,
        brief: str,
        model_policy: ModelPolicy | None = None,
        *,
        packet_id: str = "",
        attempt_id: str = "",
    ) -> SessionIdentity:
        payload: dict[str, Any] = {
            "cwd": str(worktree),
            "prompt": brief,
        }
        if model_policy:
            if model_policy.model:
                payload["model"] = model_policy.model
            if model_policy.provider:
                payload["provider"] = model_policy.provider

        try:
            resp = self._client.post("/session", json=payload)
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as exc:
            raise WorkerSessionError(
                f"OpenCode session creation failed: {exc}"
            ) from exc

        session_id = str(data.get("id", ""))
        if not session_id:
            raise WorkerSessionError("OpenCode server returned a session with no id")

        identity = SessionIdentity(session_id=session_id, backend="opencode")
        self._sessions[session_id] = data
        self._event_buffers[session_id] = []
        return identity

    def resume(self, identity: SessionIdentity) -> SessionIdentity:
        session_id = identity.session_id
        if session_id in self._disposed:
            raise WorkerSessionNotFoundError(
                f"OpenCode session {session_id} was disposed"
            )
        try:
            resp = self._client.get(f"/session/{session_id}")
            if resp.status_code == 404:
                raise WorkerSessionNotFoundError(
                    f"OpenCode session {session_id} not found on server"
                )
            resp.raise_for_status()
            self._sessions[session_id] = resp.json()
        except httpx.HTTPError as exc:
            raise WorkerSessionError(
                f"OpenCode session resume failed for {session_id}: {exc}"
            ) from exc
        return identity

    def send_instruction(self, identity: SessionIdentity, text: str) -> None:
        if identity.session_id in self._disposed:
            raise WorkerSessionNotFoundError(
                f"OpenCode session {identity.session_id} was disposed"
            )
        try:
            resp = self._client.post(
                f"/session/{identity.session_id}/prompt",
                json={"prompt": text},
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise WorkerSessionError(
                f"OpenCode instruction delivery failed: {exc}"
            ) from exc

    def events(
        self,
        identity: SessionIdentity,
        *,
        cursor: int | None = None,
    ) -> list[WorkerEvent]:
        if identity.session_id in self._disposed:
            return []

        # Fetch new events from the server if we don't have them buffered.
        try:
            params: dict[str, str] = {}
            if cursor is not None:
                params["cursor"] = str(cursor)
            resp = self._client.get("/event", params=params)
            resp.raise_for_status()
            raw_events = resp.json() if resp.content else []
        except httpx.HTTPError as exc:
            logger.warning(
                "OpenCode event fetch failed for %s: %s",
                identity.session_id,
                exc,
            )
            return []

        buffer = self._event_buffers.get(identity.session_id, [])
        if not isinstance(raw_events, list):
            raw_events = []

        parsed = _parse_opencode_events(
            raw_events,
            session_id=identity.session_id,
            start_seq=len(buffer) + (cursor or 0),
        )
        buffer.extend(parsed)

        # Apply cursor filter.
        if cursor is not None:
            return [e for e in buffer if e.seq >= cursor]
        return list(buffer)

    def snapshot(self, identity: SessionIdentity) -> WorkerSnapshot:
        session_id = identity.session_id
        if session_id in self._disposed:
            return WorkerSnapshot(
                session_id=session_id,
                state=WorkerState.DISPOSED,
            )

        data = self._sessions.get(session_id, {})
        status = data.get("status", "")
        state: WorkerState
        if session_id in self._cancelled:
            state = WorkerState.CANCELLED
        elif status == "completed":
            state = WorkerState.COMPLETED
        elif status == "error":
            state = WorkerState.FAILED
        elif status == "idle":
            state = WorkerState.IDLE
        elif status == "running":
            state = WorkerState.RUNNING
        else:
            state = WorkerState.STARTING

        buffer = self._event_buffers.get(session_id, [])
        return WorkerSnapshot(
            session_id=session_id,
            state=state,
            model=data.get("model"),
            provider=data.get("provider"),
            events_count=len(buffer),
            last_activity=buffer[-1].timestamp if buffer else 0.0,
            error=data.get("error"),
            metadata={
                "server_data": data,
            },
        )

    def cancel(self, identity: SessionIdentity, *, reason: str = "") -> None:
        session_id = identity.session_id
        self._cancelled.add(session_id)
        try:
            payload = {"reason": reason} if reason else {}
            resp = self._client.post(f"/session/{session_id}/cancel", json=payload)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning(
                "OpenCode cancel failed for %s: %s", session_id, exc
            )

    def transcript(self, identity: SessionIdentity) -> Path | None:
        # OpenCode server does not persist a local transcript — the event
        # stream is the canonical record.
        return None

    def dispose(self, identity: SessionIdentity) -> None:
        session_id = identity.session_id
        self._disposed.add(session_id)
        try:
            self._client.delete(f"/session/{session_id}")
        except httpx.HTTPError as exc:
            logger.debug(
                "OpenCode dispose for %s: %s", session_id, exc
            )
        self._sessions.pop(session_id, None)
        self._event_buffers.pop(session_id, None)

    def is_alive(self, identity: SessionIdentity) -> bool:
        if identity.session_id in self._disposed:
            return False
        try:
            resp = self._client.get(f"/session/{identity.session_id}")
            if resp.status_code == 404:
                return False
            resp.raise_for_status()
            return True
        except httpx.HTTPError:
            return False


# ---------------------------------------------------------------------------
# Event parsing helpers
# ---------------------------------------------------------------------------


def _parse_opencode_events(
    raw_events: list[dict[str, Any]],
    *,
    session_id: str,
    start_seq: int = 0,
) -> list[WorkerEvent]:
    """Normalise OpenCode server events into WorkerEvent stream."""
    parsed: list[WorkerEvent] = []
    for idx, raw in enumerate(raw_events):
        event_id = str(raw.get("id", f"opencode:{session_id}:{idx}"))
        event_type_raw = raw.get("type", "")
        event_type = _map_opencode_event_type(event_type_raw)
        parsed.append(
            WorkerEvent(
                event_id=event_id,
                seq=start_seq + idx,
                timestamp=raw.get("timestamp", time.time()),
                session_id=session_id,
                type=event_type,
                data=_extract_event_data(raw),
                raw_payload=raw,
            )
        )
    return parsed


_OPENCODE_EVENT_MAP: dict[str, WorkerEventType] = {
    "session.started": WorkerEventType.SESSION_STARTED,
    "session.resumed": WorkerEventType.SESSION_RESUMED,
    "assistant.message.delta": WorkerEventType.TEXT_DELTA,
    "assistant.message.completed": WorkerEventType.MESSAGE_COMPLETE,
    "tool.start": WorkerEventType.TOOL_START,
    "tool.end": WorkerEventType.TOOL_END,
    "command.start": WorkerEventType.COMMAND_START,
    "command.end": WorkerEventType.COMMAND_END,
    "file.change": WorkerEventType.FILE_CHANGE,
    "commit": WorkerEventType.COMMIT,
    "model.change": WorkerEventType.MODEL_SWITCH,
    "usage": WorkerEventType.USAGE,
    "attention.request": WorkerEventType.ATTENTION_REQUEST,
    "permission.request": WorkerEventType.PERMISSION_REQUEST,
    "heartbeat": WorkerEventType.HEARTBEAT,
    "idle": WorkerEventType.IDLE,
    "error": WorkerEventType.ERROR,
    "session.cancelled": WorkerEventType.CANCELLED,
    "session.completed": WorkerEventType.SESSION_ENDED,
}


def _map_opencode_event_type(raw_type: str) -> WorkerEventType:
    return _OPENCODE_EVENT_MAP.get(raw_type, WorkerEventType.RAW)


def _extract_event_data(raw: dict[str, Any]) -> dict[str, Any]:
    """Extract the subset of an OpenCode event that Kitty cares about."""
    data: dict[str, Any] = {}
    for key in (
        "text",
        "delta",
        "message",
        "tool",
        "command",
        "path",
        "model",
        "provider",
        "tokens",
        "exit_code",
        "error",
        "reason",
    ):
        if key in raw:
            data[key] = raw[key]
    return data
