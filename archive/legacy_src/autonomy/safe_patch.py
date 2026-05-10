from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


class UnsafePatchPath(ValueError):
    """Raised when an auto patch attempts to write outside the allow-list."""


@dataclass(frozen=True)
class PatchResult:
    success: bool
    branch: str
    worktree: Path
    output: str


Runner = Callable[[list[str], Path], subprocess.CompletedProcess]


class SafePatch:
    """
    Apply generated changes in a disposable git worktree.

    This avoids destructive rollback in the user's dirty checkout. Only
    allow-listed non-core paths may be written by automation.
    """

    DEFAULT_ALLOW_PREFIXES = (
        "data/agents/",
        "src/skills/",
        "config/specialists/",
        "docs/generated/",
    )

    def __init__(
        self,
        repo_root: str | Path,
        *,
        eval_command: list[str] | None = None,
        runner: Runner | None = None,
        allow_prefixes: tuple[str, ...] | None = None,
    ) -> None:
        self.repo_root = Path(repo_root).expanduser().resolve()
        self.eval_command = eval_command or self._default_eval_command()
        self.runner = runner or self._run
        self.allow_prefixes = allow_prefixes or self.DEFAULT_ALLOW_PREFIXES

    def apply_files(self, job_id: str, files: dict[str, str]) -> PatchResult:
        if not files:
            raise ValueError("files cannot be empty")

        branch = self._branch_name(job_id)
        worktree = self.repo_root / ".kitty_worktrees" / branch

        for rel_path in files:
            self.validate_path(rel_path)

        try:
            self.runner(["git", "worktree", "add", "-B", branch, worktree], self.repo_root)

            for rel_path, content in files.items():
                target = worktree / rel_path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content)

            self.runner(self.eval_command, worktree)
            self.runner(["git", "add", *files.keys()], worktree)
            self.runner(["git", "commit", "-m", f"auto patch {job_id}"], worktree)

            return PatchResult(True, branch, worktree, "patch applied in isolated worktree")
        except Exception as exc:
            return PatchResult(False, branch, worktree, str(exc))

    def validate_path(self, rel_path: str) -> None:
        path = Path(rel_path)
        if path.is_absolute() or ".." in path.parts:
            raise UnsafePatchPath(f"unsafe patch path: {rel_path}")

        normalized = path.as_posix()
        if not any(normalized.startswith(prefix) for prefix in self.allow_prefixes):
            raise UnsafePatchPath(f"path is not automation allow-listed: {rel_path}")

    def _branch_name(self, job_id: str) -> str:
        cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "-", job_id).strip("-")
        return f"auto-patch-{cleaned or 'job'}"

    def _default_eval_command(self) -> list[str]:
        if (self.repo_root / "scripts" / "eval_loop.py").exists():
            return [sys.executable, "scripts/eval_loop.py"]
        if (self.repo_root / "scripts" / "run_eval.py").exists():
            return [sys.executable, "scripts/run_eval.py"]
        return [sys.executable, "-m", "pytest", "tests/", "-q", "--tb=short"]

    def _run(self, command: list[str], cwd: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            [str(part) for part in command],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
        )
