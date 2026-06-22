"""Tests for the LLM call observability layer (Lane E)."""

from __future__ import annotations

import json

import pytest

from gateway import observability


def _read_calls(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_record_chat_appends_one_line_per_call(tmp_path):
    log = tmp_path / "llm_calls.jsonl"
    with observability.record_chat("kitty-sonnet", log_path=log):
        pass
    with observability.record_chat("kitty-sonnet", log_path=log):
        pass

    entries = _read_calls(log)
    assert len(entries) == 2
    for entry in entries:
        assert entry["model"] == "kitty-sonnet"
        assert entry["success"] is True
        assert entry["error"] is None
        assert entry["latency_ms"] >= 0
        assert "timestamp" in entry


def test_record_chat_records_success_when_body_returns(tmp_path):
    log = tmp_path / "llm_calls.jsonl"
    with observability.record_chat("kitty-sonnet", log_path=log):
        result = 42
    entries = _read_calls(log)
    assert len(entries) == 1
    assert entries[0]["success"] is True
    assert entries[0]["error"] is None
    assert result == 42


def test_record_chat_records_failure_when_body_raises(tmp_path):
    log = tmp_path / "llm_calls.jsonl"
    with pytest.raises(RuntimeError, match="boom"):
        with observability.record_chat("kitty-sonnet", log_path=log):
            raise RuntimeError("boom")

    entries = _read_calls(log)
    assert len(entries) == 1
    assert entries[0]["success"] is False
    assert "RuntimeError" in entries[0]["error"]
    assert "boom" in entries[0]["error"]


def test_record_chat_carries_operation_and_correlation_id(tmp_path):
    log = tmp_path / "llm_calls.jsonl"
    with observability.record_chat(
        "kitty-sonnet",
        operation="brief.synthesis",
        correlation_id="corr-123",
        log_path=log,
    ):
        pass

    entries = _read_calls(log)
    assert entries[0]["operation"] == "brief.synthesis"
    assert entries[0]["correlation_id"] == "corr-123"


def test_record_chat_measures_latency(tmp_path):
    import time

    log = tmp_path / "llm_calls.jsonl"
    with observability.record_chat("kitty-sonnet", log_path=log):
        time.sleep(0.05)

    entries = _read_calls(log)
    assert entries[0]["latency_ms"] >= 50.0


def test_record_chat_caller_can_set_token_counts(tmp_path):
    log = tmp_path / "llm_calls.jsonl"
    with observability.record_chat("kitty-sonnet", log_path=log) as call:
        call.prompt_tokens = 100
        call.completion_tokens = 50

    entries = _read_calls(log)
    assert entries[0]["prompt_tokens"] == 100
    assert entries[0]["completion_tokens"] == 50


def test_record_chat_does_not_break_call_on_write_failure(tmp_path, monkeypatch):
    log = tmp_path / "nested" / "llm_calls.jsonl"

    def broken_open(*_args, **_kwargs):
        raise OSError("disk full")

    monkeypatch.setattr("builtins.open", broken_open)
    with observability.record_chat("kitty-sonnet", log_path=log):
        pass

    assert True


def test_observability_path_default_under_data_dir():
    from gateway.paths import DATA_DIR

    assert observability.DEFAULT_LOG_PATH.parent == DATA_DIR
    assert observability.DEFAULT_LOG_PATH.name == "llm_calls.jsonl"
