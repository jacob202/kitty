"""Tests for Builder-owned deterministic PR janitor repairs."""

from __future__ import annotations

import importlib
import subprocess
from pathlib import Path

import pytest


def _janitor():
    try:
        return importlib.import_module("gateway.builder_pr_janitor")
    except ModuleNotFoundError:
        pytest.fail("gateway.builder_pr_janitor is not implemented")


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "janitor@example.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "PR Janitor Test"], cwd=root, check=True)
    (root / "gateway").mkdir()
    (root / ".claude").mkdir()
    (root / "gateway" / "sample.py").write_text("value = 1\n", encoding="utf-8")
    (root / ".claude" / "STATE.md").write_text("stable\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=root, check=True)
    return root


def _runner_with_ruff_action(action):
    def run(args: list[str], *, cwd: Path | None = None, check: bool = False) -> subprocess.CompletedProcess[str]:
        assert cwd is not None
        if "ruff" in args and "--fix" in args:
            action(Path(cwd))
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
        return subprocess.run(args, cwd=cwd, check=check, capture_output=True, text=True)

    return run


def test_no_change_returns_clean_receipt(tmp_path: Path):
    bj = _janitor()
    root = _repo(tmp_path)
    result = bj.apply_safe_repairs(root, run_cmd=_runner_with_ruff_action(lambda _: None))
    assert result["changed"] is False
    assert result["changed_paths"] == []
    assert result["commit_sha"] is None
    assert subprocess.run(["git", "status", "--porcelain"], cwd=root, capture_output=True, text=True).stdout == ""


def test_ruff_fix_is_committed_and_worktree_left_clean(tmp_path: Path):
    bj = _janitor()
    root = _repo(tmp_path)

    def fix(worktree: Path) -> None:
        (worktree / "gateway" / "sample.py").write_text("value = 2\n", encoding="utf-8")

    result = bj.apply_safe_repairs(root, run_cmd=_runner_with_ruff_action(fix))
    assert result["changed"] is True
    assert result["changed_paths"] == ["gateway/sample.py"]
    assert result["commit_sha"] == subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True
    ).stdout.strip()
    subject = subprocess.run(
        ["git", "log", "-1", "--pretty=%s"], cwd=root, capture_output=True, text=True, check=True
    ).stdout.strip()
    assert subject == "fix: apply PR janitor repairs"
    assert subprocess.run(["git", "status", "--porcelain"], cwd=root, capture_output=True, text=True).stdout == ""


def test_ephemeral_done_marker_does_not_block_safe_repairs(tmp_path: Path):
    bj = _janitor()
    root = _repo(tmp_path)
    (root / "done.txt").write_text("ok\n", encoding="utf-8")

    result = bj.apply_safe_repairs(
        root, run_cmd=_runner_with_ruff_action(lambda _: None)
    )

    assert result["changed"] is False
    assert result["changed_paths"] == []
    assert (root / "done.txt").exists()


def test_repair_commit_can_carry_packet_identity_marker(tmp_path: Path):
    bj = _janitor()
    root = _repo(tmp_path)

    def fix(worktree: Path) -> None:
        (worktree / "gateway" / "sample.py").write_text("value = 4\n", encoding="utf-8")

    bj.apply_safe_repairs(
        root,
        commit_marker="[LP-1]",
        run_cmd=_runner_with_ruff_action(fix),
    )
    subject = subprocess.run(
        ["git", "log", "-1", "--pretty=%s"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert subject == "fix: apply PR janitor repairs [LP-1]"


def test_dirty_worktree_is_refused_before_ruff_runs(tmp_path: Path):
    bj = _janitor()
    root = _repo(tmp_path)
    (root / "gateway" / "sample.py").write_text("already dirty\n", encoding="utf-8")
    called = False

    def should_not_run(_: Path) -> None:
        nonlocal called
        called = True

    with pytest.raises(bj.SafeRepairError, match="dirty"):
        bj.apply_safe_repairs(root, run_cmd=_runner_with_ruff_action(should_not_run))
    assert called is False


def test_change_outside_packet_scope_is_rolled_back_and_refused(tmp_path: Path):
    bj = _janitor()
    root = _repo(tmp_path)

    def out_of_scope_fix(worktree: Path) -> None:
        (worktree / "gateway" / "sample.py").write_text("value = 3\n", encoding="utf-8")

    with pytest.raises(bj.SafeRepairError, match="packet scope"):
        bj.apply_safe_repairs(
            root,
            allowed_paths=["tests/"],
            run_cmd=_runner_with_ruff_action(out_of_scope_fix),
        )
    assert (root / "gateway" / "sample.py").read_text(encoding="utf-8") == "value = 1\n"
    assert subprocess.run(
        ["git", "status", "--porcelain"], cwd=root, capture_output=True, text=True
    ).stdout == ""


def test_forbidden_path_change_is_rolled_back_and_refused(tmp_path: Path):
    bj = _janitor()
    root = _repo(tmp_path)

    def bad_fix(worktree: Path) -> None:
        (worktree / ".claude" / "STATE.md").write_text("tampered\n", encoding="utf-8")

    with pytest.raises(bj.SafeRepairError, match="forbidden path"):
        bj.apply_safe_repairs(root, run_cmd=_runner_with_ruff_action(bad_fix))
    assert (root / ".claude" / "STATE.md").read_text(encoding="utf-8") == "stable\n"
    assert subprocess.run(["git", "status", "--porcelain"], cwd=root, capture_output=True, text=True).stdout == ""
