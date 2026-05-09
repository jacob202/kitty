"""Tests for onboarding logic."""
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


def test_load_state_returns_all_domains_false_when_no_file(tmp_path, monkeypatch):
    from gateway import onboarding
    monkeypatch.setattr(onboarding, "STATE_FILE", tmp_path / "state.json")
    state = onboarding.load_state()
    assert set(state.keys()) == set(onboarding.DOMAINS.keys())
    assert all(v is False for v in state.values())


def test_save_and_load_state_roundtrip(tmp_path, monkeypatch):
    from gateway import onboarding
    monkeypatch.setattr(onboarding, "STATE_FILE", tmp_path / "state.json")
    state = onboarding.load_state()
    state["identity"] = True
    onboarding.save_state(state)
    loaded = onboarding.load_state()
    assert loaded["identity"] is True
    assert loaded["health"] is False


def test_domains_have_required_keys():
    from gateway.onboarding import DOMAINS
    for domain, config in DOMAINS.items():
        assert "sensitivity" in config, f"{domain} missing sensitivity"
        assert "title" in config, f"{domain} missing title"
        assert "questions" in config, f"{domain} missing questions"
        assert len(config["questions"]) >= 2, f"{domain} needs at least 2 questions"


def test_domains_sensitivity_values():
    from gateway.onboarding import DOMAINS
    valid = {"low", "medium", "high", "medical", "financial"}
    for domain, config in DOMAINS.items():
        assert config["sensitivity"] in valid, f"{domain} has invalid sensitivity"


def test_health_and_finances_are_sensitive():
    from gateway.onboarding import DOMAINS
    assert DOMAINS["health"]["sensitivity"] == "medical"
    assert DOMAINS["finances"]["sensitivity"] == "financial"


def test_extract_facts_falls_back_on_api_failure():
    """extract_facts returns a fallback fact when LiteLLM is unreachable."""
    with patch("requests.post", side_effect=Exception("Connection refused")):
        from gateway.onboarding import extract_facts
        facts = extract_facts("automotive", "What car do you own?", "A 2010 Honda Civic", "low")
    assert len(facts) == 1
    assert "automotive" in facts[0].lower() or "Honda" in facts[0]


def test_extract_facts_parses_json_array():
    """extract_facts correctly parses a well-formed LLM response."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": '["Jacob owns a 2010 Honda Civic.", "Jacob does oil changes himself."]'}}]
    }
    mock_response.raise_for_status = MagicMock()
    with patch("requests.post", return_value=mock_response):
        from gateway.onboarding import extract_facts
        facts = extract_facts("automotive", "What car?", "2010 Honda Civic", "low")
    assert "Jacob owns a 2010 Honda Civic." in facts
    assert len(facts) == 2
