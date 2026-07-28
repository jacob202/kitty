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
def isolated_governor_db(tmp_path, monkeypatch):
    """Never let a test write compute-governor receipts into the real store.

    The Builder CLI governs by default, and the allowance is keyed on
    initiative/packet/base SHA — identifiers the Builder tests reuse. Without
    this, the second governed CLI test in a run is correctly refused as a
    duplicate, and a test run would leave receipts in data/compute_governor/.
    """
    monkeypatch.setenv(
        "KITTY_COMPUTE_GOVERNOR_DB", str(tmp_path / "governor" / "receipts.db")
    )


@pytest.fixture(autouse=True)
def isolate_provider_prefs(tmp_path, monkeypatch):
    """Keep the saved provider order out of tests — and tests out of it.

    resolve_order() reads config/providers.json, so without this a local
    preference would silently reorder the fallback chain under the suite.
    """
    import gateway.provider_prefs as provider_prefs

    monkeypatch.setattr(provider_prefs, "PROVIDER_PREFS_FILE", tmp_path / "providers.json")


@pytest.fixture
def all_provider_keys(monkeypatch):
    """Give every cloud provider a key so ordering is what's under test.

    The chain now skips unkeyed providers outright, so a test that means to
    exercise fallback *order* has to opt in to being configured.
    """
    for name in (
        "OPENAI_API_KEY",
        "NVIDIA_API_KEY",
        "AGENTROUTER_API_KEY",
        "OPENROUTER_API_KEY",
        "GEMINI_API_KEY",
    ):
        monkeypatch.setenv(name, "sk-test-key")


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
