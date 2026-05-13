"""Tests for Phase 6: health_parser, patterns, chat_import."""
import json
import pytest
import tempfile
from pathlib import Path


class TestHealthParser:
    def test_parse_empty(self):
        from gateway.health_parser import parse_export
        result = parse_export("/nonexistent/file.xml")
        assert result == []

    def test_parse_minimal_xml(self):
        import tempfile
        xml = """<?xml version="1.0"?>
        <HealthData>
            <Record type="HKQuantityTypeIdentifierStepCount" value="5000" unit="count"
                    startDate="2026-05-10 08:00:00 -0600" sourceName="iPhone"/>
            <Record type="HKQuantityTypeIdentifierHeartRate" value="72" unit="count/min"
                    startDate="2026-05-10 09:00:00 -0600" sourceName="Apple Watch"/>
        </HealthData>"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
            f.write(xml)
            path = f.name
        try:
            from gateway.health_parser import parse_export
            records = parse_export(path)
            assert len(records) >= 2
        finally:
            Path(path).unlink(missing_ok=True)

    def test_weekly_summary(self):
        from gateway.health_parser import get_weekly_summary
        summary = get_weekly_summary([])
        assert summary["sleep"]["count"] == 0

    def test_format_summary(self):
        from gateway.health_parser import _format_summary_for_ingestion
        text = _format_summary_for_ingestion({
            "period": "test",
            "sleep": {"avg_hours": 7.5, "count": 5},
            "steps": {"total": 35000, "avg_daily": 5000},
        })
        assert "7.5h" in text
        assert "35000" in text


class TestPatterns:
    def test_analyze_empty(self):
        from gateway.patterns import analyze
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("gateway.patterns._load_traces", lambda days: [])
            result = analyze(30)
            assert result["total_interactions"] == 0

    def test_analyze_with_data(self):
        from gateway.patterns import analyze
        import time
        traces = [
            {"timestamp": time.time() - 3600, "domain_classified": "code", "elapsed_ms": 500},
            {"timestamp": time.time() - 7200, "domain_classified": "soul", "elapsed_ms": 300},
            {"timestamp": time.time() - 86400, "domain_classified": "repair", "elapsed_ms": 800},
        ]
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("gateway.patterns._load_traces", lambda days: traces)
            result = analyze(7)
            assert result["total_interactions"] == 3
            assert result["top_domains"][0][0] == "code"

    def test_get_insight_text(self):
        from gateway.patterns import get_insight_text
        text = get_insight_text(7)
        assert isinstance(text, str)


class TestChatImport:
    def test_parse_claude_empty(self):
        from gateway.chat_import import parse_claude_export
        assert parse_claude_export("/nonexistent") == []

    def test_parse_claude_messages(self):
        import tempfile, json
        data = [
            {"chat_messages": [
                {"sender": "human", "text": "Hello", "created_at": "2026-01-01"},
                {"sender": "assistant", "text": "Hi there", "created_at": "2026-01-01"},
            ]}
        ]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            path = f.name
        try:
            from gateway.chat_import import parse_claude_export
            msgs = parse_claude_export(path)
            assert len(msgs) == 2
            assert msgs[0]["role"] == "user"
            assert msgs[1]["role"] == "assistant"
        finally:
            Path(path).unlink(missing_ok=True)

    def test_parse_chatgpt_empty(self):
        from gateway.chat_import import parse_chatgpt_export
        assert parse_chatgpt_export("/nonexistent") == []

    def test_ingest_unknown_type(self):
        from gateway.chat_import import ingest_export
        assert ingest_export("/nonexistent", source_type="unknown") == 0
