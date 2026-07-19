"""Tests for chats_store — keyed-by-id chat session CRUD on kitty.db."""
import json

import pytest

from gateway import chats_store


@pytest.fixture(autouse=True)
def isolate_chats_store(monkeypatch, tmp_path):
    """Keep chats tests away from live user data while exercising the Phase C path."""
    phase_b_db = tmp_path / "kitty" / "kitty.db"
    legacy_json = tmp_path / "kitty" / "chats.json"
    monkeypatch.setattr(chats_store, "CHATS_DB_FILE", phase_b_db, raising=False)
    monkeypatch.setattr(chats_store, "LEGACY_CHATS_FILE", legacy_json, raising=False)


def test_list_chats_empty_when_no_data():
    assert chats_store.list_chats() == []


def test_upsert_then_list_round_trip():
    chat = {"id": "abc", "title": "Hello", "messages": [{"role": "user", "text": "hi"}]}
    chats_store.upsert_chat(chat)

    result = chats_store.list_chats()

    assert result == [chat]


def test_upsert_replaces_existing_chat():
    chats_store.upsert_chat({"id": "abc", "title": "v1"})
    chats_store.upsert_chat({"id": "abc", "title": "v2"})

    result = chats_store.list_chats()

    assert len(result) == 1
    assert result[0]["title"] == "v2"


def test_upsert_requires_id():
    with pytest.raises(ValueError, match="must include 'id'"):
        chats_store.upsert_chat({"title": "no id"})


def test_upsert_preserves_arbitrary_payload_shape():
    chat = {
        "id": "rich",
        "title": "Rich chat",
        "messages": [
            {"role": "user", "text": "hello", "ts": 1234567890},
            {"role": "assistant", "text": "hi", "tool_calls": [{"name": "search"}]},
        ],
        "metadata": {"source": "desktop", "project": "kitty"},
    }
    chats_store.upsert_chat(chat)

    result = chats_store.list_chats()

    assert result[0] == chat


def test_delete_existing_chat_returns_true():
    chats_store.upsert_chat({"id": "abc", "title": "x"})

    deleted = chats_store.delete_chat("abc")

    assert deleted is True
    assert chats_store.list_chats() == []


def test_delete_missing_chat_returns_false():
    deleted = chats_store.delete_chat("never-existed")

    assert deleted is False


def test_list_orders_newest_first():
    chats_store.upsert_chat({"id": "old", "title": "old"})
    chats_store.upsert_chat({"id": "new", "title": "new"})
    chats_store.upsert_chat({"id": "mid", "title": "mid"})

    # Touch "mid" after "new" so mid becomes newest.
    chats_store.upsert_chat({"id": "mid", "title": "mid v2"})

    result = chats_store.list_chats()
    ids = [c["id"] for c in result]

    assert ids == ["mid", "new", "old"]


def test_upsert_supports_unicode_payload():
    chat = {"id": "uni", "title": "こんにちは", "messages": [{"text": "🌙"}]}
    chats_store.upsert_chat(chat)

    result = chats_store.list_chats()

    assert result[0] == chat


