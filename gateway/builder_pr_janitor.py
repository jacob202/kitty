"""Builder-owned deterministic repairs before PR publication.

This module deliberately handles only safe, mechanical fixes. Anything that
requires semantic judgment stays in Builder's existing repair-worker loop.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any, Callable

from gateway import builder_scope as bs

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


def publication_preflight(
    repo_root: Path, *, run_cmd: RunCmd | None = None
) -> subprocess.CompletedProcess[str]:
    """Probe machine/toolchain prerequisites from an existing repository root."""
    runner = run_cmd or _default_run
    return runner(
        [PUBLICATION_GATE_COMMAND, "--preflight"], cwd=Path(repo_root), check=False
    )


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
    worktree: Path,
    run_cmd: RunCmd,
    *,
    ignore_done_marker: bool = False,
    ignore_expected_residue: bool = False,
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
        if ignore_expected_residue and bs.is_expected_residue(path):
            continue
        paths.append(path)
    return sorted(set(paths))


def _safe_path(path: str) -> bool:
    return path in _SAFE_EXACT or path.startswith(_SAFE_PREFIXES)


def _outside_packet_scope(path: str, allowed_paths: list[str] | None) -> bool:
    if not allowed_paths:
        return False
    normalized: list[str] = []
    for raw in allowed_paths:
        candidate = raw.strip().rstrip("/") or "."
        parsed = PurePosixPath(candidate)
        if parsed.is_absolute() or ".." in parsed.parts:
            raise SafeRepairError(
                f"invalid packet allowed path {raw!r}: use a repo-relative path without '..'"
            )
        normalized.append(parsed.as_posix())
    return not any(
        prefix == "." or path == prefix or path.startswith(f"{prefix}/")
        for prefix in normalized
    )


def _restore_paths(worktree: Path, run_cmd: RunCmd, paths: list[str]) -> None:
    if not paths:
        return
    result = run_cmd(
        ["git", "restore", "--staged", "--worktree", "--", *paths],
        cwd=worktree,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise SafeRepairError(f"PR janitor rollback failed: {detail}")


def apply_safe_repairs(
    worktree: Path,
    *,
    allowed_paths: list[str] | None = None,
    commit_marker: str | None = None,
    run_cmd: RunCmd | None = None,
) -> dict[str, Any]:
    """Apply and commit only safe Ruff fixes in a clean Builder worktree."""
    runner = run_cmd or _default_run
    worktree = Path(worktree)
    dirty = _status_paths(
        worktree,
        runner,
        ignore_done_marker=True,
        ignore_expected_residue=True,
    )
    if dirty:
        raise SafeRepairError(
            "PR janitor refuses dirty worktree before repair: " + ", ".join(dirty)
        )

    ruff = runner(
        [sys.executable, "-m", "ruff", "check", "--fix", *RUFF_TARGETS],
        cwd=worktree,
        check=False,
    )
    changed = _status_paths(
        worktree,
        runner,
        ignore_done_marker=True,
        ignore_expected_residue=True,
    )
    forbidden = [path for path in changed if not _safe_path(path)]
    if forbidden:
        _restore_paths(worktree, runner, changed)
        raise SafeRepairError(
            "PR janitor changed forbidden path(s): " + ", ".join(forbidden)
        )

    out_of_scope = [
        path for path in changed if _outside_packet_scope(path, allowed_paths)
    ]
    if out_of_scope:
        _restore_paths(worktree, runner, changed)
        raise SafeRepairError(
            "PR janitor changed path(s) outside packet scope: "
            + ", ".join(out_of_scope)
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
        _restore_paths(worktree, runner, changed)
        detail = (add.stderr or add.stdout or "").strip()
        raise SafeRepairError(f"PR janitor could not stage repairs: {detail}")

    marker = (commit_marker or "").strip()
    if "\n" in marker or "\r" in marker:
        _restore_paths(worktree, runner, changed)
        raise SafeRepairError("PR janitor commit marker must be one line")
    subject = "fix: apply PR janitor repairs" + (f" {marker}" if marker else "")
    commit = runner(
        ["git", "commit", "-m", subject],
        cwd=worktree,
        check=False,
    )
    if commit.returncode != 0:
        _restore_paths(worktree, runner, changed)
        detail = (commit.stderr or commit.stdout or "").strip()
        raise SafeRepairError(f"PR janitor could not commit repairs: {detail}")

    head = runner(["git", "rev-parse", "HEAD"], cwd=worktree, check=False)
    if head.returncode != 0:
        detail = (head.stderr or head.stdout or "").strip()
        raise SafeRepairError(f"PR janitor cannot resolve repaired HEAD: {detail}")
    leftover = _status_paths(
        worktree,
        runner,
        ignore_done_marker=True,
        ignore_expected_residue=True,
    )
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
