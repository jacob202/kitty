"""Tests for gateway.brief and gateway.notify."""

import os
from unittest.mock import patch, MagicMock


def test_brief_item_contract():
    from contracts.brief_item import BriefItem, NewsHeadline
    from datetime import datetime

    item = BriefItem(
        date="2026-05-09",
        headlines=[
            NewsHeadline(title="AI news", url="http://example.com", snippet="test")
        ],
        memory_snippet="Jacob likes cars",
        intention="Today focus on shipping Phase 7.",
    )
    assert item.date == "2026-05-09"
    assert item.headlines[0].title == "AI news"
    assert item.notification_sent is False
    assert isinstance(item.generated_at, datetime)


def test_fetch_news_returns_headlines_on_success():
    import pytest
    import gateway.brief as b

    if b.feedparser is None:
        pytest.skip("feedparser not installed")
    entry = MagicMock()
    entry.title = "Big AI news"
    entry.link = "http://t.co/1"
    entry.get.side_effect = lambda key, default="": {
        "summary": "Something happened",
        "description": "",
    }.get(key, default)
    mock_feed = MagicMock()
    mock_feed.entries = [entry]
    mock_response = MagicMock()
    mock_response.content = b"<rss></rss>"
    with patch.object(b, "_fetch_feed_response", return_value=mock_response), \
         patch.object(b.feedparser, "parse", return_value=mock_feed):
        result = b.fetch_news(limit_per_feed=1)
    assert len(result) >= 1
    assert result[0].title == "Big AI news"


def test_fetch_news_handles_feed_error():
    import pytest
    import gateway.brief as b

    if b.feedparser is None:
        pytest.skip("feedparser not installed")
    with patch.object(b.feedparser, "parse", side_effect=Exception("network error")):
        result = b.fetch_news()
    assert result == []


def test_send_pushover_skips_when_no_keys():
    with patch.dict(os.environ, {"PUSHOVER_USER_KEY": "", "PUSHOVER_API_TOKEN": ""}):
        from gateway.notify import send_pushover

        result = send_pushover("Hello", title="Test")
    assert result is False


def test_send_pushover_returns_true_on_success():
    import gateway.notify as n

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status.return_value = None
    with patch.dict(
        os.environ, {"PUSHOVER_USER_KEY": "ukey", "PUSHOVER_API_TOKEN": "tok"}
    ):
        with patch.object(n.requests, "post", return_value=mock_resp):
            result = n.send_pushover("Msg", title="Title")
    assert result is True


def test_send_pushover_returns_false_on_error():
    import gateway.notify as n

    with patch.dict(
        os.environ, {"PUSHOVER_USER_KEY": "ukey", "PUSHOVER_API_TOKEN": "tok"}
    ):
        with patch.object(n.requests, "post", side_effect=Exception("timeout")):
            result = n.send_pushover("Msg", title="Title")
    assert result is False


def test_format_brief_notification():
    from gateway.notify import format_brief_notification

    brief = {
        "date": "2026-05-09",
        "intention": "Focus on what matters.",
        "headlines": [
            {"title": "AI breakthrough", "url": "http://x.com", "snippet": ""},
        ],
    }
    title, message = format_brief_notification(brief)
    assert "2026-05-09" in title
    assert "Focus on what matters." in message
    assert "AI breakthrough" in message


def test_generate_brief_structure():
    """generate_brief returns a dict matching BriefItem schema."""
    import gateway.brief as b

    with patch.object(b, "fetch_news", return_value=[]):
        with patch.object(b, "_fetch_memory_snippet", return_value=""):
            with patch.object(b, "get_tasks_summary", return_value="Ship Phase 7."):
                with patch("gateway.llm_client.chat", return_value="Ship Phase 7."):
                    result = b.generate_brief()
    assert "date" in result
    assert "headlines" in result
    assert "intention" in result
    assert "Ship Phase 7." in result["intention"]


def test_generate_fast_brief_returns_contract_without_news():
    import gateway.brief as b

    with patch.object(
        b, "_fetch_memory_snippet", return_value="Remember the boring path."
    ):
        with patch.object(b, "get_tasks_summary", return_value="Ship Phase 7."):
            result = b.generate_fast_brief()
    assert result["headlines"] == []
    assert "Ship Phase 7." in result["intention"]
    assert "memory_snippet" in result


def test_cached_brief_round_trip():
    import gateway.brief as b

    sample = {
        "date": "2026-05-18",
        "headlines": [],
        "memory_snippet": "",
        "intention": "Cached brief",
    }
    b._store_cached_brief(sample)
    cached = b.get_cached_brief()
    assert cached is not None
    assert cached["intention"] == "Cached brief"


def test_fetch_memory_snippet_uses_unified_context():
    import gateway.brief as b

    with patch(
        "gateway.memory_graph.unified_context", new=MagicMock(return_value="ctx")
    ):
        with patch("gateway.brief.asyncio.run", side_effect=lambda coro: "ctx"):
            result = b._fetch_memory_snippet()
    assert result == "ctx"


def test_synthesize_brief_prompt_includes_unified_memory():
    import gateway.brief as b
    from contracts.brief_item import NewsHeadline

    headlines = [NewsHeadline(title="AI news", url="http://x", snippet="")]
    with patch(
        "gateway.context_enrichment.calendar_today_text_sync", return_value=""
    ), patch("gateway.context_enrichment.weather_text_sync", return_value=""), patch(
        "gateway.context_enrichment.todos_text_sync", return_value=""
    ), patch(
        "gateway.llm_client.chat",
        side_effect=lambda **kwargs: kwargs["messages"][0]["content"],
    ):
        prompt = b.synthesize_brief_with_llm(
            headlines, "Ship Phase 7.", "## Memory\n- unified context"
        )
    assert "unified context" in prompt
    assert "AI news" in prompt


def test_calendar_today_text_sync_formats_events():
    from gateway.context_enrichment import calendar_today_text_sync

    with patch("gateway.calendar_integration.is_available", return_value=True), patch(
        "gateway.calendar_integration.get_today",
        return_value=[{"start": "9:00", "title": "Standup"}],
    ):
        text = calendar_today_text_sync()
    assert "Today's Schedule:" in text
    assert "Standup" in text
