import pytest
from src.core.specialists.news import NewsFeedSpecialist

def test_news_specialist_instantiation():
    """Verify that NewsFeedSpecialist can be instantiated."""
    specialist = NewsFeedSpecialist("News", "news", "data/knowledge_bases/news/")
    assert specialist.name == "News"
    assert specialist.domain == "news"

def test_news_specialist_personality():
    """Verify personality string."""
    specialist = NewsFeedSpecialist("News", "news", "data/knowledge_bases/news/")
    personality = specialist._get_personality()
    assert "sharp" in personality.lower()
    assert "analytical" in personality.lower()

def test_news_specialist_system_prompt():
    """Verify system prompt returns expected shape."""
    specialist = NewsFeedSpecialist("News", "news", "data/knowledge_bases/news/")
    prompt = specialist._get_system_prompt()
    assert "News Feed Specialist" in prompt
    assert "aggregating" in prompt.lower()
    assert "noise" in prompt.lower()

def test_news_specialist_safety_topics():
    """Verify safety output returns expected shape."""
    specialist = NewsFeedSpecialist("News", "news", "data/knowledge_bases/news/")
    topics = specialist._get_safety_topics()
    assert isinstance(topics, list)
    assert "misinformation" in topics
    assert "fake news" in topics
