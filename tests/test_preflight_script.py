from __future__ import annotations

import json
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
