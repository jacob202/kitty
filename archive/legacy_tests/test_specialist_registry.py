import pytest
from src.core.specialists.registry import SPECIALISTS, get_specialist, list_specialists

def test_registry_includes_news():
    """Verify that NewsFeedSpecialist is correctly wired into the registry."""
    assert "News" in SPECIALISTS
    assert "News" in list_specialists()

def test_get_specialist_news():
    """Verify that get_specialist retrieves the News specialist."""
    news_spec = get_specialist("News")
    assert news_spec is not None
    assert news_spec.domain == "news"
    assert news_spec.name == "News"
