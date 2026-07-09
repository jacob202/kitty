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


# --- _check_env_parse ---


def test_env_parse_passes_on_clean_file(tmp_path) -> None:
    from gateway import doctor

    dotenv = tmp_path / ".env"
    dotenv.write_text("# comment\n\nKEY=value\nexport OTHER=x\nQUOTED=\"y\"\n", encoding="utf-8")
    checks = doctor._check_env_parse(dotenv)
    assert checks[0].name == "env:parse"
    assert checks[0].level == "PASS"


def test_env_parse_flags_stray_quote_line_with_number(tmp_path) -> None:
    # The exact live failure from 2026-07-05: a leading quote on line 1.
    from gateway import doctor

    dotenv = tmp_path / ".env"
    dotenv.write_text("'# Local-only secrets file\nGOOD=1\n", encoding="utf-8")
    checks = doctor._check_env_parse(dotenv)
    assert checks[0].level == "WARN"
    assert "line(s) at 1" in checks[0].detail


def test_env_parse_flags_line_without_equals(tmp_path) -> None:
    from gateway import doctor

    dotenv = tmp_path / ".env"
    dotenv.write_text("GOOD=1\nthis is not an assignment\n", encoding="utf-8")
    checks = doctor._check_env_parse(dotenv)
    assert checks[0].level == "WARN"
    assert "line(s) at 2" in checks[0].detail


def test_env_parse_runs_as_part_of_check_env(monkeypatch, tmp_path) -> None:
    from gateway import doctor

    monkeypatch.setattr(doctor, "ROOT", tmp_path)
    (tmp_path / ".env").write_text("OPENROUTER_API_KEY=set\n", encoding="utf-8")
    checks = doctor._check_env({"OPENROUTER_API_KEY": "set"})
    assert any(c.name == "env:parse" for c in checks)


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
    monkeypatch.setattr(shutil, "disk_usage", _fake_disk_usage(int(1.0 * 1024**3)))
    checks = doctor._check_disk()
    assert checks[0].level == "WARN"


def test_check_disk_fails_when_critically_low(monkeypatch, tmp_path) -> None:
    import shutil

    from gateway import doctor

    monkeypatch.setattr(doctor, "ROOT", tmp_path)
    monkeypatch.setattr(shutil, "disk_usage", _fake_disk_usage(int(0.2 * 1024**3)))
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
    monkeypatch.setattr(
        doctor, "_check_chromadb", lambda: [doctor.Check("PASS", "store:chromadb", "ok")]
    )
    monkeypatch.setattr(
        doctor, "_check_mem0", lambda _e: [doctor.Check("PASS", "store:mem0", "ok")]
    )
    monkeypatch.setattr(
        doctor, "_check_disk", lambda: [doctor.Check("PASS", "disk:data_dir", "ok")]
    )
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


# --- _check_mail_connector (P3, docs/packets/005) ---


def test_check_mail_connector_warn_when_token_missing(monkeypatch, tmp_path):
    from gateway import doctor

    monkeypatch.setattr(doctor, "ROOT", tmp_path)
    checks = doctor._check_mail_connector({})
    assert len(checks) == 1
    assert checks[0].level == "WARN"
    assert checks[0].name == "connector:mail"
    assert "not present" in checks[0].detail


def test_check_mail_connector_fail_when_token_unreadable(monkeypatch, tmp_path):
    from gateway import doctor
    from gateway.connectors import mail as mail_module

    token = tmp_path / "broken.json"
    token.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(doctor, "ROOT", tmp_path)
    monkeypatch.setenv("GMAIL_TOKEN_FILE", str(token))

    def _raise():
        raise mail_module.MailAuthError("malformed token")

    monkeypatch.setattr(mail_module, "_load_credentials", _raise)
    checks = doctor._check_mail_connector({"GMAIL_TOKEN_FILE": str(token)})
    assert checks[0].level == "FAIL"
    assert "unreadable" in checks[0].detail


