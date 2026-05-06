from __future__ import annotations

import sqlite3

from src.memory.source_ledger import SourceLedger


def test_source_ledger_creates_expected_schema(tmp_path):
    ledger = SourceLedger(tmp_path / "source_ledger.db")

    with sqlite3.connect(ledger.db_path) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }

    assert {"raw_source", "memory_candidates", "memory_promotions", "memory_conflicts"} <= tables


def test_source_lifecycle_and_soft_delete(tmp_path):
    ledger = SourceLedger(tmp_path / "source_ledger.db")

    source = ledger.insert_source(
        source_path="/notes/session.md",
        source_type="file",
        source_timestamp="2026-05-06T12:00:00Z",
        chunk_id="chunk-1",
        snippet_hash="hash-1",
        raw_text="hello source",
        created_at="2026-05-06T12:00:01Z",
    )
    assert source["source_path"] == "/notes/session.md"
    assert source["is_deleted"] == 0

    candidate = ledger.add_candidate(
        raw_source_id=source["id"],
        candidate_text="candidate text",
        confidence=0.25,
        created_at="2026-05-06T12:00:02Z",
    )
    assert candidate["state"] == "candidate"
    assert candidate["confidence"] == 0.25
    assert candidate["source_path"] == source["source_path"]

    quarantined = ledger.quarantine_candidate(
        candidate_id=candidate["id"],
        reason="conflicts with source policy",
        quarantined_at="2026-05-06T12:00:03Z",
    )
    assert quarantined["state"] == "quarantined"
    assert quarantined["quarantine_reason"] == "conflicts with source policy"

    promoted = ledger.promote_candidate(
        candidate_id=candidate["id"],
        promoted_at="2026-05-06T12:00:04Z",
        confidence=0.9,
    )
    assert promoted["state"] == "durable"
    assert promoted["confidence"] == 0.9

    retired = ledger.retire_candidate(
        candidate_id=candidate["id"],
        retired_at="2026-05-06T12:00:05Z",
    )
    assert retired["state"] == "retired"

    soft_deleted = ledger.soft_delete_candidate(
        candidate_id=candidate["id"],
        deleted_at="2026-05-06T12:00:06Z",
    )
    assert soft_deleted["is_deleted"] == 1
    assert soft_deleted["deleted_at"] == "2026-05-06T12:00:06Z"

    deleted_source = ledger.soft_delete_source(
        source_id=source["id"],
        deleted_at="2026-05-06T12:00:07Z",
    )
    assert deleted_source["is_deleted"] == 1
    assert deleted_source["deleted_at"] == "2026-05-06T12:00:07Z"


def test_deterministic_lookup_and_conflict_log(tmp_path):
    ledger = SourceLedger(tmp_path / "source_ledger.db")

    source = ledger.insert_source(
        source_path="/notes/a.md",
        source_type="file",
        source_timestamp="2026-05-06T12:10:00Z",
        chunk_id="chunk-a",
        snippet_hash="hash-a",
        created_at="2026-05-06T12:10:01Z",
    )
    candidate = ledger.add_candidate(
        raw_source_id=source["id"],
        candidate_text="a candidate",
        confidence=0.4,
        created_at="2026-05-06T12:10:02Z",
    )

    ledger.quarantine_candidate(
        candidate_id=candidate["id"],
        reason="needs review",
        quarantined_at="2026-05-06T12:10:03Z",
        notes="manual review",
    )

    with sqlite3.connect(ledger.db_path) as conn:
        conflict_count = conn.execute("SELECT COUNT(*) FROM memory_conflicts").fetchone()[0]
        promotion_count = conn.execute("SELECT COUNT(*) FROM memory_promotions").fetchone()[0]

    assert conflict_count == 1
    assert promotion_count == 1
