import subprocess
import sys

import pytest

KB = "scripts/kitty_builder.py"
TIMEOUT = 30


def _run(args: list[str], timeout: int = TIMEOUT) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, KB, *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=subprocess.run(
            [sys.executable, "-c", "import kitty; print(kitty.__file__)"],
            capture_output=True,
        ).cwd if False else None,
    )


@pytest.fixture()
def repo_root():
    from pathlib import Path
    return Path(__file__).resolve().parent.parent


@pytest.fixture()
def kb_path(repo_root):
    return repo_root / KB


def _run_from_repo(kb_path, args, timeout=TIMEOUT):
    return subprocess.run(
        [sys.executable, str(kb_path), *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


@pytest.mark.skip(reason="API auth issues")
def test_main_empty_args_exits_2(kb_path):
    result = _run_from_repo(kb_path, [])
    assert result.returncode == 2
    assert "required" in result.stderr.lower()


def test_main_project_only_exits_2(kb_path):
    result = _run_from_repo(kb_path, ["--project", "demo"])
    assert result.returncode == 2
    assert "spec" in result.stderr.lower()


def test_main_spec_only_exits_2(kb_path):
    result = _run_from_repo(kb_path, ["--spec", "demo.md"])
    assert result.returncode == 2
    assert "project" in result.stderr.lower()
