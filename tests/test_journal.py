"""Tests for the journal interviewer and prompt generator."""
import json
import pytest
from pathlib import Path
from gateway.journal import (
    THEMES,
    build_interview_system_prompt,
    build_synthesis_prompt,
    delete_journal_message,
    get_opener,
    get_random_prompt,
    is_journal_trigger,
    save_journal_entry,
)
from gateway.prompts import (
    JOURNAL_INTERVIEW_PROMPT,
    JOURNAL_SYNTHESIS_PROMPT,
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
    assert JOURNAL_INTERVIEW_PROMPT in result


def test_build_interview_system_prompt_base_comes_first():
    base = "You are Kitty."
    result = build_interview_system_prompt(base)
    assert result.index(base) < result.index(JOURNAL_INTERVIEW_PROMPT)


def test_build_interview_system_prompt_with_theme():
    result = build_interview_system_prompt("You are Kitty.", "mood")
    assert "mood" in result


def test_build_synthesis_prompt_returns_string():
    result = build_synthesis_prompt()
    assert result == JOURNAL_SYNTHESIS_PROMPT
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


def test_delete_journal_message_removes_entry(tmp_path, monkeypatch):
    import gateway.journal as jmod
    monkeypatch.setattr(jmod, "JOURNAL_LOG", tmp_path / "journal_entries.jsonl")

    # Write three entries
    r1 = save_journal_entry("First entry.", theme="mood")
    r2 = save_journal_entry("Second entry.", theme="work")
    r3 = save_journal_entry("Third entry.", theme="reflection")

    # Delete the second entry using its ts as message_id
    target_ts = str(r2["ts"])
    result = delete_journal_message("test_session", target_ts)
    assert result is True

    # Verify only two entries remain and the second is gone
    lines = (tmp_path / "journal_entries.jsonl").read_text().strip().splitlines()
    assert len(lines) == 2
    entries = [json.loads(l) for l in lines]
    ts_values = [e["ts"] for e in entries]
    assert r1["ts"] in ts_values
    assert r3["ts"] in ts_values
    assert r2["ts"] not in ts_values


def test_delete_journal_message_respects_session_id(tmp_path, monkeypatch):
    import gateway.journal as jmod
    monkeypatch.setattr(jmod, "JOURNAL_LOG", tmp_path / "journal_entries.jsonl")

    ts = 1234567890.0
    with (tmp_path / "journal_entries.jsonl").open("a") as f:
        f.write(json.dumps({"ts": ts, "session_id": "alpha", "theme": "mood", "entry": "Alpha"}) + "\n")
        f.write(json.dumps({"ts": ts, "session_id": "beta", "theme": "work", "entry": "Beta"}) + "\n")

    result = delete_journal_message("beta", str(ts))
    assert result is True

    entries = [json.loads(l) for l in (tmp_path / "journal_entries.jsonl").read_text().strip().splitlines()]
    assert len(entries) == 1
    assert entries[0]["session_id"] == "alpha"


def test_delete_journal_message_returns_false_when_not_found(tmp_path, monkeypatch):
    import gateway.journal as jmod
    monkeypatch.setattr(jmod, "JOURNAL_LOG", tmp_path / "journal_entries.jsonl")

    save_journal_entry("Only entry.", theme="mood")
    result = delete_journal_message("test_session", "9999999999.0")
    assert result is False


def test_delete_journal_message_returns_false_on_invalid_id(tmp_path, monkeypatch):
    import gateway.journal as jmod
    monkeypatch.setattr(jmod, "JOURNAL_LOG", tmp_path / "journal_entries.jsonl")

    result = delete_journal_message("test_session", "not_a_number")
    assert result is False


def test_delete_journal_message_returns_false_on_missing_file(tmp_path, monkeypatch):
    import gateway.journal as jmod
    missing = tmp_path / "nonexistent.jsonl"
    monkeypatch.setattr(jmod, "JOURNAL_LOG", missing)

    result = delete_journal_message("test_session", "1234567890.0")
    assert result is False
