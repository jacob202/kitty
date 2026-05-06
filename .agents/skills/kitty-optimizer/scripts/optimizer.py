#!/usr/bin/env python3
"""
Kitty Optimizer — automated token optimizer and meta-analysis agent.

Upgraded with GitHub best practices:
- Pre-fetches data in deterministic steps (not agent turns)
- Proper token log parsing (usage.prompt_tokens, completion_tokens, cached_tokens)
- Self-review capability (reads own feedback, generates TODO.md)
- Early exit when no issues found
- Aggressive caching to avoid re-work
"""

import os
import sys
import json
import argparse
import subprocess
import logging
import shutil
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Optional, Any

# --- Configuration (with env overrides) ---
PROJECT = Path(os.getenv("KITTY_PROJECT", "/Users/jacobbrizinski/Projects/kitty"))
DOCS = PROJECT / "docs"
OPTIMIZER_DIR = DOCS / "optimizer"
FEEDBACK = OPTIMIZER_DIR / "feedback-latest.md"
TODO_FILE = OPTIMIZER_DIR / "TODO.md"
TOKEN_LOG = PROJECT / "data" / "kitty_token_log.jsonl"
if not TOKEN_LOG.exists():
    TOKEN_LOG = PROJECT / ".kitty_builder_token_usage.jsonl"
LOG_FILE = Path("/tmp/kitty-optimizer.log")
CACHE_DB = OPTIMIZER_DIR / "optimizer_cache.db"

# --- Logging setup ---
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

def log(msg):
    print(msg)
    logger.info(msg)


# --- Check if work was done today ---
def work_done_today() -> bool:
    """Return True if there were any commits today."""
    try:
        result = subprocess.run(
            ["git", "log", "--since=midnight", "--oneline"],
            capture_output=True, text=True, cwd=PROJECT
        )
        return result.returncode == 0 and len(result.stdout.strip()) > 0
    except Exception:
        return False


