"""Tests for todo_store — structured task list CRUD."""
import sqlite3

import pytest

from gateway import project_store, todo_store


@pytest.fixture(autouse=True)
def isolate_todo_store(monkeypatch, tmp_path):
    """Keep todo tests away from live user data while proving the Phase B path."""
    phase_b_db = tmp_path / "kitty" / "kitty.db"
    legacy_db = tmp_path / "legacy" / "todos.db"
    monkeypatch.setattr(todo_store, "TODO_DB_FILE", phase_b_db, raising=False)
    monkeypatch.setattr(todo_store, "TODO_DB", legacy_db)
    # Projects and todos share the canonical Kitty DB in production. Keep the
    # isolated test store coherent too so selection-protection checks never
    # touch the real personal database.
    monkeypatch.setattr(project_store, "PROJECTS_DB_FILE", phase_b_db, raising=False)


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


class TestDurableIdentity:
    """A chosen action has to survive the list being regenerated around it."""

    def test_regenerating_the_same_list_keeps_ids_and_progress(self):
        todo_store.clear()
        created = todo_store.update([
            {"content": "Call the pharmacy"},
            {"content": "Book the dentist"},
        ])
        chosen = created[0]["id"]
        todo_store.set_progress(chosen, "left a voicemail, waiting on a callback")
        todo_store.set_project(chosen, 3)

        # The model re-sends the same list without ids, as it does on refresh.
        again = todo_store.update([
            {"content": "Call the pharmacy"},
            {"content": "Book the dentist"},
        ])

        assert [t["id"] for t in again] == [t["id"] for t in created]
        assert again[0]["progress_note"] == "left a voicemail, waiting on a callback"
        assert again[0]["project_id"] == 3
        assert again[0]["created_at"] == created[0]["created_at"]

    def test_an_explicit_id_keeps_identity_through_a_reword(self):
        todo_store.clear()
        created = todo_store.update([{"content": "Call the pharmacy"}])
        chosen = created[0]["id"]
        todo_store.set_progress(chosen, "on hold")

        renamed = todo_store.update([
            {"id": chosen, "content": "Call the pharmacy about the refill"}
        ])

        assert renamed[0]["id"] == chosen
        assert renamed[0]["content"] == "Call the pharmacy about the refill"
        assert renamed[0]["progress_note"] == "on hold"

    def test_new_suggestions_around_a_chosen_item_do_not_replace_it(self):
        todo_store.clear()
        created = todo_store.update([{"content": "Call the pharmacy"}])
        chosen = created[0]["id"]
        todo_store.set_progress(chosen, "left a voicemail")

        regenerated = todo_store.update([
            {"content": "Draft the cover letter"},
            {"content": "Call the pharmacy"},
            {"content": "Tidy the desk"},
        ])

        survivor = next(t for t in regenerated if t["content"] == "Call the pharmacy")
        assert survivor["id"] == chosen
        assert survivor["progress_note"] == "left a voicemail"
        assert survivor["sort_order"] == 1

    def test_an_item_the_caller_dropped_is_removed(self):
        todo_store.clear()
        created = todo_store.update([{"content": "Keep me"}, {"content": "Drop me"}])
        dropped = created[1]["id"]

        remaining = todo_store.update([{"content": "Keep me"}])

        assert [t["content"] for t in remaining] == ["Keep me"]
        assert dropped not in [t["id"] for t in remaining]

    def test_duplicate_content_does_not_collapse_into_one_row(self):
        todo_store.clear()
        created = todo_store.update([{"content": "Follow up"}, {"content": "Follow up"}])
        assert len({t["id"] for t in created}) == 2

        again = todo_store.update([{"content": "Follow up"}, {"content": "Follow up"}])
        assert {t["id"] for t in again} == {t["id"] for t in created}

    def test_an_invented_id_falls_back_to_content_instead_of_erroring(self):
        todo_store.clear()
        created = todo_store.update([{"content": "Call the pharmacy"}])

        again = todo_store.update([{"id": 9999, "content": "Call the pharmacy"}])

        assert again[0]["id"] == created[0]["id"]


class TestProgress:
    def test_progress_records_where_the_user_stopped_without_completing(self):
        todo_store.clear()
        created = todo_store.update([{"content": "Write the letter"}])
        todo_id = created[0]["id"]

        updated = todo_store.set_progress(todo_id, "got through the first paragraph")

        assert updated["progress_note"] == "got through the first paragraph"
        assert updated["status"] == "in_progress"

    def test_progress_does_not_reopen_a_completed_item(self):
        todo_store.clear()
        created = todo_store.update([{"content": "Write the letter"}])
        todo_id = created[0]["id"]
        todo_store.complete_by_id(todo_id)

        assert todo_store.set_progress(todo_id, "actually not done") is None
        assert todo_store.get()[0]["status"] == "completed"

    def test_clearing_a_note_does_not_abandon_the_work(self):
        todo_store.clear()
        created = todo_store.update([{"content": "Write the letter"}])
        todo_id = created[0]["id"]
        todo_store.set_progress(todo_id, "started")

        cleared = todo_store.set_progress(todo_id, "")

        assert cleared["progress_note"] is None
        assert cleared["status"] == "in_progress"

    def test_progress_and_project_on_a_missing_item_report_nothing(self):
        todo_store.clear()
        assert todo_store.set_progress(4242, "note") is None
        assert todo_store.set_project(4242, 1) is None


def test_update_refuses_split_project_store_before_initializing_it(
    monkeypatch, tmp_path
):
    """A redirected Todo store must never initialize the personal Project DB."""
    split_projects = tmp_path / "separate" / "projects.db"
    monkeypatch.setattr(project_store, "PROJECTS_DB_FILE", split_projects, raising=False)
    initialized = False

    def unexpected_init():
        nonlocal initialized
        initialized = True
        raise AssertionError("split project store must not be initialized")

    monkeypatch.setattr(project_store, "init_db", unexpected_init)

    with pytest.raises(todo_store.TodoStoreError, match="separate databases"):
        todo_store.update([{"content": "isolated"}])

    assert initialized is False
    assert not split_projects.exists()
