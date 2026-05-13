"""Summaries for Kitty's append-only token ledger."""
from __future__ import annotations

import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Any

from gateway.paths import DATA_DIR

TOKEN_LOG_PATH = DATA_DIR / "kitty_token_log.jsonl"
USD_TO_CAD = float(os.environ.get("KITTY_USD_TO_CAD", "1.3710"))
FX_SNAPSHOT_DATE = os.environ.get("KITTY_USD_TO_CAD_DATE", "2026-05-12")

# Snapshot prices from OpenRouter official model pages used for today's estimate.
PRICE_REGISTRY_USD_PER_MTOKENS: dict[str, dict[str, float]] = {
    "deepseek/deepseek-v4-flash": {"input": 0.14, "output": 0.28},
    "deepseek/deepseek-v4-flash-20260423": {"input": 0.14, "output": 0.28},
    "deepseek/deepseek-r1": {"input": 0.70, "output": 2.50},
    "qwen/qwen3-coder:free": {"input": 0.0, "output": 0.0},
}


def load_entries(path: Path = TOKEN_LOG_PATH) -> list[dict[str, Any]]:
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
    rows = [{key_name: key, **value} for key, value in counter.items()]
    return sorted(rows, key=lambda row: (int(row["tokens"]), int(row["calls"])), reverse=True)


def _estimate_entry_cost_usd(entry: dict[str, Any]) -> float:
    model = str(entry.get("model") or "")
    pricing = PRICE_REGISTRY_USD_PER_MTOKENS.get(model)
    if not pricing:
        return 0.0

    usage = entry.get("usage") if isinstance(entry.get("usage"), dict) else {}
    prompt = int(usage.get("prompt_tokens", 0) or 0)
    completion = int(usage.get("completion_tokens", 0) or 0)
    return (prompt * pricing["input"] + completion * pricing["output"]) / 1_000_000


def summarize_usage(entries: list[dict[str, Any]]) -> dict[str, Any]:
    totals = {"calls": 0, "tokens": 0}
    paid = {"calls": 0, "tokens": 0}
    estimated_cost = {"usd": 0.0, "cad": 0.0}

    models: dict[str, dict[str, int]] = defaultdict(lambda: {"calls": 0, "tokens": 0})
    operations: dict[str, dict[str, int]] = defaultdict(lambda: {"calls": 0, "tokens": 0})
    routes: dict[str, dict[str, int]] = defaultdict(lambda: {"calls": 0, "tokens": 0})
    recent_dates: dict[str, dict[str, int]] = defaultdict(lambda: {"calls": 0, "tokens": 0})

    for entry in entries:
        totals["calls"] += 1
        tokens = _total_tokens(entry)
        totals["tokens"] += tokens
        estimated_cost["usd"] += _estimate_entry_cost_usd(entry)

        if _is_paid(entry):
            paid["calls"] += 1
            paid["tokens"] += tokens

        model = str(entry.get("model") or "unknown")
        operation = str(entry.get("operation") or "unknown")
        date = str(entry.get("date") or "unknown")
        metadata = entry.get("metadata") if isinstance(entry.get("metadata"), dict) else {}
        route = str(metadata.get("route") or "unknown")

        for bucket, key in (
            (models, model),
            (operations, operation),
            (routes, route),
            (recent_dates, date),
        ):
            bucket[key]["calls"] += 1
            bucket[key]["tokens"] += tokens

    estimated_cost["usd"] = round(estimated_cost["usd"], 4)
    estimated_cost["cad"] = round(estimated_cost["usd"] * USD_TO_CAD, 4)
    return {
        "totals": totals,
        "paid": paid,
        "estimated_cost": estimated_cost,
        "fx": {"usd_to_cad": USD_TO_CAD, "snapshot_date": FX_SNAPSHOT_DATE},
        "models": _sorted_rows(models, "model"),
        "operations": _sorted_rows(operations, "operation"),
        "routes": _sorted_rows(routes, "route"),
        "recent_dates": sorted(
            _sorted_rows(recent_dates, "date"),
            key=lambda row: str(row["date"]),
            reverse=True,
        )[:7],
    }


def format_report(summary: dict[str, Any]) -> str:
    totals = summary["totals"]
    paid = summary["paid"]
    estimated_cost = summary["estimated_cost"]
    fx = summary["fx"]
    lines = [
        "Kitty spend report",
        f"Total ledger rows: {totals['calls']}",
        f"Total logged tokens: {totals['tokens']}",
        f"Paid traffic: {paid['calls']} calls / {paid['tokens']} tokens",
        f"Estimated spend: ${estimated_cost['usd']:.4f} USD / ${estimated_cost['cad']:.4f} CAD",
        f"FX used: 1 USD = {fx['usd_to_cad']:.4f} CAD (Bank of Canada {fx['snapshot_date']})",
        "",
        "Top operations:",
    ]

    for row in summary["operations"][:5]:
        lines.append(f"- {row['operation']}: {row['calls']} calls / {row['tokens']} tokens")

    lines.append("")
    lines.append("Top models:")
    for row in summary["models"][:5]:
        lines.append(f"- {row['model']}: {row['calls']} calls / {row['tokens']} tokens")

    lines.append("")
    lines.append("Routes:")
    for row in summary["routes"][:5]:
        lines.append(f"- {row['route']}: {row['calls']} calls / {row['tokens']} tokens")

    lines.append("")
    lines.append("Recent days:")
    for row in summary["recent_dates"]:
        lines.append(f"- {row['date']}: {row['calls']} calls / {row['tokens']} tokens")

    return "\n".join(lines)
