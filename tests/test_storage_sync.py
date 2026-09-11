"""Tests for the JSON import/export round-trip (Lane C).

Every store that goes through the storage_sync module should be able to
be exported to a JSON snapshot, the SQLite state cleared, and the
data restored from the snapshot with no loss. These tests use the real
SQLite stores and an explicit Mem0 test backend to catch schema drift early.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from gateway import db as kitty_db
from gateway import (
    journal_store,
    memory,
    plugin_registry,
    project_store,
    storage_sync,
    todo_store,
)


@pytest.fixture(autouse=True)
def isolate_memory_backend(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Keep storage-sync tests independent of the live Mem0/Ollama stack."""
    backend = MagicMock()
    backend.get_all.return_value = {"results": []}
    monkeypatch.setattr(memory, "_get_memory", lambda: backend)
    return backend


def _isolate(tmp_path, monkeypatch, name):
    db_file = tmp_path / f"{name}.db"
    monkeypatch.setattr(kitty_db, "KITTY_DB_FILE", db_file)
    monkeypatch.setattr(todo_store, "TODO_DB_FILE", db_file, raising=False)
    monkeypatch.setattr(project_store, "PROJECTS_DB_FILE", db_file, raising=False)
    return db_file


def _add_next_step(project_id, step):
    """Give a project a foreign-key-dependent row that a restore must respect."""
    with kitty_db.connect(project_store.PROJECTS_DB_FILE) as conn:
        conn.execute(
            "INSERT INTO project_next_steps "
            "(project_id, step, why, recent_win, delegable, generated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (project_id, step, "why", "", 0, 1.0),
        )
        conn.commit()


def _isolate_plugin(tmp_path, monkeypatch):
    db_file = tmp_path / "plugins.db"
    monkeypatch.setattr(plugin_registry, "PLUGIN_DB_FILE", db_file)
    monkeypatch.setattr(plugin_registry, "PLUGIN_SETTINGS", tmp_path / "plugin_settings.json")
    plugin_registry.reset()
    return db_file


def test_export_all_returns_expected_top_level_shape(tmp_path, monkeypatch):
    _isolate_plugin(tmp_path, monkeypatch)
    _isolate(tmp_path, monkeypatch, "todo")

    snapshot = storage_sync.export_all()

    assert snapshot["format_version"] == storage_sync.FORMAT_VERSION
    assert "exported_at" in snapshot
    assert set(snapshot["stores"]) >= {"plugin_settings", "todos"}
    assert "memories" in snapshot["stores"]
    assert "journal_entries" in snapshot["stores"]
    assert "preferences" in snapshot["stores"]


def test_export_all_surfaces_memory_backend_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def unavailable():
        raise memory.MemoryError("memory export unavailable")

    monkeypatch.setattr(memory, "_get_memory", unavailable)

    with pytest.raises(memory.MemoryError, match="memory export unavailable"):
        storage_sync.export_all()


def test_export_includes_real_plugin_settings_and_todos(tmp_path, monkeypatch):
    _isolate_plugin(tmp_path, monkeypatch)
    _isolate(tmp_path, monkeypatch, "todo")

    plugin_registry.register("alpha", default_enabled=True)
    plugin_registry.register("beta", default_enabled=False)
    plugin_registry.enable("alpha")
    plugin_registry.disable("beta")
    todo_store.update(
        [
            {"content": "first todo", "status": "pending", "active_form": ""},
            {"content": "second todo", "status": "completed", "active_form": ""},
        ]
    )

    snapshot = storage_sync.export_all()
    assert snapshot["stores"]["plugin_settings"] == {"alpha": True, "beta": False}
    assert {t["content"] for t in snapshot["stores"]["todos"]} == {"first todo", "second todo"}


