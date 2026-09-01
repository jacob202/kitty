from __future__ import annotations

from pathlib import Path

import pytest

from gateway import builder_autonomy as aut
from gateway import builder_initiative as bi


def _status(
    *,
    eligible: list[str] | None = None,
    recovery: list[str] | None = None,
    blocked: list[str] | None = None,
    in_progress: list[str] | None = None,
    pending: list[str] | None = None,
    done: list[str] | None = None,
    failed: list[str] | None = None,
    exhausted: list[str] | None = None,
    evidence: dict | None = None,
) -> dict:
    return {
        "eligible": eligible or [],
        "recovery_needed": recovery or [],
        "blocked": blocked or [],
        "in_progress": in_progress or [],
        "pending": pending or [],
        "done": done or [],
        "failed": failed or [],
        "exhausted": exhausted or [],
        "evidence": evidence or {},
    }


def test_runway_counts_actionable_interactive_held_blocked_and_running(monkeypatch) -> None:
    gates = [
        {"id": "active", "state": bi.INITIATIVE_ACTIVE, "superseded_by": None},
        {"id": "paused", "state": bi.INITIATIVE_PAUSED, "superseded_by": None},
    ]
    statuses = {
        "active": _status(
            eligible=["P1"],
            in_progress=["P2"],
            evidence={
                "P1": {"task_id": "t1", "current_state": "queued", "review_approved": False, "pr_opened": False},
                "P2": {"task_id": "t2", "current_state": "running", "review_approved": False, "pr_opened": False},
            },
        ),
        "paused": _status(
            blocked=["P3"],
            evidence={
                "P3": {"task_id": "t3", "current_state": "blocked", "review_approved": False, "pr_opened": False},
            },
        ),
    }
    monkeypatch.setattr(aut.bi, "list_initiative_gates", lambda _db=None: gates)
    monkeypatch.setattr(aut.bi, "initiative_status", lambda iid, db_path=None: statuses[iid])

    registry = [
        {"packet_id": "UI-1", "lane": "interactive", "status": "unresolved"},
        {"packet_id": "UI-2", "lane": "interactive", "status": "unresolved", "hold_reason": "PR #999 collision"},
        {"packet_id": "UI-3", "lane": "interactive", "status": "done"},
    ]
    runway = aut.runway_snapshot(packet_registry=registry)

    assert runway["counts"]["safe_backend_runnable"] == 1
    assert runway["counts"]["interactive_frontend"] == 1
    assert runway["counts"]["collision_held"] == 1
    assert runway["counts"]["operator_blocked"] == 1
    assert runway["counts"]["running"] == 1
    assert runway["actionable"] == 2
    assert runway["low_water"] is True


def test_refill_request_distinguishes_low_water_from_caught_up(monkeypatch) -> None:
    gates = [{"id": "done", "state": bi.INITIATIVE_COMPLETED, "superseded_by": None}]
    monkeypatch.setattr(aut.bi, "list_initiative_gates", lambda _db=None: gates)
    monkeypatch.setattr(
        aut.bi,
        "initiative_status",
        lambda iid, db_path=None: _status(done=["P1"], evidence={"P1": {"task_id": "t1", "current_state": "done", "review_approved": True, "pr_opened": True}}),
    )

    runway = aut.runway_snapshot(
        packet_registry=[{"packet_id": "UI-DONE", "lane": "interactive", "status": "done"}]
    )
    request = aut.refill_request(runway)

    assert runway["caught_up"] is True
    assert request["needed"] is False
    assert request["reason"] == "caught_up"


def test_publication_inbox_collects_reviewed_unpublished_packets(monkeypatch) -> None:
    gates = [{"id": "reviewed", "state": bi.INITIATIVE_ACTIVE, "superseded_by": None}]
    status = _status(
        in_progress=["P4"],
        evidence={
            "P4": {
                "task_id": "t4",
                "current_state": "blocked",
                "review_approved": True,
                "review_verdict": "approve",
                "pr_opened": False,
                "pr": None,
            }
        },
    )
    monkeypatch.setattr(aut.bi, "list_initiative_gates", lambda _db=None: gates)
    monkeypatch.setattr(aut.bi, "initiative_status", lambda iid, db_path=None: status)

    inbox = aut.publication_inbox()

    assert inbox == [{
        "initiative_id": "reviewed",
        "packet_id": "P4",
        "task_id": "t4",
        "review_verdict": "approve",
        "current_state": "blocked",
    }]


