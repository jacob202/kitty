"""Tests for gateway/learning.py — Socratic absorption tracking."""
import json
from unittest.mock import patch

# ── init_stats ────────────────────────────────────────────────────────────────

def test_init_stats_creates_defaults(tmp_path):
    """Creates default stats file when it doesn't exist."""
    from gateway.learning import init_stats
    stats_file = tmp_path / "user_learning_stats.json"

    with patch("gateway.learning.STATS_FILE", stats_file):
        result = init_stats()

    assert stats_file.exists()
    assert result["user_level"] == 1
    assert result["absorption_score"] == 0
    assert result["gates_passed"] == 0
    assert result["topics_mastered"] == []


def test_init_stats_loads_existing(tmp_path):
    """Returns existing stats without overwriting them."""
    from gateway.learning import init_stats
    stats_file = tmp_path / "user_learning_stats.json"
    existing = {
        "user_level": 3,
        "absorption_score": 45,
        "tool_calls_since_gate": 2,
        "gates_passed": 7,
        "topics_mastered": ["Python", "SQL"],
        "last_gate_at": None,
    }
    stats_file.write_text(json.dumps(existing))

    with patch("gateway.learning.STATS_FILE", stats_file):
        result = init_stats()

    assert result["user_level"] == 3
    assert result["absorption_score"] == 45
    assert result["topics_mastered"] == ["Python", "SQL"]


# ── update_stats ──────────────────────────────────────────────────────────────

def test_update_stats_merges_fields(tmp_path):
    """update_stats overwrites specified keys, preserves others."""
    from gateway.learning import init_stats, update_stats
    stats_file = tmp_path / "user_learning_stats.json"

    with patch("gateway.learning.STATS_FILE", stats_file):
        init_stats()
        update_stats({"user_level": 2, "gates_passed": 3})
        result = init_stats()

    assert result["user_level"] == 2
    assert result["gates_passed"] == 3
    assert result["absorption_score"] == 0  # unchanged default


def test_update_stats_persists_to_disk(tmp_path):
    """update_stats writes to STATS_FILE."""
    from gateway.learning import init_stats, update_stats
    stats_file = tmp_path / "user_learning_stats.json"

    with patch("gateway.learning.STATS_FILE", stats_file):
        init_stats()
        update_stats({"absorption_score": 55})
        raw = json.loads(stats_file.read_text())

    assert raw["absorption_score"] == 55


# ── record_interaction ────────────────────────────────────────────────────────

def test_record_interaction_increments_tool_calls(tmp_path):
    """record_interaction increments tool_calls_since_gate when tool_used=True."""
    from gateway.learning import init_stats, record_interaction
    stats_file = tmp_path / "user_learning_stats.json"

    with patch("gateway.learning.STATS_FILE", stats_file):
        init_stats()
        record_interaction(tool_used=True)
        stats = init_stats()

    assert stats["tool_calls_since_gate"] == 1


def test_record_interaction_increments_absorption(tmp_path):
    """record_interaction increases absorption_score when was_educational=True."""
    from gateway.learning import init_stats, record_interaction
    stats_file = tmp_path / "user_learning_stats.json"

    with patch("gateway.learning.STATS_FILE", stats_file):
        init_stats()
        record_interaction(was_educational=True)
        stats = init_stats()

    assert stats["absorption_score"] == 2


def test_record_interaction_gate_triggers_at_5(tmp_path):
    """Returns True when tool_calls_since_gate reaches 5."""
    from gateway.learning import init_stats, record_interaction, update_stats
    stats_file = tmp_path / "user_learning_stats.json"

    with patch("gateway.learning.STATS_FILE", stats_file):
        init_stats()
        update_stats({"tool_calls_since_gate": 4})
        result = record_interaction(tool_used=True)

    assert result is True


def test_record_interaction_no_gate_below_5(tmp_path):
    """Returns False when tool calls below threshold."""
    from gateway.learning import init_stats, record_interaction
    stats_file = tmp_path / "user_learning_stats.json"

    with patch("gateway.learning.STATS_FILE", stats_file):
        init_stats()
        result = record_interaction(tool_used=True)

    assert result is False


def test_record_interaction_caps_absorption_at_100(tmp_path):
    """absorption_score doesn't exceed 100."""
    from gateway.learning import init_stats, record_interaction, update_stats
    stats_file = tmp_path / "user_learning_stats.json"

    with patch("gateway.learning.STATS_FILE", stats_file):
        init_stats()
        update_stats({"absorption_score": 99})
        record_interaction(was_educational=True)
        stats = init_stats()

    assert stats["absorption_score"] == 100


def test_record_interaction_no_effect_without_flags(tmp_path):
    """record_interaction with no flags doesn't change scores."""
    from gateway.learning import init_stats, record_interaction
    stats_file = tmp_path / "user_learning_stats.json"

    with patch("gateway.learning.STATS_FILE", stats_file):
        init_stats()
        record_interaction()
        stats = init_stats()

    assert stats["tool_calls_since_gate"] == 0
    assert stats["absorption_score"] == 0


# ── process_gate_answer ───────────────────────────────────────────────────────

def test_process_gate_answer_correct_increments_gates_passed(tmp_path):
    """Correct gate answer increments gates_passed and resets tool counter."""
    from gateway.learning import init_stats, process_gate_answer, update_stats
    stats_file = tmp_path / "user_learning_stats.json"

    llm_response = json.dumps({"correct": True, "feedback": "Good!", "level_up": False})
    with patch("gateway.learning.STATS_FILE", stats_file):
        init_stats()
        update_stats({"tool_calls_since_gate": 5})
        with patch("gateway.llm_client.call_llm", return_value=llm_response):
            result = process_gate_answer("my answer", "test question")
        stats = init_stats()

    assert result["correct"] is True
    assert stats["gates_passed"] == 1
    assert stats["tool_calls_since_gate"] == 0


def test_process_gate_answer_level_up(tmp_path):
    """level_up=True increments user_level."""
    from gateway.learning import init_stats, process_gate_answer
    stats_file = tmp_path / "user_learning_stats.json"

    llm_response = json.dumps({"correct": True, "feedback": "Excellent!", "level_up": True})
    with patch("gateway.learning.STATS_FILE", stats_file):
        init_stats()
        with patch("gateway.llm_client.call_llm", return_value=llm_response):
            process_gate_answer("great answer", "hard question")
        stats = init_stats()

    assert stats["user_level"] == 2


def test_process_gate_answer_llm_failure_passes_gate(tmp_path):
    """LLM failure returns a default pass so Jacob isn't blocked."""
    from gateway.learning import init_stats, process_gate_answer
    stats_file = tmp_path / "user_learning_stats.json"

    with patch("gateway.learning.STATS_FILE", stats_file):
        init_stats()
        with patch("gateway.llm_client.call_llm", side_effect=Exception("timeout")):
            result = process_gate_answer("some answer", "some question")

    assert result["correct"] is True
    assert "System error" in result["feedback"]
