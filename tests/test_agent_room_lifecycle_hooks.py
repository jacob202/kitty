from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
START_HOOK = ROOT / ".claude/hooks/session-start.sh"
STOP_HOOK = ROOT / ".claude/hooks/session-stop.sh"


def _stub_cli(tmp_path: Path) -> tuple[Path, Path]:
    log = tmp_path / "room.log"
    script = tmp_path / "kitty-room-stub"
    script.write_text(
        """#!/usr/bin/env bash
set -u
printf '%s\\n' "$*" >> "$KITTY_STUB_LOG"
if [[ "$1 $2" == "room recent" ]]; then
  printf '%s\\n' "${KITTY_STUB_RECENT_TEXT:-}"
  printf '%s' "${KITTY_STUB_RECENT_ERR:-}" >&2
  exit "${KITTY_STUB_RECENT_RC:-0}"
fi
if [[ "$1 $2" == "room inbox" ]]; then
  printf '%s\\n' "${KITTY_STUB_INBOX_TEXT:-}"
  printf '%s' "${KITTY_STUB_INBOX_ERR:-}" >&2
  exit "${KITTY_STUB_INBOX_RC:-0}"
fi
if [[ "$1 $2" == "room post" ]]; then
  exit "${KITTY_STUB_POST_RC:-0}"
fi
exit 1
""",
        encoding="utf-8",
    )
    script.chmod(0o755)
    return script, log


def _run(hook: Path, payload: dict[str, object], tmp_path: Path, **overrides: str):
    cli, log = _stub_cli(tmp_path)
    env = os.environ.copy()
    env.update(
        {
            "KITTY_ROOM_CLI": str(cli),
            "KITTY_STUB_LOG": str(log),
            "KITTY_GAR_STATE_DIR": str(tmp_path / "state"),
            "KITTY_GAR_OUTBOX_DIR": str(tmp_path / "outbox"),
        }
    )
    env.update(overrides)
    return subprocess.run(
        ["bash", str(hook)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=ROOT,
        env=env,
    )


def test_session_start_injects_recent_and_direct_unread_room_context(tmp_path: Path) -> None:
    result = _run(
        START_HOOK,
        {"session_id": "sess-start", "hook_event_name": "SessionStart"},
        tmp_path,
        KITTY_STUB_RECENT_TEXT="message_1: codex: exact-head review ready",
        KITTY_STUB_INBOX_TEXT="message_2: jacob: please verify PR #999",
    )

    assert result.returncode == 0
    assert "[GAR] workspace_global recent" in result.stdout
    assert "exact-head review ready" in result.stdout
    assert "[GAR] unread direct for claude" in result.stdout
    assert "please verify PR #999" in result.stdout
    assert "gar-session:sess-start" in result.stdout
    assert "reply in-thread" in result.stdout
    assert "room ack --as claude <message_id>" in result.stdout
    assert "Do not ACK unread work you did not consume" in result.stdout
    log = (tmp_path / "room.log").read_text(encoding="utf-8")
    assert "room recent --limit 8" in log
    assert "room inbox --as claude --unread --direct-only --limit 8" in log
    assert "room ack --as claude" not in log


def test_session_start_reports_room_failure_with_bounded_diagnostics(tmp_path: Path) -> None:
    result = _run(
        START_HOOK,
        {"session_id": "sess-down", "hook_event_name": "SessionStart"},
        tmp_path,
        KITTY_STUB_RECENT_RC="1",
        KITTY_STUB_INBOX_RC="2",
        KITTY_STUB_RECENT_ERR="database locked",
        KITTY_STUB_INBOX_ERR="permission denied",
    )

    assert result.returncode == 0
    assert "[GAR] workspace_global unavailable" in result.stdout
    assert "recent failed (exit 1): database locked" in result.stdout
    assert "direct inbox failed (exit 2): permission denied" in result.stdout


def test_session_start_caps_and_deduplicates_injected_room_context(tmp_path: Path) -> None:
    huge = "x" * 5000
    result = _run(
        START_HOOK,
        {"session_id": "sess-budget", "hook_event_name": "SessionStart"},
        tmp_path,
        KITTY_STUB_RECENT_TEXT=f"message_same: jacob: {huge}",
        KITTY_STUB_INBOX_TEXT=f"message_same: jacob: {huge}\nmessage_direct: jacob: {huge}",
    )

    assert result.returncode == 0
    assert result.stdout.count("message_same:") == 1
    assert "message_direct:" in result.stdout
    assert len(result.stdout) < 14000


def test_command_stop_hook_never_forces_session_end_on_an_ordinary_turn(tmp_path: Path) -> None:
    result = _run(
        STOP_HOOK,
        {
            "session_id": "sess-ordinary",
            "hook_event_name": "Stop",
            "stop_hook_active": False,
            "last_assistant_message": "Here is the answer you asked for.",
            "background_tasks": [],
            "session_crons": [],
        },
        tmp_path,
    )

    assert result.returncode == 0
    assert '"decision":"block"' not in result.stdout.replace(" ", "")
    assert "/session-end" not in result.stdout
