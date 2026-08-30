from __future__ import annotations

from gateway.work_projection import project_work_snapshot
from tests.work_projection_packet_fixture import NOW, _base_packet
from tests.work_projection_snapshot_fixture import _snapshot_for


def test_projection_maps_active_ready_blocked_paused_failed_completed_and_waiting_states():
    scenarios = [
        ("active", _base_packet("p1", run_state="running"), "active", "p1"),
        (
            "ready",
            _base_packet("p2", eligibility_state="eligible", next_action="claim"),
            "ready",
            "p2",
        ),
        (
            "blocked",
            _base_packet("p3", eligibility_state="blocked", blocked_by=["dep-1"]),
            "blocked",
            "p3",
        ),
        ("paused", _base_packet("p4"), "paused", "p4"),
        (
            "failed",
            _base_packet("p5", task_state="failed", failure_kind="implementation"),
            "failed",
            "p5",
        ),
        ("completed", _base_packet("p6", task_state="done", next_action="done"), "completed", "p6"),
        ("waiting", _base_packet("p7", task_state="claimed"), "waiting", "p7"),
    ]
    for label, packet, expected_state, expected_packet_id in scenarios:
        initiative_state = "completed" if label == "completed" else "active"
        if label == "paused":
            initiative_state = "paused"
        payload = project_work_snapshot(
            _snapshot_for(
                packet,
                initiative_state=initiative_state,
                next_packet=packet["packet_id"] if label == "ready" else None,
            ),
            now=NOW,
        )
        item = payload["items"][0]
        assert item["state"] == expected_state
        assert item["current_packet"]["id"] == expected_packet_id
        assert item["source"] == {
            "kind": "builder",
            "initiative_id": "init-1",
            "packet_id": expected_packet_id,
        }
        assert item["evidence"]["approval"]["state"] == "unavailable"
        assert "binding" in item["evidence"]["approval"]["reason"]


def test_projection_chooses_current_packet_by_live_run_then_next_packet_then_non_terminal_then_recency():
    live = _base_packet("live", run_state="starting", updated_at="2026-08-13T11:50:00Z")
    newer = _base_packet("newer", eligibility_state="eligible", updated_at="2026-08-13T11:59:00Z")
    snapshot = {
        "schema_version": 2,
        "integrity": {"state": "complete", "partial_packets": 0, "total_packets": 2},
        "queue": {
            "total": 2,
            "queued": 2,
            "claimed": 0,
            "running": 0,
            "blocked": 0,
            "pr_opened": 0,
            "awaiting_review": 0,
            "done": 0,
            "failed": 0,
            "cancelled": 0,
        },
        "initiatives": [
            {
                "initiative_id": "init-1",
                "title": "Builder initiative",
                "state": "active",
                "pause_reason": None,
                "next_packet": "newer",
                "updated_at": "2026-08-13T11:40:00Z",
                "packets": [newer, live],
            }
        ],
    }
    payload = project_work_snapshot(snapshot, now=NOW)
    assert payload["items"][0]["current_packet"]["id"] == "live"
    live["run"] = None
    payload = project_work_snapshot(snapshot, now=NOW)
    assert payload["items"][0]["current_packet"]["id"] == "newer"
    snapshot["initiatives"][0]["next_packet"] = None
    newer["task_state"] = "done"
    live["task_state"] = "claimed"
    payload = project_work_snapshot(snapshot, now=NOW)
    assert payload["items"][0]["current_packet"]["id"] == "live"
    live["task_state"] = "done"
    payload = project_work_snapshot(snapshot, now=NOW)
    assert payload["items"][0]["current_packet"]["id"] == "newer"


def test_projection_marks_partial_integrity_as_degraded_and_reports_bounded_blocker():
    packet = _base_packet(
        "p1", eligibility_state="blocked", blocked_reason="x" * 400, data_quality_state="partial"
    )
    snapshot = _snapshot_for(packet)
    snapshot["integrity"] = {"state": "partial", "partial_packets": 1, "total_packets": 1}
    payload = project_work_snapshot(snapshot, now=NOW)
    assert payload["source"]["state"] == "degraded"
    assert "partial" in payload["source"]["reason"]
    assert payload["items"][0]["blocker"]["state"] == "blocked"
    assert len(payload["items"][0]["blocker"]["reason"]) <= 240
    assert payload["items"][0]["data_quality"]["state"] == "partial"


