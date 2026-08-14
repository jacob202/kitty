"""Project one Builder initiative into a product Work item."""

from gateway._work_projection_details import _project_blocker, _project_packet, _project_run
from gateway._work_projection_select import _has_live_run, _latest_attempt, _select_current_packet
from gateway._work_projection_support import _bounded_reason, _latest_updated_at


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


def _has_failure(initiative, current_packet, packets):
    if initiative.get("state") == "failed":
        return True
    if current_packet is not None and _packet_failed(current_packet):
        return True
    return any(_packet_failed(packet) for packet in packets)


def _packet_failed(packet):
    if packet.get("task_state") == "failed":
        return True
    failure_kind = packet.get("failure_kind")
    return failure_kind not in {None, "blocked", "cancelled"}
