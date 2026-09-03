from __future__ import annotations

import subprocess
from pathlib import Path

from gateway.run_workspace import GitWorktreeManager, snapshot_existing_worktree


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["/usr/bin/git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _init_repo(path: Path) -> str:
    path.mkdir()
    _git(path, "init")
    _git(path, "config", "user.email", "test@example.com")
    _git(path, "config", "user.name", "Test User")
    (path / "tracked.txt").write_text("base\n", encoding="utf-8")
    (path / ".gitignore").write_text("ignored.txt\n", encoding="utf-8")
    _git(path, "add", "tracked.txt", ".gitignore")
    _git(path, "commit", "-m", "base")
    return _git(path, "rev-parse", "HEAD")


def test_snapshot_sees_all_deliverable_states_and_separates_ignored(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    base = _init_repo(repo)

    (repo / "committed.txt").write_text("committed\n", encoding="utf-8")
    _git(repo, "add", "committed.txt")
    _git(repo, "commit", "-m", "committed change")
    (repo / "staged.txt").write_text("staged\n", encoding="utf-8")
    _git(repo, "add", "staged.txt")
    (repo / "tracked.txt").write_text("dirty\n", encoding="utf-8")
    (repo / "untracked.txt").write_text("untracked\n", encoding="utf-8")
    (repo / "ignored.txt").write_text("ignored\n", encoding="utf-8")

    snapshot = snapshot_existing_worktree(repo, base_commit=base)

    assert snapshot.changed_paths == (
        "committed.txt",
        "staged.txt",
        "tracked.txt",
        "untracked.txt",
    )
    assert snapshot.ignored_paths == ("ignored.txt",)
    assert snapshot.mutation_paths == (
        "committed.txt",
        "ignored.txt",
        "staged.txt",
        "tracked.txt",
        "untracked.txt",
    )
    assert snapshot.dirty is True


def test_manager_audit_remains_bound_after_worktree_gitfile_tamper(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    manager = GitWorktreeManager(repo=repo, base_ref="HEAD", run_root=tmp_path / "runs")
    worktree = manager.create("audit-run")

    (worktree / ".git").write_text("gitdir: /tmp/attacker-gitdir\n", encoding="utf-8")
    (worktree / "unexpected.txt").write_text("mutation\n", encoding="utf-8")

    snapshot = manager.audit(worktree)

    assert "unexpected.txt" in snapshot.changed_paths


def test_snapshot_preserves_whitespace_in_nul_delimited_paths(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    base = _init_repo(repo)
    weird = " leading-and-trailing .txt "
    (repo / weird).write_text("weird\n", encoding="utf-8")

    snapshot = snapshot_existing_worktree(repo, base_commit=base)

    assert weird in snapshot.changed_paths


def test_snapshot_fails_closed_when_git_times_out(tmp_path: Path, monkeypatch) -> None:
    from gateway import run_workspace

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=["/usr/bin/git"], timeout=20)

    monkeypatch.setattr(run_workspace.subprocess, "run", timeout)

    try:
        snapshot_existing_worktree(tmp_path, base_commit="a" * 40)
    except run_workspace.RunWorkspaceError as exc:
        assert "timed out" in str(exc).lower()
    else:
        raise AssertionError("a timed-out git audit must fail closed")
