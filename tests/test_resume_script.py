"""Contract tests for scripts/resume.py."""
import datetime as dt
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "resume.py"


def _run() -> subprocess.CompletedProcess:
    """Invoke resume.py as a subprocess from the worktree root."""
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
        cwd=ROOT,
        timeout=30,
    )


class TestScriptExists:
    """Verify the script file is present and syntactically valid."""

    def test_script_file_present(self):
        assert SCRIPT.exists(), f"Missing: {SCRIPT}"

    def test_script_is_valid_python(self):
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", str(SCRIPT)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr


class TestResumeOutput:
    """Verify the script exits 0 and surfaces branch + date in output."""

    def test_exits_zero(self):
        result = _run()
        assert result.returncode == 0, (
            f"resume.py exited {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_output_contains_today(self):
        result = _run()
        today = dt.date.today().isoformat()
        assert today in result.stdout, (
            f"Expected {today!r} in stdout; got:\n{result.stdout}"
        )

    def test_output_contains_current_branch(self):
        branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            cwd=ROOT,
        ).stdout.strip()
        result = _run()
        assert branch and branch in result.stdout, (
            f"Expected branch {branch!r} in stdout; got:\n{result.stdout}"
        )
