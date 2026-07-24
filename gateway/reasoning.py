"""Reasoning engine — complexity classifier, model routing, execution receipts.

Part C of packet 028: the per-message optimization layer. Classification
is a pure heuristic (<1ms), never a model call. Routing selects only among
existing LiteLLM aliases — no new aliases, no provider changes.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from gateway.token_usage_log import log_llm_usage

logger = logging.getLogger("kitty.reasoning")

_REASONING_KEYWORDS = frozenset(
    {
        "explain",
        "why",
        "analyze",
        "analyse",
        "reason",
        "think through",
        "break down",
        "compare",
        "pros and cons",
        "pros cons",
        "step by step",
        "walk me through",
        "how does",
        "what causes",
    }
)

_BEST_TRIGGERS = frozenset(
    {
        "best model",
        "use claude",
        "use sonnet",
        "use your best",
        "most capable",
        "smartest model",
    }
)

_DEEP_DOMAINS = frozenset({"health"})


@dataclass(frozen=True)
class Classification:
    """Result of classifying a message's complexity.

    Attributes:
        tier: ``trivial`` | ``standard`` | ``deep``
        trigger: The signal that decided the tier (always non-empty).
    """

    tier: str
    trigger: str

    def __post_init__(self):
        if self.tier not in ("trivial", "standard", "deep"):
            raise ValueError(f"tier must be trivial|standard|deep, got {self.tier!r}")
        if not self.trigger:
            raise ValueError("trigger must be non-empty")


def classify_complexity(message: str, domain: str | None = None) -> Classification:
    """Classify a user message without calling a model.

    Pure heuristic, <1ms. The keyword sets absorbed from
    ``gateway/llm_client.py`` are one signal among several.

    Returns ``Classification(tier, trigger)`` where ``trigger`` names the
    signal that decided.
    """
    lower = message.lower().strip()

    if any(t in lower for t in _BEST_TRIGGERS):
        return Classification(tier="deep", trigger="best_trigger")
    if any(kw in lower for kw in _REASONING_KEYWORDS):
        return Classification(tier="deep", trigger="reasoning_keyword")

    if len(lower) > 500:
        return Classification(tier="deep", trigger="length")

    if not lower.endswith("?"):
        words = lower.split()
        if len(words) <= 3 and len(lower) < 25:
            return Classification(tier="trivial", trigger="short_message")

    if domain is not None and domain in _DEEP_DOMAINS:
        return Classification(tier="deep", trigger="domain")

    return Classification(tier="standard", trigger="default")


# --- Execution receipt ---------------------------------------------------------


@dataclass
class Receipt:
    """Metadata stitched into the existing log_llm_usage() call at every turn.

    Fields are nullable so an incomplete receipt never breaks the log.
    The privacy rule: no raw message, response, or reasoning-content bodies.
    """

    mode: str | None = None
    tier: str | None = None
    trigger: str | None = None
    resolved_model: str | None = None
    correlation_id: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    cap_hit: bool | None = None
    escalation: bool | None = None
    confidence_flag: str | None = None

    def as_metadata(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        if self.tier is not None:
            out["tier"] = self.tier
        if self.trigger is not None:
            out["trigger"] = self.trigger
        if self.mode is not None:
            out["mode"] = self.mode
        if self.resolved_model is not None:
            out["resolved_model"] = self.resolved_model
        if self.correlation_id is not None:
            out["correlation_id"] = self.correlation_id
        if self.cap_hit is not None:
            out["cap_hit"] = self.cap_hit
        if self.escalation is not None:
            out["escalation"] = self.escalation
        if self.confidence_flag is not None:
            out["confidence_flag"] = self.confidence_flag
        return out


def log_receipt(receipt: Receipt, usage: dict[str, int] | None = None) -> None:
    """Append a receipt row to the existing token-log via log_llm_usage."""
    metadata = receipt.as_metadata()
    provider = "kitty"
    model = receipt.resolved_model or "unknown"
    log_llm_usage(
        provider=provider,
        model=model,
        operation="reasoning.receipt",
        usage=usage,
        metadata=metadata,
    )
