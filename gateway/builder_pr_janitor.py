"""Builder-owned deterministic repairs before PR publication.

This module deliberately handles only safe, mechanical fixes. Anything that
requires semantic judgment stays in Builder's existing repair-worker loop.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

RunCmd = Callable[..., subprocess.CompletedProcess[str]]

JANITOR_MAX_PASSES = 3
PUBLICATION_GATE_COMMAND = "./scripts/hooks/pre-push"
RUFF_TARGETS = (
    "gateway/",
    "tests/",
    "mcp/",
    "workers/",
    "scripts/runpod_worker_smoke_test.py",
)
_SAFE_PREFIXES = ("gateway/", "tests/", "mcp/", "workers/")
_SAFE_EXACT = {"scripts/runpod_worker_smoke_test.py"}


class SafeRepairError(RuntimeError):
    """Raised when a deterministic repair cannot proceed safely."""


def _default_run(
    args: list[str], *, cwd: Path | None = None, check: bool = False
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=str(cwd) if cwd is not None else None,
        check=check,
        capture_output=True,
        text=True,
    )


def _status_paths(
    worktree: Path, run_cmd: RunCmd, *, ignore_done_marker: bool = False
) -> list[str]:
    result = run_cmd(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=worktree,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise SafeRepairError(f"cannot inspect PR janitor worktree: {detail}")
    paths: list[str] = []
    for line in (result.stdout or "").splitlines():
        if not line.strip():
            continue
        if ignore_done_marker and line == "?? done.txt":
            continue
        path = line[3:]
        if " -> " in path:
            path = path.rsplit(" -> ", 1)[1]
        paths.append(path)
    return sorted(set(paths))


def _safe_path(path: str) -> bool:
    return path in _SAFE_EXACT or path.startswith(_SAFE_PREFIXES)


def _restore_all(worktree: Path, run_cmd: RunCmd) -> None:
    result = run_cmd(
        ["git", "restore", "--staged", "--worktree", "--", "."],
        cwd=worktree,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise SafeRepairError(f"PR janitor rollback failed: {detail}")


def apply_safe_repairs(
    worktree: Path, *, run_cmd: RunCmd | None = None
) -> dict[str, Any]:
    """Apply and commit only safe Ruff fixes in a clean Builder worktree."""
    runner = run_cmd or _default_run
    worktree = Path(worktree)
    dirty = _status_paths(worktree, runner, ignore_done_marker=True)
    if dirty:
        raise SafeRepairError(
            "PR janitor refuses dirty worktree before repair: " + ", ".join(dirty)
        )

    ruff = runner(
        [sys.executable, "-m", "ruff", "check", "--fix", *RUFF_TARGETS],
        cwd=worktree,
        check=False,
    )
    changed = _status_paths(worktree, runner, ignore_done_marker=True)
    forbidden = [path for path in changed if not _safe_path(path)]
    if forbidden:
        _restore_all(worktree, runner)
        raise SafeRepairError(
            "PR janitor changed forbidden path(s): " + ", ".join(forbidden)
        )

    if not changed:
        return {
            "changed": False,
            "changed_paths": [],
            "commit_sha": None,
            "ruff_exit_code": ruff.returncode,
        }

    add = runner(["git", "add", "--", *changed], cwd=worktree, check=False)
    if add.returncode != 0:
        _restore_all(worktree, runner)
        detail = (add.stderr or add.stdout or "").strip()
        raise SafeRepairError(f"PR janitor could not stage repairs: {detail}")

    commit = runner(
        ["git", "commit", "-m", "fix: apply PR janitor repairs"],
        cwd=worktree,
        check=False,
    )
    if commit.returncode != 0:
        _restore_all(worktree, runner)
        detail = (commit.stderr or commit.stdout or "").strip()
        raise SafeRepairError(f"PR janitor could not commit repairs: {detail}")

    head = runner(["git", "rev-parse", "HEAD"], cwd=worktree, check=False)
    if head.returncode != 0:
        detail = (head.stderr or head.stdout or "").strip()
        raise SafeRepairError(f"PR janitor cannot resolve repaired HEAD: {detail}")
    leftover = _status_paths(worktree, runner, ignore_done_marker=True)
    if leftover:
        raise SafeRepairError(
            "PR janitor left worktree dirty after commit: " + ", ".join(leftover)
        )
    return {
        "changed": True,
        "changed_paths": changed,
        "commit_sha": head.stdout.strip(),
        "ruff_exit_code": ruff.returncode,
    }
