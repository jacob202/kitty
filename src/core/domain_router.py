#!/usr/bin/env python3
"""
Domain Router - Routes queries to appropriate specialists
The brain of the orchestrator system
"""

from dataclasses import dataclass
from enum import Enum
from functools import lru_cache


class Domain(Enum):
    AUDIO = "audio"
    AUTOMOTIVE = "automotive"
    CODE = "code"
    CREATIVE = "creative"
    DESIGN = "design"
    FITNESS = "fitness"
    GENERAL = "general"
    GROWTH = "growth"
    INFRASTRUCTURE = "infrastructure"
    RESEARCH = "research"
    SOUL = "soul"


import json
from pathlib import Path

_CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "domain_config.json"
with open(_CONFIG_PATH, "r") as f:
    _CONFIG_DATA = json.load(f)

# Domain behavior flags - controls Kitty's response style per domain
DOMAIN_CONFIG = _CONFIG_DATA["DOMAIN_CONFIG"]


def get_domain_config(domain_key: str) -> dict:
    """Get behavior flags for a domain."""
    return DOMAIN_CONFIG.get(domain_key, DOMAIN_CONFIG["general"])


@dataclass
class RoutingDecision:
    domain: Domain
    confidence: float
    specialist: str
    reasoning: str


class DomainRouter:
    """
    Routes user queries to the appropriate domain specialist
    Uses keyword matching, pattern detection, and confidence scoring
    """

    def __init__(self):
        self.domain_patterns = {
            Domain(k): v for k, v in _CONFIG_DATA["DOMAIN_PATTERNS"].items()
        }

        # Pre-built keyword hash set for O(1) lookups
        self._keyword_set: set[str] = set()
        for config in self.domain_patterns.values():
            for kw in config["keywords"]:
                self._keyword_set.add(kw.lower())

        # Pre-computed longest keyword for early termination
        self._max_keyword_len = max(
            len(kw) for config in self.domain_patterns.values() for kw in config["keywords"]
        ) if self._keyword_set else 0

    def route(self, query: str) -> RoutingDecision:
        """
        Route a query to the appropriate domain
        Returns: RoutingDecision with domain, confidence, specialist
        """
        return self._route_cached(query.strip().lower())

    @lru_cache(maxsize=256)
    def _route_cached(self, query_lower: str) -> RoutingDecision:
        """Cached routing via lru_cache."""
        if not query_lower:
            return RoutingDecision(
                domain=Domain.GENERAL,
                confidence=1.0,
                specialist="Kitty",
                reasoning="Empty query",
            )

        # Early exit: very short queries skip keyword matching
        if len(query_lower) < 4:
            return RoutingDecision(
                domain=Domain.GENERAL,
                confidence=0.9,
                specialist="Kitty",
                reasoning="Query too short for reliable routing",
            )

        scores = {}

        # Efficient scoring using pre-built keyword set
        for domain, config in self.domain_patterns.items():
            matched_keywords = [
                kw for kw in config["keywords"]
                if kw.lower() in query_lower
            ]
            score = len(matched_keywords)

            # Normalize score - 1 keyword = 0.34 confidence, 3+ = 1.0
            confidence = min(1.0, score / 3.0) if score > 0 else 0.0
            if score > 0 and confidence < 0.34:
                confidence = 0.34
            scores[domain] = (confidence, matched_keywords)

        # Final Match Logic
        best_domain = max(scores.keys(), key=lambda d: scores[d][0])
        best_confidence, best_matches = scores[best_domain]

        # Threshold: if keyword signal is weak, use LLM classification
        if best_confidence < 0.6:
            try:
                from src.space_kitty.llm_client import call_llm

                valid_domains = [d.value for d in Domain]
                domain_list_str = ", ".join(valid_domains)

                system_prompt = (
                    f"Classify the user query into exactly one of these domains: {domain_list_str}. "
                    "Return only the domain name in lowercase. If unsure, return 'general'."
                )

                llm_response = (
                    call_llm(prompt=query, system_prompt=system_prompt, temperature=0.0)
                    .strip()
                    .lower()
                )

                # Check if response matches any valid domain
                for d in Domain:
                    if d.value == llm_response or (
                        f" {d.value} " in f" {llm_response} "
                    ):
                        return RoutingDecision(
                            domain=d,
                            confidence=0.8,
                            specialist=self.get_domain_info(d)["specialist"],
                            reasoning=f"LLM classification: {d.value} (low keyword signal: {best_confidence:.2f})",
                        )

                # If LLM returned something else (or offline mode), log it and continue to fallback
                if "[offline mode" in llm_response:
                    pass # Continue to zero-signal fallback
                else:
                    # Maybe it returned 'general' or some other text
                    pass
            except Exception as e:
                from src.core.exceptions import handle_exception
                handle_exception(e, context="domain_router.llm_classification", silent=True)


        # Return best keyword match, or fall back to general if zero signal
        if best_confidence == 0:
            return RoutingDecision(
                domain=Domain.GENERAL,
                confidence=0.1,
                specialist="Kitty",
                reasoning="No keyword signal detected and LLM fallback unavailable, defaulting to general",
            )

        return RoutingDecision(
            domain=best_domain,
            confidence=best_confidence,
            specialist=self.domain_patterns[best_domain]["specialist"],
            reasoning=f"Matched keywords: {', '.join(best_matches[:3])}",
        )

    def get_routing_for_domain(self, domain: Domain) -> RoutingDecision:
        """Force a routing decision for a specific domain."""
        info = self.get_domain_info(domain)
        return RoutingDecision(
            domain=domain,
            confidence=1.0,
            specialist=info["specialist"],
            reasoning=f"Manual domain selection: {domain.value}",
        )

    def get_domain_info(self, domain: Domain) -> dict:
        """Get information about a domain"""
        if domain in self.domain_patterns:
            return self.domain_patterns[domain]
        return {"specialist": "Kitty", "description": "General knowledge"}


# Test
if __name__ == "__main__":
    router = DomainRouter()

    test_queries = [
        "My amp is buzzing, what should I check?",
        "How do I fix my squat form?",
        "My Honda won't start",
        "I'm feeling really anxious lately",
        "This UI is too cluttered",
        "Python function not working",
        "What's the weather today?",
    ]

    print("=" * 80)
    print("DOMAIN ROUTER - TEST")
    print("=" * 80)
    print()

    for query in test_queries:
        decision = router.route(query)
        print(f'Query: "{query}"')
        print(f"  → Domain: {decision.domain.value}")
        print(f"  → Specialist: {decision.specialist}")
        print(f"  → Confidence: {decision.confidence:.1%}")
        print(f"  → Reason: {decision.reasoning}")
        print()

    print("✅ Domain Router ready!")
