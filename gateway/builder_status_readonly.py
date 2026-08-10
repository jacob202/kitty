"""Genuinely read-only detailed KittyBuilder projections.

The existing runtime/UI helpers intentionally initialize/migrate Builder schema
before reading. MCP cold starts and external inspection need a stronger
contract: inspection must not create or migrate the durable store. These helpers
open SQLite with ``mode=ro`` + ``query_only`` and reuse Builder's projection
logic.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from gateway import builder_initiative as initiative
from gateway import builder_status as status
from gateway.db import apply_pragmas


def _readonly_connection(db_path: Path) -> sqlite3.Connection:
    path = Path(db_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"Builder queue database does not exist: {path}")
    uri = f"{path.as_uri()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    apply_pragmas(conn)
    conn.execute("PRAGMA query_only = ON")
    return conn


def build_status_snapshot_readonly(*, db_path: Path) -> dict[str, Any]:
    """Return the detailed Builder snapshot without creating or mutating storage."""
    conn = _readonly_connection(db_path)
    try:
        initiatives = status._build_initiative_projection(conn)
        all_packets = [
            packet
            for item in initiatives
            for packet in item["packets"]
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


def get_initiative_readonly(
    initiative_id: str, *, db_path: Path
) -> dict[str, Any] | None:
    """Return one initiative/manifest without initializing or migrating Builder."""
    conn = _readonly_connection(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM initiatives WHERE id = ?", (initiative_id,)
        ).fetchone()
        if row is None:
            return None
        result = dict(row)
        try:
            result["manifest"] = json.loads(result.pop("manifest_json"))
        except (json.JSONDecodeError, TypeError) as exc:
            raise RuntimeError(
                f"corrupted manifest_json for initiative {initiative_id}: {exc}"
            ) from exc
        packet_rows = conn.execute(
            "SELECT * FROM initiative_packets WHERE initiative_id = ? ORDER BY seq",
            (initiative_id,),
        ).fetchall()
        result["packets"] = [initiative._row_to_packet(item) for item in packet_rows]
        return result
    finally:
        conn.close()
