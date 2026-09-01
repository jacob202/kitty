from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from gateway import agent_room_cli, agent_workspace

ROOT = Path(__file__).resolve().parents[1]
START_HOOK = ROOT / ".claude/hooks/session-start.sh"
END_HOOK = ROOT / ".claude/hooks/session-end.sh"
SETTINGS = ROOT / ".claude/settings.json"


@pytest.fixture
def room_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    db_file = tmp_path / "kitty" / "kitty.db"
    monkeypatch.setattr(agent_workspace, "WORKSPACE_DB_FILE", db_file)
    agent_workspace.init_db()
    return db_file


def test_direct_only_cli_inbox_cannot_be_starved_by_broadcasts(room_db) -> None:
    agent_workspace.ensure_global_workspace()
    direct = agent_workspace.post_global_message(
        sender_id="chatgpt",
        recipient_id="claude",
        content="old direct",
        message_kind="handoff",
    )
    for index in range(20):
        agent_workspace.post_global_message(
            sender_id="chatgpt",
            content=f"broadcast {index}",
            message_kind="status",
        )

    inbox = agent_room_cli._direct_inbox("claude", unread_only=True, limit=1)

    assert [item["id"] for item in inbox] == [direct["id"]]


def _stub_cli(tmp_path: Path) -> tuple[Path, Path]:
    log = tmp_path / "room.log"
    script = tmp_path / "kitty-room-stub"
    script.write_text(
        """#!/usr/bin/env bash
set -u
printf '%s\\n' "$*" >> "$KITTY_STUB_LOG"
if [[ "$1 $2" == "room recent" ]]; then
  printf '%s\\n' "${KITTY_STUB_RECENT_JSON:-[]}"
  exit "${KITTY_STUB_RECENT_RC:-0}"
fi
if [[ "$1 $2" == "room inbox" ]]; then
  printf '%s\\n' "${KITTY_STUB_INBOX_TEXT:-}"
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


def _env(tmp_path: Path, **overrides: str) -> dict[str, str]:
    cli, log = _stub_cli(tmp_path)
    env = os.environ.copy()
    env.update(
        {
            "KITTY_ROOM_CLI": str(cli),
            "KITTY_STUB_LOG": str(log),
            "KITTY_GAR_STATE_DIR": str(tmp_path / "state"),
        }
    )
    env.update(overrides)
    return env


def _run(hook: Path, payload: dict[str, object], tmp_path: Path, **overrides: str):
    return subprocess.run(
        ["bash", str(hook)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=ROOT,
        env=_env(tmp_path, **overrides),
    )


def _transcript(tmp_path: Path, text: str) -> Path:
    transcript = tmp_path / "session.jsonl"
    transcript.write_text(
        json.dumps(
            {
                "type": "assistant",
                "message": {"content": [{"type": "text", "text": text}]},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return transcript


def test_settings_uses_session_end_not_stop_for_gar_finalization() -> None:
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
    end_commands = [
        hook["command"]
        for group in settings["hooks"]["SessionEnd"]
        for hook in group["hooks"]
    ]
    stop_commands = [
        hook["command"]
        for group in settings["hooks"]["Stop"]
        for hook in group["hooks"]
    ]

    assert "bash .claude/hooks/session-end.sh" in end_commands
    assert not any("session-end.sh" in command for command in stop_commands)


def test_session_start_fetches_direct_unread_separately(tmp_path: Path) -> None:
    result = _run(
        START_HOOK,
        {"session_id": "sess-start", "hook_event_name": "SessionStart"},
        tmp_path,
        KITTY_STUB_INBOX_TEXT="message_direct: jacob: please review",
    )

    assert result.returncode == 0
    log = (tmp_path / "room.log").read_text(encoding="utf-8")
    assert "room inbox --as claude --unread --direct --limit 12" in log
    assert "please review" in result.stdout
    assert "gar-session:sess-start" in result.stdout
    assert "Do not wait for Jacob to say session end" in result.stdout


def test_session_start_reports_room_unavailable_without_erasing_pending(tmp_path: Path) -> None:
    pending = tmp_path / "state/pending"
    pending.mkdir(parents=True)
    queued = pending / "old-session.txt"
    queued.write_text("durable pending handoff", encoding="utf-8")

    result = _run(
        START_HOOK,
        {"session_id": "sess-down", "hook_event_name": "SessionStart"},
        tmp_path,
        KITTY_STUB_RECENT_RC="1",
        KITTY_STUB_INBOX_RC="1",
        KITTY_STUB_POST_RC="1",
    )

    assert result.returncode == 0
    assert queued.exists()
    assert "workspace_global unavailable" in result.stdout


def test_session_end_posts_fallback_only_at_real_session_end(tmp_path: Path) -> None:
    transcript = _transcript(tmp_path, "Tests pass and the PR is ready.")
    result = _run(
        END_HOOK,
        {
            "session_id": "sess-end",
            "hook_event_name": "SessionEnd",
            "reason": "prompt_input_exit",
            "transcript_path": str(transcript),
        },
        tmp_path,
    )

    assert result.returncode == 0
    log = (tmp_path / "room.log").read_text(encoding="utf-8")
    assert "room post --as claude --kind handoff" in log
    assert "gar-session:sess-end" in log
    assert "Tests pass and the PR is ready." in log


def test_session_end_queues_fallback_when_room_post_fails(tmp_path: Path) -> None:
    transcript = _transcript(tmp_path, "Durable work exists on the branch.")
    result = _run(
        END_HOOK,
        {
            "session_id": "sess-down",
            "hook_event_name": "SessionEnd",
            "reason": "other",
            "transcript_path": str(transcript),
        },
        tmp_path,
        KITTY_STUB_POST_RC="1",
    )

    assert result.returncode == 0
    pending = tmp_path / "state/pending/sess-down.txt"
    assert pending.exists()
    assert "gar-session:sess-down" in pending.read_text(encoding="utf-8")


def test_next_session_start_flushes_pending_handoff(tmp_path: Path) -> None:
    pending = tmp_path / "state/pending"
    pending.mkdir(parents=True)
    (pending / "old-session.txt").write_text(
        "[gar-session:old-session] recovered handoff", encoding="utf-8"
    )

    result = _run(
        START_HOOK,
        {"session_id": "new-session", "hook_event_name": "SessionStart"},
        tmp_path,
    )

    assert result.returncode == 0
    assert not (pending / "old-session.txt").exists()
    log = (tmp_path / "room.log").read_text(encoding="utf-8")
    assert "room post --as claude --kind handoff" in log
    assert "recovered handoff" in log


def test_session_end_does_not_duplicate_matching_receipt(tmp_path: Path) -> None:
    transcript = _transcript(tmp_path, "Already handed off.")
    recent = json.dumps(
        [
            {
                "sender_id": "claude",
                "message_kind": "handoff",
                "content": "[gar-session:sess-receipt] verified handoff",
            }
        ]
    )
    result = _run(
        END_HOOK,
        {
            "session_id": "sess-receipt",
            "hook_event_name": "SessionEnd",
            "reason": "other",
            "transcript_path": str(transcript),
        },
        tmp_path,
        KITTY_STUB_RECENT_JSON=recent,
    )

    assert result.returncode == 0
    log = (tmp_path / "room.log").read_text(encoding="utf-8")
    assert "room post" not in log
