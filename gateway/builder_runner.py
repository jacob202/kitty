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

Phase 2 upgrade — context injection:
- ``inject_worker_context`` reads task/events/PR links, builds a context
  manifest via ``builder_context.build_context_manifest``, writes it to the
  run directory, and returns ``extra_env`` entries (KB_CONTEXT_BUNDLE_PATH,
  KB_CONTEXT_MANIFEST_PATH) that ``run_worker`` adds to the child env.
- ``validate_worker_context`` reads the manifest back after the worker exits
  and confirms it has not been tampered with.

Companion wiring:
- ``run_agent_preset`` spawns an ``agent_runner`` agent (explorer / planner /
  coder / reviewer / researcher) for a builder task, bridging the 5 presets
  that were previously disconnected from the queue lifecycle.
"""

from __future__ import annotations

import argparse
import datetime as _datetime
import hashlib
import json
import logging
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path, PurePosixPath
from typing import Any, NoReturn

from gateway import agent_workspace as agent_workspace
from gateway import builder_execution_boundary as beb
from gateway import builder_queue as bq
from gateway import builder_scope as bs
from gateway.builder_brief import default_branch_name, render_worker_brief
from gateway.builder_context import build_context_manifest, write_run_manifest
from gateway.models.builder import AgentPreset, AgentPresetConfig, WorkerContextBundle
from gateway.paths import BUILDER_QUEUE_DB

logger = logging.getLogger("kitty.builder_runner")

# Arch doc §9: Phase 1C uses a short heartbeat-based lease.
DEFAULT_LEASE_SECONDS = 60
DEFAULT_HEARTBEAT_SECONDS = 10
DEFAULT_TIMEOUT_SECONDS = 3600
_GIT_TIMEOUT_SECONDS = 15
_WORKTREE_ADD_TIMEOUT_SECONDS = 120
_TERM_GRACE_SECONDS = 10

# Task blocked-reasons per run outcome (all shadow-mode exits block the task).
_BLOCK_REASONS = {
    bq.RUN_EXITED: "shadow_run_complete",
    bq.RUN_FAILED: "worker_failed",
    bq.RUN_TIMEOUT: "run_timeout",
    bq.RUN_CANCELLED: "run_cancelled",
    bq.RUN_SCOPE_VIOLATION: "scope_violation",
}


# Env vars the runner strips for credential isolation; extra_env (KB-S3b)
# may never re-supply them.
_EXTRA_ENV_BLOCKED = frozenset(
    {
        "GITHUB_TOKEN", "GH_TOKEN", "SSH_AUTH_SOCK", "SSH_AGENT_PID",
        "GIT_SSH_COMMAND", "GIT_SSH", "GH_CONFIG_DIR", "GIT_ASKPASS",
        "SSH_ASKPASS",
    }
)


class RunnerError(RuntimeError):
    """Raised for worktree or run-orchestration failures."""


def _existing_parent(path: Path) -> Path:
    """Return the nearest existing parent for a path we may create later."""
    candidate = path
    while not candidate.exists() and candidate != candidate.parent:
        candidate = candidate.parent
    return candidate


def _require_writable_directory(path: Path, label: str) -> None:
    """Fail before a run when a required directory cannot be used safely."""
    existing = _existing_parent(path)
    if not existing.is_dir():
        raise RunnerError(f"{label} parent is not a directory: {existing}")
    if not os.access(existing, os.W_OK | os.X_OK):
        raise RunnerError(f"{label} is not writable/executable: {existing}")
    if path.exists() and not path.is_dir():
        raise RunnerError(f"{label} exists but is not a directory: {path}")


def preflight_worktree(
    task_id: str, *, repo_root: Path | None = None
) -> dict[str, str]:
    """Check worktree and Git metadata prerequisites without mutating state.

    This is intentionally separate from ``ensure_worktree``: callers use it
    before opening an implementation attempt so an infrastructure failure does
    not consume the packet's attempt budget.
    """
    root = _repo_root(repo_root)
    if not task_id or "/" in task_id or "\\" in task_id:
        raise RunnerError(f"invalid builder task id for preflight: {task_id!r}")

    _require_writable_directory(root, "repository root")
    worktree_root = root / ".worktrees" / "kittybuilder"
    _require_writable_directory(worktree_root, "Builder worktree root")

    metadata_paths: dict[str, str] = {}
    for flag in ("--git-common-dir", "--git-path refs/heads", "--git-path worktrees"):
        result = _git(["rev-parse", flag], cwd=root)
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or "no output"
            raise RunnerError(
                f"git metadata preflight failed for {flag}: {detail}"
            )
        raw = result.stdout.strip()
        path = Path(raw)
        if not path.is_absolute():
            path = root / path
        _require_writable_directory(path, f"Git metadata ({flag})")
        metadata_paths[flag] = str(path)

    return {
        "repo_root": str(root),
        "worktree_root": str(worktree_root),
        **{f"git_{key.replace(' ', '_').replace('/', '_')}": value
           for key, value in metadata_paths.items()},
    }


def _repo_root(repo_root: Path | None) -> Path:
    if repo_root is not None:
        return Path(repo_root)
    runtime_override = os.environ.get("KITTY_BUILDER_REPO_ROOT")
    if runtime_override:
        return Path(runtime_override).expanduser().resolve()
    out = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    return Path(out.stdout.strip())


def worktree_path(task_id: str, *, repo_root: Path | None = None) -> Path:
    return _repo_root(repo_root) / ".worktrees" / "kittybuilder" / task_id


_MAX_SYMLINK_HOPS = 16


def _interpreter_hops(python: Path) -> list[Path]:
    """Return every path the interpreter symlink chain passes through.

    Seatbelt authorises an ``execve`` against each name in the chain as
    written, not against the final real path, so a venv whose interpreter
    points through an alias directory (uv installs ``cpython-3.12-*`` as a
    symlink to ``cpython-3.12.14-*``) is denied unless the alias hop is
    allowed too.
    """
    hops: list[Path] = []
    seen: set[Path] = set()
    current = python.absolute()
    for _ in range(_MAX_SYMLINK_HOPS):
        if current in seen:
            break
        seen.add(current)
        hops.append(current)
        if not current.is_symlink():
            break
        target = Path(os.readlink(current))
        current = target if target.is_absolute() else (current.parent / target)
    return hops


def _validation_toolchain(repo_root: Path) -> tuple[Path | None, list[Path]]:
    """Return the repo validation venv and read-only runtime roots, if present."""
    for name in ("venv", ".venv"):
        venv = (repo_root / name).resolve()
        python = venv / "bin" / "python"
        if not python.exists():
            continue
        read_roots = [venv]
        for hop in _interpreter_hops(python):
            read_roots.append(hop.parent.parent)
        return venv, list(dict.fromkeys(read_roots))
    return None, []


def _git(
    args: list[str],
    cwd: Path,
    *,
    timeout_seconds: int = _GIT_TIMEOUT_SECONDS,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
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



def _cleanup_timed_out_worktree(root: Path, path: Path) -> None:
    """Remove only an incomplete worktree created by this failed add."""
    if path.exists():
        _git(
            ["worktree", "unlock", str(path)],
            cwd=root,
            timeout_seconds=_GIT_TIMEOUT_SECONDS,
        )
        removed = _git(
            ["worktree", "remove", "--force", str(path)],
            cwd=root,
            timeout_seconds=_WORKTREE_ADD_TIMEOUT_SECONDS,
        )
        if removed.returncode != 0 and path.exists():
            shutil.rmtree(path)
    _git(
        ["worktree", "prune"],
        cwd=root,
        timeout_seconds=_WORKTREE_ADD_TIMEOUT_SECONDS,
    )


def ensure_worktree(
    task_id: str,
    branch: str,
    *,
    repo_root: Path | None = None,
    base_sha: str | None = None,
    reuse_dirty: bool = False,
) -> Path:
    """Create (or safely reuse) the deterministic worktree for a task.

    Reuse requires the existing worktree to be on *branch* and, unless
    ``reuse_dirty`` is set, completely clean; anything else raises — a dirty
    or ambiguous worktree is never overwritten (it may hold a crashed
    worker's partial progress). ``reuse_dirty`` is an explicit opt-in for the
    repair loop only: the builder loop has already decided the dirty tree is
    the deliberate continuation of a prior rejected implementation, so
    reusing it does not overwrite anything. The branch check always holds;
    a wrong-branch tree is never reusable. A nonzero ``git status`` exit is an
    infrastructure failure and always raises; ``reuse_dirty`` accepts only
    successful status output that truthfully reports the tree as dirty.
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
        status = _git(
            [
                "status",
                "--porcelain=v1",
                "--untracked-files=all",
                "--",
                ".",
                f":(exclude){bs.OPENCODE_CONTINUATION_RESIDUE_PREFIX}**",
            ],
            cwd=path,
        )
        if status.returncode != 0:
            detail = status.stderr.strip() or status.stdout.strip() or "no output"
            raise RunnerError(
                f"git status failed in {path} (exit {status.returncode}): {detail}"
            )
        if status.stdout.strip():
            if reuse_dirty:
                return path
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
    try:
        if branch_exists:
            result = _git(
                ["worktree", "add", str(path), branch],
                cwd=root,
                timeout_seconds=_WORKTREE_ADD_TIMEOUT_SECONDS,
            )
        else:
            base = base_sha
            if base is None:
                base = "origin/main"
                if (
                    _git(["rev-parse", "--verify", "--quiet", base], cwd=root).returncode
                    != 0
                ):
                    base = "main"
            if _git(["rev-parse", "--verify", "--quiet", base], cwd=root).returncode != 0:
                raise RunnerError(
                    f"cannot create worktree {path}: base {base!r} does not exist"
                )
            result = _git(
                ["worktree", "add", str(path), "-b", branch, base],
                cwd=root,
                timeout_seconds=_WORKTREE_ADD_TIMEOUT_SECONDS,
            )
    except subprocess.TimeoutExpired as exc:
        _cleanup_timed_out_worktree(root, path)
        raise RunnerError(
            f"git worktree add timed out for {path} after "
            f"{_WORKTREE_ADD_TIMEOUT_SECONDS} seconds"
        ) from exc

    if result.returncode != 0:
        raise RunnerError(
            f"git worktree add failed for {path}: {result.stderr.strip()}"
        )
    return path


def remove_worktree(
    task_id: str,
    *,
    repo_root: Path | None = None,
    discard_done_marker: bool = False,
) -> Path:
    """Remove a task worktree, optionally discarding its lone done marker.

    ``done.txt`` is an ephemeral worker handoff marker, not product output.
    Cleanup may remove exactly that one untracked file; every other dirty
    state, including a modified or tracked marker, still fails loudly.
    """
    root = _repo_root(repo_root)
    path = root / ".worktrees" / "kittybuilder" / task_id
    if not path.exists():
        raise RunnerError(f"no worktree at {path}")

    status = _git(["status", "--porcelain=v1", "--untracked-files=all"], cwd=path)
    if discard_done_marker and status.stdout.splitlines() == ["?? done.txt"]:
        try:
            (path / "done.txt").unlink()
        except OSError as exc:
            raise RunnerError(
                f"cannot remove done marker {path / 'done.txt'}: {exc}"
            ) from exc
        status = _git(
            ["status", "--porcelain=v1", "--untracked-files=all"], cwd=path
        )
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


def _diff_sha256(path: Path, start_sha: str) -> str:
    """Hash the complete observable worktree diff since dispatch.

    Git's binary diff output covers committed, staged, and unstaged tracked
    changes. Untracked files are appended with explicit path/length framing so
    two different file sets cannot produce the same digest by concatenation.
    The digest is evidence only; it never substitutes for the changed-path
    allowlist check.
    """
    digest = hashlib.sha256()
    for label, args in (
        (b"committed", ["diff", "--binary", f"{start_sha}..HEAD"]),
        (b"unstaged", ["diff", "--binary"]),
        (b"staged", ["diff", "--cached", "--binary"]),
    ):
        result = subprocess.run(
            ["git", *args], cwd=path, capture_output=True, check=False, timeout=30
        )
        if result.returncode != 0:
            detail = result.stderr.decode(errors="replace").strip() or "no output"
            raise RunnerError(
                f"git {' '.join(args)} failed in {path} "
                f"(exit {result.returncode}): {detail}"
            )
        digest.update(label)
        digest.update(len(result.stdout).to_bytes(8, "big"))
        digest.update(result.stdout)

    untracked = _git_output(
        ["ls-files", "--others", "--exclude-standard", "-z"], cwd=path
    ).split("\0")
    for raw in sorted(item for item in untracked if item):
        file_path = path / raw
        if not file_path.is_file():
            raise RunnerError(f"untracked path is not a regular file: {file_path}")
        content = file_path.read_bytes()
        encoded_path = raw.encode("utf-8")
        digest.update(b"untracked")
        digest.update(len(encoded_path).to_bytes(8, "big"))
        digest.update(encoded_path)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def archive_and_reset_worktree(
    path: Path,
    evidence_dir: Path,
    *,
    reset_sha: str | None = None,
) -> dict[str, Any]:
    """Preserve failed-attempt changes, then return to a clean base.

    When ``reset_sha`` is provided, evidence is cumulative from that durable
    packet base and committed worker changes are reset too. This prevents a
    non-repairable retry from silently inheriting commits made by a crashed or
    orphaned worker. Without ``reset_sha`` the historical HEAD-relative
    behavior is preserved for callers that only need to clear dirty state.
    """
    if not path.exists():
        return {"state": "missing", "patch_path": None}

    status = _git_output(
        ["status", "--porcelain=v1", "--untracked-files=all"], cwd=path
    )
    current_head = worktree_head(path)
    reset_target = reset_sha or current_head
    if not status.strip() and current_head == reset_target:
        return {"state": "clean", "patch_path": None}

    evidence_dir.mkdir(parents=True, exist_ok=True)
    _git_output(["add", "-A"], cwd=path)
    patch = _git_output(["diff", "--cached", reset_target], cwd=path)
    patch_path = evidence_dir / "crashed-worktree.patch"
    patch_path.write_text(patch, encoding="utf-8")
    (evidence_dir / "crashed-worktree-status.txt").write_text(
        status, encoding="utf-8"
    )
    (evidence_dir / "crashed-worktree-head.txt").write_text(
        f"{current_head}\n", encoding="utf-8"
    )
    _git_output(["reset", "--hard", reset_target], cwd=path)
    _git_output(["clean", "-fd"], cwd=path)
    return {"state": "archived_and_reset", "patch_path": str(patch_path)}


def worktree_head(path: Path) -> str:
    """Return the exact commit currently checked out in a worker worktree."""
    return _git_output(["rev-parse", "HEAD"], cwd=path).strip()


def worktree_diff_sha256(path: Path, start_sha: str) -> str:
    """Return the stable digest used to bind reviewer evidence to a diff."""
    return _diff_sha256(path, start_sha)


def worktree_changed_paths(path: Path, start_sha: str) -> list[str]:
    """Return every path changed since *start_sha* (committed, staged, dirty).

    The packet-cumulative counterpart to ``run_worker``'s per-run
    ``changed_paths``, which is measured from the retry-local HEAD at run
    start. Callers that own a durable base SHA (the builder loop's review and
    final-success evidence) use this so the final state binds to the packet
    base rather than only the latest retry's delta, while the per-attempt
    delta stays in each run record.
    """
    return _changed_paths(path, start_sha)


# Residue every attempt may legitimately touch outside its allowlist (repo
# session-state convention, the runner's own worker-staging files) is
# canonical in builder_scope.is_expected_residue — builder_identity's own
# independent scope check calls the same function, and the two diverging
# was itself a CP-08 dogfood finding (a worker that dutifully updated
# .claude/STATE.md per CLAUDE.md convention failed identity verification
# because that check didn't know about the exemption this one has).
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

    return [
        path
        for path in changed_paths
        if not allowed(path) and not bs.is_expected_residue(path)
    ]


def _scope_snapshot(
    path: Path,
    start_sha: str,
    allowed_paths: list[str] | None,
) -> tuple[list[str], list[str]]:
    """Capture the current changed-path set and any scope violations."""
    changed_paths = _changed_paths(path, start_sha)
    return changed_paths, _scope_violations(changed_paths, allowed_paths)


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
        diff_sha256 = _diff_sha256(wt_path, start_sha)
        scope_violations = _scope_violations(
            changed_paths, task.get("allowed_paths")
        )
        worktree_state = _worktree_summary(wt_path)
    except Exception as inspect_exc:
        changed_paths = []
        diff_sha256 = None
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
        "diff_sha256": diff_sha256,
        "worker_started": False,
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


# ---------------------------------------------------------------------------
# Phase 2 — Context injection
# ---------------------------------------------------------------------------


def inject_worker_context(
    task_id: str,
    run_id: str,
    *,
    branch: str,
    worker: str = "local-runner",
    model: str | None = None,
    provider: str | None = None,
    allowed_paths: list[str] | None = None,
    acceptance_criteria: list[str] | None = None,
    agent_preset: str | None = None,
    db_path: Path | None = None,
    repo_root: Path | None = None,
) -> tuple[dict[str, str], WorkerContextBundle]:
    """Build and persist a context manifest, returning extra_env entries.

    Reads the task's events and PR links, builds a ``build_context_manifest``
    with allowed_paths, writes it as a run manifest, and returns the env vars
    the worker needs to locate the context at runtime.

    Returns (extra_env, context_bundle) where extra_env includes
    KB_CONTEXT_BUNDLE_PATH and KB_CONTEXT_MANIFEST_PATH.
    """
    queue_db = Path(db_path) if db_path is not None else BUILDER_QUEUE_DB
    run_dir = queue_db.parent / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    bundle_path = run_dir / "context-bundle.json"
    manifest_path = run_dir / "context-manifest.json"

    context: dict[str, Any] = {
        "task_id": task_id,
        "run_id": run_id,
        "branch": branch,
        "worker": worker,
        "model": model,
        "provider": provider,
        "allowed_paths": allowed_paths or [],
        "acceptance_criteria": acceptance_criteria or [],
        "agent_preset": agent_preset,
    }
    if agent_preset is not None:
        try:
            context["agent_preset"] = AgentPreset(agent_preset).value
        except ValueError:
            pass

    bundle_path.write_text(
        json.dumps(context, indent=2, sort_keys=True), encoding="utf-8"
    )

    root = Path(repo_root) if repo_root is not None else Path.cwd()
    manifest = build_context_manifest(root, bundle_path, allowed_paths=allowed_paths)
    write_run_manifest(manifest_path, manifest)

    try:
        bq.list_events(task_id, db_path=db_path)
        bq.get_pr_links(task_id, db_path=db_path)
    except Exception:
        logger.warning(
            "Failed to fetch events/pr_links for task %s — "
            "context bundle will be built without event history",
            task_id,
        )

    context_bundle = WorkerContextBundle(
        task_id=task_id,
        run_id=run_id,
        branch=branch,
        brief_path=str(run_dir / "brief.md"),
        bundle_path=str(bundle_path),
        result_path=str(run_dir / "implementation.json"),
        context_manifest_path=str(manifest_path),
        allowed_paths=allowed_paths or [],
        acceptance_criteria=acceptance_criteria or [],
        agent_preset=AgentPreset(agent_preset) if agent_preset and agent_preset in {p.value for p in AgentPreset} else None,
        model=model,
        provider=provider,
    )

    extra_env = {
        "KB_CONTEXT_BUNDLE_PATH": str(bundle_path),
        "KB_CONTEXT_MANIFEST_PATH": str(manifest_path),
    }
    return extra_env, context_bundle


def validate_worker_context(
    task_id: str,
    run_id: str,
    *,
    db_path: Path | None = None,
) -> list[str]:
    """Validate that the context manifest is intact after a worker run.

    Returns a list of validation issues (empty if context is valid).
    """
    queue_db = Path(db_path) if db_path is not None else BUILDER_QUEUE_DB
    run_dir = queue_db.parent / "runs" / run_id
    bundle_path = run_dir / "context-bundle.json"
    manifest_path = run_dir / "context-manifest.json"

    issues: list[str] = []

    if not bundle_path.is_file():
        issues.append(f"context bundle missing: {bundle_path}")
    else:
        try:
            parsed = json.loads(bundle_path.read_text(encoding="utf-8"))
            if not isinstance(parsed, dict):
                issues.append("context bundle is not a JSON object")
            elif parsed.get("task_id") != task_id:
                issues.append(
                    f"context bundle task_id mismatch: "
                    f"{parsed.get('task_id')!r} != {task_id!r}"
                )
        except (OSError, json.JSONDecodeError) as exc:
            issues.append(f"context bundle unreadable: {exc}")

    if not manifest_path.is_file():
        issues.append(f"context manifest missing: {manifest_path}")
    else:
        try:
            parsed = json.loads(manifest_path.read_text(encoding="utf-8"))
            if not isinstance(parsed, dict):
                issues.append("context manifest is not a JSON object")
        except (OSError, json.JSONDecodeError) as exc:
            issues.append(f"context manifest unreadable: {exc}")

    return issues


# ---------------------------------------------------------------------------
# Companion wiring — agent preset dispatch
# ---------------------------------------------------------------------------


AGENT_PRESET_CONFIGS: dict[AgentPreset, AgentPresetConfig] = {
    AgentPreset.explorer: AgentPresetConfig(
        preset=AgentPreset.explorer,
        description="Search and discover — wide research, finding sources, exploring topics",
        system_prompt=(
            "You are an explorer agent for Kitty. Your job is research and discovery.\n"
            "Given a goal, search broadly, find relevant information, and return a "
            "concise summary of what you found with sources."
        ),
        max_iterations=3,
        temperature=0.5,
        timeout_seconds=300,
    ),
    AgentPreset.planner: AgentPresetConfig(
        preset=AgentPreset.planner,
        description="Break down a complex goal into ordered, actionable steps",
        system_prompt=(
            "You are a planner agent for Kitty. Your job is to break down complex "
            "goals into clear, ordered, actionable steps.\n"
            "For each step, include: what needs to happen, dependencies, and estimated effort."
        ),
        max_iterations=2,
        temperature=0.4,
        timeout_seconds=300,
    ),
    AgentPreset.coder: AgentPresetConfig(
        preset=AgentPreset.coder,
        description="Analyze and implement code changes",
        system_prompt=(
            "You are a coder agent for Kitty. Your job is to analyze code and "
            "propose or implement changes.\n"
            "Explain your reasoning. Show the code changes clearly."
        ),
        max_iterations=5,
        temperature=0.2,
        timeout_seconds=600,
    ),
    AgentPreset.reviewer: AgentPresetConfig(
        preset=AgentPreset.reviewer,
        description="Review code or output for issues and suggest improvements",
        system_prompt=(
            "You are a reviewer agent for Kitty. Your job is to examine work "
            "and identify issues, risks, and improvement opportunities.\n"
            "Be constructive. Flag real problems, don't nitpick."
        ),
        max_iterations=2,
        temperature=0.3,
        timeout_seconds=300,
    ),
    AgentPreset.researcher: AgentPresetConfig(
        preset=AgentPreset.researcher,
        description="Deep technical research with structured output",
        system_prompt=(
            "You are a researcher agent for Kitty. Your job is deep technical research.\n"
            "Analyze the topic thoroughly. Provide structured output."
        ),
        max_iterations=4,
        temperature=0.4,
        timeout_seconds=600,
    ),
}


async def run_agent_preset(
    goal: str,
    preset: AgentPreset | str,
    *,
    task_id: str | None = None,
    extra_context: str | None = None,
    model: str | None = None,
    max_iterations: int | None = None,
    temperature: float | None = None,
) -> dict[str, Any]:
    """Dispatch a builder task to an agent preset.

    Spawns an ``agent_runner`` agent with the given preset configuration,
    bridging the 5 presets (explorer, planner, coder, reviewer, researcher)
    into the builder lifecycle.

    Returns ``{"session_id", "preset", "goal", "status", "output", "error"}``.
    """
    if isinstance(preset, str):
        try:
            preset = AgentPreset(preset)
        except ValueError:
            return {
                "session_id": 0,
                "preset": preset,
                "goal": goal,
                "status": "failed",
                "error": f"Unknown agent preset: {preset}",
            }

    config = AGENT_PRESET_CONFIGS.get(preset)
    if config is None:
        return {
            "session_id": 0,
            "preset": preset.value,
            "goal": goal,
            "status": "failed",
            "error": f"No configuration for preset: {preset.value}",
        }

    try:
        from gateway.agent_runner import await_completion, get_output, spawn

        session_id = await spawn(
            goal,
            agent_type=preset.value,
            model=model or config.model,
            max_iterations=max_iterations or config.max_iterations,
            temperature=temperature or config.temperature,
            extra_context=extra_context,
            algorithm=True,
        )

        status_result = await await_completion(
            session_id,
            timeout=config.timeout_seconds,
            poll=3.0,
        )

        output = get_output(session_id)

        return {
            "session_id": int(session_id),
            "preset": preset.value,
            "goal": goal,
            "status": status_result.get("status", "unknown"),
            "output": output,
            "error": None,
        }
    except Exception as exc:
        return {
            "session_id": 0,
            "preset": preset.value,
            "goal": goal,
            "status": "failed",
            "output": None,
            "error": f"{type(exc).__name__}: {exc}",
        }



def _dsh_presence_session_id(run_id: str, worker: str | None) -> str | None:
    """Map a real DSH Builder run to one durable Agent Room presence session."""
    if not str(worker or "").startswith("dsh-"):
        return None
    return f"builder-{run_id}"


def _presence_issue(action: str, exc: Exception) -> str:
    return f"{action}:{type(exc).__name__}:{exc}"


def _presence_check_in(
    *, run_id: str, worker: str | None, task_id: str, start_sha: str, model: str | None
) -> tuple[str | None, list[str]]:
    session_id = _dsh_presence_session_id(run_id, worker)
    if session_id is None:
        return None, []
    try:
        agent_workspace.check_in(
            participant_id="dsh",
            session_id=session_id,
            runtime="kittybuilder-dsh",
            role="OWN",
            lane_id=task_id,
            exact_ref=start_sha,
            summary=f"KittyBuilder run {run_id} using {model or 'configured model'}",
            declared_status="active",
        )
    except Exception as exc:
        return session_id, [_presence_issue("checkin", exc)]
    return session_id, []


def _presence_heartbeat(session_id: str | None, issues: list[str]) -> None:
    if session_id is None:
        return
    try:
        agent_workspace.heartbeat(session_id, "dsh")
    except Exception as exc:
        issues.append(_presence_issue("heartbeat", exc))


def _presence_checkout(session_id: str | None, issues: list[str]) -> None:
    if session_id is None:
        return
    try:
        agent_workspace.checkout(session_id, "dsh")
    except Exception as exc:
        issues.append(_presence_issue("checkout", exc))


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
    extra_env: dict[str, str] | None = None,
    base_sha: str | None = None,
    inject_context: bool = False,
    reuse_dirty_worktree: bool = False,
) -> dict[str, Any]:
    """Claim *task_id*, run *command* in its isolated worktree, record all.

    Returns the final run dict. The task ends in ``blocked`` with a reason
    from the outcome (shadow_run_complete / worker_failed / run_timeout /
    run_cancelled) unless the worker command already transitioned it itself
    (smart workers hold the lease via KB_LEASE_TOKEN and may do so).

    ``extra_env`` adds variables to the worker environment (the KB-S3b
    packet loop passes attempt bundle/result paths). It may not re-inject
    the credentials this runner strips.

    ``reuse_dirty_worktree`` opts into reusing an existing worktree that is
    on the correct branch but dirty. Only the runner loop's repair retry
    sets it, after it has decided the dirty tree is a deliberately preserved
    prior implementation to build on; every other caller keeps the default
    fail-closed refusal.
    """
    if not command:
        raise ValueError("command must be a non-empty list")
    if extra_env:
        overlap = _EXTRA_ENV_BLOCKED & set(extra_env)
        if overlap:
            raise ValueError(
                f"extra_env may not override credential isolation: {sorted(overlap)}"
            )
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

    # Worktree creation and context preparation can legitimately take longer
    # than one lease interval. Keep ownership alive from the moment we claim
    # the task, not only after the model process has started.
    prelaunch_stop = threading.Event()
    prelaunch_errors: list[Exception] = []

    def _prelaunch_heartbeat() -> None:
        while not prelaunch_stop.wait(heartbeat_seconds):
            try:
                bq.renew_lease(
                    task_id,
                    lease_token,
                    claim_version,
                    lease_seconds=lease_seconds,
                    db_path=db_path,
                )
            except Exception as exc:
                prelaunch_errors.append(exc)
                return

    prelaunch_thread = threading.Thread(
        target=_prelaunch_heartbeat,
        name=f"builder-prelaunch-heartbeat-{task_id}",
        daemon=True,
    )
    prelaunch_thread.start()

    def _stop_prelaunch_heartbeat(*, check_error: bool) -> None:
        prelaunch_stop.set()
        prelaunch_thread.join(timeout=max(1.0, heartbeat_seconds * 2))
        if prelaunch_thread.is_alive():
            raise RunnerError(f"prelaunch heartbeat did not stop for task {task_id}")
        if check_error and prelaunch_errors:
            exc = prelaunch_errors[0]
            raise RunnerError(
                f"prelaunch lease heartbeat failed for task {task_id}: "
                f"{type(exc).__name__}: {exc}"
            ) from exc

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
        wt_path = ensure_worktree(
            task_id,
            branch,
            repo_root=root,
            base_sha=base_sha,
            reuse_dirty=reuse_dirty_worktree,
        )
    except Exception:
        # Nothing started yet — stop lease maintenance and hand the claim back.
        _stop_prelaunch_heartbeat(check_error=False)
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

        # Phase 2: inject context bundle if enabled
        context_env: dict[str, str] = {}
        if inject_context:
            try:
                ctx_env, _ctx_bundle = inject_worker_context(
                    task_id,
                    run_id,
                    branch=branch,
                    worker=worker,
                    model=model,
                    provider=provider,
                    allowed_paths=task.get("allowed_paths"),
                    acceptance_criteria=task.get("acceptance_criteria"),
                    db_path=db_path,
                    repo_root=root,
                )
                context_env = ctx_env
            except Exception as exc:
                raise RunnerError(
                    f"context injection failed for run {run_id}: {exc}"
                ) from exc

        bq.worker_transition_task(
            task_id,
            bq.RUNNING,
            lease_token,
            claim_version,
            payload={"run_id": run_id, "worker": worker},
            db_path=db_path,
        )
        _stop_prelaunch_heartbeat(check_error=True)
        # Hand the process-monitoring loop a full fresh lease window.
        bq.renew_lease(
            task_id,
            lease_token,
            claim_version,
            lease_seconds=lease_seconds,
            db_path=db_path,
        )
    except Exception as exc:
        _stop_prelaunch_heartbeat(check_error=False)
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
                "worker_started": False,
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

    child_env = beb.build_child_environment(os.environ, run_dir=run_dir)
    validation_venv, validation_read_roots = _validation_toolchain(root)
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
    if extra_env:
        # Additions only — validated against _EXTRA_ENV_BLOCKED up front; the
        # runner-owned KB_* vars below always win.
        child_env.update(extra_env)
    if context_env:
        child_env.update(context_env)
    # Runner-owned validation tooling wins over optional attempt/context env.
    if validation_venv is not None:
        child_env["VIRTUAL_ENV"] = str(validation_venv)
        child_env["PATH"] = f"{validation_venv / 'bin'}:{child_env['PATH']}"
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
    presence_session_id: str | None = None
    presence_issues: list[str] = []

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
            boundary_read_paths = [
                Path(child_env[key])
                for key in ("KB_BUNDLE_PATH", "KB_CONTEXT_MANIFEST_PATH")
                if child_env.get(key)
            ]
            boundary_write_paths = [
                Path(child_env["KB_RESULT_PATH"])
            ] if child_env.get("KB_RESULT_PATH") else []
            sandboxed_command = beb.wrap_command(
                command,
                worktree=wt_path,
                run_dir=run_dir,
                environment=child_env,
                read_paths=boundary_read_paths,
                extra_read_subpaths=validation_read_roots,
                write_paths=boundary_write_paths,
            )
            proc = subprocess.Popen(
                sandboxed_command,
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
        scope_violation_snapshot: tuple[list[str], list[str]] | None = None
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
            presence_session_id, presence_issues = _presence_check_in(
                run_id=run_id,
                worker=worker,
                task_id=task_id,
                start_sha=start_sha,
                model=model,
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

                    try:
                        bq.renew_lease(
                            task_id,
                            lease_token,
                            claim_version,
                            lease_seconds=lease_seconds,
                            db_path=db_path,
                        )
                        bq.update_run(run_id, mark_heartbeat=True, db_path=db_path)
                        _presence_heartbeat(presence_session_id, presence_issues)
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
                        break

                    try:
                        changed_paths, scope_violations = _scope_snapshot(
                            wt_path,
                            start_sha,
                            task.get("allowed_paths"),
                        )
                    except Exception as exc:
                        _terminate_group(proc)
                        exit_code = proc.returncode
                        control_error = exc
                        break

                    if scope_violations:
                        scope_violation_snapshot = (changed_paths, scope_violations)
                        _terminate_group(proc)
                        exit_code = proc.returncode
                        outcome = bq.RUN_SCOPE_VIOLATION
                        break

                    if time.monotonic() - started > timeout_seconds:
                        _terminate_group(proc)
                        exit_code = proc.returncode
                        outcome = bq.RUN_TIMEOUT
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
    elif outcome not in (
        bq.RUN_CANCELLED,
        bq.RUN_TIMEOUT,
        bq.RUN_LEASE_LOST,
        bq.RUN_SCOPE_VIOLATION,
    ):
        outcome = bq.RUN_EXITED if exit_code == 0 else bq.RUN_FAILED

    start_sha = str(run.get("start_sha") or "")
    if not start_sha and control_error is None:
        control_error = RunnerError(f"run {run_id} has no recorded start SHA")
    try:
        changed_paths = _changed_paths(wt_path, start_sha)
        diff_sha256 = _diff_sha256(wt_path, start_sha)
        scope_violations = _scope_violations(
            changed_paths,
            task.get("allowed_paths"),
        )
        worktree_state = _worktree_summary(wt_path)
    except Exception as exc:
        if control_error is None:
            control_error = exc
        changed_paths = []
        diff_sha256 = None
        scope_violations = []
        worktree_state = {"inspection_error": f"{type(exc).__name__}: {exc}"}

    if scope_violation_snapshot is not None:
        changed_paths, scope_violations = scope_violation_snapshot
        outcome = bq.RUN_SCOPE_VIOLATION
        control_error = None

    if control_error is not None and outcome != bq.RUN_LEASE_LOST:
        outcome = bq.RUN_FAILED
    elif scope_violations and outcome != bq.RUN_LEASE_LOST:
        outcome = bq.RUN_SCOPE_VIOLATION

    # Phase 2: validate context manifest integrity after run
    context_issues: list[str] = []
    if inject_context:
        try:
            context_issues = validate_worker_context(
                task_id, run_id, db_path=db_path
            )
        except Exception as exc:
            context_issues = [f"context validation error: {exc}"]
        if context_issues:
            if control_error is None:
                control_error = RunnerError(
                    f"context validation failed: {'; '.join(context_issues)}"
                )

    _presence_checkout(presence_session_id, presence_issues)

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
        "diff_sha256": diff_sha256,
        "worker_started": True,
        "scope_violations": scope_violations,
        "worktree_state": worktree_state,
        "context_issues": context_issues,
        "context_injected": inject_context,
        "presence_issues": presence_issues,
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
        elif not bq.process_identity_matches(expected_identity, current_identity):
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


# ---------------------------------------------------------------------------
# Durable detached execution (B7-detached-execution-durable)
# ---------------------------------------------------------------------------
#
# A terminal disconnect or watcher death must not strand a live worker. The
# synchronous ``run_worker`` owns the worker from inside the *calling* process,
# so if that process (the loop, the watcher, the terminal) dies, nobody is left
# heartbeating the lease and the worker continues unowned — its output is never
# attributed and its process leaks. The primitives below give the worker a
# detached, durable owner instead:
#
#   * ``run_worker_detached`` spawns a *supervisor* subprocess in its own
#     session. The supervisor runs the exact same ``run_worker`` lifecycle
#     (claim -> worktree -> spawn -> heartbeat -> collect -> finalize), so
#     ownership lives in a process that outlives the caller. The caller returns
#     immediately with the supervisor pid.
#   * ``detached_worker_status`` is the reconnectable status surface. Given a
#     run (or a task), it reads the durable DB record and the live process to
#     distinguish *still running* from *crashed* from *completed*, so an
#     operator can reconnect to a still-running worker after a restart and its
#     eventual output is attributed to the attempt that produced it.
#   * ``reap_detached_workers`` reclaims orphaned worker process groups whose
#     owner died (lease went stale while the worker is still alive), so no
#     orphan workers accumulate across repeated detach/restart cycles.

_DETACHED_DIR = "detached"
_DETACH_SUPERVISE_FLAG = "--supervise"
_DETACH_SUPERVISE_GRACE_PAD_SECONDS = 5


def _parse_timestamp(value: str | None) -> float | None:
    """Parse a builder timestamp (``%Y-%m-%d %H:%M:%f``) into epoch seconds."""
    if not value:
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return _datetime.datetime.strptime(text, fmt).timestamp()
        except ValueError:
            continue
    return None


def _process_alive(pid: int, expected_identity: str | None) -> tuple[bool, str]:
    """Return ``(alive, detail)`` for a recorded worker pid.

    Alive means the pid is currently running *and* its start-time identity
    matches the run's recorded identity, so a recycled pid is never mistaken
    for a live worker (PID-reuse fencing, same invariant as
    ``request_cancel`` / ``recover_interrupted_runs``). A missing or
    mismatched identity is treated as not alive.
    """
    if not pid or pid <= 0:
        return False, "process_not_recorded"
    try:
        os.kill(int(pid), 0)
    except ProcessLookupError:
        return False, "process_not_running"
    except OSError:
        return False, "process_probe_error"
    if not expected_identity:
        return False, "process_identity_missing"
    try:
        current = bq.capture_process_identity(int(pid))
    except Exception:
        return False, "process_identity_probe_error"
    if not bq.process_identity_matches(expected_identity, current):
        return False, "process_identity_mismatch"
    return True, "alive"


def _single_worker_run(
    task_id: str, run_id: str | None, *, db_path: Path | None
) -> dict[str, Any] | None:
    if run_id is not None:
        run = bq.get_run(run_id, db_path=db_path)
        if run is not None and run["task_id"] != task_id:
            raise ValueError(
                f"run {run_id} belongs to task {run['task_id']}, not {task_id}"
            )
        return run
    runs = bq.list_runs(task_id=task_id, db_path=db_path)
    return runs[-1] if runs else None


def detached_worker_status(
    run_id: str | None = None,
    *,
    task_id: str | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Reconnectable status of a (possibly detached) worker run.

    Exactly one of ``run_id`` or ``task_id`` is required. Reads the durable run
    record and the live worker process to classify the run as:

      * ``completed`` — the run is in a terminal state; its final report is the
        attempt's attached output (branch, commit, changed paths).
      * ``running`` — the run is active, its worker process is alive with a
        matching identity, and the task lease is current (a live owner exists).
      * ``orphaned`` — the run is active and its worker is alive, but the task
        lease has expired: the owner (loop/supervisor) died and the worker is
        still running unowned. The operator (or ``reap_detached_workers``) may
        reclaim it.
      * ``crashed`` — the run is active in the DB but the worker process is
        gone (or its identity does not match); the owner recorded a run it
        never got to finalize.
      * ``starting`` — active with no worker pid recorded yet.
      * ``missing`` — no run rows for the given identity.
    """
    if (run_id is None) == (task_id is None):
        raise ValueError("exactly one of run_id or task_id is required")
    if task_id is None:
        run = bq.get_run(str(run_id), db_path=db_path)
        if run is not None:
            task_id = str(run["task_id"])
        else:
            return {"status": "missing", "run_id": run_id, "task_id": None}
    run = _single_worker_run(task_id, run_id, db_path=db_path)
    if run is None:
        return {"status": "missing", "run_id": run_id, "task_id": task_id}

    rid = str(run["id"])
    base: dict[str, Any] = {
        "run_id": rid,
        "task_id": task_id,
        "run_state": run["state"],
        "pid": run.get("pid"),
        "exit_code": run.get("exit_code"),
        "branch": run.get("branch"),
        "worktree_path": run.get("worktree_path"),
        "log_path": run.get("log_path"),
        "last_heartbeat_at": run.get("last_heartbeat_at"),
        "reconnectable": False,
    }

    if run["state"] in bq.RUN_TERMINAL_STATES:
        base["status"] = "completed"
        base["outcome"] = run["state"]
        # A completed run is fully attributable: the operator can reconnect to
        # its durable final report and worktree.
        base["reconnectable"] = run.get("final_report") is not None
        base["final_report"] = run.get("final_report")
        return base

    if run.get("pid") is None:
        base["status"] = "starting"
        return base

    pid = int(run["pid"])
    alive, detail = _process_alive(pid, run.get("process_identity"))
    if not alive:
        base["status"] = "crashed"
        base["reason"] = detail
        return base

    # Worker is alive. Decide whether it has a live owner by lease freshness.
    task = bq.get_task(task_id, db_path=db_path)
    lease_expires = _parse_timestamp(
        task.get("lease_expires_at") if task is not None else None
    )
    current = time.time()
    if lease_expires is not None and current <= lease_expires:
        base["status"] = "running"
        base["reason"] = "alive"
    else:
        base["status"] = "orphaned"
        base["reason"] = "lease_expired"
    base["reconnectable"] = base["status"] == "running"
    return base


def reap_detached_workers(
    db_path: Path | None = None,
    *,
    grace_seconds: int = DEFAULT_LEASE_SECONDS,
    _killpg: Any = os.killpg,
) -> dict[str, Any]:
    """Reclaim orphaned worker process groups so none accumulate.

    A worker whose owner died keeps running in its own session, but its task
    lease stops being renewed and expires. This scans every active (non
    terminal) run whose worker process is still alive and identity-matches, and
    whose task lease has been expired for more than ``grace_seconds`` — a
    positive, durable signal that the owning supervisor/loop is gone — and
    SIGTERMs (then SIGKILLs) that worker's process group. Runs whose worker is
    already gone are left for ``recover_interrupted_runs`` to mark. Runs with a
    live, currently-leased owner are never touched.

    Returns a summary of reaped / skipped runs. ``_killpg`` is injectable for
    tests.
    """
    if grace_seconds < 0:
        raise ValueError("grace_seconds must be non-negative")
    reaped: list[str] = []
    skipped: list[str] = []
    reaped_pids: list[int] = []
    for run in bq.list_runs(state=None, db_path=db_path):
        if run["state"] not in bq.RUN_ACTIVE_STATES:
            continue
        run_id = str(run["id"])
        if run.get("pid") is None:
            skipped.append(run_id)
            continue
        pid = int(run["pid"])
        alive, detail = _process_alive(pid, run.get("process_identity"))
        if not alive:
            skipped.append(run_id)
            continue
        task = bq.get_task(str(run["task_id"]), db_path=db_path)
        lease_expires = _parse_timestamp(
            task.get("lease_expires_at") if task is not None else None
        )
        if lease_expires is None:
            # Cannot positively confirm the owner is gone — fail closed and
            # leave the run to the lease-recovery path.
            skipped.append(run_id)
            continue
        if time.time() <= lease_expires + grace_seconds:
            skipped.append(run_id)
            continue
        # Owner is durably gone (lease stale past grace) while the worker is
        # still alive — reclaim the orphan's process group.
        try:
            _killpg(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        except OSError:
            skipped.append(run_id)
            continue
        time.sleep(0.1)
        try:
            _killpg(pid, signal.SIGKILL)
        except (ProcessLookupError, OSError):
            pass
        reaped.append(run_id)
        reaped_pids.append(pid)
    return {
        "reaped": reaped,
        "reaped_pids": reaped_pids,
        "skipped": skipped,
        "count": len(reaped),
    }


def _detached_spec_payload(
    task_id: str,
    command: list[str],
    *,
    worker: str,
    model: str | None,
    provider: str | None,
    timeout_seconds: int,
    lease_seconds: int,
    heartbeat_seconds: int,
    repo_root: Path,
    db_path: Path | None,
    extra_env: dict[str, str] | None,
    base_sha: str | None,
    inject_context: bool,
    reuse_dirty_worktree: bool,
) -> dict[str, Any]:
    """Serialize the ``run_worker`` parameters a detached supervisor needs."""
    return {
        "task_id": task_id,
        "command": list(command),
        "worker": worker,
        "model": model,
        "provider": provider,
        "timeout_seconds": timeout_seconds,
        "lease_seconds": lease_seconds,
        "heartbeat_seconds": heartbeat_seconds,
        "repo_root": str(repo_root),
        "db_path": str(db_path) if db_path is not None else None,
        "extra_env": dict(extra_env) if extra_env else None,
        "base_sha": base_sha,
        "inject_context": inject_context,
        "reuse_dirty_worktree": reuse_dirty_worktree,
    }


def _supervise_worker(spec_path: str | Path) -> int:
    """Run a detached worker to completion inside a supervisor process.

    This is the entrypoint the detached supervisor process executes. It reads
    the spec written by ``run_worker_detached`` and runs the exact synchronous
    ``run_worker`` lifecycle so that *this* process — not the original caller —
    owns every step. Writes a completion/error status file beside the spec, so
    a later operator can inspect what the supervisor observed even if it had to
    exit abnormally. Returns the process exit code.
    """
    spec_path = Path(spec_path)
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    status_path = spec_path.with_suffix(".status.json")

    def _write_status(payload: dict[str, Any]) -> None:
        status_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
        )

    def _wrapped_finalize(status: dict[str, Any]) -> int:
        try:
            _write_status(status)
        except OSError:
            pass
        return 1 if status.get("ok") is False else 0

    try:
        final = run_worker(
            spec["task_id"],
            spec["command"],
            worker=spec.get("worker", "local-runner"),
            model=spec.get("model"),
            provider=spec.get("provider"),
            timeout_seconds=spec.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS),
            lease_seconds=spec.get("lease_seconds", DEFAULT_LEASE_SECONDS),
            heartbeat_seconds=spec.get("heartbeat_seconds", DEFAULT_HEARTBEAT_SECONDS),
            repo_root=Path(spec["repo_root"]) if spec.get("repo_root") else None,
            db_path=Path(spec["db_path"]) if spec.get("db_path") else None,
            extra_env=spec.get("extra_env"),
            base_sha=spec.get("base_sha"),
            inject_context=bool(spec.get("inject_context")),
            reuse_dirty_worktree=bool(spec.get("reuse_dirty_worktree")),
        )
    except Exception as exc:
        return _wrapped_finalize(
            {
                "ok": False,
                "task_id": spec.get("task_id"),
                "error": f"{type(exc).__name__}: {exc}",
                "needle_reconnect": (
                    "supervisor crashed; reconnect via detached_worker_status"
                ),
            }
        )
    return _wrapped_finalize(
        {
            "ok": True,
            "task_id": spec.get("task_id"),
            "run_id": final.get("id"),
            "run_state": final.get("state"),
            "outcome": (final.get("final_report") or {}).get("outcome"),
        }
    )


def run_worker_detached(
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
    extra_env: dict[str, str] | None = None,
    base_sha: str | None = None,
    inject_context: bool = False,
    reuse_dirty_worktree: bool = False,
    spec_dir: Path | None = None,
) -> dict[str, Any]:
    """Launch *command* under a durable detached supervisor and return at once.

    The supervisor is a separate process in its own session
    (``start_new_session=True``). It owns the entire ``run_worker`` lifecycle —
    claim, worktree, spawn, heartbeat, collect, finalize — so the worker is
    not stranded when this calling process (loop, watcher, terminal) dies. This
    call returns immediately once the supervisor is spawned; the run row
    appears in the queue DB (and is observable via :func:`detached_worker_status`)
    as the supervisor proceeds.

    Parameter validation is identical to :func:`run_worker` and raises *before*
    anything is spawned. Returns a dispatch record containing the supervisor
    pid and the spec path; it deliberately does not block for completion.
    """
    # Validate identically to run_worker, before spawning anything, so a bad
    # invocation cannot leak a partial detached run.
    if not command:
        raise ValueError("command must be a non-empty list")
    if extra_env:
        overlap = _EXTRA_ENV_BLOCKED & set(extra_env)
        if overlap:
            raise ValueError(
                f"extra_env may not override credential isolation: {sorted(overlap)}"
            )
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

    root = _repo_root(repo_root).resolve()
    queue_db = Path(db_path) if db_path is not None else BUILDER_QUEUE_DB
    runs_dir = queue_db.parent / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    detach_dir = (spec_dir or (runs_dir / _DETACHED_DIR)).resolve()
    detach_dir.mkdir(parents=True, exist_ok=True)

    stamp = time.strftime("%Y%m%d-%H%M%S")
    spec_path = detach_dir / f"supervisor-{stamp}-{task_id}.spec.json"
    spec_path.write_text(
        json.dumps(
            _detached_spec_payload(
                task_id,
                command,
                worker=worker,
                model=model,
                provider=provider,
                timeout_seconds=timeout_seconds,
                lease_seconds=lease_seconds,
                heartbeat_seconds=heartbeat_seconds,
                repo_root=root,
                db_path=db_path,
                extra_env=extra_env,
                base_sha=base_sha,
                inject_context=inject_context,
                reuse_dirty_worktree=reuse_dirty_worktree,
            ),
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    supervisor_log = detach_dir / f"supervisor-{stamp}-{task_id}.log"

    # The supervisor is an operator-owned process: it needs no ambient GitHub /
    # SSH credentials (the worker's env is built and stripped inside
    # run_worker), so strip them here too to keep them out of the supervisor
    # log stream.
    supervisor_env = dict(os.environ)
    for key in _EXTRA_ENV_BLOCKED:
        supervisor_env.pop(key, None)
    supervisor_env["GIT_CONFIG_GLOBAL"] = os.devnull
    supervisor_env["GIT_CONFIG_SYSTEM"] = os.devnull
    supervisor_env["GIT_TERMINAL_PROMPT"] = "0"

    # project_root is where `gateway` is importable so `python -m
    # gateway.builder_runner` runs in the child regardless of the task's
    # worktree repo (passed explicitly as repo_root).
    project_root = Path.cwd().resolve()
    try:
        log_fh = open(supervisor_log, "ab")
    except OSError as exc:
        raise RunnerError(
            f"cannot open detached supervisor log {supervisor_log}: {exc}"
        ) from exc
    with log_fh:
        try:
            proc = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "gateway.builder_runner",
                    _DETACH_SUPERVISE_FLAG,
                    str(spec_path),
                ],
                cwd=str(project_root),
                stdout=log_fh,
                stderr=subprocess.STDOUT,
                env=supervisor_env,
                start_new_session=True,
            )
        except OSError as exc:
            raise RunnerError(
                f"failed to spawn detached supervisor for task {task_id}: {exc}"
            ) from exc

    logger.info(
        "dispatched detached worker for task %s (supervisor pid=%s spec=%s)",
        task_id,
        proc.pid,
        spec_path,
    )
    return {
        "status": "dispatched",
        "task_id": task_id,
        "supervisor_pid": proc.pid,
        "spec_path": str(spec_path),
        "supervisor_log": str(supervisor_log),
        "detached": True,
    }


def _detached_main(argv: list[str] | None = None) -> int:
    """Internal CLI entrypoint for the detached supervisor process."""
    parser = argparse.ArgumentParser(
        prog="gateway.builder_runner", description="KittyBuilder worker runner (internal)."
    )
    parser.add_argument(
        _DETACH_SUPERVISE_FLAG,
        dest="spec_path",
        metavar="SPEC",
        help="run the detached worker described by SPEC to completion",
    )
    args = parser.parse_args(argv)
    if not args.spec_path:
        parser.error("missing supervisor spec path")
    return _supervise_worker(args.spec_path)


if __name__ == "__main__":
    raise SystemExit(_detached_main())
