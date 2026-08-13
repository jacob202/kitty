"""Project Builder snapshot facts into the product Work read model."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

SCHEMA_VERSION = 1
WORK_TTL_SECONDS = 30
WORK_ITEM_LIMIT = 50
_ACTIVE_RUN_STATES = {"starting", "running", "cancel_requested"}
_NON_TERMINAL_TASK_STATES = {
    "queued",
    "claimed",
    "running",
    "blocked",
    "pr_opened",
    "awaiting_review",
}
_TERMINAL_TASK_STATES = {"done", "failed", "cancelled"}
_MAX_REASON_LENGTH = 240


def project_work_snapshot(
    snapshot: dict[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return the schema-v1 product Work snapshot from Builder snapshot facts."""
    observed = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    observed_at = _timestamp(observed)
    valid_until = _timestamp(observed + timedelta(seconds=WORK_TTL_SECONDS))
    items = [_project_work_item(initiative) for initiative in snapshot.get("initiatives", [])]
    bounded_items = items[:WORK_ITEM_LIMIT]
    return {
        "schema_version": SCHEMA_VERSION,
        "observed_at": observed_at,
        "valid_until": valid_until,
        "source": _source_projection(snapshot),
        "counts": _count_states(bounded_items),
        "queue": _project_queue(snapshot.get("queue")),
        "items": bounded_items,
        "item_limit": WORK_ITEM_LIMIT,
        "total_items": len(items),
    }


def _project_work_item(initiative: dict[str, Any]) -> dict[str, Any]:
    packets = initiative.get("packets") or []
    current_packet = _select_current_packet(initiative, packets)
    blocker = _project_blocker(initiative, current_packet, packets)
    state = _project_state(initiative, current_packet, packets, blocker)
    current_run = _project_run(current_packet)
    current_attempt = _latest_attempt(current_packet)
    publication = (current_packet or {}).get("publication")
    return {
        "id": initiative["initiative_id"],
        "title": initiative.get("title"),
        "state": state,
        "source": {
            "kind": "builder",
            "initiative_id": initiative["initiative_id"],
            "packet_id": (current_packet or {}).get("packet_id"),
        },
        "current_packet": _project_packet(current_packet),
        "current_run": current_run,
        "blocker": blocker,
        "next_action": _bounded_reason((current_packet or {}).get("projection", {}).get("next_action")),
        "evidence": {
            "validation": (current_attempt or {}).get("validation"),
            "review": (current_attempt or {}).get("review"),
            "publication": publication,
            "approval": {
                "state": "unavailable",
                "reason": (
                    "No durable Gateway approval binding exists for Builder initiatives yet."
                ),
            },
        },
        "data_quality": dict((current_packet or {}).get("data_quality") or {"state": "complete", "issues": []}),
        "updated_at": _latest_updated_at(initiative, packets),
    }


def _project_state(
    initiative: dict[str, Any],
    current_packet: dict[str, Any] | None,
    packets: list[dict[str, Any]],
    blocker: dict[str, Any] | None,
) -> str:
    if any(_has_live_run(packet) for packet in packets):
        return "active"
    if initiative.get("state") == "paused":
        return "paused"
    if blocker is not None and blocker.get("state") == "blocked":
        return "blocked"
    if initiative.get("state") == "completed":
        return "completed"
    if _has_failure(initiative, current_packet, packets):
        return "failed"
    if any((packet.get("eligibility") or {}).get("state") == "eligible" for packet in packets):
        return "ready"
    return "waiting"


def _has_failure(
    initiative: dict[str, Any],
    current_packet: dict[str, Any] | None,
    packets: list[dict[str, Any]],
) -> bool:
    if initiative.get("state") == "failed":
        return True
    if current_packet is not None and _packet_failed(current_packet):
        return True
    return any(_packet_failed(packet) for packet in packets)


def _packet_failed(packet: dict[str, Any]) -> bool:
    if packet.get("task_state") == "failed":
        return True
    failure_kind = packet.get("failure_kind")
    return failure_kind not in {None, "blocked", "cancelled"}


def _project_packet(packet: dict[str, Any] | None) -> dict[str, Any] | None:
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


def _project_run(packet: dict[str, Any] | None) -> dict[str, Any] | None:
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


def _project_blocker(
    initiative: dict[str, Any],
    current_packet: dict[str, Any] | None,
    packets: list[dict[str, Any]],
) -> dict[str, Any] | None:
    packet = current_packet or next((candidate for candidate in packets if _blocking_reason(candidate)), None)
    if packet is None:
        return None
    reason = _blocking_reason(packet)
    if reason is None:
        if initiative.get("state") == "paused" and initiative.get("pause_reason"):
            return {"state": "blocked", "reason": _bounded_reason(initiative.get("pause_reason"))}
        return None
    blocked_by = list(((packet.get("eligibility") or {}).get("blocked_by") or []))[:10]
    return {
        "state": "blocked",
        "packet_id": packet.get("packet_id"),
        "reason": reason,
        "blocked_by": blocked_by,
    }


