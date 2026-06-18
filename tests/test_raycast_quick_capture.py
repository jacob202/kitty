from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "raycast" / "kitty-quick-capture.sh"


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_raycast_quick_capture_script_writes_to_inbox(tmp_path):
    inbox_file = tmp_path / "inbox.jsonl"
    env = {
        **os.environ,
        "KITTY_INBOX_FILE": str(inbox_file),
        "KITTY_PYTHON": "python3.12",
    }

    result = subprocess.run(
        [str(SCRIPT), "Follow up on the Sansui recap"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Captured" in result.stdout
    rows = _rows(inbox_file)
    assert rows[0]["source"] == "raycast_quick_capture"
    assert rows[0]["text"] == "Follow up on the Sansui recap"
    assert rows[0]["processed"] is False


def test_raycast_quick_capture_script_rejects_empty_text(tmp_path):
    env = {
        **os.environ,
        "KITTY_INBOX_FILE": str(tmp_path / "inbox.jsonl"),
        "KITTY_PYTHON": "python3.12",
    }

    result = subprocess.run(
        [str(SCRIPT), "   "],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "Nothing captured" in result.stderr
