import atexit
import os
import shutil
import site
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_TEST_DATA_ROOT = Path(tempfile.mkdtemp(prefix="kitty-pytest-data-"))
os.environ["KITTY_ENV"] = "test"
os.environ["KITTY_TEST_GUARD"] = "1"
os.environ["KITTY_DATA_ROOT"] = str(_TEST_DATA_ROOT)
os.environ.pop("KITTY_BUILDER_DATA_DIR", None)
os.environ["GATEWAY_SECRET"] = ""
os.environ["KITTY_IMAGE_PAID_ENABLED"] = "0"
os.environ["PYTHON_DOTENV_DISABLED"] = "1"

# Make the checkout's sitecustomize importable by every Python child process.
_existing_pythonpath = os.environ.get("PYTHONPATH", "")
_startup = ROOT / "tests" / "python_startup"
_existing_pythonpath_parts = [
    part for part in _existing_pythonpath.split(os.pathsep) if part
]
_child_pythonpath = [
    str(_startup),
    str(ROOT),
    *site.getsitepackages(),
    *_existing_pythonpath_parts,
]
os.environ["PYTHONPATH"] = os.pathsep.join(dict.fromkeys(_child_pythonpath))

_PAID_PROVIDER_KEYS = (
    "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "OPENROUTER_API_KEY",
    "GEMINI_API_KEY", "GOOGLE_API_KEY", "NVIDIA_API_KEY", "BFL_API_KEY",
    "RUNWARE_API_KEY", "FAL_KEY", "AIRFORCE_API_KEY", "RUNPOD_API_KEY",
    "REPLICATE_API_TOKEN", "MEM0_API_KEY", "LLAMA_CLOUD_API_KEY",
    "TAVILY_API_KEY",
)
for _key in _PAID_PROVIDER_KEYS:
    os.environ.pop(_key, None)

import kitty_test_guard as _test_guard  # noqa: E402

_test_guard.install_test_guards()
atexit.register(shutil.rmtree, _TEST_DATA_ROOT, True)


@pytest.fixture(autouse=True)
def enforce_controlled_live_contract(request, monkeypatch):
    marker = request.node.get_closest_marker("controlled_live")
    if marker is None:
        monkeypatch.delenv("KITTY_TEST_CONTROLLED_LIVE_ACTIVE", raising=False)
        for key in _PAID_PROVIDER_KEYS:
            monkeypatch.delenv(key, raising=False)
        monkeypatch.setenv("KITTY_IMAGE_PAID_ENABLED", "0")
        return

    if os.environ.get("KITTY_TEST_ALLOW_LIVE") != "1":
        pytest.skip("controlled_live requires KITTY_TEST_ALLOW_LIVE=1")
    if os.environ.get("KITTY_TEST_CHARGE_OK") != "1":
        pytest.skip("controlled_live requires KITTY_TEST_CHARGE_OK=1")
    max_requests = int(os.environ.get("KITTY_TEST_LIVE_MAX_REQUESTS", "0"))
    max_cost = float(os.environ.get("KITTY_TEST_MAX_COST_USD", "0"))
    if max_requests < 1 or max_requests > 1:
        pytest.fail("controlled_live requires KITTY_TEST_LIVE_MAX_REQUESTS=1")
    if max_cost <= 0 or max_cost > 0.10:
        pytest.fail("controlled_live requires 0 < KITTY_TEST_MAX_COST_USD <= 0.10")
    monkeypatch.setenv("KITTY_TEST_CONTROLLED_LIVE_ACTIVE", "1")
    _test_guard.reset_live_counter()


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
