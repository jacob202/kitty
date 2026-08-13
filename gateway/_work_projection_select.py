"""Select current Builder packet facts for the Work projection."""

from __future__ import annotations

_ACTIVE_RUN_STATES = {"starting", "running", "cancel_requested"}
_NON_TERMINAL_TASK_STATES = {
    "queued",
    "claimed",
    "running",
    "blocked",
    "pr_opened",
    "awaiting_review",
}


def _select_current_packet(initiative, packets):
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
        packet for packet in packets if packet.get("task_state") in _NON_TERMINAL_TASK_STATES
    ]
    if non_terminal:
        return _sort_packets(non_terminal)[0]
    return _sort_packets(packets)[0]


def _sort_packets(packets):
    return sorted(
        packets,
        key=lambda packet: (
            _sort_timestamp(packet.get("updated_at")),
            packet.get("packet_id") or "",
        ),
        reverse=True,
    )


def _has_live_run(packet):
    run_state = ((packet.get("run") or {}).get("state") or "").strip()
    return run_state in _ACTIVE_RUN_STATES


def _latest_attempt(packet):
    attempts = (packet or {}).get("attempt_history") or []
    return attempts[0] if attempts else None


def _sort_timestamp(value):
    if not value:
        return (0, "")
    return (1, value)
