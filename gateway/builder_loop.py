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
import math
import os
import shlex
import subprocess
import time
from pathlib import Path
from typing import Any

from gateway import builder_attempt as ba
from gateway import builder_contract_gate as bcg
from gateway import builder_execution_boundary as beb
from gateway import builder_identity as bid
from gateway import builder_initiative as bi
from gateway import builder_pr_janitor as bj
from gateway import builder_queue as bq
from gateway import compute_governor as cg
from gateway.builder_brief import default_branch_name
from gateway.builder_context import build_context_manifest, write_run_manifest
from gateway.builder_runner import (
    DEFAULT_HEARTBEAT_SECONDS,
    DEFAULT_LEASE_SECONDS,
    RunnerError,
    archive_and_reset_worktree,
    preflight_worktree,
    remove_worktree,
    run_worker,
    worktree_changed_paths,
    worktree_diff_sha256,
    worktree_head,
    worktree_path,
)
from gateway.paths import BUILDER_QUEUE_DB

DEFAULT_REVIEW_TIMEOUT = 240

# P027: consecutive identical infrastructure crashes tolerated before the
# loop stops with a truthful blocker instead of recovering forever.
DEFAULT_MAX_CONSECUTIVE_RECOVERIES = 3

LOOP_SUCCEEDED = "succeeded"
LOOP_EXHAUSTED = "exhausted"
LOOP_CANCELLED = "cancelled"
LOOP_PAUSED = "paused"
LOOP_INFRASTRUCTURE_BLOCKED = "infrastructure_blocked"

LOOP_PROVIDER_EXHAUSTED = "provider_exhausted"
PROVIDER_EXHAUSTED_EXIT_CODE = 75


class LoopError(RuntimeError):
    """Raised when the packet loop cannot proceed at all."""


def _runtime_budget_expired(deadline_monotonic: float | None) -> bool:
    return deadline_monotonic is not None and time.monotonic() >= deadline_monotonic


def _bounded_timeout(timeout_seconds: int, deadline_monotonic: float | None) -> int:
    if deadline_monotonic is None:
        return timeout_seconds
    remaining = max(0.0, deadline_monotonic - time.monotonic())
    return max(1, min(timeout_seconds, math.ceil(remaining)))


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


def _close_provider_exhaustion(
    *,
    initiative_id: str,
    packet_id: str,
    task_id: str,
    attempt: dict[str, Any],
    lease: dict[str, Any],
    entry: dict[str, Any],
    history: list[dict[str, Any]],
    manifest: dict[str, Any],
    manifest_path: Path,
    reason: str,
    phase: str,
    db_path: Path | None,
) -> dict[str, Any]:
    """Close a clean provider outage without charging the implementation budget."""
    entry["outcome"] = ba.ATTEMPT_CRASHED
    entry["failure"] = reason
    entry["provider_exhausted"] = True
    manifest["outcome"] = LOOP_PROVIDER_EXHAUSTED
    manifest["failure"] = _text_evidence(reason)
    write_run_manifest(manifest_path, manifest)
    _close_bound_attempt(attempt, lease, ba.ATTEMPT_CRASHED, db_path=db_path)
    _record_infrastructure_failure(
        task_id,
        reason=reason,
        phase=phase,
        attempt_id=attempt["id"],
        db_path=db_path,
    )
    task = bq.get_task(task_id, db_path=db_path)
    if task is not None and task["state"] == bq.BLOCKED:
        bq.operator_release_task(
            task_id,
            reason="provider_exhausted_resumable_pause",
            db_path=db_path,
        )
    final_task = bq.get_task(task_id, db_path=db_path)
    return {
        "outcome": LOOP_PROVIDER_EXHAUSTED,
        "initiative_id": initiative_id,
        "packet_id": packet_id,
        "task_id": task_id,
        "task_state": final_task["state"] if final_task else None,
        "reason": reason,
        "attempts": history,
    }


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
        elif etype in {"run_exited", "recovery_lane_changed"}:
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
    stale = ba.list_all_stale_attempts(db_path=db_path)
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

        # P027: the crashed attempt's partial work is evidence, not a starting
        # point — archive it into the attempt dir, then reset the worktree so
        # the next attempt starts clean.
        worktree_evidence = archive_and_reset_worktree(
            worktree_path(task_id, repo_root=repo_root),
            attempt_dir_path,
            reset_sha=ba.get_packet_base_sha(
                attempt["initiative_id"], attempt["packet_id"], db_path=db_path
            ),
        )

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
                packet_id=attempt["packet_id"],
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
                "worktree": worktree_evidence,
            },
            db_path=db_path,
        )
        reconciled.append(attempt)
    return reconciled


def reconcile_interrupted_packet(
    initiative_id: str,
    packet_id: str,
    *,
    db_path: Path | None = None,
    repo_root: Path | None = None,
) -> list[dict[str, Any]]:
    """Close one liveness-certified stale attempt and safely requeue its task.

    This is recovery housekeeping only: it never dispatches a worker. It
    preserves the crashed attempt evidence, releases the bound branch lease,
    and uses the queue's operator-release transition so a paused initiative
    can remain paused while its packet becomes reclaimable on resume.
    """
    bundle = ba.build_context_bundle(initiative_id, packet_id, db_path=db_path)
    task_id = str(bundle["task_id"])
    task = bq.get_task(task_id, db_path=db_path)
    if task is None:
        raise LoopError(f"task {task_id} for {initiative_id}/{packet_id} is missing")
    if task["state"] != bq.BLOCKED:
        return []

    stale = ba.list_stale_attempts(initiative_id, packet_id, db_path=db_path)
    reconciled: list[dict[str, Any]] = []
    recovery_attempt_id: int | None = stale[-1]["id"] if stale else None
    if stale:
        reconciled = _reconcile_stale_attempts(
            initiative_id, packet_id, db_path=db_path, repo_root=repo_root
        )
    else:
        status = bi.initiative_status(initiative_id, db_path=db_path)
        if packet_id not in status.get("recovery_needed", []):
            return []
        attempts = ba.list_attempts(initiative_id, packet_id, db_path=db_path)
        recovery_attempt_id = attempts[-1]["id"] if attempts else None
    try:
        bq.operator_release_task(
            task_id,
            reason="stale_attempt_reconciliation",
            db_path=db_path,
        )
    except Exception as exc:
        _record_infrastructure_failure(
            task_id,
            reason=f"stale task release failed: {exc}",
            phase="stale_attempt_task_release",
            attempt_id=recovery_attempt_id,
            db_path=db_path,
        )
        raise LoopError(
            f"stale attempts were reconciled but task {task_id} could not be released: {exc}"
        ) from exc
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


