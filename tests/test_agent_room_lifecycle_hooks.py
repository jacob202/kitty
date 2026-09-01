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
  if [[ " $* " == *" --json "* ]]; then
    printf '%s\\n' "${KITTY_STUB_RECENT_JSON:-[]}"
  else
    printf '%s\\n' "${KITTY_STUB_RECENT_TEXT:-}"
  fi
  exit "${KITTY_STUB_RECENT_RC:-0}"
fi
""",
        encoding="utf-8",
    )
    script.write_text(
        script.read_text(encoding="utf-8")
        + """if [[ \"$1 $2\" == \"room inbox\" ]]; then
  printf '%s\\n' "${KITTY_STUB_INBOX_TEXT:-}"
  exit "${KITTY_STUB_INBOX_RC:-0}"
fi
if [[ \"$1 $2\" == \"room post\" ]]; then
  exit "${KITTY_STUB_POST_RC:-0}"
fi
exit 1
""",
        encoding="utf-8",
    )
    script.chmod(0o755)
    return script, log


def _run(
    hook: Path,
    payload: dict[str, object],
    tmp_path: Path,
    **env_overrides: str,
) -> subprocess.CompletedProcess[str]:
    cli, log = _stub_cli(tmp_path)
    env = os.environ.copy()
    env.update(
        {
            "KITTY_ROOM_CLI": str(cli),
            "KITTY_STUB_LOG": str(log),
            "KITTY_GAR_STATE_DIR": str(tmp_path / "state"),
        }
    )
    env.update(env_overrides)
    return subprocess.run(
        ["bash", str(hook)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=ROOT,
        env=env,
    )


def test_session_start_injects_recent_and_unread_room_context(tmp_path: Path) -> None:
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
    assert "[GAR] unread for claude" in result.stdout
    assert "please verify PR #999" in result.stdout
    log = (tmp_path / "room.log").read_text(encoding="utf-8")
    assert "room recent --limit 12" in log
    assert "room inbox --as claude --unread --limit 12" in log
    assert (tmp_path / "state/sess-start.start").exists()


def test_session_start_reports_room_unavailable_without_failing(tmp_path: Path) -> None:
    result = _run(
        START_HOOK,
        {"session_id": "sess-down", "hook_event_name": "SessionStart"},
        tmp_path,
        KITTY_STUB_RECENT_RC="1",
        KITTY_STUB_INBOX_RC="1",
    )

    assert result.returncode == 0
    assert "[GAR] workspace_global unavailable" in result.stdout


def _mark_started(tmp_path: Path, session_id: str, started_at: int = 100) -> None:
    state = tmp_path / "state"
    state.mkdir(parents=True, exist_ok=True)
    (state / f"{session_id}.start").write_text(f"{started_at}\n", encoding="utf-8")


def test_stop_blocks_first_completion_without_session_end_handoff(tmp_path: Path) -> None:
    _mark_started(tmp_path, "sess-stop")
    result = _run(
        STOP_HOOK,
        {
            "session_id": "sess-stop",
            "hook_event_name": "Stop",
            "stop_hook_active": False,
            "last_assistant_message": "Implementation complete.",
            "background_tasks": [],
            "session_crons": [],
        },
        tmp_path,
        KITTY_STUB_RECENT_JSON="[]",
    )

    decision = json.loads(result.stdout)
    assert decision["decision"] == "block"
    assert "/session-end" in decision["reason"]
    assert "workspace_global" in decision["reason"]

def test_stop_accepts_a_same_session_gar_handoff(tmp_path: Path) -> None:
    _mark_started(tmp_path, "sess-receipt")
    recent = json.dumps(
        [
            {
                "sender_id": "claude",
                "message_kind": "handoff",
                "created_at": 101,
                "content": "[gar-session:sess-receipt] verified result",
            }
        ]
    )
    result = _run(
        STOP_HOOK,
        {
            "session_id": "sess-receipt",
            "hook_event_name": "Stop",
            "stop_hook_active": False,
            "last_assistant_message": "Done.",
            "background_tasks": [],
            "session_crons": [],
        },
        tmp_path,
        KITTY_STUB_RECENT_JSON=recent,
    )

    assert result.returncode == 0
    assert '"decision":"block"' not in result.stdout.replace(" ", "")
    log = (tmp_path / "room.log").read_text(encoding="utf-8")
    assert "room recent --limit 100 --json" in log
    assert "room post" not in log


def test_stop_second_pass_posts_last_message_as_fallback_handoff(tmp_path: Path) -> None:
    _mark_started(tmp_path, "sess-fallback")
    result = _run(
        STOP_HOOK,
        {
            "session_id": "sess-fallback",
            "hook_event_name": "Stop",
            "stop_hook_active": True,
            "last_assistant_message": "Tests passed; PR is ready for review.",
            "background_tasks": [],
            "session_crons": [],
        },
        tmp_path,
        KITTY_STUB_RECENT_JSON="[]",
    )

    assert result.returncode == 0
    log = (tmp_path / "room.log").read_text(encoding="utf-8")
    assert "room post --as claude --kind handoff" in log
    assert "Tests passed; PR is ready for review." in log


def test_stop_does_not_finalize_while_background_work_is_active(tmp_path: Path) -> None:
    _mark_started(tmp_path, "sess-background")
    result = _run(
        STOP_HOOK,
        {
            "session_id": "sess-background",
            "hook_event_name": "Stop",
            "stop_hook_active": False,
            "last_assistant_message": "Waiting on reviewer.",
            "background_tasks": [{"id": "task-1", "status": "running"}],
            "session_crons": [],
        },
        tmp_path,
        KITTY_STUB_RECENT_JSON="[]",
    )

    assert result.returncode == 0
    assert "decision" not in result.stdout
    log = (tmp_path / "room.log").read_text(encoding="utf-8") if (tmp_path / "room.log").exists() else ""
    assert "room post" not in log


def test_stop_does_not_accept_another_claude_sessions_handoff(tmp_path: Path) -> None:
    _mark_started(tmp_path, "sess-own")
    recent = json.dumps(
        [
            {
                "sender_id": "claude",
                "message_kind": "handoff",
                "created_at": 101,
                "content": "handoff from a different concurrent Claude session",
            }
        ]
    )
    result = _run(
        STOP_HOOK,
        {
            "session_id": "sess-own",
            "hook_event_name": "Stop",
            "stop_hook_active": False,
            "last_assistant_message": "My own work is done.",
            "background_tasks": [],
            "session_crons": [],
        },
        tmp_path,
        KITTY_STUB_RECENT_JSON=recent,
    )

    decision = json.loads(result.stdout)
    assert decision["decision"] == "block"
    assert "gar-session:sess-own" in decision["reason"]


def test_stop_fails_open_if_hook_json_cannot_be_parsed(tmp_path: Path) -> None:
    _mark_started(tmp_path, "sess-no-jq")
    cli, log = _stub_cli(tmp_path)
    env = os.environ.copy()
    env.update(
        {
            "KITTY_ROOM_CLI": str(cli),
            "KITTY_STUB_LOG": str(log),
            "KITTY_GAR_STATE_DIR": str(tmp_path / "state"),
        }
    )
    result = subprocess.run(
        ["bash", str(STOP_HOOK)],
        input="{malformed-hook-json",
        capture_output=True,
        text=True,
        cwd=ROOT,
        env=env,
    )

    assert result.returncode == 0
    assert '"decision":"block"' not in result.stdout.replace(" ", "")