class TestLegacyImport:
    """Phase C C4: one-time JSON import for backward compat."""

    def test_imports_existing_json_file_on_first_read(self, tmp_path):
        legacy = tmp_path / "kitty" / "chats.json"
        legacy.parent.mkdir(parents=True, exist_ok=True)
        legacy.write_text(
            json.dumps(
                [
                    {"id": "old1", "title": "from json"},
                    {"id": "old2", "messages": [{"role": "user", "text": "hi"}]},
                ]
            ),
            encoding="utf-8",
        )

        result = chats_store.list_chats()

        assert {c["id"] for c in result} == {"old1", "old2"}

    def test_json_file_never_deleted_after_import(self, tmp_path):
        legacy = tmp_path / "kitty" / "chats.json"
        legacy.parent.mkdir(parents=True, exist_ok=True)
        legacy.write_text(json.dumps([{"id": "x", "title": "stay"}]), encoding="utf-8")

        chats_store.list_chats()

        assert legacy.exists()

    def test_does_not_reimport_on_second_call(self, tmp_path):
        legacy = tmp_path / "kitty" / "chats.json"
        legacy.parent.mkdir(parents=True, exist_ok=True)
        legacy.write_text(json.dumps([{"id": "x", "title": "v1"}]), encoding="utf-8")

        chats_store.list_chats()
        # Mutate the JSON file on disk; second read should NOT pick this up.
        legacy.write_text(json.dumps([{"id": "x", "title": "v2"}]), encoding="utf-8")
        result = chats_store.list_chats()

        assert result[0]["title"] == "v1"

    def test_skips_import_when_table_already_has_data(self, tmp_path):
        chats_store.upsert_chat({"id": "fresh", "title": "from sqlite"})
        legacy = tmp_path / "kitty" / "chats.json"
        legacy.write_text(json.dumps([{"id": "old", "title": "should not import"}]),
                          encoding="utf-8")

        result = chats_store.list_chats()

        assert {c["id"] for c in result} == {"fresh"}

    def test_marks_no_source_when_json_does_not_exist(self, tmp_path):
        # The fixture's legacy path points at a tmp_path file that does not exist.
        result = chats_store.list_chats()

        assert result == []

    def test_patch_objective_sets_and_returns(self):
        """Set an objective via patch_objective and verify it appears in list."""
        chats_store.upsert_chat({"id": "goal", "title": "test"})
        updated = chats_store.patch_objective("goal", "Find the answer")
        assert updated["objective"] == "Find the answer"

        listed = chats_store.list_chats()
        assert listed[0]["objective"] == "Find the answer"

    def test_patch_objective_clears_when_none(self):
        """Clearing also removes an objective supplied in the legacy payload."""
        chats_store.upsert_chat(
            {"id": "goal", "title": "test", "objective": "Find the answer"}
        )
        chats_store.patch_objective("goal", None)

        listed = chats_store.list_chats()
        assert "objective" not in listed[0] or listed[0].get("objective") is None

    def test_patch_objective_raises_on_missing_chat(self):
        """patch_objective on a non-existent chat raises ValueError."""
        with pytest.raises(ValueError, match="does not exist"):
            chats_store.patch_objective("no-such-chat", "anything")

    def test_bad_json_raises_runtime_error(self, tmp_path):
        legacy = tmp_path / "kitty" / "chats.json"
        legacy.parent.mkdir(parents=True, exist_ok=True)
        legacy.write_text("not json", encoding="utf-8")

        with pytest.raises(RuntimeError, match="Legacy chats import failed"):
            chats_store.list_chats()

    def test_rollback_re_imports_from_intact_json(self, tmp_path):
        """Phase C C6: if the chats table is lost, re-import from JSON rebuilds it.

        Documents the escape hatch: drop the table + clear both markers, the
        next read re-runs the migration and the import rebuilds the table from
        the JSON file. The JSON file is the source of truth.
        """
        import sqlite3

        legacy = tmp_path / "kitty" / "chats.json"
        legacy.parent.mkdir(parents=True, exist_ok=True)
        legacy.write_text(
            json.dumps([{"id": "x", "title": "from json"}]), encoding="utf-8"
        )

        # First import populates the table.
        first = chats_store.list_chats()
        assert first == [{"id": "x", "title": "from json"}]

        # Simulate rollback: drop the table, clear the import marker, and
        # clear migration markers so migrate re-applies 004_chats.sql
        # and 020_chat_objective.sql (which adds the objective column back).
        with sqlite3.connect(chats_store.CHATS_DB_FILE) as conn:
            conn.execute("DROP TABLE chats")
            conn.execute(
                "DELETE FROM app_settings WHERE key = ?",
                (chats_store.LEGACY_IMPORT_SETTING,),
            )
            conn.execute(
                "DELETE FROM schema_migrations WHERE name IN ('004_chats.sql', '020_chat_objective.sql')"
            )
            conn.commit()

        # Re-import rebuilds the table from the still-intact JSON file.
        rebuilt = chats_store.list_chats()

        assert rebuilt == [{"id": "x", "title": "from json"}]
