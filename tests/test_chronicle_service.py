"""Unit tests for the pure chronicle analysis service.

These tests exercise the logic directly — no HTTP, no store, no monkeypatching.
"""

from __future__ import annotations

import pytest

from gateway import chronicle_service as svc


def _chat(
    *,
    title: str = "untitled",
    messages: list[dict] | None = None,
    model: str = "deepseek/deepseek-v4-flash",
    created_at: str | None = None,
    objective: str | None = None,
) -> dict:
    return {
        "id": title,
        "title": title,
        "messages": messages or [],
        "model": model,
        "createdAt": created_at or "2026-07-01T10:00:00+00:00",
        "updatedAt": created_at or "2026-07-01T10:00:00+00:00",
        "objective": objective,
    }


# ---------------------------------------------------------------------------
# Signal extractors
# ---------------------------------------------------------------------------

class TestTopTopics:
    def test_most_common_word_is_first(self):
        chats = [
            _chat(title="python refactoring"),
            _chat(title="python testing"),
            _chat(title="database design"),
        ]
        topics = svc.top_topics(chats)
        assert topics[0] == "python"

    def test_stop_words_are_excluded(self):
        chats = [_chat(title="and the for") for _ in range(5)]
        assert svc.top_topics(chats) == []

    def test_empty_chats(self):
        assert svc.top_topics([]) == []

    def test_at_most_three_topics(self):
        chats = [_chat(title=f"word{i} word{i}") for i in range(10)]
        assert len(svc.top_topics(chats)) <= 3


class TestHourlyDistribution:
    def test_correct_hour_counted(self):
        chats = [_chat(created_at="2026-07-10T14:30:00+00:00")]
        hourly = svc.hourly_distribution(chats)
        assert hourly.get(14) == 1

    def test_unix_timestamp_supported(self):
        # 2026-07-10T08:00:00Z as a float timestamp
        import datetime as _dt
        ts = _dt.datetime(2026, 7, 10, 8, 0, 0, tzinfo=_dt.timezone.utc).timestamp()
        chats = [{"createdAt": ts}]
        hourly = svc.hourly_distribution(chats)
        assert hourly.get(8) == 1

    def test_missing_created_at_skipped(self):
        assert svc.hourly_distribution([{"title": "no date"}]) == {}

    def test_empty_chats(self):
        assert svc.hourly_distribution([]) == {}


class TestSessionLengths:
    def test_counts_messages_per_chat(self):
        chats = [
            _chat(messages=[{}, {}, {}]),
            _chat(messages=[{}]),
        ]
        assert svc.session_lengths(chats) == [3, 1]

    def test_chats_without_messages_key_excluded(self):
        assert svc.session_lengths([{"title": "no messages"}]) == []


class TestModelUsage:
    def test_counts_by_model(self):
        chats = [_chat(model="a"), _chat(model="a"), _chat(model="b")]
        counts = svc.model_usage(chats)
        assert counts["a"] == 2
        assert counts["b"] == 1

    def test_at_most_five_models_returned(self):
        chats = [_chat(model=f"model-{i}") for i in range(10)]
        assert len(svc.model_usage(chats)) <= 5


class TestMessagesCount:
    def test_sums_across_chats(self):
        chats = [
            _chat(messages=[{}, {}]),
            _chat(messages=[{}]),
        ]
        assert svc.messages_count(chats) == 3

    def test_empty(self):
        assert svc.messages_count([]) == 0


# ---------------------------------------------------------------------------
# analyze() — integration of all signals
# ---------------------------------------------------------------------------

class TestAnalyze:
    def test_output_shape(self):
        result = svc.analyze([])
        assert set(result) == {"tip_count", "tips", "summary"}
        assert set(result["summary"]) == {
            "session_count", "message_count", "top_topics", "peak_hour", "model_spread"
        }

    def test_tip_count_matches_list(self):
        chats = [_chat() for _ in range(5)]
        result = svc.analyze(chats)
        assert result["tip_count"] == len(result["tips"])

    def test_new_user_tip_when_no_sessions(self):
        result = svc.analyze([])
        assert any("first session" in t.lower() for t in result["tips"])

    def test_peak_hour_in_summary(self):
        chats = [
            _chat(created_at="2026-07-10T22:00:00+00:00"),
            _chat(created_at="2026-07-11T22:00:00+00:00"),
        ]
        result = svc.analyze(chats)
        assert result["summary"]["peak_hour"] == 22

    def test_peak_hour_none_when_no_chats(self):
        assert svc.analyze([])["summary"]["peak_hour"] is None
