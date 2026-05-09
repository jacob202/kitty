"""Unit tests for domain classifier — no services required."""
from gateway.domain_router import classify_domain


def test_soul_is_default():
    assert classify_domain("how are you doing today?") == "soul"


def test_repair_keywords():
    assert classify_domain("my car makes a weird noise when I brake") == "repair"


def test_health_keywords():
    assert classify_domain("I have a headache and took ibuprofen") == "health"


def test_research_keywords():
    assert classify_domain("research the best budget CPU for gaming") == "research"


def test_code_keywords():
    assert classify_domain("debug this python function") == "code"


def test_empty_message_is_soul():
    assert classify_domain("") == "soul"


def test_health_routes_to_private_model():
    """Health domain always uses kitty-private."""
    # Tested via app layer — here just confirm classifier returns health
    result = classify_domain("what are my blood test results telling me?")
    assert result == "health"
