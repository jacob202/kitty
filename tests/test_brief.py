"""Tests for gateway.brief and gateway.notify."""

import os
from unittest.mock import MagicMock, patch


def test_brief_item_contract():
    from datetime import datetime

    from contracts.brief_item import BriefItem, NewsHeadline

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
    mock_response.content = b"<rss/>"
    with patch.object(b, "_fetch_feed_response", return_value=mock_response), patch.object(
        b.feedparser, "parse", return_value=mock_feed
    ):
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


def test_detect_research_themes_returns_list():
    """detect_research_themes returns a list of theme dicts from journal."""
    import gateway.brief as b

    fake_entries = [
        {"ts": 1.0, "entry": "Spent the morning on authentication systems for the new gateway."},
        {"ts": 2.0, "entry": "More authentication systems work, plus a bit of performance optimization."},
    ]
    with patch("gateway.brief.recent_entries", return_value=fake_entries):
        result = b.detect_research_themes(limit=5)
    assert isinstance(result, list)
    assert len(result) > 0
    assert "theme" in result[0]
    assert "mentions" in result[0]
    assert "source" in result[0]
    assert result[0]["source"] == "journal"


def test_detect_research_themes_extracts_keywords():
    """detect_research_themes extracts multi-word themes from journal entries."""
    import gateway.brief as b

    fake_entries = [
        {"ts": 1.0, "entry": "I'm learning about authentication systems"},
        {"ts": 2.0, "entry": "performance optimization is key for this project"},
    ]
    with patch("gateway.brief.recent_entries", return_value=fake_entries):
        result = b.detect_research_themes(limit=5)
    assert len(result) > 0
    theme_strings = [t["theme"] for t in result]
    assert any("authentication" in t for t in theme_strings)


def test_detect_research_themes_handles_empty_journal():
    """detect_research_themes returns [] when the journal is empty."""
    import gateway.brief as b

    with patch("gateway.brief.recent_entries", return_value=[]):
        result = b.detect_research_themes()
    assert result == []


def test_detect_research_themes_handles_exception():
    """detect_research_themes returns [] when the journal raises."""
    import gateway.brief as b

    with patch("gateway.brief.recent_entries", side_effect=Exception("disk error")):
        result = b.detect_research_themes()
    assert result == []


def test_detect_research_themes_filters_stopwords():
    """detect_research_themes does not surface common words as themes."""
    import gateway.brief as b

    fake_entries = [
        {"ts": 1.0, "entry": "the and for with that this have from are was but"},
        {"ts": 2.0, "entry": "authentication systems and storage routers"},
    ]
    with patch("gateway.brief.recent_entries", return_value=fake_entries):
        result = b.detect_research_themes(limit=10)
    theme_strings = {t["theme"] for t in result}
    assert "authentication systems" in theme_strings
    assert "storage routers" in theme_strings
    for stop in ("the and", "and for", "for with", "with that", "but not", "are was"):
        assert stop not in theme_strings


def test_detect_research_themes_integration_with_real_journal(tmp_path, monkeypatch):
    """Integration: real recent_entries + real detect_research_themes, no mocks.

    This is the test that proves the function does not fall back to a
    fabricated "general knowledge" theme when there is no signal. If
    you see "general knowledge" surface here, the empty-state
    contract is broken (issue #30).
    """
    import json

    from gateway import brief, journal, journal_store

    log = tmp_path / "journal_entries.jsonl"
    db_file = tmp_path / "kitty" / "kitty.db"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("w") as f:
        f.write(json.dumps({"ts": 1.0, "entry": "old, irrelevant entry"}) + "\n")
    monkeypatch.setattr(journal, "JOURNAL_LOG", log)
    monkeypatch.setattr(journal_store, "JOURNAL_DB_FILE", db_file, raising=False)
    monkeypatch.setattr(journal_store, "LEGACY_JOURNAL_LOG", log, raising=False)
    monkeypatch.setattr(brief, "recent_entries", journal.recent_entries)

    result = brief.detect_research_themes(lookback_days=14, limit=5)
    assert result == []


def test_synthesize_brief_skips_theme_section_when_themes_empty():
    """When no themes are detected, the prompt must not claim Jacob has been working on anything."""
    import gateway.brief as b
    from contracts.brief_item import NewsHeadline

    headlines = [NewsHeadline(title="OAuth news", url="http://x", snippet="")]
    with patch("gateway.context_enrichment.calendar_today_text_sync", return_value=""), \
         patch("gateway.context_enrichment.weather_text_sync", return_value=""), \
         patch("gateway.context_enrichment.todos_text_sync", return_value=""), \
         patch("gateway.llm_client.chat", side_effect=lambda **kwargs: kwargs["messages"][0]["content"]):
        prompt = b.synthesize_brief_with_llm(headlines, "Task", "Memory", themes=[], novelty={})

    assert "YOUR RESEARCH INTERESTS" not in prompt
    assert "general knowledge" not in prompt


