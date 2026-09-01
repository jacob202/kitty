from __future__ import annotations

import subprocess
from pathlib import Path

from gateway import context_receipt as cr

ROOT = Path(__file__).resolve().parents[1]
SESSION_END = ROOT / ".agents/skills/session-end/SKILL.md"
AGENTS = ROOT / "AGENTS.md"
START_HERE = ROOT / "START_HERE.md"
CONTEXT_ENGINEERING = ROOT / "docs/reference/CONTEXT_ENGINEERING.md"


def _canonical_worktree() -> Path:
    result = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    first = next(
        line.removeprefix("worktree ")
        for line in result.stdout.splitlines()
        if line.startswith("worktree ")
    )
    return Path(first).resolve()


def test_gar_first_receipt_makes_legacy_checkpoint_failures_non_blocking(monkeypatch):
    def malformed_checkpoint(*_args, **_kwargs):
        raise ValueError("synthetic malformed legacy checkpoint")

    monkeypatch.setattr(cr._legacy, "_load_checkpoint", malformed_checkpoint)
    inspection = cr.inspect_continuity(
        ROOT,
        expected_canonical=_canonical_worktree(),
        include_legacy_continuity=False,
    )

    assert inspection["state"] is None
    assert inspection["handoff"] is None
    assert not any(
        check.name.startswith(("state:", "handoff:", "checkpoint:"))
        or check.name == "mission:active_state"
        for check in inspection["checks"]
    )


def test_gar_first_receipt_exports_no_legacy_next_action():
    receipt = cr.build_context_receipt(
        ROOT,
        expected_canonical=_canonical_worktree(),
        include_builder=False,
        include_legacy_continuity=False,
    )

    assert receipt["continuity"]["state"] is None
    assert receipt["continuity"]["handoff"] is None
    assert receipt["blockers"] is None
    assert receipt["next_action"] is None
    assert receipt["recommendations"] is None
    assert receipt["evidence"]["checkpoint_source"] == []


def test_context_cli_accepts_skip_legacy_continuity(monkeypatch, capsys):
    captured: dict[str, object] = {}

    def fake_build(_root, **kwargs):
        captured.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(cr, "build_context_receipt", fake_build)
    assert cr.main(["--agent", "--skip-legacy-continuity"]) == 0
    assert captured["include_legacy_continuity"] is False
    assert "\"ok\": true" in capsys.readouterr().out.lower()


def test_session_end_posts_room_handoff_after_final_validation():
    text = SESSION_END.read_text(encoding="utf-8")
    validate_at = text.index("check_continuity_state.py")
    final_post_at = text.index("Post the final Global Agent Room handoff")

    assert validate_at < final_post_at
    tail = text[final_post_at:]
    assert "If validation fails" in tail
    assert "blocked" in tail or "failed" in tail


def test_bootloader_uses_deterministic_room_discovery_before_recent_context():
    agents = AGENTS.read_text(encoding="utf-8")
    start_here = START_HERE.read_text(encoding="utf-8")

    for text in (agents, start_here):
        assert "--unread" in text
        assert "room_thread" in text
        assert "durable locator" in text
    assert "--skip-legacy-continuity" in start_here


def test_context_engineering_preserves_verified_delivery_contract():
    text = CONTEXT_ENGINEERING.read_text(encoding="utf-8")
    for required in (
        "outcome contract and non-goals",
        "accepted decisions and their authority",
        "branch/worktree, and SHA",
        "exact verification commands and results",
        "unresolved failures and blockers",
        "one concrete next action",
    ):
        assert required in text
