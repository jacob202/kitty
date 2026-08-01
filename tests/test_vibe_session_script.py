from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "vibe_session.py"


def test_vibe_session_creates_scaffold_file(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["KITTY_VIBE_ROOT"] = str(tmp_path)

    result = subprocess.run(
        [
            "python3.12",
            str(SCRIPT),
            "Ship packet docs refresh",
            "--minutes",
            "45",
            "--active-task",
            "Update docs/reference/VIBE_CODER_WORKFLOW.md",
        ],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )

    assert result.returncode == 0
    output_path = Path(result.stdout.strip())
    assert output_path.exists()
    content = output_path.read_text(encoding="utf-8")
    assert "Outcome: Ship packet docs refresh" in content
    assert "Timebox: 45 minutes" in content
    assert "Active task: Update docs/reference/VIBE_CODER_WORKFLOW.md" in content
    assert "Parking-lot interruptions" in content
    assert "PR quality checklist" in content


def test_vibe_session_rejects_out_of_range_minutes(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["KITTY_VIBE_ROOT"] = str(tmp_path)

    result = subprocess.run(
        [
            "python3.12",
            str(SCRIPT),
            "Bad timebox",
            "--minutes",
            "30",
        ],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )

    assert result.returncode != 0
    assert "minutes must be between 45 and 90" in result.stderr
