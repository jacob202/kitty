#!/usr/bin/env python3
"""Summarize KittyBuilder token telemetry JSONL."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize data/kitty_token_log.jsonl telemetry.")
    parser.add_argument(
        "--file",
        type=Path,
        default=Path("data/kitty_token_log.jsonl"),
        help="Path to token-usage JSONL file (default: data/kitty_token_log.jsonl)",
    )
    parser.add_argument(
        "--date",
        default=datetime.now().strftime("%Y-%m-%d"),
        help="Date filter in YYYY-MM-DD (default: today)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.file.exists():
        print(f"No telemetry file found: {args.file}")
        return 1

    totals = {
        "calls": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "reasoning_tokens": 0,
        "cached_tokens": 0,
        "completion_chars": 0,
    }
    per_model = defaultdict(lambda: {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})
    per_provider = defaultdict(int)

    with args.file.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("date") != args.date:
                continue
            totals["calls"] += 1
            provider = row.get("provider", "unknown")
            per_provider[provider] += 1
            model = row.get("model", "unknown")
            usage = row.get("usage") if isinstance(row.get("usage"), dict) else {}
            md = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}

            for key in ("prompt_tokens", "completion_tokens", "total_tokens", "reasoning_tokens", "cached_tokens"):
                val = usage.get(key, 0)
                if isinstance(val, int):
                    totals[key] += val
            comp_chars = md.get("completion_chars", 0)
            if isinstance(comp_chars, int):
                totals["completion_chars"] += comp_chars

            slot = per_model[model]
            slot["calls"] += 1
            for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
                val = usage.get(key, 0)
                if isinstance(val, int):
                    slot[key] += val

    print(f"Token usage summary for {args.date}")
    print(f"  calls: {totals['calls']}")
    print(f"  prompt_tokens: {totals['prompt_tokens']}")
    print(f"  completion_tokens: {totals['completion_tokens']}")
    print(f"  total_tokens: {totals['total_tokens']}")
    print(f"  reasoning_tokens: {totals['reasoning_tokens']}")
    print(f"  cached_tokens: {totals['cached_tokens']}")
    print(f"  completion_chars: {totals['completion_chars']}")

    if per_provider:
        print("\nBy provider:")
        for provider, calls in sorted(per_provider.items(), key=lambda kv: kv[1], reverse=True):
            print(f"  {provider}: {calls} calls")

    if per_model:
        print("\nBy model:")
        rows = sorted(per_model.items(), key=lambda kv: kv[1]["total_tokens"], reverse=True)
        for model, stats in rows:
            print(
                f"  {model:<55} total={stats['total_tokens']} "
                f"prompt={stats['prompt_tokens']} completion={stats['completion_tokens']} "
                f"calls={stats['calls']}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
