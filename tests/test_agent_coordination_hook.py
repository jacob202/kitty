from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "scripts/pre-commit.template"


def _repo(tmp_path: Path, *, guard_rc: int) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    (repo / "kitty").write_text(
        "#!/bin/sh\n"
        "if [ \"$1 $2 $3\" = \"agent guard --staged\" ]; then\n"
        f"  echo guard-rc-{guard_rc}\n  exit {guard_rc}\n"
        "fi\nexit 99\n",
        encoding="utf-8",
    )
    (repo / "kitty").chmod(0o755)
    (repo / "tests").mkdir()
    (repo / "tests/test_ok.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    (repo / "tracked.txt").write_text("before\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "base"],
        check=True,
    )
    (repo / "tracked.txt").write_text("after\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "tracked.txt"], check=True)
    hook = repo / ".git/hooks/pre-commit"
    shutil.copy2(TEMPLATE, hook)
    hook.chmod(0o755)
    return repo


def test_precommit_blocks_before_tests_when_coordination_guard_fails(tmp_path: Path) -> None:
    repo = _repo(tmp_path, guard_rc=2)
    result = subprocess.run(
        [str(repo / ".git/hooks/pre-commit")],
        cwd=repo,
        capture_output=True,
        text=True,
        env=os.environ.copy(),
        timeout=20,
    )
    assert result.returncode == 2
    assert "guard-rc-2" in result.stdout
    assert "Running pre-commit tests" not in result.stdout


def test_precommit_runs_existing_tests_after_coordination_guard_passes(tmp_path: Path) -> None:
    repo = _repo(tmp_path, guard_rc=0)
    result = subprocess.run(
        [str(repo / ".git/hooks/pre-commit")],
        cwd=repo,
        capture_output=True,
        text=True,
        env=os.environ.copy(),
        timeout=30,
    )
    assert "guard-rc-0" in result.stdout
    assert "Running pre-commit tests" in result.stdout


def test_tracked_precommit_hook_delegates_to_coordination_template() -> None:
    hook = ROOT / "scripts/hooks/pre-commit"
    assert hook.exists()
    text = hook.read_text(encoding="utf-8")
    assert "scripts/pre-commit.template" in text
    assert "exec" in text


def test_install_hooks_target_installs_tracked_hook_directory() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "git config core.hooksPath scripts/hooks" in makefile
    assert "pre-commit" in makefile.split("hooks:", 1)[1].split("\n\n", 1)[0]
