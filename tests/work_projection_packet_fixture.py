from __future__ import annotations

from datetime import datetime, timezone

NOW = datetime(2026, 8, 13, 12, 0, tzinfo=timezone.utc)


def _base_packet(
    packet_id,
    *,
    task_state="queued",
    run_state=None,
    eligibility_state="waiting",
    blocked_by=None,
    blocked_reason=None,
    failure_kind=None,
    next_action="wait",
    updated_at="2026-08-13T12:00:00Z",
    data_quality_state="complete",
):
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
        "eligibility": {"state": eligibility_state, "blocked_by": blocked_by or []},
        "run": run,
        "failure_kind": failure_kind,
        "blocked_reason": blocked_reason,
        "last_error": None,
        "updated_at": updated_at,
        "projection": {"next_action": next_action},
        "attempt_history": [],
        "publication": None,
        "data_quality": {"state": data_quality_state, "issues": []},
    }
