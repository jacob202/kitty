#!/usr/bin/env python3
"""
Unified query routing — domain classification + model selection.
Consolidates DomainRouter, CostRouter, and dead orphan routers.
"""

from __future__ import annotations

import concurrent.futures
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ── Shared types ─────────────────────────────────────────────────────────────

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


class ModelTier(Enum):
    FREE = "free"
    CHEAP = "cheap"
    MODERATE = "moderate"
    EXPENSIVE = "expensive"


@dataclass
class RoutingDecision:
    domain: Domain
    confidence: float
    specialist: str
    reasoning: str
    model_tier: ModelTier | None = None
    model: str | None = None
    model_provider: str | None = None
    model_reasoning: str | None = None


# ── Config ───────────────────────────────────────────────────────────────────

_CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "domain_config.json"
with open(_CONFIG_PATH, "r") as f:
    _CONFIG_DATA = json.load(f)

DOMAIN_CONFIG = _CONFIG_DATA["DOMAIN_CONFIG"]


def get_domain_config(domain_key: str) -> dict:
    return DOMAIN_CONFIG.get(domain_key, DOMAIN_CONFIG["general"])


# ── Domain Classifier ────────────────────────────────────────────────────────

_LLM_FALLBACK_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=2)


class DomainClassifier:
    """
    Classifies a user query into a Domain using keyword matching + LLM fallback.
    Extracted from the original DomainRouter.
    """

    def __init__(self):
        self.domain_patterns = {
            Domain(k): v for k, v in _CONFIG_DATA["DOMAIN_PATTERNS"].items()
        }
        self._keyword_set: set[str] = set()
        for config in self.domain_patterns.values():
            for kw in config["keywords"]:
                self._keyword_set.add(kw.lower())
        self._max_keyword_len = max(
            len(kw) for config in self.domain_patterns.values() for kw in config["keywords"]
        ) if self._keyword_set else 0

    def classify(self, query: str) -> tuple[Domain, float, str, str]:
        query_lower = query.strip().lower()
        result = self._classify_cached(query_lower)
        return (result.domain, result.confidence, result.specialist, result.reasoning)

    @lru_cache(maxsize=256)
    def _classify_cached(self, query_lower: str) -> RoutingDecision:
        if not query_lower:
            return RoutingDecision(
                domain=Domain.GENERAL, confidence=1.0, specialist="Kitty",
                reasoning="Empty query",
            )
        if len(query_lower) < 4:
            return RoutingDecision(
                domain=Domain.GENERAL, confidence=0.9, specialist="Kitty",
                reasoning="Query too short for reliable routing",
            )

        scores = {}
        for domain, config in self.domain_patterns.items():
            matched_keywords = [
                kw for kw in config["keywords"] if kw.lower() in query_lower
            ]
            score = len(matched_keywords)
            confidence = min(1.0, score / 3.0) if score > 0 else 0.0
            if score > 0 and confidence < 0.34:
                confidence = 0.34
            scores[domain] = (confidence, matched_keywords)

        best_domain = max(scores.keys(), key=lambda d: scores[d][0])
        best_confidence, best_matches = scores[best_domain]

        if best_confidence < 0.6:
            llm_result = self._llm_classify(query_lower)
            if llm_result is not None:
                return llm_result

        if best_confidence == 0:
            return RoutingDecision(
                domain=Domain.GENERAL, confidence=0.1, specialist="Kitty",
                reasoning="No keyword signal detected and LLM fallback unavailable, defaulting to general",
            )
        return RoutingDecision(
            domain=best_domain, confidence=best_confidence,
            specialist=self._specialist_for(best_domain),
            reasoning=f"Matched keywords: {', '.join(best_matches[:3])}",
        )

    def _llm_classify(self, query_lower: str) -> RoutingDecision | None:
        try:
            from src.space_kitty.llm_client import call_llm
            valid_domains = [d.value for d in Domain]
            domain_list_str = ", ".join(valid_domains)
            system_prompt = (
                f"Classify the user query into exactly one of these domains: {domain_list_str}. "
                "Return only the domain name in lowercase. If unsure, return 'general'."
            )
            response = call_llm(prompt=query_lower, system_prompt=system_prompt, temperature=0.0).strip().lower()
            for d in Domain:
                if d.value == response or f" {d.value} " in f" {response} ":
                    return RoutingDecision(
                        domain=d, confidence=0.8,
                        specialist=self._specialist_for(d),
                        reasoning=f"LLM classification: {d.value} (low keyword signal)",
                    )
        except Exception as e:
            from src.core.exceptions import handle_exception
            handle_exception(e, context="query_router.llm_classification", silent=True)
        return None

    def get_routing_for_domain(self, domain: Domain) -> RoutingDecision:
        return RoutingDecision(
            domain=domain, confidence=1.0, specialist=self._specialist_for(domain),
            reasoning=f"Manual domain selection: {domain.value}",
        )

    def get_domain_info(self, domain: Domain) -> dict:
        if domain in self.domain_patterns:
            return self.domain_patterns[domain]
        return {"specialist": "Kitty", "description": "General knowledge"}

    def _specialist_for(self, domain: Domain) -> str:
        return self.domain_patterns.get(domain, {}).get("specialist", "Kitty")


