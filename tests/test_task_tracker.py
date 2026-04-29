"""
Tests for task tracker and task_repo.
"""
import sys, os, sqlite3, pytest, tempfile
import src.memory.task_repo as task_repo

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.memory.task_repo import init_task_db, add_task, mark_done, get_open_tasks, get_next_task, get_next_action, DB_PATH
from src.memory.task_tracker import process_done_command, get_next_task_brief

@pytest.fixture(autouse=True)
def setup_db(tmp_path):
    db = tmp_path / "test_kitty.db"
    original = task_repo.DB_PATH
    task_repo.DB_PATH = str(db)
    from src.memory.task_repo import init_task_db
    init_task_db()
    yield
    task_repo.DB_PATH = original
    if os.path.exists(str(db)):
        os.unlink(str(db))


class TestTaskRepo:
    def test_init_creates_table(self):
        conn = sqlite3.connect(task_repo.DB_PATH)
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        conn.close()
        assert any(t[0] == "tasks" for t in tables)

    def test_add_and_get(self):
        tid = add_task("Test task")
        assert isinstance(tid, int)
        open_tasks = get_open_tasks()
        assert len(open_tasks) == 1
        assert open_tasks[0]["title"] == "Test task"

    def test_mark_done(self):
        add_task("Task 1")
        result = mark_done("Task 1")
        assert result["found"] is True
        assert result["task"]["status"] == "done"
        assert result["next_open"] is None  # no more open tasks

    def test_mark_done_returns_next(self):
        add_task("Task 1")
        add_task("Task 2")
        result = mark_done("Task 1")
        assert result["next_open"] is not None
        assert result["next_open"]["title"] == "Task 2"

    def test_mark_done_no_match(self):
        result = mark_done("nonexistent")
        assert result["found"] is False

    def test_get_next_action(self):
        add_task("First task")
        assert "First task" in get_next_action()


class TestTaskTracker:
    def test_process_done_matched(self):
        add_task("Build brief")
        result = process_done_command("done Build brief")
        assert result["matched"] is True
        assert "Marked done" in result["response"]

    def test_process_done_no_match(self):
        result = process_done_command("hello")
        assert result["matched"] is False

    def test_process_done_no_open_task(self):
        result = process_done_command("done nonexistent")
        assert result["matched"] is True
        assert "No open task" in result["response"]

    def test_get_next_task_brief(self):
        add_task("My task")
        brief = get_next_task_brief()
        assert "Next:" in brief
        assert "My task" in brief

    def test_get_next_task_brief_empty(self):
        brief = get_next_task_brief()
        assert "No open tasks" in brief
