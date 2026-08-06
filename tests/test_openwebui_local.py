from __future__ import annotations

import json
import plistlib
import sqlite3
import subprocess
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


def test_read_dotenv_expands_in_assignment_order(tmp_path):
    path = tmp_path / ".env"
    path.write_text("BASE=8123\nGATEWAY_PORT=$BASE\n")

    assert common.read_dotenv(path, base={}) == {
        "BASE": "8123",
        "GATEWAY_PORT": "8123",
    }


@pytest.fixture
def service_paths(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    home = tmp_path / "service"
    root.mkdir()
    (root / ".env").write_text("GATEWAY_PORT=8123\nGATEWAY_SECRET=test-secret\n")
    data = home / "data-fresh"
    for module in (common, service, system):
        monkeypatch.setattr(module, "DATA_DIR", data, raising=False)
        monkeypatch.setattr(module, "SERVICE_ROOT", home, raising=False)
    monkeypatch.setattr(common, "ROOT", root)
    monkeypatch.setattr(common, "LOG_DIR", home / "logs")
    monkeypatch.setattr(common, "RUN_DIR", home / "run")
    monkeypatch.setattr(common, "BACKUP_ROOT", home / "backups")
    monkeypatch.setattr(common, "SECRET_FILE", home / "webui-secret")
    monkeypatch.setattr(service, "PID_FILE", home / "run/openwebui.pid")
    monkeypatch.setattr(service, "START_LOCK", home / "run/openwebui-start.lock")
    monkeypatch.setattr(system, "BACKUP_ROOT", home / "backups")
    monkeypatch.setattr(system, "SECRET_FILE", home / "webui-secret")
    for key in ("GATEWAY_SECRET", "KITTY_GATEWAY_SECRET", "GATEWAY_PORT"):
        monkeypatch.delenv(key, raising=False)
    data.mkdir(parents=True)
    return root, home


def test_repository_config_wins_over_stale_shell_values(service_paths, monkeypatch):
    monkeypatch.setenv("GATEWAY_PORT", "9999")
    monkeypatch.setenv("GATEWAY_SECRET", "wrong-secret")

    assert common.gateway_config() == ("http://127.0.0.1:8123", "test-secret")


def test_runtime_env_points_only_to_kitty(service_paths):
    _, home = service_paths

    env = common.runtime_env()

    assert env["OPENAI_API_BASE_URL"] == "http://127.0.0.1:8123/v1"
    assert env["OPENAI_API_KEY"] == "test-secret"
    assert env["ENABLE_OLLAMA_API"] == "False"
    assert env["DEFAULT_MODELS"] == common.DEFAULT_AGENT
    assert common.DEFAULT_AGENT in common.PINNED_AGENTS
    assert env["TASK_MODEL_EXTERNAL"] == common.TASK_MODEL
    assert env["WEBUI_AUTH"] == "False"
    assert env["ENABLE_PERSISTENT_CONFIG"] == "False"
    assert (home / "webui-secret").stat().st_mode & 0o777 == 0o600


def test_runtime_env_allowlists_the_parent_environment(service_paths, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "must-not-leak")
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-leak")
    monkeypatch.setenv("GITHUB_TOKEN", "must-not-leak")
    monkeypatch.setenv("PATH", "/usr/bin:/bin")

    env = common.runtime_env()

    assert env["PATH"] == "/usr/bin:/bin"
    assert env["OPENAI_API_KEY"] == "test-secret"
    assert "OPENROUTER_API_KEY" not in env
    assert "GITHUB_TOKEN" not in env
    assert env["NO_PROXY"] == "127.0.0.1,localhost"


def test_runtime_env_drops_kitty_import_path(service_paths, monkeypatch):
    monkeypatch.setenv("PYTHONPATH", str(REPO_ROOT))
    monkeypatch.setenv("PYTHONHOME", "/somewhere/else")
    monkeypatch.setenv("PYTHONSTARTUP", str(REPO_ROOT / "sitecustomize.py"))

    env = common.runtime_env()

    assert "PYTHONPATH" not in env
    assert "PYTHONHOME" not in env
    assert "PYTHONSTARTUP" not in env
    assert env["PYTHONNOUSERSITE"] == "1"


def test_service_directories_are_owner_only(tmp_path, monkeypatch):
    service_root = tmp_path / "service"
    paths = [
        service_root,
        service_root / "data",
        service_root / "backups",
        service_root / "logs",
        service_root / "run",
    ]
    monkeypatch.setattr(common, "SERVICE_ROOT", paths[0])
    monkeypatch.setattr(common, "DATA_DIR", paths[1])
    monkeypatch.setattr(common, "BACKUP_ROOT", paths[2])
    monkeypatch.setattr(common, "LOG_DIR", paths[3])
    monkeypatch.setattr(common, "RUN_DIR", paths[4])

    common.ensure_dirs()

    assert all(path.stat().st_mode & 0o777 == 0o700 for path in paths)


def test_non_loopback_host_is_rejected():
    with pytest.raises(common.Failure):
        common._require_loopback_host("0.0.0.0")


def test_launch_agent_never_runs_from_the_repo(tmp_path, monkeypatch):
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
    monkeypatch.setattr(system, "claim_system_admin", lambda: "token")
    monkeypatch.setattr(system, "ensure_agents", lambda token: "ok")
    monkeypatch.setattr(system, "write_desktop_shortcut", lambda: None)
    monkeypatch.setattr(system, "_verify_launch_agent_enabled", lambda domain: None)
    monkeypatch.setattr(
        system,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(a, 0, stdout="", stderr=""),
    )

    system.install_launch_agent()
    plist = plistlib.loads(agent.read_bytes())

    assert plist["WorkingDirectory"] == str(home)
    assert plist["WorkingDirectory"] != str(system.ROOT)
    assert "PYTHONPATH" not in plist["EnvironmentVariables"]
    assert plist["EnvironmentVariables"]["PYTHONNOUSERSITE"] == "1"


def _seed_webui_db(
    path: Path,
    admin_ids: list[str],
    *,
    chat_owner: str | None = None,
    role: str = "admin",
):
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE user (id TEXT PRIMARY KEY, email TEXT, role TEXT, created_at INT)"
        )
        connection.execute("CREATE TABLE auth (id TEXT PRIMARY KEY, email TEXT, active INT)")
        connection.execute("CREATE TABLE chat (id TEXT PRIMARY KEY, user_id TEXT)")
        for index, admin_id in enumerate(admin_ids):
            connection.execute(
                "INSERT INTO user VALUES (?, 'admin@localhost', ?, ?)",
                (admin_id, role, 1785695804 + index),
            )
            connection.execute(
                "INSERT INTO auth VALUES (?, 'admin@localhost', 1)", (admin_id,)
            )
        if chat_owner is not None:
            connection.execute("INSERT INTO chat VALUES ('chat-1', ?)", (chat_owner,))
        connection.commit()


