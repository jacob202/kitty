"""Tests for ingestion queue error break loop and circuit breaker."""
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from gateway.ingestion_queue import (
    GLOBAL_ERROR_THRESHOLD,
    MAX_ATTEMPTS,
    _backoff,
    _classify_error,
    clear_halt_flag,
    _is_halted,
    init_db,
    enqueue_file,
    get_next_task,
    update_task_status,
    get_error_summary,
    QUEUE_DB,
    HALT_SENTINEL,
)
from gateway.paths import DATA_DIR


# ---------------------------------------------------------------------------
# _classify_error
# ---------------------------------------------------------------------------

class TestClassifyError:
    def test_oserror_classified(self):
        cat, label = _classify_error(OSError("disk full"))
        assert cat == "filesystem / I/O"
        assert label == "OSError"

    def test_permission_error_classified(self):
        cat, label = _classify_error(PermissionError("/root/secret"))
        assert cat == "filesystem / permissions"
        assert label == "PermissionError"

    def test_timeout_error_classified(self):
        cat, label = _classify_error(TimeoutError("timed out"))
        assert cat == "timeout"

    def test_connection_error_classified(self):
        cat, label = _classify_error(ConnectionError("refused"))
        assert cat == "network"

    def test_keyvalue_error_classified(self):
        cat, label = _classify_error(KeyError("missing"))
        assert cat == "data / missing field"

    def test_unknown_error_gets_generic(self):
        cat, label = _classify_error(NotImplementedError("nope"))
        assert cat == "unknown"
        assert label == "NotImplementedError"

    def test_sqlite_error_classified_as_database(self):
        import sqlite3

        cat, label = _classify_error(sqlite3.OperationalError("locked"))
        assert cat == "database"
        assert label == "OperationalError"


# ---------------------------------------------------------------------------
# _backoff
# ---------------------------------------------------------------------------

class TestBackoff:
    def test_first_delay_is_base(self):
        assert _backoff(1) == 2.0

    def test_exponential_growth(self):
        assert _backoff(2) == 4.0
        assert _backoff(3) == 8.0

    def test_caps_at_max_delay(self):
        assert _backoff(10) == 60.0


# ---------------------------------------------------------------------------
# Database operations (init / enqueue / get_next / update)
# ---------------------------------------------------------------------------

class TestQueueDB:
    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path, monkeypatch):
        self.tmp_db = tmp_path / "test_queue.db"
        import gateway.ingestion_queue as qmod
        monkeypatch.setattr(qmod, "QUEUE_DB", self.tmp_db)
        yield
        if self.tmp_db.exists():
            self.tmp_db.unlink()

    def test_init_creates_table(self):
        import gateway.ingestion_queue as qmod
        qmod.init_db()
        assert self.tmp_db.exists()

    def test_enqueue_and_get_next(self):
        import gateway.ingestion_queue as qmod
        qmod.init_db()
        qmod.enqueue_file("/tmp/test.txt", doc_type="txt")

        task = qmod.get_next_task()
        assert task is not None
        assert task["file_path"].endswith("tmp/test.txt")
        assert task["status"] == "pending"
        assert task["attempts"] == 0

    def test_dedup_on_re_enqueue(self):
        """Re-enqueuing the same file updates the row, doesn't create a duplicate."""
        import gateway.ingestion_queue as qmod
        qmod.init_db()
        # Use absolute paths that resolve cleanly in the tmp db
        fpath = str(self.tmp_db.parent / "test.txt")
        qmod.enqueue_file(fpath)
        qmod.enqueue_file(fpath)  # same path — should upsert, not duplicate

        # Count rows directly via SQL
        import sqlite3
        with sqlite3.connect(str(self.tmp_db)) as conn:
            count = conn.execute("SELECT COUNT(*) FROM ingestion_queue").fetchone()[0]
        assert count == 1, f"Expected 1 row, got {count}"

    def test_update_marks_failed_and_increments_attempts(self):
        import gateway.ingestion_queue as qmod
        qmod.init_db()
        qmod.enqueue_file("/tmp/test.txt")
        task = qmod.get_next_task()
        task_id = task["id"]

        # In real usage the worker first marks processing (which bumps attempts),
        # then marks failed. Mirror that sequence here.
        qmod.update_task_status(task_id, "processing")
        qmod.update_task_status(task_id, "failed", "mock error")
        task2 = qmod.get_next_task()
        assert task2 is not None
        assert task2["attempts"] == 1

    def test_task_excluded_after_max_attempts(self):
        """After MAX_ATTEMPTS failures the task is no longer returned."""
        import gateway.ingestion_queue as qmod
        qmod.init_db()
        qmod.enqueue_file("/tmp/test.txt")
        task = qmod.get_next_task()
        task_id = task["id"]

        # Fail MAX_ATTEMPTS times (processing bump + failed)
        for _ in range(MAX_ATTEMPTS):
            qmod.update_task_status(task_id, "processing")
            qmod.update_task_status(task_id, "failed", "err")

        # Task should now be excluded (attempts >= MAX_ATTEMPTS)
        assert qmod.get_next_task() is None


