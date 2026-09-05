"""Unit tests for TL-02: gateway process freshness check."""
import subprocess
import time
from pathlib import Path

from gateway import doctor
from gateway.doctor import _check_gateway_freshness


def test_warns_when_process_predates_source():
    now = time.time()
    process_start = now - 120  # started 2 minutes ago
    source_mtime = now - 30    # source changed 30 seconds ago

    checks = _check_gateway_freshness(process_start=process_start, source_mtime=source_mtime)

    assert len(checks) == 1
    assert checks[0].level == "WARN"
    assert checks[0].name == "runtime:gateway_freshness"
    assert "restart" in checks[0].detail


def test_passes_when_process_is_newer_than_source():
    now = time.time()
    process_start = now - 10   # started 10 seconds ago
    source_mtime = now - 120   # source last touched 2 minutes ago

    checks = _check_gateway_freshness(process_start=process_start, source_mtime=source_mtime)

    assert len(checks) == 1
    assert checks[0].level == "PASS"
    assert checks[0].name == "runtime:gateway_freshness"


def test_passes_when_gateway_not_running():
    checks = _check_gateway_freshness(process_start=None, source_mtime=time.time())

    assert len(checks) == 1
    assert checks[0].level == "PASS"
    assert "not running" in checks[0].detail


def test_passes_when_source_mtime_equals_process_start():
    ts = time.time() - 60
    checks = _check_gateway_freshness(process_start=ts, source_mtime=ts)

    assert checks[0].level == "PASS"


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def _ui_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    source = root / "gateway" / "kitty-chat" / "src" / "components"
    source.mkdir(parents=True)
    (source / "Nested.tsx").write_text("export const value = 1\n")
    (root / "gateway" / "kitty-chat" / ".gitignore").write_text(".next/\n")
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Kitty Test")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "fixture")
    next_dir = root / "gateway" / "kitty-chat" / ".next"
    next_dir.mkdir()
    (next_dir / "BUILD_ID").write_text("build\n")
    (next_dir / "KITTY_SOURCE_SHA").write_text(_git(root, "rev-parse", "HEAD") + "\n")
    return root


def test_ui_build_provenance_rejects_nested_dirty_edit(tmp_path):
    root = _ui_repo(tmp_path)
    nested = root / "gateway" / "kitty-chat" / "src" / "components" / "Nested.tsx"
    nested.write_text("export const value = 2\n")

    result = doctor._ui_build_provenance(root)

    assert result["state"] == "stale"
    assert result["source_state"] == "dirty"


def test_ui_build_provenance_marks_dirty_build_unverifiable(tmp_path):
    root = _ui_repo(tmp_path)
    sha = _git(root, "rev-parse", "HEAD")
    stamp = root / "gateway" / "kitty-chat" / ".next" / "KITTY_SOURCE_SHA"
    stamp.write_text(f"dirty:{sha}\n")

    result = doctor._ui_build_provenance(root)

    assert result["state"] == "dirty-built"
    assert result["build_source"] == f"dirty:{sha}"


def test_gateway_probe_detects_uvicorn_listener_without_proc(monkeypatch, tmp_path):
    class Result:
        def __init__(self, stdout: str = "", returncode: int = 0):
            self.stdout = stdout
            self.stderr = ""
            self.returncode = returncode

    def fake_run(args, **_kwargs):
        command = tuple(args)
        if command[:2] == ("lsof", "-tiTCP:8000"):
            return Result("4321\n")
        if command == ("ps", "-p", "4321", "-o", "command="):
            return Result("python -m uvicorn gateway.app:app --host 127.0.0.1 --port 8000\n")
        if command == ("lsof", "-a", "-p", "4321", "-d", "cwd", "-Fn"):
            return Result(f"p4321\nfcwd\nn{tmp_path}\n")
        if command == ("ps", "-p", "4321", "-o", "lstart="):
            return Result("Sat Sep  5 10:00:00 2026\n")
        raise AssertionError(command)

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = doctor._gateway_process_info(port=8000)

    assert result["state"] == "running"
    assert result["pid"] == 4321
    assert result["cwd"] == str(tmp_path)
    assert "gateway.app:app" in result["command"]
    assert result["start_time"] is not None


