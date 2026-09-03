from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncIterator, Mapping

from gateway.run_workspace import DiffSnapshot

from .adapters.codex import CodexAdapter
from .models import ProgressEvent
from .runner import SubprocessRunner, build_child_environment
from .runtime import CodexRuntime
from .workspace import GitWorktreeManager

logger = logging.getLogger(__name__)
_CANCELLATION_CLEANUP_TIMEOUT_SECONDS = 5


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
        try:
            worktree = self.workspace.create(run_id)
        except Exception as exc:
            yield ProgressEvent(
                kind="failed",
                code="worktree_create_failed",
                message=(
                    "Command Center could not create its disposable worktree: "
                    f"{type(exc).__name__}: {exc}"
                ),
            )
            return
        runtime = CodexRuntime(worktree, self.environment)
        exit_event: ProgressEvent | None = None
        runner_error: Exception | None = None
        worker_error: ProgressEvent | None = None
        final_answer: str | None = None
        cancelled = False
        runtime_cleanup_error: Exception | None = None

        try:
            runtime_path = runtime.prepare()
            child_env = build_child_environment(self.environment)
            child_env["HOME"] = str(runtime_path)
            child_env["CODEX_HOME"] = str(runtime_path)
            child_env["TMPDIR"] = str(runtime_path)
            child_env["CODEX_AUTH_FILE"] = str(runtime.auth_source)
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
                if event.kind == "process_error":
                    worker_error = event
                    continue
                message = _format_codex_progress(event.message)
                agent_answer = _extract_agent_answer(event.message)
                if agent_answer:
                    final_answer = agent_answer
                if message:
                    yield ProgressEvent(kind="progress", message=message)
        except asyncio.CancelledError:
            cancelled = True
            raise
        except Exception as exc:
            runner_error = exc
        finally:
            if cancelled:
                await self._best_effort_cancellation_cleanup(runtime, worktree)
            else:
                try:
                    runtime.cleanup()
                except Exception as exc:
                    runtime_cleanup_error = exc

        if runtime_cleanup_error is not None:
            yield ProgressEvent(
                kind="failed",
                code="runtime_cleanup_failed",
                message=(
                    "Command Center could not clean up its disposable runtime: "
                    f"{type(runtime_cleanup_error).__name__}: {runtime_cleanup_error}; "
                    "preserving worktree for inspection."
                ),
            )
            return

        try:
            audit = self.workspace.audit(worktree)
        except Exception as exc:
            yield ProgressEvent(
                kind="failed",
                code="audit_unavailable",
                message=(
                    "Command Center post-run read-only audit unavailable: "
                    f"{type(exc).__name__}: {exc}; preserving worktree for inspection."
                ),
            )
            return
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
            cleanup_event = self._remove_event(worktree, runner_error)
            if cleanup_event is not None:
                yield cleanup_event
                return
            yield ProgressEvent(
                kind="failed",
                code="runner_error",
                message=f"Command Center run failed: {type(runner_error).__name__}: {runner_error}",
            )
            return

        if worker_error is not None:
            cleanup_event = self._remove_event(worktree, worker_error)
            if cleanup_event is not None:
                yield cleanup_event
                return
            yield ProgressEvent(
                kind="failed",
                code=worker_error.code or "worker_error",
                message=f"Codex reported an error: {_format_codex_progress(worker_error.message) or worker_error.message}",
            )
            return

        if exit_event is None or exit_event.exit_code != 0:
            code = exit_event.code if exit_event else "missing_exit_status"
            detail = exit_event.message if exit_event else "worker ended without exit evidence"
            cleanup_event = self._remove_event(worktree, RuntimeError(detail))
            if cleanup_event is not None:
                yield cleanup_event
                return
            yield ProgressEvent(kind="failed", code=code, message=detail)
            return

        cleanup_event = self._remove_event(worktree)
        if cleanup_event is not None:
            yield cleanup_event
            return
        yield ProgressEvent(
            kind="done",
            message="Codex completed; read-only diff audit clean.",
            answer=final_answer,
        )

    def _remove_event(
        self, worktree, prior_error: Exception | ProgressEvent | None = None
    ) -> ProgressEvent | None:
        try:
            self.workspace.remove(worktree)
        except Exception as exc:
            prior = (
                f" after {type(prior_error).__name__}: {prior_error}"
                if prior_error is not None
                else ""
            )
            return ProgressEvent(
                kind="failed",
                code="worktree_cleanup_failed",
                message=(
                    "Command Center could not confirm disposable worktree cleanup"
                    f"{prior}: {type(exc).__name__}: {exc}; preserving worktree for inspection."
                ),
            )
        return None

    async def _best_effort_cancellation_cleanup(self, runtime, worktree) -> None:
        runtime_cleanup_succeeded, _ = await self._bounded_cleanup_call(
            "runtime cleanup", runtime.cleanup
        )
        if not runtime_cleanup_succeeded:
            return
        audit_succeeded, audit = await self._bounded_cleanup_call(
            "cancellation audit", self.workspace.audit, worktree
        )
        if audit_succeeded and isinstance(audit, DiffSnapshot) and not audit.dirty:
            await self._bounded_cleanup_call(
                "cancellation worktree removal", self.workspace.remove, worktree
            )

    async def _bounded_cleanup_call(self, label, function, *args) -> tuple[bool, object]:
        try:
            result = await asyncio.wait_for(
                asyncio.shield(asyncio.to_thread(function, *args)),
                timeout=_CANCELLATION_CLEANUP_TIMEOUT_SECONDS,
            )
            return True, result
        except BaseException as exc:
            logger.warning("best-effort %s failed: %s: %s", label, type(exc).__name__, exc)
            return False, None


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
            return _extract_agent_answer(line)
        if item_type == "command_execution":
            return "Inspecting repository…"
    if event_type in {"error", "turn.failed"}:
        message = payload.get("message") or payload.get("error") or payload
        return f"Codex error: {message}"
    return None


def _extract_agent_answer(line: str) -> str | None:
    try:
        payload = json.loads(line)
    except json.JSONDecodeError:
        return None
    if payload.get("type") != "item.completed":
        return None
    item = payload.get("item") or {}
    if item.get("type") != "agent_message":
        return None
    return str(item.get("text") or "").strip() or None
