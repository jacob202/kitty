"""Read-only explanation projection over the governed explicit-memory store (#552).

QoL Packet 04: for any significant remembered fact the user can ask *where did you get
that?* and receive a truthful, id-addressable explanation — fact, source, source type,
time, authority, confidence/truth status, superseded value, current state, sensitivity —
without ever touching Kitty's memory internals. This module never mutates and never
exposes embedding bytes; it composes ``explicit_memory`` only.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from gateway import explicit_memory
from gateway.explicit_memory import ExplicitMemoryNotFound

# source_kinds that are user-attributed authority. Everything else (insight_loop,
# repairs, web_search, ...) is automated.
_USER_KINDS = frozenset({"user_explicit", "user_correction", "verbal_confirmation"})


def _authority(source_kind: str) -> str:
    return "user" if source_kind in _USER_KINDS else "automated"


def _source_type(source_kind: str, source_ref: str | None) -> str:
    if source_ref and source_ref.startswith("conversation:"):
        return "conversation"
    if source_kind in _USER_KINDS:
        return "user"
    return "automated"


def _supersedes(memory_id: str) -> dict[str, Any] | None:
    """Return the value this memory replaced (the row whose superseded_by points at it)."""
    row = explicit_memory.get_replaced(memory_id, include_inactive=True)
    if row is None:
        return None
    return {
        "id": row["id"],
        "fact": row["text"],
        "source": {"kind": row["source_kind"], "ref": row["source_ref"]},
        "remembered_at": row["created_at"],
    }


def explain(memory_id: str, *, now: datetime | None = None) -> dict[str, Any]:
    """Project one governed memory into the packet's explainable shape.

    Id-addressable and read-only. Raises ``ExplicitMemoryNotFound`` when the row does
    not exist (including inactive rows, so a forgotten/superseded memory still explains).
    """
    row = explicit_memory.get(memory_id, include_inactive=True)
    if row is None:
        raise ExplicitMemoryNotFound(
            f"active explicit memory {memory_id!r} was not found"
        )
    return {
        "id": row["id"],
        "fact": row["text"],
        "namespace": row["namespace"],
        "memory_key": row["memory_key"],
        "source": {
            "kind": row["source_kind"],
            "ref": row["source_ref"],
            "authority": _authority(row["source_kind"]),
        },
        "source_type": _source_type(row["source_kind"], row["source_ref"]),
        "remembered_at": row["created_at"],
        "updated_at": row["updated_at"],
        "truth": {"confidence": row["truth_confidence"], "stable": True},
        "current_state": row["status"],
        "sensitivity": row["sensitivity"],
        "pinned": row["pinned"],
        "supersedes": _supersedes(memory_id),
    }
