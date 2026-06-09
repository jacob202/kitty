"""Tests for the TELOS interview flow (user_context additions)."""
import importlib

import pytest

from gateway import user_context


@pytest.fixture
def user_dir(tmp_path, monkeypatch):
    d = tmp_path / "USER"
    d.mkdir()
    monkeypatch.setattr(user_context, "USER_DIR", d)
    user_context.load_user_context.cache_clear()
    yield d
    user_context.load_user_context.cache_clear()


def test_missing_sections_lists_unfilled(user_dir):
    (user_dir / "MISSION.md").write_text("# Mission\nReal mission.\n")
    (user_dir / "GOALS.md").write_text("TEMPLATE: x\n# Goals\n")
    missing = user_context.missing_sections()
    assert "MISSION.md" not in missing
    assert "GOALS.md" in missing
    assert "PROBLEMS.md" in missing  # absent entirely


@pytest.mark.parametrize(
    "msg,expected",
    [
        ("can you interview me about my goals", True),
        ("set up my TELOS please", True),
        ("what's the weather", False),
    ],
)
def test_is_interview_trigger(msg, expected):
    assert user_context.is_interview_trigger(msg) is expected


def test_update_section_writes_and_activates(user_dir):
    assert user_context.update_section("MISSION", "Build leverage tools.") is True
    assert (user_dir / "MISSION.md").read_text().strip() == "Build leverage tools."
    assert "MISSION.md" not in user_context.missing_sections()


def test_update_section_rejects_unknown(user_dir):
    assert user_context.update_section("BOGUS", "x") is False


def test_build_interview_prompt_targets_next_missing(user_dir):
    (user_dir / "MISSION.md").write_text("# Mission\nFilled.\n")
    prompt = user_context.build_interview_prompt("BASE")
    assert "TELOS Interview Mode" in prompt
    assert "GOALS.md" in prompt  # MISSION filled, GOALS is next
    assert "ONE focused question" in prompt
