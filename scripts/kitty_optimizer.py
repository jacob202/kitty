#!/usr/bin/env python3
"""
Kitty optimizer: deterministic token + workflow audit.

Modes:
  --quick  : print per-model token usage summary for recent data
  --full   : write docs/optimizer/feedback-latest.md and docs/optimizer/TODO.md
"""

from __future__ import annotations

import argparse
import json
import subprocess
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path


PROJECT = Path(__file__).resolve().parent.parent
DOCS = PROJECT / "docs" / "optimizer"
FEEDBACK = DOCS / "feedback-latest.md"
TODO = DOCS / "TODO.md"
TOKEN_LOG = PROJECT / "data" / "kitty_token_log.jsonl"


def _iter_rows(path: Path):
    if not path.exists():
        return
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def analyze_tokens(days: int = 7) -> dict[str, object]:
    cutoff = datetime.now() - timedelta(days=days)
    total = {
        "calls": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "cached_tokens": 0,
        "estimated": False,
    }
    per_model: dict[str, dict[str, int]] = defaultdict(
        lambda: {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "cached_tokens": 0}
    )

    for row in _iter_rows(TOKEN_LOG):
        ts = row.get("ts", "")
        try:
            if datetime.fromisoformat(ts) < cutoff:
                continue
        except Exception:
            pass

        usage = row.get("usage") or {}
        md = row.get("metadata") or {}
        model = row.get("model", "unknown")

        prompt = int(usage.get("prompt_tokens", 0) or 0)
        completion = int(usage.get("completion_tokens", 0) or 0)
        cached = int(usage.get("cached_tokens", 0) or 0)

        if prompt == 0 and completion == 0:
            # Some providers do not return token usage; estimate from response chars.
            chars = int(md.get("completion_chars", 0) or 0)
            if chars > 0:
                completion = max(1, chars // 4)
                prompt = completion * 3
            else:
                prompt = 200
                completion = 50
            total["estimated"] = True

        total["calls"] += 1
        total["prompt_tokens"] += prompt
        total["completion_tokens"] += completion
        total["cached_tokens"] += cached

        slot = per_model[model]
        slot["calls"] += 1
        slot["prompt_tokens"] += prompt
        slot["completion_tokens"] += completion
        slot["cached_tokens"] += cached

    return {"total": total, "per_model": dict(per_model)}


def _tail_pytest() -> str:
    try:
        result = subprocess.run(
            ["venv/bin/python", "-m", "pytest", "tests/", "-q", "--tb=short"],
            capture_output=True,
            text=True,
            cwd=PROJECT,
            timeout=120,
        )
        lines = (result.stdout or "").strip().splitlines()
        return lines[-1] if lines else "no test output"
    except Exception as exc:
        return f"pytest check failed: {exc}"


def _git_short(n: int = 10) -> list[str]:
    try:
        result = subprocess.run(
            ["git", "log", "--oneline", f"-{n}"],
            capture_output=True,
            text=True,
            cwd=PROJECT,
            timeout=10,
        )
        return [line for line in result.stdout.strip().splitlines() if line][:n]
    except Exception:
        return []


def run_quick() -> int:
    stats = analyze_tokens(days=1)
    total = stats["total"]
    per_model = stats["per_model"]
    print("=== QUICK TOKEN CHECK ===")
    if total["calls"] == 0:
        print("No token usage rows found.")
        return 0
    for model, row in per_model.items():
        tokens = row["prompt_tokens"] + row["completion_tokens"]
        print(f"{model}: {tokens} tokens, {row['calls']} calls")
    return 0


def run_full() -> int:
    DOCS.mkdir(parents=True, exist_ok=True)
    stats = analyze_tokens(days=7)
    total = stats["total"]
    per_model = stats["per_model"]

    lines = [
        f"# Kitty Optimizer Report — {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "## Executive Summary",
        "Automated scan complete. See token and build signals below.",
        "",
        "## Build Health",
        f"- Status: {_tail_pytest()}",
        "",
        "## Token Audit",
    ]

    if total["calls"] == 0:
        lines.append("- No token rows found in data/kitty_token_log.jsonl")
    else:
        est = " (estimated)" if total["estimated"] else ""
        lines.extend(
            [
                f"- Calls: {total['calls']}",
                f"- Prompt tokens: {total['prompt_tokens']:,}{est}",
                f"- Completion tokens: {total['completion_tokens']:,}{est}",
                f"- Cached tokens: {total['cached_tokens']:,}",
                "",
                "### Per-model",
            ]
        )
        for model, row in per_model.items():
            lines.append(
                f"- {model}: calls={row['calls']} prompt={row['prompt_tokens']:,} "
                f"completion={row['completion_tokens']:,} cached={row['cached_tokens']:,}"
            )

    lines.extend(
        [
            "",
            "## Recent Commits",
        ]
    )
    commits = _git_short(8)
    if commits:
        lines.extend([f"- {line}" for line in commits])
    else:
        lines.append("- no recent commits")

    lines.extend(
        [
            "",
            "## Actionable Recommendations",
            "1. [HIGH] Keep delegated context minimal and packetized.",
            "2. [HIGH] Route simple deterministic checks to scripts/tools, not LLM calls.",
            "3. [MED] Run quick startup by default, full startup on demand.",
            "4. [MED] Track cache hit ratio and uncached prompt ratio each handoff.",
        ]
    )

    FEEDBACK.write_text("\n".join(lines) + "\n", encoding="utf-8")

    todo = [
        "# Kitty Optimizer TODO",
        "",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "## Next actions",
        "- [ ] Keep compile->delegate packet schema stable (builder_handoff.v1).",
        "- [ ] Add automated packet quality checks in prompt evals.",
        "- [ ] Alert when token rows have 0 usage and rely on estimation.",
    ]
    TODO.write_text("\n".join(todo) + "\n", encoding="utf-8")
    print(f"Feedback written: {FEEDBACK}")
    print(f"TODO written: {TODO}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Kitty optimizer")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--quick", action="store_true", help="Fast token summary")
    mode.add_argument("--full", action="store_true", help="Full analysis + report files")
    args = parser.parse_args()

    if args.full:
        return run_full()
    return run_quick()


if __name__ == "__main__":
    raise SystemExit(main())

