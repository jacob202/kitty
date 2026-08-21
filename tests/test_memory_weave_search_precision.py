from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from gateway import memory_weave
from gateway.memory_weave import MemoryWeave


@pytest.fixture
def weave(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> MemoryWeave:
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
    return MemoryWeave()


def test_search_does_not_match_terms_inside_unrelated_words(weave: MemoryWeave):
    weave.fact(
        "transport",
        "kind",
        "automobile",
        "note",
        source_type="document",
        confidence=0.8,
    )

    assert weave.search("mobile phone") == []


def test_search_matches_underscore_separated_relation_words(weave: MemoryWeave):
    weave.fact(
        "project_kitty",
        "canonical_surface",
        "native frontend",
        "ADR 0039",
        source_type="document",
        confidence=0.95,
    )

    results = weave.search("canonical surface")
    assert results
    assert results[0].fact.endswith("= native frontend")
