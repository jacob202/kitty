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
import shutil
import signal
import subprocess
import time
from pathlib import Path, PurePosixPath
from typing import Any, NoReturn

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
    bq.RUN_SCOPE_VIOLATION: "scope_violation",
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


def _git_output(args: list[str], cwd: Path) -> str:
    result = _git(args, cwd=cwd)
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "no output"
        raise RunnerError(
            f"git {' '.join(args)} failed in {cwd} "
            f"(exit {result.returncode}): {detail}"
        )
    return result.stdout


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
    commits = _git_output(["log", "--oneline", "-5"], cwd=path).strip()
    dirty = _git_output(
        ["status", "--porcelain=v1", "--untracked-files=all"], cwd=path
    )
    dirty_files = [line for line in dirty.splitlines() if line.strip()]
    return {"recent_commits": commits.splitlines(), "dirty_files": dirty_files}


def _changed_paths(path: Path, start_sha: str) -> list[str]:
    """Return committed, staged, unstaged, and untracked paths since dispatch."""
    commands = (
        ["diff", "--name-only", "--no-renames", "-z", f"{start_sha}..HEAD"],
        ["diff", "--name-only", "--no-renames", "-z"],
        ["diff", "--cached", "--name-only", "--no-renames", "-z"],
        ["ls-files", "--others", "--exclude-standard", "-z"],
    )
    changed: set[str] = set()
    for command in commands:
        changed.update(
            item for item in _git_output(command, cwd=path).split("\0") if item
        )
    return sorted(changed)


def _scope_violations(
    changed_paths: list[str],
    allowed_paths: list[str] | None,
) -> list[str]:
    """Return changed paths outside the task's explicit file allowlist."""
    if not allowed_paths:
        return []

    normalized: list[str] = []
    for raw_path in allowed_paths:
        candidate = raw_path.strip().rstrip("/") or "."
        parsed = PurePosixPath(candidate)
        if parsed.is_absolute() or ".." in parsed.parts:
            raise RunnerError(
                f"invalid allowed path {raw_path!r}: use a repo-relative path "
                "without '..'"
            )
        normalized.append(parsed.as_posix())

    def allowed(path: str) -> bool:
        return any(
            prefix == "." or path == prefix or path.startswith(f"{prefix}/")
            for prefix in normalized
        )

    return [path for path in changed_paths if not allowed(path)]


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


