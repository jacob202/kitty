"""Tests for Phase 7: nudge, ambient, context_compactor."""
import pytest


class TestNudge:
    def test_check_returns_list(self):
        from gateway.nudge import check
        nudges = check()
        assert isinstance(nudges, list)

    def test_dismiss(self):
        from gateway.nudge import dismiss
        assert dismiss("test-nudge-id") is True

    def test_get_pending(self):
        from gateway.nudge import get_pending
        assert isinstance(get_pending(), list)


class TestAmbient:
    def test_is_enabled_default_false(self):
        from gateway.ambient import is_enabled
        assert is_enabled() is False

    def test_suggest_domain_disabled(self):
        from gateway.ambient import suggest_domain
        assert suggest_domain() is None

    def test_preload_context_disabled(self):
        from gateway.ambient import preload_context
        result = preload_context()
        assert result["active_app"] is None

    def test_app_domain_map(self):
        from gateway.ambient import APP_DOMAIN_MAP
        assert APP_DOMAIN_MAP["terminal"] == "code"
        assert APP_DOMAIN_MAP["safari"] == "research"


class TestContextCompactor:
    def test_estimate_tokens(self):
        from gateway.context_compactor import estimate_tokens
        assert estimate_tokens("hello world") > 0

    def test_should_compact_small(self):
        from gateway.context_compactor import should_compact
        msgs = [
            {"role": "system", "content": "prompt"},
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ]
        assert should_compact(msgs) is False

    def test_should_compact_large(self):
        from gateway.context_compactor import should_compact
        msgs = [{"role": "system", "content": "prompt"}] + [
            {"role": "user", "content": "x" * 5000},
            {"role": "assistant", "content": "y" * 5000},
            {"role": "user", "content": "z" * 1000},
            {"role": "assistant", "content": "w" * 1000},
            {"role": "user", "content": "last"},
            {"role": "assistant", "content": "final"},
        ]
        assert should_compact(msgs, max_tokens=2000) is True

    def test_compact_reduces_messages(self):
        from gateway.context_compactor import compact
        msgs = [
            {"role": "system", "content": "base prompt"},
            {"role": "user", "content": "topic A"},
            {"role": "assistant", "content": "response A"},
            {"role": "user", "content": "topic B"},
            {"role": "assistant", "content": "response B"},
            {"role": "user", "content": "topic C"},
            {"role": "assistant", "content": "response C"},
        ]
        result = compact(msgs)
        assert len(result) < len(msgs)

    def test_compact_preserves_last_messages(self):
        from gateway.context_compactor import compact
        msgs = [
            {"role": "system", "content": "base"},
            {"role": "user", "content": "old"},
            {"role": "assistant", "content": "old response"},
            {"role": "user", "content": "old2"},
            {"role": "assistant", "content": "old2 response"},
            {"role": "user", "content": "recent question"},
            {"role": "assistant", "content": "recent answer"},
        ]
        result = compact(msgs)
        assert result[-2]["content"] == "recent question"
        assert result[-1]["content"] == "recent answer"
