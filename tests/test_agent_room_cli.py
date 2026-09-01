"""CLI tests for the global agent room."""

from __future__ import annotations

import importlib
import json

import pytest

from gateway import agent_workspace


@pytest.fixture
def room_db(monkeypatch: pytest.MonkeyPatch, tmp_path):
    db_file = tmp_path / "kitty" / "kitty.db"
    monkeypatch.setattr(agent_workspace, "WORKSPACE_DB_FILE", db_file)
    agent_workspace.init_db()
    return db_file


def _run(args: list[str], capsys):
    cli = importlib.import_module("gateway.agent_room_cli")
    code = cli.main(args)
    captured = capsys.readouterr()
    return code, captured


def _json_stdout(captured):
    return json.loads(captured.out)


def test_cli_round_trip_post_inbox_reply_ack_and_thread(room_db, capsys):
    code, captured = _run([
        "post", "--as", "chatgpt", "--to", "claude", "--kind", "handoff",
        "Review the global room protocol.", "--json",
    ], capsys)
    assert code == 0
    root = _json_stdout(captured)
    assert root["sender_id"] == "chatgpt"
    assert root["recipient_id"] == "claude"
    code, captured = _run(
        ["inbox", "--as", "claude", "--unread", "--json"], capsys
    )
    assert code == 0
    assert [item["id"] for item in _json_stdout(captured)] == [root["id"]]

    code, captured = _run([
        "reply", "--as", "claude", "--to", "chatgpt", "--kind", "review",
        root["id"], "The protocol looks coherent.", "--json",
    ], capsys)
    assert code == 0
    reply = _json_stdout(captured)
    assert reply["parent_message_id"] == root["id"]

    code, captured = _run(
        ["ack", "--as", "claude", root["id"], "--json"], capsys
    )
    assert code == 0
    receipt = _json_stdout(captured)
    assert receipt["receipt_state"] == "acknowledged"

    code, captured = _run(
        ["inbox", "--as", "claude", "--unread", "--json"], capsys
    )
    assert code == 0
    assert _json_stdout(captured) == []

    code, captured = _run(["thread", reply["id"], "--json"], capsys)
    assert code == 0
    assert [item["id"] for item in _json_stdout(captured)] == [
        root["id"], reply["id"]
    ]

def test_cli_json_ensure_status_recent_and_invalid_participant(room_db, capsys):
    code, captured = _run(["ensure", "--json"], capsys)
    assert code == 0
    assert _json_stdout(captured)["id"] == "workspace_global"

    code, captured = _run(["status", "--json"], capsys)
    assert code == 0
    status = _json_stdout(captured)
    assert status["id"] == "workspace_global"
    assert status["participants"] == ["chatgpt", "claude", "codex", "kitty"]

    code, captured = _run(["recent", "--json"], capsys)
    assert code == 0
    assert _json_stdout(captured) == []

    code, captured = _run([
        "post", "--as", "imaginary", "No impersonation", "--json"
    ], capsys)
    assert code == 2
    assert captured.out == ""
    assert "unknown global participant" in captured.err
