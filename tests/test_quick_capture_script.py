from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts.quick_capture import main


def _read_rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_quick_capture_writes_direct_text(tmp_path, capsys):
    inbox_file = tmp_path / "inbox.jsonl"

    result = main(
        [
            "remember",
            "bias",
            "trim",
            "--tag",
            "sansui",
            "--project",
            "repair",
            "--inbox-file",
            str(inbox_file),
        ]
    )

    assert result == 0
    rows = _read_rows(inbox_file)
    assert len(rows) == 1
    assert rows[0]["source"] == "desktop_quick_capture"
    assert rows[0]["type"] == "text"
    assert rows[0]["text"] == "remember bias trim"
    assert rows[0]["processed"] is False
    assert rows[0]["project"] == "repair"
    assert rows[0]["tags"] == ["sansui"]
    assert "Captured" in capsys.readouterr().out


def test_quick_capture_reads_stdin_text(tmp_path):
    inbox_file = tmp_path / "inbox.jsonl"

    result = main(["--source", "raycast_quick_capture", "--inbox-file", str(inbox_file)], "What am I avoiding?")

    assert result == 0
    rows = _read_rows(inbox_file)
    assert rows[0]["source"] == "raycast_quick_capture"
    assert rows[0]["text"] == "What am I avoiding?"


def test_quick_capture_rejects_empty_text(tmp_path, capsys):
    result = main(["--inbox-file", str(tmp_path / "inbox.jsonl")], "   ")

    assert result == 2
    assert "Nothing captured" in capsys.readouterr().err
