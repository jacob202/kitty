"""Tests for buddy_store — single-row buddy state persistence in kitty.db."""
import json

import pytest

from gateway import buddy_store


@pytest.fixture(autouse=True)
def isolate_buddy_store(monkeypatch, tmp_path):
    """Keep tests away from live user data while exercising the Phase C path."""
    db = tmp_path / "kitty" / "kitty.db"
    legacy_file = tmp_path / "buddy_state.json"
    monkeypatch.setattr(buddy_store, "LEGACY_STATE_FILE", legacy_file, raising=False)
    import gateway.db as kitty_db
    monkeypatch.setattr(kitty_db, "KITTY_DB_FILE", db, raising=False)
    monkeypatch.setattr(buddy_store, "KITTY_DB_FILE", db, raising=False)


# ---------------------------------------------------------------------------
# Basic CRUD
# ---------------------------------------------------------------------------

def test_get_state_returns_defaults_when_empty():
    state = buddy_store.get_state()

    assert state["mood"] == "idle"
    assert state["energy"] == 100
    assert state["session_turns"] == 0
    assert state["total_turns"] == 0
    assert state["last_active_ts"] == 0.0
    assert state["drift_count"] == 0


def test_save_and_get_round_trip():
    buddy_store.save_state({
        "mood": "success",
        "energy": 80,
        "session_turns": 3,
        "total_turns": 42,
        "last_active_ts": 1700000000.0,
        "drift_count": 2,
    })

    result = buddy_store.get_state()

    assert result["mood"] == "success"
    assert result["energy"] == 80
    assert result["session_turns"] == 3
    assert result["total_turns"] == 42
    assert result["last_active_ts"] == 1700000000.0
    assert result["drift_count"] == 2


def test_save_overwrites_previous_state():
    buddy_store.save_state({"mood": "thinking", "energy": 90})
    buddy_store.save_state({"mood": "confused", "energy": 60})

    result = buddy_store.get_state()

    assert result["mood"] == "confused"
    assert result["energy"] == 60


def test_only_one_row_ever_exists():
    buddy_store.save_state({"mood": "thinking"})
    buddy_store.save_state({"mood": "success"})

    import gateway.db as kitty_db
    with kitty_db.connect(buddy_store.KITTY_DB_FILE) as conn:
        count = conn.execute("SELECT COUNT(*) FROM buddy_state").fetchone()[0]

    assert count == 1


# ---------------------------------------------------------------------------
# Legacy import
# ---------------------------------------------------------------------------

class TestLegacyImport:
    def test_imports_from_json_on_first_access(self, tmp_path, monkeypatch):
        legacy_file = tmp_path / "buddy_state.json"
        legacy_file.write_text(json.dumps({
            "mood": "idle",
            "energy": 55,
            "session_turns": 1,
            "total_turns": 100,
            "last_active_ts": 1700000001.0,
            "drift_count": 7,
        }))
        monkeypatch.setattr(buddy_store, "LEGACY_STATE_FILE", legacy_file)

        result = buddy_store.get_state()

        assert result["energy"] == 55
        assert result["total_turns"] == 100
        assert result["drift_count"] == 7

    def test_json_file_not_deleted_after_import(self, tmp_path, monkeypatch):
        legacy_file = tmp_path / "buddy_state.json"
        legacy_file.write_text(json.dumps({"mood": "idle", "energy": 70}))
        monkeypatch.setattr(buddy_store, "LEGACY_STATE_FILE", legacy_file)

        buddy_store.get_state()

        assert legacy_file.exists()

    def test_import_skipped_when_table_already_has_data(self, tmp_path, monkeypatch):
        legacy_file = tmp_path / "buddy_state.json"
        legacy_file.write_text(json.dumps({"mood": "idle", "energy": 99}))
        monkeypatch.setattr(buddy_store, "LEGACY_STATE_FILE", legacy_file)

        buddy_store.save_state({"mood": "success", "energy": 50})
        buddy_store.get_state()  # would trigger import attempt

        result = buddy_store.get_state()
        assert result["energy"] == 50  # live data, not legacy

    def test_import_skipped_when_no_source_file(self):
        result = buddy_store.get_state()

        assert result["mood"] == "idle"  # defaults, no error

    def test_rollback_re_imports_from_intact_json(self, tmp_path, monkeypatch):
        """Escape hatch: dropping the table and marker re-imports from JSON."""
        legacy_file = tmp_path / "buddy_state.json"
        legacy_file.write_text(json.dumps({"mood": "idle", "energy": 77}))
        monkeypatch.setattr(buddy_store, "LEGACY_STATE_FILE", legacy_file)

        buddy_store.get_state()  # initial import

        import gateway.db as kitty_db
        with kitty_db.connect(buddy_store.KITTY_DB_FILE) as conn:
            conn.executescript("""
                DROP TABLE IF EXISTS buddy_state;
                DELETE FROM app_settings WHERE key = 'buddy_state_legacy_imported';
                DELETE FROM schema_migrations WHERE name = '006_buddy_state.sql';
            """)

        result = buddy_store.get_state()
        assert result["energy"] == 77
