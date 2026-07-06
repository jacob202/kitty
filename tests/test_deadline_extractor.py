"""Tests for gateway/deadline_extractor.py."""
from __future__ import annotations

import pytest

import json

from gateway import deadline_extractor


def _fake_llm(response: list[dict]):
    def llm_fn(prompt: str, privacy_tier: str, content_class: str | None) -> str:
        assert privacy_tier == "local"
        assert content_class == "health_admin"
        return json.dumps({"deadlines": response})

    return llm_fn


def test_extract_from_text_finds_deadline():
    llm = _fake_llm(
        [
            {
                "due_date": "2026-08-15",
                "obligation": "Renew disability parking permit",
                "amount": "$25",
                "currency": "CAD",
                "confidence": "high",
                "notes": "",
            }
        ]
    )
    results = deadline_extractor.extract_from_text(
        "Please renew by August 15, 2026.", source="knowledge:letter.pdf", llm_fn=llm
    )
    assert len(results) == 1
    assert results[0]["due_date"] == "2026-08-15"
    assert results[0]["obligation"] == "Renew disability parking permit"
    assert results[0]["confidence"] == "high"


def test_extract_skips_empty_obligation():
    llm = _fake_llm([{"due_date": "2026-08-15", "obligation": "", "confidence": "high"}])
    results = deadline_extractor.extract_from_text("text", source="doc", llm_fn=llm)
    assert results == []


def test_extract_needs_jacob_for_ambiguous():
    llm = _fake_llm([{"due_date": None, "obligation": "Some deadline", "confidence": "low"}])
    results = deadline_extractor.extract_from_text("text", source="doc", llm_fn=llm)
    assert results[0]["confidence"] == "needs_jacob"


def test_extract_from_mail_signal_only_mail_source():
    signal = {"source": "calendar", "payload": {"summary": "meeting"}}
    results = deadline_extractor.extract_from_mail_signal(signal, llm_fn=_fake_llm([]))
    assert results == []


def test_extract_from_mail_signal_reads_payload():
    captured = {}

    def llm_fn(prompt: str, privacy_tier: str, content_class: str | None) -> str:
        captured["prompt"] = prompt
        assert privacy_tier == "local"
        assert content_class == "health_admin"
        return '{"deadlines": [{"due_date": "2026-09-01", "obligation": "Pay tuition", "confidence": "medium"}]}'

    signal = {
        "source": "mail",
        "id": 42,
        "payload": {"summary": "Tuition due 2026-09-01", "message_id": "msg-123"},
    }
    results = deadline_extractor.extract_from_mail_signal(signal, llm_fn=llm_fn)
    assert len(results) == 1
    assert results[0]["source"] == "mail"
    assert results[0]["source_id"] == "msg-123"


def test_extract_raises_on_invalid_json():
    def llm_fn(_prompt: str, _tier: str, _cls: str | None) -> str:
        return "not json"

    with pytest.raises(deadline_extractor.DeadlineExtractorError):
        deadline_extractor.extract_from_text("text", source="doc", llm_fn=llm_fn)


def test_extract_raises_on_non_array():
    def llm_fn(_prompt: str, _tier: str, _cls: str | None) -> str:
        return '{"foo": "bar"}'

    with pytest.raises(deadline_extractor.DeadlineExtractorError):
        deadline_extractor.extract_from_text("text", source="doc", llm_fn=llm_fn)