def _cumulative_evidence(worktree: Path, base_sha: str) -> dict[str, Any]:
    """Bind the packet's final state to its durable ``base_sha``.

    On a repair retry the retained implementation is committed on an earlier
    attempt, so the reviewer and the final report must cover the *cumulative*
    change since the packet base — not only the latest retry's delta. The
    per-attempt delta stays in each run record (``run_worker`` measures from
    the retry-local HEAD); this block is the packet-level final evidence.
    """
    return {
        "base_sha": base_sha,
        "review_sha": worktree_head(worktree),
        "diff_sha256": worktree_diff_sha256(worktree, base_sha),
        "changed_paths": worktree_changed_paths(worktree, base_sha),
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
    """Run a reviewer inside the lower-trust read-only boundary."""
    result_raw = env_extra.get("KB_REVIEW_RESULT_PATH")
    if not result_raw:
        return "review command missing KB_REVIEW_RESULT_PATH"
    result_path = Path(result_raw).resolve()
    runtime_dir = result_path.parent / ".review-runtime"
    env = beb.build_child_environment(os.environ, run_dir=runtime_dir)
    env.update(env_extra)

    read_keys = (
        "KB_BUNDLE_PATH",
        "KB_IMPL_RESULT_PATH",
        "KB_CONTEXT_MANIFEST_PATH",
        "KB_REVIEW_CONTEXT_PATH",
    )
    read_paths = [Path(env[key]) for key in read_keys if env.get(key)]
    write_keys = ("KB_REVIEW_RESULT_PATH", "KB_REVIEW_NOTE_PATH")
    write_paths = [Path(env[key]) for key in write_keys if env.get(key)]

    # The canonical reviewer adapter stages runner-owned evidence as local
    # copies because OpenCode denies external-directory access. Keep the source
    # tree read-only while allowing only those exact, disposable staging files.
    attempt_id = env_extra.get("KB_ATTEMPT_ID", "")
    if attempt_id.isdigit():
        write_paths.extend(
            cwd / f".kittybuilder-review-{name}-{attempt_id}.json"
            for name in ("bundle", "impl", "context", "binding", "result")
        )
    try:
        wrapped = beb.wrap_command(
            command,
            worktree=cwd,
            run_dir=runtime_dir,
            environment=env,
            read_paths=read_paths,
            write_paths=write_paths,
            worktree_writable=False,
        )
        proc = subprocess.run(
            wrapped,
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
    worker_command: list[str] | None,
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
        "command_sha256": _command_digest(worker_command) if worker_command else "",
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


def _is_explicit_free_model(model: str) -> bool:
    return model == "openrouter/free" or model.endswith(":free") or (
        model.startswith("opencode/") and model.endswith("-free")
    )


def _sanitize_free_adapter_env(adapter_env: dict[str, str]) -> dict[str, str]:
    """Force the free lane to remain free even for direct library callers."""
    for key in ("KITTYBUILDER_MODEL", "KITTYBUILDER_REVIEW_MODEL"):
        model = adapter_env.get(key, "").strip()
        if model and not _is_explicit_free_model(model):
            raise LoopError(f"free route rejects paid model override {model!r}")
    for key in ("KITTYBUILDER_MODELS", "KITTYBUILDER_REVIEW_MODELS"):
        for model in adapter_env.get(key, "").split():
            if not _is_explicit_free_model(model):
                raise LoopError(f"free route rejects paid model override {model!r}")
    return {
        "KITTYBUILDER_AGENT": "free-builder",
        "KITTYBUILDER_REVIEW_AGENT": "free-reviewer",
        "KITTYBUILDER_MODEL": adapter_env.get("KITTYBUILDER_MODEL", ""),
        "KITTYBUILDER_REVIEW_MODEL": adapter_env.get("KITTYBUILDER_REVIEW_MODEL", ""),
        "KITTYBUILDER_MODELS": adapter_env.get("KITTYBUILDER_MODELS", ""),
        "KITTYBUILDER_REVIEW_MODELS": adapter_env.get("KITTYBUILDER_REVIEW_MODELS", ""),
    }


def _configure_paid_route(
    tier: str, worker: str, adapter_env: dict[str, str]
) -> tuple[Any, str, dict[str, str]]:
    """Bind an explicit paid tier to child-only adapter environment."""
    from gateway.builder_paid_routing import resolve_paid_route

    route = resolve_paid_route(tier)
    env = dict(adapter_env)
    env.update(
        {
            "KITTYBUILDER_AGENT": "paid-builder",
            "KITTYBUILDER_REVIEW_AGENT": "paid-reviewer",
            "KITTYBUILDER_MODEL": route.worker_model,
            "KITTYBUILDER_REVIEW_MODEL": "",
            "KITTYBUILDER_MODELS": "",
            "KITTYBUILDER_REVIEW_MODELS": " ".join(route.reviewer_candidates),
        }
    )
    if worker.startswith("opencode-paid-"):
        worker = f"opencode-paid-{route.tier}"
    return route, worker, env


def _governor_dispatch(
    initiative_id: str,
    packet_id: str,
    *,
    base_sha: str,
    risk_class: str = "routine",
    requested_route: str | None = None,
) -> "cg.Dispatch":
    """Describe this packet run in the governor's terms.

    Scope and acceptance come from the packet contract Builder already
    enforces, so the governor is not inventing a second definition of done.
    """
    return cg.Dispatch(
        task_type="implement",
        work_kind="implementation",
        subject_ref=f"{initiative_id}/{packet_id}",
        head_sha=base_sha,
        artifact=f"packet {initiative_id}/{packet_id}",
        acceptance_tests=("packet contract validation_commands",),
        allowed_scope=("packet allowed_paths",),
        exclusions=("paths outside the packet contract",),
        risk_class=risk_class,
        stopping_condition="the bounded repair loop succeeds or exhausts its attempt budget",
        requested_route=requested_route,
    )


def _governor_gate(
    initiative_id: str,
    packet_id: str,
    task_id: str,
    *,
    base_sha: str,
    governor_db: Path | None,
    risk_class: str,
    requested_route: str | None,
    override_reason: str | None,
    db_path: Path | None,
) -> "cg.Decision | None":
    """Refuse a packet run the governor has already paid for at this base SHA."""
    if governor_db is None:
        return None

    cg.init_db(governor_db)
    config = cg.load_reserve_config(cg.ROOT_CONFIG_PATH)
    reserve = cg.reserve_from_ledger(governor_db, config)
    decision = cg.decide(
        governor_db,
        _governor_dispatch(
            initiative_id,
            packet_id,
            base_sha=base_sha,
            risk_class=risk_class,
            requested_route=requested_route,
        ),
        reserve=reserve,
        override_reason=override_reason,
    )
    if decision.action in {cg.ACTION_RUN, cg.ACTION_DOWNGRADE}:
        if (
            requested_route in {cg.ROUTE_CHEAP, cg.ROUTE_FRONTIER}
            and decision.route in {cg.ROUTE_CHEAP, cg.ROUTE_FRONTIER}
        ):
            from gateway.builder_paid_routing import resolve_paid_route

            configured_cost = resolve_paid_route(decision.route).projected_cost_cad
            if configured_cost > reserve.remaining_cad:
                reasons = (
                    *decision.reasons,
                    f"configured paid route projects CAD {configured_cost:.4f} against "
                    f"CAD {reserve.remaining_cad:.4f} left this week",
                )
                bq.append_event(
                    task_id,
                    "compute_governor_refused",
                    payload={
                        "action": cg.ACTION_DEFER,
                        "reasons": list(reasons),
                        "dispatch_hash": decision.dispatch_hash,
                        "base_sha": base_sha,
                        "counts_toward_budget": False,
                    },
                    db_path=db_path,
                )
                raise LoopError(
                    f"compute governor defers {initiative_id}/{packet_id} at "
                    f"{base_sha[:12]}: " + "; ".join(reasons)
                )
        return decision

    bq.append_event(
        task_id,
        "compute_governor_refused",
        payload={
            "action": decision.action,
            "reasons": list(decision.reasons),
            "dispatch_hash": decision.dispatch_hash,
            "base_sha": base_sha,
            "counts_toward_budget": False,
        },
        db_path=db_path,
    )
    raise LoopError(
        f"compute governor {decision.action}s {initiative_id}/{packet_id} at "
        f"{base_sha[:12]}: " + "; ".join(decision.reasons)
    )


def _governor_settle(
    initiative_id: str,
    packet_id: str,
    *,
    base_sha: str,
    governor_db: Path | None,
    decision: "cg.Decision | None",
    outcome: str,
    attempts: list[dict[str, Any]],
    model: str | None,
    provider: str | None,
    risk_class: str,
    projected_cost_cad: float | None,
    requested_route: str | None,
    override_reason: str | None,
) -> None:
    """Write the receipt for a finished packet run.

    A succeeded run settles the allowance for this base SHA; an exhausted or
    cancelled one does not, because the work is still owed.
    """
    if governor_db is None or decision is None:
        return
    route = decision.route or cg.ROUTE_FREE
    cg.record_receipt(
        governor_db,
        _governor_dispatch(
            initiative_id,
            packet_id,
            base_sha=base_sha,
            risk_class=risk_class,
            requested_route=requested_route,
        ),
        outcome=cg.OUTCOME_SETTLED if outcome == LOOP_SUCCEEDED else cg.OUTCOME_FAILED,
        route=route,
        model=model,
        provider=provider,
        retries=max(len(attempts) - 1, 0),
        estimated_usage_cad=(projected_cost_cad or cg.estimate_pass_cost_cad(route)) * max(len(attempts), 1),
        override_reason=override_reason,
    )


def run_packet(
    initiative_id: str,
    packet_id: str,
    *,
    worker_command: list[str],
    review_command: list[str] | None = None,
    adapter_env: dict[str, str] | None = None,
    worker: str = "packet-loop",
    model: str | None = None,
    provider: str | None = None,
    timeout_seconds: int = 3600,
    validation_timeout_seconds: int = ba.DEFAULT_VALIDATION_TIMEOUT,
    review_timeout_seconds: int = DEFAULT_REVIEW_TIMEOUT,
    deadline_monotonic: float | None = None,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
    heartbeat_seconds: int = DEFAULT_HEARTBEAT_SECONDS,
    max_consecutive_recoveries: int = DEFAULT_MAX_CONSECUTIVE_RECOVERIES,
    repo_root: Path | None = None,
    db_path: Path | None = None,
    governor_db: Path | None = None,
    governor_override: str | None = None,
    governor_risk_class: str = "routine",
    governor_projected_cost_cad: float | None = None,
    governor_requested_route: str | None = None,
    publication_preflight: bool = False,
) -> dict[str, Any]:
    """Run the bounded repair loop for one packet.

    Returns ``{"outcome": "succeeded"|"exhausted"|"cancelled", ...}`` where
    each attempt entry records what happened and why. Raises ``LoopError``
    when infrastructure or durable task state prevents safe execution.

    Passing ``governor_db`` gates the run through the compute governor: a
    packet whose implement pass already settled at this base SHA is refused
    before any model is dispatched. Omitting it leaves the loop ungoverned,
    which is what library callers and tests get by default; the CLI and the
    autonomous runner both pass it.
    """
    effective_adapter_env = dict(adapter_env or {})
    if governor_requested_route == cg.ROUTE_FREE:
        effective_adapter_env = _sanitize_free_adapter_env(effective_adapter_env)

    ba.init_db(db_path)
    try:
        # An open attempt is recoverable only after this liveness probe has
        # durably fenced its worker run as interrupted. Do this before reading
        # task state: a dead running worker is transitioned to blocked here.
        bq.recover_interrupted_runs(db_path=db_path)
    except Exception as exc:
        raise LoopError(
            f"cannot recover interrupted worker runs before starting "
            f"{initiative_id}/{packet_id}: {exc}"
        ) from exc
    bundle_preview = ba.build_context_bundle(initiative_id, packet_id, db_path=db_path)
    task_id = bundle_preview["task_id"]
    initiative_contract = bi.get_initiative(initiative_id, db_path=db_path) or {}
    packet_contract: dict[str, Any] = next(
        (
            packet
            for packet in initiative_contract.get("packets", [])
            if packet.get("packet_id") == packet_id
        ),
        {},
    )

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
        if not ba.list_stale_attempts(initiative_id, packet_id, db_path=db_path):
            raise LoopError(
                f"task {task_id} for {initiative_id}/{packet_id} is blocked "
                "without a stale open attempt; operator release is required"
            )
        reconcile_interrupted_packet(
            initiative_id, packet_id, db_path=db_path, repo_root=repo_root
        )
        task = bq.get_task(task_id, db_path=db_path)
        if task is None or task["state"] != bq.QUEUED:
            raise LoopError(
                f"task {task_id} did not become queued after stale-attempt reconciliation"
            )
    else:
        raise LoopError(
            f"task {task_id} for {initiative_id}/{packet_id} is "
            f"{task['state']}; the loop only starts on a queued task or a "
            "blocked task with a stale attempt"
        )

    try:
        model, provider = bi.resolve_packet_routing(
            initiative_id,
            packet_id,
            model=model,
            provider=provider,
            db_path=db_path,
        )
    except (bi.InitiativeNotFoundError, bi.RoutingPolicyError) as exc:
        raise LoopError(f"durable routing policy rejected execution: {exc}") from exc

    crash_count, crash_reason = _consecutive_identical_crashes(
        task_id, db_path=db_path
    )
    if (
        governor_requested_route in {cg.ROUTE_CHEAP, cg.ROUTE_FRONTIER}
        and crash_count
        and crash_reason.startswith("all configured free ")
        and crash_reason.endswith("providers were unavailable")
    ):
        bq.append_event(
            task_id,
            "recovery_lane_changed",
            payload={
                "from": "free",
                "to": "paid",
                "requested_route": governor_requested_route,
                "cleared_crash_count": crash_count,
                "previous_reason": crash_reason,
            },
            db_path=db_path,
        )
        crash_count, crash_reason = 0, ""
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
        # Truthful closeout: leave the task durably blocked with the real
        # reason instead of queued, so the rollup and the operator both see
        # why the loop stopped. (QUEUED tasks walk the legal state chain.)
        current = bq.get_task(task_id, db_path=db_path)
        if current is not None and current["state"] == bq.QUEUED:
            bq.transition_task(task_id, bq.CLAIMED, db_path=db_path)
            bq.transition_task(task_id, bq.RUNNING, db_path=db_path)
        current = bq.get_task(task_id, db_path=db_path)
        if current is not None and current["state"] == bq.RUNNING:
            bq.transition_task(
                task_id,
                bq.BLOCKED,
                payload={"reason": "recovery_budget_exhausted"},
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

    if governor_requested_route in {cg.ROUTE_CHEAP, cg.ROUTE_FRONTIER}:
        requested_paid, worker, effective_adapter_env = _configure_paid_route(
            governor_requested_route, worker, effective_adapter_env
        )
        model = requested_paid.worker_model
        provider = requested_paid.provider
        governor_projected_cost_cad = requested_paid.projected_cost_cad

    governor_decision = _governor_gate(
        initiative_id,
        packet_id,
        task_id,
        base_sha=base_sha,
        governor_db=governor_db,
        risk_class=governor_risk_class,
        requested_route=governor_requested_route,
        override_reason=governor_override,
        db_path=db_path,
    )
    if (
        governor_requested_route is not None
        and governor_decision is not None
        and governor_decision.route != governor_requested_route
    ):
        if (
            governor_decision.action == cg.ACTION_DOWNGRADE
            and governor_decision.route in {cg.ROUTE_CHEAP, cg.ROUTE_FRONTIER}
        ):
            authorized, worker, effective_adapter_env = _configure_paid_route(
                governor_decision.route, worker, effective_adapter_env
            )
            model = authorized.worker_model
            provider = authorized.provider
            governor_projected_cost_cad = authorized.projected_cost_cad
            bq.append_event(
                task_id,
                "compute_governor_route_downgraded",
                payload={
                    "requested_route": governor_requested_route,
                    "authorized_route": governor_decision.route,
                    "worker_model": authorized.worker_model,
                    "reviewer_model": authorized.reviewer_model,
                    "projected_cost_cad": authorized.projected_cost_cad,
                    "reasons": list(governor_decision.reasons),
                    "base_sha": base_sha,
                    "counts_toward_budget": False,
                },
                db_path=db_path,
            )
        else:
            raise LoopError(
                f"compute governor authorized route {governor_decision.route!r} "
                f"instead of requested route {governor_requested_route!r}"
            )

    history: list[dict[str, Any]] = []
    janitor_passes = 0
    while True:
        if bi.get_initiative_state(initiative_id, db_path=db_path) == bi.INITIATIVE_PAUSED:
            initiative = bi.get_initiative(initiative_id, db_path=db_path) or {}
            return {
                "outcome": LOOP_PAUSED,
                "initiative_id": initiative_id,
                "packet_id": packet_id,
                "task_id": task_id,
                "task_state": (bq.get_task(task_id, db_path=db_path) or {}).get("state"),
                "reason": initiative.get("pause_reason") or "operator pause",
                "attempts": history,
            }

        if _runtime_budget_expired(deadline_monotonic):
            reason = "initiative runtime budget exceeded"
            bi.pause_initiative(initiative_id, reason, db_path=db_path)
            return {
                "outcome": LOOP_PAUSED,
                "initiative_id": initiative_id,
                "packet_id": packet_id,
                "task_id": task_id,
                "task_state": (bq.get_task(task_id, db_path=db_path) or {}).get("state"),
                "reason": reason,
                "attempts": history,
            }

        if publication_preflight and janitor_passes >= bj.JANITOR_MAX_PASSES:
            reason = f"PR janitor exhausted after {bj.JANITOR_MAX_PASSES} passes"
            _governor_settle(
                initiative_id,
                packet_id,
                base_sha=base_sha,
                governor_db=governor_db,
                decision=governor_decision,
                outcome=LOOP_EXHAUSTED,
                attempts=history,
                model=model,
                provider=provider,
                risk_class=governor_risk_class,
                projected_cost_cad=governor_projected_cost_cad,
                requested_route=governor_requested_route,
                override_reason=governor_override,
            )
            return {
                "outcome": LOOP_EXHAUSTED,
                "initiative_id": initiative_id,
                "packet_id": packet_id,
                "task_id": task_id,
                "task_state": (bq.get_task(task_id, db_path=db_path) or {}).get("state"),
                "reason": reason,
                "attempts": history,
            }

        # If a non-repairable attempt consumed the final retry slot, there is
        # no next attempt to prepare. Preserve its worktree exactly as evidence
        # for operator review instead of resetting it merely to discover the
        # budget is exhausted on the following claim.
        if history and not history[-1].get("repairable"):
            if ba.attempt_budget_remaining(initiative_id, packet_id, db_path=db_path) <= 0:
                reason = "attempt budget exhausted; final failed worktree preserved for operator review"
                _governor_settle(
                    initiative_id,
                    packet_id,
                    base_sha=base_sha,
                    governor_db=governor_db,
                    decision=governor_decision,
                    outcome=LOOP_EXHAUSTED,
                    attempts=history,
                    model=model,
                    provider=provider,
                    risk_class=governor_risk_class,
                    projected_cost_cad=governor_projected_cost_cad,
                    requested_route=governor_requested_route,
                    override_reason=governor_override,
                )
                return {
                    "outcome": LOOP_EXHAUSTED,
                    "initiative_id": initiative_id,
                    "packet_id": packet_id,
                    "task_id": task_id,
                    "task_state": (bq.get_task(task_id, db_path=db_path) or {}).get("state"),
                    "reason": reason,
                    "attempts": history,
                }

        # Choose this attempt's worktree disposition from the previous attempt
        # BEFORE anything is durably opened, so a failed cleanup can never
        # strand a new attempt or its lease (P1-2). Only an explicitly
        # repairable previous outcome — deterministic validation failure or a
        # clean reviewer ``request_changes`` verdict, where the post-worker
        # worktree is still bound to the worker result — keeps its dirty tree
        # as repair input for the next attempt (P1-1). Anything else — a
        # worker that crashed/was interrupted mid-execution, or a review
        # execution/mutation/evidence-integrity failure — archives the tree
        # into the failed attempt's artifact dir as evidence and resets so the
        # next attempt starts clean and inherits nothing.
        reuse_dirty_worktree = False
        if history:
            prior = history[-1]
            if prior.get("repairable"):
                reuse_dirty_worktree = True
            else:
                prior_dir = _attempt_dir(task_id, prior["attempt_id"], db_path)
                try:
                    worktree_evidence = archive_and_reset_worktree(
                        worktree_path(task_id, repo_root=repo_root),
                        prior_dir,
                        reset_sha=base_sha,
                    )
                except Exception as exc:
                    _record_infrastructure_failure(
                        task_id,
                        reason=(
                            "clean retry worktree reset failed: "
                            f"{type(exc).__name__}: {exc}"
                        ),
                        phase="clean_retry_worktree",
                        attempt_id=prior["attempt_id"],
                        db_path=db_path,
                    )
                    raise LoopError(
                        f"cannot reset worktree for clean retry after attempt "
                        f"{prior['attempt_no']}: {exc}"
                    ) from exc
                if worktree_evidence.get("state") == "archived_and_reset":
                    bq.append_event(
                        task_id,
                        "worktree_archived_for_clean_retry",
                        payload={
                            "attempt_id": prior["attempt_id"],
                            "attempt_no": prior["attempt_no"],
                            "phase": "clean_retry_worktree",
                        },
                        db_path=db_path,
                    )

        try:
            worktree_preflight = preflight_worktree(task_id, repo_root=repo_root)
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

        if publication_preflight:
            publication_root = Path(worktree_preflight["repo_root"])
            publication_probe = bj.publication_preflight(publication_root)
            detail = (publication_probe.stderr or publication_probe.stdout or "").strip()
            if (
                publication_probe.returncode != 0
                and publication_probe.returncode != PROVIDER_EXHAUSTED_EXIT_CODE
            ):
                suffix = f": {detail}" if detail else ""
                raise LoopError(
                    "publication environment preflight failed unexpectedly "
                    f"(exit {publication_probe.returncode}){suffix}"
                )
            if publication_probe.returncode == PROVIDER_EXHAUSTED_EXIT_CODE:
                reason = "publication environment preflight exited 75" + (
                    f": {detail}" if detail else ""
                )
                _record_infrastructure_failure(
                    task_id,
                    reason=reason,
                    phase="publication_preflight",
                    attempt_id=None,
                    db_path=db_path,
                )
                return {
                    "outcome": LOOP_INFRASTRUCTURE_BLOCKED,
                    "initiative_id": initiative_id,
                    "packet_id": packet_id,
                    "task_id": task_id,
                    "task_state": (bq.get_task(task_id, db_path=db_path) or {}).get("state"),
                    "reason": reason,
                    "attempts": history,
                }

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
            _governor_settle(
                initiative_id,
                packet_id,
                base_sha=base_sha,
                governor_db=governor_db,
                decision=governor_decision,
                outcome=LOOP_EXHAUSTED,
                attempts=history,
                model=model,
                provider=provider,
                risk_class=governor_risk_class,
                projected_cost_cad=governor_projected_cost_cad,
                requested_route=governor_requested_route,
                override_reason=governor_override,
            )
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
        if governor_decision is not None:
            manifest["governor"] = {
                **governor_decision.to_dict(),
                "risk_class": governor_risk_class,
                "requested_route": governor_requested_route,
                "projected_cost_cad": governor_projected_cost_cad,
            }
            write_run_manifest(manifest_path, manifest)

        try:
            worker_timeout_seconds = _bounded_timeout(
                timeout_seconds, deadline_monotonic
            )
            run = run_worker(
                task_id,
                worker_command,
                worker=worker,
                model=model,
                provider=provider,
                timeout_seconds=worker_timeout_seconds,
                lease_seconds=lease_seconds,
                heartbeat_seconds=min(heartbeat_seconds, worker_timeout_seconds),
                repo_root=repo_root,
                db_path=db_path,
                base_sha=base_sha,
                reuse_dirty_worktree=reuse_dirty_worktree,
                extra_env={
                    **effective_adapter_env,
                    "KB_ATTEMPT_ID": str(attempt_id),
                    "KB_BUNDLE_PATH": str(bundle_path),
                    "KB_RESULT_PATH": str(result_path),
                    "KB_CONTEXT_MANIFEST_PATH": str(manifest_path),
                    "KB_WORKER_TIMEOUT_SECONDS": str(worker_timeout_seconds),
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

        if (
            run.get("exit_code") == PROVIDER_EXHAUSTED_EXIT_CODE
            and not run_report.get("changed_paths")
        ):
            return _close_provider_exhaustion(
                initiative_id=initiative_id,
                packet_id=packet_id,
                task_id=task_id,
                attempt=attempt,
                lease=lease,
                entry=entry,
                history=history,
                manifest=manifest,
                manifest_path=manifest_path,
                reason="all configured free worker providers were unavailable",
                phase="worker_provider_exhaustion",
                db_path=db_path,
            )

        failure: str | None = None
        # CP-03: set only when this attempt's failure needs a human decision
        # (scope/identity escalation) rather than a routine retry. Carries
        # structured findings so run_initiative can classify the packet
        # exhaustion without re-deriving them.
        scope_escalation: dict[str, Any] | None = None
        # Whether this attempt's failure leaves a worktree that is safe to
        # reuse as repair input for the next attempt. Set only where the
        # post-worker tree is still bound to the worker result: deterministic
        # validation failure and a clean reviewer ``request_changes`` verdict.
        # Review execution/mutation/evidence-integrity failures are not
        # repairable state and must never feed the next worker.
        repairable = False

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
            _governor_settle(
                initiative_id,
                packet_id,
                base_sha=base_sha,
                governor_db=governor_db,
                decision=governor_decision,
                outcome=LOOP_CANCELLED,
                attempts=history,
                model=model,
                provider=provider,
                risk_class=governor_risk_class,
                projected_cost_cad=governor_projected_cost_cad,
                requested_route=governor_requested_route,
                override_reason=governor_override,
            )
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

        if run["state"] == bq.RUN_SCOPE_VIOLATION:
            violation_paths = list(run_report.get("scope_violations") or [])
            failure = "worker changed files outside the packet's allowed scope"
            scope_escalation = {
                "category": "scope_violation",
                "findings": [
                    {
                        "category": "scope_drift",
                        "field": "changed_paths",
                        "message": f"file outside allowed scope: {path}",
                    }
                    for path in violation_paths
                ],
            }
            entry["scope_violations"] = violation_paths

        identity_findings = bid.verify_worker_identity(
            initiative_id,
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
            # A scope violation on this same attempt already set failure and
            # scope_escalation above; identity is the more specific finding
            # when both fire, but scope_violation's failure text stands so
            # the earlier detection isn't silently discarded.
            if failure is None:
                failure = "worker identity verification failed: " + "; ".join(
                    finding.message for finding in identity_findings
                )
                scope_escalation = {
                    "category": "identity_violation",
                    "findings": entry["identity_findings"],
                }

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

        if (
            failure is None
            and impl is not None
            and impl.get("status") == "completed"
        ):
            try:
                trusted_commit_sha = _commit_completed_worker_changes(
                    expected_worktree,
                    packet_id=packet_id,
                    task_id=task_id,
                    attempt_id=attempt_id,
                )
            except LoopError as exc:
                failure = f"trusted parent commit failed: {exc}"
            else:
                if trusted_commit_sha is not None:
                    entry["trusted_parent_commit_sha"] = trusted_commit_sha

        if failure is None:
            try:
                contract_gate = bcg.evaluate_contract_checks(
                    expected_worktree,
                    base_sha=base_sha,
                    forbidden_symbols=packet_contract.get("forbidden_symbols"),
                    required_symbols=packet_contract.get("required_symbols"),
                    forbidden_paths=packet_contract.get("forbidden_paths"),
                )
            except bcg.ContractGateError as exc:
                failure = f"deterministic contract gate could not run: {exc}"
            else:
                entry["contract_gate"] = contract_gate
                manifest["contract_gate"] = contract_gate
                write_run_manifest(manifest_path, manifest)
                if not contract_gate["passed"]:
                    failure = "deterministic contract gate failed"
                    repairable = True
                    bq.append_event(
                        task_id,
                        "contract_gate_failed",
                        payload={"attempt_id": attempt_id, **contract_gate},
                        db_path=db_path,
                    )

        if failure is None and _runtime_budget_expired(deadline_monotonic):
            failure = "initiative runtime budget exceeded"

        janitor_receipt: dict[str, Any] | None = None
        janitor_error: str | None = None
        janitor_head_before: str | None = None
        janitor_head_after: str | None = None
        janitor_pass_no: int | None = None
        gate: dict[str, Any] | None = None
        if failure is None and publication_preflight:
            janitor_passes += 1
            janitor_pass_no = janitor_passes
            janitor_worktree = worktree_path(task_id, repo_root=repo_root)
            janitor_head_before = worktree_head(janitor_worktree)
            try:
                janitor_receipt = bj.apply_safe_repairs(
                    janitor_worktree,
                    allowed_paths=bundle_preview.get("allowed_paths"),
                    commit_marker=f"[{packet_id}]",
                )
            except bj.SafeRepairError as exc:
                janitor_error = str(exc)
                janitor_receipt = {
                    "changed": False,
                    "changed_paths": [],
                    "commit_sha": None,
                    "error": janitor_error,
                }
            janitor_head_after = worktree_head(janitor_worktree)

        if failure is None:
            extra_commands: list[str] = []
            if publication_preflight:
                if janitor_error is not None:
                    message = shlex.quote(
                        f"PR janitor safe repair failed: {janitor_error}"
                    )
                    extra_commands.append(f"printf '%s\n' {message} >&2; exit 1")
                extra_commands.append(bj.PUBLICATION_GATE_COMMAND)
            validated = ba.run_validation(
                attempt_id,
                cwd=worktree_path(task_id, repo_root=repo_root),
                timeout_seconds=_bounded_timeout(
                    validation_timeout_seconds, deadline_monotonic
                ),
                db_path=db_path,
                extra_commands=extra_commands,
            )
            entry["validation_status"] = validated["validation"]["status"]
            manifest["validation"] = _validation_evidence(validated["validation"])
            if publication_preflight and janitor_pass_no is not None:
                gate = next(
                    (
                        command
                        for command in validated["validation"]["commands"]
                        if command.get("command") == bj.PUBLICATION_GATE_COMMAND
                    ),
                    None,
                )
                gate_status = (
                    "passed" if gate is not None and gate.get("passed") else "failed"
                )
                janitor_event = {
                    "pass_no": janitor_pass_no,
                    "attempt_id": attempt_id,
                    "head_before": janitor_head_before,
                    "head_after": janitor_head_after,
                    "repairs": janitor_receipt,
                    "repair_error": janitor_error,
                    "gate_status": gate_status,
                    "gate_exit_code": gate.get("exit_code") if gate else None,
                    "output_tail": str(gate.get("output_tail", ""))[-2000:]
                    if gate
                    else "",
                }
                entry["pr_janitor"] = janitor_event
                manifest["pr_janitor"] = janitor_event
                bq.append_event(
                    task_id,
                    "pr_janitor_pass",
                    payload=janitor_event,
                    db_path=db_path,
                )
            write_run_manifest(manifest_path, manifest)
            if validated["validation"]["status"] == ba.VALIDATION_FAILED:
                failure = "deterministic validation failed"
                # Validation is a read of the worker's own output — the tree
                # is still bound to the worker result, so it is repair input.
                repairable = True
                # CP-03 failure signature: (validation command, exit code,
                # review finding class) — crude and mechanical by design, see
                # docs/plans/KITTYBUILDER_DAILY_DRIVER_PLAN.md §1.3/§4.4.
                failed_command = next(
                    (
                        c
                        for c in validated["validation"]["commands"]
                        if not c.get("passed")
                    ),
                    None,
                )
                if failed_command is not None:
                    entry["validation_failure"] = {
                        "command": failed_command.get("command"),
                        "exit_code": failed_command.get("exit_code"),
                    }

                if gate is not None and gate.get("exit_code") == PROVIDER_EXHAUSTED_EXIT_CODE:
                    reason = "publication gate exited 75"
                    output_tail = str(gate.get("output_tail", "")).strip()
                    if output_tail:
                        reason += f": {output_tail}"
                    entry["outcome"] = ba.ATTEMPT_CRASHED
                    entry["failure"] = reason
                    entry["repairable"] = False
                    manifest["outcome"] = "crashed"
                    manifest["failure"] = _text_evidence(reason)
                    write_run_manifest(manifest_path, manifest)
                    worktree_evidence = archive_and_reset_worktree(
                        worktree_path(task_id, repo_root=repo_root),
                        attempt_dir,
                        reset_sha=base_sha,
                    )
                    _close_bound_attempt(attempt, lease, ba.ATTEMPT_CRASHED, db_path=db_path)
                    _record_infrastructure_failure(
                        task_id,
                        reason=reason,
                        phase="publication_gate",
                        attempt_id=attempt_id,
                        db_path=db_path,
                    )
                    blocked_task = bq.get_task(task_id, db_path=db_path)
                    if blocked_task is not None and blocked_task["state"] == bq.BLOCKED:
                        bq.operator_release_task(
                            task_id,
                            reason="publication infrastructure unavailable; retry queued",
                            db_path=db_path,
                        )
                    return {
                        "outcome": LOOP_INFRASTRUCTURE_BLOCKED,
                        "initiative_id": initiative_id,
                        "packet_id": packet_id,
                        "task_id": task_id,
                        "task_state": (bq.get_task(task_id, db_path=db_path) or {}).get("state"),
                        "reason": reason,
                        "attempts": history,
                        "worktree": worktree_evidence,
                    }

        if failure is None and _runtime_budget_expired(deadline_monotonic):
            failure = "initiative runtime budget exceeded"

        if failure is None and review_command:
            review_context_path = attempt_dir / "review-context.json"
            review_worktree = worktree_path(task_id, repo_root=repo_root)
            # Bind the reviewer to the packet-cumulative state since the
            # durable base_sha, not only this retry's delta: on a repair retry
            # the retained implementation (committed on an earlier attempt)
            # must be part of what the reviewer approves. The retry-local
            # delta stays in this attempt's run record as per-attempt evidence.
            cumulative = _cumulative_evidence(review_worktree, base_sha)
            review_context = _write_review_context(
                review_context_path,
                task_id=task_id,
                attempt_id=attempt_id,
                review_sha=cumulative["review_sha"],
                diff_sha256=cumulative["diff_sha256"],
                changed_paths=cumulative["changed_paths"],
            )
            manifest["review_context"] = {
                "path": str(review_context_path),
                "base_sha": base_sha,
                "review_sha": review_context["review_sha"],
                "diff_sha256": review_context["diff_sha256"],
                "changed_paths": review_context["changed_paths"],
            }
            write_run_manifest(manifest_path, manifest)
            review_note_path = Path(attempt_dir) / "review-note.md"
            review_error = _run_review_command(
                review_command,
                cwd=worktree_path(task_id, repo_root=repo_root),
                env_extra={
                    **effective_adapter_env,
                    "KB_TASK_ID": str(task_id),
                    "KB_ATTEMPT_ID": str(attempt_id),
                    "KB_BUNDLE_PATH": str(bundle_path),
                    "KB_IMPL_RESULT_PATH": str(result_path),
                    "KB_REVIEW_RESULT_PATH": str(review_path),
                    "KB_REVIEW_NOTE_PATH": str(review_note_path),
                    "KB_CONTEXT_MANIFEST_PATH": str(manifest_path),
                    "KB_REVIEW_CONTEXT_PATH": str(review_context_path),
                    "KB_REVIEW_SHA": str(review_context["review_sha"]),
                    "KB_REVIEW_DIFF_SHA256": str(review_context["diff_sha256"]),
                    "KB_REVIEW_TIMEOUT_SECONDS": str(
                        _bounded_timeout(review_timeout_seconds, deadline_monotonic)
                    ),
                },
                timeout_seconds=_bounded_timeout(
                    review_timeout_seconds, deadline_monotonic
                ),
            )
            if (
                review_error is not None
                and review_error.startswith(
                    f"review command exited {PROVIDER_EXHAUSTED_EXIT_CODE}:"
                )
            ):
                return _close_provider_exhaustion(
                    initiative_id=initiative_id,
                    packet_id=packet_id,
                    task_id=task_id,
                    attempt=attempt,
                    lease=lease,
                    entry=entry,
                    history=history,
                    manifest=manifest,
                    manifest_path=manifest_path,
                    reason="all configured free reviewer providers were unavailable",
                    phase="review_provider_exhaustion",
                    db_path=db_path,
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
                            start_sha=base_sha,
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
                            "review_note": str(review_note_path)
                            if review_note_path.exists()
                            else None,
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
                            # Only a clean request_changes — reviewer exited 0,
                            # produced a valid contract, and the review
                            # evidence validated (tree unchanged since the
                            # worker) — is repair input. Every other verdict
                            # or any review failure leaves ``repairable``
                            # False, so the next worker never inherits a tree
                            # the reviewer could have touched.
                            if review.get("verdict") == "request_changes":
                                repairable = True
                            # CP-03 failure signature component: the set of
                            # finding severities the reviewer raised.
                            entry["review_finding_class"] = sorted(
                                {
                                    f.get("severity")
                                    for f in review.get("findings", [])
                                    if isinstance(f, dict) and f.get("severity")
                                }
                            )

        if failure is None and _runtime_budget_expired(deadline_monotonic):
            failure = "initiative runtime budget exceeded"

        if failure is None:
            # Final success evidence covers the packet cumulatively since the
            # durable base_sha (including implementation retained from earlier
            # repair attempts), while each attempt's run record keeps its own
            # retry-local delta.
            task_worktree = worktree_path(task_id, repo_root=repo_root)
            manifest["cumulative"] = _cumulative_evidence(
                task_worktree, base_sha
            )
            manifest["outcome"] = "succeeded"
            write_run_manifest(manifest_path, manifest)
            _close_bound_attempt(
                attempt, lease, ba.ATTEMPT_SUCCEEDED, db_path=db_path
            )
            entry["outcome"] = ba.ATTEMPT_SUCCEEDED

            # A worker's done marker is the explicit handoff boundary. Remove
            # only after every success gate passes; failed or interrupted work
            # must remain available for inspection and recovery.
            if (task_worktree / "done.txt").is_file():
                remove_worktree(
                    task_id, repo_root=repo_root, discard_done_marker=True
                )
                entry["worktree_cleanup"] = "removed"
            else:
                entry["worktree_cleanup"] = "kept_no_done_marker"

            final_task = bq.get_task(task_id, db_path=db_path)
            _governor_settle(
                initiative_id,
                packet_id,
                base_sha=base_sha,
                governor_db=governor_db,
                decision=governor_decision,
                outcome=LOOP_SUCCEEDED,
                attempts=history,
                model=model,
                provider=provider,
                risk_class=governor_risk_class,
                projected_cost_cad=governor_projected_cost_cad,
                requested_route=governor_requested_route,
                override_reason=governor_override,
            )
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
        entry["repairable"] = repairable
        manifest["outcome"] = "failed"
        manifest["failure"] = _text_evidence(failure)
        write_run_manifest(manifest_path, manifest)
        _close_bound_attempt(
            attempt, lease, ba.ATTEMPT_FAILED, db_path=db_path
        )

        if scope_escalation is not None:
            # CP-03: scope/identity escalation needs a human decision, not
            # more retries against the same worktree — stop the packet here
            # instead of grinding the remaining attempt budget.
            final_task = bq.get_task(task_id, db_path=db_path)
            _governor_settle(
                initiative_id,
                packet_id,
                base_sha=base_sha,
                governor_db=governor_db,
                decision=governor_decision,
                outcome=LOOP_EXHAUSTED,
                attempts=history,
                model=model,
                provider=provider,
                risk_class=governor_risk_class,
                projected_cost_cad=governor_projected_cost_cad,
                requested_route=governor_requested_route,
                override_reason=governor_override,
            )
            return {
                "outcome": LOOP_EXHAUSTED,
                "initiative_id": initiative_id,
                "packet_id": packet_id,
                "task_id": task_id,
                "task_state": final_task["state"] if final_task else None,
                "reason": failure,
                "attempts": history,
                "escalation": scope_escalation,
            }


# NOTE: helper appended temporarily for E03; placement is normalized before commit.
def _commit_completed_worker_changes(
    worktree: Path,
    *,
    packet_id: str,
    task_id: str,
    attempt_id: int,
) -> str | None:
    status = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=worktree,
        capture_output=True,
        text=True,
        check=False,
    )
    if status.returncode != 0:
        raise LoopError((status.stderr or status.stdout or "git status failed").strip())
    if not status.stdout.strip():
        return None
    add = subprocess.run(["git", "add", "-A"], cwd=worktree, capture_output=True, text=True)
    if add.returncode != 0:
        raise LoopError((add.stderr or add.stdout or "git add failed").strip())
    message = (
        f"[{packet_id}] kittybuilder: {task_id} attempt {attempt_id} "
        "(trusted parent)"
    )
    commit = subprocess.run(
        [
            "git", "-c", "user.name=KittyBuilder",
            "-c", "user.email=kittybuilder@localhost",
            "commit", "--quiet", "-m", message,
        ],
        cwd=worktree,
        capture_output=True,
        text=True,
        check=False,
    )
    if commit.returncode != 0:
        raise LoopError((commit.stderr or commit.stdout or "git commit failed").strip())
    return worktree_head(worktree)
