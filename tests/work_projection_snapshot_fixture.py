from __future__ import annotations


def _snapshot_for(packet, *, initiative_state="active", next_packet=None):
    return {
        "schema_version": 2,
        "integrity": {"state": "complete", "partial_packets": 0, "total_packets": 1},
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
