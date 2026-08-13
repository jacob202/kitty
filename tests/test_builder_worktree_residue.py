"""Tests for Codex staging residue exclusion in ensure_worktree().

Verifies that a worktree whose only dirty paths are .kittybuilder-codex-*
runner staging files is treated as clean (reusable), while any unrelated dirty
file still causes ensure_worktree to fail closed.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from gateway import builder_runner as br


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A git repo with one commit on main."""
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)
    (root / "README.md").write_text("hello\n")
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=root, check=True)
    return root


# ---------------------------------------------------------------------------
# Codex staging residue exclusion
# ---------------------------------------------------------------------------


class TestCodexStagingResidue:
    """ensure_worktree reuses a worktree whose only dirtiness is Codex staging."""

    def test_codex_only_residue_reusable(self, repo: Path):
        """A worktree containing only .kittybuilder-codex-* files should be
        treated as clean when reuse_dirty=False."""
        branch = "kittybuilder/kb_codex_residue"
        path = br.ensure_worktree("kb_codex_residue", branch, repo_root=repo)

        # Simulate Codex staging residue (the files from a prior failed attempt).
        (path / ".kittybuilder-codex-139-bundle.json").write_text("{}\n")
        (path / ".kittybuilder-codex-139-context.json").write_text("{}\n")
        (path / ".kittybuilder-codex-139-schema.json").write_text("{}\n")

        # reuse_dirty=False must still succeed — the residue is excluded.
        reused = br.ensure_worktree("kb_codex_residue", branch, repo_root=repo)
        assert reused == path

    def test_non_residue_dirty_file_still_fails(self, repo: Path):
        """Adding an unrelated dirty file to a worktree must still raise
        RunnerError, even if Codex staging residue is also present."""
        branch = "kittybuilder/kb_codex_mixed"
        path = br.ensure_worktree("kb_codex_mixed", branch, repo_root=repo)

        # Codex staging residue (should be ignored).
        (path / ".kittybuilder-codex-139-bundle.json").write_text("{}\n")

        # Unrelated dirty file (must NOT be ignored).
        (path / "outside.txt").write_text("unexpected\n")

        with pytest.raises(br.RunnerError, match="dirty"):
            br.ensure_worktree("kb_codex_mixed", branch, repo_root=repo)
