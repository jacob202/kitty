from __future__ import annotations

from datetime import datetime, timezone

from gateway.work_projection import project_work_snapshot

NOW = datetime(2026, 8, 13, 12, 0, tzinfo=timezone.utc)


def _base_packet(
    packet_id: str,
    *,
    task_state: str = "queued",
    run_state: str | None = None,
    eligibility_state: str = "waiting",
    blocked_by: list[str] | None = None,
    blocked_reason: str | None = None,
    failure_kind: str | None = None,
    last_error: str | None = None,
    next_action: str | None = "wait",
    updated_at: str = "2026-08-13T12:00:00Z",
    data_quality_state: str = "complete",
) -> dict:
    run = None
    if run_state is not None:
        run = {
            "id": 91,
            "state": run_state,
            "started_at": "2026-08-13T11:58:00Z",
            "last_heartbeat_at": "2026-08-13T11:59:30Z",
            "ended_at": None,
            "exit_code": None,
            "updated_at": updated_at,
        }
    return {
        "packet_id": packet_id,
        "title": f"title-{packet_id}",
        "objective": f"objective-{packet_id}",
        "task_id": f"task-{packet_id}",
        "task_state": task_state,
        "eligibility": {
            "state": eligibility_state,
            "blocked_by": blocked_by or [],
        },
        "run": run,
        "failure_kind": failure_kind,
        "blocked_reason": blocked_reason,
        "last_error": last_error,
        "updated_at": updated_at,
        "projection": {"next_action": next_action},
        "attempt_history": [
            {
                "validation": {"status": "passed", "command_count": 1},
                "review": {"verdict": "approved", "summary": "looks good"},
            }
        ],
        "publication": {
            "pr_number": 12,
            "pr_url": "https://github.com/example/repo/pull/12",
            "checks_state": "success",
            "review_state": "approved",
            "merged": False,
            "merged_at": None,
            "updated_at": updated_at,
        },
        "data_quality": {"state": data_quality_state, "issues": []},
    }


def _snapshot_for(packet: dict, *, initiative_state: str = "active", next_packet: str | None = None) -> dict:
    return {
        "schema_version": 2,
        "integrity": {"state": "complete", "partial_packets": 0, "total_packets": 1},
        "queue": {"total": 1, "queued": 1, "claimed": 0, "running": 0, "blocked": 0, "pr_opened": 0, "awaiting_review": 0, "done": 0, "failed": 0, "cancelled": 0},
        "initiatives": [
            {
                "initiative_id": "init-1",
                "title": "Builder initiative",
                "state": initiative_state,
                "pause_reason": "operator pause",
                "next_packet": next_packet,
                "updated_at": "2026-08-13T11:59:00Z",
                "packets": [packet],
            }
        ],
    }


def test_projection_maps_active_ready_blocked_paused_failed_completed_and_waiting_states():
    scenarios = [
        ("active", _base_packet("p1", run_state="running"), "active", "p1"),
        ("ready", _base_packet("p2", eligibility_state="eligible", next_action="claim"), "ready", "p2"),
        ("blocked", _base_packet("p3", eligibility_state="blocked", blocked_by=["dep-1"]), "blocked", "p3"),
        ("paused", _base_packet("p4"), "paused", "p4"),
        ("failed", _base_packet("p5", task_state="failed", failure_kind="implementation"), "failed", "p5"),
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
        "queue": {"total": 2, "queued": 2, "claimed": 0, "running": 0, "blocked": 0, "pr_opened": 0, "awaiting_review": 0, "done": 0, "failed": 0, "cancelled": 0},
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
        "p1",
        eligibility_state="blocked",
        blocked_reason="x" * 400,
        data_quality_state="partial",
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

