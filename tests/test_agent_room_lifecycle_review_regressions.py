from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SETTINGS = ROOT / ".claude/settings.json"
START_HOOK = ROOT / ".claude/hooks/session-start.sh"
STOP_HOOK = ROOT / ".claude/hooks/session-stop.sh"
END_HOOK = ROOT / ".claude/hooks/session-end.sh"


def _hook_entries(event: str) -> list[dict[str, object]]:
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
    return [
        hook
        for group in settings["hooks"].get(event, [])
        for hook in group.get("hooks", [])
    ]


def _stub_cli(tmp_path: Path) -> tuple[Path, Path]:
    log = tmp_path / "room.log"
    script = tmp_path / "kitty-room-stub"
    script.write_text(
        """#!/usr/bin/env bash
set -u
printf '%s\\n' "$*" >> "$KITTY_STUB_LOG"
case "$1 $2" in
  "room recent") printf '%s\\n' "${KITTY_STUB_RECENT:-[]}"; printf '%s' "${KITTY_STUB_RECENT_ERR:-}" >&2; exit "${KITTY_STUB_RECENT_RC:-0}" ;;
  "room inbox") printf '%s\\n' "${KITTY_STUB_INBOX:-[]}"; printf '%s' "${KITTY_STUB_INBOX_ERR:-}" >&2; exit "${KITTY_STUB_INBOX_RC:-0}" ;;
  "room post") exit "${KITTY_STUB_POST_RC:-0}" ;;
esac
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
            "KITTY_GAR_OUTBOX_DIR": str(tmp_path / "outbox"),
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


def test_stop_uses_completion_prompt_instead_of_unconditional_session_end() -> None:
    prompts = [entry for entry in _hook_entries("Stop") if entry.get("type") == "prompt"]
    assert len(prompts) == 1
    prompt = str(prompts[0]["prompt"])
    assert "$ARGUMENTS" in prompt
    assert "ordinary turn" in prompt.lower()
    assert "/session-end" in prompt
    assert "gar-session:" in prompt
    assert "last_assistant_message" in prompt

    stop_text = STOP_HOOK.read_text(encoding="utf-8")
    assert '"decision":"block"' not in stop_text.replace(" ", "")
    assert "/session-end" not in stop_text


def test_real_session_end_has_durable_fallback_hook() -> None:
    entries = _hook_entries("SessionEnd")
    command = next(
        entry for entry in entries
        if entry.get("command") == "bash .claude/hooks/session-end.sh"
    )
    assert command.get("type") == "command"
    assert int(command.get("timeout", 0)) >= 5
    assert END_HOOK.exists()


def test_session_start_requests_direct_unread_separately() -> None:
    text = START_HOOK.read_text(encoding="utf-8")
    assert "room inbox --as claude --unread --direct-only" in text


def test_session_start_reports_command_failures(tmp_path: Path) -> None:
    result = _run(
        START_HOOK,
        {"session_id": "sess-errors", "hook_event_name": "SessionStart"},
        tmp_path,
        KITTY_STUB_RECENT_RC="1",
        KITTY_STUB_INBOX_RC="2",
        KITTY_STUB_RECENT_ERR="database locked",
        KITTY_STUB_INBOX_ERR="permission denied",
    )
    assert result.returncode == 0
    assert "recent failed (exit 1): database locked" in result.stdout
    assert "direct inbox failed (exit 2): permission denied" in result.stdout


def test_session_start_bounds_and_deduplicates_context(tmp_path: Path) -> None:
    huge = "x" * 5000
    result = _run(
        START_HOOK,
        {"session_id": "sess-budget", "hook_event_name": "SessionStart"},
        tmp_path,
        KITTY_STUB_RECENT=f"message_same: jacob: {huge}",
        KITTY_STUB_INBOX=f"message_same: jacob: {huge}\nmessage_direct: jacob: {huge}",
    )
    assert result.returncode == 0
    assert result.stdout.count("message_same:") == 1
    assert "message_direct:" in result.stdout
    assert len(result.stdout) < 14000


def test_session_end_queues_fallback_when_gar_post_fails(tmp_path: Path) -> None:
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text(
        json.dumps(
            {
                "type": "assistant",
                "message": {"content": [{"type": "text", "text": "Verified work is complete."}]},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    result = _run(
        END_HOOK,
        {
            "session_id": "sess-durable",
            "transcript_path": str(transcript),
            "hook_event_name": "SessionEnd",
            "reason": "other",
        },
        tmp_path,
        KITTY_STUB_RECENT_RC="1",
        KITTY_STUB_POST_RC="1",
    )
    assert result.returncode == 0
    queued = list((tmp_path / "outbox").glob("*.json"))
    assert len(queued) == 1
    payload = json.loads(queued[0].read_text(encoding="utf-8"))
    assert "gar-session:sess-durable" in payload["content"]
    assert "Verified work is complete." in payload["content"]


def test_session_start_flushes_durable_outbox_before_reading_room(tmp_path: Path) -> None:
    outbox = tmp_path / "outbox"
    outbox.mkdir()
    queued = outbox / "sess-pending.json"
    queued.write_text(
        json.dumps({"content": "[gar-session:sess-pending] recovered handoff"}),
        encoding="utf-8",
    )
    result = _run(
        START_HOOK,
        {"session_id": "sess-new", "hook_event_name": "SessionStart"},
        tmp_path,
    )
    assert result.returncode == 0
    log = (tmp_path / "room.log").read_text(encoding="utf-8")
    assert "room post --as claude --kind handoff" in log
    assert "recovered handoff" in log
    assert not queued.exists()