def test_gateway_probe_failure_is_warn_not_false_not_running(monkeypatch):
    monkeypatch.setattr(doctor, "_gateway_process_info", lambda **_kwargs: {"state": "unknown", "error": "lsof failed"})

    checks = _check_gateway_freshness(source_mtime=time.time())

    assert checks[0].level == "WARN"
    assert "unverifiable" in checks[0].detail


def test_ui_runtime_provenance_uses_the_listener_worktree(monkeypatch, tmp_path):
    root = _ui_repo(tmp_path)
    runtime_cwd = root / "gateway" / "kitty-chat" / ".next" / "standalone"
    runtime_cwd.mkdir(parents=True)
    monkeypatch.setattr(
        doctor,
        "_listener_process_info",
        lambda **_kwargs: {
            "state": "running",
            "pid": 55,
            "cwd": str(runtime_cwd),
            "command": "next-server (v16.3.0)",
            "start_time": time.time(),
        },
        raising=False,
    )

    result = doctor._ui_runtime_provenance(port=4000)

    assert result["state"] == "checkout-current"
    assert result["build_id"] == "build"
    assert result["runtime_root"] == str(root)
    assert result["runtime_pid"] == "55"


def test_doctor_ui_check_reports_shared_runtime_build_state(monkeypatch):
    monkeypatch.setattr(
        doctor,
        "_ui_runtime_provenance",
        lambda *_args, **_kwargs: {
            "state": "stale",
            "build_source": "abc",
            "source_sha": "def",
            "source_state": "dirty",
            "runtime_root": "/tmp/kitty",
            "runtime_pid": "55",
        },
        raising=False,
    )

    checks = doctor._check_ui_build_provenance()

    assert checks[0].level == "WARN"
    assert checks[0].name == "runtime:ui_build_provenance"
    assert "stale" in checks[0].detail
    assert "/tmp/kitty" in checks[0].detail


def test_gateway_probe_rejects_unrelated_command_that_mentions_gateway_target(monkeypatch):
    monkeypatch.setattr(
        doctor,
        "_listener_process_info",
        lambda **_kwargs: {
            "state": "running",
            "pid": 4321,
            "cwd": "/tmp",
            "command": "python fake.py --note gateway.app:app",
            "start_time": time.time(),
        },
    )

    result = doctor._gateway_process_info(port=8000)

    assert result["state"] == "running-unverifiable"
    assert "not the Kitty gateway" in result["error"]


def test_ui_runtime_provenance_rejects_unrelated_listener_inside_repo(monkeypatch, tmp_path):
    root = _ui_repo(tmp_path)
    runtime_cwd = root / "gateway" / "kitty-chat" / ".next" / "standalone"
    runtime_cwd.mkdir(parents=True)
    monkeypatch.setattr(
        doctor,
        "_listener_process_info",
        lambda **_kwargs: {
            "state": "running",
            "pid": 55,
            "cwd": str(runtime_cwd),
            "command": "python3 -m http.server 4000",
            "start_time": time.time(),
        },
    )

    result = doctor._ui_runtime_provenance(port=4000)

    assert result["state"] == "unknown"
    assert result["runtime_pid"] == "55"


def test_ui_runtime_provenance_rejects_next_server_outside_standalone_cwd(monkeypatch, tmp_path):
    root = _ui_repo(tmp_path)
    runtime_cwd = root / "gateway" / "kitty-chat"
    monkeypatch.setattr(
        doctor,
        "_listener_process_info",
        lambda **_kwargs: {
            "state": "running",
            "pid": 56,
            "cwd": str(runtime_cwd),
            "command": "next-server (v16.3.0)",
            "start_time": time.time(),
        },
    )

    result = doctor._ui_runtime_provenance(port=4000)

    assert result["state"] == "unknown"
    assert result["runtime_pid"] == "56"
