from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / ".githooks" / "pre-commit"
PUSH_HOOK = ROOT / ".githooks" / "pre-push"


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=check,
        timeout=30,
    )


def test_tracked_precommit_is_executable_and_runs_coordination_preflight() -> None:
    assert HOOK.exists()
    assert HOOK.stat().st_mode & stat.S_IXUSR
    text = HOOK.read_text(encoding="utf-8")
    assert "./kitty agent preflight --staged --json" in text


def test_hooks_setup_uses_tracked_githooks_directory() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "git config core.hooksPath .githooks" in makefile
    assert PUSH_HOOK.exists()
    assert PUSH_HOOK.stat().st_mode & stat.S_IXUSR
    assert "scripts/hooks/pre-push" in PUSH_HOOK.read_text(encoding="utf-8")


def _copy_runtime(repo: Path) -> None:
    (repo / "gateway" / "lib").mkdir(parents=True)
    for relative in (
        "gateway/__init__.py",
        "gateway/agent_coordination.py",
        "gateway/agent_coordination_cli.py",
        "gateway/agent_workspace.py",
        "gateway/db.py",
        "gateway/paths.py",
        "gateway/lib/load_env_safe.sh",
        "kitty",
    ):
        target = repo / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    shutil.copytree(ROOT / "coordination", repo / "coordination")
    shutil.copytree(ROOT / ".githooks", repo / ".githooks")


def _seed_repo(repo: Path) -> None:
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.name", "Kitty Test")
    _git(repo, "config", "user.email", "kitty-test@example.invalid")
    _copy_runtime(repo)
    (repo / "docs").mkdir()
    (repo / "docs" / "ROADMAP.md").write_text("roadmap\n", encoding="utf-8")
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "--no-verify", "-qm", "seed")
    _git(repo, "branch", "-M", "main")
    _git(repo, "config", "core.hooksPath", ".githooks")


def _agent_env(tmp_path: Path) -> dict[str, str]:
    return {
        **os.environ,
        "PYTHON_BIN": sys.executable,
        "KITTY_AGENT_SESSION_ID": "fresh-worktree-owner",
        "KITTY_AGENT_PARTICIPANT": "chatgpt",
        "KITTY_DATA_ROOT": str(tmp_path / "data"),
    }


@pytest.mark.integration
def test_fresh_worktree_inherits_hook_and_blocks_unauthorized_staged_mutation(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    fresh = tmp_path / "fresh"
    _seed_repo(repo)
    _git(repo, "worktree", "add", "-qb", "feature", str(fresh), "main")
    assert _git(fresh, "config", "--get", "core.hooksPath").stdout.strip() == ".githooks"

    env = _agent_env(tmp_path)
    claim = subprocess.run(
        [
            str(fresh / "kitty"), "agent", "claim",
            "--resource", "docs:roadmap",
            "--role", "OWN",
            "--paths", "docs/ROADMAP.md",
            "--json",
        ],
        cwd=fresh,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert claim.returncode == 0, claim.stderr

    (fresh / "README.md").write_text("seed\nunauthorized\n", encoding="utf-8")
    _git(fresh, "add", "README.md")
    commit = subprocess.run(
        ["git", "commit", "-m", "unauthorized mutation"],
        cwd=fresh,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert commit.returncode != 0
    combined = commit.stdout + commit.stderr
    assert "MUTATION BLOCKED" in combined
    assert "outside the declared path fence" in combined
