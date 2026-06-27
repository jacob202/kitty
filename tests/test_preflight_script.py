from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT = ROOT / "scripts" / "preflight.sh"


def _write_executable(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)


def _fake_path(tmp_path: Path) -> Path:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_executable(
        fake_bin / "gh",
        """#!/bin/bash
if [[ "${1:-}" == "auth" && "${2:-}" == "status" && -z "${GITHUB_TOKEN:-}" ]]; then
  exit 0
fi
exit 1
""",
    )
    _write_executable(
        fake_bin / "git",
        """#!/bin/bash
echo "https://github.com/jacob202/kitty.git"
""",
    )
    _write_executable(fake_bin / "python3", "#!/bin/bash\nexit 1\n")
    _write_executable(fake_bin / "ollama", "#!/bin/bash\nexit 0\n")
    return fake_bin


def _run_preflight(tmp_path: Path, *, token: str | None) -> subprocess.CompletedProcess[str]:
    fake_bin = _fake_path(tmp_path)
    claude_env_file = tmp_path / "claude-env.sh"
    env = {
        **os.environ,
        "ANTHROPIC_API_KEY": "test-key",
        "CLAUDE_ENV_FILE": str(claude_env_file),
        "HOME": str(tmp_path),
        "KITTY_ENV_FILE": str(tmp_path / "missing.env"),
        "PATH": f"{fake_bin}:/usr/bin:/bin",
    }
    if token is None:
        env.pop("GITHUB_TOKEN", None)
    else:
        env["GITHUB_TOKEN"] = token

    return subprocess.run(
        ["bash", str(PREFLIGHT)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_preflight_completes_all_checks_without_ambient_token(tmp_path: Path) -> None:
    result = _run_preflight(tmp_path, token=None)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "gh auth ok" in result.stdout
    assert "GITHUB_TOKEN not set" in result.stdout
    assert "git remote: https://github.com/jacob202/kitty.git" in result.stdout
    assert "ANTHROPIC_API_KEY is set" in result.stdout
    assert "ollama available as fallback" in result.stdout
    assert "0 failures" in result.stdout


def test_preflight_neutralizes_stale_token_when_keyring_auth_works(tmp_path: Path) -> None:
    result = _run_preflight(tmp_path, token="stale-token")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "stale GITHUB_TOKEN masks valid keyring auth" in result.stdout
    assert "0 failures" in result.stdout
    claude_env_file = tmp_path / "claude-env.sh"
    assert claude_env_file.read_text(encoding="utf-8") == "export GITHUB_TOKEN=''\n"


def test_claude_session_start_runs_preflight() -> None:
    settings = json.loads((ROOT / ".claude/settings.json").read_text(encoding="utf-8"))
    commands = [
        hook["command"]
        for group in settings["hooks"]["SessionStart"]
        for hook in group["hooks"]
    ]

    assert any("scripts/preflight.sh" in command for command in commands)


def test_codex_instructions_define_safe_github_auth_preflight() -> None:
    instructions = (ROOT / "AGENTS.md").read_text(encoding="utf-8")

    assert "GITHUB_TOKEN" in instructions
    assert "env -u GITHUB_TOKEN" in instructions