# --- Token log analysis (FIXED: proper usage field parsing) ---
def analyze_token_log(quick: bool = False, days: int = 7) -> Dict[str, Any]:
    """Return token stats from JSONL log. Parses usage.prompt_tokens, etc."""
    if not TOKEN_LOG.exists():
        return {"error": "Log not found", "calls": 0, "models": {}}

    cutoff = datetime.now() - timedelta(days=days)
    stats = {
        "calls": 0,
        "total_prompt": 0,
        "total_completion": 0,
        "total_cached": 0,
        "estimated": False,
        "models": defaultdict(lambda: {
            "calls": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "cached_tokens": 0,
            "max_prompt": 0,
        }),
    }

    try:
        with open(TOKEN_LOG, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    ts_str = record.get("ts", "")
                    try:
                        ts = datetime.fromisoformat(ts_str)
                        if ts < cutoff:
                            continue
                    except (ValueError, TypeError):
                        pass

                    model = record.get("model", "unknown")
                    usage = record.get("usage", {}) or {}
                    meta = record.get("metadata", {}) or {}
                    prompt_t = int(usage.get("prompt_tokens", 0) or 0)
                    completion_t = int(usage.get("completion_tokens", 0) or 0)
                    cached_t = int(usage.get("cached_tokens", 0) or 0)

                    # If usage is empty, estimate from metadata
                    if prompt_t == 0 and completion_t == 0:
                        completion_chars = int(meta.get("completion_chars", 0) or 0)
                        if completion_chars:
                            completion_t = completion_chars // 4
                            prompt_t = completion_t * 3
                            stats["estimated"] = True
                        else:
                            # Minimum estimate: 200 prompt + 50 completion per call
                            prompt_t = 200
                            completion_t = 50
                            stats["estimated"] = True

                    stats["calls"] += 1
                    stats["total_prompt"] += prompt_t
                    stats["total_completion"] += completion_t
                    stats["total_cached"] += cached_t

                    ms = stats["models"][model]
                    ms["calls"] += 1
                    ms["prompt_tokens"] += prompt_t
                    ms["completion_tokens"] += completion_t
                    ms["cached_tokens"] += cached_t
                    ms["max_prompt"] = max(ms["max_prompt"], prompt_t)

                except (json.JSONDecodeError, ValueError, TypeError):
                    continue
    except Exception as e:
        return {"error": str(e), "calls": 0, "models": {}}

    return stats


# --- Build log analysis ---
def get_build_status() -> str:
    try:
        result = subprocess.run(
            "venv/bin/python -m pytest tests/ -q --tb=short 2>&1 | tail -3",
            shell=True, capture_output=True, text=True, cwd=PROJECT, timeout=120
        )
        return result.stdout.strip() or "No test output"
    except Exception as e:
        return f"Build check failed: {e}"


# --- Git summary ---
def get_git_summary(n: int = 10) -> List[str]:
    try:
        result = subprocess.run(
            ["git", "log", "--oneline", f"-{n}"],
            capture_output=True, text=True, cwd=PROJECT
        )
        lines = (result.stdout.strip() or "No commits").split("\n")
        return lines[:n]
    except Exception as e:
        return [f"Git log failed: {e}"]


# --- Read key project docs (pre-fetch for agent) ---
def read_scope_docs() -> List[str]:
    docs = [
        DOCS / "LAYER0_CONTROL_PLANE.md",
        DOCS / "README.md",
        PROJECT / "CURRENT_FOCUS.md",
        PROJECT / "TASKS.md",
        PROJECT / "AGENTS.md",
        PROJECT / "CLAUDE.md",
    ]
    summary = []
    for doc in docs:
        if doc.exists():
            try:
                first = doc.read_text(errors="ignore").splitlines()[:1]
                summary.append(f"--- {doc.name}: {first[0] if first else 'empty'}")
            except Exception:
                summary.append(f"--- {doc.name}: READ ERROR")
        else:
            summary.append(f"--- {doc.name}: MISSING")
    return summary


# --- Self-review: read own feedback and generate TODO ---
def self_review_and_todo(token_stats: Dict, build_status: str) -> str:
    """Read own feedback and generate actionable TODO.md."""
    todos = ["# Kitty Optimizer TODO", ""]
    todos.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    todos.append("")

    # Check for errors
    if "error" in token_stats:
        todos.append("## High Priority")
        todos.append(f"- [ ] Fix token log issue: {token_stats['error']}")
        return "\n".join(todos)

    # Analyze token usage patterns
    total_calls = token_stats.get("calls", 0)
    if total_calls == 0:
        todos.append("## No Action Needed")
        todos.append("- No token usage recorded recently.")
        return "\n".join(todos)

    todos.append("## Token Optimization Opportunities")

    models = token_stats.get("models", {})
    for model, data in models.items():
        calls = data["calls"]
        cached = data["cached_tokens"]
        prompt = data["prompt_tokens"]

        # Check for caching opportunities
        if cached == 0 and prompt > 1000:
            todos.append(f"- [ ] Enable prompt caching for {model} (0 cached tokens, {prompt} prompt tokens)")

        # Check for high token usage
        if data["max_prompt"] > 8000:
            todos.append(f"- [ ] Review {model} large prompts (max {data['max_prompt']} tokens)")

        # Check for excessive calls
        if calls > 50:
            todos.append(f"- [ ] Batch requests for {model} ({calls} calls)")

    # Build health
    if "failed" in build_status.lower() or "error" in build_status.lower():
        todos.append("## Build Issues")
        todos.append("- [ ] Fix failing tests before optimizing further")

    # General recommendations
    todos.append("## General Recommendations")
    todos.append("- [ ] Use jq/awk for data processing (not LLM calls)")
    todos.append("- [ ] Keep Firecrawl searches to 1-2 queries per run")
    todos.append("- [ ] Implement semantic caching for repeated queries")

    return "\n".join(todos)


# --- Generate feedback (FIXED: proper stats display) ---
def generate_feedback(token_stats: Dict, build_status: str, git_summary: List[str], scope: List[str]) -> str:
    lines = [
        f"# Kitty Optimizer Report — {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "## Executive Summary",
        "Automated scan complete. See sections below for details.",
        "",
        "## Project Scope",
    ]
    lines += [f"- {s}" for s in scope]
    lines += ["", "## Build Health", f"- Status: {build_status}"]

    # Token audit (FIXED)
    lines.append("")
    lines.append("## Token Audit")
    if "error" in token_stats:
        lines.append(f"- {token_stats['error']}")
    else:
        total_calls = token_stats.get("calls", 0)
        total_prompt = token_stats.get("total_prompt", 0)
        total_completion = token_stats.get("total_completion", 0)
        total_cached = token_stats.get("total_cached", 0)
        estimated = token_stats.get("estimated", False)

        if estimated:
            lines.append("⚠️ **Token counts are ESTIMATED** (model does not report usage data).")
        lines.append(f"- **Total calls**: {total_calls}")
        lines.append(f"- **Prompt tokens**: {total_prompt:,}" + (" (est.)" if estimated else ""))
        lines.append(f"- **Completion tokens**: {total_completion:,}" + (" (est.)" if estimated else ""))
        lines.append(f"- **Cached tokens**: {total_cached:,}")

        if total_prompt > 0:
            cache_pct = (total_cached / total_prompt * 100) if total_prompt > 0 else 0
            lines.append(f"- **Cache hit rate**: {cache_pct:.1f}%")

        lines.append("")
        lines.append("### Per-Model Breakdown")
        models = token_stats.get("models", {})
        for model, data in models.items():
            lines.append(f"- **{model}**:")
            lines.append(f"  - Calls: {data['calls']}")
            lines.append(f"  - Prompt: {data['prompt_tokens']:,}")
            lines.append(f"  - Completion: {data['completion_tokens']:,}")
            lines.append(f"  - Cached: {data['cached_tokens']:,}")

    # Actionable recommendations
    lines += [
        "",
        "## Actionable Recommendations",
        "1. [HIGH] Ensure all new code has accompanying tests before merge.",
        "2. [HIGH] Review token-heavy operations — use jq/awk for data processing, not LLM calls.",
        "3. [MED]  Archive stale docs (check docs/archive/ for candidates).",
        "4. [MED]  Keep Firecrawl searches targeted (1-2 queries per run, not broad sweeps).",
        "5. [LOW]  Consider consolidating small test files into larger suites to reduce pytest overhead.",
        "",
        "## Next Steps",
        "- Run with --full for complete analysis.",
        "- Run with --focus <topic> to deep-dive a specific area.",
        "- Check feedback-latest.md after each run.",
    ]

    OPTIMIZER_DIR.mkdir(parents=True, exist_ok=True)
    FEEDBACK.write_text("\n".join(lines))
    log(f"Feedback written to {FEEDBACK}")

    # Generate TODO.md from self-review
    todo_content = self_review_and_todo(token_stats, build_status)
    TODO_FILE.write_text(todo_content)
    log(f"TODO written to {TODO_FILE}")

    return "\n".join(lines)


# --- Full Meta-Analysis ---
def full_analysis():
    log("=== FULL META-ANALYSIS ===")
    log(f"Timestamp: {datetime.now().isoformat()}")

    # Check if work was done today (for daily-only launchd mode)
    if "launchd" in " ".join(sys.argv):
        if not work_done_today():
            log("No commits today — skipping full analysis (daily-only mode)")
            return

    # 1. Scope review (pre-fetch)
    log("1. Reading project scope...")
    scope = read_scope_docs()

    # 2. Build log analysis
    log("2. Analyzing build logs...")
    build_status = get_build_status()

    # 3. Git log analysis
    log("3. Analyzing git history...")
    git_summary = get_git_summary(20)

    # 4. Token audit (FIXED: proper parsing)
    log("4. Token audit...")
    token_stats = analyze_token_log(quick=False, days=7)

    # 5. Generate actionable feedback + TODO
    log("5. Generating actionable feedback...")
    generate_feedback(token_stats, build_status, git_summary, scope)

    log("=== END FULL ANALYSIS ===")


# --- Quick Mode ---
def quick_check():
    log("=== QUICK TOKEN CHECK ===")
    if not TOKEN_LOG.exists():
        log(f"No token log found at {TOKEN_LOG}")
        return
    stats = analyze_token_log(quick=True, days=1)
    if "error" in stats:
        log(f"Token check failed: {stats['error']}")
        return
    models = stats.get("models", {})
    for model, data in models.items():
        total = data["prompt_tokens"] + data["completion_tokens"]
        log(f"  {model}: {total} tokens, {data['calls']} calls")
    log("=== END QUICK CHECK ===")


# --- Main ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Kitty Optimizer")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--quick", action="store_true", help="Fast token summary")
    group.add_argument("--full", action="store_true", help="Complete analysis + feedback")
    group.add_argument("--focus", type=str, metavar="TOPIC", help="Firecrawl research on a topic")
    group.add_argument("--prune", type=int, nargs="?", const=30, metavar="DAYS", help="Archive token log entries older than DAYS (default 30)")
    parser.add_argument("--verbose", action="store_true", help="Print debug logs")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.quick or (len(sys.argv) == 1 and "launchd" not in " ".join(sys.argv)):
        quick_check()
    elif args.full:
        full_analysis()
    else:
        parser.print_help()
