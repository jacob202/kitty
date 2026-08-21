"""MemoryBench v1: deterministic baseline for Retrieval V2 (#552).

This intentionally benchmarks the current MemoryWeave search behavior before
changing retrieval. Quality gaps are measured, not hidden behind xfails.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from gateway import memory_weave
from gateway.memory_weave import MemoryWeave

FIXTURE = Path(__file__).parent / "fixtures" / "memory_bench_v1.json"


def _load_cases() -> list[dict]:
    payload = json.loads(FIXTURE.read_text())
    assert payload["version"] == 1
    return payload["cases"]


@pytest.fixture
def bench_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db_file = tmp_path / "kitty.db"
    with sqlite3.connect(db_file) as conn:
        conn.executescript(
            """
            CREATE TABLE weave_edges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity TEXT NOT NULL, relation TEXT NOT NULL, value TEXT NOT NULL,
                confidence REAL DEFAULT 0.5, source TEXT NOT NULL,
                source_type TEXT DEFAULT 'unknown', timestamp TEXT NOT NULL,
                last_verified TEXT, deprecated INTEGER DEFAULT 0,
                deprecated_by INTEGER, deprecated_reason TEXT,
                UNIQUE(entity, relation, source)
            );
            CREATE TABLE weave_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL, entity TEXT, description TEXT NOT NULL,
                severity TEXT DEFAULT 'info', timestamp TEXT NOT NULL, metadata TEXT
            );
            """
        )
    monkeypatch.setattr(memory_weave, "KITTY_DB_FILE", db_file)
    memory_weave._weave = None
    return db_file


def _seed_case(db_file: Path, case: dict) -> dict[str, str]:
    """Insert a case and return fact-string -> logical fixture id."""
    now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    fact_ids: dict[str, str] = {}
    with sqlite3.connect(db_file) as conn:
        conn.execute("DELETE FROM weave_edges")
        conn.execute("DELETE FROM weave_events")
        for fact in case["facts"]:
            conn.execute(
                """
                INSERT INTO weave_edges
                (entity, relation, value, confidence, source, source_type,
                 timestamp, last_verified, deprecated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    fact["entity"], fact["relation"], fact["value"],
                    fact["confidence"], fact["source"], fact["source_type"],
                    now, now, int(fact["deprecated"]),
                ),
            )
            rendered = f"{fact['entity']} {fact['relation']} = {fact['value']}"
            fact_ids[rendered] = fact["id"]
        conn.commit()
    return fact_ids


def _score_case(case: dict, ranked_ids: list[str]) -> dict[str, float | int | bool]:
    expected = case["expected_fact_ids"]
    forbidden = set(case["forbidden_fact_ids"])
    expected_set = set(expected)
    hits = [fact_id for fact_id in ranked_ids if fact_id in expected_set]
    first_rank = next(
        (rank for rank, fact_id in enumerate(ranked_ids, start=1) if fact_id in expected_set),
        None,
    )
    return {
        "expected": len(expected),
        "hits": len(set(hits)),
        "recall": len(set(hits)) / len(expected) if expected else float(not ranked_ids),
        "hit_at_1": bool(ranked_ids and ranked_ids[0] in expected_set) if expected else not ranked_ids,
        "rr": 1.0 / first_rank if first_rank else (1.0 if not expected and not ranked_ids else 0.0),
        "forbidden_hits": sum(fact_id in forbidden for fact_id in ranked_ids),
    }


def test_memory_bench_fixture_contract() -> None:
    cases = _load_cases()
    assert len(cases) >= 8
    assert len({case["id"] for case in cases}) == len(cases)
    for case in cases:
        assert case["query"].strip()
        assert isinstance(case["expected_fact_ids"], list)
        assert isinstance(case["forbidden_fact_ids"], list)
        known = {fact["id"] for fact in case["facts"]}
        assert set(case["expected_fact_ids"]) <= known
        assert set(case["forbidden_fact_ids"]) <= known


def test_memory_weave_search_baseline_is_measured(bench_db: Path) -> None:
    """Pin safety invariants and expose quality headroom for Retrieval V2.

    We deliberately do not require perfect recall: v1's contradiction case
    documents that the current entity/relation collapse returns one of two
    valid active facts. A challenger must improve aggregate recall without
    regressing forbidden-fact safety.
    """
    case_scores = []
    for case in _load_cases():
        mapping = _seed_case(bench_db, case)
        weave = MemoryWeave()
        results = weave.search(case["query"], limit=case.get("limit", 10))
        ranked_ids = [mapping[result.fact] for result in results if result.fact in mapping]
        score = _score_case(case, ranked_ids)
        case_scores.append((case["id"], score))

    total_expected = sum(score["expected"] for _, score in case_scores)
    total_hits = sum(score["hits"] for _, score in case_scores)
    recall = total_hits / total_expected
    mean_rr = sum(float(score["rr"]) for _, score in case_scores) / len(case_scores)

    # Safety baseline: deprecated/forbidden facts must never surface.
    assert sum(score["forbidden_hits"] for _, score in case_scores) == 0
    # Current keyword search should remain meaningfully functional while the
    # benchmark leaves room for Retrieval V2 to prove an actual improvement.
    assert recall >= 0.80
    assert mean_rr >= 0.80

    contradiction = dict(case_scores)["contradiction_preserved"]
    assert contradiction["recall"] == 0.5


def test_memory_bench_metric_math() -> None:
    score = _score_case(
        {"expected_fact_ids": ["a", "b"], "forbidden_fact_ids": ["x"]},
        ["x", "b", "other"],
    )
    assert score["recall"] == 0.5
    assert score["hit_at_1"] is False
    assert score["rr"] == 0.5
    assert score["forbidden_hits"] == 1
