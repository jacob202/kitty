"""Tests for todo_store — structured task list CRUD."""
import pytest
from gateway.todo_store import update, get, add, complete, clear, init_db, complete_by_id, delete_by_id


class TestUpdate:
    def test_update_replaces_list(self):
        clear()
        items = [
            {"content": "First task", "status": "in_progress", "active_form": "Working on first"},
            {"content": "Second task"},
        ]
        result = update(items)
        assert len(result) == 2
        assert result[0]["content"] == "First task"
        assert result[0]["status"] == "in_progress"
        assert result[1]["status"] == "pending"

    def test_update_empty_clears(self):
        update([{"content": "temp"}])
        result = update([])
        assert result == []

    def test_update_preserves_input_order(self):
        clear()
        items = [
            {"content": "A"},
            {"content": "B"},
            {"content": "C"},
        ]
        result = update(items)
        assert result[0]["content"] == "A"
        assert result[1]["content"] == "B"
        assert result[2]["content"] == "C"


class TestGet:
    def test_get_empty(self):
        clear()
        assert get() == []

    def test_get_after_update(self):
        clear()
        update([{"content": "test"}])
        result = get()
        assert len(result) == 1
        assert result[0]["content"] == "test"


class TestAdd:
    def test_add_single(self):
        clear()
        result = add("new task", status="pending", active_form="Adding task")
        assert result["content"] == "new task"
        assert result["status"] == "pending"
        assert result["active_form"] == "Adding task"

    def test_add_appends_to_end(self):
        clear()
        update([{"content": "first"}, {"content": "second"}])
        add("third")
        result = get()
        assert len(result) == 3
        assert result[2]["content"] == "third"


class TestComplete:
    def test_complete_existing(self):
        clear()
        update([{"content": "task 0"}, {"content": "task 1"}])
        assert complete(0) is True
        result = get()
        assert result[0]["status"] == "completed"
        assert result[1]["status"] == "pending"

    def test_complete_nonexistent(self):
        clear()
        assert complete(999) is False


class TestClear:
    def test_clear_removes_all(self):
        update([{"content": "a"}, {"content": "b"}])
        clear()
        assert get() == []


class TestCompleteById:
    def test_complete_by_id_returns_true(self):
        clear()
        todo = add("task to complete")
        result = complete_by_id(todo["id"])
        assert result is True

    def test_complete_by_id_updates_status(self):
        clear()
        todo = add("finish me")
        complete_by_id(todo["id"])
        result = get()
        match = next(t for t in result if t["id"] == todo["id"])
        assert match["status"] == "completed"

    def test_complete_by_id_nonexistent(self):
        clear()
        assert complete_by_id(99999) is False

    def test_complete_by_id_does_not_affect_other_todos(self):
        clear()
        a = add("keep me")
        b = add("complete me")
        complete_by_id(b["id"])
        result = get()
        a_row = next(t for t in result if t["id"] == a["id"])
        assert a_row["status"] == "pending"


class TestDeleteById:
    def test_delete_by_id_returns_true(self):
        clear()
        todo = add("to delete")
        result = delete_by_id(todo["id"])
        assert result is True

    def test_delete_by_id_removes_row(self):
        clear()
        todo = add("ephemeral")
        delete_by_id(todo["id"])
        result = get()
        assert not any(t["id"] == todo["id"] for t in result)

    def test_delete_by_id_nonexistent(self):
        clear()
        assert delete_by_id(99999) is False

    def test_delete_by_id_does_not_affect_other_todos(self):
        clear()
        a = add("keep")
        b = add("delete")
        delete_by_id(b["id"])
        result = get()
        assert len(result) == 1
        assert result[0]["id"] == a["id"]


class TestInit:
    def test_init_idempotent(self):
        init_db()
        init_db()  # should not raise