def test_load_packet_registry_reads_compiled_source_slates(tmp_path: Path) -> None:
    slate_dir = tmp_path / "docs" / "packets" / "slates"
    slate_dir.mkdir(parents=True)
    (slate_dir / "wave.source.json").write_text(
        '{"initiative_id":"wave-v1","packets":['
        '{"lane":"interactive","hold_reason":"PR collision","manifest":{"id":"UI-HOLD"}},'
        '{"lane":"builder","manifest":{"id":"BE-READY"}}]}',
        encoding="utf-8",
    )
    packet_dir = tmp_path / "docs" / "packets"
    (packet_dir / "UI-PRESERVED.md").write_text(
        "# UI-PRESERVED\n\n**Initiative:** `wave-old`\n**Owner:** interactive\n",
        encoding="utf-8",
    )

    registry = aut.load_packet_registry(tmp_path)

    assert registry == [
        {"initiative_id": "wave-v1", "packet_id": "UI-HOLD", "lane": "interactive", "status": "unresolved", "hold_reason": "PR collision"},
        {"initiative_id": "wave-v1", "packet_id": "BE-READY", "lane": "builder", "status": "unresolved"},
    ]


def test_runway_does_not_count_builder_packet_with_existing_open_pr_as_actionable(monkeypatch) -> None:
    gates = [{"id": "active", "state": bi.INITIATIVE_ACTIVE, "superseded_by": None}]
    status = _status(
        eligible=["P1"],
        evidence={"P1": {"task_id": "t1", "current_state": "queued", "review_approved": False, "pr_opened": False}},
    )
    monkeypatch.setattr(aut.bi, "list_initiative_gates", lambda _db=None: gates)
    monkeypatch.setattr(aut.bi, "initiative_status", lambda iid, db_path=None: status)
    monkeypatch.setattr(aut.bq, "get_task", lambda task_id, db_path=None: {"id": task_id, "title": "[P1] Packet"})
    monkeypatch.setattr(aut, "default_branch_name", lambda task: "kittybuilder/t1")
    truth = {"available": True, "by_head": {"kittybuilder/t1": {"number": 99, "state": "OPEN", "mergedAt": None}}}

    runway = aut.runway_snapshot(github_truth=truth)

    assert runway["counts"]["safe_backend_runnable"] == 0
    assert runway["counts"]["operator_blocked"] == 1
    assert runway["buckets"]["operator_blocked"][0]["reason"] == "github_pr_open"


def test_load_packet_registry_does_not_synthesize_state_from_interactive_docs(tmp_path: Path) -> None:
    packet_dir = tmp_path / "docs" / "packets"
    packet_dir.mkdir(parents=True)
    (packet_dir / "UI-ONLY.md").write_text(
        "# UI-ONLY\n\n**Initiative:** `wave-v1`\n**Owner:** interactive\n",
        encoding="utf-8",
    )

    assert aut.load_packet_registry(tmp_path) == []


def test_runway_can_scope_to_one_campaign_prefix(monkeypatch) -> None:
    gates = [
        {"id": "kitty-opens-the-doors-20260831-v1", "state": bi.INITIATIVE_ACTIVE, "superseded_by": None},
        {"id": "old-proof-v1", "state": bi.INITIATIVE_ACTIVE, "superseded_by": None},
    ]
    monkeypatch.setattr(aut.bi, "list_initiative_gates", lambda _db=None: gates)
    monkeypatch.setattr(
        aut.bi,
        "initiative_status",
        lambda iid, db_path=None: _status(
            eligible=["P1"],
            evidence={"P1": {"task_id": f"t-{iid}", "current_state": "queued", "review_approved": False, "pr_opened": False}},
        ),
    )

    runway = aut.runway_snapshot(initiative_prefix="kitty-opens-the-doors-20260831-v")

    assert runway["counts"]["safe_backend_runnable"] == 1
    assert runway["buckets"]["safe_backend_runnable"][0]["initiative_id"] == "kitty-opens-the-doors-20260831-v1"


