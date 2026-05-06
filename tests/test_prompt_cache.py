"""
Tests for prompt caching infrastructure.
"""

import pytest
import time
from src.core.prompt_cache import (
    PromptCache,
    SemanticCache,
    estimate_tokens,
    truncate_to_token_budget,
)


class TestPromptCache:
    def test_anthropic_cache_preparation(self):
        cache = PromptCache(provider="anthropic")
        long_prompt = "x" * 5000  # ~1250 tokens
        result = cache.prepare_system_prompt(long_prompt, cacheable=True)
        assert isinstance(result, list)
        assert "cache_control" in result[0]

    def test_anthropic_short_prompt_no_cache(self):
        cache = PromptCache(provider="anthropic")
        short_prompt = "x" * 100  # ~25 tokens
        result = cache.prepare_system_prompt(short_prompt, cacheable=True)
        assert isinstance(result, str)

    def test_openai_no_modification(self):
        cache = PromptCache(provider="openai")
        prompt = "Test system prompt"
        result = cache.prepare_system_prompt(prompt)
        assert result == prompt

    def test_stats(self):
        cache = PromptCache()
        cache.cache_hits = 10
        cache.cache_misses = 5
        stats = cache.get_stats()
        assert stats["cache_hits"] == 10
        assert stats["hit_rate_percent"] == 66.67


class TestSemanticCache:
    @pytest.fixture
    def cache(self, tmp_path):
        return SemanticCache(
            db_path=str(tmp_path / "test_cache.db"), ttl_seconds=3600
        )

    def test_store_and_retrieve(self, cache):
        cache.put("openai", "gpt-4", "system", "user query", "response text")
        result = cache.get("openai", "gpt-4", "system", "user query")
        assert result == "response text"

    def test_miss_on_different_query(self, cache):
        cache.put("openai", "gpt-4", "system", "query1", "response1")
        result = cache.get("openai", "gpt-4", "system", "query2")
        assert result is None

    def test_expiry(self, cache):
        cache.put("openai", "gpt-4", "system", "query", "response")
        # Manually expire by updating created_at
        import sqlite3

        with sqlite3.connect(cache.db_path) as conn:
            conn.execute(
                "UPDATE cache_entries SET created_at = ?",
                (time.time() - 4000,),
            )
        result = cache.get("openai", "gpt-4", "system", "query")
        assert result is None

    def test_stats(self, cache):
        cache.put("openai", "gpt-4", "system", "q1", "r1")
        cache.get("openai", "gpt-4", "system", "q1")
        cache.get("openai", "gpt-4", "system", "q2")
        stats = cache.get_stats()
        assert stats["cache_hits"] == 1
        assert stats["cache_misses"] == 1


class TestTokenHelpers:
    def test_estimate_tokens(self):
        assert estimate_tokens("x" * 100) == 25  # 100/4 = 25

    def test_truncate_to_budget(self):
        long_text = "x" * 10000
        result = truncate_to_token_budget(long_text, max_tokens=100)
        assert estimate_tokens(result) <= 100 + 10  # Allow some margin

    def test_no_truncation_if_under_budget(self):
        short_text = "short"
        result = truncate_to_token_budget(short_text, max_tokens=100)
        assert result == short_text
