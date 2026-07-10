"""KittyBuilder Phase 1C-alpha — runner shadow mode.

Claims a queue task, creates an isolated git worktree, launches a configured
worker command, heartbeats the lease while it runs, and records everything
(command, PID, timestamps, exit status, branch, worktree, log path, final
report). Shadow mode performs **no GitHub mutations**: no push, no PR, no
comments. Every outcome lands the task in ``blocked`` with a machine-readable
reason so the operator (or Phase 1C-beta) decides what happens next.

Crash safety: if this runner process dies, the lease stops renewing and the
existing recovery scan moves the task to ``blocked(stale_heartbeat)``;
``recover_interrupted_runs`` marks the dead run row. The worktree and log
always survive for inspection — partial progress is never destroyed.
"""

from __future__ import annotations

import os
import signal
import subprocess
import time
from pathlib import Path
from typing import Any

from gateway import builder_queue as bq
from gateway.builder_brief import default_branch_name, render_worker_brief
from gateway.paths import BUILDER_QUEUE_DB

# Arch doc §9: Phase 1C uses a short heartbeat-based lease.
DEFAULT_LEASE_SECONDS = 60
DEFAULT_HEARTBEAT_SECONDS = 10
DEFAULT_TIMEOUT_SECONDS = 3600
_TERM_GRACE_SECONDS = 10

# Task blocked-reasons per run outcome (all shadow-mode exits block the task).
_BLOCK_REASONS = {
    bq.RUN_EXITED: "shadow_run_complete",
    bq.RUN_FAILED: "worker_failed",
    bq.RUN_TIMEOUT: "run_timeout",
    bq.RUN_CANCELLED: "run_cancelled",
}


class RunnerError(RuntimeError):
    """Raised for worktree or run-orchestration failures."""


def _repo_root(repo_root: Path | None) -> Path:
    if repo_root is not None:
        return Path(repo_root)
    out = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=True,
    )
    return Path(out.stdout.strip())


def worktree_path(task_id: str, *, repo_root: Path | None = None) -> Path:
    return _repo_root(repo_root) / ".worktrees" / "kittybuilder" / task_id


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True
    )


def ensure_worktree(
    task_id: str,
    branch: str,
    *,
    repo_root: Path | None = None,
) -> Path:
    """Create (or safely reuse) the deterministic worktree for a task.

    Reuse requires the existing worktree to be on *branch* and completely
    clean; anything else raises — a dirty or ambiguous worktree is never
    overwritten (it may hold a crashed worker's partial progress).
    """
    root = _repo_root(repo_root)
    path = root / ".worktrees" / "kittybuilder" / task_id

    if path.exists():
        head = _git(["symbolic-ref", "--quiet", "--short", "HEAD"], cwd=path)
        current_branch = head.stdout.strip()
        if head.returncode != 0 or current_branch != branch:
            raise RunnerError(
                f"worktree {path} exists but is on "
                f"{current_branch or 'a detached HEAD'!r}, expected {branch!r}; "
                "refusing to reuse. Inspect or clean it explicitly."
            )
        status = _git(["status", "--porcelain=v1", "--untracked-files=all"], cwd=path)
        if status.returncode != 0 or status.stdout.strip():
            raise RunnerError(
                f"worktree {path} is dirty; refusing to overwrite partial "
                "progress. Inspect it, commit/stash, or clean it explicitly."
            )
        return path

    path.parent.mkdir(parents=True, exist_ok=True)

    branch_exists = (
        _git(["rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"], cwd=root)
        .returncode
        == 0
    )
    if branch_exists:
        result = _git(["worktree", "add", str(path), branch], cwd=root)
    else:
        base = "origin/main"
        if _git(["rev-parse", "--verify", "--quiet", base], cwd=root).returncode != 0:
            base = "main"
        result = _git(["worktree", "add", str(path), "-b", branch, base], cwd=root)

    if result.returncode != 0:
        raise RunnerError(
            f"git worktree add failed for {path}: {result.stderr.strip()}"
        )
    return path


def remove_worktree(task_id: str, *, repo_root: Path | None = None) -> Path:
    """Remove a task worktree only if it is clean (conservative cleanup)."""
    root = _repo_root(repo_root)
    path = root / ".worktrees" / "kittybuilder" / task_id
    if not path.exists():
        raise RunnerError(f"no worktree at {path}")

    status = _git(["status", "--porcelain=v1", "--untracked-files=all"], cwd=path)
    if status.returncode != 0 or status.stdout.strip():
        raise RunnerError(
            f"worktree {path} is dirty; refusing to remove. "
            "Commit, stash, or inspect first."
        )
    result = _git(["worktree", "remove", str(path)], cwd=root)
    if result.returncode != 0:
        raise RunnerError(f"git worktree remove failed: {result.stderr.strip()}")
    return path


