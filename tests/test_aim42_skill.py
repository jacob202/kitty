"""Contract tests for the AIM42 software-improvement skill."""

from gateway.skill_registry import discover, invoke, suggest


SKILL_NAME = "aim42-software-improvement"


def test_aim42_skill_is_discoverable():
    names = {skill["name"] for skill in discover(force_refresh=True)}
    assert SKILL_NAME in names


def test_aim42_skill_invocation_contains_full_loop():
    result = invoke(SKILL_NAME)

    assert "error" not in result
    assert "Analyze → Evaluate → Improve → Verify" in result["prompt"]
    assert "No orphan improvements" in result["prompt"]
    assert "VERIFIED" in result["prompt"]
    assert "---\nname:" not in result["prompt"]


def test_aim42_skill_can_be_suggested_for_technical_debt_audit():
    suggestions = suggest(
        "Perform a technical debt audit before planning the architecture modernization.",
        limit=5,
    )
    assert SKILL_NAME in {skill["name"] for skill in suggestions}