# ── Model Selector ───────────────────────────────────────────────────────────

@dataclass
class ModelOption:
    tier: ModelTier
    model: str
    provider: str
    max_complexity: int
    estimated_cost_per_1k: float


class ModelSelector:
    """
    Selects a model tier from query complexity.
    Adapted from the (dead) CostRouter — pure strategy, no budget state.
    """

    OPTIONS: dict[ModelTier, ModelOption] = {
        ModelTier.FREE: ModelOption(
            tier=ModelTier.FREE, model="mlx-community/Qwen3.5-4B-4bit",
            provider="mlx", max_complexity=1, estimated_cost_per_1k=0.0,
        ),
        ModelTier.CHEAP: ModelOption(
            tier=ModelTier.CHEAP, model="qwen/qwen3-235b-a22b-2507",
            provider="openrouter", max_complexity=3, estimated_cost_per_1k=0.0001,
        ),
        ModelTier.MODERATE: ModelOption(
            tier=ModelTier.MODERATE, model="deepseek/deepseek-r1-0528",
            provider="openrouter", max_complexity=4, estimated_cost_per_1k=0.002,
        ),
        ModelTier.EXPENSIVE: ModelOption(
            tier=ModelTier.EXPENSIVE, model="anthropic/claude-sonnet-4-6",
            provider="openrouter", max_complexity=5, estimated_cost_per_1k=0.015,
        ),
    }

    COMPLEXITY_HINTS: dict[int, tuple[str, ...]] = {
        5: ("production", "architecture", "formal proof", "security audit", "full refactor"),
        4: ("debug", "root cause", "multi-step", "optimize", "benchmark", "integration"),
        3: ("write", "implement", "compare", "design", "plan", "analyze"),
        2: ("explain", "summarize", "classify", "outline", "review"),
    }

    def select(self, query: str, domain: Domain | None = None, complexity: int | None = None) -> tuple[ModelTier, str, str, str]:
        if complexity is None:
            complexity = self._compute_complexity(query)
        tier = self._tier_for_complexity(complexity)
        option = self.OPTIONS[tier]
        return (tier, option.model, option.provider, f"complexity T{complexity}")

    def _compute_complexity(self, query: str) -> int:
        import re
        text = (query or "").lower()
        if not text.strip():
            return 0
        score = 1
        for tier, hints in self.COMPLEXITY_HINTS.items():
            if any(hint in text for hint in hints):
                score = max(score, tier)
        if len(text) > 900:
            score = max(score, 4)
        if len(re.findall(r"\b(and|then|also|after|before|while)\b", text)) >= 3:
            score = max(score, 4)
        if "?" in text and len(text) < 160 and score < 3:
            score = max(score, 2)
        return min(5, score)

    @staticmethod
    def _tier_for_complexity(complexity: int) -> ModelTier:
        if complexity <= 1:
            return ModelTier.FREE
        if complexity <= 3:
            return ModelTier.CHEAP
        if complexity == 4:
            return ModelTier.MODERATE
        return ModelTier.EXPENSIVE


# ── Query Router (consolidated) ──────────────────────────────────────────────

class QueryRouter:
    """
    Unified router combining domain classification and model selection.
    Replaces DomainRouter, CostRouter, and the dead SemanticRouter/ToolDispatcher.
    """

    def __init__(self):
        self.domain_classifier = DomainClassifier()
        self.model_selector = ModelSelector()

    def route(self, query: str) -> RoutingDecision:
        decision = self.domain_classifier.classify(query)
        domain, confidence, specialist, reasoning = decision
        model_tier, model, provider, model_reason = self.model_selector.select(query, domain)
        return RoutingDecision(
            domain=domain, confidence=confidence, specialist=specialist,
            reasoning=reasoning, model_tier=model_tier, model=model,
            model_provider=provider, model_reasoning=model_reason,
        )

    def get_routing_for_domain(self, domain: Domain) -> RoutingDecision:
        return self.domain_classifier.get_routing_for_domain(domain)
