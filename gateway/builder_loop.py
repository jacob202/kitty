"""KittyBuilder KB-S3b — bounded per-packet repair loop.

Drives one packet through implement → validate → review → repair using only
existing machinery: attempts (KB-S2), deterministic validation (KB-S3a), and
the shadow runner. Each attempt is a real ``run_worker`` execution in the
task's isolated worktree; the loop is bounded by ``policy.max_attempts``
(enforced by ``start_attempt``).

Contract wiring: the worker command receives KB_ATTEMPT_ID, KB_BUNDLE_PATH
(the persisted context bundle as JSON), and KB_RESULT_PATH; it must write an
implementation-result contract to KB_RESULT_PATH. The optional review command
runs afterwards as a plain subprocess in the same worktree with
KB_REVIEW_RESULT_PATH added, and must write a review-result contract there.
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

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from gateway import builder_attempt as ba
from gateway import builder_queue as bq
from gateway.builder_runner import run_worker, worktree_path
from gateway.paths import BUILDER_QUEUE_DB

DEFAULT_REVIEW_TIMEOUT = 1800

LOOP_SUCCEEDED = "succeeded"
LOOP_EXHAUSTED = "exhausted"


class LoopError(RuntimeError):
    """Raised when the packet loop cannot proceed at all."""


def _attempt_dir(attempt_id: int, db_path: Path | None) -> Path:
    queue_db = Path(db_path) if db_path is not None else BUILDER_QUEUE_DB
    return queue_db.parent / "attempts" / str(attempt_id)


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

        attempt_dir = _attempt_dir(attempt_id, db_path)
        attempt_dir.mkdir(parents=True, exist_ok=True)
        bundle_path = attempt_dir / "bundle.json"
        result_path = attempt_dir / "implementation.json"
        review_path = attempt_dir / "review.json"
        bundle_path.write_text(
            json.dumps(attempt["bundle"], indent=2), encoding="utf-8"
        )

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
            },
        )
        entry["run_id"] = run["id"]
        entry["run_state"] = run["state"]

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
            if validated["validation"]["status"] == ba.VALIDATION_FAILED:
                failure = "deterministic validation failed"

        if failure is None and review_command:
            review_error = _run_review_command(
                review_command,
                cwd=worktree_path(task_id, repo_root=repo_root),
                env_extra={
                    "KB_ATTEMPT_ID": str(attempt_id),
                    "KB_BUNDLE_PATH": str(bundle_path),
                    "KB_IMPL_RESULT_PATH": str(result_path),
                    "KB_REVIEW_RESULT_PATH": str(review_path),
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
                        if review.get("verdict") != "approve":
                            failure = f"review verdict {review.get('verdict')}"

        if failure is None:
            ba.close_attempt(attempt_id, ba.ATTEMPT_SUCCEEDED, db_path=db_path)
            entry["outcome"] = ba.ATTEMPT_SUCCEEDED
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
        ba.close_attempt(attempt_id, ba.ATTEMPT_FAILED, db_path=db_path)