def _roles(path: Path) -> list[str]:
    with sqlite3.connect(path) as connection:
        return [row[0] for row in connection.execute("SELECT role FROM user")]


def test_dedupe_collapses_the_signin_race(service_paths):
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


def test_dedupe_clears_the_pending_account_wall(service_paths):
    _seed_webui_db(service.webui_db_path(), ["keep", "dupe-1"], role="pending")

    service.dedupe_system_admin()

    assert _roles(service.webui_db_path()) == ["admin"]


def test_dedupe_promotes_a_lone_pending_account(service_paths):
    _seed_webui_db(service.webui_db_path(), ["only"], role="pending")

    assert "promoted to admin" in service.dedupe_system_admin()
    assert _roles(service.webui_db_path()) == ["admin"]
    assert "promoted to admin" not in service.dedupe_system_admin()


def test_runtime_env_never_leaves_a_new_account_pending(service_paths):
    assert common.runtime_env()["DEFAULT_USER_ROLE"] == "admin"


def test_dedupe_without_a_database_is_a_no_op(service_paths):
    assert service.dedupe_system_admin() == "no database yet"
    assert service.count_system_admins() == 0


def test_stream_smoke_requires_explicit_charge_acceptance():
    with pytest.raises(common.Failure) as excinfo:
        service.direct_stream_smoke(accept_charges=False)
    assert "--accept-charges" in str(excinfo.value)


