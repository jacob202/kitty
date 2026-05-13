"""Tests for todo_store — structured task list CRUD."""
import pytest
from gateway.todo_store import update, get, add, complete, clear, init_db


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


class TestInit:
    def test_init_idempotent(self):
        init_db()
        init_db()  # should not raise
