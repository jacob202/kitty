from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.fixture()
def launcher_repo(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    root = tmp_path / "kitty"
    root.mkdir()
    shutil.copy2(Path(__file__).parents[1] / "kitty", root / "kitty")
    (root / "kitty").chmod(0o755)
    (root / "gateway" / "lib").mkdir(parents=True)
    (root / "gateway" / "lib" / "load_env_safe.sh").write_text(
        "load_env_assignments() { :; }\n", encoding="utf-8"
    )
    (root / "venv" / "bin").mkdir(parents=True)
    fake_python = root / "venv" / "bin" / "python"
    fake_python.write_text(
        "#!/usr/bin/env bash\n"
        "if [[ \"${1:-} ${2:-}\" == \"-m mcp.builder.server\" ]]; then\n"
        "  trap 'exit 0' TERM INT\n"
        "  while true; do sleep 0.1; done\n"
        "fi\n"
        "printf '%s\\n' \"$*\" >> \"$TEST_MODULE_CALLS\"\n",
        encoding="utf-8",
    )
    fake_python.chmod(0o755)
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    lsof = fake_bin / "lsof"
    lsof.write_text(
        "#!/usr/bin/env bash\n"
        "if [[ \" $* \" == *\" -d cwd \"* ]]; then\n"
        "  if [[ \"${TEST_FORCE_UNRELATED:-0}\" == \"1\" ]]; then echo 'n/tmp'; else echo \"n$TEST_KITTY_ROOT\"; fi\n"
        "  exit 0\n"
        "fi\n"
        "exit 1\n",
        encoding="utf-8",
    )
    lsof.chmod(0o755)
    env = os.environ.copy()
    env.update(
        TEST_KITTY_ROOT=str(root),
        TEST_MODULE_CALLS=str(tmp_path / "calls.txt"),
        PATH=f"{fake_bin}:{env['PATH']}",
        KITTYBUILDER_MCP_PORT="18765",
    )
    return root, env


def run_kitty(root: Path, env: dict[str, str], *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(root / "kitty"), *args], cwd=root, env=env, text=True,
        capture_output=True, timeout=5,
    )


def test_mcp_up_is_idempotent_and_down_stops_only_owned_process(launcher_repo):
    root, env = launcher_repo
    first = run_kitty(root, env, "mcp", "up")
    assert first.returncode == 0, first.stderr
    pid_file = root / "logs" / ".run" / "mcp.pid"
    first_pid = int(pid_file.read_text().strip())
    assert first_pid > 0

    second = run_kitty(root, env, "mcp", "up")
    assert second.returncode == 0, second.stderr
    assert int(pid_file.read_text().strip()) == first_pid

    stopped = run_kitty(root, env, "mcp", "down")
    assert stopped.returncode == 0, stopped.stderr
    assert not pid_file.exists()


def test_mcp_public_bind_is_refused_before_launch(launcher_repo):
    root, env = launcher_repo
    env["KITTYBUILDER_MCP_HOST"] = "0.0.0.0"
    result = run_kitty(root, env, "mcp", "up")
    assert result.returncode != 0
    assert "loopback" in (result.stderr + result.stdout).lower()
    assert not (root / "logs" / ".run" / "mcp.pid").exists()


def test_mcp_down_refuses_unrelated_live_pid(launcher_repo):
    root, env = launcher_repo
    proc = subprocess.Popen(["sleep", "10"], cwd="/tmp")
    try:
        pid_file = root / "logs" / ".run" / "mcp.pid"
        pid_file.parent.mkdir(parents=True, exist_ok=True)
        pid_file.write_text(f"{proc.pid}\n")
        env["TEST_FORCE_UNRELATED"] = "1"
        result = run_kitty(root, env, "mcp", "down")
        assert result.returncode != 0
        assert proc.poll() is None
        assert pid_file.exists()
    finally:
        proc.terminate()
        proc.wait(timeout=3)


@pytest.mark.parametrize("sub", ["status", "doctor", "proof"])
def test_mcp_operator_subcommands_delegate_to_operator_cli(launcher_repo, sub):
    root, env = launcher_repo
    result = run_kitty(root, env, "mcp", sub, "--json")
    assert result.returncode == 0, result.stderr
    calls = Path(env["TEST_MODULE_CALLS"]).read_text()
    assert f"-m mcp.builder.operator_cli {sub} --json" in calls
