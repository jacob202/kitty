"""Project Builder control-plane state into product Work items.

Turns a Builder status snapshot (initiatives, packets, runs, queue) into the
flat ``project_work_snapshot`` document that the product Work surface and
Project Resume consume. It introduces no new source of truth: every field is a
projection of existing Builder state, heavily bounded so a broken or partial
snapshot degrades gracefully instead of surfacing raw internal shape.

This module is deliberately one deep module rather than a cluster of small
helper modules: the private projection/selection/formatting functions share one
snapshot shape and one set of invariants, and the only surface external callers
see is ``project_work_snapshot``.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

SCHEMA_VERSION = 1
WORK_TTL_SECONDS = 30
WORK_ITEM_LIMIT = 50

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
_ACTIVE_RUN_STATES = {"starting", "running", "cancel_requested"}
_NON_TERMINAL_TASK_STATES = {"queued", "claimed", "running", "blocked", "pr_opened", "awaiting_review"}


def _timestamp(now):
    return now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _sort_timestamp(value):
    return (1, value) if value else (0, "")


def _bounded_reason(value):
    if value is None:
        return None
    text = str(value).strip().replace("\n", " ")
    if not text:
        return None
    if len(text) <= _MAX_REASON_LENGTH:
        return text
    return text[: _MAX_REASON_LENGTH - 1].rstrip() + "…"


def _is_failed(packet):
    kind = packet.get("failure_kind")
    return packet.get("task_state") == "failed" or kind not in {None, "blocked", "cancelled"}


def _has_live_run(packet):
    state = ((packet.get("run") or {}).get("state") or "").strip()
    return state in _ACTIVE_RUN_STATES


def _sort_packets(packets):
    return sorted(
        packets,
        key=lambda packet: (_sort_timestamp(packet.get("updated_at")), packet.get("packet_id") or ""),
        reverse=True,
    )


def _select_current_packet(initiative, packets):
    if not packets:
        return None
    live = [packet for packet in packets if _has_live_run(packet)]
    if live:
        return _sort_packets(live)[0]
    if initiative.get("state") == "failed":
        failures = [packet for packet in packets if _is_failed(packet)]
        if failures:
            return _sort_packets(failures)[0]
    next_id = initiative.get("next_packet")
    if next_id:
        for packet in packets:
            if packet.get("packet_id") == next_id:
                return packet
    candidates = [packet for packet in packets if packet.get("task_state") in _NON_TERMINAL_TASK_STATES]
    if candidates:
        return _sort_packets(candidates)[0]
    return _sort_packets(packets)[0]


def _latest_attempt(packet):
    attempts = (packet or {}).get("attempt_history") or []
    return attempts[0] if attempts else None


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


def _product_group(item):
    state = item.get("state")
    if state == "completed" or item.get("next_action") in {"cancelled", "done"}:
        return "completed"
    if state in {"blocked", "failed", "paused"}:
        return "needs-you"
    return "in-progress"


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


def _select_bounded_work_items(ranked, limit):
    if len(ranked) <= limit:
        return ranked

    selected = list(ranked[:limit])
    group_counts = {}
    for item in selected:
        group = _product_group(item)
        group_counts[group] = group_counts.get(group, 0) + 1

    for group in ("needs-you", "in-progress", "completed"):
        if group_counts.get(group, 0) > 0:
            continue
        candidate = next((item for item in ranked if _product_group(item) == group), None)
        if candidate is None:
            continue
        replace_index = next(
            (
                index
                for index in range(len(selected) - 1, -1, -1)
                if group_counts.get(_product_group(selected[index]), 0) > 1
            ),
            None,
        )
        if replace_index is None:
            continue
        replaced_group = _product_group(selected[replace_index])
        group_counts[replaced_group] -= 1
        selected[replace_index] = candidate
        group_counts[group] = 1

    selected_ids = {id(item) for item in selected}
    return [item for item in ranked if id(item) in selected_ids]


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


def _packet_failed(packet):
    if packet.get("task_state") == "failed":
        return True
    failure_kind = packet.get("failure_kind")
    return failure_kind not in {None, "blocked", "cancelled"}


def _has_failure(initiative, current_packet, packets):
    if initiative.get("state") == "failed":
        return True
    if current_packet is not None and _packet_failed(current_packet):
        return True
    return any(_packet_failed(packet) for packet in packets)


def _project_state(initiative, current_packet, packets, blocker):
    if any(_has_live_run(packet) for packet in packets):
        return "active"
    if initiative.get("state") == "paused" and initiative.get("pause_reason"):
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


def _project_work_item(initiative):
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
                "reason": "No durable Gateway approval binding exists for Builder initiatives yet.",
            },
        },
        "data_quality": dict((current_packet or {}).get("data_quality") or {"state": "complete", "issues": []}),
        "updated_at": _latest_updated_at(initiative, packets),
    }


def _build(source, now=None):
    observed = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    initiatives = source.get("initiatives", [])
    historical = [item for item in initiatives if item.get("superseded_by")]
    current = [item for item in initiatives if not item.get("superseded_by")]
    source_for_projection = source
    if historical:
        packets = [
            packet
            for initiative in current
            for packet in (initiative.get("packets") or [])
            if isinstance(packet, dict)
        ]
        partial_packets = sum(
            1
            for packet in packets
            if (packet.get("data_quality") or {}).get("state") != "complete"
        )
        source_for_projection = dict(source)
        source_for_projection["integrity"] = {
            "state": "partial" if partial_packets else "complete",
            "partial_packets": partial_packets,
            "total_packets": len(packets),
        }
    items = [_project_work_item(item) for item in current]
    ranked = _rank_work_items(items)
    bounded = _select_bounded_work_items(ranked, WORK_ITEM_LIMIT)
    return {
        "schema_version": SCHEMA_VERSION,
        "observed_at": _timestamp(observed),
        "valid_until": _timestamp(observed + timedelta(seconds=WORK_TTL_SECONDS)),
        "source": _source_projection(source_for_projection),
        "counts": _count_states(items),
        "queue": _project_queue(source.get("queue")),
        "items": bounded,
        "item_limit": WORK_ITEM_LIMIT,
        "total_items": len(items),
        "historical_items": len(historical),
    }


project_work_snapshot = _build
