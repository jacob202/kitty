"""Project packet, run, and blocker details for Work items."""

from __future__ import annotations

from gateway._work_projection_support import _bounded_reason


def _project_packet(packet):
    if packet is None:
        return None
    eligibility = packet.get("eligibility") or {}
    projection = packet.get("projection") or {}
    return {
        "id": packet.get("packet_id"),
        "title": packet.get("title"),
        "objective": packet.get("objective"),
        "task_id": packet.get("task_id"),
        "task_state": packet.get("task_state"),
        "eligibility": {
            "state": eligibility.get("state"),
            "blocked_by": list(eligibility.get("blocked_by") or []),
        },
        "failure_kind": packet.get("failure_kind"),
        "next_action": _bounded_reason(projection.get("next_action")),
        "updated_at": packet.get("updated_at"),
    }


def _project_run(packet):
    run = (packet or {}).get("run")
    if run is None:
        return None
    return {
        "id": run.get("id"),
        "state": run.get("state"),
        "started_at": run.get("started_at"),
        "last_heartbeat_at": run.get("last_heartbeat_at"),
        "ended_at": run.get("ended_at"),
        "exit_code": run.get("exit_code"),
        "updated_at": run.get("updated_at"),
    }


def _project_blocker(initiative, current_packet, packets):
    packet = current_packet or next(
        (candidate for candidate in packets if _blocking_reason(candidate)), None
    )
    if packet is None:
        return None
    reason = _blocking_reason(packet)
    if reason is None:
        if initiative.get("state") == "paused" and initiative.get("pause_reason"):
            return {"state": "blocked", "reason": _bounded_reason(initiative.get("pause_reason"))}
        return None
    blocked_by = list((packet.get("eligibility") or {}).get("blocked_by") or [])[:10]
    return {
        "state": "blocked",
        "packet_id": packet.get("packet_id"),
        "reason": reason,
        "blocked_by": blocked_by,
    }


def _blocking_reason(packet):
    eligibility = packet.get("eligibility") or {}
    blocked_by = list(eligibility.get("blocked_by") or [])
    if packet.get("blocked_reason"):
        return _bounded_reason(packet.get("blocked_reason"))
    if eligibility.get("state") == "blocked":
        if blocked_by:
            joined = ", ".join((str(item) for item in blocked_by[:5]))
            return _bounded_reason(f"Blocked by {joined}.")
        return "Blocked by Builder eligibility."
    if eligibility.get("state") == "unavailable":
        if blocked_by:
            joined = ", ".join((str(item) for item in blocked_by[:5]))
            return _bounded_reason(f"Eligibility data is unavailable for {joined}.")
        return "Eligibility data is unavailable."
    if packet.get("last_error"):
        return _bounded_reason(packet.get("last_error"))
    return None
