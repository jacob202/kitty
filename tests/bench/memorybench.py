from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from gateway import memory_weave
from gateway.memory_weave import MemoryWeave


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    returned_values: tuple[str, ...]
    expected_values: tuple[str, ...]
    forbidden_values: tuple[str, ...]
    reciprocal_rank: float
    hit_at_1: float
    recall_at_k: float
    forbidden_hit: float


def load_cases(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text())
    if payload.get("version") != 1:
        raise ValueError("unsupported MemoryBench fixture version")
    cases = payload.get("cases")
    if not isinstance(cases, list):
        raise ValueError("MemoryBench cases must be a list")
    return cases


def create_weave_db(path: Path) -> None:
    with sqlite3.connect(path) as conn:
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


def _apply_operation(weave: MemoryWeave, op: dict[str, Any]) -> None:
    common = {
        "entity": op["entity"],
        "relation": op["relation"],
        "source": op["source"],
        "source_type": op.get("source_type", "unknown"),
    }
    if op["op"] == "fact":
        weave.fact(
            **common,
            value=op["value"],
            confidence=float(op.get("confidence", 0.5)),
        )
        return
    if op["op"] == "correct":
        weave.correct(**common, new_value=op["value"])
        return
    raise ValueError(f"unknown MemoryBench operation: {op['op']}")


def _value_from_fact(fact: str) -> str:
    _, separator, value = fact.partition(" = ")
    return value if separator else fact


def run_case(case: dict[str, Any], db_path: Path, *, limit: int = 10) -> CaseResult:
    create_weave_db(db_path)
    old_db = memory_weave.KITTY_DB_FILE
    memory_weave.KITTY_DB_FILE = db_path
    memory_weave._weave = None
    try:
        weave = MemoryWeave()
        for operation in case.get("operations", []):
            _apply_operation(weave, operation)
        results = weave.search(case["query"], limit=limit)
    finally:
        memory_weave.KITTY_DB_FILE = old_db
        memory_weave._weave = None

    returned = tuple(_value_from_fact(item.fact) for item in results)
    expected = tuple(case.get("expected_fact_values", []))
    forbidden = tuple(case.get("forbidden_fact_values", []))
    expected_set = set(expected)
    first_relevant_rank = next(
        (index for index, value in enumerate(returned, start=1) if value in expected_set),
        None,
    )
    matched = expected_set.intersection(returned)
    recall = len(matched) / len(expected_set) if expected_set else 1.0
    return CaseResult(
        case_id=case["id"],
        returned_values=returned,
        expected_values=expected,
        forbidden_values=forbidden,
        reciprocal_rank=(1.0 / first_relevant_rank) if first_relevant_rank else 0.0,
        hit_at_1=float(bool(returned and returned[0] in expected_set)) if expected_set else 1.0,
        recall_at_k=recall,
        forbidden_hit=float(any(value in set(forbidden) for value in returned)),
    )


def aggregate(results: list[CaseResult]) -> dict[str, float]:
    if not results:
        return {"hit_at_1": 0.0, "mrr": 0.0, "recall_at_k": 0.0, "forbidden_rate": 0.0}
    count = float(len(results))
    return {
        "hit_at_1": sum(item.hit_at_1 for item in results) / count,
        "mrr": sum(item.reciprocal_rank for item in results) / count,
        "recall_at_k": sum(item.recall_at_k for item in results) / count,
        "forbidden_rate": sum(item.forbidden_hit for item in results) / count,
    }
