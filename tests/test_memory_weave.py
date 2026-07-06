"""Tests for gateway/memory_weave.py — port from the salvage.

Covers the 11 public methods of MemoryWeave:
  - fact, correct, event, get_recent_events, query (core CRUD)
  - get_reliability, get_conflicts, surface_conflict (analysis)
  - log_conversation, detect_corrections, get_stale_facts (logging + analysis)

Per-test fixture: point KITTY_DB_FILE at a tmp path so tests don't
touch the real `data/kitty/kitty.db`. The MemoryWeave module reads
its 4 tables (weave_edges, weave_events, weave_reliability_windows,
weave_conversation_logs) from the shared kitty.db (migration 013).
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from gateway import memory_weave
from gateway.memory_weave import (
    MemoryWeave,
    SourceType,
    WeaveEdge,
    WeaveQuery,
    get_weave,
)


@pytest.fixture
def tmp_kitty_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Per-test tmp kitty.db with migration 013 tables. Clears the in-process
    edge cache between tests so order doesn't matter."""
    from gateway import db as kitty_db

    db_file = tmp_path / "kitty.db"
    with kitty_db.connect(db_file) as conn:
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
            CREATE TABLE weave_reliability_windows (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                resource TEXT NOT NULL, reliability TEXT DEFAULT 'unknown',
                window_start TEXT, window_end TEXT,
                failure_count INTEGER DEFAULT 0, success_count INTEGER DEFAULT 0,
                last_updated TEXT
            );
            CREATE TABLE weave_conversation_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL,
                annotated INTEGER DEFAULT 0
            );
            """
        )
        conn.commit()

    monkeypatch.setattr(memory_weave, "KITTY_DB_FILE", db_file)

    # Reset module-level singleton + caches
    memory_weave._weave = None
    yield db_file


# ── Core CRUD ──────────────────────────────────────────────────────────


def test_fact_inserts_and_returns_id(tmp_kitty_db):
    w = MemoryWeave()
    edge_id = w.fact(
        entity="PTH487A",
        relation="resistance",
        value="47Ω",
        source="datasheet pg 23",
        source_type=SourceType.DOCUMENT.value,
        confidence=0.8,
    )
    assert isinstance(edge_id, int) and edge_id > 0

    with sqlite3.connect(tmp_kitty_db) as conn:
        row = conn.execute(
            "SELECT entity, relation, value, source, source_type, confidence "
            "FROM weave_edges WHERE id = ?",
            (edge_id,),
        ).fetchone()
    assert row == ("PTH487A", "resistance", "47Ω", "datasheet pg 23", "document", 0.8)


def test_correct_deprecates_old_and_inserts_new(tmp_kitty_db):
    w = MemoryWeave()
    old_id = w.fact("PTH487A", "resistance", "470Ω", "first guess", confidence=0.3)
    new_id = w.correct(
        "PTH487A", "resistance", "47Ω", "datasheet pg 23",
        reason="measured with multimeter",
    )
    assert new_id != old_id

    with sqlite3.connect(tmp_kitty_db) as conn:
        old = conn.execute(
            "SELECT deprecated, deprecated_reason FROM weave_edges WHERE id = ?",
            (old_id,),
        ).fetchone()
        events = conn.execute(
            "SELECT event_type, description FROM weave_events ORDER BY id"
        ).fetchall()
    assert old == (1, "measured with multimeter")
    assert any("correction" in e[0] for e in events)


def test_event_writes_a_row(tmp_kitty_db):
    w = MemoryWeave()
    w.event(
        "api_timeout", entity="DeepSeek", description="Timeout at 2am",
        severity="warn", metadata={"endpoint": "/v1/chat"},
    )
    with sqlite3.connect(tmp_kitty_db) as conn:
        row = conn.execute(
            "SELECT event_type, entity, description, severity, metadata "
            "FROM weave_events"
        ).fetchone()
    assert row[0] == "api_timeout"
    assert row[1] == "DeepSeek"
    assert row[3] == "warn"
    assert json.loads(row[4]) == {"endpoint": "/v1/chat"}


def test_get_recent_events_filters_by_type_and_window(tmp_kitty_db):
    w = MemoryWeave()
    w.event("api_timeout", "DeepSeek", "fail 1")
    w.event("api_timeout", "DeepSeek", "fail 2")
    w.event("success", "OpenAI", "ok 1")
    only_timeouts = w.get_recent_events(event_type="api_timeout", hours=24)
    assert len(only_timeouts) == 2
    assert all(e["event_type"] == "api_timeout" for e in only_timeouts)


def test_query_returns_best_fact_with_decay(tmp_kitty_db):
    w = MemoryWeave()
    w.fact("Sansui", "transistor", "2SA726", "manual", confidence=0.9)
    w.fact("Sansui", "transistor", "2N3055", "web guess", confidence=0.3)
    q = w.query("Sansui", "transistor")
    assert isinstance(q, WeaveQuery)
    assert q.fact == "Sansui transistor = 2SA726"
    assert q.confidence > 0.3  # user_manual source wins


def test_query_returns_none_when_no_match(tmp_kitty_db):
    w = MemoryWeave()
    assert w.query("nonexistent", "irrelevant") is None


# ── Reliability + conflicts ───────────────────────────────────────────


def test_get_reliability_with_no_events_is_unknown(tmp_kitty_db):
    w = MemoryWeave()
    r = w.get_reliability("DeepSeek")
    assert r == {
        "resource": "DeepSeek",
        "reliability": "unknown",
        "score": 0.5,
        "recent_failures": 0,
        "recent_successes": 0,
        "window": "last 6 hours",
    }


def test_get_reliability_counts_failures_and_successes(tmp_kitty_db):
    w = MemoryWeave()
    w.event("api_failure", "DeepSeek", "fail")
    w.event("api_failure", "DeepSeek", "fail")
    w.event("api_success", "DeepSeek", "ok")
    r = w.get_reliability("DeepSeek")
    assert r["recent_failures"] == 2
    assert r["recent_successes"] == 1
    assert r["reliability"] == "low"  # 33% success


def test_get_conflicts_returns_all_non_deprecated(tmp_kitty_db):
    w = MemoryWeave()
    w.fact("X", "y", "v1", "src1")
    w.fact("X", "y", "v2", "src2")
    conflicts = w.get_conflicts("X", "y")
    assert len(conflicts) == 2
    assert {c.fact for c in conflicts} == {"X y = v1", "X y = v2"}


def test_surface_conflict_signals_no_conflict_when_one_value(tmp_kitty_db):
    w = MemoryWeave()
    w.fact("X", "y", "only", "src1")
    assert w.surface_conflict("X", "y") == {"has_conflict": False}


def test_surface_conflict_returns_best_fact_and_recommendation(tmp_kitty_db):
    w = MemoryWeave()
    w.fact("X", "y", "weak", "web", confidence=0.3)
    w.fact("X", "y", "strong", "manual", confidence=0.95)
    out = w.surface_conflict("X", "y")
    assert out["has_conflict"] is True
    assert len(out["conflicts"]) == 2
    assert out["best_fact"]["fact"] == "X y = strong"


# ── Logging + analysis ───────────────────────────────────────────────


def test_log_conversation_inserts_a_row(tmp_kitty_db):
    w = MemoryWeave()
    w.log_conversation("user", "no, it's 47Ω not 470Ω")
    w.log_conversation("assistant", "Got it, updating the weave.")
    with sqlite3.connect(tmp_kitty_db) as conn:
        rows = conn.execute(
            "SELECT role, content FROM weave_conversation_logs ORDER BY id"
        ).fetchall()
    assert rows[0] == ("user", "no, it's 47Ω not 470Ω")
    assert rows[1][0] == "assistant"


def test_detect_corrections_finds_regex_matches(tmp_kitty_db):
    w = MemoryWeave()
    w.log_conversation("user", "no, actually it's 47Ω")
    w.log_conversation("user", "wrong: 470Ω is not right")
    w.log_conversation("user", "thanks for the help")
    found = w.detect_corrections(hours=24)
    assert len(found) == 2
    assert any("no, actually" in c["content"] for c in found)


def test_get_stale_facts_returns_only_stale(tmp_kitty_db):
    w = MemoryWeave()
    # Fresh fact: just created, last_verified = now
    w.fact("X", "y", "fresh", "src1")
    # Backdate one to make it stale
    with sqlite3.connect(tmp_kitty_db) as conn:
        w.fact("X", "y", "old", "src2")
        conn.execute(
            "UPDATE weave_edges SET last_verified = ? WHERE value = 'old'",
            ((datetime.now() - timedelta(days=60)).isoformat(),),
        )
        conn.commit()
    stale = w.get_stale_facts(days=30)
    assert len(stale) == 1
    assert stale[0].value == "old"


# ── Singleton + module surface ───────────────────────────────────────


def test_get_weave_singleton(tmp_kitty_db, monkeypatch):
    memory_weave._weave = None
    a = get_weave()
    b = get_weave()
    assert a is b


def test_to_dict_round_trips():
    q = WeaveQuery(
        fact="X y = z",
        confidence=0.7,
        last_verified="2026-07-05T00:00:00",
        source_chain=["manual pg 23"],
        related_failures=[],
        is_stale=False,
    )
    d = q.to_dict()
    assert d["fact"] == "X y = z"
    assert d["confidence"] == 0.7
    assert d["source_chain"] == ["manual pg 23"]


def test_weave_edge_age_days():
    e = WeaveEdge(
        id=1, entity="X", relation="y", value="z", confidence=0.5,
        source="s", source_type="unknown",
        timestamp=(datetime.now() - timedelta(days=10)).isoformat(),
    )
    assert 9.9 < e.age_days < 10.1
