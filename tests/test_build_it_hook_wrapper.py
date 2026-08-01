"""Tests for .claude/hooks/build-it-hook.sh.

The wrapper resolves the installed build-it plugin at run time instead of
hardcoding a cache path into .claude/settings.json. These tests stub the cache
under a fake HOME, so they pass whether or not the plugin is actually installed.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / ".claude" / "hooks" / "build-it-hook.sh"

STDIN_PAYLOAD = '{"tool_input": {"file_path": "x"}}'


def _run(hook_name: str | None, home: Path, cwd: Path) -> subprocess.CompletedProcess[str]:
    args = ["bash", str(WRAPPER)]
    if hook_name is not None:
        args.append(hook_name)
    return subprocess.run(
        args,
        input=STDIN_PAYLOAD,
        capture_output=True,
        text=True,
        cwd=cwd,
        env={"HOME": str(home), "PATH": "/usr/bin:/bin:/usr/local/bin"},
    )


def _install_stub(home: Path, version: str, body: str, name: str = "stub.py") -> Path:
    hooks_dir = home / ".claude/plugins/cache/build-it/build-it" / version / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    script = hooks_dir / name
    script.write_text(body, encoding="utf-8")
    return script


def _log_text(cwd: Path) -> str:
    log = cwd / ".taskstate" / "hooks.log"
    return log.read_text(encoding="utf-8") if log.exists() else ""


def test_runs_the_resolved_hook_and_passes_stdin_through(tmp_path: Path) -> None:
    home, cwd = tmp_path / "home", tmp_path / "cwd"
    cwd.mkdir()
    _install_stub(home, "1.0.0", "import sys; print(sys.stdin.read(), end='')\n")

    result = _run("stub.py", home, cwd)

    assert result.returncode == 0
    assert result.stdout == STDIN_PAYLOAD


def test_propagates_a_blocking_exit_code(tmp_path: Path) -> None:
    """A real gate must still be able to block; the wrapper only fails open when
    it cannot find the plugin."""
    home, cwd = tmp_path / "home", tmp_path / "cwd"
    cwd.mkdir()
    _install_stub(home, "1.0.0", "import sys; print('denied'); sys.exit(2)\n")

    result = _run("stub.py", home, cwd)

    assert result.returncode == 2
    assert "denied" in result.stdout


def test_picks_the_highest_installed_version(tmp_path: Path) -> None:
    home, cwd = tmp_path / "home", tmp_path / "cwd"
    cwd.mkdir()
    for version in ("3.1.1", "3.2.0", "3.10.0"):
        _install_stub(home, version, f"print({version.split('.')[1]!r})\n")

    result = _run("stub.py", home, cwd)

    assert result.returncode == 0
    assert result.stdout.strip() == "10"


def test_fails_open_when_plugin_is_not_installed(tmp_path: Path) -> None:
    home, cwd = tmp_path / "home", tmp_path / "cwd"
    home.mkdir()
    cwd.mkdir()

    result = _run("evidence-lint.py", home, cwd)

    assert result.returncode == 0
    assert result.stdout == ""
    assert "plugin not installed" in _log_text(cwd)


def test_fails_open_when_hook_file_is_missing(tmp_path: Path) -> None:
    home, cwd = tmp_path / "home", tmp_path / "cwd"
    cwd.mkdir()
    _install_stub(home, "1.0.0", "print('unused')\n")

    result = _run("does-not-exist.py", home, cwd)

    assert result.returncode == 0
    assert result.stdout == ""
    assert "not found" in _log_text(cwd)


def test_fails_open_when_no_hook_name_is_given(tmp_path: Path) -> None:
    home, cwd = tmp_path / "home", tmp_path / "cwd"
    home.mkdir()
    cwd.mkdir()

    result = _run(None, home, cwd)

    assert result.returncode == 0
    assert "no hook name given" in _log_text(cwd)


def test_skip_survives_an_unwritable_log_directory(tmp_path: Path) -> None:
    """Logging must never be what breaks the hook chain."""
    home, cwd = tmp_path / "home", tmp_path / "cwd"
    home.mkdir()
    cwd.mkdir()
    (cwd / ".taskstate").write_text("not a directory", encoding="utf-8")

    result = _run("evidence-lint.py", home, cwd)

    assert result.returncode == 0


def test_settings_wires_both_gates_after_kitty_hooks() -> None:
    """Kitty's own hooks must evaluate before the third-party gates."""
    import json

    settings = json.loads((ROOT / ".claude/settings.json").read_text(encoding="utf-8"))

    pre_tool_use = settings["hooks"]["PreToolUse"]
    commands = [h["command"] for group in pre_tool_use for h in group["hooks"]]
    evidence_lint = next(i for i, c in enumerate(commands) if "evidence-lint.py" in c)
    assert all(commands.index(c) < evidence_lint for c in commands if "scan-secrets.sh" in c)

    stop_commands = [h["command"] for group in settings["hooks"]["Stop"] for h in group["hooks"]]
    assert stop_commands.index("bash .claude/hooks/session-stop.sh") < next(
        i for i, c in enumerate(stop_commands) if "turn-end-gate.py" in c
    )
