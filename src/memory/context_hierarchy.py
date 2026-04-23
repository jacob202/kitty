"""
OpenViking Hierarchical Context -- L0/L1/L2 Tiered Retrieval.

Implements three-tier context hierarchy for efficient knowledge access:
- L0: Abstract (domain classification, topic summary) -- fast, ~50 tokens
- L1: Overview (key entities, facts, relationships) -- moderate, ~500 tokens
- L2: Detail (full text chunks, complete information) -- slow, full size

Usage:
    hierarchy = ContextHierarchy()

    # Get all tiers at once
    result = hierarchy.query_tiered("What is the Sansui AU-417?", top_k=3)
    print(result['l0_abstract'])  # Fast domain hint
    print(result['l1_overview'])  # Key facts
    print(result['l2_detail'])    # Full context

    # Or drill down on demand
    if should_go_deep(result['l0_abstract']):
        result['l2_detail'] = hierarchy.get_tier('..document_id..', 'l2')
"""

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class TieredResult:
    """Single document across all tiers."""
    document_id: str
    domain: str  # e.g., "electronics", "automotive", "health"

    l0_abstract: str  # ~50 tokens: "This is about Sansui AU-417 vintage amplifier"
    l1_overview: str  # ~500 tokens: key specs, key entities
    l2_detail: str    # full text: complete information

    relevance_score: float = 0.0


@dataclass
class HierarchyQueryResult:
    """Result from tiered query."""
    query: str
    tier_requested: str  # 'all', 'l0', 'l1', 'l2'
    results: list[TieredResult]
    query_time_ms: float = 0.0
    tier_note: str = ""  # e.g., "showing L0 abstracts (fast)"


