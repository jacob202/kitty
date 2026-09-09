from __future__ import annotations

from pathlib import Path

import pytest

from mcp.builder import context


@pytest.fixture()
def snapshot() -> dict:
    return {
        "schema_version": 2,
        "integrity": {"state": "complete", "partial_packets": 0, "total_packets": 1},
        "queue": {"queued": 0, "running": 1},
        "initiatives": [
            {
                "initiative_id": "mission-1",
                "title": "MCP proof",
                "state": "active",
                "pause_reason": None,
                "next_packet": "packet-1",
                "counts": {"running": 1},
                "data_quality": {"state": "complete", "partial_packets": 0},
                "packets": [
                    {
                        "initiative_id": "mission-1",
                        "packet_id": "packet-1",
                        "title": "Implement seam",
                        "objective": "Make the seam work",
                        "task_id": "kb_1234_abcd",
                        "task_state": "running",
                        "attempt_count": 1,
                        "attempt_history": [
                            {
                                "id": 7,
                                "number": 1,
                                "outcome": None,
                                "implementation": {
                                    "status": "implemented",
                                    "summary": "Changed the adapter",
                                    "diff_summary": "2 files",
                                },
                                "validation": {
                                    "status": "passed",
                                    "command_count": 3,
                                    "failed_command_count": 0,
                                    "summary": "3 validation commands passed.",
                                },
                                "review": {
                                    "verdict": "approved",
                                    "summary": "Looks good",
                                    "findings": [],
                                    "findings_truncated": False,
                                },
                            }
                        ],
                        "publication": {
                            "pr_number": 451,
                            "pr_url": "https://github.com/jacob202/kitty/pull/451",
                            "checks_state": "success",
                            "review_state": "approved",
                            "head_sha": "a" * 40,
                            "merged": False,
                        },
                        "blocked_reason": None,
                        "last_error": None,
                        "base_sha": "b" * 40,
                        "updated_at": "2026-08-09T22:00:00-06:00",
                        "projection": {
                            "initiative_id": "mission-1",
                            "packet_id": "packet-1",
                            "task_id": "kb_1234_abcd",
                            "task_state": "running",
                            "attempt_count": 1,
                            "next_action": "wait",
                        },
                    }
                ],
            }
        ],
    }


def test_kitty_context_delegates_to_authoritative_context_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = {
        "schema_version": 2,
        "ok": False,
        "git": {"head": "c" * 40},
        "unknowns": [{"field": "builder", "reason": "unavailable"}],
    }
    seen: dict[str, Path] = {}

    def fake_receipt(root: Path) -> dict:
        seen["root"] = root
        return expected

    monkeypatch.setattr(context, "build_context_receipt", fake_receipt)
    monkeypatch.setattr(context, "repo_root", lambda: Path("/tmp/kitty"))

    result = context.kitty_context()

    assert seen["root"] == Path("/tmp/kitty")
    assert result["ok"] is False
    assert result["context"] is expected
    assert result["context"]["unknowns"][0]["field"] == "builder"


def test_status_snapshot_reads_through_the_one_builder_queue_db_symbol(
    monkeypatch: pytest.MonkeyPatch,
    snapshot: dict,
) -> None:
    """mission_approve() -> bi.apply_manifest() writes through
    gateway.builder_queue.BUILDER_QUEUE_DB (see that module and
    tests/test_conversation_handoff.py's `repo` fixture, which points both
    reader and writer at one file via this exact symbol). Reading anything
    else here -- a hand-rolled KITTY_DATA_ROOT/repo_root() reimplementation,
    for instance -- can silently diverge from where mission_approve() actually
    wrote, so a freshly approved job's resume()/status reads come back
    "unavailable" even though it exists."""
    import gateway.builder_queue as bq

    monkeypatch.delenv("KITTY_BUILDER_DATA_DIR", raising=False)
    monkeypatch.setattr(bq, "BUILDER_QUEUE_DB", Path("/tmp/kitty-isolated/kittybuilder/builder_queue.db"))
    seen: dict[str, Path] = {}

    def fake_readonly(*, db_path: Path) -> dict:
        seen["db_path"] = db_path
        return snapshot

    monkeypatch.setattr(context, "build_status_snapshot_readonly", fake_readonly)

    result = context._status_snapshot()

    assert result is snapshot
    assert seen["db_path"] == Path("/tmp/kitty-isolated/kittybuilder/builder_queue.db")


def test_work_status_filters_exact_mission(monkeypatch: pytest.MonkeyPatch, snapshot: dict) -> None:
    monkeypatch.setattr(context, "_status_snapshot", lambda: snapshot)

    result = context.work_status(mission_id="mission-1")

    assert result["ok"] is True
    assert result["state"] == "active"
    assert result["work"]["initiative_id"] == "mission-1"