def _raise_worker_launch_error(
    exc: OSError,
    *,
    run: dict[str, Any],
    task: dict[str, Any],
    command: list[str],
    branch: str,
    wt_path: Path,
    log_path: Path,
    brief_path: Path,
    lease_token: str,
    claim_version: int,
    worker: str,
    model: str | None,
    provider: str | None,
    db_path: Path | None,
) -> NoReturn:
    """Persist a failed launch, then raise the original failure with context."""
    run_id = str(run["id"])
    start_sha = str(run.get("start_sha") or "")
    inspection_error: str | None = None
    try:
        changed_paths = _changed_paths(wt_path, start_sha)
        scope_violations = _scope_violations(
            changed_paths, task.get("allowed_paths")
        )
        worktree_state = _worktree_summary(wt_path)
    except Exception as inspect_exc:
        changed_paths = []
        scope_violations = []
        inspection_error = f"{type(inspect_exc).__name__}: {inspect_exc}"
        worktree_state = {"inspection_error": inspection_error}

    report = {
        "run_id": run_id,
        "outcome": bq.RUN_FAILED,
        "exit_code": None,
        "error": f"{type(exc).__name__}: {exc}",
        "branch": branch,
        "worktree": str(wt_path),
        "log_path": str(log_path),
        "brief_path": str(brief_path),
        "start_sha": start_sha,
        "command": command,
        "claim_version": claim_version,
        "worker": worker,
        "model": model,
        "provider": provider,
        "changed_paths": changed_paths,
        "scope_violations": scope_violations,
        "worktree_state": worktree_state,
    }
    if inspection_error is not None:
        report["inspection_error"] = inspection_error
    try:
        bq.finalize_run(
            run_id,
            bq.RUN_FAILED,
            exit_code=None,
            report=report,
            lease_token=lease_token,
            claim_version=claim_version,
            block_reason="worker_launch_failed",
            db_path=db_path,
        )
    except Exception as finalize_exc:
        raise RunnerError(
            f"worker launch failed for run {run_id} with command "
            f"{command!r}: {exc}; durable failure recording also failed: "
            f"{finalize_exc}"
        ) from exc
    raise RunnerError(
        f"worker launch failed for run {run_id} with command {command!r}: {exc}"
    ) from exc


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
    for name, seconds in (
        ("timeout_seconds", timeout_seconds),
        ("lease_seconds", lease_seconds),
        ("heartbeat_seconds", heartbeat_seconds),
    ):
        if seconds <= 0:
            raise ValueError(f"{name} must be positive")
    if heartbeat_seconds >= lease_seconds:
        raise ValueError(
            "heartbeat_seconds must be shorter than lease_seconds so the "
            "runner renews ownership before it expires"
        )
    false_command = shutil.which("false")
    if false_command is None:
        raise RunnerError("cannot isolate worker credentials: 'false' not found")

    task = bq.claim_task(task_id, worker, lease_seconds=lease_seconds, db_path=db_path)
    lease_token = task["lease_token"]
    claim_version = task["claim_version"]

    try:
        root = _repo_root(repo_root).resolve()
        configured_repo = task.get("repo_path")
        if configured_repo:
            expected_root = Path(str(configured_repo)).expanduser().resolve()
            if expected_root != root:
                raise RunnerError(
                    f"task {task_id} targets repo {expected_root}, but the "
                    f"runner was invoked for {root}"
                )
        _scope_violations([], task.get("allowed_paths"))
        branch = default_branch_name(task)
        wt_path = ensure_worktree(task_id, branch, repo_root=root)
    except Exception:
        # Nothing started yet — hand the claim back cleanly.
        bq.worker_release_task(task_id, lease_token, claim_version, db_path=db_path)
        raise

    queue_db = Path(db_path) if db_path is not None else BUILDER_QUEUE_DB
    log_dir = queue_db.parent / "runs"
    run: dict[str, Any] | None = None
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        start_sha = _git_output(["rev-parse", "HEAD"], cwd=wt_path).strip()
        run = bq.create_run(
            task_id,
            command,
            lease_token=lease_token,
            claim_version=claim_version,
            worker=worker,
            model=model,
            provider=provider,
            branch=branch,
            worktree_path=str(wt_path),
            start_sha=start_sha,
            log_path="",  # set below once the run ID names the file
            db_path=db_path,
        )
        run_id = str(run["id"])
        run_dir = log_dir / run_id
        run_dir.mkdir()
        log_path = run_dir / "combined.log"
        brief_path = run_dir / "brief.md"
        gh_config_dir = run_dir / "gh-config"
        gh_config_dir.mkdir(mode=0o700)

        events = bq.list_events(task_id, db_path=db_path)
        pr_links = bq.get_pr_links(task_id, db_path=db_path)
        brief_path.write_text(
            render_worker_brief(task, events, pr_links, branch=branch)
        )

        bq.worker_transition_task(
            task_id,
            bq.RUNNING,
            lease_token,
            claim_version,
            payload={"run_id": run_id, "worker": worker},
            db_path=db_path,
        )
    except Exception as exc:
        if run is None:
            try:
                bq.worker_release_task(
                    task_id,
                    lease_token,
                    claim_version,
                    db_path=db_path,
                )
            except Exception as release_exc:
                raise RunnerError(
                    f"prelaunch setup failed for task {task_id}: {exc}; "
                    f"releasing its claim also failed: {release_exc}"
                ) from exc
        else:
            failed_run_id = str(run["id"])
            failed_run_dir = log_dir / failed_run_id
            current_run = bq.get_run(failed_run_id, db_path=db_path)
            failed_outcome = (
                bq.RUN_CANCELLED
                if current_run is not None
                and current_run["state"] == bq.RUN_CANCEL_REQUESTED
                else bq.RUN_FAILED
            )
            report = {
                "run_id": failed_run_id,
                "outcome": failed_outcome,
                "exit_code": None,
                "error": f"{type(exc).__name__}: {exc}",
                "branch": branch,
                "worktree": str(wt_path),
                "log_path": str(failed_run_dir / "combined.log"),
                "brief_path": str(failed_run_dir / "brief.md"),
                "start_sha": run.get("start_sha"),
                "command": command,
                "claim_version": claim_version,
                "worker": worker,
                "model": model,
                "provider": provider,
                "changed_paths": [],
                "scope_violations": [],
            }
            try:
                bq.finalize_run(
                    failed_run_id,
                    failed_outcome,
                    exit_code=None,
                    report=report,
                    lease_token=lease_token,
                    claim_version=claim_version,
                    block_reason="runner_setup_failed",
                    db_path=db_path,
                )
            except Exception as finalize_exc:
                raise RunnerError(
                    f"prelaunch setup failed for run {failed_run_id}: {exc}; "
                    f"durable failure recording also failed: {finalize_exc}"
                ) from exc
        raise RunnerError(
            f"prelaunch setup failed for task {task_id}: "
            f"{type(exc).__name__}: {exc}"
        ) from exc

    assert run is not None

    child_env = dict(os.environ)
    # Shadow mode: no ambient GitHub credentials reach the worker.
    child_env.pop("GITHUB_TOKEN", None)
    child_env.pop("GH_TOKEN", None)
    # Strip SSH agent access — workers must not push via the host SSH agent.
    child_env.pop("SSH_AUTH_SOCK", None)
    child_env.pop("SSH_AGENT_PID", None)
    child_env.pop("GIT_SSH_COMMAND", None)
    child_env.pop("GIT_SSH", None)
    child_env["GH_CONFIG_DIR"] = str(gh_config_dir)
    child_env["GIT_CONFIG_GLOBAL"] = os.devnull
    child_env["GIT_CONFIG_SYSTEM"] = os.devnull
    child_env["GIT_CONFIG_NOSYSTEM"] = "1"
    child_env["GIT_TERMINAL_PROMPT"] = "0"
    child_env["GIT_ASKPASS"] = false_command
    child_env["SSH_ASKPASS"] = false_command
    git_overrides = (
        ("credential.helper", ""),
        ("credential.interactive", "never"),
        ("core.askPass", false_command),
    )
    child_env["GIT_CONFIG_COUNT"] = str(len(git_overrides))
    for index, (key, config_value) in enumerate(git_overrides):
        child_env[f"GIT_CONFIG_KEY_{index}"] = key
        child_env[f"GIT_CONFIG_VALUE_{index}"] = config_value
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

    try:
        log_fh = open(log_path, "wb")
    except OSError as exc:
        _raise_worker_launch_error(
            exc,
            run=run,
            task=task,
            command=command,
            branch=branch,
            wt_path=wt_path,
            log_path=log_path,
            brief_path=brief_path,
            lease_token=lease_token,
            claim_version=claim_version,
            worker=worker,
            model=model,
            provider=provider,
            db_path=db_path,
        )

    with log_fh:
        try:
            proc = subprocess.Popen(
                command,
                cwd=wt_path,
                stdout=log_fh,
                stderr=subprocess.STDOUT,
                env=child_env,
                start_new_session=True,  # own process group → clean termination
            )
        except OSError as exc:
            _raise_worker_launch_error(
                exc,
                run=run,
                task=task,
                command=command,
                branch=branch,
                wt_path=wt_path,
                log_path=log_path,
                brief_path=brief_path,
                lease_token=lease_token,
                claim_version=claim_version,
                worker=worker,
                model=model,
                provider=provider,
                db_path=db_path,
            )
        lost_lease = False
        cancelled_before_start = False
        control_error: Exception | None = None
        try:
            process_identity = bq.capture_process_identity(proc.pid)
            bq.update_run(
                run_id,
                state=bq.RUN_RUNNING,
                pid=proc.pid,
                process_identity=process_identity,
                log_path=str(log_path),
                mark_started=True,
                mark_heartbeat=True,
                expected_states=frozenset({bq.RUN_STARTING}),
                db_path=db_path,
            )
        except bq.RunStateConflictError as exc:
            try:
                current = bq.get_run(run_id, db_path=db_path)
            except Exception as read_exc:
                current = None
                control_error = exc
                control_error.__notes__ = [
                    f"also, get_run failed: {type(read_exc).__name__}: {read_exc}"
                ]
            if current is not None and current["state"] == bq.RUN_CANCEL_REQUESTED:
                outcome = bq.RUN_CANCELLED
                cancelled_before_start = True
            elif control_error is None:
                control_error = exc
            _terminate_group(proc)
            exit_code = proc.returncode
        except Exception as exc:
            _terminate_group(proc)
            exit_code = proc.returncode
            control_error = exc

        if not cancelled_before_start and control_error is None:
            try:
                bq.append_event(
                    task_id,
                    "run_started",
                    payload={"run_id": run_id, "pid": proc.pid, "command": command},
                    run_id=run_id,
                    db_path=db_path,
                )

                while True:
                    try:
                        exit_code = proc.wait(timeout=heartbeat_seconds)
                        break
                    except subprocess.TimeoutExpired:
                        pass

                    current = bq.get_run(run_id, db_path=db_path)
                    if current is None:
                        raise RuntimeError(
                            f"run {run_id} disappeared during heartbeat"
                        )
                    if current["state"] == bq.RUN_CANCEL_REQUESTED:
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
            except Exception as exc:
                _terminate_group(proc)
                exit_code = proc.returncode
                control_error = exc

    # Fence once more after process exit. A cancellation signal can make the
    # child exit before the heartbeat loop observes that the task lease was
    # stolen; durable ownership must take priority over the run flag.
    if not lost_lease:
        try:
            bq.renew_lease(
                task_id,
                lease_token,
                claim_version,
                lease_seconds=lease_seconds,
                db_path=db_path,
            )
        except bq.LeaseConflictError:
            lost_lease = True
        except Exception as exc:
            if control_error is None:
                control_error = exc

    if lost_lease:
        outcome = bq.RUN_LEASE_LOST

    # Re-check a requested cancellation if we exited the loop because the
    # process died (rather than because we observed the flag). request_cancel
    # SIGTERMs the worker's process group, so a short-lived worker can be
    # killed by the cancel signal *before* the loop's TimeoutExpired branch
    # gets a chance to see RUN_CANCEL_REQUESTED. Without this re-check, that
    # process death is misclassified as RUN_FAILED (the SIGTERM exit code is
    # non-zero), turning a legitimate cancellation into a spurious failure.
    # We must NOT do this when we lost the lease — that's an ownership change,
    # not a cancellation, and should be classified by exit code below.
    if outcome == bq.RUN_FAILED and not lost_lease and control_error is None:
        try:
            final_check = bq.get_run(run_id, db_path=db_path)
        except Exception as exc:
            control_error = exc
        else:
            if final_check and final_check["state"] == bq.RUN_CANCEL_REQUESTED:
                outcome = bq.RUN_CANCELLED

    if control_error is not None and not lost_lease:
        outcome = bq.RUN_FAILED
    elif outcome not in (bq.RUN_CANCELLED, bq.RUN_TIMEOUT, bq.RUN_LEASE_LOST):
        outcome = bq.RUN_EXITED if exit_code == 0 else bq.RUN_FAILED

    start_sha = str(run.get("start_sha") or "")
    if not start_sha and control_error is None:
        control_error = RunnerError(f"run {run_id} has no recorded start SHA")
    try:
        changed_paths = _changed_paths(wt_path, start_sha)
        scope_violations = _scope_violations(
            changed_paths,
            task.get("allowed_paths"),
        )
        worktree_state = _worktree_summary(wt_path)
    except Exception as exc:
        if control_error is None:
            control_error = exc
        changed_paths = []
        scope_violations = []
        worktree_state = {"inspection_error": f"{type(exc).__name__}: {exc}"}

    if control_error is not None and outcome != bq.RUN_LEASE_LOST:
        outcome = bq.RUN_FAILED
    elif scope_violations and outcome != bq.RUN_LEASE_LOST:
        outcome = bq.RUN_SCOPE_VIOLATION

    report = {
        "run_id": run_id,
        "outcome": outcome,
        "exit_code": exit_code,
        "branch": branch,
        "worktree": str(wt_path),
        "log_path": str(log_path),
        "brief_path": str(brief_path),
        "start_sha": start_sha,
        "command": command,
        "claim_version": claim_version,
        "worker": worker,
        "model": model,
        "provider": provider,
        "changed_paths": changed_paths,
        "scope_violations": scope_violations,
        "worktree_state": worktree_state,
    }
    if control_error is not None:
        report["error"] = f"{type(control_error).__name__}: {control_error}"
    final = bq.finalize_run(
        run_id,
        outcome,
        exit_code=exit_code,
        report=report,
        lease_token=lease_token,
        claim_version=claim_version,
        block_reason=(
            "runner_control_failed"
            if control_error is not None
            else _BLOCK_REASONS.get(outcome)
        ),
        db_path=db_path,
    )
    if control_error is not None:
        raise RunnerError(
            f"runner monitoring failed for run {run_id}; durable state is "
            f"{final['state']}: {type(control_error).__name__}: {control_error}"
        ) from control_error
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
    signal_sent = False
    signal_status = "process_not_started"
    if pid:
        expected_identity = run.get("process_identity")
        current_identity = bq.capture_process_identity(int(pid))
        if expected_identity is None:
            signal_status = "process_identity_missing"
        elif current_identity != expected_identity:
            signal_status = "process_identity_mismatch"
        else:
            sig = signal.SIGKILL if kill else signal.SIGTERM
            try:
                os.killpg(int(pid), sig)
                signal_sent = True
                signal_status = "signal_sent"
            except ProcessLookupError:
                signal_status = "process_not_found"
            except OSError as exc:
                raise RunnerError(
                    f"cancellation recorded for run {run_id}, but signaling "
                    f"process group {pid} failed: {exc}"
                ) from exc
    refreshed = bq.get_run(run_id, db_path=db_path)
    if refreshed is None:
        raise bq.RunNotFoundError(
            f"run {run_id} disappeared after finalize_run"
        )
    refreshed["signal_sent"] = signal_sent
    refreshed["signal_status"] = signal_status
    return refreshed
