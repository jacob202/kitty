"""Tests for .claude/hooks/build-it-hook.sh.

The wrapper resolves the installed build-it plugin at run time from Claude
Code's installed_plugins.json ledger, instead of hardcoding a cache path into
.claude/settings.json or scanning the shared cache directory. These tests stub
the ledger under a fake HOME, so they pass whether or not the plugin is
actually installed.
"""

from __future__ import annotations

import json
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


def _install_stub(
    home: Path,
    version: str,
    body: str,
    name: str = "stub.py",
    scope: str = "project",
    project_path: Path | None = None,
) -> None:
    """Write a stub hook into the cache and record it in the plugin ledger."""
    install_path = home / ".claude/plugins/cache/build-it/build-it" / version
    (install_path / "hooks").mkdir(parents=True, exist_ok=True)
    (install_path / "hooks" / name).write_text(body, encoding="utf-8")

    ledger = home / ".claude/plugins/installed_plugins.json"
    payload = json.loads(ledger.read_text(encoding="utf-8")) if ledger.exists() else {"plugins": {}}
    entry = {"scope": scope, "installPath": str(install_path), "version": version}
    if project_path is not None:
        entry["projectPath"] = str(project_path)
    payload["plugins"].setdefault("build-it@build-it", []).append(entry)
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text(json.dumps(payload), encoding="utf-8")


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


def test_prefers_this_projects_install_over_a_newer_one_elsewhere(tmp_path: Path) -> None:
    """The shared cache holds every project's versions. Another project pulling a
    newer build-it must not make Kitty execute that release's hook code."""
    home, cwd = tmp_path / "home", tmp_path / "cwd"
    cwd.mkdir()
    _install_stub(home, "3.1.1", "print('ours')\n", project_path=cwd)
    _install_stub(home, "9.0.0", "print('someone-elses')\n", project_path=tmp_path / "other")

    result = _run("stub.py", home, cwd)

    assert result.returncode == 0
    assert result.stdout.strip() == "ours"


def test_falls_back_to_a_user_scope_install(tmp_path: Path) -> None:
    home, cwd = tmp_path / "home", tmp_path / "cwd"
    cwd.mkdir()
    _install_stub(home, "2.0.0", "print('user-scope')\n", scope="user")

    result = _run("stub.py", home, cwd)

    assert result.returncode == 0
    assert result.stdout.strip() == "user-scope"


def test_resolves_without_gnu_sort(tmp_path: Path) -> None:
    """macOS ships BSD sort, which has no -V. The old cache scan silently
    disabled both gates there; ledger lookup must not depend on it."""
    home, cwd = tmp_path / "home", tmp_path / "cwd"
    cwd.mkdir()
    _install_stub(home, "3.1.1", "print('ran')\n", project_path=cwd)

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    bsd_sort = fake_bin / "sort"
    bsd_sort.write_text(
        '#!/bin/bash\nfor a in "$@"; do [ "$a" = "-V" ] && '
        '{ echo "sort: illegal option -- V" >&2; exit 2; }; done\nexec /usr/bin/sort "$@"\n',
        encoding="utf-8",
    )
    bsd_sort.chmod(0o755)

    result = subprocess.run(
        ["bash", str(WRAPPER), "stub.py"],
        input=STDIN_PAYLOAD,
        capture_output=True,
        text=True,
        cwd=cwd,
        env={"HOME": str(home), "PATH": f"{fake_bin}:/usr/bin:/bin"},
    )

    assert result.returncode == 0
    assert result.stdout.strip() == "ran"


def test_check_mode_reports_an_unavailable_gate_out_loud(tmp_path: Path) -> None:
    """Fail-open must not be silent — session start says the gates are off."""
    home, cwd = tmp_path / "home", tmp_path / "cwd"
    home.mkdir()
    cwd.mkdir()

    result = _run("--check", home, cwd)

    assert result.returncode == 0
    assert "build-it hardened gates are NOT active" in result.stdout


def test_check_mode_is_quiet_when_the_gates_are_installed(tmp_path: Path) -> None:
    home, cwd = tmp_path / "home", tmp_path / "cwd"
    cwd.mkdir()
    _install_stub(home, "3.1.1", "print('x')\n", name="turn-end-gate.py", project_path=cwd)

    result = _run("--check", home, cwd)

    assert result.returncode == 0
    assert result.stdout == ""


def test_fails_open_when_plugin_is_not_installed(tmp_path: Path) -> None:
    home, cwd = tmp_path / "home", tmp_path / "cwd"
    home.mkdir()
    cwd.mkdir()

    result = _run("evidence-lint.py", home, cwd)

    assert result.returncode == 0
    assert result.stdout == ""
    assert "plugin ledger not found" in _log_text(cwd)


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

    commands = [h["command"] for group in settings["hooks"]["PreToolUse"] for h in group["hooks"]]
    evidence_lint = next(i for i, c in enumerate(commands) if "evidence-lint.py" in c)
    # Compare enumerated positions, not list.index(): scan-secrets.sh appears in
    # two groups, so index() would report the first occurrence for both and the
    # assertion would still pass with the gate moved ahead of the second scanner.
    scanners = [i for i, c in enumerate(commands) if "scan-secrets.sh" in c]
    assert len(scanners) == 2, "expected scan-secrets.sh in both the Bash and Write|Edit groups"
    assert max(scanners) < evidence_lint

    stop_commands = [
        h["command"]
        for group in settings["hooks"]["Stop"]
        for h in group["hooks"]
        if h.get("type") == "command"
    ]
    assert stop_commands.index("bash .claude/hooks/session-stop.sh") < next(
        i for i, c in enumerate(stop_commands) if "turn-end-gate.py" in c
    )


def test_session_start_reports_gate_availability() -> None:
    """Fail-open must not be silent: session start says when the gates are off."""
    import json

    settings = json.loads((ROOT / ".claude/settings.json").read_text(encoding="utf-8"))
    commands = [h["command"] for group in settings["hooks"]["SessionStart"] for h in group["hooks"]]

    assert "bash .claude/hooks/build-it-hook.sh --check" in commands
