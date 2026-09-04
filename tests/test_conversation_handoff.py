"""Tests for gateway/conversation_handoff.py — conversation -> approved Builder job.

This module adds no queue, approval state machine, or execution engine of its
own. It compiles a conversation-derived task into the existing Builder
Mission/packet manifest shape and delegates to the same
``mcp.builder.commands``/``mcp.builder.context`` functions an external MCP
client already uses. These tests prove that delegation actually happens and
that the safety boundaries (no mutation before explicit approval, idempotent
re-approval, Builder-owned execution truth, unchanged paid-execution gate)
hold through the new surface.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from gateway import builder_attempt as ba
from gateway import builder_initiative as bi
from gateway import builder_queue as bq
from gateway import conversation_handoff
from mcp.builder import commands as mcp_commands
from mcp.builder import context as mcp_context


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


@pytest.fixture()
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A minimal real Git checkout, wired so Builder reads/writes land in it."""
    _git(tmp_path, "init", "-b", "main")
    _git(tmp_path, "config", "user.name", "Kitty Test")
    _git(tmp_path, "config", "user.email", "kitty-test@example.invalid")
    (tmp_path / "gateway").mkdir()
    (tmp_path / "gateway" / "app.py").write_text("pass\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# fixture\n", encoding="utf-8")
    _git(tmp_path, "add", "README.md", "gateway/app.py")
    _git(tmp_path, "commit", "-m", "fixture")

    monkeypatch.setenv("KITTY_REPO_ROOT", str(tmp_path))
    monkeypatch.delenv("KITTY_BUILDER_DATA_DIR", raising=False)
    # mission_approve() -> bi.apply_manifest() resolves the default DB path
    # through gateway.builder_queue.BUILDER_QUEUE_DB at call time; context.py's
    # resume/work_status read through repo_root()/data/kittybuilder — pointing
    # both at the same file keeps writer and reader on one durable store.
    db_path = tmp_path / "data" / "kittybuilder" / "builder_queue.db"
    monkeypatch.setattr(bq, "BUILDER_QUEUE_DB", db_path)
    # packet_attempts is owned by builder_attempt.py's own schema, not
    # bi.init_db()'s; a fresh test DB needs it explicitly before any
    # read-only projection (resume_context/work_status) touches attempts.
    ba.init_db(db_path)
    return tmp_path


def _task(**overrides) -> dict:
    base = {
        "objective": "Fix the flaky retry loop in the worker adapter",
        "instructions": "The retry loop double-counts attempts; cap it at max_attempts.",
        "allowed_paths": ["gateway/"],
        "acceptance_criteria": ["Retry loop stops at max_attempts."],
        "validation_commands": ["python3.12 -m pytest tests/test_conversation_handoff.py -q"],
    }
    base.update(overrides)
    return base


def _initiative_rows(db_path: Path) -> list[dict]:
    return bi.list_initiatives(db_path=db_path)


def test_propose_without_approval_does_not_create_builder_job(repo: Path) -> None:
    result = conversation_handoff.propose(**_task())

    assert result["ok"] is True
    assert result["state"] == "prepared"
    assert result["approval_nonce"]
    assert result["prepared_manifest"]["packets"][0]["objective"] == _task()["objective"]

    db_path = repo / "data" / "kittybuilder" / "builder_queue.db"
    assert _initiative_rows(db_path) == []