def test_export_reads_projects_and_todos_as_one_snapshot(tmp_path, monkeypatch):
    """A change between the two reads must not produce a torn snapshot.

    A project's `selected_todo_id` and a todo's owning `project_id` are one
    cross-table state. Reading each through its own connection can capture a
    selection that landed between the reads, exporting a state that never
    existed — and importing it would restore without the user's chosen action.
    """
    _isolate_plugin(tmp_path, monkeypatch)
    db_file = _isolate(tmp_path, monkeypatch, "todo")
    project_store.init_db()
    project = project_store.create(name="job-search", kind="admin")
    todo = todo_store.update([{"content": "Chosen next action", "status": "pending"}])[0]
    todo_store.set_project(todo["id"], project["id"])
    project_store.select_todo(project["id"], todo["id"])

    original_mapper = project_store._row_to_project
    mutated = {"done": False}

    def _mapper(row):
        mapped = original_mapper(row)
        if not mutated["done"]:
            mutated["done"] = True
            # Lands after the projects read and before the todos read.
            with kitty_db.connect(db_file) as conn:
                conn.execute(
                    "UPDATE projects SET selected_todo_id = NULL WHERE id = ?",
                    (project["id"],),
                )
                conn.execute(
                    "UPDATE todos SET project_id = NULL WHERE id = ?", (todo["id"],)
                )
                conn.commit()
        return mapped

    monkeypatch.setattr(project_store, "_row_to_project", _mapper)

    snapshot = storage_sync.export_all()

    assert mutated["done"] is True
    exported_project = next(
        row for row in snapshot["stores"]["projects"] if row["id"] == project["id"]
    )
    exported_todo = next(
        row for row in snapshot["stores"]["todos"] if row["id"] == todo["id"]
    )
    assert exported_project["selected_todo_id"] == todo["id"]
    assert exported_todo["project_id"] == project["id"]


def test_round_trip_preserves_plugin_settings(tmp_path, monkeypatch):
    _isolate_plugin(tmp_path, monkeypatch)
    _isolate(tmp_path, monkeypatch, "todo")
    plugin_registry.register("alpha", default_enabled=True)
    plugin_registry.register("beta", default_enabled=False)
    plugin_registry.enable("alpha")
    plugin_registry.disable("beta")

    snapshot = storage_sync.export_all()
    plugin_registry.reset()
    assert plugin_registry._load_db_settings() == {}

    counts = storage_sync.import_all(snapshot)
    assert counts["plugin_settings"] == 2
    assert plugin_registry._load_db_settings() == {"alpha": True, "beta": False}


def test_round_trip_preserves_todos(tmp_path, monkeypatch):
    _isolate_plugin(tmp_path, monkeypatch)
    _isolate(tmp_path, monkeypatch, "todo")
    todo_store.update(
        [
            {"content": "x", "status": "pending", "active_form": "x-form"},
            {"content": "y", "status": "completed", "active_form": ""},
        ]
    )

    snapshot = storage_sync.export_all()
    todo_store.clear()
    assert todo_store.get() == []

    counts = storage_sync.import_all(snapshot)
    assert counts["todos"] == 2
    restored = todo_store.get()
    assert {t["content"] for t in restored} == {"x", "y"}


def test_round_trip_restores_user_project_owned_todo_into_fresh_database(
    tmp_path, monkeypatch
):
    """A todo owned by a user-created project survives export -> fresh restore.

    `projects` used to be absent from the snapshot while `todo_store.restore`
    rejects any todo whose owner is missing from the destination, so a valid
    snapshot aborted the entire todo restore into a rebuilt database.
    """
    _isolate_plugin(tmp_path, monkeypatch)
    db_file = _isolate(tmp_path, monkeypatch, "todo")
    project_store.init_db()
    seed_ids = {project["id"] for project in project_store.list_projects()}

    project = project_store.create(name="job-search", kind="admin")
    assert project["id"] not in seed_ids
    todo = todo_store.update([{"content": "Chosen next action", "status": "pending"}])[0]
    todo_store.set_project(todo["id"], project["id"])
    project_store.select_todo(project["id"], todo["id"])
    todo_store.set_progress(todo["id"], "halfway")

    snapshot = storage_sync.export_all()
    assert "projects" in snapshot["stores"]
    assert snapshot["stores"]["todos"][0]["project_id"] == project["id"]

    # Rebuild the database from scratch: only the seeded projects exist.
    db_file.unlink()
    kitty_db.migrate(db_file=db_file)
    project_store.init_db()
    assert project["id"] not in {p["id"] for p in project_store.list_projects()}

    counts = storage_sync.import_all(snapshot)

    assert counts["projects"] == len(snapshot["stores"]["projects"])
    restored_project = project_store.get(project["id"])
    assert restored_project is not None
    assert restored_project["name"] == "job-search"
    assert restored_project["selected_todo_id"] == todo["id"]

    rows = todo_store.get()
    assert [row["id"] for row in rows] == [todo["id"]]
    assert rows[0]["project_id"] == project["id"]
    assert rows[0]["progress_note"] == "halfway"
    assert project_store.selected_todo(project["id"])["id"] == todo["id"]


