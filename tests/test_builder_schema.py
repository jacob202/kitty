"""Contract tests for the single Builder schema entry point."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from gateway.builder_schema import ensure_builder_schema

EXPECTED_TABLES = {
    "tasks",
    "events",
    "pr_links",
    "runs",
    "operation_receipts",
    "branch_leases",
    "initiatives",
    "initiative_packets",
    "packet_attempts",
}


def _tables(db_path: Path) -> set[str]:
    conn = sqlite3.connect(db_path)
    try:
        return {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            if not row[0].startswith("sqlite_")
        }
    finally:
        conn.close()


def test_ensure_builder_schema_creates_every_builder_table(tmp_path: Path) -> None:
    db_path = tmp_path / "builder.db"

    ensure_builder_schema(db_path)

    assert EXPECTED_TABLES <= _tables(db_path)


def test_ensure_builder_schema_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "builder.db"

    ensure_builder_schema(db_path)
    before = _tables(db_path)
    ensure_builder_schema(db_path)

    assert _tables(db_path) == before
    assert EXPECTED_TABLES <= before
