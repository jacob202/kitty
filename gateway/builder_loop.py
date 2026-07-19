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
from gateway import builder_identity as bid
from gateway import builder_queue as bq
from gateway.builder_brief import default_branch_name
from gateway.builder_context import build_context_manifest, write_run_manifest
from gateway.builder_runner import (
    RunnerError,
    preflight_worktree,
    remove_worktree,
    run_worker,
    worktree_diff_sha256,
    worktree_head,
    worktree_path,
)
from gateway.paths import BUILDER_QUEUE_DB

DEFAULT_REVIEW_TIMEOUT = 1800

# P027: consecutive identical infrastructure crashes tolerated before the
# loop stops with a truthful blocker instead of recovering forever.
DEFAULT_MAX_CONSECUTIVE_RECOVERIES = 3

LOOP_SUCCEEDED = "succeeded"
LOOP_EXHAUSTED = "exhausted"
LOOP_CANCELLED = "cancelled"


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


def _close_bound_attempt(
    attempt: dict[str, Any],
    lease: dict[str, Any],
    outcome: str,
    *,
    db_path: Path | None,
) -> None:
    """Close an attempt and release only the lease it was created with."""
    ba.close_attempt_and_release_lease(
        attempt["id"],
        outcome,
        lease_id=lease["lease_id"],
        packet_id=attempt["packet_id"],
        worker_id=lease["worker_id"],
        db_path=db_path,
    )


def _record_infrastructure_failure(
    task_id: str,
    *,
    reason: str,
    phase: str,
    attempt_id: int | None,
    db_path: Path | None,
) -> None:
    payload: dict[str, Any] = {
        "reason": reason,
        "counts_toward_budget": False,
        "phase": phase,
    }
    if attempt_id is not None:
        payload["attempt_id"] = attempt_id
    bq.append_event(
        task_id,
        "infrastructure_failed",
        payload=payload,
        db_path=db_path,
    )


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


