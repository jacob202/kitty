from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from openwebui_tool import common, service  # noqa: E402


def test_read_dotenv(tmp_path):
    path = tmp_path / ".env"
    path.write_text('\n# comment\nexport GATEWAY_PORT=8123\nGATEWAY_SECRET="abc xyz"\nBROKEN\n')
    assert common.read_dotenv(path) == {"GATEWAY_PORT": "8123", "GATEWAY_SECRET": "abc xyz"}


def test_runtime_env_points_only_to_kitty(tmp_path, monkeypatch):
    root, home = tmp_path / "repo", tmp_path / "service"
    root.mkdir(); (root / ".env").write_text("GATEWAY_PORT=8123\nGATEWAY_SECRET=test-secret\n")
    monkeypatch.setattr(common, "ROOT", root); monkeypatch.setattr(common, "SERVICE_ROOT", home)
    monkeypatch.setattr(common, "DATA_DIR", home / "data-fresh"); monkeypatch.setattr(common, "LOG_DIR", home / "logs")
    monkeypatch.setattr(common, "RUN_DIR", home / "run"); monkeypatch.setattr(common, "SECRET_FILE", home / "webui-secret")
    for key in ("GATEWAY_SECRET", "KITTY_GATEWAY_SECRET", "GATEWAY_PORT"): monkeypatch.delenv(key, raising=False)
    env = common.runtime_env()
    assert env["OPENAI_API_BASE_URL"] == "http://127.0.0.1:8123/v1"
    assert env["OPENAI_API_KEY"] == "test-secret"
    assert env["ENABLE_OLLAMA_API"] == "False" and env["DEFAULT_MODELS"] == "kitty-default"
    assert env["WEBUI_AUTH"] == "False" and env["ENABLE_PERSISTENT_CONFIG"] == "False"
    assert (home / "webui-secret").stat().st_mode & 0o777 == 0o600


def test_stream_smoke_requires_explicit_charge_acceptance():
    try: service.direct_stream_smoke(accept_charges=False)
    except common.Failure as exc: assert "--accept-charges" in str(exc)
    else: raise AssertionError("expected Failure")