def test_check_mail_connector_pass_when_token_loadable(monkeypatch, tmp_path):
    from gateway import doctor
    from gateway.connectors import mail as mail_module

    token = tmp_path / "ok.json"
    token.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(doctor, "ROOT", tmp_path)
    monkeypatch.setenv("GMAIL_TOKEN_FILE", str(token))
    fake_creds = type("FakeCreds", (), {"valid": True, "expired": False, "refresh_token": "r"})()
    monkeypatch.setattr(mail_module, "_load_credentials", lambda: fake_creds)
    checks = doctor._check_mail_connector({"GMAIL_TOKEN_FILE": str(token)})
    assert checks[0].level == "PASS"
    assert "ok.json" in checks[0].detail


def test_check_mail_connector_fail_when_expired_no_refresh(monkeypatch, tmp_path):
    from gateway import doctor
    from gateway.connectors import mail as mail_module

    token = tmp_path / "expired.json"
    token.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(doctor, "ROOT", tmp_path)
    monkeypatch.setenv("GMAIL_TOKEN_FILE", str(token))
    fake_creds = type("FakeCreds", (), {"valid": False, "expired": True, "refresh_token": None})()
    monkeypatch.setattr(mail_module, "_load_credentials", lambda: fake_creds)
    checks = doctor._check_mail_connector({"GMAIL_TOKEN_FILE": str(token)})
    assert checks[0].level == "FAIL"
    assert "re-authorize" in checks[0].detail


# --- _check_push_channel (P3, docs/packets/015) ---


def test_check_push_channel_warn_when_nothing_configured(monkeypatch, tmp_path):
    from gateway import doctor, push

    monkeypatch.setattr(push, "PUSH_LOG_FILE", tmp_path / "push_log.jsonl")
    checks = doctor._check_push_channel({})
    assert checks[0].level == "WARN"
    assert "no channel configured" in checks[0].detail


def test_check_push_channel_pass_when_configured_with_no_attempts(monkeypatch, tmp_path):
    from gateway import doctor, push

    monkeypatch.setattr(push, "PUSH_LOG_FILE", tmp_path / "push_log.jsonl")
    checks = doctor._check_push_channel({"PUSH_IMESSAGE_RECIPIENT": "+15551234567"})
    assert checks[0].level == "PASS"
    assert "no attempts logged yet" in checks[0].detail


