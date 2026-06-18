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