def _context_manifest_metadata(manifest: dict[str, Any]) -> dict[str, Any]:
    """Return stable identity/hash evidence for the context payload."""
    context = manifest.get("context")
    encoded = json.dumps(
        context, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return {
        "sha256": hashlib.sha256(encoded).hexdigest(),
        "task_id": manifest.get("task_id"),
        "attempt_id": manifest.get("attempt_id"),
        "attempt_no": manifest.get("attempt_no"),
    }


def _validate_context_manifest(
    path: Path,
    *,
    attempt_dir: Path,
    task_id: str,
    attempt_id: int,
    bundle_path: Path,
) -> dict[str, Any]:
    """Validate the runner-owned context manifest and its bundle identity."""
    resolved = path.resolve()
    root = attempt_dir.resolve()
    if not resolved.is_relative_to(root):
        raise ValueError(
            f"context manifest {resolved} is outside attempt artifact root {root}"
        )
    try:
        parsed = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"context manifest unreadable: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("context manifest must be a JSON object")
    if parsed.get("task_id") != task_id:
        raise ValueError(
            f"context manifest task mismatch: {parsed.get('task_id')!r} != {task_id!r}"
        )
    if int(parsed.get("attempt_id", -1)) != attempt_id:
        raise ValueError(
            "context manifest attempt mismatch: "
            f"{parsed.get('attempt_id')!r} != {attempt_id!r}"
        )
    expected = parsed.get("bundle_sha256")
    actual = hashlib.sha256(bundle_path.read_bytes()).hexdigest()
    if expected != actual:
        raise ValueError(
            f"context bundle hash mismatch: manifest={expected!r} actual={actual!r}"
        )
    metadata = parsed.get("context_manifest")
    if metadata != _context_manifest_metadata(parsed):
        raise ValueError("context manifest metadata/hash is invalid")
    return parsed


def _consecutive_identical_crashes(
    task_id: str,
    *,
    db_path: Path | None = None,
) -> tuple[int, str]:
    """Return (count, reason) of the trailing run of identical infra crashes.

    Walks the task's event log newest-first, counting ``infrastructure_failed``
    events that share one reason. A ``run_exited`` event breaks the run — a
    worker completing a run is proof the infrastructure works. A crash with a
    different reason also breaks it, so distinct failure modes are tracked
    independently.
    """
    count = 0
    reason = ""
    for event in reversed(bq.list_events(task_id, db_path=db_path)):
        etype = event["type"]
        if etype == "infrastructure_failed":
            this_reason = str((event.get("payload") or {}).get("reason") or "")
            if count and this_reason != reason:
                break
            reason = this_reason
            count += 1
        elif etype == "run_exited":
            break
    return count, reason


def _reconcile_stale_attempts(
    initiative_id: str,
    packet_id: str,
    *,
    db_path: Path | None = None,
    repo_root: Path | None = None,
) -> list[dict[str, Any]]:
    """Detect open attempts left by crashed workers and close them as crashed.

    Preserves each crashed attempt's run-manifest.json with ``outcome:'crashed'``
    and the crash reason, and logs ``infrastructure_failed`` events with
    ``counts_toward_budget: False``. Returns the list of reconciled attempt
    dicts so callers can report them.
    """
    stale = ba.list_stale_attempts(initiative_id, packet_id, db_path=db_path)
    reconciled: list[dict[str, Any]] = []
    for attempt in stale:
        task_id = attempt["task_id"]
        attempt_id = attempt["id"]
        attempt_dir_path = _attempt_dir(task_id, attempt_id, db_path)
        manifest_path = attempt_dir_path / "run-manifest.json"

        crash_reason = (
            f"Builder run_packet process was interrupted or terminated "
            f"while attempt {attempt['attempt_no']} was running"
        )

        manifest: dict[str, Any] = {}
        if manifest_path.exists():
            try:
                manifest = json.loads(
                    manifest_path.read_text(encoding="utf-8")
                )
            except (OSError, json.JSONDecodeError) as exc:
                raise LoopError(
                    f"cannot reconcile stale attempt {attempt_id}: "
                    f"run manifest is unreadable: {exc}"
                ) from exc
            if not isinstance(manifest, dict):
                raise LoopError(
                    f"cannot reconcile stale attempt {attempt_id}: "
                    "run manifest must be a JSON object"
                )

        manifest["outcome"] = "crashed"
        manifest["failure"] = _text_evidence(crash_reason)
        attempt_dir_path.mkdir(parents=True, exist_ok=True)
        write_run_manifest(manifest_path, manifest)

        lease_id = attempt.get("lease_id")
        if lease_id is None:
            # Legacy attempts predate branch-lease binding. Their lack of a
            # lease is explicit durable state, not a missing-owner fallback.
            ba.close_attempt(attempt_id, ba.ATTEMPT_CRASHED, db_path=db_path)
        else:
            lease = bq.get_branch_lease(lease_id, db_path=db_path)
            if lease is None:
                raise LoopError(
                    f"cannot reconcile stale attempt {attempt_id}: bound lease "
                    f"{lease_id} is missing"
                )
            ba.close_attempt_and_release_lease(
                attempt_id,
                ba.ATTEMPT_CRASHED,
                lease_id=lease_id,
                packet_id=packet_id,
                worker_id=lease["worker_id"],
                db_path=db_path,
            )

        bq.append_event(
            task_id,
            "infrastructure_failed",
            payload={
                "reason": crash_reason,
                "counts_toward_budget": False,
                "phase": "stale_attempt_reconciliation",
                "attempt_id": attempt_id,
                "attempt_no": attempt["attempt_no"],
            },
            db_path=db_path,
        )
        reconciled.append(attempt)
    return reconciled


def _write_review_context(
    path: Path,
    *,
    task_id: str,
    attempt_id: int,
    review_sha: str,
    diff_sha256: str,
    changed_paths: list[str],
) -> dict[str, Any]:
    """Persist the exact revision/diff that the reviewer is authorized to inspect."""
    context = {
        "task_id": task_id,
        "attempt_id": attempt_id,
        "review_sha": review_sha,
        "diff_sha256": diff_sha256,
        "changed_paths": changed_paths,
    }
    path.write_text(json.dumps(context, indent=2, sort_keys=True), encoding="utf-8")
    return context


def _validate_review_context(
    path: Path,
    *,
    task_id: str,
    attempt_id: int,
    worktree: Path,
    start_sha: str,
) -> dict[str, Any]:
    """Reject reviewer output if the inspected commit or diff moved."""
    try:
        context = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"review context unreadable: {exc}") from exc
    if not isinstance(context, dict):
        raise ValueError("review context must be a JSON object")
    if context.get("task_id") != task_id or int(context.get("attempt_id", -1)) != attempt_id:
        raise ValueError("review context task/attempt identity mismatch")
    actual_head = worktree_head(worktree)
    if actual_head != context.get("review_sha"):
        raise ValueError(
            f"reviewed HEAD changed: expected {context.get('review_sha')!r}, "
            f"actual {actual_head!r}"
        )
    actual_diff = worktree_diff_sha256(worktree, start_sha)
    if actual_diff != context.get("diff_sha256"):
        raise ValueError(
            f"reviewed diff changed: expected {context.get('diff_sha256')!r}, "
            f"actual {actual_diff!r}"
        )
    return context


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