def test_projection_preserves_observation_window_and_counts():
    packet = _base_packet("p1", eligibility_state="eligible", next_action="claim")
    payload = project_work_snapshot(_snapshot_for(packet, next_packet="p1"), now=NOW)
    assert payload["schema_version"] == 1
    assert payload["observed_at"] == "2026-08-13T12:00:00Z"
    assert payload["valid_until"] == "2026-08-13T12:00:30Z"
    assert payload["counts"] == {
        "total": 1,
        "active": 0,
        "paused": 0,
        "failed": 0,
        "blocked": 0,
        "completed": 0,
        "ready": 1,
        "waiting": 0,
    }

def test_bounded_projection_keeps_each_present_product_group_represented():
    initiatives = []
    for index in range(54):
        packet = _base_packet(
            f"blocked-{index}",
            eligibility_state="blocked",
            blocked_by=["dependency"],
            updated_at=f"2026-08-13T11:{index % 60:02d}:00Z",
        )
        item = _snapshot_for(packet)["initiatives"][0]
        item["initiative_id"] = f"blocked-{index}"
        initiatives.append(item)

    waiting_packet = _base_packet("waiting-1", task_state="claimed")
    waiting = _snapshot_for(waiting_packet)["initiatives"][0]
    waiting["initiative_id"] = "waiting-1"
    initiatives.append(waiting)

    for index in range(10):
        packet = _base_packet(f"done-{index}", task_state="done", next_action="done")
        item = _snapshot_for(packet, initiative_state="completed")["initiatives"][0]
        item["initiative_id"] = f"done-{index}"
        initiatives.append(item)

    source = {
        "schema_version": 2,
        "integrity": {"state": "complete", "partial_packets": 0, "total_packets": 65},
        "initiatives": initiatives,
    }

    payload = project_work_snapshot(source, now=NOW)

    assert payload["total_items"] == 65
    assert len(payload["items"]) == 50
    states = {item["state"] for item in payload["items"]}
    assert "blocked" in states
    assert "waiting" in states
    assert "completed" in states
    assert payload["counts"]["completed"] == 10


def test_bounded_projection_treats_terminal_cancelled_failures_as_completed_group():
    initiatives = []
    for index in range(50):
        packet = _base_packet(
            f"blocked-{index}",
            eligibility_state="blocked",
            blocked_by=["dependency"],
            updated_at=f"2026-08-13T11:{index % 60:02d}:00Z",
        )
        item = _snapshot_for(packet)["initiatives"][0]
        item["initiative_id"] = f"blocked-{index}"
        initiatives.append(item)

    cancelled_packet = _base_packet("cancelled-terminal", task_state="cancelled", next_action="cancelled")
    cancelled = _snapshot_for(cancelled_packet, initiative_state="failed")["initiatives"][0]
    cancelled["initiative_id"] = "cancelled-terminal"
    initiatives.append(cancelled)

    payload = project_work_snapshot({
        "schema_version": 2,
        "integrity": {"state": "complete", "partial_packets": 0, "total_packets": 51},
        "initiatives": initiatives,
    }, now=NOW)

    terminal = next(item for item in payload["items"] if item["id"] == "cancelled-terminal")
    assert terminal["state"] == "failed"
    assert terminal["next_action"] == "cancelled"


def test_primary_work_projection_hides_superseded_history_but_counts_it():
    current_packet = _base_packet("current", eligibility_state="eligible", next_action="claim")
    old_packet = _base_packet("old", task_state="blocked", next_action="recover")
    current = _snapshot_for(current_packet, next_packet="current")["initiatives"][0]
    current["initiative_id"] = "current-init"
    old = _snapshot_for(old_packet, initiative_state="paused")["initiatives"][0]
    old["initiative_id"] = "old-init"
    old["superseded_by"] = "KITTY-RECOVERY-001"
    old["superseded_at"] = "2026-08-30T17:00:00Z"
    source = {
        "schema_version": 2,
        "integrity": {"state": "complete", "partial_packets": 0, "total_packets": 2},
        "initiatives": [old, current],
    }

    payload = project_work_snapshot(source, now=NOW)

    assert [item["id"] for item in payload["items"]] == ["current-init"]
    assert payload["total_items"] == 1
    assert payload["historical_items"] == 1
    assert payload["counts"]["total"] == 1
