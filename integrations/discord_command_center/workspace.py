from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .models import DiffAudit

_SAFE_RUN_ID = re.compile(r"^[A-Za-z0-9._-]+$")


@dataclass
class GitWorktreeManager:
    repo: Path
    base_ref: str = "HEAD"
    run_root: Path | None = None

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
        self._git("worktree", "add", "--detach", str(path), self.base_ref, cwd=self.repo)
        return path

    def audit(self, path: Path) -> DiffAudit:
        status = self._git(
            "status", "--porcelain=v1", "--untracked-files=all", cwd=path
        )
        status_lines = tuple(line for line in status.splitlines() if line.strip())
        ignored = self._git(
            "ls-files", "--others", "--ignored", "--exclude-standard", cwd=path
        )
        ignored_lines = tuple(
            f"!! {line}" for line in ignored.splitlines() if line.strip()
        )
        status_lines = status_lines + ignored_lines
        insertions = 0
        deletions = 0
        numstat = self._git("diff", "--numstat", "HEAD", "--", cwd=path)
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

    @staticmethod
    def _git(*args: str, cwd: Path) -> str:
        result = subprocess.run(
            ["/usr/bin/git", "-C", str(cwd), *args],
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
