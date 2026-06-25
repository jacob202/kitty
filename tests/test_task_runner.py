"""Tests for task_runner — create, get, list, cancel, output."""
from unittest.mock import MagicMock, patch

import pytest

from gateway.task_runner import (
    VALID_TYPES,
    cancel,
    create,
    get,
    get_output,
    init_db,
    list_tasks,
)


def _discard_background_task(coro):
    """Stand in for asyncio.create_task in sync tests — no loop, no orphan coroutines."""
    close = getattr(coro, "close", None)
    if callable(close):
        close()
    return MagicMock(name="fake_task", cancelled=False, cancel=MagicMock())


class TestCreate:
    def test_creates_task_and_returns_id(self):
        with patch("gateway.task_runner.asyncio.create_task", side_effect=_discard_background_task):
            task_id = create("test research goal", task_type="research")
        assert isinstance(task_id, str)
        assert len(task_id) == 8

    def test_creates_all_valid_types(self):
        with patch("gateway.task_runner.asyncio.create_task", side_effect=_discard_background_task):
            for t in VALID_TYPES:
                task_id = create(f"test {t}", task_type=t, run_immediately=False)
                assert isinstance(task_id, str)

    def test_invalid_type_raises(self):
        with pytest.raises(ValueError, match="Unknown task type"):
            create("test", task_type="invalid_type")

    def test_run_immediately_false_does_not_execute(self):
        task_id = create("test goal", task_type="research", run_immediately=False)
        task = get(task_id)
        assert task["status"] == "queued"

    def test_metadata_stored(self):
        with patch("gateway.task_runner.asyncio.create_task", side_effect=_discard_background_task):
            task_id = create("test", task_type="cleanup", metadata={"priority": "low"})
        task = get(task_id)
        assert task["metadata"] == {"priority": "low"}


class TestGet:
    def test_get_existing_task(self):
        with patch("gateway.task_runner.asyncio.create_task", side_effect=_discard_background_task):
            task_id = create("test", task_type="dream")
        task = get(task_id)
        assert task["id"] == task_id
        assert task["goal"] == "test"
        assert task["task_type"] == "dream"
        assert task["status"] == "queued"

    def test_get_nonexistent(self):
        result = get("nonexistent")
        assert result["status"] == "not_found"


class TestListTasks:
    def test_returns_list(self):
        tasks = list_tasks(limit=5)
        assert isinstance(tasks, list)

    def test_status_filter(self):
        tasks = list_tasks(status="queued", limit=5)
        for t in tasks:
            assert t["status"] == "queued"


class TestCancel:
    def test_cancel_queued_task(self):
        task_id = create("test", task_type="research", run_immediately=False)
        assert cancel(task_id) is True
        task = get(task_id)
        assert task["status"] == "cancelled"

    def test_cancel_nonexistent(self):
        assert cancel("nonexistent") is False


class TestOutput:
    def test_output_empty_for_no_file(self):
        assert get_output("nonexistent") == ""


class TestDBInit:
    def test_init_idempotent(self):
        init_db()
        init_db()  # should not raise
