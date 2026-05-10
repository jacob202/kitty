import subprocess
from pathlib import Path

import pytest

from src.autonomy.safe_patch import SafePatch, UnsafePatchPath


def test_safe_patch_defaults_to_repo_eval_loop_when_present(tmp_path):
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "eval_loop.py").write_text("")

    patcher = SafePatch(repo_root=tmp_path)

    assert patcher.eval_command[1:] == ["scripts/eval_loop.py"]


def test_safe_patch_rejects_paths_outside_allowlist(tmp_path):
    patcher = SafePatch(repo_root=tmp_path)

    with pytest.raises(UnsafePatchPath):
        patcher.validate_path("src/core/orchestrator.py")

    with pytest.raises(UnsafePatchPath):
        patcher.validate_path("../escape.py")


def test_safe_patch_uses_worktree_not_dirty_checkout(tmp_path):
    calls = []

    def fake_runner(command, cwd):
        calls.append((command, Path(cwd)))
        if command[:3] == ["git", "worktree", "add"]:
            command[-1].mkdir(parents=True, exist_ok=True)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    patcher = SafePatch(
        repo_root=tmp_path,
        eval_command=["python", "-m", "compileall", "src/skills"],
        runner=fake_runner,
    )

    result = patcher.apply_files(
        "job-1",
        {"src/skills/demo/SKILL.md": "# Demo\n"},
    )

    assert result.success is True
    assert (tmp_path / ".kitty_worktrees" / "auto-patch-job-1" / "src/skills/demo/SKILL.md").exists()
    assert all(cwd != tmp_path for command, cwd in calls if command[0] != "git" or command[1] != "worktree")