class _FakeStream:
    def __init__(self, lines: list[bytes]):
        self._lines = lines

    def __enter__(self):
        return self._lines

    def __exit__(self, *exc):
        return False


def test_stream_smoke_reports_the_gateway_error_not_a_shrug(monkeypatch):
    monkeypatch.setattr(service, "verify_gateway", lambda: ("http://gw", "secret"))
    error = json.dumps(
        {"error": {"kind": "routing", "message": "provider is out of credit"}}
    )
    monkeypatch.setattr(
        service,
        "open_local",
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
        service,
        "open_local",
        lambda *a, **k: _FakeStream([f"data: {chunk}\n".encode()]),
    )

    with pytest.raises(common.Failure) as excinfo:
        service.direct_stream_smoke(accept_charges=True)

    assert "[DONE]" in str(excinfo.value)


def test_stream_smoke_is_token_bounded_and_requires_ready(monkeypatch):
    monkeypatch.setattr(service, "verify_gateway", lambda: ("http://gw", "secret"))
    captured: dict = {}
    chunk = json.dumps({"choices": [{"delta": {"content": "not ready"}}]})

    def fake_open(request, *, timeout):
        captured.update(json.loads(request.data))
        return _FakeStream([f"data: {chunk}\n".encode(), b"data: [DONE]\n"])

    monkeypatch.setattr(service, "open_local", fake_open)

    with pytest.raises(common.Failure) as excinfo:
        service.direct_stream_smoke(accept_charges=True)

    assert captured["max_tokens"] == service.SMOKE_MAX_TOKENS
    assert captured["temperature"] == 0
    assert "expected exactly" in str(excinfo.value)


def test_read_pid_refuses_a_reused_unrelated_process(service_paths, monkeypatch):
    _, home = service_paths
    service.PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    service.PID_FILE.write_text("123\n")
    monkeypatch.setattr(service, "pid_alive", lambda pid: True)
    monkeypatch.setattr(service, "_pid_owned_by_openwebui", lambda pid: False)

    assert service.read_pid() is None
    assert not (home / "run/openwebui.pid").exists()


def test_daily_agent_advertises_vision_for_auto_routing():
    daily = next(agent for agent in service.AGENTS if agent["id"] == "daily-kitty")
    assert daily["vision"] is True


def _make_sqlite(path: Path, value: str) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE marker (value TEXT)")
        connection.execute("INSERT INTO marker VALUES (?)", (value,))
        connection.commit()


def _sqlite_value(path: Path) -> str:
    with sqlite3.connect(path) as connection:
        return connection.execute("SELECT value FROM marker").fetchone()[0]


def test_atomic_restore_copy_preserves_live_database_on_invalid_source(tmp_path):
    live = tmp_path / "webui.db"
    invalid = tmp_path / "invalid.db"
    _make_sqlite(live, "keep")
    invalid.write_text("not sqlite")

    with pytest.raises(common.Failure):
        system._atomic_copy(invalid, live, validate_sqlite=True)

    assert _sqlite_value(live) == "keep"


def test_bootstrap_requires_smoke_before_enabling_autostart(monkeypatch):
    monkeypatch.setattr(system, "start_webui", lambda: pytest.fail("must fail before start"))

    with pytest.raises(common.Failure) as excinfo:
        system.bootstrap(accept_charges=False, no_autostart=False)

    assert "--accept-charges" in str(excinfo.value)
