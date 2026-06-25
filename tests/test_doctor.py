from __future__ import annotations

import json
import sys
from unittest.mock import MagicMock, patch


def test_gateway_secret_warning_matches_fail_closed_auth(monkeypatch, tmp_path) -> None:
    from gateway import doctor

    monkeypatch.setattr(doctor, "ROOT", tmp_path)
    (tmp_path / ".env").write_text("OPENROUTER_API_KEY=set\n", encoding="utf-8")

    checks = doctor._check_env({"OPENROUTER_API_KEY": "set"})

    gateway_secret = next(c for c in checks if c.name == "env:gateway_secret")

    assert gateway_secret.level == "WARN"
    assert "fails closed" in gateway_secret.detail
    assert "accepts any request" not in gateway_secret.detail


def test_doctor_uses_litellm_readiness_endpoint(monkeypatch) -> None:
    from gateway import doctor

    seen_urls: list[str] = []

    def fake_http_ok(url: str, timeout: float = 3.0, headers: dict | None = None) -> bool:
        seen_urls.append(url)
        return True

    monkeypatch.setattr(doctor, "_http_ok", fake_http_ok)

    doctor._check_services({"GATEWAY_PORT": "5001", "LITELLM_PORT": "8001"})

    assert "http://127.0.0.1:8001/health/readiness" in seen_urls


# --- _check_env ---

def test_check_env_fails_when_no_dotenv(monkeypatch, tmp_path) -> None:
    from gateway import doctor

    monkeypatch.setattr(doctor, "ROOT", tmp_path)
    checks = doctor._check_env({})
    names = {c.name for c in checks}
    assert "env:.env" in names
    dotenv_check = next(c for c in checks if c.name == "env:.env")
    assert dotenv_check.level == "FAIL"


def test_check_env_passes_with_llm_key(monkeypatch, tmp_path) -> None:
    from gateway import doctor

    monkeypatch.setattr(doctor, "ROOT", tmp_path)
    (tmp_path / ".env").write_text("ANTHROPIC_API_KEY=sk-test\n", encoding="utf-8")
    checks = doctor._check_env({"ANTHROPIC_API_KEY": "sk-test"})
    llm_check = next(c for c in checks if c.name == "env:llm_key")
    assert llm_check.level == "PASS"


def test_check_env_fails_without_any_llm_key(monkeypatch, tmp_path) -> None:
    from gateway import doctor

    monkeypatch.setattr(doctor, "ROOT", tmp_path)
    (tmp_path / ".env").write_text("GATEWAY_SECRET=x\n", encoding="utf-8")
    checks = doctor._check_env({"GATEWAY_SECRET": "x"})
    llm_check = next(c for c in checks if c.name == "env:llm_key")
    assert llm_check.level == "FAIL"


def test_check_env_warns_when_telegram_token_missing(monkeypatch, tmp_path) -> None:
    from gateway import doctor

    monkeypatch.setattr(doctor, "ROOT", tmp_path)
    (tmp_path / ".env").write_text("OPENROUTER_API_KEY=set\n", encoding="utf-8")
    checks = doctor._check_env({"OPENROUTER_API_KEY": "set"})
    tg = next(c for c in checks if c.name == "env:telegram_token")
    assert tg.level == "WARN"


def test_check_env_passes_when_telegram_token_set(monkeypatch, tmp_path) -> None:
    from gateway import doctor

    monkeypatch.setattr(doctor, "ROOT", tmp_path)
    (tmp_path / ".env").write_text("OPENROUTER_API_KEY=set\n", encoding="utf-8")
    checks = doctor._check_env({"OPENROUTER_API_KEY": "set", "TELEGRAM_BOT_TOKEN": "123:ABC"})
    tg = next(c for c in checks if c.name == "env:telegram_token")
    assert tg.level == "PASS"


# --- _check_services ---

def test_check_services_fails_when_gateway_unreachable(monkeypatch) -> None:
    from gateway import doctor

    monkeypatch.setattr(doctor, "_http_ok", lambda *a, **k: False)
    checks = doctor._check_services({"GATEWAY_PORT": "8000", "LITELLM_PORT": "8001"})
    gw = next(c for c in checks if c.name == "service:gateway")
    assert gw.level == "FAIL"


def test_check_services_passes_when_gateway_reachable(monkeypatch) -> None:
    from gateway import doctor

    monkeypatch.setattr(doctor, "_http_ok", lambda *a, **k: True)
    checks = doctor._check_services({"GATEWAY_PORT": "8000", "LITELLM_PORT": "8001"})
    gw = next(c for c in checks if c.name == "service:gateway")
    assert gw.level == "PASS"


def test_check_services_uses_env_gateway_port(monkeypatch) -> None:
    from gateway import doctor

    seen: list[str] = []
    monkeypatch.setattr(doctor, "_http_ok", lambda url, **k: (seen.append(url), True)[1])
    doctor._check_services({"GATEWAY_PORT": "9999", "LITELLM_PORT": "8001"})
    assert any("9999" in u for u in seen)


