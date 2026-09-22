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


def test_authority_map_makes_legacy_state_files_non_authoritative() -> None:
    authority = (ROOT / "docs/AUTHORITY_MAP.md").read_text(encoding="utf-8")
    assert (
        "| `session_checkpoint` | `.claude/STATE.md` | Historical compatibility snapshot "
        "preserved for rollback/archaeology during ADR 0043"
    ) in authority
    assert (
        "| `continuation` | `.claude/HANDOFF.md` | Historical compatibility handoff "
        "preserved for rollback/archaeology during ADR 0043"
    ) in authority
    assert "Current assignment, ownership, branch, next action, or project truth" in authority


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