def test_self_restore_preserves_existing_project_foreign_key_dependents(
    tmp_path, monkeypatch
):
    """Restoring an exported project must not delete/reinsert its referenced parent row."""
    _isolate_plugin(tmp_path, monkeypatch)
    db_file = _isolate(tmp_path, monkeypatch, "todo")
    project_store.init_db()
    project = project_store.create(name="job-search", kind="admin")
    with kitty_db.connect(db_file) as conn:
        conn.execute(
            "INSERT INTO project_next_steps "
            "(project_id, step, why, recent_win, delegable, generated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (project["id"], "Apply", "important", "", 0, 1.0),
        )
        conn.commit()

    snapshot = storage_sync.export_all()
    counts = storage_sync.import_all(snapshot)

    assert counts["projects"] == len(snapshot["stores"]["projects"])
    with kitty_db.connect(db_file) as conn:
        row = conn.execute(
            "SELECT step FROM project_next_steps WHERE project_id = ?",
            (project["id"],),
        ).fetchone()
    assert row is not None
    assert row["step"] == "Apply"


def test_import_rejects_malformed_todo_project_owner_before_writing_stores(
    tmp_path, monkeypatch
):
    _isolate_plugin(tmp_path, monkeypatch)
    _isolate(tmp_path, monkeypatch, "todo")
    project_store.init_db()
    project = project_store.create(name="keep-me", kind="admin")
    todo_store.update([{"content": "Keep current state"}])
    before_projects = project_store.list_projects()
    before_todos = todo_store.get()

    snapshot = storage_sync.export_all()
    snapshot["stores"]["projects"] = [
        {**row, "name": "would-have-been-written"}
        for row in snapshot["stores"]["projects"]
    ]
    snapshot["stores"]["todos"] = [
        {"content": "corrupt owner", "sort_order": 0, "project_id": str(project["id"])}
    ]

    with pytest.raises(ValueError, match="project_id.*integer or null"):
        storage_sync.import_all(snapshot)

    assert project_store.list_projects() == before_projects
    assert todo_store.get() == before_todos


def test_import_rejects_duplicate_todo_sort_orders_before_writing_any_store(
    tmp_path, monkeypatch
):
    """A failing todo payload must not leave earlier stores committed.

    `import_all` restores projects before todos, so a snapshot whose todos
    cannot be restored has to be rejected before any store is written.
    """
    _isolate_plugin(tmp_path, monkeypatch)
    _isolate(tmp_path, monkeypatch, "todo")
    project_store.init_db()
    todo_store.update([{"content": "Keep current state"}])
    before_projects = project_store.list_projects()
    before_todos = todo_store.get()

    snapshot = storage_sync.export_all()
    snapshot["stores"]["projects"] = [
        {**row, "name": "would-have-been-written"}
        for row in snapshot["stores"]["projects"]
    ]
    snapshot["stores"]["todos"] = [
        {"content": "first", "sort_order": 3},
        {"content": "second", "sort_order": 3},
    ]

    with pytest.raises(ValueError, match="duplicate sort_order 3"):
        storage_sync.import_all(snapshot)

    assert project_store.list_projects() == before_projects
    assert todo_store.get() == before_todos