def test_check_services_fails_when_litellm_unreachable(monkeypatch) -> None:
    from gateway import doctor

    def selective(url: str, **kwargs) -> bool:
        return "8000" in url  # gateway ok, LiteLLM fails

    monkeypatch.setattr(doctor, "_http_ok", selective)
    checks = doctor._check_services({"GATEWAY_PORT": "8000", "LITELLM_PORT": "8001"})
    ll = next(c for c in checks if c.name == "service:litellm")
    assert ll.level == "FAIL"


# --- _check_chromadb ---

def test_check_chromadb_fails_on_import_error(monkeypatch) -> None:
    from gateway import doctor

    with patch.dict(sys.modules, {"chromadb": None}):
        checks = doctor._check_chromadb()
    assert checks[0].level == "FAIL"
    assert "chromadb" in checks[0].name


def test_check_chromadb_fails_on_client_exception(monkeypatch, tmp_path) -> None:
    from gateway import doctor

    monkeypatch.setattr(doctor, "ROOT", tmp_path)

    import chromadb as _chroma
    with patch.object(_chroma, "PersistentClient", side_effect=RuntimeError("locked")):
        checks = doctor._check_chromadb()
    assert checks[0].level == "FAIL"
    assert "locked" in checks[0].detail


def test_check_chromadb_passes_when_working(monkeypatch, tmp_path) -> None:
    from gateway import doctor

    monkeypatch.setattr(doctor, "ROOT", tmp_path)

    import chromadb as _chroma
    fake_client = MagicMock()
    fake_client.list_collections.return_value = ["col1", "col2"]
    with patch.object(_chroma, "PersistentClient", return_value=fake_client):
        checks = doctor._check_chromadb()
    assert checks[0].level == "PASS"
    assert "2" in checks[0].detail


# --- _check_mem0 ---

def test_check_mem0_passes_when_api_key_set() -> None:
    from gateway import doctor

    checks = doctor._check_mem0({"MEM0_API_KEY": "m0-abc"})
    assert checks[0].level == "PASS"
    assert "API key" in checks[0].detail


def test_check_mem0_fails_on_import_error() -> None:
    from gateway import doctor

    with patch.dict(sys.modules, {"mem0": None}):
        checks = doctor._check_mem0({})
    assert checks[0].level == "FAIL"


def test_check_mem0_warns_on_init_exception() -> None:
    import mem0 as _mem0

    from gateway import doctor
    with patch.object(_mem0, "Memory", side_effect=RuntimeError("config error")):
        checks = doctor._check_mem0({})
    assert checks[0].level == "WARN"
    assert "config error" in checks[0].detail


def test_check_mem0_passes_local_mode() -> None:
    import mem0 as _mem0

    from gateway import doctor
    with patch.object(_mem0, "Memory", return_value=MagicMock()):
        checks = doctor._check_mem0({})
    assert checks[0].level == "PASS"
    assert "local" in checks[0].detail


# --- _check_disk ---

def _fake_disk_usage(free_bytes: int):
    from collections import namedtuple
    DU = namedtuple("DU", ["total", "used", "free"])
    return lambda _: DU(total=100 << 30, used=(100 << 30) - free_bytes, free=free_bytes)


def test_check_disk_passes_when_sufficient(monkeypatch, tmp_path) -> None:
    import shutil

    from gateway import doctor

    monkeypatch.setattr(doctor, "ROOT", tmp_path)
    monkeypatch.setattr(shutil, "disk_usage", _fake_disk_usage(10 << 30))
    checks = doctor._check_disk()
    assert checks[0].level == "PASS"


def test_check_disk_warns_when_low(monkeypatch, tmp_path) -> None:
    import shutil

    from gateway import doctor

    monkeypatch.setattr(doctor, "ROOT", tmp_path)
    monkeypatch.setattr(shutil, "disk_usage", _fake_disk_usage(int(1.0 * 1024 ** 3)))
    checks = doctor._check_disk()
    assert checks[0].level == "WARN"


def test_check_disk_fails_when_critically_low(monkeypatch, tmp_path) -> None:
    import shutil

    from gateway import doctor

    monkeypatch.setattr(doctor, "ROOT", tmp_path)
    monkeypatch.setattr(shutil, "disk_usage", _fake_disk_usage(int(0.2 * 1024 ** 3)))
    checks = doctor._check_disk()
    assert checks[0].level == "FAIL"


# --- _check_venv ---

def test_check_venv_passes_when_exists(monkeypatch, tmp_path) -> None:
    from gateway import doctor

    monkeypatch.setattr(doctor, "ROOT", tmp_path)
    venv_bin = tmp_path / "venv" / "bin"
    venv_bin.mkdir(parents=True)
    (venv_bin / "python").touch()
    checks = doctor._check_venv()
    assert checks[0].level == "PASS"


def test_check_venv_fails_when_missing(monkeypatch, tmp_path) -> None:
    from gateway import doctor

    monkeypatch.setattr(doctor, "ROOT", tmp_path)
    checks = doctor._check_venv()
    assert checks[0].level == "FAIL"


# --- main() exit codes ---

