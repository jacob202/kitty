"""KittyBuilder KB-S3b — bounded per-packet repair loop.

Drives one packet through implement → validate → review → repair using only
existing machinery: attempts (KB-S2), deterministic validation (KB-S3a), and
the shadow runner. Each attempt is a real ``run_worker`` execution in the
task's isolated worktree; the loop is bounded by ``policy.max_attempts``
(enforced by ``start_attempt``).

Contract wiring: the worker command receives KB_ATTEMPT_ID, KB_BUNDLE_PATH
(the persisted context bundle as JSON), KB_RESULT_PATH, and
KB_CONTEXT_MANIFEST_PATH; it must write an implementation-result contract to
KB_RESULT_PATH. The optional review command runs afterwards as a plain
subprocess in the same worktree with KB_REVIEW_RESULT_PATH and
KB_CONTEXT_MANIFEST_PATH added, and must write a review-result contract there.
Missing or invalid contracts fail the attempt — fail loud, never invent data.

Attempt verdict: success requires implementation status ``completed``,
validation not ``failed``, and (when a review command is configured) review
verdict ``approve``. Anything else closes the attempt ``failed`` and the loop
retries until the attempt budget is exhausted.

Scope boundaries: shadow mode throughout — no push, no PR, no GitHub
mutation (KB-S4). Every run leaves the task ``blocked`` per the runner; the
loop releases it back to ``queued`` between retries via the existing
operator-release path and leaves the final state for the operator/KB-S4.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any

from gateway import builder_attempt as ba
from gateway import builder_queue as bq
from gateway.builder_context import build_context_manifest, write_run_manifest
from gateway.builder_runner import remove_worktree, run_worker, worktree_path
from gateway.paths import BUILDER_QUEUE_DB

DEFAULT_REVIEW_TIMEOUT = 1800

LOOP_SUCCEEDED = "succeeded"
LOOP_EXHAUSTED = "exhausted"


class LoopError(RuntimeError):
    """Raised when the packet loop cannot proceed at all."""


def _attempt_dir(task_id: str, attempt_id: int, db_path: Path | None) -> Path:
    queue_db = Path(db_path) if db_path is not None else BUILDER_QUEUE_DB
    # Scope artifacts by task as well as numeric attempt ID. Test runs and
    # concurrent initiatives can otherwise reuse attempt 1 and overwrite a
    # different packet's bundle before its reviewer reads it.
    return queue_db.parent / "attempts" / task_id / str(attempt_id)


def _command_digest(command: list[str]) -> str:
    encoded = json.dumps(command, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _text_evidence(value: str) -> dict[str, int | str]:
    """Record proof of text without copying potentially sensitive contents."""
    encoded = value.encode("utf-8", errors="replace")
    return {"sha256": hashlib.sha256(encoded).hexdigest(), "length": len(value)}


def _validation_evidence(validation: dict[str, Any]) -> dict[str, Any]:
    """Keep validation status and metadata while excluding command output."""
    commands = []
    for result in validation.get("commands", []):
        output = str(result.get("output_tail", ""))
        commands.append(
            {
                "command_sha256": _command_digest([str(result.get("command", ""))]),
                "exit_code": result.get("exit_code"),
                "passed": result.get("passed"),
                "duration_s": result.get("duration_s"),
                "output": _text_evidence(output),
            }
        )
    return {"status": validation.get("status"), "commands": commands}


def _review_evidence(review: dict[str, Any]) -> dict[str, Any]:
    """Keep review decisions and finding severities without raw prose."""
    return {
        "verdict": review.get("verdict"),
        "summary": _text_evidence(str(review.get("summary", ""))),
        "finding_severities": [
            finding.get("severity")
            for finding in review.get("findings", [])
            if isinstance(finding, dict)
        ],
    }


def _read_contract(path: Path, kind: str) -> tuple[dict[str, Any] | None, str | None]:
    """Read a contract file. Returns (contract, error)."""
    if not path.is_file():
        return None, f"worker did not write a {kind} result to {path}"
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"{kind} result unreadable: {exc}"
    if not isinstance(parsed, dict):
        return None, f"{kind} result must be a JSON object"
    return parsed, None


def _run_review_command(
    command: list[str],
    *,
    cwd: Path,
    env_extra: dict[str, str],
    timeout_seconds: int,
) -> str | None:
    """Run the reviewer subprocess. Returns an error string or None."""
    env = dict(os.environ)
    env.pop("GITHUB_TOKEN", None)
    env.pop("GH_TOKEN", None)
    env.update(env_extra)
    try:
        proc = subprocess.run(
            command,
            cwd=str(cwd),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        return f"review command timed out after {timeout_seconds}s"
    except OSError as exc:
        return f"review command failed to launch: {exc}"
    if proc.returncode != 0:
        tail = ((proc.stdout or "") + (proc.stderr or ""))[-2000:]
        return f"review command exited {proc.returncode}: {tail}"
    return None


def run_packet(
    initiative_id: str,
    packet_id: str,
    *,
    worker_command: list[str],
    review_command: list[str] | None = None,
    worker: str = "packet-loop",
    model: str | None = None,
    provider: str | None = None,
    timeout_seconds: int = 3600,
    validation_timeout_seconds: int = ba.DEFAULT_VALIDATION_TIMEOUT,
    review_timeout_seconds: int = DEFAULT_REVIEW_TIMEOUT,
    repo_root: Path | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Run the bounded repair loop for one packet.

    Returns ``{"outcome": "succeeded"|"exhausted", "attempts": [...]}`` where
    each attempt entry records what happened and why. Raises LoopError when
    the packet/task cannot be driven at all (wrong task state at entry).
    """
    if not worker_command:
        raise LoopError("worker_command must be a non-empty list")

    ba.init_db(db_path)
    bundle_preview = ba.build_context_bundle(initiative_id, packet_id, db_path=db_path)
    task_id = bundle_preview["task_id"]

    task = bq.get_task(task_id, db_path=db_path)
    if task is None or task["state"] != bq.QUEUED:
        state = task["state"] if task else "missing"
        raise LoopError(
            f"task {task_id} for {initiative_id}/{packet_id} is {state}; "
            "the loop only starts on a queued task"
        )

    history: list[dict[str, Any]] = []
    while True:
        try:
            attempt = ba.start_attempt(initiative_id, packet_id, db_path=db_path)
        except ba.AttemptLimitError as exc:
            return {
                "outcome": LOOP_EXHAUSTED,
                "initiative_id": initiative_id,
                "packet_id": packet_id,
                "task_id": task_id,
                "reason": str(exc),
                "attempts": history,
            }

        # A prior failed attempt's shadow run left the task blocked; hand it
        # back to queued only now that the next attempt is secured, so budget
        # exhaustion leaves the task blocked for the operator.
        if attempt["attempt_no"] > 1:
            task = bq.get_task(task_id, db_path=db_path)
            if task is not None and task["state"] == bq.BLOCKED:
                bq.operator_release_task(
                    task_id,
                    reason=f"repair_loop_retry attempt {attempt['attempt_no']}",
                    db_path=db_path,
                )
            elif task is None or task["state"] != bq.QUEUED:
                raise LoopError(
                    f"task {task_id} is {task['state'] if task else 'missing'} "
                    "before retry; expected blocked or queued — not retrying"
                )

        attempt_id = attempt["id"]
        entry: dict[str, Any] = {"attempt_id": attempt_id, "attempt_no": attempt["attempt_no"]}
        history.append(entry)

        attempt_dir = _attempt_dir(task_id, attempt_id, db_path)
        attempt_dir.mkdir(parents=True, exist_ok=True)
        bundle_path = attempt_dir / "bundle.json"
        result_path = attempt_dir / "implementation.json"
        review_path = attempt_dir / "review.json"
        manifest_path = attempt_dir / "run-manifest.json"
        bundle_path.write_text(
            json.dumps(attempt["bundle"], indent=2), encoding="utf-8"
        )
        manifest = {
            "initiative_id": initiative_id,
            "packet_id": packet_id,
            "task_id": task_id,
            "attempt_id": attempt_id,
            "attempt_no": attempt["attempt_no"],
            "worker": worker,
            "model": model,
            "provider": provider,
            "command_sha256": _command_digest(worker_command),
            "artifact_dir": str(attempt_dir),
            "bundle_sha256": hashlib.sha256(bundle_path.read_bytes()).hexdigest(),
            "context": build_context_manifest(
                Path(repo_root or Path.cwd()), bundle_path
            ),
            "worker_run": None,
            "validation": None,
            "review": None,
            "outcome": "running",
            "failure": None,
        }
        write_run_manifest(manifest_path, manifest)
        entry["manifest_path"] = str(manifest_path)

        try:
            run = run_worker(
                task_id,
                worker_command,
                worker=worker,
                model=model,
                provider=provider,
                timeout_seconds=timeout_seconds,
                repo_root=repo_root,
                db_path=db_path,
                extra_env={
                    "KB_ATTEMPT_ID": str(attempt_id),
                    "KB_BUNDLE_PATH": str(bundle_path),
                    "KB_RESULT_PATH": str(result_path),
                    "KB_CONTEXT_MANIFEST_PATH": str(manifest_path),
                },
            )
        except Exception as exc:
            failure = (
                f"worker orchestration failed: {type(exc).__name__}: {exc}"
            )
            manifest["outcome"] = "failed"
            manifest["failure"] = _text_evidence(failure)
            # If persisting the failure manifest itself fails, the attempt
            # must still close as failed and the original exception must
            # propagate (chained, not shadowed).
            try:
                write_run_manifest(manifest_path, manifest)
            finally:
                ba.close_attempt(attempt_id, ba.ATTEMPT_FAILED, db_path=db_path)
            raise
        entry["run_id"] = run["id"]
        entry["run_state"] = run["state"]
        run_report = run.get("final_report") or {}
        manifest["worker_run"] = {
            "run_id": run.get("id"),
            "state": run.get("state"),
            "exit_code": run.get("exit_code"),
            "branch": run_report.get("branch"),
            "worktree": run_report.get("worktree"),
            "start_sha": run_report.get("start_sha"),
            "changed_paths": run_report.get("changed_paths", []),
            "scope_violations": run_report.get("scope_violations", []),
            "log_path": run_report.get("log_path"),
        }
        write_run_manifest(manifest_path, manifest)

        failure: str | None = None

        impl, error = _read_contract(result_path, "implementation")
        if impl is not None:
            try:
                ba.record_implementation_result(attempt_id, impl, db_path=db_path)
            except ba.ResultContractError as exc:
                failure = f"implementation contract invalid: {exc}"
            else:
                entry["implementation_status"] = impl.get("status")
                if run["state"] != bq.RUN_EXITED:
                    failure = f"worker run ended {run['state']}"
                elif impl.get("status") != "completed":
                    failure = f"worker reported status {impl.get('status')}"
        else:
            failure = error

        if failure is None:
            validated = ba.run_validation(
                attempt_id,
                cwd=worktree_path(task_id, repo_root=repo_root),
                timeout_seconds=validation_timeout_seconds,
                db_path=db_path,
            )
            entry["validation_status"] = validated["validation"]["status"]
            manifest["validation"] = _validation_evidence(validated["validation"])
            write_run_manifest(manifest_path, manifest)
            if validated["validation"]["status"] == ba.VALIDATION_FAILED:
                failure = "deterministic validation failed"

        if failure is None and review_command:
            review_error = _run_review_command(
                review_command,
                cwd=worktree_path(task_id, repo_root=repo_root),
                env_extra={
                    "KB_TASK_ID": str(task_id),
                    "KB_ATTEMPT_ID": str(attempt_id),
                    "KB_BUNDLE_PATH": str(bundle_path),
                    "KB_IMPL_RESULT_PATH": str(result_path),
                    "KB_REVIEW_RESULT_PATH": str(review_path),
                    "KB_CONTEXT_MANIFEST_PATH": str(manifest_path),
                },
                timeout_seconds=review_timeout_seconds,
            )
            if review_error is not None:
                failure = review_error
            else:
                review, error = _read_contract(review_path, "review")
                if review is None:
                    failure = error
                else:
                    try:
                        ba.record_review_result(attempt_id, review, db_path=db_path)
                    except ba.ResultContractError as exc:
                        failure = f"review contract invalid: {exc}"
                    else:
                        entry["review_verdict"] = review.get("verdict")
                        manifest["review"] = _review_evidence(review)
                        write_run_manifest(manifest_path, manifest)
                        if review.get("verdict") != "approve":
                            failure = f"review verdict {review.get('verdict')}"

        if failure is None:
            manifest["outcome"] = "succeeded"
            write_run_manifest(manifest_path, manifest)
            ba.close_attempt(attempt_id, ba.ATTEMPT_SUCCEEDED, db_path=db_path)
            entry["outcome"] = ba.ATTEMPT_SUCCEEDED

            # A worker's done marker is the explicit handoff boundary. Remove
            # only after every success gate passes; failed or interrupted work
            # must remain available for inspection and recovery.
            task_worktree = worktree_path(task_id, repo_root=repo_root)
            if (task_worktree / "done.txt").is_file():
                remove_worktree(
                    task_id, repo_root=repo_root, discard_done_marker=True
                )
                entry["worktree_cleanup"] = "removed"
            else:
                entry["worktree_cleanup"] = "kept_no_done_marker"

            final_task = bq.get_task(task_id, db_path=db_path)
            return {
                "outcome": LOOP_SUCCEEDED,
                "initiative_id": initiative_id,
                "packet_id": packet_id,
                "task_id": task_id,
                "task_state": final_task["state"] if final_task else None,
                "attempts": history,
            }

        entry["outcome"] = ba.ATTEMPT_FAILED
        entry["failure"] = failure
        manifest["outcome"] = "failed"
        manifest["failure"] = _text_evidence(failure)
        write_run_manifest(manifest_path, manifest)
        ba.close_attempt(attempt_id, ba.ATTEMPT_FAILED, db_path=db_path)