def test_check_push_channel_pass_when_last_attempt_succeeded(monkeypatch, tmp_path):
    from gateway import doctor, push

    log = tmp_path / "push_log.jsonl"
    log.write_text(
        '{"ts": 1, "kind": "info", "title": "Kitty", "channel": "imessage", "ok": false, "dedupe_key": null}\n'
        '{"ts": 2, "kind": "info", "title": "Kitty", "channel": "pushover", "ok": true, "dedupe_key": null}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(push, "PUSH_LOG_FILE", log)
    checks = doctor._check_push_channel({"PUSHOVER_USER_KEY": "u", "PUSHOVER_API_TOKEN": "t"})
    assert checks[0].level == "PASS"
    assert "pushover" in checks[0].detail


def test_check_push_channel_fail_when_last_attempt_failed(monkeypatch, tmp_path):
    from gateway import doctor, push

    log = tmp_path / "push_log.jsonl"
    log.write_text(
        '{"ts": 1, "kind": "info", "title": "Kitty", "channel": "imessage", "ok": false, "dedupe_key": null}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(push, "PUSH_LOG_FILE", log)
    checks = doctor._check_push_channel({"PUSH_IMESSAGE_RECIPIENT": "+15551234567"})
    assert checks[0].level == "FAIL"
    assert "imessage" in checks[0].detail


def test_check_deadlines_warn_when_none_open(monkeypatch, tmp_path):
    from gateway import db, deadline_store, doctor, paths, push

    db_file = tmp_path / "kitty.db"
    monkeypatch.setattr(deadline_store, "DEADLINES_DB_FILE", db_file)
    monkeypatch.setattr(db, "KITTY_DB_FILE", db_file)
    monkeypatch.setattr(paths, "KITTY_DB_FILE", db_file)
    monkeypatch.setattr(push, "PUSH_LOG_FILE", tmp_path / "push_log.jsonl")
    deadline_store.init_db()
    checks = doctor._check_deadlines()
    assert checks[0].level == "WARN"
    assert "no open deadlines" in checks[0].detail


# --- _check_github_connector ---


def test_github_connector_passes_when_token_present(monkeypatch) -> None:
    from gateway import doctor

    checks = doctor._check_github_connector({"GITHUB_TOKEN": "ghp_abc123"})
    assert len(checks) == 1
    assert checks[0].level == "PASS"
    assert checks[0].name == "connector:github"
    assert "token present" in checks[0].detail


def test_github_connector_warns_when_token_missing(monkeypatch) -> None:
    from gateway import doctor

    checks = doctor._check_github_connector({})
    assert len(checks) == 1
    assert checks[0].level == "WARN"
    assert checks[0].detail == "GITHUB_TOKEN not present in environment or .env"


# --- _load_env ---


def test_load_env_returns_os_environ_when_no_dotenv(monkeypatch, tmp_path) -> None:
    from gateway import doctor

    monkeypatch.setattr(doctor, "ROOT", tmp_path)
    monkeypatch.setenv("TEST_VAR", "from_env")
    result = doctor._load_env()
    assert result["TEST_VAR"] == "from_env"


def test_load_env_reads_dotenv_values(monkeypatch, tmp_path) -> None:
    from gateway import doctor

    monkeypatch.setattr(doctor, "ROOT", tmp_path)
    (tmp_path / ".env").write_text(
        "MY_KEY=my_value\nANOTHER=123\n", encoding="utf-8"
    )
    result = doctor._load_env()
    assert result["MY_KEY"] == "my_value"
    assert result["ANOTHER"] == "123"


def test_load_env_skips_comments_and_empty_lines(monkeypatch, tmp_path) -> None:
    from gateway import doctor

    monkeypatch.setattr(doctor, "ROOT", tmp_path)
    (tmp_path / ".env").write_text(
        "# this is a comment\n\nKEY=val\n", encoding="utf-8"
    )
    result = doctor._load_env()
    assert result["KEY"] == "val"
    assert "# this is a comment" not in result


def test_load_env_uses_setdefault_not_override(monkeypatch, tmp_path) -> None:
    """Existing env vars take precedence over .env values."""
    from gateway import doctor

    monkeypatch.setattr(doctor, "ROOT", tmp_path)
    monkeypatch.setenv("EXISTING", "from_env")
    (tmp_path / ".env").write_text("EXISTING=from_dotenv\n", encoding="utf-8")
    result = doctor._load_env()
    assert result["EXISTING"] == "from_env"


def test_load_env_strips_quotes_from_values(monkeypatch, tmp_path) -> None:
    from gateway import doctor

    monkeypatch.setattr(doctor, "ROOT", tmp_path)
    (tmp_path / ".env").write_text('QUOTED="hello"\n', encoding="utf-8")
    result = doctor._load_env()
    assert result["QUOTED"] == "hello"


# --- _http_ok ---


def test_http_ok_returns_true_on_2xx() -> None:
    from unittest.mock import MagicMock, patch

    from gateway import doctor

    mock_resp = MagicMock()
    mock_resp.getcode.return_value = 200
    with patch("gateway.doctor.urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value = mock_resp
        assert doctor._http_ok("http://example.test/health") is True


def test_http_ok_returns_false_on_4xx() -> None:
    from unittest.mock import MagicMock, patch

    from gateway import doctor

    mock_resp = MagicMock()
    mock_resp.getcode.return_value = 404
    with patch("gateway.doctor.urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value = mock_resp
        assert doctor._http_ok("http://example.test/missing") is False


def test_http_ok_returns_false_on_connection_error() -> None:
    from unittest.mock import patch

    from gateway import doctor

    with patch("gateway.doctor.urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = ConnectionError("connection refused")
        assert doctor._http_ok("http://example.test/down") is False


# --- _level_order ---


def test_level_order_correct_priority() -> None:
    from gateway import doctor

    assert doctor._level_order("PASS") == 0
    assert doctor._level_order("WARN") == 1
    assert doctor._level_order("FAIL") == 2


def test_level_order_unknown_defaults_to_fail() -> None:
    from gateway import doctor

    assert doctor._level_order("UNKNOWN") == 2
    assert doctor._level_order("") == 2
    assert doctor._level_order("INFO") == 2


def test_check_mail_connector_pass_with_expired_token_and_refresh(
    monkeypatch, tmp_path
) -> None:
    """Token expired but has a refresh_token — detail says 'refresh pending', level stays PASS."""
    from gateway import doctor
    from gateway.connectors import mail as mail_module

    token = tmp_path / "expired_refresh.json"
    token.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(doctor, "ROOT", tmp_path)
    monkeypatch.setenv("GMAIL_TOKEN_FILE", str(token))
    fake_creds = type("FakeCreds", (), {"valid": False, "expired": True, "refresh_token": "r"})()
    monkeypatch.setattr(mail_module, "_load_credentials", lambda: fake_creds)
    checks = doctor._check_mail_connector({"GMAIL_TOKEN_FILE": str(token)})
    assert checks[0].level == "PASS"
    assert "expired" in checks[0].detail


def test_check_deadlines_fail_on_last_push_failure(monkeypatch, tmp_path) -> None:
    from gateway import db, deadline_store, doctor, paths, push

    db_file = tmp_path / "kitty.db"
    monkeypatch.setattr(deadline_store, "DEADLINES_DB_FILE", db_file)
    monkeypatch.setattr(db, "KITTY_DB_FILE", db_file)
    monkeypatch.setattr(paths, "KITTY_DB_FILE", db_file)
    monkeypatch.setattr("gateway.project_store.PROJECTS_DB_FILE", db_file)
    monkeypatch.setattr("gateway.project_store.KITTY_DB_FILE", db_file)
    log = tmp_path / "push_log.jsonl"
    log.write_text(
        '{"ts": 1, "kind": "info", "title": "Kitty", "channel": "pushover", '
        '"ok": false, "dedupe_key": "deadline-proj-a"}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(push, "PUSH_LOG_FILE", log)
    deadline_store.init_db()
    from gateway import project_store
    project_store.create("benefits-admin", "admin")
    deadline_store.upsert({
        "project_id": 2, "source": "test", "due_date": "2026-08-01",
        "obligation": "x", "confidence": "high",
    })
    checks = doctor._check_deadlines()
    assert checks[0].level == "FAIL"
    assert "failed" in checks[0].detail


def test_check_deadlines_pass_when_open_and_no_pushes_yet(monkeypatch, tmp_path):
    from gateway import db, deadline_store, doctor, paths, push

    db_file = tmp_path / "kitty.db"
    monkeypatch.setattr(deadline_store, "DEADLINES_DB_FILE", db_file)
    monkeypatch.setattr(db, "KITTY_DB_FILE", db_file)
    monkeypatch.setattr(paths, "KITTY_DB_FILE", db_file)
    monkeypatch.setattr(push, "PUSH_LOG_FILE", tmp_path / "push_log.jsonl")
    monkeypatch.setattr("gateway.project_store.PROJECTS_DB_FILE", db_file)
    monkeypatch.setattr("gateway.project_store.KITTY_DB_FILE", db_file)
    deadline_store.init_db()
    from gateway import project_store
    project_store.create("benefits-admin", "admin")
    deadline_store.upsert({"project_id": 2, "source": "test", "due_date": "2026-08-01", "obligation": "x", "confidence": "high"})
    checks = doctor._check_deadlines()
    assert checks[0].level == "PASS"
    assert "no pushes yet" in checks[0].detail