class ContextHierarchy:
    """
    Manages hierarchical context extraction and retrieval.

    Wraps LightRAGStore to add:
    1. Automatic tier extraction (L0/L1/L2 from ingested docs)
    2. Lazy-load detail tier (L2 only on demand)
    3. Domain classification (for routing decisions)
    4. Fast L0 summary response times
    """

    def __init__(self, lightrag_store=None, tier_cache_dir: str | None = None):
        """
        Args:
            lightrag_store: LightRAGStore instance (or None to use default)
            tier_cache_dir: where to cache tier extractions (default: data/cache/tiers/)
        """
        self.store = lightrag_store
        self.tier_cache_dir = Path(tier_cache_dir or "data/cache/tiers")
        self.tier_cache_dir.mkdir(parents=True, exist_ok=True)

        # Domain->tier mapping for routing optimization
        self.domain_patterns = {
            "electronics": ["sansui", "amplifier", "capacitor", "resistor", "tube", "circuit"],
            "automotive": ["honda", "ridgeline", "engine", "transmission", "brake"],
            "health": ["supplement", "herb", "vitamin", "wellness", "remedy"],
            "ml": ["neural", "model", "training", "gradient", "network"],
            "reference": [],  # catch-all
        }

    def query_tiered(self, query: str, tier: str = "all", top_k: int = 5) -> HierarchyQueryResult:
        """
        Query LightRAG with tiered result extraction.

        Args:
            query: search query
            tier: 'l0' (abstract only), 'l1' (overview), 'l2' (detail), 'all' (all tiers, L0 loaded)
            top_k: number of documents to retrieve

        Returns:
            HierarchyQueryResult with tiered data
        """
        if not self.store:
            return HierarchyQueryResult(
                query=query,
                tier_requested=tier,
                results=[],
                tier_note="[No LightRAGStore configured]"
            )

        import time
        start_ms = time.time() * 1000

        # Search using LightRAG
        raw_results = self.store.search(query, top_k=top_k)

        # Parse raw results into TieredResult objects
        tiered_results = self._extract_tiers(raw_results, query)

        # If 'all' or 'l0', load L0 abstracts for all results
        if tier in ["all", "l0"]:
            for result in tiered_results:
                if not result.l0_abstract:
                    result.l0_abstract = self._extract_l0(result.l2_detail, result.domain)

        # If 'l1' or 'all', load L1 overviews
        if tier in ["all", "l1"]:
            for result in tiered_results:
                if not result.l1_overview:
                    result.l1_overview = self._extract_l1(result.l2_detail, result.domain)

        # If 'l2' only, don't load detail tier (lazy)
        if tier == "l2":
            for result in tiered_results:
                if not result.l2_detail:
                    result.l2_detail = "[Detail not loaded -- call get_tier() to fetch]"

        query_time_ms = time.time() * 1000 - start_ms

        tier_note = {
            "l0": "showing L0 abstracts (fast, ~50 tokens/result)",
            "l1": "showing L1 overviews (moderate, ~500 tokens/result)",
            "l2": "showing L2 detail (full, may be slow)",
            "all": "showing all tiers (L0 loaded; L1/L2 on demand)",
        }.get(tier, "")

        return HierarchyQueryResult(
            query=query,
            tier_requested=tier,
            results=tiered_results,
            query_time_ms=query_time_ms,
            tier_note=tier_note
        )

    def get_tier(self, document_id: str, tier: str) -> str:
        """
        Fetch a specific tier for a document (lazy-load on demand).

        Args:
            document_id: unique doc ID from TieredResult
            tier: 'l0', 'l1', or 'l2'

        Returns:
            tier content string
        """
        cache_file = self.tier_cache_dir / f"{document_id}_{tier}.json"
        if cache_file.exists():
            try:
                data = json.loads(cache_file.read_text())
                return data.get("content", "")
            except Exception:
                pass

        # Not cached -- would need to re-fetch from store
        return f"[{tier.upper()} not cached for {document_id}]"

    def _extract_tiers(self, raw_results: str, query: str) -> list[TieredResult]:
        """
        Parse LightRAG search results into TieredResult objects.
        For now, treats entire result as L2 detail; L0/L1 extracted on demand.
        """
        if not raw_results or "[LightRAG search error" in raw_results:
            return []

        # Simple heuristic: split on document boundaries if present
        # LightRAG typically returns concatenated text chunks
        docs = raw_results.split("\n---\n") if "\n---\n" in raw_results else [raw_results]

        results = []
        for i, doc_text in enumerate(docs):
            if not doc_text.strip():
                continue

            domain = self._classify_domain(doc_text)
            result = TieredResult(
                document_id=f"doc_{i}_{hash(doc_text[:100]) % 10000}",
                domain=domain,
                l0_abstract="",  # Lazy-extracted
                l1_overview="",  # Lazy-extracted
                l2_detail=doc_text.strip(),
                relevance_score=1.0 - (i * 0.1),  # Simple ranking by order
            )
            results.append(result)

        return results

    def _classify_domain(self, text: str) -> str:
        """
        Classify document domain based on keyword patterns.
        """
        text_lower = text.lower()
        for domain, patterns in self.domain_patterns.items():
            if domain != "reference" and any(p in text_lower for p in patterns):
                return domain
        return "reference"

    def _extract_l0(self, full_text: str, domain: str) -> str:
        """
        Extract L0 abstract (~50 tokens) from L2 detail.
        Uses heuristics: first sentence(s) + domain context.
        """
        sentences = full_text.split(".")[:3]  # First 3 sentences
        abstract = ".".join(sentences).strip()
        if not abstract.endswith("."):
            abstract += "."

        # Add domain context
        return f"[{domain.upper()}] {abstract[:50]}..."

    def _extract_l1(self, full_text: str, domain: str) -> str:
        """
        Extract L1 overview (~500 tokens) from L2 detail.
        Uses heuristics: paragraph headers + key facts.
        """
        # Take first 3 paragraphs
        paragraphs = full_text.split("\n\n")[:3]
        overview = "\n\n".join(paragraphs)

        # Truncate to ~500 tokens (rough: 5 chars per token)
        if len(overview) > 2500:
            overview = overview[:2500] + "..."

        return overview

    def format_result_for_supervisor(self, result: HierarchyQueryResult, tier: str = "l0") -> str:
        """
        Format tiered results for Supervisor output.

        Args:
            result: HierarchyQueryResult from query_tiered()
            tier: which tier to show ('l0', 'l1', 'l2')

        Returns:
            formatted string for display/injection into LLM context
        """
        if not result.results:
            return "[No results found]"

        lines = []
        lines.append(f"Query: {result.query}")
        lines.append(f"Mode: {result.tier_requested} ({result.tier_note})")
        lines.append(f"Time: {result.query_time_ms:.0f}ms")
        lines.append("")

        for i, r in enumerate(result.results, 1):
            lines.append(f"Result {i} [{r.domain}] (relevance: {r.relevance_score:.2f})")

            if tier == "l0" and r.l0_abstract:
                lines.append(f"  {r.l0_abstract}")
            elif tier == "l1" and r.l1_overview:
                for line in r.l1_overview.split("\n")[:5]:
                    lines.append(f"  {line}")
            elif tier == "l2" and r.l2_detail:
                for line in r.l2_detail.split("\n")[:10]:
                    lines.append(f"  {line}")

            lines.append("")

        return "\n".join(lines)


def integrate_with_lightrag(lightrag_store) -> ContextHierarchy:
    """
    Factory function: create a ContextHierarchy bound to a LightRAGStore.

    Usage:
        from src.memory.lightrag_store import LightRAGStore
        from src.memory.context_hierarchy import integrate_with_lightrag

        store = LightRAGStore()
        hierarchy = integrate_with_lightrag(store)
        result = hierarchy.query_tiered("What is the Sansui AU-417?")
    """
    return ContextHierarchy(lightrag_store=lightrag_store)
