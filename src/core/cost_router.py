#!/usr/bin/env python3
"""Cost-aware model routing for Kitty's local-first LLM calls."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class ModelTier(Enum):
    FREE = "free"
    CHEAP = "cheap"
    MODERATE = "moderate"
    EXPENSIVE = "expensive"


@dataclass(frozen=True)
class ModelOption:
    tier: ModelTier
    model: str
    provider: str
    max_complexity: int
    fallback: ModelTier | None
    estimated_cost_per_1k: float


@dataclass
class BudgetState:
    daily_limit: float = 1.00
    spent_today: float = 0.0

    @property
    def usage_ratio(self) -> float:
        if self.daily_limit <= 0:
            return 1.0
        return min(1.0, self.spent_today / self.daily_limit)


@dataclass
class ModelRoutingDecision:
    tier: ModelTier
    model: str
    provider: str
    complexity: int
    estimated_cost: float
    warnings: list[str] = field(default_factory=list)
    forced: bool = False
    fallback_tier: ModelTier | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "tier": self.tier.value,
            "model": self.model,
            "provider": self.provider,
            "complexity": self.complexity,
            "estimated_cost": self.estimated_cost,
            "warnings": list(self.warnings),
            "forced": self.forced,
            "fallback_tier": self.fallback_tier.value if self.fallback_tier else None,
        }


class CostRouter:
    """Select a model tier from query complexity, budget, and user overrides.

    Complexity uses a T0-T5 scale:
    - T0/T1: local/free
    - T2/T3: cheap API tier
    - T4: moderate reasoning tier
    - T5: expensive/best-effort tier
    """

    OPTIONS: dict[ModelTier, ModelOption] = {
        ModelTier.FREE: ModelOption(
            tier=ModelTier.FREE,
            model="mlx-community/Qwen3.5-4B-4bit",
            provider="mlx",
            max_complexity=1,
            fallback=None,
            estimated_cost_per_1k=0.0,
        ),
        ModelTier.CHEAP: ModelOption(
            tier=ModelTier.CHEAP,
            model="qwen/qwen3-235b-a22b-2507",
            provider="openrouter",
            max_complexity=3,
            fallback=ModelTier.FREE,
            estimated_cost_per_1k=0.0001,
        ),
        ModelTier.MODERATE: ModelOption(
            tier=ModelTier.MODERATE,
            model="deepseek/deepseek-r1-0528",
            provider="openrouter",
            max_complexity=4,
            fallback=ModelTier.CHEAP,
            estimated_cost_per_1k=0.002,
        ),
        ModelTier.EXPENSIVE: ModelOption(
            tier=ModelTier.EXPENSIVE,
            model="anthropic/claude-sonnet-4-6",
            provider="openrouter",
            max_complexity=5,
            fallback=ModelTier.MODERATE,
            estimated_cost_per_1k=0.015,
        ),
    }

    OVERRIDES = {
        ModelTier.FREE: ("free", "local", "offline", "mlx", "tier 0", "tier 1"),
        ModelTier.CHEAP: ("cheap", "budget", "save money", "qwen", "tier 2"),
        ModelTier.MODERATE: ("moderate", "balanced", "deepseek", "reasoning", "r1", "tier 3", "tier 4"),
        ModelTier.EXPENSIVE: ("premium", "expensive", "claude", "sonnet", "best", "tier 5"),
    }

    COMPLEXITY_HINTS = {
        5: ("production", "architecture", "formal proof", "security audit", "full refactor"),
        4: ("debug", "root cause", "multi-step", "optimize", "benchmark", "integration"),
        3: ("write", "implement", "compare", "design", "plan", "analyze"),
        2: ("explain", "summarize", "classify", "outline", "review"),
    }

    def __init__(self, budget: BudgetState | None = None):
        if budget:
            self.budget = budget
        else:
            try:
                from src.space_kitty.llm_client import get_today_spend
                spend = get_today_spend()
                self.budget = BudgetState(spent_today=spend.get("total_usd", 0.0))
            except Exception:
                self.budget = BudgetState()

    def route(self, query: str, estimated_tokens: int | None = None) -> ModelRoutingDecision:
        text = query or ""
        forced_tier = self._forced_tier(text)
        complexity = self.classify_complexity(text)
        tier = forced_tier or self._tier_for_complexity(complexity)

        if self.budget.usage_ratio >= 0.95 and forced_tier != ModelTier.FREE:
            tier = ModelTier.FREE
        elif self.budget.usage_ratio >= 0.80 and forced_tier is None:
            tier = min(tier, ModelTier.CHEAP, key=self._tier_rank)

        option = self.OPTIONS[tier]
        token_count = estimated_tokens or self._estimate_tokens(text)
        estimated_cost = self.estimate_cost(option, token_count)
        warnings = self._budget_warnings(estimated_cost)

        if forced_tier:
            warnings.append(f"user forced {forced_tier.value} tier")

        return ModelRoutingDecision(
            tier=tier,
            model=option.model,
            provider=option.provider,
            complexity=complexity,
            estimated_cost=estimated_cost,
            warnings=warnings,
            forced=forced_tier is not None,
            fallback_tier=option.fallback,
        )

    def classify_complexity(self, query: str) -> int:
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

    def estimate_cost(self, option: ModelOption, estimated_tokens: int) -> float:
        return round((max(0, estimated_tokens) / 1000.0) * option.estimated_cost_per_1k, 6)

    def _forced_tier(self, query: str) -> ModelTier | None:
        text = (query or "").lower()
        for tier, keywords in self.OVERRIDES.items():
            if any(keyword in text for keyword in keywords):
                return tier
        return None

    def _tier_for_complexity(self, complexity: int) -> ModelTier:
        if complexity <= 1:
            return ModelTier.FREE
        if complexity <= 3:
            return ModelTier.CHEAP
        if complexity == 4:
            return ModelTier.MODERATE
        return ModelTier.EXPENSIVE

    def _budget_warnings(self, estimated_cost: float) -> list[str]:
        projected = self.budget.spent_today + estimated_cost
        ratio = projected / self.budget.daily_limit if self.budget.daily_limit > 0 else 1.0

        if ratio >= 0.95:
            return ["daily budget at or above 95%; defaulting toward free/local models"]
        if ratio >= 0.80:
            return ["daily budget at or above 80%; prefer cheap or free models"]
        if ratio >= 0.50:
            return ["daily budget at or above 50%; watch paid model usage"]
        return []

    def _estimate_tokens(self, query: str) -> int:
        words = len((query or "").split())
        return max(256, int(words * 1.35) + 512)

    def _tier_rank(self, tier: ModelTier) -> int:
        return {
            ModelTier.FREE: 0,
            ModelTier.CHEAP: 1,
            ModelTier.MODERATE: 2,
            ModelTier.EXPENSIVE: 3,
        }[tier]
