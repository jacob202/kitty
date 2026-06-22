"""Tests for journal_store — normalized journal entry CRUD on kitty.db."""
import json
import time

import pytest

from gateway import journal_store


@pytest.fixture(autouse=True)
def isolate_journal_store(monkeypatch, tmp_path):
    """Keep journal tests away from live user data while exercising the Phase C path."""
    phase_b_db = tmp_path / "kitty" / "kitty.db"
    legacy_log = tmp_path / "journal_entries.jsonl"
    monkeypatch.setattr(journal_store, "JOURNAL_DB_FILE", phase_b_db, raising=False)
    monkeypatch.setattr(journal_store, "LEGACY_JOURNAL_LOG", legacy_log, raising=False)


def test_list_entries_empty_when_no_data():
    assert journal_store.list_entries() == []


def test_append_entry_returns_stored_record():
    record = journal_store.append_entry(
        ts=1700000000.0, theme="recovery", entry="slept well"
    )

    assert record["ts"] == 1700000000.0
    assert record["theme"] == "recovery"
    assert record["entry"] == "slept well"
    assert "id" in record
    assert "session_id" not in record


def test_append_entry_includes_session_id_when_provided():
    record = journal_store.append_entry(
        ts=1700000001.0, theme="work", entry="shipped", session_id="abc-123"
    )

    assert record["session_id"] == "abc-123"


def test_list_orders_newest_first():
    journal_store.append_entry(ts=1.0, entry="first")
    journal_store.append_entry(ts=3.0, entry="third")
    journal_store.append_entry(ts=2.0, entry="second")

    result = journal_store.list_entries()

    assert [e["entry"] for e in result] == ["third", "second", "first"]


def test_list_respects_limit():
    for i in range(5):
        journal_store.append_entry(ts=float(i), entry=f"e{i}")

    assert len(journal_store.list_entries(limit=3)) == 3


def test_list_filters_by_theme():
    journal_store.append_entry(ts=1.0, entry="a", theme="work")
    journal_store.append_entry(ts=2.0, entry="b", theme="mood")
    journal_store.append_entry(ts=3.0, entry="c", theme="work")

    result = journal_store.list_entries(theme="work")

    assert [e["entry"] for e in result] == ["c", "a"]


def test_count_total_and_by_theme():
    journal_store.append_entry(ts=1.0, entry="a", theme="work")
    journal_store.append_entry(ts=2.0, entry="b", theme="mood")
    journal_store.append_entry(ts=3.0, entry="c", theme="work")

    assert journal_store.count_entries() == 3
    assert journal_store.count_entries(theme="work") == 2
    assert journal_store.count_entries(theme="mood") == 1
    assert journal_store.count_entries(theme="missing") == 0


def test_list_recent_filters_by_cutoff():
    now = time.time()
    journal_store.append_entry(ts=now, entry="fresh")
    journal_store.append_entry(ts=now - (30 * 86400), entry="stale")

    result = journal_store.list_recent(days=14, limit=10)

    assert [entry["entry"] for entry in result] == ["fresh"]


def test_search_scores_and_limits_results():
    journal_store.append_entry(ts=1.0, entry="quick brown fox")
    journal_store.append_entry(ts=2.0, entry="quick dog")
    journal_store.append_entry(ts=3.0, entry="dog only")

    result = journal_store.search("quick dog", limit=2)

    assert [entry["entry"] for entry in result] == ["quick dog", "dog only"]
    assert result[0]["_score"] == 2


