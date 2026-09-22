from __future__ import annotations

import stat
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / ".githooks" / "pre-commit"
PUSH_HOOK = ROOT / ".githooks" / "pre-push"
CLAIM = ROOT / "scripts" / "work_claim.py"


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True,
        check=check, timeout=30,
    )


def test_tracked_precommit_uses_local_worktree_claim_preflight() -> None:
    assert HOOK.exists()
    assert HOOK.stat().st_mode & stat.S_IXUSR
    text = HOOK.read_text(encoding="utf-8")
    assert "scripts/work_claim.py preflight --staged" in text
    assert "kitty agent preflight" not in text


def test_hooks_setup_keeps_remote_pre_push_gate() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "git config core.hooksPath .githooks" in makefile
    assert PUSH_HOOK.exists()
    assert PUSH_HOOK.stat().st_mode & stat.S_IXUSR
    assert "scripts/hooks/pre-push" in PUSH_HOOK.read_text(encoding="utf-8")


@pytest.mark.integration
def test_fresh_worktree_hook_blocks_staged_path_outside_claim(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.name", "Kitty Test")
    _git(repo, "config", "user.email", "kitty-test@example.invalid")
    (repo / "scripts").mkdir()
    (repo / ".githooks").mkdir()
    (repo / "docs").mkdir()
    (repo / "README.md").write_text("seed\n")
    (repo / "docs" / "owned.md").write_text("owned\n")
    (repo / "scripts" / "work_claim.py").write_bytes(CLAIM.read_bytes())
    (repo / ".githooks" / "pre-commit").write_bytes(HOOK.read_bytes())
    (repo / ".githooks" / "pre-commit").chmod(0o755)
    _git(repo, "add", ".")
    _git(repo, "commit", "--no-verify", "-m", "seed")
    _git(repo, "config", "core.hooksPath", ".githooks")

    fresh = tmp_path / "fresh"
    _git(repo, "worktree", "add", "-b", "feature", str(fresh), "main")
    claim = subprocess.run(
        [sys.executable, str(fresh / "scripts/work_claim.py"), "claim",
         "--owner", "alpha", "--task", "test", "--path", "docs"],
        cwd=fresh, capture_output=True, text=True, timeout=30,
    )
    assert claim.returncode == 0, claim.stderr

    (fresh / "README.md").write_text("seed\nunauthorized\n")
    _git(fresh, "add", "README.md")
    commit = subprocess.run(
        ["git", "commit", "-m", "unauthorized"], cwd=fresh,
        capture_output=True, text=True, timeout=30,
    )
    assert commit.returncode != 0
    assert "outside claim" in (commit.stdout + commit.stderr)
