from __future__ import annotations

import json
import plistlib
import sqlite3
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from openwebui_tool import common, service, system  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_read_dotenv(tmp_path):
    path = tmp_path / ".env"
    path.write_text(
        '\n# comment\nexport GATEWAY_PORT=8123\nGATEWAY_SECRET="abc xyz"\nBROKEN\n'
    )
    assert common.read_dotenv(path) == {
        "GATEWAY_PORT": "8123",
        "GATEWAY_SECRET": "abc xyz",
    }


@pytest.fixture
def service_paths(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    home = tmp_path / "service"
    root.mkdir()
    (root / ".env").write_text("GATEWAY_PORT=8123\nGATEWAY_SECRET=test-secret\n")
    data = home / "data-fresh"
    for module in (common, service):
        monkeypatch.setattr(module, "DATA_DIR", data, raising=False)
        monkeypatch.setattr(module, "SERVICE_ROOT", home, raising=False)
    monkeypatch.setattr(common, "ROOT", root)
    monkeypatch.setattr(common, "LOG_DIR", home / "logs")
    monkeypatch.setattr(common, "RUN_DIR", home / "run")
    monkeypatch.setattr(common, "SECRET_FILE", home / "webui-secret")
    for key in ("GATEWAY_SECRET", "KITTY_GATEWAY_SECRET", "GATEWAY_PORT"):
        monkeypatch.delenv(key, raising=False)
    data.mkdir(parents=True)
    return root, home


def test_runtime_env_points_only_to_kitty(service_paths):
    _, home = service_paths

    env = common.runtime_env()

    assert env["OPENAI_API_BASE_URL"] == "http://127.0.0.1:8123/v1"
    assert env["OPENAI_API_KEY"] == "test-secret"
    assert env["ENABLE_OLLAMA_API"] == "False"
    assert env["DEFAULT_MODELS"] == "kitty-default"
    assert env["WEBUI_AUTH"] == "False"
    assert env["ENABLE_PERSISTENT_CONFIG"] == "False"
    assert (home / "webui-secret").stat().st_mode & 0o777 == 0o600


def test_runtime_env_drops_kitty_import_path(service_paths, monkeypatch):
    """Kitty's repo root holds a top-level ``mcp`` package.

    Inheriting PYTHONPATH from ``./kitty`` shadows Open WebUI's MCP SDK, which
    surfaces as ``cannot import name 'ClientSession' from 'mcp'``.
    """
    monkeypatch.setenv("PYTHONPATH", str(REPO_ROOT))
    monkeypatch.setenv("PYTHONHOME", "/somewhere/else")
    monkeypatch.setenv("PYTHONSTARTUP", str(REPO_ROOT / "sitecustomize.py"))

    env = common.runtime_env()

    assert "PYTHONPATH" not in env
    assert "PYTHONHOME" not in env
    assert "PYTHONSTARTUP" not in env
    assert env["PYTHONNOUSERSITE"] == "1"


def test_launch_agent_never_runs_from_the_repo(tmp_path, monkeypatch):
    """WorkingDirectory is on sys.path, so the repo root shadows ``mcp`` too.

    An empty PYTHONPATH would be just as bad as a wrong one — it puts the
    working directory back on the path — so the key must be absent entirely.
    """
    home = tmp_path / "service"
    agent = tmp_path / "com.kitty.openwebui.plist"
    monkeypatch.setattr(system, "SERVICE_ROOT", home)
    monkeypatch.setattr(system, "LAUNCH_AGENT", agent)
    monkeypatch.setattr(system, "LOG_FILE", home / "logs/openwebui.log")
    monkeypatch.setattr(system, "ensure_dirs", lambda: home.mkdir(parents=True, exist_ok=True))
    monkeypatch.setattr(system, "install_openwebui", lambda: None)
    monkeypatch.setattr(system, "ensure_webui_secret", lambda: "secret")
    monkeypatch.setattr(system, "stop_webui", lambda: None)
    monkeypatch.setattr(system, "wait_for_webui", lambda: None)
    monkeypatch.setattr(system, "run", lambda *a, **k: None)

    system.install_launch_agent()
    plist = plistlib.loads(agent.read_bytes())

    assert plist["WorkingDirectory"] == str(home)
    assert plist["WorkingDirectory"] != str(system.ROOT)
    assert "PYTHONPATH" not in plist["EnvironmentVariables"]
    assert plist["EnvironmentVariables"]["PYTHONNOUSERSITE"] == "1"


def _seed_webui_db(path: Path, admin_ids: list[str], *, chat_owner: str | None = None):
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE user (id TEXT PRIMARY KEY, email TEXT, role TEXT, created_at INT)"
        )
        connection.execute("CREATE TABLE auth (id TEXT PRIMARY KEY, email TEXT, active INT)")
        connection.execute("CREATE TABLE chat (id TEXT PRIMARY KEY, user_id TEXT)")
        for index, admin_id in enumerate(admin_ids):
            connection.execute(
                "INSERT INTO user VALUES (?, 'admin@localhost', 'admin', ?)",
                (admin_id, 1785695804 + index),
            )
            connection.execute(
                "INSERT INTO auth VALUES (?, 'admin@localhost', 1)", (admin_id,)
            )
        if chat_owner is not None:
            connection.execute("INSERT INTO chat VALUES ('chat-1', ?)", (chat_owner,))
        connection.commit()