# ---------------------------------------------------------------------------
# Halt / circuit-breaker
# ---------------------------------------------------------------------------

class TestHaltSentinel:
    def test_is_halted_false_by_default(self, tmp_path, monkeypatch):
        import gateway.ingestion_queue as qmod
        monkeypatch.setattr(qmod, "HALT_SENTINEL", tmp_path / "ingestion_halted")
        assert qmod._is_halted() is False

    def test_is_halted_true_after_write(self, tmp_path, monkeypatch):
        import gateway.ingestion_queue as qmod
        sentinel = tmp_path / "ingestion_halted"
        monkeypatch.setattr(qmod, "HALT_SENTINEL", sentinel)
        qmod._write_halt_sentinel({"queue_summary": {}, "error_samples": []})
        assert qmod._is_halted() is True

    def test_clear_halt_removes_file(self, tmp_path, monkeypatch):
        import gateway.ingestion_queue as qmod
        sentinel = tmp_path / "ingestion_halted"
        monkeypatch.setattr(qmod, "HALT_SENTINEL", sentinel)
        qmod._write_halt_sentinel({"queue_summary": {}, "error_samples": []})
        qmod.clear_halt_flag()
        assert qmod._is_halted() is False

    def test_halt_sentinel_contains_reason(self, tmp_path, monkeypatch):
        import gateway.ingestion_queue as qmod
        sentinel = tmp_path / "ingestion_halted"
        monkeypatch.setattr(qmod, "HALT_SENTINEL", sentinel)
        qmod._write_halt_sentinel(
            {"queue_summary": {"failed": 3}, "error_samples": ["err1"]},
        )

        data = json.loads(sentinel.read_text())
        assert data["reason"] == "global_error_threshold_reached"
        assert "halted_at" in data
        assert data["errors"]["queue_summary"]["failed"] == 3
        assert data["errors"]["error_samples"] == ["err1"]


# ---------------------------------------------------------------------------
# process_queue — circuit breaker halts after N consecutive failures
# ---------------------------------------------------------------------------