def _blocking_reason(packet: dict[str, Any]) -> str | None:
    eligibility = packet.get("eligibility") or {}
    blocked_by = list(eligibility.get("blocked_by") or [])
    if packet.get("blocked_reason"):
        return _bounded_reason(packet.get("blocked_reason"))
    if eligibility.get("state") == "blocked":
        if blocked_by:
            joined = ", ".join(str(item) for item in blocked_by[:5])
            return _bounded_reason(f"Blocked by {joined}.")
        return "Blocked by Builder eligibility."
    if eligibility.get("state") == "unavailable":
        if blocked_by:
            joined = ", ".join(str(item) for item in blocked_by[:5])
            return _bounded_reason(f"Eligibility data is unavailable for {joined}.")
        return "Eligibility data is unavailable."
    if packet.get("last_error"):
        return _bounded_reason(packet.get("last_error"))
    return None


def _select_current_packet(
    initiative: dict[str, Any],
    packets: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if not packets:
        return None
    live_packets = [packet for packet in packets if _has_live_run(packet)]
    if live_packets:
        return _sort_packets(live_packets)[0]
    next_packet_id = initiative.get("next_packet")
    if next_packet_id:
        for packet in packets:
            if packet.get("packet_id") == next_packet_id:
                return packet
    non_terminal = [
        packet
        for packet in packets
        if packet.get("task_state") in _NON_TERMINAL_TASK_STATES
    ]
    if non_terminal:
        return _sort_packets(non_terminal)[0]
    return _sort_packets(packets)[0]


def _sort_packets(packets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        packets,
        key=lambda packet: (
            _sort_timestamp(packet.get("updated_at")),
            packet.get("packet_id") or "",
        ),
        reverse=True,
    )


def _has_live_run(packet: dict[str, Any]) -> bool:
    run_state = ((packet.get("run") or {}).get("state") or "").strip()
    return run_state in _ACTIVE_RUN_STATES


def _latest_attempt(packet: dict[str, Any] | None) -> dict[str, Any] | None:
    attempts = (packet or {}).get("attempt_history") or []
    return attempts[0] if attempts else None


def _project_queue(queue: Any) -> dict[str, int] | None:
    if not isinstance(queue, dict):
        return None
    keys = (
        "total",
        "queued",
        "claimed",
        "running",
        "blocked",
        "pr_opened",
        "awaiting_review",
        "done",
        "failed",
        "cancelled",
    )
    return {key: int(queue.get(key, 0) or 0) for key in keys}


def _source_projection(snapshot: dict[str, Any]) -> dict[str, Any]:
    integrity = snapshot.get("integrity") or {}
    if integrity.get("state") == "partial":
        partial = int(integrity.get("partial_packets", 0) or 0)
        total = int(integrity.get("total_packets", 0) or 0)
        return {
            "kind": "builder",
            "state": "degraded",
            "snapshot_schema_version": snapshot.get("schema_version"),
            "integrity": integrity,
            "reason": _bounded_reason(
                f"Builder snapshot integrity is partial: {partial} of {total} packets are incomplete."
            ),
        }
    return {
        "kind": "builder",
        "state": "available",
        "snapshot_schema_version": snapshot.get("schema_version"),
        "integrity": integrity,
    }


def _count_states(items: list[dict[str, Any]]) -> dict[str, int]:
    counts = {
        "total": len(items),
        "active": 0,
        "paused": 0,
        "failed": 0,
        "blocked": 0,
        "completed": 0,
        "ready": 0,
        "waiting": 0,
    }
    for item in items:
        state = item.get("state")
        if state in counts:
            counts[state] += 1
    return counts


def _latest_updated_at(initiative: dict[str, Any], packets: list[dict[str, Any]]) -> str | None:
    timestamps = [initiative.get("updated_at"), *(packet.get("updated_at") for packet in packets)]
    available = [value for value in timestamps if value]
    if not available:
        return None
    return max(available, key=_sort_timestamp)


def _sort_timestamp(value: str | None) -> tuple[int, str]:
    if not value:
        return (0, "")
    return (1, value)


def _timestamp(now: datetime) -> str:
    return now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _bounded_reason(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().replace("\n", " ")
    if not text:
        return None
    if len(text) <= _MAX_REASON_LENGTH:
        return text
    return text[: _MAX_REASON_LENGTH - 1].rstrip() + "…"
