"""Genuinely read-only detailed KittyBuilder status projection.

The existing :func:`gateway.builder_status.build_status_snapshot` is a runtime/UI
helper and intentionally initializes/migrates Builder schema before reading. MCP
cold starts and external inspection need a stronger contract: inspection must
not create or migrate the durable store. This adapter opens SQLite with
``mode=ro`` + ``query_only`` and reuses Builder's existing projection logic.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from gateway import builder_status as status
from gateway.db import apply_pragmas


def build_status_snapshot_readonly(*, db_path: Path) -> dict[str, Any]:
    """Return the detailed Builder snapshot without creating or mutating storage.

    Missing databases and missing/outdated schema fail loudly. Callers that need
    migrations must use Builder's normal initialization path explicitly instead
    of obtaining that side effect from an inspection request.
    """
    path = Path(db_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"Builder queue database does not exist: {path}")

    uri = f"{path.as_uri()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    apply_pragmas(conn)
    try:
        conn.execute("PRAGMA query_only = ON")
        initiatives = status._build_initiative_projection(conn)
        all_packets = [
            packet
            for initiative in initiatives
            for packet in initiative["packets"]
        ]
        partial_packets = sum(
            packet["data_quality"]["state"] != "complete"
            for packet in all_packets
        )
        return {
            "schema_version": status.SCHEMA_VERSION,
            "attempt_history_limit": status.ATTEMPT_HISTORY_LIMIT,
            "integrity": {
                "state": "partial" if partial_packets else "complete",
                "partial_packets": partial_packets,
                "total_packets": len(all_packets),
            },
            "queue": status._queue_projection(conn),
            "initiatives": initiatives,
        }
    finally:
        conn.close()
