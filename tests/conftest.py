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
