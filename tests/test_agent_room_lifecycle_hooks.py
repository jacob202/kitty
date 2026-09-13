from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
START_HOOK = ROOT / ".claude/hooks/session-start.sh"
STOP_HOOK = ROOT / ".claude/hooks/session-stop.sh"

BRIEFING_JSON = json.dumps(
    {
        "schema_version": 1,
        "kind": "room_briefing",
        "identity": "claude",
        "session_id": "sess-start",
        "generated_at": "2026-09-13T00:00:00+00:00",
        "degraded": True,
        "assignment": {
            "state": "unresolved",
            "scope": None,
            "authority_source": None,
            "reason": "participant-wide directs are attention only",
        },
        "sources": {"gar": {"state": "current"}, "github": {"state": "unknown"}},
        "attention": [
            {
                "kind": "broadcast_context",
                "message_id": "message_briefing_1",
                "sender_id": "chatgpt",
                "trust": "untrusted",
                "reason": "participant-wide broadcast is shared context only, never an assignment",
            }
        ],
        "next_continuation": None,
    }
)


def _stub_cli(tmp_path: Path) -> tuple[Path, Path]:
    log = tmp_path / "room.log"
    script = tmp_path / "kitty-room-stub"
    script.write_text(
        """#!/usr/bin/env bash
set -u
printf '%s\\n' "$*" >> "$KITTY_STUB_LOG"
if [[ "$1 $2" == "room briefing" ]]; then
  printf '%s\\n' "${KITTY_STUB_BRIEFING_TEXT:-}"
  printf '%s' "${KITTY_STUB_BRIEFING_ERR:-}" >&2
  exit "${KITTY_STUB_BRIEFING_RC:-0}"
fi
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


def _log(tmp_path: Path) -> str:
    return (tmp_path / "room.log").read_text(encoding="utf-8")


def test_session_start_consumes_shared_briefing_instead_of_rebuilding_room_state(
    tmp_path: Path,
) -> None:
    """Assignment truth comes from Room Briefing, not from room recent or directs."""
    result = _run(
        START_HOOK,
        {"session_id": "sess-start", "hook_event_name": "SessionStart"},
        tmp_path,
        KITTY_STUB_BRIEFING_TEXT=BRIEFING_JSON,
        KITTY_STUB_RECENT_TEXT="message_1: codex: exact-head review ready",
        KITTY_STUB_INBOX_TEXT="message_2: jacob: please verify PR #999",
    )

    assert result.returncode == 0
    assert "[GAR] shared briefing" in result.stdout
    # The briefing's own truthful position is injected.
    assert "assignment.state: unresolved" in result.stdout
    assert "assignment.authority: none" in result.stdout
    # Unavailable sources stay explicit instead of reading as a healthy empty room.
    assert "source github: unknown" in result.stdout
    assert "degraded: true" in result.stdout
    # The client must not rebuild world state from the participant-wide window.
    log = _log(tmp_path)
    assert "room briefing --as claude --session-id sess-start --json" in log
    assert "room recent" not in log


def test_session_start_labels_directs_as_attention_not_assignment(tmp_path: Path) -> None:
    result = _run(
        START_HOOK,
        {"session_id": "sess-start", "hook_event_name": "SessionStart"},
        tmp_path,
        KITTY_STUB_BRIEFING_TEXT=BRIEFING_JSON,
        KITTY_STUB_INBOX_TEXT="message_2: jacob: please verify PR #999",
    )

    assert result.returncode == 0
    assert "attention/receipt only" in result.stdout
    assert "please verify PR #999" in result.stdout
    assert "gar-session:sess-start" in result.stdout
    assert "reply in-thread" in result.stdout
    assert "room ack --as claude <message_id>" in result.stdout
    assert "Do not ACK unread work you did not consume" in result.stdout
    assert "room ack --as claude" not in _log(tmp_path)


def test_session_start_reports_briefing_unavailable_with_bounded_diagnostics(
    tmp_path: Path,
) -> None:
    result = _run(
        START_HOOK,
        {"session_id": "sess-down", "hook_event_name": "SessionStart"},
        tmp_path,
        KITTY_STUB_BRIEFING_RC="3",
        KITTY_STUB_BRIEFING_ERR="gateway refused: database locked",
    )

    assert result.returncode == 0
    assert "[GAR] shared briefing unavailable" in result.stdout
    assert "briefing failed (exit 3): gateway refused: database locked" in result.stdout
    # Fail closed: no invented assignment and no healthy-looking empty room.
    assert "assignment.state:" not in result.stdout
    assert "do not treat this as an empty room" in result.stdout
    assert len(result.stdout) < 4000


def test_session_start_does_not_invent_a_degraded_state_when_sources_are_healthy(
    tmp_path: Path,
) -> None:
    """`degraded` is a list of degraded sources; an empty list is healthy."""
    briefing = json.loads(BRIEFING_JSON)
    briefing["degraded"] = []
    result = _run(
        START_HOOK,
        {"session_id": "sess-healthy", "hook_event_name": "SessionStart"},
        tmp_path,
        KITTY_STUB_BRIEFING_TEXT=json.dumps(briefing),
    )

    assert result.returncode == 0
    assert "[GAR] shared briefing" in result.stdout
    assert "degraded:" not in result.stdout


def test_session_start_rejects_valid_json_that_is_not_a_briefing(tmp_path: Path) -> None:
    """Syntactically valid JSON with no briefing contract must not read as success."""
    for payload in (
        "{}",
        '"a string"',
        "[]",
        '{"schema_version":999,"kind":"not_a_briefing","assignment":{}}',
        '{"schema_version":1,"kind":"room_briefing"}',
    ):
        result = _run(
            START_HOOK,
            {"session_id": "sess-shape", "hook_event_name": "SessionStart"},
            tmp_path,
            KITTY_STUB_BRIEFING_TEXT=payload,
        )
        assert result.returncode == 0, payload
        assert "[GAR] shared briefing unavailable" in result.stdout, payload
        assert "assignment.state:" not in result.stdout, payload


def test_session_start_treats_unparseable_briefing_as_unavailable(tmp_path: Path) -> None:
    result = _run(
        START_HOOK,
        {"session_id": "sess-junk", "hook_event_name": "SessionStart"},
        tmp_path,
        KITTY_STUB_BRIEFING_TEXT="not json at all",
    )

    assert result.returncode == 0
    assert "[GAR] shared briefing unavailable" in result.stdout
    assert "assignment.state:" not in result.stdout


def test_session_start_caps_and_deduplicates_injected_room_context(tmp_path: Path) -> None:
    huge = "x" * 5000
    result = _run(
        START_HOOK,
        {"session_id": "sess-budget", "hook_event_name": "SessionStart"},
        tmp_path,
        KITTY_STUB_BRIEFING_TEXT=BRIEFING_JSON,
        KITTY_STUB_INBOX_TEXT=f"message_direct: jacob: {huge}",
    )

    assert result.returncode == 0
    assert "message_direct:" in result.stdout
    assert len(result.stdout) < 14000


def test_session_start_replays_session_end_outbox_before_briefing(tmp_path: Path) -> None:
    outbox = tmp_path / "outbox"
    outbox.mkdir()
    (outbox / "queued.json").write_text(
        json.dumps({"content": "durable handoff from a killed session"}),
        encoding="utf-8",
    )
    cli, _logpath = _stub_cli(tmp_path)

    result = _run(
        START_HOOK,
        {"session_id": "sess-outbox", "hook_event_name": "SessionStart"},
        tmp_path,
        KITTY_STUB_BRIEFING_TEXT=BRIEFING_JSON,
    )

    assert result.returncode == 0
    lines = _log(tmp_path).splitlines()
    post_calls = [line for line in lines if line.startswith("room post")]
    assert post_calls, "SessionEnd outbox must still be replayed"
    assert "durable handoff from a killed session" in post_calls[0]
    assert not (outbox / "queued.json").exists()


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
