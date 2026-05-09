"""Tests for the unified retrieval strategy."""

from __future__ import annotations

from src.memory.retrieval_strategy import (
    RetrievalStrategy,
    RetrievalStrategyConfig,
    UnifiedRetrievalAdapter
)


def test_retrieval_strategy_init():
    """Test that RetrievalStrategy initializes with default config."""
    strategy = RetrievalStrategy()
    assert strategy.config is not None
    assert "knowledge" in strategy.config.ingest_policy


def test_retrieval_strategy_custom_config():
    """Test that RetrievalStrategy accepts custom config."""
    custom_config = RetrievalStrategyConfig(
        ingest_policy={"test": "test_store"},
        fallback_domains_map={"test": [None]}
    )
    strategy = RetrievalStrategy(custom_config)
    assert strategy.config.ingest_policy["test"] == "test_store"


def test_get_ingest_target():
    """Test getting ingest target for data kinds."""
    strategy = RetrievalStrategy()
    assert strategy.get_ingest_target("knowledge") == "lightrag"
    assert strategy.get_ingest_target("journal") == "journaldb"
    assert strategy.get_ingest_target("unknown") is None


def test_validate_ingest_target():
    """Test validating ingest targets."""
    strategy = RetrievalStrategy()
    
    # Valid target
    is_valid, error = strategy.validate_ingest_target("knowledge", "lightrag")
    assert is_valid is True
    assert error is None
    
    # Invalid target
    is_valid, error = strategy.validate_ingest_target("knowledge", "wrong_store")
    assert is_valid is False
    assert "wrong-store write blocked" in error
    
    # Unknown data kind
    is_valid, error = strategy.validate_ingest_target("unknown", "any_store")
    assert is_valid is False
    assert "unknown data_kind" in error


def test_get_fallback_domains():
    """Test getting fallback domains."""
    strategy = RetrievalStrategy()
    assert strategy.get_fallback_domains(None) == [None]
    assert strategy.get_fallback_domains("general") == ["general", None]
    assert strategy.get_fallback_domains("specific") == ["specific"]


def test_unified_retrieval_adapter():
    """Test the unified retrieval adapter."""
    # Mock search functions
    def mock_lightrag_search(question):
        if "test" in question:
            return "LightRAG result for: " + question
        return ""
    
    def mock_memory_search(question, domain):
        if "memory" in question:
            return "Memory result for: " + question
        return ""
    
    def mock_is_empty_lightrag_result(result):
        return not result or "not found" in result.lower()
    
    strategy = RetrievalStrategy()
    adapter = UnifiedRetrievalAdapter(
        strategy=strategy,
        lightrag_search=mock_lightrag_search,
        memory_search=mock_memory_search,
        is_empty_lightrag_result=mock_is_empty_lightrag_result
    )
    
    # Test LightRAG hit
    hits = adapter.query("test question", "audio")
    assert len(hits) == 1
    assert hits[0].source_store == "lightrag"
    assert hits[0].text == "LightRAG result for: test question"
    
    # Test memory fallback
    hits = adapter.query("memory question", "audio")
    assert len(hits) == 1
    assert hits[0].source_store == "chromadb"
    assert hits[0].text == "Memory result for: memory question"
    
    # Test no results
    hits = adapter.query("random question", "audio")
    assert len(hits) == 0