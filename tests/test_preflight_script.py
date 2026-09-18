from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_claude_session_start_uses_live_session_hook() -> None:
    settings = json.loads((ROOT / ".claude/settings.json").read_text(encoding="utf-8"))
    commands = [
        hook["command"]
        for group in settings["hooks"]["SessionStart"]
        for hook in group["hooks"]
    ]

    assert any(".claude/hooks/session-start.sh" in command for command in commands)
    assert not any("scripts/preflight.sh" in command for command in commands)


def test_codex_instructions_define_safe_github_auth_preflight() -> None:
    instructions = (ROOT / "AGENTS.md").read_text(encoding="utf-8")

    assert "GITHUB_TOKEN" in instructions
    assert "env -u GITHUB_TOKEN" in instructions


def test_preflight_agent_spawn_contract_is_explicit_and_syntax_valid() -> None:
    script_path = ROOT / "scripts" / "preflight.sh"
    script = script_path.read_text(encoding="utf-8")

    assert "--agent-spawn" in script
    assert "--probe-claude-quota" in script
    assert "--require-dotenv" in script
    assert "claude auth status" in script
    assert '[[ -f "${ROOT_DIR}/.env" ]]' in script
    assert "Reply exactly AVAILABLE" in script

    result = subprocess.run(
        ["bash", "-n", str(script_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_orchestration_requires_spawn_preflight_and_product_guard() -> None:
    orchestration = (ROOT / ".agents/skills/orca-orchestration/SKILL.md").read_text(
        encoding="utf-8"
    )
    next_skill = (ROOT / ".agents/skills/next/SKILL.md").read_text(encoding="utf-8")

    assert "scripts/preflight.sh --agent-spawn --probe-claude-quota" in orchestration
    assert "scripts/product_gain_guard.py --enforce" in orchestration
    assert "scripts/product_gain_guard.py --enforce" in next_skill
    assert "does not cancel Jacob's explicit task" in orchestration
    assert "Code-only/read-only workers do not need secrets copied" in orchestration
