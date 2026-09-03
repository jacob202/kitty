"""Discord compatibility wrapper for the shared run-workspace primitive."""
from __future__ import annotations

from gateway.run_workspace import GitWorktreeManager as _SharedGitWorktreeManager
from gateway.run_workspace import WorktreeIdentity


class GitWorktreeManager(_SharedGitWorktreeManager):
    """Preserve Command Center's historical worktree location while sharing logic."""

    def __post_init__(self) -> None:
        self.repo = self.repo.resolve()
        if self.run_root is None:
            self.run_root = (
                self.repo.parent / ".discord-command-center-worktrees" / self.repo.name
            )
        super().__post_init__()



__all__ = ["GitWorktreeManager", "WorktreeIdentity"]
