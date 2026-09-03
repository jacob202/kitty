"""Behavioral tests for scripts/resume.py without live external dependencies."""
from __future__ import annotations

import datetime as dt
import importlib.util
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "resume.py"


def _load_resume_module():
    spec = importlib.util.spec_from_file_location("kitty_resume_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def resume_module():
    return _load_resume_module()


def test_script_file_present():
    assert SCRIPT.is_file()


def test_script_is_valid_python():
    result = subprocess.run(
        [sys.executable, "-m", "py_compile", str(SCRIPT)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_open_prs_formats_api_result_without_live_github(resume_module, monkeypatch):
    response = subprocess.CompletedProcess(
        args=["gh"],
        returncode=0,
        stdout='[{"number":42,"title":"Harden tests","state":"OPEN"}]',
        stderr="",
    )
    monkeypatch.setattr(resume_module, "run", lambda _cmd, _timeout: response)

    assert resume_module.open_prs() == ["#42 Harden tests"]


def test_main_prints_orientation_from_probe_results(resume_module, monkeypatch, capsys):
    class FrozenDate(dt.date):
        @classmethod
        def today(cls):
            return cls(2026, 8, 23)

    monkeypatch.setattr(resume_module, "dt", SimpleNamespace(date=FrozenDate))
    monkeypatch.setattr(resume_module, "open_prs", lambda: ["#42 Harden tests"])
    monkeypatch.setattr(resume_module, "test_count", lambda: "4716/4716 tests collected")
    monkeypatch.setattr(resume_module, "doctor_summary", lambda: "pass=9 warn=1 fail=0")
    monkeypatch.setattr(resume_module, "branch_state", lambda: ("audit/tests", True))
    monkeypatch.setattr(
        resume_module, "packet_state", lambda: ("123 Fix tests", ["124 Blocked"])
    )
    monkeypatch.setattr(
        resume_module, "local_only_branches", lambda _current: ["local-only"]
    )
    monkeypatch.setattr(resume_module, "last_session_note", lambda: "session.md")

    assert resume_module.main() == 0

    # resume.py's sectioned output intentionally carries ANSI styling on all
    # streams (see the ANSI helpers in scripts/resume.py), so the golden
    # string includes the escape codes.
    B, C, R, G, Y = "\x1b[1m", "\x1b[96m", "\x1b[0m", "\x1b[92m", "\x1b[93m"
    assert capsys.readouterr().out == (
        f"{B}Kitty{R} — 2026-08-23\n"
        f"\n{B}{C}Git{R}\n{C}───{R}\n"
        f"  Branch:  audit/tests {Y}[dirty]{R}\n"
        f"  Open PRs:  #42 Harden tests\n"
        f"\n{B}{C}Tests{R}\n{C}─────{R}\n"
        f"  Collected:  \x1b[91m✗{R} 4716/4716 tests collected\n"
        f"\n{B}{C}Services{R}\n{C}────────{R}\n"
        f"  Checks:  {G}9 pass{R}, {Y}1 warn{R}, 0 fail\n"
        f"\n{B}{C}Packets{R}\n{C}───────{R}\n"
        f"  Active:   123 Fix tests\n"
        f"  Blocked:  124 Blocked\n"
        f"\n{B}{C}Workspace{R}\n{C}─────────{R}\n"
        f"  Local-only:    local-only\n"
        f"  Last session:  session.md\n"
    )
