"""Contract tests for the continuity CI wrapper."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "check_continuity_state.py"
STATE = ROOT / ".claude" / "STATE.md"
HANDOFF = ROOT / ".claude" / "HANDOFF.md"


def _run(max_age_days: int) -> subprocess.CompletedProcess:
    """Invoke check_continuity_state.py as a subprocess and return the result."""
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--max-age-days", str(max_age_days)],
        capture_output=True,
        text=True,
    )


class TestScriptExists:
    """Verify the script file is present and syntactically valid."""

    def test_script_file_present(self):
        """Script must exist at the expected path."""
        assert SCRIPT.exists(), f"Missing: {SCRIPT}"

    def test_script_is_valid_python(self):
        """Script must compile without errors."""
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", str(SCRIPT)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr


class TestCheckpointFiles:
    """Verify both active checkpoint files use strict structured metadata."""

    def test_handoff_file_present(self):
        assert HANDOFF.exists(), f".claude/HANDOFF.md not found at {HANDOFF}"

    def test_state_file_present(self):
        assert STATE.exists(), f".claude/STATE.md not found at {STATE}"

    def test_checkpoint_markers_present(self):
        assert "<!-- kitty-state" in STATE.read_text(encoding="utf-8")
        assert "<!-- kitty-handoff" in HANDOFF.read_text(encoding="utf-8")


class TestScriptBehavior:
    """Verify exit codes and output for various --max-age-days values."""

    def test_passes_with_generous_limit(self):
        """The repository's current checkpoint must satisfy the full contract."""
        result = _run(max_age_days=3650)
        assert result.returncode == 0, f"Expected pass but got:\n{result.stdout}{result.stderr}"
        assert "PASS:" in result.stdout

    def test_fails_with_zero_days(self):
        """A zero-day limit makes the recorded checkpoint stale."""
        result = _run(max_age_days=0)
        assert result.returncode == 1, f"Expected fail but got:\n{result.stdout}{result.stderr}"
        assert "FAIL:" in result.stdout

    def test_current_checkpoint_within_seven_days(self):
        """Real CI gate: both active checkpoints must be fresh and consistent."""
        result = _run(max_age_days=7)
        assert result.returncode == 0, (
            "active checkpoint is stale or inconsistent — replace it before stopping\n"
            f"{result.stdout}{result.stderr}"
        )

    def test_json_output_is_structured(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--max-age-days", "3650", "--json"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        payload = json.loads(result.stdout)
        assert payload["ok"] is True
        assert payload["summary"]["fail"] == 0
        assert payload["checks"]
