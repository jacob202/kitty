"""Format bounded Builder facts for the Work projection."""

from __future__ import annotations

from datetime import timezone

from gateway._work_projection_select import _sort_timestamp

_MAX_REASON_LENGTH = 240
_WORK_STATE_PRIORITY = {
    "active": 0,
    "blocked": 1,
    "failed": 2,
    "ready": 3,
    "waiting": 4,
    "paused": 5,
    "completed": 6,
}


def _project_queue(queue):
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


def _source_projection(builder_status):
    integrity = builder_status.get("integrity") or {}
    integrity_state = integrity.get("state")
    if integrity_state == "complete":
        return {
            "kind": "builder",
            "state": "available",
            "snapshot_schema_version": builder_status.get("schema_version"),
            "integrity": integrity,
        }

    partial = int(integrity.get("partial_packets", 0) or 0)
    total = int(integrity.get("total_packets", 0) or 0)
    if integrity_state == "partial":
        reason = f"Builder snapshot integrity is partial: {partial} of {total} packets are incomplete."
    else:
        reason = f"Builder snapshot integrity state is unsupported: {integrity_state or 'missing'}."
    return {
        "kind": "builder",
        "state": "degraded",
        "snapshot_schema_version": builder_status.get("schema_version"),
        "integrity": integrity,
        "reason": _bounded_reason(reason),
    }


def _rank_work_items(items):
    recent_first = sorted(
        items,
        key=lambda item: (item.get("updated_at") or "", item.get("id") or ""),
        reverse=True,
    )
    return sorted(
        recent_first,
        key=lambda item: _WORK_STATE_PRIORITY.get(item.get("state"), 99),
    )


def _count_states(items):
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


def _latest_updated_at(initiative, packets):
    timestamps = [initiative.get("updated_at"), *(packet.get("updated_at") for packet in packets)]
    available = [value for value in timestamps if value]
    if not available:
        return None
    return max(available, key=_sort_timestamp)


def _timestamp(now):
    return now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _bounded_reason(value):
    if value is None:
        return None
    text = str(value).strip().replace("\n", " ")
    if not text:
        return None
    if len(text) <= _MAX_REASON_LENGTH:
        return text
    return text[: _MAX_REASON_LENGTH - 1].rstrip() + "…"