def test_work_status_filters_exact_task(monkeypatch: pytest.MonkeyPatch, snapshot: dict) -> None:
    monkeypatch.setattr(context, "_status_snapshot", lambda: snapshot)

    result = context.work_status(task_id="kb_1234_abcd")

    assert result["ok"] is True
    assert result["state"] == "running"
    assert result["work"]["task_id"] == "kb_1234_abcd"
    assert result["work"]["packet_id"] == "packet-1"


def test_work_status_unknown_identifier_fails_loudly(
    monkeypatch: pytest.MonkeyPatch, snapshot: dict
) -> None:
    monkeypatch.setattr(context, "_status_snapshot", lambda: snapshot)

    result = context.work_status(task_id="missing")

    assert result["ok"] is False
    assert result["error_code"] == "work_not_found"
    assert "missing" in result["error"]


def test_work_result_uses_durable_attempt_validation_review_and_publication(
    monkeypatch: pytest.MonkeyPatch, snapshot: dict
) -> None:
    monkeypatch.setattr(context, "_status_snapshot", lambda: snapshot)

    result = context.work_result(task_id="kb_1234_abcd")

    assert result["ok"] is True
    assert result["result"]["task_state"] == "running"
    assert result["result"]["attempt"]["id"] == 7
    assert result["result"]["attempt"]["validation"]["status"] == "passed"
    assert result["result"]["attempt"]["review"]["verdict"] == "approved"
    assert result["result"]["publication"]["pr_number"] == 451
    assert result["result"]["complete"] is False


def test_work_result_never_calls_worker_narration_completion(
    monkeypatch: pytest.MonkeyPatch, snapshot: dict
) -> None:
    packet = snapshot["initiatives"][0]["packets"][0]
    packet["attempt_history"][0]["implementation"]["summary"] = "DONE EVERYTHING"
    packet["task_state"] = "running"
    monkeypatch.setattr(context, "_status_snapshot", lambda: snapshot)

    result = context.work_result(task_id="kb_1234_abcd")

    assert result["result"]["complete"] is False
    assert result["state"] == "running"


def test_status_snapshot_honors_builder_data_dir_override(
    monkeypatch: pytest.MonkeyPatch,
    snapshot: dict,
) -> None:
    override = Path("/tmp/kproof-canonical-builder")
    monkeypatch.setenv("KITTY_BUILDER_DATA_DIR", str(override))
    seen: dict[str, Path] = {}

    def fake_readonly(*, db_path: Path) -> dict:
        seen["db_path"] = db_path
        return snapshot

    monkeypatch.setattr(context, "build_status_snapshot_readonly", fake_readonly)

    result = context._status_snapshot()

    assert result is snapshot
    assert seen["db_path"] == override / "builder_queue.db"


def _mission(state: str, *, reviewer: str | None = "reviewer-1") -> dict:
    return {
        "mission_id": "mission_gw_1",
        "acceptance": {"state": state, "reviewer_id": reviewer, "evidence": None},
    }


def test_finished_builder_task_reports_that_acceptance_is_still_open(
    monkeypatch: pytest.MonkeyPatch, snapshot: dict
) -> None:
    """Builder finishing is implementation evidence, not user-outcome acceptance."""
    packet = snapshot["initiatives"][0]["packets"][0]
    packet["task_state"] = "done"
    monkeypatch.setattr(context, "_status_snapshot", lambda: snapshot)
    monkeypatch.setattr(
        context, "_mission_acceptance", lambda _id: _mission("unreviewed")["acceptance"]
    )

    result = context.work_result(task_id="kb_1234_abcd")["result"]

    assert result["builder_task_complete"] is True
    assert result["awaiting_acceptance"] is True
    assert "not accepted" in result["awaiting_acceptance_because"]


def test_accepted_outcome_stops_waiting_on_acceptance(
    monkeypatch: pytest.MonkeyPatch, snapshot: dict
) -> None:
    packet = snapshot["initiatives"][0]["packets"][0]
    packet["task_state"] = "done"
    monkeypatch.setattr(context, "_status_snapshot", lambda: snapshot)
    monkeypatch.setattr(
        context, "_mission_acceptance", lambda _id: _mission("accepted")["acceptance"]
    )

    result = context.work_result(task_id="kb_1234_abcd")["result"]

    assert result["awaiting_acceptance"] is False
    assert result["awaiting_acceptance_because"] is None


