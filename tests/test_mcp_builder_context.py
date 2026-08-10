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


def test_status_snapshot_uses_genuinely_read_only_builder_projection(
    monkeypatch: pytest.MonkeyPatch,
    snapshot: dict,
) -> None:
    seen: dict[str, Path] = {}
    monkeypatch.setattr(context, "repo_root", lambda: Path("/tmp/kitty"))

    def fake_readonly(*, db_path: Path) -> dict:
        seen["db_path"] = db_path
        return snapshot

    monkeypatch.setattr(context, "build_status_snapshot_readonly", fake_readonly)

    result = context._status_snapshot()

    assert result is snapshot
    assert seen["db_path"] == Path("/tmp/kitty/data/kittybuilder/builder_queue.db")


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