class TestLegacyImport:
    """Phase C B4: one-time JSONL import for backward compat."""

    def test_imports_existing_jsonl_on_first_read(self, tmp_path):
        legacy = tmp_path / "journal_entries.jsonl"
        legacy.parent.mkdir(parents=True, exist_ok=True)
        legacy.write_text(
            "\n".join(
                [
                    json.dumps({"ts": 1.0, "theme": "work", "entry": "one"}),
                    json.dumps(
                        {"ts": 2.0, "theme": "mood", "entry": "two", "session_id": "s1"}
                    ),
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        result = journal_store.list_entries()

        assert {e["entry"] for e in result} == {"one", "two"}

    def test_jsonl_never_deleted_after_import(self, tmp_path):
        legacy = tmp_path / "journal_entries.jsonl"
        legacy.parent.mkdir(parents=True, exist_ok=True)
        legacy.write_text(
            json.dumps({"ts": 1.0, "entry": "stay"}) + "\n", encoding="utf-8"
        )

        journal_store.list_entries()

        assert legacy.exists()

    def test_does_not_reimport_on_second_call(self, tmp_path):
        legacy = tmp_path / "journal_entries.jsonl"
        legacy.parent.mkdir(parents=True, exist_ok=True)
        legacy.write_text(
            json.dumps({"ts": 1.0, "entry": "v1"}) + "\n", encoding="utf-8"
        )

        journal_store.list_entries()
        # Mutate the JSONL file on disk; second read should NOT pick this up.
        legacy.write_text(
            json.dumps({"ts": 2.0, "entry": "v2"}) + "\n", encoding="utf-8"
        )
        result = journal_store.list_entries()

        assert result[0]["entry"] == "v1"

    def test_skips_import_when_table_already_has_data(self, tmp_path):
        journal_store.append_entry(ts=99.0, entry="from sqlite")
        legacy = tmp_path / "journal_entries.jsonl"
        legacy.write_text(
            json.dumps({"ts": 1.0, "entry": "should not import"}) + "\n",
            encoding="utf-8",
        )

        result = journal_store.list_entries()

        assert {e["entry"] for e in result} == {"from sqlite"}

    def test_marks_no_source_when_jsonl_missing(self, tmp_path):
        assert journal_store.list_entries() == []

    def test_bad_jsonl_line_raises_runtime_error(self, tmp_path):
        legacy = tmp_path / "journal_entries.jsonl"
        legacy.parent.mkdir(parents=True, exist_ok=True)
        legacy.write_text("not json\n", encoding="utf-8")

        with pytest.raises(RuntimeError, match="Legacy journal import failed"):
            journal_store.list_entries()

    def test_missing_required_entry_field_raises_runtime_error(self, tmp_path):
        legacy = tmp_path / "journal_entries.jsonl"
        legacy.parent.mkdir(parents=True, exist_ok=True)
        legacy.write_text(
            json.dumps({"ts": 1.0, "theme": "work"}) + "\n",
            encoding="utf-8",
        )

        with pytest.raises(RuntimeError, match="missing required 'entry'"):
            journal_store.list_entries()

    def test_non_numeric_ts_raises_runtime_error(self, tmp_path):
        legacy = tmp_path / "journal_entries.jsonl"
        legacy.parent.mkdir(parents=True, exist_ok=True)
        legacy.write_text(
            json.dumps({"ts": "not-a-number", "entry": "bad ts"}) + "\n",
            encoding="utf-8",
        )

        with pytest.raises(RuntimeError, match="non-numeric 'ts'"):
            journal_store.list_entries()

    def test_rollback_re_imports_from_intact_jsonl(self, tmp_path):
        """Phase C B6: if the journal_entries table is lost, re-import from JSONL rebuilds it.

        Documents the escape hatch: drop the table + clear both markers, the
        next read re-runs the migration and the import rebuilds the table from
        the JSONL file. The JSONL file is the source of truth.
        """
        import sqlite3

        legacy = tmp_path / "journal_entries.jsonl"
        legacy.parent.mkdir(parents=True, exist_ok=True)
        legacy.write_text(
            json.dumps({"ts": 1.0, "theme": "work", "entry": "from jsonl"})
            + "\n",
            encoding="utf-8",
        )

        # First import populates the table.
        first = journal_store.list_entries()
        assert first[0]["entry"] == "from jsonl"

        # Simulate rollback: drop the table, clear the import marker, and
        # clear the migration marker so migrate re-applies 005_journal_entries.sql.
        with sqlite3.connect(journal_store.JOURNAL_DB_FILE) as conn:
            conn.execute("DROP TABLE journal_entries")
            conn.execute(
                "DELETE FROM app_settings WHERE key = ?",
                (journal_store.LEGACY_IMPORT_SETTING,),
            )
            conn.execute(
                "DELETE FROM schema_migrations WHERE name = '005_journal_entries.sql'"
            )
            conn.commit()

        # Re-import rebuilds the table from the still-intact JSONL file.
        rebuilt = journal_store.list_entries()

        assert rebuilt[0]["entry"] == "from jsonl"