def _worktree_summary(path: Path) -> dict[str, Any]:
    """Small evidence block for the final report: commits + dirty files."""
    commits = _git(["log", "--oneline", "-5"], cwd=path).stdout.strip()
    dirty = _git(["status", "--porcelain=v1", "--untracked-files=all"], cwd=path)
    dirty_files = [line for line in dirty.stdout.splitlines() if line.strip()]
    return {"recent_commits": commits.splitlines(), "dirty_files": dirty_files}


def _terminate_group(proc: subprocess.Popen[Any]) -> None:
    """SIGTERM the worker's process group, escalate to SIGKILL after grace."""
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        proc.wait(timeout=_TERM_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait()


def run_worker(
    task_id: str,
    command: list[str],
    *,
    worker: str = "local-runner",
    model: str | None = None,
    provider: str | None = None,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
    heartbeat_seconds: int = DEFAULT_HEARTBEAT_SECONDS,
    repo_root: Path | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Claim *task_id*, run *command* in its isolated worktree, record all.

    Returns the final run dict. The task ends in ``blocked`` with a reason
    from the outcome (shadow_run_complete / worker_failed / run_timeout /
    run_cancelled) unless the worker command already transitioned it itself
    (smart workers hold the lease via KB_LEASE_TOKEN and may do so).
    """
    if not command:
        raise ValueError("command must be a non-empty list")

    task = bq.claim_task(task_id, worker, lease_seconds=lease_seconds, db_path=db_path)
    lease_token = task["lease_token"]
    claim_version = task["claim_version"]

    try:
        branch = default_branch_name(task)
        wt_path = ensure_worktree(task_id, branch, repo_root=repo_root)
    except Exception:
        # Nothing started yet — hand the claim back cleanly.
        bq.worker_release_task(task_id, lease_token, claim_version, db_path=db_path)
        raise

    events = bq.list_events(task_id, db_path=db_path)
    pr_links = bq.get_pr_links(task_id, db_path=db_path)
    brief_dir = wt_path / ".kittybuilder"
    brief_dir.mkdir(exist_ok=True)
    brief_path = brief_dir / "brief.md"
    brief_path.write_text(
        render_worker_brief(task, events, pr_links, branch=branch)
    )

    queue_db = Path(db_path) if db_path is not None else BUILDER_QUEUE_DB
    log_dir = queue_db.parent / "runs"
    log_dir.mkdir(parents=True, exist_ok=True)

    run = bq.create_run(
        task_id,
        command,
        worker=worker,
        model=model,
        provider=provider,
        branch=branch,
        worktree_path=str(wt_path),
        log_path="",  # set below once the run ID names the file
        db_path=db_path,
    )
    run_id = run["id"]
    log_path = log_dir / f"{run_id}.log"

    bq.worker_transition_task(
        task_id,
        bq.RUNNING,
        lease_token,
        claim_version,
        payload={"run_id": run_id, "worker": worker},
        db_path=db_path,
    )

    child_env = dict(os.environ)
    # Shadow mode: no ambient GitHub credentials reach the worker.
    child_env.pop("GITHUB_TOKEN", None)
    child_env.pop("GH_TOKEN", None)
    child_env["GIT_TERMINAL_PROMPT"] = "0"
    child_env.update(
        KB_TASK_ID=task_id,
        KB_RUN_ID=run_id,
        KB_BRANCH=branch,
        KB_BRIEF_PATH=str(brief_path),
        KB_LEASE_TOKEN=str(lease_token),
        KB_CLAIM_VERSION=str(claim_version),
    )

    outcome = bq.RUN_FAILED
    exit_code: int | None = None
    started = time.monotonic()

    with open(log_path, "wb") as log_fh:
        proc = subprocess.Popen(
            command,
            cwd=wt_path,
            stdout=log_fh,
            stderr=subprocess.STDOUT,
            env=child_env,
            start_new_session=True,  # own process group → clean termination
        )
        bq.update_run(
            run_id,
            state=bq.RUN_RUNNING,
            pid=proc.pid,
            log_path=str(log_path),
            mark_started=True,
            mark_heartbeat=True,
            db_path=db_path,
        )
        bq.append_event(
            task_id,
            "run_started",
            payload={"run_id": run_id, "pid": proc.pid, "command": command},
            db_path=db_path,
        )

        lost_lease = False
        while True:
            try:
                exit_code = proc.wait(timeout=heartbeat_seconds)
                break
            except subprocess.TimeoutExpired:
                pass

            current = bq.get_run(run_id, db_path=db_path)
            if current and current["state"] == bq.RUN_CANCEL_REQUESTED:
                _terminate_group(proc)
                exit_code = proc.returncode
                outcome = bq.RUN_CANCELLED
                break

            if time.monotonic() - started > timeout_seconds:
                _terminate_group(proc)
                exit_code = proc.returncode
                outcome = bq.RUN_TIMEOUT
                break

            try:
                bq.renew_lease(
                    task_id,
                    lease_token,
                    claim_version,
                    lease_seconds=lease_seconds,
                    db_path=db_path,
                )
                bq.update_run(run_id, mark_heartbeat=True, db_path=db_path)
            except bq.LeaseConflictError:
                # We no longer own the task (operator released / another
                # worker). Stop the worker; do not touch task state.
                _terminate_group(proc)
                exit_code = proc.returncode
                lost_lease = True
                break

    if outcome not in (bq.RUN_CANCELLED, bq.RUN_TIMEOUT):
        outcome = bq.RUN_EXITED if exit_code == 0 else bq.RUN_FAILED

    bq.update_run(
        run_id,
        state=outcome,
        exit_code=exit_code,
        mark_ended=True,
        db_path=db_path,
    )
    bq.append_event(
        task_id,
        f"run_{outcome}",
        payload={"run_id": run_id, "exit_code": exit_code},
        db_path=db_path,
    )

    if lost_lease:
        final = bq.get_run(run_id, db_path=db_path)
        assert final is not None
        return final

    report = {
        "run_id": run_id,
        "outcome": outcome,
        "exit_code": exit_code,
        "branch": branch,
        "worktree": str(wt_path),
        "log_path": str(log_path),
        "worker": worker,
        "model": model,
        "provider": provider,
        "worktree_state": _worktree_summary(wt_path),
    }
    try:
        # Keep the lease alive long enough to record the outcome.
        bq.renew_lease(
            task_id,
            lease_token,
            claim_version,
            lease_seconds=lease_seconds,
            db_path=db_path,
        )
        bq.attach_final_report(
            task_id,
            report,
            lease_token=lease_token,
            claim_version=claim_version,
            db_path=db_path,
        )
        bq.worker_transition_task(
            task_id,
            bq.BLOCKED,
            lease_token,
            claim_version,
            payload={
                "reason": _BLOCK_REASONS[outcome],
                "run_id": run_id,
                "exit_code": exit_code,
            },
            db_path=db_path,
        )
    except (bq.LeaseConflictError, bq.IllegalTransitionError) as exc:
        # A smart worker already moved the task (or ownership changed while
        # we were finishing). The run record and report events still tell
        # the whole story — do not fight over task state.
        bq.append_event(
            task_id,
            "runner_note",
            payload={
                "run_id": run_id,
                "note": f"final transition skipped: {exc}",
            },
            db_path=db_path,
        )

    final = bq.get_run(run_id, db_path=db_path)
    assert final is not None
    return final


def request_cancel(
    run_id: str,
    *,
    kill: bool = False,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Ask a live run to stop: flag it and signal the worker process group.

    The owning runner notices the flag (or the process death) within one
    heartbeat and records the cancelled outcome. ``kill=True`` escalates to
    SIGKILL for a worker that ignores SIGTERM.
    """
    run = bq.get_run(run_id, db_path=db_path)
    if run is None:
        raise bq.RunNotFoundError(f"run not found: {run_id}")
    if run["state"] not in bq.RUN_ACTIVE_STATES:
        raise ValueError(f"run {run_id} is not active (state={run['state']})")

    bq.update_run(
        run_id,
        state=bq.RUN_CANCEL_REQUESTED,
        expected_states=bq.RUN_ACTIVE_STATES,
        db_path=db_path,
    )
    pid = run.get("pid")
    if pid:
        sig = signal.SIGKILL if kill else signal.SIGTERM
        try:
            os.killpg(int(pid), sig)
        except ProcessLookupError:
            pass
    refreshed = bq.get_run(run_id, db_path=db_path)
    assert refreshed is not None
    return refreshed
