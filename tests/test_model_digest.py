# tests/test_model_digest.py
"""Tests for AI model digest — mocked HTTP, real SQLite (in-memory)."""
from unittest.mock import MagicMock, patch

import gateway.model_digest as digest_module

FAKE_MODELS_RESPONSE = {
    "data": [
        {
            "id": "openai/gpt-4o",
            "name": "GPT-4o",
            "pricing": {"prompt": "0.0000025", "completion": "0.000010"},
            "context_length": 128000,
        },
        {
            "id": "google/gemini-2.5-flash",
            "name": "Gemini 2.5 Flash",
            "pricing": {"prompt": "0.000000075", "completion": "0.0000003"},
            "context_length": 1048576,
        },
    ]
}


def _mock_openrouter(response_data):
    mock_resp = MagicMock()
    mock_resp.json.return_value = response_data
    mock_resp.raise_for_status = MagicMock()
    return patch("requests.get", return_value=mock_resp)


def test_fetch_models_returns_list():
    with _mock_openrouter(FAKE_MODELS_RESPONSE):
        models = digest_module.fetch_models()
    assert len(models) == 2
    assert models[0]["id"] == "openai/gpt-4o"


def test_parse_model_extracts_fields():
    raw = FAKE_MODELS_RESPONSE["data"][0]
    parsed = digest_module._parse_model(raw)
    assert parsed["id"] == "openai/gpt-4o"
    assert parsed["name"] == "GPT-4o"
    assert parsed["prompt_price"] == 0.0000025
    assert parsed["completion_price"] == 0.000010
    assert parsed["context_length"] == 128000


def test_detect_new_model():
    previous = {}
    current = {"openai/gpt-4o": {"id": "openai/gpt-4o", "name": "GPT-4o",
                                   "prompt_price": 0.0000025, "completion_price": 0.000010,
                                   "context_length": 128000}}
    events = digest_module.diff_models(previous, current)
    assert len(events) == 1
    assert events[0]["event_type"] == "new_model"
    assert events[0]["model_id"] == "openai/gpt-4o"


def test_detect_price_drop():
    prev = {"openai/gpt-4o": {"id": "openai/gpt-4o", "name": "GPT-4o",
                               "prompt_price": 0.000005, "completion_price": 0.000015,
                               "context_length": 128000}}
    curr = {"openai/gpt-4o": {"id": "openai/gpt-4o", "name": "GPT-4o",
                               "prompt_price": 0.0000025, "completion_price": 0.000010,
                               "context_length": 128000}}
    events = digest_module.diff_models(prev, curr)
    assert len(events) == 1
    assert events[0]["event_type"] == "price_drop"


def test_detect_price_increase():
    prev = {"qwen/qwen3-235b": {"id": "qwen/qwen3-235b", "name": "Qwen3 235B",
                                 "prompt_price": 0.00005, "completion_price": 0.0001,
                                 "context_length": 32768}}
    curr = {"qwen/qwen3-235b": {"id": "qwen/qwen3-235b", "name": "Qwen3 235B",
                                 "prompt_price": 0.0001, "completion_price": 0.0002,
                                 "context_length": 32768}}
    events = digest_module.diff_models(prev, curr)
    assert len(events) == 1
    assert events[0]["event_type"] == "price_increase"


def test_no_change_produces_no_events():
    snap = {"openai/gpt-4o": {"id": "openai/gpt-4o", "name": "GPT-4o",
                               "prompt_price": 0.0000025, "completion_price": 0.000010,
                               "context_length": 128000}}
    events = digest_module.diff_models(snap, snap)
    assert events == []


def test_get_model_digest_section_returns_string():
    with patch.object(digest_module, "_load_recent_events", return_value=[
        {"event_type": "new_model", "model_id": "fake/model", "details": "New model added"},
        {"event_type": "price_drop", "model_id": "openai/gpt-4o", "details": "Prompt: $5 → $2.50/M"},
    ]):
        section = digest_module.get_model_digest_section()
    assert "Model News" in section or "model" in section.lower()
    assert len(section) > 0


def test_get_model_digest_section_empty_when_no_events():
    with patch.object(digest_module, "_load_recent_events", return_value=[]):
        section = digest_module.get_model_digest_section()
    assert section == ""
