from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .models import DiffAudit

_SAFE_RUN_ID = re.compile(r"^[A-Za-z0-9._-]+$")


@dataclass
class GitWorktreeManager:
    repo: Path
    base_ref: str = "HEAD"
    run_root: Path | None = None
    _authenticated: dict[Path, "WorktreeIdentity"] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        self.repo = self.repo.resolve()
        if self.run_root is None:
            self.run_root = self.repo.parent / ".discord-command-center-worktrees" / self.repo.name
        self.run_root = self.run_root.resolve()

    def create(self, run_id: str) -> Path:
        if not _SAFE_RUN_ID.fullmatch(run_id):
            raise ValueError("run_id contains unsafe characters")
        run_root = self.run_root
        assert run_root is not None
        path = run_root / run_id
        if path.exists():
            raise FileExistsError(f"run worktree already exists: {path}")
        run_root.mkdir(parents=True, exist_ok=True)
        repo_git_dir = self._git_path("rev-parse", "--git-dir", cwd=self.repo)
        repo_common_dir = self._git_path("rev-parse", "--git-common-dir", cwd=self.repo)
        base_commit = self._git("rev-parse", self.base_ref, cwd=self.repo)
        self._git("worktree", "add", "--detach", str(path), base_commit, cwd=self.repo)
        try:
            worktree_git_dir = self._git_path("rev-parse", "--git-dir", cwd=path)
            worktree_common_dir = self._git_path("rev-parse", "--git-common-dir", cwd=path)
            worktree_commit = self._git("rev-parse", "HEAD", cwd=path)
            if worktree_commit != base_commit or worktree_common_dir != repo_common_dir:
                raise RuntimeError(
                    "linked worktree identity did not match its controlling repository"
                )
        except Exception as primary_error:
            self._remove_created_worktree(path, primary_error)
            raise
        self._authenticated[path] = WorktreeIdentity(
            repo_git_dir=repo_git_dir,
            repo_common_dir=repo_common_dir,
            worktree_git_dir=worktree_git_dir,
            base_commit=base_commit,
        )
        return path

    def audit(self, path: Path) -> DiffAudit:
        identity = self._authenticated.get(path.resolve())
        if identity is None:
            raise RuntimeError(f"worktree was not authenticated before audit: {path}")
        self._verify_identity(identity, path)
        status = self._trusted_git(
            "status", "--porcelain=v1", "--untracked-files=all", cwd=path
        )
        status_lines = tuple(line for line in status.splitlines() if line.strip())
        ignored = self._trusted_git(
            "ls-files", "--others", "--ignored", "--exclude-standard", cwd=path
        )
        ignored_lines = tuple(
            f"!! {line}" for line in ignored.splitlines() if line.strip()
        )
        status_lines = status_lines + ignored_lines
        insertions = 0
        deletions = 0
        numstat = self._trusted_git("diff", "--numstat", identity.base_commit, "--", cwd=path)
        for line in numstat.splitlines():
            parts = line.split("\t", 2)
            if len(parts) < 2:
                continue
            if parts[0].isdigit():
                insertions += int(parts[0])
            if parts[1].isdigit():
                deletions += int(parts[1])
        return DiffAudit(
            files=len(status_lines),
            insertions=insertions,
            deletions=deletions,
            status_lines=status_lines,
        )

    def remove(self, path: Path) -> None:
        self._git("worktree", "remove", "--force", str(path), cwd=self.repo)
        self._git("worktree", "prune", cwd=self.repo)
        self._authenticated.pop(path.resolve(), None)

    def _verify_identity(self, identity: "WorktreeIdentity", path: Path) -> None:
        if self._git_path("rev-parse", "--git-dir", cwd=self.repo) != identity.repo_git_dir:
            raise RuntimeError("controlling repository gitdir changed")
        if (
            self._git_path("rev-parse", "--git-common-dir", cwd=self.repo)
            != identity.repo_common_dir
        ):
            raise RuntimeError("controlling repository common gitdir changed")
        if self._trusted_git("rev-parse", "HEAD", cwd=path) != identity.base_commit:
            raise RuntimeError("linked worktree base commit changed")

    def _trusted_git(self, *args: str, cwd: Path) -> str:
        identity = self._authenticated[cwd.resolve()]
        return self._run_git(
            ("--git-dir", str(identity.worktree_git_dir), "--work-tree", str(cwd), *args)
        )

    def _remove_created_worktree(self, path: Path, primary_error: Exception) -> None:
        cleanup_error: Exception | None = None
        try:
            self._git("worktree", "remove", "--force", str(path), cwd=self.repo)
        except Exception as exc:
            cleanup_error = exc

        verification_error: Exception | None = None
        try:
            path_exists = path.exists()
            registered = self._worktree_is_registered(path)
            remaining = path_exists or registered
        except Exception as exc:
            remaining = False
            verification_error = exc

        if cleanup_error is not None or verification_error is not None or remaining:
            if cleanup_error is not None:
                detail = f"cleanup failed: {type(cleanup_error).__name__}: {cleanup_error}"
            elif verification_error is not None:
                detail = (
                    f"verification failed: {type(verification_error).__name__}: "
                    f"{verification_error}"
                )
            else:
                detail = "the exact path or registration remains"
            raise RuntimeError(
                f"{type(primary_error).__name__}: {primary_error}; "
                f"cleanup not confirmed for {path}: {detail}"
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
        return GitWorktreeManager._run_git(("-C", str(cwd), *args))

    @staticmethod
    def _run_git(args: tuple[str, ...]) -> str:
        result = subprocess.run(
            ["/usr/bin/git", *args],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode:
            detail = (result.stderr or result.stdout).strip()
            raise RuntimeError(
                f"git {' '.join(args)} failed with exit {result.returncode}: {detail}"
            )
        return result.stdout.strip()


@dataclass(frozen=True)
class WorktreeIdentity:
    repo_git_dir: Path
    repo_common_dir: Path
    worktree_git_dir: Path
    base_commit: str
