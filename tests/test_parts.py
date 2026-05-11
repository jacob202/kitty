"""Tests for the parts system — external toggle and context detection."""
from gateway.parts import should_surface_parts, build_parts_system_prompt, PARTS_PROMPT


def test_parts_prompt_appended():
    base = "You are Kitty."
    result = build_parts_system_prompt(base)
    assert base in result
    assert PARTS_PROMPT in result
    assert result.index(base) < result.index(PARTS_PROMPT)


def test_validation_seeking_triggers_parts():
    assert should_surface_parts("what do you think, am I right?")


def test_high_stakes_with_assertion_triggers_parts():
    assert should_surface_parts("I know I should definitely quit this job")


def test_decision_without_assertion_does_not_trigger():
    assert not should_surface_parts("should I have coffee or tea")


def test_routine_message_does_not_trigger():
    assert not should_surface_parts("what's the weather like today")


def test_reassurance_seeking_triggers_parts():
    assert should_surface_parts("tell me I'm making the right call here")


def test_agreement_request_triggers_parts():
    assert should_surface_parts("agree with me that this approach is correct")
