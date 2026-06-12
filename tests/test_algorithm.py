"""Tests for the Algorithm reasoning loop (gateway/algorithm.py) and its wiring
into the agent runner."""

import pytest

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


# --- Integration: the loop frames the prompt and tags the detected phase ---


class _FakeState:
    """Stand-in for AutonomyState that just collects recorded steps."""

    def __init__(self, session_id):
        self.session_id = session_id
        self.steps: list[dict] = []
        self.status = None

    def record_step(self, role, content="", thinking=""):
        self.steps.append({"role": role, "content": content, "thinking": thinking})

    def finish(self, status):
        self.status = status


def _wire_loop(monkeypatch, response):
    """Patch the loop's runtime deps; return (captured, state) for assertions."""
    captured: dict = {}
    state = _FakeState(session_id=1)

    def fake_call_llm(**kwargs):
        captured["messages"] = kwargs["messages"]
        return response

    monkeypatch.setattr("gateway.llm_client.call_llm", fake_call_llm)
    monkeypatch.setattr("gateway.llm_client.route_model", lambda goal: "test-model")
    monkeypatch.setattr(
        "gateway.autonomy_state.AutonomyState", lambda session_id: state
    )
    return captured, state


@pytest.mark.asyncio
async def test_run_agent_loop_frames_prompt_and_tags_phase(monkeypatch):
    from gateway.agent_runner import _run_agent_loop

    captured, state = _wire_loop(monkeypatch, "## PHASE: DECIDE\nhere is the plan")
    await _run_agent_loop(1, "do the thing", "BASE PROMPT", "test-model", 1, 0.2, True)

    system_prompt = captured["messages"][0]["content"]
    assert "## The Algorithm" in system_prompt
    for name in algorithm.PHASE_NAMES:
        assert name in system_prompt

    assistant = [s for s in state.steps if s["role"] == "assistant"]
    assert assistant and assistant[-1]["thinking"].startswith("[DECIDE]")


@pytest.mark.asyncio
async def test_run_agent_loop_leaves_prompt_unframed_when_disabled(monkeypatch):
    from gateway.agent_runner import _run_agent_loop

    captured, state = _wire_loop(monkeypatch, "## PHASE: DECIDE\nplan")
    await _run_agent_loop(1, "do the thing", "BASE PROMPT", "test-model", 1, 0.2, False)

    assert captured["messages"][0]["content"] == "BASE PROMPT"
    assistant = [s for s in state.steps if s["role"] == "assistant"]
    assert assistant and not assistant[-1]["thinking"].startswith("[")