def test_import_rejects_non_integer_todo_id_before_writing_stores(
    tmp_path, monkeypatch
):
    """A non-integer todo id must fail loud, never be silently reallocated."""
    _isolate_plugin(tmp_path, monkeypatch)
    _isolate(tmp_path, monkeypatch, "todo")
    project_store.init_db()
    project = project_store.create(name="job-search", kind="admin")
    todo = todo_store.update([{"content": "Chosen next action", "status": "pending"}])[0]
    todo_store.set_project(todo["id"], project["id"])
    project_store.select_todo(project["id"], todo["id"])
    before_projects = project_store.list_projects()
    before_todos = todo_store.get()

    snapshot = storage_sync.export_all()
    snapshot["stores"]["projects"] = [
        {**row, "name": "would-have-been-written"}
        for row in snapshot["stores"]["projects"]
    ]
    snapshot["stores"]["todos"] = [
        {**row, "id": str(row["id"])} for row in snapshot["stores"]["todos"]
    ]

    with pytest.raises(ValueError, match="todo id must be an integer or null"):
        storage_sync.import_all(snapshot)

    assert project_store.list_projects() == before_projects
    assert todo_store.get() == before_todos
    assert project_store.get(project["id"])["selected_todo_id"] == todo["id"]


def test_import_rejects_referenced_omitted_project_before_writing_earlier_stores(
    tmp_path, monkeypatch
):
    """A project that cannot be removed must be caught before Memories/Journal.

    Restoring an older snapshot after a newer project acquired a dependent row
    hits foreign-key enforcement. Projects restore after Memories and Journal,
    so that failure must be found up front or those stores are left partially
    imported.
    """
    _isolate_plugin(tmp_path, monkeypatch)
    _isolate(tmp_path, monkeypatch, "todo")
    project_store.init_db()
    kept = project_store.create(name="kept", kind="admin")
    _add_next_step(kept["id"], "kept-step")
    # The snapshot carries a journal entry so the importer ordered before
    # Projects has something it would commit before hitting the failure.
    journal_store.append_entry(ts=1.0, entry="snapshot entry", theme=None, session_id=None)
    snapshot = storage_sync.export_all()

    newer = project_store.create(name="newer", kind="admin")
    _add_next_step(newer["id"], "newer-step")
    with kitty_db.connect(journal_store.JOURNAL_DB_FILE) as conn:
        conn.execute("DELETE FROM journal_entries")
        conn.commit()
    before_projects = project_store.list_projects()

    with pytest.raises(ValueError, match="still referenced"):
        storage_sync.import_all(snapshot)

    # Nothing may survive a rejected snapshot, including the store imported
    # ahead of Projects.
    assert journal_store.list_entries(limit=100) == []
    assert project_store.list_projects() == before_projects


def test_import_rejects_v1_todo_owner_absent_from_destination_before_writing(
    tmp_path, monkeypatch
):
    """A v1 snapshot has no projects store, so its owners need a destination check.

    Without it `todo_store.restore` is the first to notice the unknown owner —
    after Memories and Journal have already been imported.
    """
    _isolate_plugin(tmp_path, monkeypatch)
    _isolate(tmp_path, monkeypatch, "todo")
    project_store.init_db()
    journal_store.append_entry(ts=1.0, entry="snapshot entry", theme=None, session_id=None)
    snapshot = storage_sync.export_all()
    snapshot["format_version"] = 1
    del snapshot["stores"]["projects"]
    snapshot["stores"]["todos"] = [
        {"content": "orphan v1 todo", "sort_order": 0, "project_id": 999999}
    ]
    with kitty_db.connect(journal_store.JOURNAL_DB_FILE) as conn:
        conn.execute("DELETE FROM journal_entries")
        conn.commit()

    with pytest.raises(ValueError, match="absent from the destination"):
        storage_sync.import_all(snapshot)

    assert journal_store.list_entries(limit=100) == []
    assert todo_store.get() == []


def test_import_accepts_a_v1_snapshot_whose_owner_exists_on_the_destination(
    tmp_path, monkeypatch
):
    """The destination check must keep a legitimate v1 owner importable."""
    _isolate_plugin(tmp_path, monkeypatch)
    _isolate(tmp_path, monkeypatch, "todo")
    project_store.init_db()
    project = project_store.create(name="job-search", kind="admin")
    todo = todo_store.update([{"content": "Chosen next action", "status": "pending"}])[0]
    todo_store.set_project(todo["id"], project["id"])

    snapshot = storage_sync.export_all()
    snapshot["format_version"] = 1
    del snapshot["stores"]["projects"]
    todo_store.clear()

    counts = storage_sync.import_all(snapshot)

    assert counts["todos"] == 1
    restored = todo_store.get()
    assert [row["project_id"] for row in restored] == [project["id"]]