def test_propose_binds_to_current_checkout_head_when_local_main_is_stale(repo: Path) -> None:
    _git(repo, "switch", "-c", "feature/live-cockpit")
    (repo / "README.md").write_text("# fixture\n\nfeature work\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "feature work")
    current_head = _git(repo, "rev-parse", "HEAD")
    assert _git(repo, "rev-parse", "main") != current_head

    result = conversation_handoff.propose(**_task())
    assert result["ok"] is True, result
    assert result["state"] == "prepared"
    assert result["expected_base_sha"] == current_head


def test_approved_conversation_job_keeps_current_checkout_base_when_main_is_stale(repo: Path) -> None:
    _git(repo, "switch", "-c", "feature/live-approval")
    (repo / "README.md").write_text("# fixture\n\napproval work\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "approval work")
    current_head = _git(repo, "rev-parse", "HEAD")
    assert _git(repo, "rev-parse", "main") != current_head

    proposal = conversation_handoff.propose(**_task())
    assert proposal["ok"] is True, proposal
    approved = conversation_handoff.approve(
        prepared_manifest=proposal["prepared_manifest"],
        expected_manifest_sha=proposal["manifest_sha256"],
        expected_base_sha=proposal["expected_base_sha"],
        approval_nonce=proposal["approval_nonce"],
        confirmed=True,
    )

    assert approved["ok"] is True, approved
    db_path = repo / "data" / "kittybuilder" / "builder_queue.db"
    conn = bq.connect(db_path)
    try:
        row = conn.execute(
            "SELECT base_sha FROM initiative_packets WHERE initiative_id = ? AND packet_id = ?",
            (approved["mission_id"], "packet-1"),
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
    assert row["base_sha"] == current_head


def test_explicit_approval_creates_exactly_one_durable_job(repo: Path) -> None:
    proposal = conversation_handoff.propose(**_task())

    approved = conversation_handoff.approve(
        prepared_manifest=proposal["prepared_manifest"],
        expected_manifest_sha=proposal["manifest_sha256"],
        expected_base_sha=proposal["expected_base_sha"],
        approval_nonce=proposal["approval_nonce"],
        confirmed=True,
    )

    assert approved["ok"] is True
    assert approved["state"] == "accepted"
    mission_id = approved["mission_id"]
    assert mission_id

    db_path = repo / "data" / "kittybuilder" / "builder_queue.db"
    rows = _initiative_rows(db_path)
    assert [row["id"] for row in rows] == [mission_id]
    assert len(approved["tasks"]) == 1


def test_proposal_without_confirmed_flag_refuses_even_with_full_payload(repo: Path) -> None:
    """A model narrating "approved" in prose must not create a job."""
    proposal = conversation_handoff.propose(**_task())

    result = conversation_handoff.approve(
        prepared_manifest=proposal["prepared_manifest"],
        expected_manifest_sha=proposal["manifest_sha256"],
        expected_base_sha=proposal["expected_base_sha"],
        approval_nonce=proposal["approval_nonce"],
        confirmed=False,
    )

    assert result["ok"] is False
    assert result["error_code"] == "approval_required"
    db_path = repo / "data" / "kittybuilder" / "builder_queue.db"
    assert _initiative_rows(db_path) == []


def test_duplicate_approval_is_idempotent(repo: Path) -> None:
    proposal = conversation_handoff.propose(**_task())
    kwargs = dict(
        prepared_manifest=proposal["prepared_manifest"],
        expected_manifest_sha=proposal["manifest_sha256"],
        expected_base_sha=proposal["expected_base_sha"],
        approval_nonce=proposal["approval_nonce"],
        confirmed=True,
    )

    first = conversation_handoff.approve(**kwargs)
    second = conversation_handoff.approve(**kwargs)

    assert first["ok"] is True and second["ok"] is True
    assert first["mission_id"] == second["mission_id"]
    assert second["apply_status"] == "unchanged"

    db_path = repo / "data" / "kittybuilder" / "builder_queue.db"
    rows = _initiative_rows(db_path)
    assert len(rows) == 1


def test_resume_context_recovers_job_without_original_transcript(repo: Path) -> None:
    proposal = conversation_handoff.propose(**_task())
    approved = conversation_handoff.approve(
        prepared_manifest=proposal["prepared_manifest"],
        expected_manifest_sha=proposal["manifest_sha256"],
        expected_base_sha=proposal["expected_base_sha"],
        approval_nonce=proposal["approval_nonce"],
        confirmed=True,
    )
    mission_id = approved["mission_id"]

    # A fresh call carrying only the durable identifier — no proposal object,
    # no chat history — must be enough to recover the job.
    resumed = conversation_handoff.resume(mission_id=mission_id)

    assert resumed["mission"]["id"] == mission_id
    assert resumed["objective"] == _task()["objective"]
    assert resumed["artifacts"]["design"]["path"].startswith("docs/superpowers/specs/")
    assert resumed["artifacts"]["plan"]["path"].startswith("docs/superpowers/plans/")


def test_builder_execution_failure_is_represented_as_builder_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed Builder run must surface as failure, never as chat success."""
    failed_snapshot = {
        "schema_version": 2,
        "integrity": {"state": "complete", "partial_packets": 0, "total_packets": 1},
        "queue": {"queued": 0, "running": 0},
        "initiatives": [
            {
                "initiative_id": "conv-fix-retry-loop",
                "title": "Fix the flaky retry loop",
                "state": "failed",
                "pause_reason": None,
                "next_packet": None,
                "manifest": {},
                "packets": [
                    {
                        "initiative_id": "conv-fix-retry-loop",
                        "packet_id": "packet-1",
                        "title": "Fix the flaky retry loop",
                        "objective": "Fix the flaky retry loop in the worker adapter",
                        "task_id": "kb_9999_dead",
                        "task_state": "failed",
                        "attempt_count": 3,
                        "blocked_reason": "validation command failed 3 times",
                        "last_error": "pytest exited 1",
                        "attempt_history": [],
                        "publication": None,
                        "projection": {"next_action": "Inspect the failed attempt."},
                    }
                ],
            }
        ],
    }
    monkeypatch.setattr(mcp_context, "_status_snapshot", lambda: failed_snapshot)
    monkeypatch.setattr(
        mcp_context,
        "kitty_context",
        lambda: {"ok": True, "context": {"git": {}, "unknowns": []}},
    )
    monkeypatch.setattr(
        mcp_context,
        "get_initiative",
        lambda mission_id, db_path=None: failed_snapshot["initiatives"][0],
    )

    resumed = conversation_handoff.resume(mission_id="conv-fix-retry-loop")

    assert resumed["state"] == "failed"
    assert resumed["blocker"] == "validation command failed 3 times"
    assert resumed["current_work"]["state"] == "failed"


def test_paid_execution_remains_behind_existing_authorization_boundary() -> None:
    """The conversation handoff must not add its own execution path or bypass spend gating."""
    assert not hasattr(conversation_handoff, "execution_start")

    result = mcp_commands.execution_start("conv-fix-retry-loop", free=False, spend_authorized=False)

    assert result["ok"] is False
    assert result["error_code"] == "spend_not_authorized"


def test_compile_request_uses_lightweight_builder_only_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    from gateway import llm_client

    seen = {}

    def fake_call(messages, **kwargs):
        seen["messages"] = messages
        seen["kwargs"] = kwargs
        return '{"objective":"Add the proof file","instructions":"Create rc0-builder-proof.txt with exactly rc0 builder proof.","allowed_paths":["rc0-builder-proof.txt"],"acceptance_criteria":["The file contains exactly rc0 builder proof."]}'

    monkeypatch.setattr(llm_client, "call_llm", fake_call)

    request = 'Add a text file named rc0-builder-proof.txt containing exactly "rc0 builder proof".'
    result = conversation_handoff.compile_request(request)

    assert result["ok"] is True
    assert result["task"]["objective"] == "Add the proof file"
    assert result["task"]["instructions"] == request
    assert result["task"]["allowed_paths"] == ["rc0-builder-proof.txt"]
    assert "route" not in result
    assert seen["kwargs"]["model"] == "kitty-small"
    assert seen["kwargs"]["temperature"] == 0
    combined = "\n".join(str(message.get("content", "")) for message in seen["messages"])
    from gateway.prompts import BUILDER_PROPOSAL_PROMPT
    assert BUILDER_PROPOSAL_PROMPT in combined
    assert len(combined) < 5000
    assert "personal memory" not in combined.lower()
    assert "morning brief" not in combined.lower()


def test_compile_request_rejects_unbounded_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    from gateway import llm_client

    monkeypatch.setattr(
        llm_client,
        "call_llm",
        lambda *args, **kwargs: '{"objective":"Change everything","instructions":"Edit the repository.","allowed_paths":["."]}',
    )
    result = conversation_handoff.compile_request("Fix everything in the repository")

    assert result["ok"] is False
    assert result["error_code"] == "proposal_scope_invalid"
    assert "repository" not in result["error"].lower()
    assert "narrow" in result["error"].lower()


def test_compile_request_translates_provider_failure_without_internal_details(monkeypatch: pytest.MonkeyPatch) -> None:
    from gateway import llm_client

    def fail(*args, **kwargs):
        raise llm_client.ProviderChainExhausted(["openrouter: 401 sk-secret-token", "local: connection refused 127.0.0.1:8010"])

    monkeypatch.setattr(llm_client, "call_llm", fail)

    result = conversation_handoff.compile_request("Change gateway/example.py so the example returns true.")

    assert result["ok"] is False
    assert result["error_code"] == "proposal_compile_failed"
    assert "openrouter" not in result["error"].lower()
    assert "127.0.0.1" not in result["error"]
    assert "sk-secret-token" not in result["error"]
    assert "no model provider" in result["error"].lower() or "try again" in result["error"].lower()
