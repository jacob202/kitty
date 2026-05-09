"""Unified retrieval strategy for memory operations - combines routing and retrieval logic."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional
from src.memory.retrieval_adapter import RetrievalHit, RetrievalAdapter


@dataclass
class RetrievalStrategyConfig:
    """Configuration for retrieval strategy."""
    # Ingestion policies - where different types of data should be stored
    ingest_policy: dict[str, str] = field(default_factory=lambda: {
        "knowledge": "lightrag",
        "journal": "journaldb",
    })
    
    # Fallback domains for retrieval when primary domain yields no results
    fallback_domains_map: dict[str, List[Optional[str]]] = field(default_factory=lambda: {
        None: [None],
        "general": ["general", None],
    })


class RetrievalStrategy:
    """Unified strategy for memory retrieval and ingestion routing."""
    
    def __init__(self, config: Optional[RetrievalStrategyConfig] = None):
        self.config = config or RetrievalStrategyConfig()
    
    def get_ingest_target(self, data_kind: str) -> Optional[str]:
        """Get the target store for ingesting a specific kind of data."""
        return self.config.ingest_policy.get(data_kind)
    
    def validate_ingest_target(self, data_kind: str, requested_store: str) -> tuple[bool, Optional[str]]:
        """
        Validate if the requested store is appropriate for the data kind.
        
        Returns:
            (is_valid, error_message) - is_valid is True if valid, False otherwise
        """
        required_store = self.get_ingest_target(data_kind)
        if required_store is None:
            return False, f"unknown data_kind: {data_kind}"
        
        if requested_store != required_store:
            return False, (
                f"wrong-store write blocked: data_kind '{data_kind}' must use '{required_store}', "
                f"not '{requested_store}'"
            )
        
        return True, None
    
    def get_fallback_domains(self, domain: Optional[str]) -> List[Optional[str]]:
        """Get fallback domains to try when primary domain yields no results."""
        return self.config.fallback_domains_map.get(domain, [domain])


@dataclass
class UnifiedRetrievalAdapter(RetrievalAdapter):
    """Unified retrieval adapter that uses RetrievalStrategy for decision making."""
    
    # Search functions
    lightrag_search: Callable[[str], str]
    memory_search: Callable[[str, Optional[str]], str]
    is_empty_lightrag_result: Callable[[str], bool]
    strategy: RetrievalStrategy
    backend_name: str = "unified"
    
    def query(self, question: str, domain: Optional[str]) -> List[RetrievalHit]:
        """Query using the unified strategy with fallback logic."""
        # Try LightRAG first
        lightrag_result = self.lightrag_search(question)
        if lightrag_result and not self.is_empty_lightrag_result(lightrag_result):
            return [
                RetrievalHit(
                    text=lightrag_result,
                    source_store="lightrag",
                    domain=domain,
                )
            ]
        
        # Try memory search with fallback domains
        for fallback_domain in self.strategy.get_fallback_domains(domain):
            memory_result = self.memory_search(question, fallback_domain)
            if memory_result:
                return [
                    RetrievalHit(
                        text=memory_result,
                        source_store="chromadb",
                        domain=fallback_domain,
                        metadata={"fallback_from_domain": domain} if fallback_domain != domain else {},
                    )
                ]
        
        return []


# Default strategy instance for convenience
default_strategy = RetrievalStrategy()