def test_import_rejects_malformed_project_selected_todo_id_before_writing(
    tmp_path, monkeypatch
):
    """A non-integer selected_todo_id must fail loud, not be silently cleared."""
    _isolate_plugin(tmp_path, monkeypatch)
    _isolate(tmp_path, monkeypatch, "todo")
    project_store.init_db()
    project = project_store.create(name="job-search", kind="admin")
    todo = todo_store.update([{"content": "Chosen next action", "status": "pending"}])[0]
    todo_store.set_project(todo["id"], project["id"])
    project_store.select_todo(project["id"], todo["id"])
    before_projects = project_store.list_projects()
    before_todos = todo_store.get()

    snapshot = storage_sync.export_all()
    snapshot["stores"]["projects"] = [
        {**row, "selected_todo_id": "not-an-id"} if row["id"] == project["id"] else row
        for row in snapshot["stores"]["projects"]
    ]

    with pytest.raises(ValueError, match="selected_todo_id must be an integer or null"):
        storage_sync.import_all(snapshot)

    assert project_store.list_projects() == before_projects
    assert todo_store.get() == before_todos


def test_import_rejects_wrongly_shaped_later_store_before_writing_earlier_ones(
    tmp_path, monkeypatch
):
    """A late store's payload shape must not decide after earlier stores commit."""
    _isolate_plugin(tmp_path, monkeypatch)
    _isolate(tmp_path, monkeypatch, "todo")
    project_store.init_db()
    todo_store.update([{"content": "Keep current state"}])
    before_projects = project_store.list_projects()
    before_todos = todo_store.get()

    snapshot = storage_sync.export_all()
    snapshot["stores"]["projects"] = [
        {**row, "name": "would-have-been-written"}
        for row in snapshot["stores"]["projects"]
    ]
    snapshot["stores"]["todos"] = [{"content": "would-have-been-written", "sort_order": 0}]
    snapshot["stores"]["plugin_settings"] = "not-a-dict"

    with pytest.raises(ValueError, match="plugin_settings payload must be a dict"):
        storage_sync.import_all(snapshot)

    assert project_store.list_projects() == before_projects
    assert todo_store.get() == before_todos


def test_import_rejects_snapshot_todo_with_owner_absent_from_snapshot(
    tmp_path, monkeypatch
):
    """An internally inconsistent snapshot fails before any store is written."""
    _isolate_plugin(tmp_path, monkeypatch)
    _isolate(tmp_path, monkeypatch, "todo")
    todo_store.update([{"content": "Keep current state"}])
    before = todo_store.get()

    snapshot = storage_sync.export_all()
    snapshot["stores"]["todos"] = [
        {"content": "Orphaned snapshot todo", "sort_order": 0, "project_id": 999999}
    ]

    with pytest.raises(ValueError, match="absent from snapshot projects"):
        storage_sync.import_all(snapshot)

    assert todo_store.get() == before


def test_snapshot_import_replaces_omitted_selected_todo_and_clears_dangling_pointer(
    tmp_path, monkeypatch
):
    """Snapshot restore is exact replacement, not generated-list reconciliation."""
    _isolate_plugin(tmp_path, monkeypatch)
    _isolate(tmp_path, monkeypatch, "todo")
    project_store.init_db()
    project = project_store.create(name="job-search", kind="admin")
    current = todo_store.update(
        [
            {"content": "Chosen current action"},
            {"content": "Also current"},
        ]
    )
    project_store.select_todo(project["id"], current[0]["id"])

    # Restoring an older snapshot that does not contain the currently selected
    # row must not smuggle that newer row into the restored state.
    storage_sync.import_todos(
        [
            {
                "id": 9001,
                "content": "Only snapshot todo",
                "status": "pending",
                "active_form": "",
                "sort_order": 0,
                "progress_note": None,
                "project_id": None,
                "created_at": 10.0,
                "updated_at": 11.0,
            }
        ]
    )

    restored = todo_store.get()
    assert [row["content"] for row in restored] == ["Only snapshot todo"]
    assert project_store.get(project["id"])["selected_todo_id"] is None