def test_rank_headlines_by_relevance_prioritizes_matches():
    """rank_headlines_by_relevance prioritizes headlines matching themes."""
    import gateway.brief as b
    from contracts.brief_item import NewsHeadline

    headlines = [
        NewsHeadline(title="Random tech news", url="http://x1", snippet=""),
        NewsHeadline(title="New OAuth authentication system", url="http://x2", snippet=""),
        NewsHeadline(title="React released", url="http://x3", snippet=""),
    ]
    themes = [
        {"theme": "authentication systems", "mentions": 5, "confidence": 0.92},
    ]
    result = b.rank_headlines_by_relevance(headlines, themes)
    assert len(result) == 3
    # OAuth headline should be ranked higher (matches "authentication")
    assert "OAuth" in result[0].title


def test_rank_headlines_by_relevance_empty_themes():
    """rank_headlines_by_relevance returns unranked headlines if no themes."""
    import gateway.brief as b
    from contracts.brief_item import NewsHeadline

    headlines = [
        NewsHeadline(title="Article A", url="http://x1", snippet=""),
        NewsHeadline(title="Article B", url="http://x2", snippet=""),
    ]
    result = b.rank_headlines_by_relevance(headlines, [])
    assert result == headlines


def test_rank_headlines_returns_reordered_headlines():
    """rank_headlines_by_relevance returns headlines in new order."""
    import gateway.brief as b
    from contracts.brief_item import NewsHeadline

    headlines = [
        NewsHeadline(title="Random article", url="http://x1", snippet=""),
        NewsHeadline(title="Authentication system", url="http://x2", snippet=""),
    ]
    themes = [{"theme": "authentication", "mentions": 5, "confidence": 0.92}]
    result = b.rank_headlines_by_relevance(headlines, themes)
    assert len(result) == 2
    assert result[0].title == "Authentication system"  # Matched theme should be first


def test_detect_brief_novelty_no_cache():
    """detect_brief_novelty marks everything as new when no cache exists."""
    import gateway.brief as b
    from contracts.brief_item import NewsHeadline

    headlines = [
        NewsHeadline(title="Article A", url="http://x1", snippet=""),
        NewsHeadline(title="Article B", url="http://x2", snippet=""),
    ]
    with patch.object(b, "get_cached_brief", return_value=None):
        result = b.detect_brief_novelty(headlines, [])
    assert result["new_count"] == len(headlines)
    assert result["repeated_count"] == 0
    assert len(result["novel_headlines"]) > 0
    assert "summary" in result


def test_detect_brief_novelty_compares_against_cache():
    """detect_brief_novelty detects novel headlines vs cached ones."""
    import gateway.brief as b
    from contracts.brief_item import NewsHeadline

    headlines = [
        NewsHeadline(title="New Article", url="http://x1", snippet=""),
        NewsHeadline(title="Cached Article", url="http://x2", snippet=""),
    ]
    cached = {
        "headlines": [
            {"title": "Cached Article"},
            {"title": "Old Article"},
        ]
    }
    with patch.object(b, "get_cached_brief", return_value=cached):
        result = b.detect_brief_novelty(headlines, [])
    assert result["new_count"] == 1
    assert result["repeated_count"] == 1
    assert "New Article" in [h.title for h in result["novel_headlines"]]


def test_generate_brief_orchestrates_context_functions():
    """generate_brief calls detect_research_themes, rank_headlines, and detect_novelty."""
    import gateway.brief as b
    from contracts.brief_item import NewsHeadline

    mock_headlines = [NewsHeadline(title="Test", url="http://x", snippet="")]
    with patch.object(b, "fetch_news", return_value=mock_headlines), patch.object(
        b, "_fetch_memory_snippet", return_value=""
    ), patch.object(b, "get_tasks_summary", return_value="Task"), patch.object(
        b, "detect_research_themes", return_value=[]
    ) as mock_themes, patch.object(
        b, "rank_headlines_by_relevance", return_value=mock_headlines
    ) as mock_rank, patch.object(
        b, "detect_brief_novelty", return_value={"summary": "new"}
    ) as mock_novelty, patch(
        "gateway.llm_client.chat", return_value="Brief text"
    ):
        result = b.generate_brief()
    # Verify orchestration functions were called
    mock_themes.assert_called_once()
    mock_rank.assert_called_once()
    mock_novelty.assert_called_once()
    assert "intention" in result


def test_synthesize_brief_includes_theme_context():
    """synthesize_brief_with_llm includes theme context in prompt when provided."""
    import gateway.brief as b
    from contracts.brief_item import NewsHeadline

    headlines = [NewsHeadline(title="OAuth news", url="http://x", snippet="")]
    themes = [{"theme": "authentication", "mentions": 5, "confidence": 0.92}]

    with patch("gateway.context_enrichment.calendar_today_text_sync", return_value=""), \
         patch("gateway.context_enrichment.weather_text_sync", return_value=""), \
         patch("gateway.context_enrichment.todos_text_sync", return_value=""), \
         patch("gateway.brief._fetch_recent_journal_text", return_value=""), \
         patch("gateway.llm_client.chat", side_effect=lambda **kwargs: kwargs["messages"][0]["content"]):
        prompt = b.synthesize_brief_with_llm(headlines, "Task", "Memory", themes=themes)

    assert "authentication" in prompt