def test_dedupe_collapses_the_signin_race(service_paths):
    """WEBUI_AUTH=False checks for a user then inserts one, without a lock.

    A first page load fires several signins at once, they all miss, and they all
    insert — six identical admins on Jacob's Mac.
    """
    _, home = service_paths
    _seed_webui_db(service.webui_db_path(), ["keep", "dupe-1", "dupe-2"])

    assert service.count_system_admins() == 3
    message = service.dedupe_system_admin()

    assert "removed 2" in message
    assert service.count_system_admins() == 1
    with sqlite3.connect(service.webui_db_path()) as connection:
        assert [r[0] for r in connection.execute("SELECT id FROM user")] == ["keep"]
        assert [r[0] for r in connection.execute("SELECT id FROM auth")] == ["keep"]


def test_dedupe_is_idempotent(service_paths):
    _seed_webui_db(service.webui_db_path(), ["keep", "dupe-1"])

    service.dedupe_system_admin()
    assert service.dedupe_system_admin() == "1 admin account"
    assert service.count_system_admins() == 1


def test_dedupe_refuses_to_delete_an_account_that_owns_chats(service_paths):
    _seed_webui_db(service.webui_db_path(), ["keep", "dupe-1"], chat_owner="dupe-1")

    with pytest.raises(common.Failure) as excinfo:
        service.dedupe_system_admin()

    assert "refusing to delete" in str(excinfo.value)
    assert service.count_system_admins() == 2


def test_dedupe_without_a_database_is_a_no_op(service_paths):
    assert service.dedupe_system_admin() == "no database yet"
    assert service.count_system_admins() == 0


def test_stream_smoke_requires_explicit_charge_acceptance():
    try:
        service.direct_stream_smoke(accept_charges=False)
    except common.Failure as exc:
        assert "--accept-charges" in str(exc)
    else:
        raise AssertionError("expected Failure")


class _FakeStream:
    def __init__(self, lines: list[bytes]):
        self._lines = lines

    def __enter__(self):
        return self._lines

    def __exit__(self, *exc):
        return False


def test_stream_smoke_reports_the_gateway_error_not_a_shrug(monkeypatch):
    """The gateway names the cause; the smoke used to replace it with a shrug."""
    monkeypatch.setattr(service, "verify_gateway", lambda: ("http://gw", "secret"))
    error = json.dumps(
        {"error": {"kind": "routing", "message": "provider is out of credit"}}
    )
    monkeypatch.setattr(
        service.urllib.request,
        "urlopen",
        lambda *a, **k: _FakeStream([f"data: {error}\n".encode(), b"data: [DONE]\n"]),
    )

    with pytest.raises(common.Failure) as excinfo:
        service.direct_stream_smoke(accept_charges=True)

    assert "routing" in str(excinfo.value)
    assert "out of credit" in str(excinfo.value)


def test_stream_smoke_rejects_a_stream_with_no_completion_boundary(monkeypatch):
    monkeypatch.setattr(service, "verify_gateway", lambda: ("http://gw", "secret"))
    chunk = json.dumps({"choices": [{"delta": {"content": "ready"}}]})
    monkeypatch.setattr(
        service.urllib.request,
        "urlopen",
        lambda *a, **k: _FakeStream([f"data: {chunk}\n".encode()]),
    )

    with pytest.raises(common.Failure) as excinfo:
        service.direct_stream_smoke(accept_charges=True)

    assert "[DONE]" in str(excinfo.value)
