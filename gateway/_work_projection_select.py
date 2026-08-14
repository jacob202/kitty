_ACTIVE_RUN_STATES = {"starting", "running", "cancel_requested"}
_NON_TERMINAL_TASK_STATES = {"queued", "claimed", "running", "blocked", "pr_opened", "awaiting_review"}


def _is_failed(packet):
    kind = packet.get("failure_kind")
    return packet.get("task_state") == "failed" or kind not in {None, "blocked", "cancelled"}


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


def _sort_packets(packets):
    return sorted(packets, key=lambda packet: (_sort_timestamp(packet.get("updated_at")), packet.get("packet_id") or ""), reverse=True)


def _has_live_run(packet):
    state = ((packet.get("run") or {}).get("state") or "").strip()
    return state in _ACTIVE_RUN_STATES


def _latest_attempt(packet):
    attempts = (packet or {}).get("attempt_history") or []
    return attempts[0] if attempts else None


def _sort_timestamp(value):
    return (1, value) if value else (0, "")
