"""Tests for the Algorithm reasoning loop (gateway/algorithm.py)."""

from gateway import algorithm


def test_phase_order_is_canonical():
    assert algorithm.PHASE_NAMES == (
        "OBSERVE",
        "ORIENT",
        "DECIDE",
        "ACT",
        "VERIFY",
        "LEARN",
    )


def test_every_phase_has_intent_and_guidance():
    for p in algorithm.PHASES:
        assert p.intent.strip()
        assert p.guidance.strip()


def test_frame_prompt_keeps_base_and_adds_all_phases():
    framed = algorithm.frame_prompt("BASE PROMPT")
    assert framed.startswith("BASE PROMPT")
    assert "## The Algorithm" in framed
    for name in algorithm.PHASE_NAMES:
        assert name in framed


def test_detect_phase_reads_marker():
    assert algorithm.detect_phase("## PHASE: OBSERVE\nrestating the goal") == "OBSERVE"


def test_detect_phase_is_case_insensitive():
    assert algorithm.detect_phase("phase: decide — here's the plan") == "DECIDE"


def test_detect_phase_last_marker_wins():
    text = "## PHASE: ACT\ndid the thing\n## PHASE: VERIFY\nchecking it"
    assert algorithm.detect_phase(text) == "VERIFY"


def test_detect_phase_none_when_absent_or_unknown():
    assert algorithm.detect_phase("just some prose, no markers") is None
    assert algorithm.detect_phase("## PHASE: BOGUS") is None
    assert algorithm.detect_phase("") is None
