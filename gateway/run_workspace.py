"""Authenticated Git worktree containment and cumulative mutation snapshots.

This module is the shared primitive for agent execution paths that need to bind
work to one repository/worktree identity and audit everything observable since
a recorded base commit. Scheduling and semantic mutation ownership remain with
Builder leases and KX coordination respectively.
"""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

_SAFE_RUN_ID = re.compile(r"^[A-Za-z0-9._-]+$")
_GIT_TIMEOUT_SECONDS = 20


class RunWorkspaceError(RuntimeError):
    """Raised when a worktree cannot be authenticated or audited safely."""


@dataclass(frozen=True)
class WorktreeIdentity:
    repo_git_dir: Path
    repo_common_dir: Path
    worktree_git_dir: Path
    worktree_device: int
    worktree_inode: int
    base_commit: str

    def to_payload(self) -> dict[str, str | int]:
        return {
            "repo_git_dir": str(self.repo_git_dir),
            "repo_common_dir": str(self.repo_common_dir),
            "worktree_git_dir": str(self.worktree_git_dir),
            "worktree_device": self.worktree_device,
            "worktree_inode": self.worktree_inode,
            "base_commit": self.base_commit,
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "WorktreeIdentity":
        expected = {
            "repo_git_dir",
            "repo_common_dir",
            "worktree_git_dir",
            "worktree_device",
            "worktree_inode",
            "base_commit",
        }
        if set(payload) != expected:
            raise RunWorkspaceError("persisted worktree identity has invalid fields")
        paths: dict[str, Path] = {}
        for key in ("repo_git_dir", "repo_common_dir", "worktree_git_dir"):
            value = payload[key]
            if not isinstance(value, str) or not value:
                raise RunWorkspaceError(f"persisted worktree identity {key} is invalid")
            path = Path(value)
            if not path.is_absolute():
                raise RunWorkspaceError(f"persisted worktree identity {key} is not absolute")
            paths[key] = path
        worktree_device = payload["worktree_device"]
        worktree_inode = payload["worktree_inode"]
        if not isinstance(worktree_device, int) or isinstance(worktree_device, bool) or worktree_device < 0:
            raise RunWorkspaceError("persisted worktree identity worktree_device is invalid")
        if not isinstance(worktree_inode, int) or isinstance(worktree_inode, bool) or worktree_inode <= 0:
            raise RunWorkspaceError("persisted worktree identity worktree_inode is invalid")
        base_commit = payload["base_commit"]
        if not isinstance(base_commit, str) or not base_commit:
            raise RunWorkspaceError("persisted worktree identity base_commit is invalid")
        return cls(
            repo_git_dir=paths["repo_git_dir"],
            repo_common_dir=paths["repo_common_dir"],
            worktree_git_dir=paths["worktree_git_dir"],
            worktree_device=worktree_device,
            worktree_inode=worktree_inode,
            base_commit=base_commit,
        )


@dataclass(frozen=True)
class DiffSnapshot:
    base_commit: str
    head_commit: str
    changed_paths: tuple[str, ...]
    ignored_paths: tuple[str, ...]
    status_lines: tuple[str, ...]
    insertions: int = 0
    deletions: int = 0

    @property
    def mutation_paths(self) -> tuple[str, ...]:
        return tuple(sorted(set(self.changed_paths) | set(self.ignored_paths)))

    @property
    def files(self) -> int:
        return len(self.mutation_paths)

    @property
    def dirty(self) -> bool:
        return bool(self.mutation_paths)


def _run_git_raw(args: tuple[str, ...]) -> str:
    try:
        result = subprocess.run(
            ["/usr/bin/git", *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise RunWorkspaceError(
            f"git {' '.join(args)} timed out after {_GIT_TIMEOUT_SECONDS}s"
        ) from exc
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise RunWorkspaceError(
            f"git {' '.join(args)} failed with exit {result.returncode}: {detail}"
        )
    return result.stdout


def _run_git(args: tuple[str, ...]) -> str:
    return _run_git_raw(args).strip()


def _git_from_cwd(cwd: Path, *args: str) -> str:
    return _run_git(("-C", str(cwd), *args))


def _git_path_from_cwd(cwd: Path, *args: str) -> Path:
    value = Path(_git_from_cwd(cwd, *args))
    return (cwd / value).resolve() if not value.is_absolute() else value.resolve()


def _trusted_git(identity: WorktreeIdentity, worktree: Path, *args: str) -> str:
    return _run_git(
        ("--git-dir", str(identity.worktree_git_dir), "--work-tree", str(worktree), *args)
    )


def _trusted_git_raw(identity: WorktreeIdentity, worktree: Path, *args: str) -> str:
    return _run_git_raw(
        ("--git-dir", str(identity.worktree_git_dir), "--work-tree", str(worktree), *args)
    )


def _z_paths(output: str) -> set[str]:
    return {item for item in output.split("\0") if item}


def _verify_base(identity: WorktreeIdentity, worktree: Path) -> str:
    head = _trusted_git(identity, worktree, "rev-parse", "HEAD")
    try:
        result = subprocess.run(
            [
                "/usr/bin/git",
                "--git-dir",
                str(identity.worktree_git_dir),
                "--work-tree",
                str(worktree),
                "merge-base",
                "--is-ancestor",
                identity.base_commit,
                head,
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise RunWorkspaceError(
            f"git merge-base --is-ancestor timed out after {_GIT_TIMEOUT_SECONDS}s"
        ) from exc
    if result.returncode == 1:
        raise RunWorkspaceError(
            f"worktree HEAD {head} is not descended from base {identity.base_commit}"
        )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise RunWorkspaceError(f"cannot verify worktree base ancestry: {detail}")
    return head


def _snapshot(
    identity: WorktreeIdentity, worktree: Path, *, include_ignored: bool = True
) -> DiffSnapshot:
    worktree = worktree.resolve()
    head = _verify_base(identity, worktree)
    changed: set[str] = set()
    for args in (
        ("diff", "--name-only", "--no-renames", "-z", f"{identity.base_commit}..HEAD"),
        ("diff", "--name-only", "--no-renames", "-z"),
        ("diff", "--cached", "--name-only", "--no-renames", "-z"),
        ("ls-files", "--others", "--exclude-standard", "-z"),
    ):
        changed.update(_z_paths(_trusted_git_raw(identity, worktree, *args)))

    ignored = (
        tuple(
            sorted(
                _z_paths(
                    _trusted_git_raw(
                        identity,
                        worktree,
                        "ls-files",
                        "--others",
                        "--ignored",
                        "--exclude-standard",
                        "-z",
                    )
                )
            )
        )
        if include_ignored
        else ()
    )
    status = _trusted_git(
        identity, worktree, "status", "--porcelain=v1", "--untracked-files=all"
    )
    status_lines = tuple(line for line in status.splitlines() if line.strip()) + tuple(
        f"!! {path}" for path in ignored
    )

    insertions = 0
    deletions = 0
    numstat = _trusted_git(identity, worktree, "diff", "--numstat", identity.base_commit, "--")
    for line in numstat.splitlines():
        parts = line.split("\t", 2)
        if len(parts) < 2:
            continue
        if parts[0].isdigit():
            insertions += int(parts[0])
        if parts[1].isdigit():
            deletions += int(parts[1])

    return DiffSnapshot(
        base_commit=identity.base_commit,
        head_commit=head,
        changed_paths=tuple(sorted(changed)),
        ignored_paths=ignored,
        status_lines=status_lines,
        insertions=insertions,
        deletions=deletions,
    )


def authenticate_existing_worktree(
    repo: Path, worktree: Path, *, base_commit: str
) -> WorktreeIdentity:
    """Capture creation-time Git identity for an existing linked worktree."""
    repo = repo.resolve()
    worktree = worktree.resolve()
    repo_git_dir = _git_path_from_cwd(repo, "rev-parse", "--git-dir")
    repo_common_dir = _git_path_from_cwd(repo, "rev-parse", "--git-common-dir")
    worktree_git_dir = _git_path_from_cwd(worktree, "rev-parse", "--git-dir")
    worktree_common_dir = _git_path_from_cwd(worktree, "rev-parse", "--git-common-dir")
    if worktree_common_dir != repo_common_dir:
        raise RunWorkspaceError(
            "worktree common gitdir does not match controlling repository identity"
        )
    worktree_stat = worktree.stat()
    identity = WorktreeIdentity(
        repo_git_dir=repo_git_dir,
        repo_common_dir=repo_common_dir,
        worktree_git_dir=worktree_git_dir,
        worktree_device=worktree_stat.st_dev,
        worktree_inode=worktree_stat.st_ino,
        base_commit=base_commit,
    )
    _verify_base(identity, worktree)
    return identity


def verify_worktree_identity(
    identity: WorktreeIdentity, *, repo: Path, worktree: Path
) -> None:
    """Fail closed unless live Git discovery matches persisted identity exactly."""
    repo = repo.resolve()
    worktree = worktree.resolve()
    live = {
        "repo_git_dir": _git_path_from_cwd(repo, "rev-parse", "--git-dir"),
        "repo_common_dir": _git_path_from_cwd(repo, "rev-parse", "--git-common-dir"),
        "worktree_git_dir": _git_path_from_cwd(worktree, "rev-parse", "--git-dir"),
        "worktree_common_dir": _git_path_from_cwd(worktree, "rev-parse", "--git-common-dir"),
    }
    if live["repo_git_dir"] != identity.repo_git_dir:
        raise RunWorkspaceError("controlling repository gitdir identity changed")
    if live["repo_common_dir"] != identity.repo_common_dir:
        raise RunWorkspaceError("controlling repository common gitdir identity changed")
    if live["worktree_git_dir"] != identity.worktree_git_dir:
        raise RunWorkspaceError("worktree gitdir identity changed")
    if live["worktree_common_dir"] != identity.repo_common_dir:
        raise RunWorkspaceError("worktree common gitdir identity changed")
    worktree_stat = worktree.stat()
    if (worktree_stat.st_dev, worktree_stat.st_ino) != (
        identity.worktree_device,
        identity.worktree_inode,
    ):
        raise RunWorkspaceError("worktree directory identity changed or was replaced")
    _verify_base(identity, worktree)


def snapshot_existing_worktree(
    worktree: Path, *, base_commit: str, include_ignored: bool = True
) -> DiffSnapshot:
    """Audit an existing Git checkout from its currently resolved Git identity.

    This is suitable for consumers that did not create the worktree themselves.
    Strong creation-time identity binding is provided by :class:`GitWorktreeManager`.
    """
    worktree = worktree.resolve()
    git_dir = _git_path_from_cwd(worktree, "rev-parse", "--git-dir")
    common_dir = _git_path_from_cwd(worktree, "rev-parse", "--git-common-dir")
    worktree_stat = worktree.stat()
    identity = WorktreeIdentity(
        repo_git_dir=git_dir,
        repo_common_dir=common_dir,
        worktree_git_dir=git_dir,
        worktree_device=worktree_stat.st_dev,
        worktree_inode=worktree_stat.st_ino,
        base_commit=base_commit,
    )
    return _snapshot(identity, worktree, include_ignored=include_ignored)


@dataclass
class GitWorktreeManager:
    repo: Path
    base_ref: str = "HEAD"
    run_root: Path | None = None
    _authenticated: dict[Path, WorktreeIdentity] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        self.repo = self.repo.resolve()
        if self.run_root is None:
            self.run_root = self.repo.parent / ".agent-run-worktrees" / self.repo.name
        self.run_root = self.run_root.resolve()

    def create(self, run_id: str) -> Path:
        if not _SAFE_RUN_ID.fullmatch(run_id):
            raise ValueError("run_id contains unsafe characters")
        assert self.run_root is not None
        path = self.run_root / run_id
        if path.exists():
            raise FileExistsError(f"run worktree already exists: {path}")
        self.run_root.mkdir(parents=True, exist_ok=True)
        repo_git_dir = self._git_path("rev-parse", "--git-dir", cwd=self.repo)
        repo_common_dir = self._git_path("rev-parse", "--git-common-dir", cwd=self.repo)
        base_commit = self._git("rev-parse", self.base_ref, cwd=self.repo)
        try:
            self._git("worktree", "add", "--detach", str(path), base_commit, cwd=self.repo)
            worktree_git_dir = self._git_path("rev-parse", "--git-dir", cwd=path)
            worktree_common_dir = self._git_path("rev-parse", "--git-common-dir", cwd=path)
            worktree_commit = self._git("rev-parse", "HEAD", cwd=path)
            if worktree_commit != base_commit or worktree_common_dir != repo_common_dir:
                raise RunWorkspaceError(
                    "linked worktree identity did not match its controlling repository"
                )
        except Exception as primary_error:
            self._remove_created_worktree(path, primary_error)
            raise
        worktree_stat = path.stat()
        self._authenticated[path.resolve()] = WorktreeIdentity(
            repo_git_dir=repo_git_dir,
            repo_common_dir=repo_common_dir,
            worktree_git_dir=worktree_git_dir,
            worktree_device=worktree_stat.st_dev,
            worktree_inode=worktree_stat.st_ino,
            base_commit=base_commit,
        )
        return path

    def audit(self, path: Path) -> DiffSnapshot:
        resolved = path.resolve()
        identity = self._authenticated.get(resolved)
        if identity is None:
            raise RunWorkspaceError(f"worktree was not authenticated before audit: {path}")
        self._verify_identity(identity, resolved)
        return _snapshot(identity, resolved)

    def remove(self, path: Path) -> None:
        self._git("worktree", "remove", "--force", str(path), cwd=self.repo)
        self._git("worktree", "prune", cwd=self.repo)
        self._authenticated.pop(path.resolve(), None)

    def _verify_identity(self, identity: WorktreeIdentity, path: Path) -> None:
        if self._git_path("rev-parse", "--git-dir", cwd=self.repo) != identity.repo_git_dir:
            raise RunWorkspaceError("controlling repository gitdir changed")
        if self._git_path("rev-parse", "--git-common-dir", cwd=self.repo) != identity.repo_common_dir:
            raise RunWorkspaceError("controlling repository common gitdir changed")
        worktree_stat = path.stat()
        if (worktree_stat.st_dev, worktree_stat.st_ino) != (
            identity.worktree_device,
            identity.worktree_inode,
        ):
            raise RunWorkspaceError("worktree directory identity changed or was replaced")
        _verify_base(identity, path)

    def _remove_created_worktree(self, path: Path, primary_error: Exception) -> None:
        cleanup_error: Exception | None = None
        try:
            self._git("worktree", "remove", "--force", str(path), cwd=self.repo)
        except Exception as exc:
            cleanup_error = exc

        verification_error: Exception | None = None
        try:
            remaining = path.exists() or self._worktree_is_registered(path)
        except Exception as exc:
            remaining = False
            verification_error = exc

        if verification_error is not None or remaining:
            detail = (
                f"verification failed: {type(verification_error).__name__}: {verification_error}"
                if verification_error is not None
                else "the exact path or registration remains"
            )
            raise RunWorkspaceError(
                f"{type(primary_error).__name__}: {primary_error}; "
                f"cleanup not confirmed for {path}: {detail}"
            ) from primary_error
        cleanup_detail = ""
        if cleanup_error is not None:
            cleanup_detail = (
                f" after cleanup command failure ({type(cleanup_error).__name__}: {cleanup_error})"
            )
        raise RunWorkspaceError(
            f"{type(primary_error).__name__}: {primary_error}; "
            f"exact-path cleanup confirmed for {path}{cleanup_detail}"
        ) from primary_error

    def _worktree_is_registered(self, path: Path) -> bool:
        output = self._git("worktree", "list", "--porcelain", cwd=self.repo)
        target = path.resolve()
        return any(
            line.startswith("worktree ")
            and Path(line.removeprefix("worktree ")).resolve() == target
            for line in output.splitlines()
        )

    @classmethod
    def _git_path(cls, *args: str, cwd: Path) -> Path:
        value = Path(cls._git(*args, cwd=cwd))
        return (cwd / value).resolve() if not value.is_absolute() else value.resolve()

    @staticmethod
    def _git(*args: str, cwd: Path) -> str:
        return _run_git(("-C", str(cwd), *args))

    @staticmethod
    def _run_git(args: tuple[str, ...]) -> str:
        return _run_git(args)
