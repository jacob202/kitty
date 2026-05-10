"""Tests for the journal interviewer and prompt generator."""
import json
import pytest
from pathlib import Path
from gateway.journal import (
    INTERVIEW_SYSTEM_PROMPT,
    SYNTHESIS_PROMPT,
    THEMES,
    build_interview_system_prompt,
    build_synthesis_prompt,
    get_opener,
    get_random_prompt,
    is_journal_trigger,
    save_journal_entry,
)


def test_get_opener_with_known_theme():
    opener = get_opener("recovery")
    assert isinstance(opener, str)
    assert len(opener) > 0


def test_get_opener_without_theme_returns_string():
    opener = get_opener()
    assert isinstance(opener, str)
    assert len(opener) > 0


def test_get_opener_unknown_theme_does_not_crash():
    opener = get_opener("nonexistent")
    assert isinstance(opener, str)


def test_get_random_prompt_returns_theme_and_prompt():
    result = get_random_prompt()
    assert "theme" in result
    assert "prompt" in result
    assert result["theme"] in THEMES
    assert isinstance(result["prompt"], str)


def test_get_random_prompt_with_known_theme():
    result = get_random_prompt("work")
    assert result["theme"] == "work"
    assert isinstance(result["prompt"], str)


def test_get_random_prompt_unknown_theme_picks_random():
    result = get_random_prompt("nonexistent")
    assert result["theme"] in THEMES


def test_build_interview_system_prompt_contains_base_and_interview():
    base = "You are Kitty."
    result = build_interview_system_prompt(base)
    assert base in result
    assert INTERVIEW_SYSTEM_PROMPT in result


def test_build_interview_system_prompt_base_comes_first():
    base = "You are Kitty."
    result = build_interview_system_prompt(base)
    assert result.index(base) < result.index(INTERVIEW_SYSTEM_PROMPT)


def test_build_interview_system_prompt_with_theme():
    result = build_interview_system_prompt("You are Kitty.", "mood")
    assert "mood" in result


def test_build_synthesis_prompt_returns_string():
    result = build_synthesis_prompt()
    assert result == SYNTHESIS_PROMPT
    assert "Jacob" in result
    assert "first person" in result.lower() or "his voice" in result.lower()


def test_is_journal_trigger_detects_journal():
    assert is_journal_trigger("journal with me for a bit")


def test_is_journal_trigger_detects_interview_me():
    assert is_journal_trigger("interview me about my week")


def test_is_journal_trigger_detects_check_in():
    assert is_journal_trigger("let's do a check in")


def test_is_journal_trigger_ignores_unrelated():
    assert not is_journal_trigger("what's the weather")
    assert not is_journal_trigger("help me debug this code")
    assert not is_journal_trigger("order a pizza")


def test_save_journal_entry_writes_to_file(tmp_path, monkeypatch):
    import gateway.journal as jmod
    monkeypatch.setattr(jmod, "JOURNAL_LOG", tmp_path / "journal_entries.jsonl")
    record = save_journal_entry("Today was good.", theme="mood")
    assert record["entry"] == "Today was good."
    assert record["theme"] == "mood"
    assert "ts" in record
    lines = (tmp_path / "journal_entries.jsonl").read_text().strip().splitlines()
    assert len(lines) == 1
    saved = json.loads(lines[0])
    assert saved["entry"] == "Today was good."


def test_save_journal_entry_appends():
    from gateway.paths import DATA_DIR
    import gateway.journal as jmod
    import tempfile, os
    tmp = Path(tempfile.mktemp(suffix=".jsonl"))
    original = jmod.JOURNAL_LOG
    jmod.JOURNAL_LOG = tmp
    try:
        save_journal_entry("Entry one.")
        save_journal_entry("Entry two.")
        lines = tmp.read_text().strip().splitlines()
        assert len(lines) == 2
    finally:
        jmod.JOURNAL_LOG = original
        tmp.unlink(missing_ok=True)
