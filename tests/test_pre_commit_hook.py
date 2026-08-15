from __future__ import annotations

import stat
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "scripts" / "hooks" / "pre-commit"


def test_pre_commit_hook_exists_and_is_executable() -> None:
    assert HOOK.is_file()
    assert HOOK.stat().st_mode & stat.S_IXUSR


def test_pre_commit_hook_runs_fast_staged_safety_checks() -> None:
    text = HOOK.read_text(encoding="utf-8")
    assert "git diff --cached --check" in text
    assert "PRIVATE KEY" in text
    assert "check-no-macos-metadata.sh" in text
    assert "trufflehog" in text
    assert "--no-verification" in text
    assert "--fail" in text


def test_macos_metadata_checker_referenced_by_hooks_exists_and_is_executable() -> None:
    checker = ROOT / "scripts" / "check-no-macos-metadata.sh"
    assert checker.is_file()
    assert checker.stat().st_mode & stat.S_IXUSR
