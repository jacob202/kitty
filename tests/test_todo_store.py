"""Tests for todo_store — structured task list CRUD."""
import sqlite3

import pytest

from gateway import todo_store


@pytest.fixture(autouse=True)
def isolate_todo_store(monkeypatch, tmp_path):
    """Keep todo tests away from live user data while proving the Phase B path."""
    phase_b_db = tmp_path / "kitty" / "kitty.db"
    legacy_db = tmp_path / "legacy" / "todos.db"
    monkeypatch.setattr(todo_store, "TODO_DB_FILE", phase_b_db, raising=False)
    monkeypatch.setattr(todo_store, "TODO_DB", legacy_db)


class TestUpdate:
    def test_update_replaces_list(self):
        todo_store.clear()
        items = [
            {
                "content": "First task",
                "status": "in_progress",
                "active_form": "Working on first",
            },
            {"content": "Second task"},
        ]
        result = todo_store.update(items)
        assert len(result) == 2
        assert result[0]["content"] == "First task"
        assert result[0]["status"] == "in_progress"
        assert result[1]["status"] == "pending"

    def test_update_empty_clears(self):
        todo_store.update([{"content": "temp"}])
        result = todo_store.update([])
        assert result == []

    def test_update_preserves_input_order(self):
        todo_store.clear()
        items = [
            {"content": "A"},
            {"content": "B"},
            {"content": "C"},
        ]
        result = todo_store.update(items)
        assert result[0]["content"] == "A"
        assert result[1]["content"] == "B"
        assert result[2]["content"] == "C"


class TestGet:
    def test_get_empty(self):
        todo_store.clear()
        assert todo_store.get() == []

    def test_get_after_update(self):
        todo_store.clear()
        todo_store.update([{"content": "test"}])
        result = todo_store.get()
        assert len(result) == 1
        assert result[0]["content"] == "test"


class TestAdd:
    def test_add_single(self):
        todo_store.clear()
        result = todo_store.add(
            "new task",
            status="pending",
            active_form="Adding task",
        )
        assert result["content"] == "new task"
        assert result["status"] == "pending"
        assert result["active_form"] == "Adding task"

    def test_add_appends_to_end(self):
        todo_store.clear()
        todo_store.update([{"content": "first"}, {"content": "second"}])
        todo_store.add("third")
        result = todo_store.get()
        assert len(result) == 3
        assert result[2]["content"] == "third"


class TestComplete:
    def test_complete_existing(self):
        todo_store.clear()
        todo_store.update([{"content": "task 0"}, {"content": "task 1"}])
        assert todo_store.complete(0) is True
        result = todo_store.get()
        assert result[0]["status"] == "completed"
        assert result[1]["status"] == "pending"

    def test_complete_nonexistent(self):
        todo_store.clear()
        assert todo_store.complete(999) is False


class TestClear:
    def test_clear_removes_all(self):
        todo_store.update([{"content": "a"}, {"content": "b"}])
        todo_store.clear()
        assert todo_store.get() == []


class TestCompleteById:
    def test_complete_by_id_returns_true(self):
        todo_store.clear()
        todo = todo_store.add("task to complete")
        result = todo_store.complete_by_id(todo["id"])
        assert result is True

    def test_complete_by_id_updates_status(self):
        todo_store.clear()
        todo = todo_store.add("finish me")
        todo_store.complete_by_id(todo["id"])
        result = todo_store.get()
        match = next(t for t in result if t["id"] == todo["id"])
        assert match["status"] == "completed"

    def test_complete_by_id_nonexistent(self):
        todo_store.clear()
        assert todo_store.complete_by_id(99999) is False

    def test_complete_by_id_does_not_affect_other_todos(self):
        todo_store.clear()
        a = todo_store.add("keep me")
        b = todo_store.add("complete me")
        todo_store.complete_by_id(b["id"])
        result = todo_store.get()
        a_row = next(t for t in result if t["id"] == a["id"])
        assert a_row["status"] == "pending"


class TestDeleteById:
    def test_delete_by_id_returns_true(self):
        todo_store.clear()
        todo = todo_store.add("to delete")
        result = todo_store.delete_by_id(todo["id"])
        assert result is True

    def test_delete_by_id_removes_row(self):
        todo_store.clear()
        todo = todo_store.add("ephemeral")
        todo_store.delete_by_id(todo["id"])
        result = todo_store.get()
        assert not any(t["id"] == todo["id"] for t in result)

    def test_delete_by_id_nonexistent(self):
        todo_store.clear()
        assert todo_store.delete_by_id(99999) is False

    def test_delete_by_id_does_not_affect_other_todos(self):
        todo_store.clear()
        a = todo_store.add("keep")
        b = todo_store.add("delete")
        todo_store.delete_by_id(b["id"])
        result = todo_store.get()
        assert len(result) == 1
        assert result[0]["id"] == a["id"]


class TestInit:
    def test_init_idempotent(self):
        todo_store.init_db()
        todo_store.init_db()  # should not raise

    def test_init_uses_phase_b_db_not_legacy_todos_db(self):
        todo_store.init_db()

        assert todo_store.TODO_DB_FILE.exists()
        assert not todo_store.TODO_DB.exists()

    def test_imports_legacy_todos_once_without_deleting_file(self):
        todo_store.TODO_DB.parent.mkdir(parents=True)
        with sqlite3.connect(todo_store.TODO_DB) as conn:
            conn.execute("""
                CREATE TABLE todos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    active_form TEXT DEFAULT '',
                    sort_order INTEGER DEFAULT 0,
                    created_at REAL,
                    updated_at REAL
                )
            """)
            conn.execute(
                "INSERT INTO todos "
                "(content, status, active_form, sort_order, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                ("legacy task", "in_progress", "checking seam", 0, 1.0, 2.0),
            )

        assert todo_store.get()[0]["content"] == "legacy task"
        assert todo_store.TODO_DB.exists()

        todo_store.clear()

        assert todo_store.get() == []

    def test_corrupt_legacy_todos_fail_loud(self):
        todo_store.TODO_DB.parent.mkdir(parents=True)
        todo_store.TODO_DB.write_text("not sqlite", encoding="utf-8")

        with pytest.raises(RuntimeError) as exc:
            todo_store.init_db()

        message = str(exc.value)
        assert str(todo_store.TODO_DB) in message
        assert str(todo_store.TODO_DB_FILE) in message
