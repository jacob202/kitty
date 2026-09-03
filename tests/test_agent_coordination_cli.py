from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest

from gateway import agent_coordination, agent_workspace

BASE = "b" * 40


@pytest.fixture
def coordination_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    db_file = tmp_path / "kitty.db"
    monkeypatch.setattr(agent_coordination, "KITTY_DB_FILE", db_file)
    monkeypatch.setattr(agent_workspace, "WORKSPACE_DB_FILE", db_file)
    return db_file


def _run(args: list[str], capsys):
    cli = importlib.import_module("gateway.agent_coordination_cli")
    code = cli.main(args)
    captured = capsys.readouterr()
    return code, captured


def _claim_args(worktree: Path, *, session: str = "session-one") -> list[str]:
    return [
        "claim",
        "--as", "chatgpt",
        "--session-id", session,
        "--role", "OWN",
        "--lane", "coordination-mvp",
        "--base-sha", BASE,
        "--branch", f"feat/{session}",
        "--worktree", str(worktree),
        "--path", "gateway",
        "--resource", "coordination:claims",
        "--json",
    ]


def test_cli_claim_status_and_guard_round_trip(coordination_db: Path, tmp_path: Path, capsys) -> None:
    worktree = tmp_path / "worktree"
    code, captured = _run(_claim_args(worktree), capsys)
    assert code == 0
    claimed = json.loads(captured.out)
    assert claimed["claim"]["session_id"] == "session-one"
    assert claimed["gar_projection"]["ok"] is True

    code, captured = _run(["status", "--json"], capsys)
    assert code == 0
    status = json.loads(captured.out)
    assert [claim["session_id"] for claim in status["claims"]] == ["session-one"]

    code, captured = _run([
        "guard", "--worktree", str(worktree), "--path", "gateway/routes/chat.py", "--json"
    ], capsys)
    assert code == 0
    guarded = json.loads(captured.out)
    assert guarded["claim"]["session_id"] == "session-one"


def test_cli_conflict_is_nonzero_and_names_owner(coordination_db: Path, tmp_path: Path, capsys) -> None:
    code, _ = _run(_claim_args(tmp_path / "one", session="one"), capsys)
    assert code == 0
    code, captured = _run(_claim_args(tmp_path / "two", session="two"), capsys)
    assert code == 2
    assert "chatgpt/coordination-mvp" in captured.err
    assert captured.out == ""


def test_cli_release_posts_result_and_removes_active_claim(coordination_db: Path, tmp_path: Path, capsys) -> None:
    code, captured = _run(_claim_args(tmp_path / "one"), capsys)
    assert code == 0
    claim_id = json.loads(captured.out)["claim"]["claim_id"]

    code, captured = _run([
        "release", claim_id, "--session-id", "session-one", "--json"
    ], capsys)
    assert code == 0
    released = json.loads(captured.out)
    assert released["claim"]["released_at"] is not None
    assert released["gar_projection"]["ok"] is True

    code, captured = _run(["status", "--json"], capsys)
    assert code == 0
    assert json.loads(captured.out)["claims"] == []

    messages = agent_workspace.list_messages(agent_workspace.GLOBAL_WORKSPACE_ID, limit=20)
    assert any("COORDINATION CLAIM ACQUIRED" in message["content"] for message in messages)
    assert any("COORDINATION CLAIM RELEASED" in message["content"] for message in messages)
