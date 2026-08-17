"""Summaries for Kitty's append-only token ledger."""
from __future__ import annotations

import json
import os
from collections import defaultdict
from datetime import date as date_cls
from pathlib import Path
from typing import Any

from gateway.paths import KITTY_TOKEN_LOG_FILE

USD_TO_CAD = float(os.environ.get("KITTY_USD_TO_CAD", "1.3710"))
FX_SNAPSHOT_DATE = os.environ.get("KITTY_USD_TO_CAD_DATE", "2026-05-12")

# Snapshot prices from provider docs used for today's estimate.
PRICE_REGISTRY_USD_PER_MTOKENS: dict[str, dict[str, float]] = {
    "deepseek-v4-flash": {"input": 0.14, "cached_input": 0.0028, "output": 0.28},
    "deepseek-v4-pro": {"input": 0.435, "cached_input": 0.003625, "output": 0.87},
    "openrouter/deepseek/deepseek-v4-pro": {"input": 0.435, "cached_input": 0.003625, "output": 0.87},
    "deepseek/deepseek-v4-pro": {"input": 0.435, "output": 0.87},
    "deepseek/deepseek-v4-flash": {"input": 0.09, "output": 0.18},
    "deepseek/deepseek-v4-flash-20260423": {"input": 0.09, "output": 0.18},
    "deepseek/deepseek-r1": {"input": 0.70, "output": 2.50},
    "qwen/qwen3.7-plus": {"input": 0.32, "cached_input": 0.064, "output": 1.28},
    "qwen/qwen3.7-max": {"input": 1.25, "output": 3.75},
    "qwen/qwen3-coder:free": {"input": 0.0, "output": 0.0},
    # OpenRouter provider snapshot, 2026-08-17. These paid Builder model
    # slugs do not pin one provider, so pre-dispatch budgeting must not assume
    # the cheapest/headline route. Use the highest currently listed standard
    # provider input/output price; cached input is conservatively charged at
    # the full input rate because not every provider guarantees a cache
    # discount. This intentionally overestimates rather than underfunds spend.
    "xiaomi/mimo-v2.5": {"input": 0.40, "cached_input": 0.40, "output": 2.00},
    "minimax/minimax-m3": {"input": 0.60, "cached_input": 0.60, "output": 2.40},
}


def load_entries(path: Path = KITTY_TOKEN_LOG_FILE) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    if not path.exists():
        return entries

    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(raw, dict):
                entries.append(raw)
    return entries


def _total_tokens(entry: dict[str, Any]) -> int:
    usage = entry.get("usage")
    if not isinstance(usage, dict):
        return 0
    total = usage.get("total_tokens", 0)
    return total if isinstance(total, int) and total >= 0 else 0


def _is_paid(entry: dict[str, Any]) -> bool:
    metadata = entry.get("metadata")
    if isinstance(metadata, dict) and metadata.get("from_pool") is True:
        return False
    return _total_tokens(entry) > 0


def _sorted_rows(counter: dict[str, dict[str, int]], key_name: str) -> list[dict[str, int | str]]:
    rows: list[dict[str, int | str]] = [{key_name: key, **value} for key, value in counter.items()]
    return sorted(rows, key=lambda row: (int(row["tokens"]), int(row["calls"])), reverse=True)


def filter_entries(
    entries: list[dict[str, Any]],
    *,
    since: str | None = None,
    provider: str | None = None,
) -> list[dict[str, Any]]:
    """Filter ledger entries by ISO date and provider."""
    filtered = entries
    if since:
        since_date = date_cls.fromisoformat(since)
        filtered = [
            entry
            for entry in filtered
            if date_cls.fromisoformat(str(entry.get("date") or "1970-01-01")) >= since_date
        ]
    if provider:
        provider_l = provider.lower()
        filtered = [
            entry
            for entry in filtered
            if str(entry.get("provider") or "").lower() == provider_l
        ]
    return filtered


def _estimate_entry_cost_usd(entry: dict[str, Any]) -> float:
    model = str(entry.get("model") or "")
    pricing = PRICE_REGISTRY_USD_PER_MTOKENS.get(model)
    if not pricing:
        return 0.0

    _usage = entry.get("usage")
    usage = _usage if isinstance(_usage, dict) else {}
    prompt = int(usage.get("prompt_tokens", 0) or 0)
    completion = int(usage.get("completion_tokens", 0) or 0)
    cached = int(usage.get("cached_tokens", 0) or 0)
    uncached_prompt = max(0, prompt - cached)
    input_cost = uncached_prompt * pricing["input"] / 1_000_000
    cached_cost = cached * pricing.get("cached_input", pricing["input"]) / 1_000_000
    output_cost = completion * pricing["output"] / 1_000_000
    return input_cost + cached_cost + output_cost


def summarize_entries(entries: list[dict[str, Any]]) -> dict[str, Any]:
    by_provider: dict[str, dict[str, int]] = defaultdict(lambda: {"calls": 0, "tokens": 0})
    by_model: dict[str, dict[str, int]] = defaultdict(lambda: {"calls": 0, "tokens": 0})
    paid_calls = 0
    tokens = 0
    estimated_usd = 0.0

    for entry in entries:
        provider = str(entry.get("provider") or "unknown")
        model = str(entry.get("model") or "unknown")
        entry_tokens = _total_tokens(entry)
        by_provider[provider]["calls"] += 1
        by_provider[provider]["tokens"] += entry_tokens
        by_model[model]["calls"] += 1
        by_model[model]["tokens"] += entry_tokens
        tokens += entry_tokens
        if _is_paid(entry):
            paid_calls += 1
        estimated_usd += _estimate_entry_cost_usd(entry)

    return {
        "calls": len(entries),
        "paid_calls": paid_calls,
        "tokens": tokens,
        "estimated_usd": round(estimated_usd, 6),
        "estimated_cad": round(estimated_usd * USD_TO_CAD, 6),
        "by_provider": _sorted_rows(by_provider, "provider"),
        "by_model": _sorted_rows(by_model, "model"),
    }
