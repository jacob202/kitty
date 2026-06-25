"""Memory consolidation — periodic compression of traces into durable long-term memory.

Called by:
  - cron action  "memory.consolidate"  (registered at gateway startup)
  - dream task via task_runner._run_dream()
  - POST /session/end  (per-session lightweight consolidation)

Main entry point: nightly_dream()
"""
from __future__ import annotations

import json
import logging
import time
from collections import defaultdict
from typing import Optional

from gateway.paths import DATA_DIR, LOG_FILE

logger = logging.getLogger("kitty.memory_consolidation")

CONSOL_CACHE = DATA_DIR / "last_consolidation.json"
PRUNE_KEEP_DAYS = 30
MIN_TRACES_FOR_SUMMARY = 3


# ── public API ────────────────────────────────────────────────────────────────

def nightly_dream() -> str:
    """Full consolidation pass: summarize recent clusters, prune log, update mirror."""
    results: list[str] = []

    try:
        n = consolidate_recent(days=3)
        results.append(f"Consolidated {n} trace cluster(s) into long-term memory")
    except Exception as e:
        logger.error("consolidate_recent failed: %s", e)
        results.append(f"Consolidation error: {e}")

    try:
        pruned = prune_trace_log(keep_days=PRUNE_KEEP_DAYS)
        results.append(f"Pruned {pruned} old trace entries (kept last {PRUNE_KEEP_DAYS}d)")
    except Exception as e:
        results.append(f"Prune error: {e}")

    try:
        from gateway.honcho import get_weekly_mirror
        mirror = get_weekly_mirror(use_cache=False)
        summary = mirror.get("summary", "")[:120]
        results.append(f"Weekly mirror refreshed: {summary}")
    except Exception as e:
        results.append(f"Mirror error: {e}")

    _save_timestamp()
    return "\n".join(results)


def consolidate_recent(days: int = 3) -> int:
    """
    Read traces from the last N days, group by domain, call LLM to summarize
    each cluster, store result as a memory fact. Returns cluster count processed.
    """
    from gateway.honcho import get_recent_traces
    traces = get_recent_traces(days=days)
    if not traces:
        return 0

    last_ts = _load_last_consolidation_ts()
    new_traces = [t for t in traces if t.get("timestamp", 0) > last_ts]
    if len(new_traces) < MIN_TRACES_FOR_SUMMARY:
        return 0

    clusters = _cluster_by_domain(new_traces)
    count = 0
    for domain, cluster_traces in clusters.items():
        if len(cluster_traces) < MIN_TRACES_FOR_SUMMARY:
            continue
        summary = _summarize_cluster(domain, cluster_traces)
        if summary:
            _store_memory(domain, summary, cluster_traces)
            count += 1

    return count


def prune_trace_log(keep_days: int = PRUNE_KEEP_DAYS) -> int:
    """Remove lines older than keep_days from the trace log. Returns pruned count."""
    if not LOG_FILE.exists():
        return 0
    cutoff = time.time() - keep_days * 86400
    kept: list[str] = []
    pruned = 0
    with LOG_FILE.open("r", errors="ignore") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                if entry.get("timestamp", 0) >= cutoff:
                    kept.append(line)
                else:
                    pruned += 1
            except json.JSONDecodeError:
                kept.append(line)
    if pruned:
        LOG_FILE.write_text("".join(kept))
    return pruned


def get_last_run_info() -> dict:
    """Return metadata about the last consolidation run."""
    if not CONSOL_CACHE.exists():
        return {"last_run": None, "never": True}
    try:
        return json.loads(CONSOL_CACHE.read_text())
    except Exception:
        return {"last_run": None, "error": True}


# ── internals ─────────────────────────────────────────────────────────────────

def _cluster_by_domain(traces: list[dict]) -> dict[str, list[dict]]:
    clusters: dict[str, list[dict]] = defaultdict(list)
    for t in traces:
        domain = t.get("domain_classified", "general") or "general"
        clusters[domain].append(t)
    return dict(clusters)


def _summarize_cluster(domain: str, traces: list[dict]) -> Optional[str]:
    """Use LLM to summarize a cluster of traces into a durable fact sentence."""
    try:
        from gateway.llm_client import call_llm
    except ImportError:
        return None

    snippets = "\n".join(
        f"- {t.get('user_request', '')[:100]}" for t in traces[-15:]
    )
    messages = [
        {
            "role": "system",
            "content": (
                "You are summarizing recent interactions for a personal AI companion. "
                "Write ONE concise sentence (under 80 words) capturing what Jacob has "
                "been focused on in the '{domain}' domain. Start with 'Jacob has been...'"
            ).replace("{domain}", domain),
        },
        {
            "role": "user",
            "content": f"Recent {domain} interactions:\n{snippets}",
        },
    ]
    try:
        result = call_llm(messages=messages, model="kitty-default")
        return result.strip() if result else None
    except Exception as e:
        logger.warning("Cluster summarization failed for %s: %s", domain, e)
        return None


def _store_memory(domain: str, summary: str, traces: list[dict]) -> None:
    """Write summary into long-term memory store."""
    try:
        from gateway.memory import add_memory
        ts_str = time.strftime("%Y-%m-%d")
        text = f"[{ts_str} consolidation/{domain}] {summary}"
        add_memory(text, namespace="consolidations", metadata={"domain": domain, "trace_count": len(traces)})
    except Exception as e:
        logger.warning("Failed to store memory for %s: %s", domain, e)


def _load_last_consolidation_ts() -> float:
    info = get_last_run_info()
    return info.get("timestamp", 0) or 0


def _save_timestamp() -> None:
    CONSOL_CACHE.parent.mkdir(parents=True, exist_ok=True)
    CONSOL_CACHE.write_text(json.dumps({
        "last_run": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "timestamp": time.time(),
    }))