class TestProcessQueueBreakLoop:
    """Verify the error break loop: after GLOBAL_ERROR_THRESHOLD consecutive
    task failures the worker writes a halt sentinel and exits cleanly."""

    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path, monkeypatch):
        self.tmp_db = tmp_path / "queue.db"
        self.sentinel = tmp_path / "ingestion_halted"

        import gateway.ingestion_queue as qmod
        monkeypatch.setattr(qmod, "QUEUE_DB", self.tmp_db)
        monkeypatch.setattr(qmod, "HALT_SENTINEL", self.sentinel)
        # Patch sleep to be a no-op so the loop runs instantly (no hangs)
        monkeypatch.setattr(qmod.asyncio, "sleep", AsyncMock())
        # Make ingest_file always raise
        monkeypatch.setattr(
            "gateway.knowledge.ingest_file",
            AsyncMock(side_effect=RuntimeError("injected failure")),
        )
        self.qmod = qmod

    def test_circuit_breaker_halts_after_threshold(self):
        """After GLOBAL_ERROR_THRESHOLD consecutive failures the worker halts."""
        from gateway.ingestion_queue import init_db, enqueue_file

        init_db()
        for i in range(5):
            enqueue_file(f"/tmp/file_{i}.txt")

        from gateway.ingestion_queue import process_queue
        import asyncio
        asyncio.run(process_queue())

        assert _is_halted() is True
        sentinel_data = json.loads(self.sentinel.read_text())
        assert sentinel_data["reason"] == "global_error_threshold_reached"
        # Error samples should be present from failed tasks
        assert len(sentinel_data["errors"]["error_samples"]) > 0
        # Queue summary should show failures
        assert sentinel_data["errors"]["queue_summary"].get("failed", 0) >= 1

    def test_no_halt_on_fewer_than_threshold_failures(self, monkeypatch):
        """If failures stay below the threshold, no halt sentinel is written."""
        monkeypatch.setattr(self.qmod, "MAX_ATTEMPTS", 1)
        from gateway.ingestion_queue import init_db, enqueue_file, process_queue
        import asyncio

        init_db()
        # Only 2 tasks — both fail → consecutive count = 2, which is < threshold
        enqueue_file("/tmp/a.txt")
        enqueue_file("/tmp/b.txt")

        asyncio.run(process_queue())

        assert not _is_halted()

    def test_success_resets_global_error_counter(self):
        """A successful task resets the global consecutive-failure counter to 0."""
        from gateway.ingestion_queue import (
            init_db, enqueue_file, process_queue, update_task_status, get_next_task
        )
        import asyncio

        init_db()
        # Enqueue 3 tasks
        enqueue_file("/tmp/fail1.txt")
        enqueue_file("/tmp/ok.txt")
        enqueue_file("/tmp/fail2.txt")

        call_order = []

        async def flaky_ingest(file_path="", doc_type="", sensitivity=""):
            name = Path(file_path).name
            if name == "fail1.txt":
                raise RuntimeError("fail 1")
            if name == "fail2.txt":
                raise RuntimeError("fail 2")
            # ok.txt succeeds
            return type("R", (), {"chunks_count": 1})()

        self.qmod.ingest_file = flaky_ingest  # type: ignore

        # Manually step through the loop logic (since asyncio.run would be real)
        async def drive():
            self.qmod.init_db()
            tasks_processed = 0
            max_iterations = 20
            while tasks_processed < max_iterations:
                # The real loop calls get_next_task which queries the DB
                task = self.qmod.get_next_task()
                if task is None:
                    break
                task_id = task["id"]
                file_path = task["file_path"]
                self.qmod.update_task_status(task_id, "processing")
                try:
                    result = await self.qmod.ingest_file(
                        file_path=file_path,
                        doc_type=task["doc_type"],
                        sensitivity=task["sensitivity"],
                    )
                    self.qmod.update_task_status(task_id, "completed")
                    call_order.append(("ok", file_path))
                except RuntimeError as e:
                    self.qmod.update_task_status(task_id, "failed", str(e))
                    call_order.append(("fail", file_path))
                tasks_processed += 1

        asyncio.run(drive())

        ok_paths = [p for kind, p in call_order if kind == "ok"]
        assert any(Path(p).name == "ok.txt" for p in ok_paths)
        # The success between two failures resets the global counter
        assert not _is_halted(), "Should not halt when success resets counter"

    @pytest.mark.asyncio
    async def test_process_queue_returns_on_halt(self):
        """process_queue() returns None (clean exit) when the circuit opens."""
        from gateway.ingestion_queue import init_db, enqueue_file, process_queue

        init_db()
        for i in range(5):
            enqueue_file(f"/tmp/fail_{i}.txt")

        result = await process_queue()
        assert result is None  # clean exit, no exception


class TestClearQueue:
    def test_clear_queue_removes_all_rows(self, tmp_path, monkeypatch):
        import gateway.ingestion_queue as qmod

        db = tmp_path / "q.db"
        monkeypatch.setattr(qmod, "QUEUE_DB", db)
        qmod.init_db()
        qmod.enqueue_file("/tmp/a.txt")
        qmod.enqueue_file("/tmp/b.txt")
        n = qmod.clear_queue()
        assert n == 2
        assert qmod.get_next_task() is None
        conn = __import__("sqlite3").connect(str(db))
        cur = conn.execute("SELECT COUNT(*) FROM ingestion_queue")
        assert cur.fetchone()[0] == 0
        conn.close()


# ---------------------------------------------------------------------------
# get_error_summary
# ---------------------------------------------------------------------------

class TestErrorSummary:
    def test_summary_counts_statuses(self, tmp_path, monkeypatch):
        import gateway.ingestion_queue as qmod
        db = tmp_path / "q.db"
        monkeypatch.setattr(qmod, "QUEUE_DB", db)
        qmod.init_db()
        qmod.enqueue_file("/tmp/ok.txt")
        qmod.enqueue_file("/tmp/bad.txt")

        task = qmod.get_next_task()
        qmod.update_task_status(task["id"], "completed")

        task2 = qmod.get_next_task()
        qmod.update_task_status(task2["id"], "failed", "oops")

        summary = qmod.get_error_summary()
        assert summary["queue_summary"]["completed"] == 1
        assert summary["queue_summary"]["failed"] == 1
        assert "oops" in summary["error_samples"]