def test_snapshot_import_rejects_duplicate_sort_orders_before_replacing_todos(
    tmp_path, monkeypatch
):
    _isolate_plugin(tmp_path, monkeypatch)
    _isolate(tmp_path, monkeypatch, "todo")
    todo_store.update([{"content": "Keep current state"}])
    before = todo_store.get()

    with pytest.raises(todo_store.TodoStoreError, match="duplicate sort_order 4"):
        storage_sync.import_todos(
            [
                {"content": "First snapshot todo", "sort_order": 4},
                {"content": "Second snapshot todo", "sort_order": 4},
            ]
        )

    assert todo_store.get() == before


def test_snapshot_import_rejects_missing_project_owner_before_replacing_todos(
    tmp_path, monkeypatch
):
    _isolate_plugin(tmp_path, monkeypatch)
    _isolate(tmp_path, monkeypatch, "todo")
    todo_store.update([{"content": "Keep current state"}])
    before = todo_store.get()
    missing_project_id = (
        max(project["id"] for project in project_store.list_projects()) + 100
    )

    with pytest.raises(
        todo_store.TodoStoreError,
        match=rf"unknown project_id.*{missing_project_id}",
    ):
        storage_sync.import_todos(
            [
                {
                    "content": "Snapshot todo with a missing owner",
                    "sort_order": 0,
                    "project_id": missing_project_id,
                }
            ]
        )

    assert todo_store.get() == before


def test_import_rejects_unknown_format_version():
    with pytest.raises(ValueError, match="format_version"):
        storage_sync.import_all({"format_version": 999, "stores": {}})


def test_import_accepts_an_older_snapshot_without_a_projects_store(
    tmp_path, monkeypatch
):
    """A pre-`projects` backup must stay restorable after the format bump."""
    _isolate_plugin(tmp_path, monkeypatch)
    _isolate(tmp_path, monkeypatch, "todo")
    todo_store.update([{"content": "Backed-up todo", "status": "pending"}])

    snapshot = storage_sync.export_all()
    snapshot["format_version"] = 1
    del snapshot["stores"]["projects"]
    todo_store.clear()

    counts = storage_sync.import_all(snapshot)

    assert "projects" not in counts
    assert counts["todos"] == 1
    assert [row["content"] for row in todo_store.get()] == ["Backed-up todo"]


def test_import_rejects_missing_stores_key():
    with pytest.raises(ValueError, match="snapshot.stores"):
        storage_sync.import_all({"format_version": storage_sync.FORMAT_VERSION})


def test_import_rejects_unknown_store_keys(tmp_path, monkeypatch):
    _isolate_plugin(tmp_path, monkeypatch)
    _isolate(tmp_path, monkeypatch, "todo")
    snapshot = storage_sync.export_all()
    snapshot["stores"]["never_existed"] = "wat"

    with pytest.raises(ValueError, match="never_existed"):
        storage_sync.import_all(snapshot)


def test_import_rejects_wrong_payload_shape(tmp_path, monkeypatch):
    _isolate_plugin(tmp_path, monkeypatch)
    _isolate(tmp_path, monkeypatch, "todo")
    snapshot = storage_sync.export_all()
    snapshot["stores"]["plugin_settings"] = "not-a-dict"
    snapshot["stores"]["todos"] = "not-a-list"

    with pytest.raises(ValueError):
        storage_sync.import_all(snapshot)


def test_export_to_file_and_import_from_file_round_trip(tmp_path, monkeypatch):
    _isolate_plugin(tmp_path, monkeypatch)
    _isolate(tmp_path, monkeypatch, "todo")
    plugin_registry.register("alpha", default_enabled=True)
    plugin_registry.enable("alpha")
    todo_store.update([{"content": "z", "status": "pending", "active_form": ""}])

    target = tmp_path / "snapshot.json"
    out = storage_sync.export_to_file(target)
    assert out == target
    assert (
        json.loads(target.read_text(encoding="utf-8"))["format_version"]
        == storage_sync.FORMAT_VERSION
    )

    plugin_registry.reset()
    todo_store.clear()
    assert plugin_registry._load_db_settings() == {}
    assert todo_store.get() == []

    counts = storage_sync.import_from_file(target)
    assert counts["plugin_settings"] == 1
    assert counts["todos"] == 1
    assert plugin_registry._load_db_settings() == {"alpha": True}
    assert todo_store.get()[0]["content"] == "z"
