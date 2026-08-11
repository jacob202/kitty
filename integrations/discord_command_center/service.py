from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator, Mapping

from .adapters.codex import CodexAdapter
from .models import ProgressEvent
from .runner import SubprocessRunner, build_child_environment
from .runtime import CodexRuntime
from .workspace import GitWorktreeManager


class VibeService:
    def __init__(
        self,
        *,
        workspace: GitWorktreeManager,
        adapter: CodexAdapter,
        runner: SubprocessRunner,
        timeout_seconds: int,
        environment: Mapping[str, str],
    ) -> None:
        self.workspace = workspace
        self.adapter = adapter
        self.runner = runner
        self.timeout_seconds = timeout_seconds
        self.environment = dict(environment)

    async def run(self, request: str) -> AsyncIterator[ProgressEvent]:
        run_id = f"cc-{uuid.uuid4().hex[:12]}"
        worktree = self.workspace.create(run_id)
        runtime = CodexRuntime(worktree, self.environment)
        exit_event: ProgressEvent | None = None
        runner_error: Exception | None = None
        cancelled = False

        try:
            runtime_path = runtime.prepare()
            child_env = build_child_environment(self.environment)
            child_env["HOME"] = str(runtime_path)
            child_env["CODEX_HOME"] = str(runtime_path)
            child_env["TMPDIR"] = str(runtime_path)
            child_env.pop("TMP", None)
            child_env.pop("TEMP", None)
            command = self.adapter.command(request, worktree)

            async for event in self.runner.stream(
                command,
                cwd=worktree,
                environment=child_env,
                timeout_seconds=self.timeout_seconds,
            ):
                if event.kind == "process_exit":
                    exit_event = event
                    continue
                message = _format_codex_progress(event.message)
                if message:
                    yield ProgressEvent(kind="progress", message=message)
        except asyncio.CancelledError:
            cancelled = True
            raise
        except Exception as exc:
            runner_error = exc
        finally:
            runtime.cleanup()
            if cancelled:
                audit = self.workspace.audit(worktree)
                if not audit.dirty:
                    self.workspace.remove(worktree)

        audit = self.workspace.audit(worktree)
        if audit.dirty:
            detail = ""
            if runner_error is not None:
                detail = f" while the worker also failed ({type(runner_error).__name__}: {runner_error})"
            yield ProgressEvent(
                kind="failed",
                code="readonly_violation",
                message=(
                    "READ-ONLY VIOLATION: repository mutation detected"
                    f"{detail}; preserving worktree for inspection ({audit.files} changed files)."
                ),
            )
            return

        if runner_error is not None:
            self.workspace.remove(worktree)
            yield ProgressEvent(
                kind="failed",
                code="runner_error",
                message=f"Command Center run failed: {type(runner_error).__name__}: {runner_error}",
            )
            return

        if exit_event is None or exit_event.exit_code != 0:
            code = exit_event.code if exit_event else "missing_exit_status"
            detail = exit_event.message if exit_event else "worker ended without exit evidence"
            self.workspace.remove(worktree)
            yield ProgressEvent(kind="failed", code=code, message=detail)
            return

        self.workspace.remove(worktree)
        yield ProgressEvent(kind="done", message="Codex completed; read-only diff audit clean.")


def _format_codex_progress(line: str) -> str | None:
    if not line:
        return None
    try:
        payload = json.loads(line)
    except json.JSONDecodeError:
        return "Codex is working…"

    event_type = payload.get("type")
    if event_type == "item.completed":
        item = payload.get("item") or {}
        item_type = item.get("type")
        if item_type == "agent_message":
            return str(item.get("text") or "").strip() or None
        if item_type == "command_execution":
            return "Inspecting repository…"
    if event_type in {"error", "turn.failed"}:
        message = payload.get("message") or payload.get("error") or payload
        return f"Codex error: {message}"
    return None