def test_work_with_no_bound_mission_reads_as_none_never_as_accepted(
    monkeypatch: pytest.MonkeyPatch, snapshot: dict
) -> None:
    """Absence of evidence must not be read as acceptance."""
    packet = snapshot["initiatives"][0]["packets"][0]
    packet["task_state"] = "done"
    monkeypatch.setattr(context, "_status_snapshot", lambda: snapshot)

    import gateway.memory_mission as mm

    monkeypatch.setattr(mm, "mission_for_initiative", lambda _id, **_kw: None)

    result = context.work_result(task_id="kb_1234_abcd")["result"]

    assert result["mission_acceptance"] == {
        "state": context.ACCEPTANCE_NONE,
        "reviewer_id": None,
        "mission_id": None,
        "error": None,
    }
    # No Mission is bound, so acceptance does not apply and nothing is waiting.
    assert result["builder_task_complete"] is True
    assert result["awaiting_acceptance"] is False


def test_acceptance_lookup_reports_the_bound_mission(monkeypatch: pytest.MonkeyPatch) -> None:
    import gateway.memory_mission as mm

    monkeypatch.setattr(
        mm,
        "mission_for_initiative",
        lambda _id, **_kw: {
            "mission_id": "mission_gw_1",
            "acceptance": {"state": "accepted", "reviewer_id": "reviewer-1"},
        },
    )

    assert context._mission_acceptance("mission-1") == {
        "state": "accepted",
        "reviewer_id": "reviewer-1",
        "mission_id": "mission_gw_1",
        "error": None,
    }
    assert context._mission_acceptance(None)["state"] == context.ACCEPTANCE_NONE


def test_initiative_level_result_applies_the_same_acceptance_gate(
    monkeypatch: pytest.MonkeyPatch, snapshot: dict
) -> None:
    snapshot["initiatives"][0]["state"] = "completed"
    monkeypatch.setattr(context, "_status_snapshot", lambda: snapshot)
    monkeypatch.setattr(
        context, "_mission_acceptance", lambda _id: _mission("unreviewed")["acceptance"]
    )

    result = context.work_result(mission_id="mission-1")["result"]

    assert result["builder_task_complete"] is True
    assert result["awaiting_acceptance"] is True


def test_unreadable_mission_store_is_reported_not_swallowed(
    monkeypatch: pytest.MonkeyPatch, snapshot: dict
) -> None:
    """A read-only projection must stay readable when the Mission store is not."""
    packet = snapshot["initiatives"][0]["packets"][0]
    packet["task_state"] = "done"
    monkeypatch.setattr(context, "_status_snapshot", lambda: snapshot)

    import gateway.memory_mission as mm

    def _boom(_initiative_id, **_kwargs):
        raise RuntimeError("mission store unavailable")

    monkeypatch.setattr(mm, "mission_for_initiative", _boom)

    result = context.work_result(task_id="kb_1234_abcd")

    # The projection stays readable, but an outage is reported as an outage
    # with its cause — never as "nothing is recorded".
    assert result["ok"] is True
    acceptance = result["result"]["mission_acceptance"]
    assert acceptance["state"] == context.ACCEPTANCE_UNAVAILABLE
    assert "mission store unavailable" in acceptance["error"]
    assert result["result"]["awaiting_acceptance"] is True


def test_acceptance_lookup_never_creates_schema_on_a_read(tmp_path: Path) -> None:
    """Polling a result must not mutate or lock the application database."""
    import gateway.memory_mission as mm

    empty_db = tmp_path / "kitty.db"
    with pytest.raises(mm.MissionError, match="Mission store is unavailable"):
        mm.mission_for_initiative("mission-1", db_path=empty_db)

    # Nothing was created just by asking.
    import sqlite3 as _sqlite3

    with _sqlite3.connect(empty_db) as conn:
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    assert "missions" not in tables


def test_resume_context_carries_acceptance_into_the_chat_projection(
    monkeypatch: pytest.MonkeyPatch, snapshot: dict
) -> None:
    """Chat reopens work through resume_context, so the fact has to reach here."""
    packet = snapshot["initiatives"][0]["packets"][0]
    packet["task_state"] = "done"
    monkeypatch.setattr(context, "_status_snapshot", lambda: snapshot)
    monkeypatch.setattr(context, "kitty_context", lambda: {"ok": True, "context": {}})
    monkeypatch.setattr(context, "get_initiative", lambda *a, **k: None)
    monkeypatch.setattr(
        context, "_mission_acceptance", lambda _id: _mission("unreviewed")["acceptance"]
    )

    result = context.resume_context(task_id="kb_1234_abcd")

    assert result["builder_task_complete"] is True
    assert result["awaiting_acceptance"] is True
    assert result["mission_acceptance"]["state"] == "unreviewed"
    assert any(u["field"] == "outcome_acceptance" for u in result["unknowns"])
