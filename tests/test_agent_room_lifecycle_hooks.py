from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SETTINGS = ROOT / ".claude/settings.json"
START_HOOK = ROOT / ".claude/hooks/session-start.sh"


def _hook_entries(event: str) -> list[dict[str, object]]:
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
    return [
        hook
        for group in settings["hooks"].get(event, [])
        for hook in group.get("hooks", [])
    ]


def test_lifecycle_settings_unwire_gar_and_non_safety_completion_gates() -> None:
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
    assert "SessionEnd" not in settings["hooks"]

    start_commands = [str(h.get("command", "")) for h in _hook_entries("SessionStart")]
    assert start_commands == ["bash .claude/hooks/session-start.sh"]
    assert not any("recall-thread" in command for command in start_commands)

    stop = _hook_entries("Stop")
    assert not any(h.get("type") == "prompt" for h in stop)
    stop_commands = [str(h.get("command", "")) for h in stop]
    assert stop_commands == ["bash .claude/hooks/warn-unpushed.sh"]
    assert not any("session-stop" in command for command in stop_commands)
    assert not any("turn-end-gate" in command for command in stop_commands)


def test_session_start_does_not_call_room_or_write_gar_state(tmp_path: Path) -> None:
    marker = tmp_path / "room-called"
    room = tmp_path / "room-stub"
    room.write_text(f"#!/bin/sh\ntouch {marker}\nexit 99\n", encoding="utf-8")
    room.chmod(0o755)
    state = tmp_path / "gar-state"
    env = {
        **os.environ,
        "KITTY_ROOM_CLI": str(room),
        "KITTY_GAR_STATE_DIR": str(state),
    }
    result = subprocess.run(
        ["bash", str(START_HOOK)], input='{"session_id":"suspended"}',
        cwd=ROOT, env=env, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0
    assert not marker.exists()
    assert not state.exists()
    assert "[GAR]" not in result.stdout
    assert "gar-session:" not in result.stdout


def test_session_start_reports_live_git_context_only() -> None:
    result = subprocess.run(
        ["bash", str(START_HOOK)], cwd=ROOT, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0
    assert "Branch:" in result.stdout or "HEAD: detached" in result.stdout
    assert "workspace_global" not in result.stdout
