"""Contract tests for scripts/check_continuity_state.py."""
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "check_continuity_state.py"
HANDOFF = ROOT / "SESSION_HANDOFF.md"


def _run(max_age_days: int) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--max-age-days", str(max_age_days)],
        capture_output=True,
        text=True,
    )


class TestScriptExists:
    def test_script_file_present(self):
        assert SCRIPT.exists(), f"Missing: {SCRIPT}"

    def test_script_is_valid_python(self):
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", str(SCRIPT)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr


class TestHandoffPresent:
    def test_handoff_file_present(self):
        assert HANDOFF.exists(), f"SESSION_HANDOFF.md not found at {HANDOFF}"

    def test_handoff_contains_date(self):
        import re
        text = HANDOFF.read_text(encoding="utf-8")
        dates = re.findall(r"\b\d{4}-\d{2}-\d{2}\b", text)
        assert dates, "SESSION_HANDOFF.md contains no ISO date (YYYY-MM-DD)"


class TestScriptBehavior:
    def test_passes_with_generous_limit(self):
        # 3650 days (10 years) should always pass
        result = _run(max_age_days=3650)
        assert result.returncode == 0, f"Expected pass but got:\n{result.stdout}{result.stderr}"
        assert "OK:" in result.stdout

    def test_fails_with_zero_days(self):
        # A 0-day limit means any handoff is too old
        result = _run(max_age_days=0)
        assert result.returncode == 1, f"Expected fail but got:\n{result.stdout}{result.stderr}"
        assert "FAIL:" in result.stdout

    def test_current_handoff_within_21_days(self):
        # The real CI gate — SESSION_HANDOFF.md must be < 21 days old
        result = _run(max_age_days=21)
        assert result.returncode == 0, (
            f"SESSION_HANDOFF.md is more than 21 days old — update it!\n"
            f"{result.stdout}{result.stderr}"
        )

    def test_output_contains_age(self):
        result = _run(max_age_days=3650)
        assert "days old" in result.stdout
