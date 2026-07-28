import os

import pytest

# Ensure gateway auth uses test bypass when GATEWAY_SECRET is unset during pytest runs.
os.environ.setdefault("KITTY_ENV", "test")
os.environ["GATEWAY_SECRET"] = ""


@pytest.fixture(autouse=True)
def isolate_gateway_auth_env(monkeypatch):
    """Keep real local .env secrets from leaking into TestClient tests."""
    monkeypatch.setenv("KITTY_ENV", "test")
    monkeypatch.setenv("GATEWAY_SECRET", "")


@pytest.fixture(autouse=True)
def isolate_task_queue(tmp_path, monkeypatch):
    """Point the background-task queue at a scratch DB.

    Without this the suite writes to (and reconcile_stale would fail) the real
    data/task_queue.db, so running tests locally would eat Jacob's queued work.
    """
    import gateway.task_runner as task_runner

    monkeypatch.setattr(task_runner, "TASK_DB", tmp_path / "task_queue.db")
    monkeypatch.setattr(task_runner, "TASK_OUTPUT_DIR", tmp_path / "task_outputs")
    monkeypatch.setattr(task_runner, "_TASKS", {})