def test_main_exits_nonzero_on_failure(monkeypatch, tmp_path) -> None:
    """main() returns 1 when any FAIL check exists."""
    from gateway import doctor

    monkeypatch.setattr(doctor, "ROOT", tmp_path)  # no .env → FAIL

    def _all_pass(*_a, **_k):
        return [doctor.Check("PASS", "service:gateway", "ok")]

    monkeypatch.setattr(doctor, "_check_services", _all_pass)
    monkeypatch.setattr(doctor, "_check_chromadb", lambda: [doctor.Check("PASS", "store:chromadb", "ok")])
    monkeypatch.setattr(doctor, "_check_mem0", lambda _e: [doctor.Check("PASS", "store:mem0", "ok")])
    monkeypatch.setattr(doctor, "_check_disk", lambda: [doctor.Check("PASS", "disk:data_dir", "ok")])
    monkeypatch.setattr(doctor, "_check_venv", lambda: [doctor.Check("PASS", "runtime:venv", "ok")])

    import sys
    sys_argv_orig = sys.argv
    sys.argv = ["doctor"]
    try:
        rc = doctor.main()
    finally:
        sys.argv = sys_argv_orig

    assert rc == 1


def test_main_exits_zero_on_all_pass(monkeypatch, tmp_path) -> None:
    """main() returns 0 when all checks pass."""
    from gateway import doctor

    monkeypatch.setattr(doctor, "ROOT", tmp_path)
    (tmp_path / ".env").write_text(
        "OPENROUTER_API_KEY=sk\nGATEWAY_SECRET=x\nTELEGRAM_BOT_TOKEN=123\n",
        encoding="utf-8",
    )

    pass_check = doctor.Check("PASS", "x", "ok")
    monkeypatch.setattr(doctor, "_check_services", lambda _e: [pass_check])
    monkeypatch.setattr(doctor, "_check_chromadb", lambda: [pass_check])
    monkeypatch.setattr(doctor, "_check_mem0", lambda _e: [pass_check])
    monkeypatch.setattr(doctor, "_check_disk", lambda: [pass_check])
    monkeypatch.setattr(doctor, "_check_venv", lambda: [doctor.Check("PASS", "runtime:venv", "ok")])

    import sys
    sys_argv_orig = sys.argv
    sys.argv = ["doctor"]
    try:
        rc = doctor.main()
    finally:
        sys.argv = sys_argv_orig

    assert rc == 0


def test_main_strict_fails_on_warn(monkeypatch, tmp_path) -> None:
    """--strict makes WARN checks count as failure."""
    from gateway import doctor

    monkeypatch.setattr(doctor, "ROOT", tmp_path)
    (tmp_path / ".env").write_text("OPENROUTER_API_KEY=sk\n", encoding="utf-8")

    doctor.Check("WARN", "env:gateway_secret", "not set")
    pass_check = doctor.Check("PASS", "x", "ok")
    monkeypatch.setattr(doctor, "_check_services", lambda _e: [pass_check])
    monkeypatch.setattr(doctor, "_check_chromadb", lambda: [pass_check])
    monkeypatch.setattr(doctor, "_check_mem0", lambda _e: [pass_check])
    monkeypatch.setattr(doctor, "_check_disk", lambda: [pass_check])
    monkeypatch.setattr(doctor, "_check_venv", lambda: [doctor.Check("PASS", "runtime:venv", "ok")])

    import sys
    sys_argv_orig = sys.argv
    sys.argv = ["doctor", "--strict"]
    try:
        rc = doctor.main()
    finally:
        sys.argv = sys_argv_orig

    # env checks produce a WARN for gateway_secret when not set
    assert rc == 1


def test_main_json_output_shape(monkeypatch, tmp_path, capsys) -> None:
    """--json emits valid JSON with summary + checks keys."""
    from gateway import doctor

    monkeypatch.setattr(doctor, "ROOT", tmp_path)
    (tmp_path / ".env").write_text(
        "OPENROUTER_API_KEY=sk\nGATEWAY_SECRET=x\nTELEGRAM_BOT_TOKEN=123\n",
        encoding="utf-8",
    )

    pass_check = doctor.Check("PASS", "x", "ok")
    monkeypatch.setattr(doctor, "_check_services", lambda _e: [pass_check])
    monkeypatch.setattr(doctor, "_check_chromadb", lambda: [pass_check])
    monkeypatch.setattr(doctor, "_check_mem0", lambda _e: [pass_check])
    monkeypatch.setattr(doctor, "_check_disk", lambda: [pass_check])
    monkeypatch.setattr(doctor, "_check_venv", lambda: [doctor.Check("PASS", "runtime:venv", "ok")])

    import sys
    sys_argv_orig = sys.argv
    sys.argv = ["doctor", "--json"]
    try:
        doctor.main()
    finally:
        sys.argv = sys_argv_orig

    out = capsys.readouterr().out
    payload = json.loads(out)
    assert "summary" in payload
    assert "checks" in payload
    assert "pass" in payload["summary"]
    assert "fail" in payload["summary"]
    assert isinstance(payload["checks"], list)
    for c in payload["checks"]:
        assert "level" in c
        assert "name" in c
        assert "detail" in c