def _create_attempt_artifacts(
    *,
    initiative_id: str,
    packet_id: str,
    task_id: str,
    attempt: dict[str, Any],
    lease: dict[str, Any],
    worker: str,
    model: str | None,
    provider: str | None,
    worker_command: list[str],
    repo_root: Path | None,
    db_path: Path | None,
) -> tuple[Path, Path, Path, Path, Path, dict[str, Any]]:
    """Persist runner-owned artifacts before a worker can execute."""
    attempt_id = attempt["id"]
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
        "lease": {
            "lease_id": lease["lease_id"],
            "worker_id": lease["worker_id"],
            "branch": lease["branch"],
            "worktree_path": lease["worktree_path"],
            "base_sha": lease["base_sha"],
        },
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
    manifest["context_manifest"] = _context_manifest_metadata(manifest)
    write_run_manifest(manifest_path, manifest)
    _validate_context_manifest(
        manifest_path,
        attempt_dir=attempt_dir,
        task_id=task_id,
        attempt_id=attempt_id,
        bundle_path=bundle_path,
    )
    bq.append_event(
        task_id,
        "attempt_artifacts_created",
        payload={
            "attempt_id": attempt_id,
            "lease_id": lease["lease_id"],
            "artifact_dir": str(attempt_dir),
            "manifest_path": str(manifest_path),
        },
        db_path=db_path,
    )
    return (
        attempt_dir,
        bundle_path,
        result_path,
        review_path,
        manifest_path,
        manifest,
    )


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
    max_consecutive_recoveries: int = DEFAULT_MAX_CONSECUTIVE_RECOVERIES,
    repo_root: Path | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Run the bounded repair loop for one packet.

    Returns ``{"outcome": "succeeded"|"exhausted"|"cancelled", ...}`` where
    each attempt entry records what happened and why. Raises ``LoopError``
    when infrastructure or durable task state prevents safe execution.
    """
    if not worker_command:
        raise LoopError("worker_command must be a non-empty list")

    ba.init_db(db_path)
    bundle_preview = ba.build_context_bundle(initiative_id, packet_id, db_path=db_path)
    task_id = bundle_preview["task_id"]

    task = bq.get_task(task_id, db_path=db_path)
    if task is None:
        raise LoopError(
            f"task {task_id} for {initiative_id}/{packet_id} is missing"
        )

    if task["state"] == bq.QUEUED:
        _reconcile_stale_attempts(
            initiative_id, packet_id, db_path=db_path, repo_root=repo_root
        )
    elif task["state"] == bq.BLOCKED:
        # A runner exception can durably block the task while the process dies
        # before closing its packet attempt. Only that exact paired condition
        # permits automatic recovery; claimed/running tasks remain fenced.
        stale = ba.list_stale_attempts(
            initiative_id, packet_id, db_path=db_path
        )
        if not stale:
            raise LoopError(
                f"task {task_id} for {initiative_id}/{packet_id} is blocked "
                "without a stale open attempt; operator release is required"
            )
        _reconcile_stale_attempts(
            initiative_id, packet_id, db_path=db_path, repo_root=repo_root
        )
        try:
            task = bq.operator_release_task(
                task_id,
                reason="stale_attempt_reconciliation",
                db_path=db_path,
            )
        except Exception as exc:
            _record_infrastructure_failure(
                task_id,
                reason=f"stale task release failed: {exc}",
                phase="stale_attempt_task_release",
                attempt_id=stale[-1]["id"],
                db_path=db_path,
            )
            raise LoopError(
                f"stale attempts were reconciled but task {task_id} could "
                f"not be released: {exc}"
            ) from exc
    else:
        raise LoopError(
            f"task {task_id} for {initiative_id}/{packet_id} is "
            f"{task['state']}; the loop only starts on a queued task or a "
            "blocked task with a stale attempt"
        )

    crash_count, crash_reason = _consecutive_identical_crashes(
        task_id, db_path=db_path
    )
    if max_consecutive_recoveries > 0 and crash_count >= max_consecutive_recoveries:
        blocker = (
            f"recovery budget exhausted: {crash_count} consecutive identical "
            f"infrastructure crashes (reason: {crash_reason}); recovery was "
            f"attempted after each crash. Operator inspection required before "
            f"another run."
        )
        bq.append_event(
            task_id,
            "recovery_budget_exhausted",
            payload={
                "crash_count": crash_count,
                "reason": crash_reason,
                "max_consecutive_recoveries": max_consecutive_recoveries,
            },
            db_path=db_path,
        )
        raise LoopError(blocker)

    # Verify the packet has a durable base SHA before entering the repair
    # loop. Without it, branch lease claims cannot proceed safely.
    try:
        base_sha = ba.get_packet_base_sha(
            initiative_id, packet_id, db_path=db_path
        )
    except ba.AttemptError:
        raise LoopError(
            f"branch lease claim failed: no durable base_sha for "
            f"{initiative_id}/{packet_id}"
        )

    history: list[dict[str, Any]] = []
    while True:
        try:
            preflight_worktree(task_id, repo_root=repo_root)
        except RunnerError as exc:
            bq.append_event(
                task_id,
                "infrastructure_failed",
                payload={
                    "reason": str(exc),
                    "counts_toward_budget": False,
                    "phase": "preflight",
                },
                db_path=db_path,
            )
            raise LoopError(f"builder preflight failed: {exc}") from exc

        try:
            expected_branch = default_branch_name(task)
            expected_worktree = worktree_path(task_id, repo_root=repo_root)
            attempt, lease = ba.claim_and_start_attempt(
                initiative_id,
                packet_id,
                worker_id=worker,
                branch=expected_branch,
                worktree_path=str(expected_worktree),
                base_sha=base_sha,
                db_path=db_path,
            )
        except ba.AttemptLimitError as exc:
            return {
                "outcome": LOOP_EXHAUSTED,
                "initiative_id": initiative_id,
                "packet_id": packet_id,
                "task_id": task_id,
                "reason": str(exc),
                "attempts": history,
            }
        except (ba.AttemptError, bq.BranchLeaseConflictError) as exc:
            raise LoopError(
                f"failed to claim lease and open attempt for "
                f"{initiative_id}/{packet_id}: {exc}"
            ) from exc

        # A prior failed attempt's shadow run left the task blocked; hand it
        # back to queued only now that the next attempt is secured, so budget
        # exhaustion leaves the task blocked for the operator.
        if attempt["attempt_no"] > 1:
            task = bq.get_task(task_id, db_path=db_path)
            if task is not None and task["state"] == bq.BLOCKED:
                try:
                    bq.operator_release_task(
                        task_id,
                        reason=f"repair_loop_retry attempt {attempt['attempt_no']}",
                        db_path=db_path,
                    )
                except Exception as exc:
                    _close_bound_attempt(
                        attempt, lease, ba.ATTEMPT_CRASHED, db_path=db_path
                    )
                    _record_infrastructure_failure(
                        task_id,
                        reason=f"retry task release failed: {exc}",
                        phase="retry_release",
                        attempt_id=attempt["id"],
                        db_path=db_path,
                    )
                    raise LoopError(
                        f"failed to release task {task_id} for retry: {exc}"
                    ) from exc
            elif task is None or task["state"] != bq.QUEUED:
                _close_bound_attempt(
                    attempt, lease, ba.ATTEMPT_CRASHED, db_path=db_path
                )
                _record_infrastructure_failure(
                    task_id,
                    reason=(
                        f"task state changed before retry: "
                        f"{task['state'] if task else 'missing'}"
                    ),
                    phase="retry_release",
                    attempt_id=attempt["id"],
                    db_path=db_path,
                )
                raise LoopError(
                    f"task {task_id} is {task['state'] if task else 'missing'} "
                    "before retry; expected blocked or queued — not retrying"
                )

        attempt_id = attempt["id"]
        entry: dict[str, Any] = {"attempt_id": attempt_id, "attempt_no": attempt["attempt_no"]}
        history.append(entry)

        try:
            (
                attempt_dir,
                bundle_path,
                result_path,
                review_path,
                manifest_path,
                manifest,
            ) = _create_attempt_artifacts(
                initiative_id=initiative_id,
                packet_id=packet_id,
                task_id=task_id,
                attempt=attempt,
                lease=lease,
                worker=worker,
                model=model,
                provider=provider,
                worker_command=worker_command,
                repo_root=repo_root,
                db_path=db_path,
            )
        except Exception as exc:
            _close_bound_attempt(
                attempt, lease, ba.ATTEMPT_CRASHED, db_path=db_path
            )
            _record_infrastructure_failure(
                task_id,
                reason=f"attempt artifact setup failed: {type(exc).__name__}: {exc}",
                phase="attempt_artifacts",
                attempt_id=attempt_id,
                db_path=db_path,
            )
            raise LoopError(
                f"failed to create artifacts for attempt {attempt_id}: {exc}"
            ) from exc
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
                base_sha=base_sha,
                extra_env={
                    "KB_ATTEMPT_ID": str(attempt_id),
                    "KB_BUNDLE_PATH": str(bundle_path),
                    "KB_RESULT_PATH": str(result_path),
                    "KB_CONTEXT_MANIFEST_PATH": str(manifest_path),
                },
            )
        except Exception as exc:
            orchestration_failure = (
                f"worker orchestration failed: {type(exc).__name__}: {exc}"
            )
            manifest["outcome"] = "crashed"
            manifest["failure"] = _text_evidence(orchestration_failure)
            manifest_error: Exception | None = None
            try:
                write_run_manifest(manifest_path, manifest)
            except Exception as write_exc:
                manifest_error = write_exc
            _close_bound_attempt(
                attempt, lease, ba.ATTEMPT_CRASHED, db_path=db_path
            )
            _record_infrastructure_failure(
                task_id,
                reason=orchestration_failure,
                phase="worker_orchestration",
                attempt_id=attempt_id,
                db_path=db_path,
            )
            if manifest_error is not None:
                raise LoopError(
                    f"{orchestration_failure}; writing crash manifest also "
                    f"failed: {manifest_error}"
                ) from exc
            raise LoopError(orchestration_failure) from exc
        entry["run_id"] = run["id"]
        entry["run_state"] = run["state"]
        try:
            _validate_context_manifest(
                manifest_path,
                attempt_dir=attempt_dir,
                task_id=task_id,
                attempt_id=attempt_id,
                bundle_path=bundle_path,
            )
        except ValueError as exc:
            entry["outcome"] = ba.ATTEMPT_FAILED
            entry["failure"] = f"context manifest invalid after worker: {exc}"
            manifest["outcome"] = "failed"
            manifest["failure"] = _text_evidence(entry["failure"])
            write_run_manifest(manifest_path, manifest)
            _close_bound_attempt(
                attempt, lease, ba.ATTEMPT_FAILED, db_path=db_path
            )
            raise LoopError(entry["failure"]) from exc
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

        if run["state"] == bq.RUN_CANCELLED:
            entry["outcome"] = ba.ATTEMPT_ABORTED
            entry["failure"] = "worker run was cancelled"
            manifest["outcome"] = "cancelled"
            manifest["failure"] = _text_evidence(entry["failure"])
            write_run_manifest(manifest_path, manifest)
            _close_bound_attempt(
                attempt, lease, ba.ATTEMPT_ABORTED, db_path=db_path
            )
            final_task = bq.get_task(task_id, db_path=db_path)
            return {
                "outcome": LOOP_CANCELLED,
                "initiative_id": initiative_id,
                "packet_id": packet_id,
                "task_id": task_id,
                "task_state": final_task["state"] if final_task else None,
                "reason": entry["failure"],
                "attempts": history,
            }

        if run["state"] == bq.RUN_LEASE_LOST:
            infrastructure_failure = "worker lost its task lease during execution"
            entry["outcome"] = ba.ATTEMPT_CRASHED
            entry["failure"] = infrastructure_failure
            manifest["outcome"] = "crashed"
            manifest["failure"] = _text_evidence(infrastructure_failure)
            write_run_manifest(manifest_path, manifest)
            _close_bound_attempt(
                attempt, lease, ba.ATTEMPT_CRASHED, db_path=db_path
            )
            _record_infrastructure_failure(
                task_id,
                reason=infrastructure_failure,
                phase="worker_lease",
                attempt_id=attempt_id,
                db_path=db_path,
            )
            raise LoopError(infrastructure_failure)

        identity_findings = bid.verify_worker_identity(
            packet_id,
            repo_root=expected_worktree,
            db_path=db_path,
            expected_lease_id=lease["lease_id"],
            expected_worker_id=worker,
            expected_branch=expected_branch,
            expected_worktree_path=str(expected_worktree),
            expected_base_sha=base_sha,
        )
        if identity_findings:
            failure = "worker identity verification failed: " + "; ".join(
                finding.message for finding in identity_findings
            )
            entry["identity_findings"] = [
                {
                    "category": finding.category,
                    "field": finding.field,
                    "message": finding.message,
                }
                for finding in identity_findings
            ]
            bq.append_event(
                task_id,
                "identity_verification_failed",
                payload={
                    "attempt_id": attempt_id,
                    "lease_id": lease["lease_id"],
                    "findings": entry["identity_findings"],
                    "counts_toward_budget": True,
                },
                db_path=db_path,
            )

        if failure is None:
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
            review_context_path = attempt_dir / "review-context.json"
            start_sha = str(run_report.get("start_sha") or "")
            review_worktree = worktree_path(task_id, repo_root=repo_root)
            review_context = _write_review_context(
                review_context_path,
                task_id=task_id,
                attempt_id=attempt_id,
                review_sha=worktree_head(review_worktree),
                diff_sha256=str(run_report.get("diff_sha256") or ""),
                changed_paths=list(run_report.get("changed_paths") or []),
            )
            manifest["review_context"] = {
                "path": str(review_context_path),
                "review_sha": review_context["review_sha"],
                "diff_sha256": review_context["diff_sha256"],
                "changed_paths": review_context["changed_paths"],
            }
            write_run_manifest(manifest_path, manifest)
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
                    "KB_REVIEW_CONTEXT_PATH": str(review_context_path),
                    "KB_REVIEW_SHA": str(review_context["review_sha"]),
                    "KB_REVIEW_DIFF_SHA256": str(review_context["diff_sha256"]),
                },
                timeout_seconds=review_timeout_seconds,
            )
            if review_error is not None:
                failure = review_error
            else:
                try:
                    _validate_context_manifest(
                        manifest_path,
                        attempt_dir=attempt_dir,
                        task_id=task_id,
                        attempt_id=attempt_id,
                        bundle_path=bundle_path,
                    )
                except ValueError as exc:
                    failure = f"context manifest invalid after reviewer: {exc}"
                if failure is None:
                    try:
                        _validate_review_context(
                            review_context_path,
                            task_id=task_id,
                            attempt_id=attempt_id,
                            worktree=review_worktree,
                            start_sha=start_sha,
                        )
                    except ValueError as exc:
                        failure = f"review evidence invalid: {exc}"
                review, error = _read_contract(review_path, "review")
                if failure is not None:
                    review = None
                elif review is None:
                    failure = error
                else:
                    try:
                        ba.record_review_result(attempt_id, review, db_path=db_path)
                    except ba.ResultContractError as exc:
                        failure = f"review contract invalid: {exc}"
                    else:
                        entry["review_verdict"] = review.get("verdict")
                        manifest["review"] = {
                            **_review_evidence(review),
                            "review_sha": review_context["review_sha"],
                            "diff_sha256": review_context["diff_sha256"],
                        }
                        bq.append_event(
                            task_id,
                            "review_evidence_bound",
                            payload={
                                "attempt_id": attempt_id,
                                "review_sha": review_context["review_sha"],
                                "diff_sha256": review_context["diff_sha256"],
                                "changed_paths": review_context["changed_paths"],
                                "artifact_dir": str(attempt_dir),
                            },
                            db_path=db_path,
                        )
                        write_run_manifest(manifest_path, manifest)
                        if review.get("verdict") != "approve":
                            failure = f"review verdict {review.get('verdict')}"

        if failure is None:
            manifest["outcome"] = "succeeded"
            write_run_manifest(manifest_path, manifest)
            _close_bound_attempt(
                attempt, lease, ba.ATTEMPT_SUCCEEDED, db_path=db_path
            )
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
        _close_bound_attempt(
            attempt, lease, ba.ATTEMPT_FAILED, db_path=db_path
        )