def test_runway_moves_eligible_backend_to_blocked_when_github_truth_unavailable(monkeypatch) -> None:
    gates = [{"id": "active", "state": bi.INITIATIVE_ACTIVE, "superseded_by": None}]
    status = _status(
        eligible=["P1"],
        evidence={"P1": {"task_id": "t1", "current_state": "queued", "review_approved": False, "pr_opened": False}},
    )
    monkeypatch.setattr(aut.bi, "list_initiative_gates", lambda _db=None: gates)
    monkeypatch.setattr(aut.bi, "initiative_status", lambda iid, db_path=None: status)

    runway = aut.runway_snapshot(
        github_truth={"available": False, "error": "gh unavailable", "by_head": {}},
        reconciliation={"github_available": False, "github_error": "gh unavailable"},
    )

    assert runway["counts"]["safe_backend_runnable"] == 0
    assert runway["counts"]["operator_blocked"] == 1
    assert runway["buckets"]["operator_blocked"][0]["reason"] == "github_truth_unavailable"
    assert runway["actionable"] == 0


def test_refill_is_suppressed_when_reconciliation_truth_is_unavailable() -> None:
    runway = {
        "caught_up": False,
        "low_water": True,
        "actionable": 0,
        "reconciliation": {"github_available": False, "github_error": "offline"},
    }

    request = aut.refill_request(runway)

    assert request == {"needed": False, "reason": "truth_unavailable", "target_candidates": 0}


def test_publication_inbox_is_empty_when_github_truth_is_unavailable(monkeypatch) -> None:
    gates = [{"id": "active", "state": bi.INITIATIVE_ACTIVE, "superseded_by": None}]
    status = _status(
        evidence={"P1": {"task_id": "t1", "current_state": "blocked", "review_approved": True, "review_verdict": "approve", "pr_opened": False, "done": False}}
    )
    monkeypatch.setattr(aut.bi, "list_initiative_gates", lambda _db=None: gates)
    monkeypatch.setattr(aut.bi, "initiative_status", lambda iid, db_path=None: status)

    inbox = aut.publication_inbox(
        github_truth={"available": False, "error": "gh unavailable", "by_head": {}}
    )

    assert inbox == []


def test_unapplied_backend_registry_contract_is_not_actionable(monkeypatch) -> None:
    monkeypatch.setattr(aut.bi, "list_initiative_gates", lambda _db=None: [])
    registry = [
        {
            "initiative_id": "campaign-v9",
            "packet_id": "BE-READY",
            "lane": "builder",
            "status": "unresolved",
        }
    ]

    runway = aut.runway_snapshot(
        packet_registry=registry,
        github_truth={"available": True, "by_head": {}},
        reconciliation={"github_available": True},
    )

    assert runway["counts"]["safe_backend_runnable"] == 0
    assert runway["counts"]["operator_blocked"] == 1
    assert runway["buckets"]["operator_blocked"][0]["reason"] == "unapplied_registry_contract"
    assert runway["actionable"] == 0


def test_load_packet_registry_fails_closed_on_malformed_source_slate(tmp_path: Path) -> None:
    slate_dir = tmp_path / "docs" / "packets" / "slates"
    slate_dir.mkdir(parents=True)
    (slate_dir / "broken.source.json").write_text("{not-json", encoding="utf-8")

    with pytest.raises(aut.PacketRegistryError, match="broken.source.json"):
        aut.load_packet_registry(tmp_path)


def test_load_packet_registry_does_not_infer_live_work_from_retained_packet_docs(tmp_path: Path) -> None:
    packet_dir = tmp_path / "docs" / "packets"
    packet_dir.mkdir(parents=True)
    (packet_dir / "UI-OLD.md").write_text(
        "# UI-OLD\n\n**Initiative:** `wave-v1`\n**Owner:** interactive\n",
        encoding="utf-8",
    )

    assert aut.load_packet_registry(tmp_path) == []
