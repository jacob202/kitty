from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_doctrine_suspends_builder_and_gar_without_retiring_kitty() -> None:
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    claude = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    start = (ROOT / "START_HERE.md").read_text(encoding="utf-8")

    assert "Builder is not the default executor" in agents
    assert "GAR is not mandatory recall" in agents
    assert "Builder is suspended as the default executor" in claude
    assert "Do not use Builder or GAR during ordinary startup" in start
    assert "retire Kitty" not in agents.lower()


def test_legacy_state_files_are_explicitly_non_authoritative() -> None:
    for name in ("STATE.md", "HANDOFF.md"):
        text = (ROOT / ".claude" / name).read_text(encoding="utf-8")
        assert "SUSPENDED COMPATIBILITY SNAPSHOT" in text
        assert "Do not use this file to establish current assignment" in text


def test_session_end_skill_cannot_recreate_suspended_lifecycle() -> None:
    text = (ROOT / ".agents/skills/session-end/SKILL.md").read_text(encoding="utf-8")
    assert "do not invoke this skill automatically" in text.lower()
    assert "Do not post GAR handoffs" in text
    assert "rewrite `.claude/STATE.md`" in text


def test_catchup_uses_live_state_not_legacy_handoffs() -> None:
    for path in (
        ROOT / ".agents/skills/catchup/SKILL.md",
        ROOT / ".claude/skills/catchup/SKILL.md",
    ):
        text = path.read_text(encoding="utf-8")
        assert "Catchup is read-only" in text
        assert "STATE.md` and `.claude/HANDOFF.md` are preserved compatibility" in text
        assert "They are not catchup inputs" in text
