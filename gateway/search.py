"""Unified Search — query across all Kitty stores.

Public API:
  search(query) -> dict    Search memory, knowledge, journal, todos, and traces
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from gateway.paths import DATA_DIR, LOGS_DIR

logger = logging.getLogger("kitty.search")


def search(query: str, limit: int = 5) -> dict:
    """Unified search across all stores. Returns results grouped by source."""
    results: dict[str, list] = {
        "memories": [],
        "knowledge": [],
        "journal": [],
        "todos": [],
        "query": query,
    }

    # Memory
    try:
        from gateway.memory import search_memory
        results["memories"] = search_memory(query, limit=limit)
    except Exception:
        pass

    # Knowledge
    try:
        import asyncio
        from gateway.knowledge import search as kn_search
        results["knowledge"] = asyncio.run(kn_search(query, limit=limit))
    except RuntimeError:
        pass  # event loop conflict
    except Exception:
        pass

    # Journal
    try:
        from gateway.journal import JOURNAL_LOG
        if JOURNAL_LOG.exists():
            terms = query.lower().split()
            matches = []
            with JOURNAL_LOG.open("r") as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        text = entry.get("entry", "").lower()
                        score = sum(1 for t in terms if t in text)
                        if score > 0:
                            matches.append({"entry": entry.get("entry", "")[:300], "score": score, "ts": entry.get("ts")})
                    except json.JSONDecodeError:
                        continue
            matches.sort(key=lambda x: x["score"], reverse=True)
            results["journal"] = matches[:limit]
    except Exception:
        pass

    # Todos
    try:
        from gateway.todo_store import get
        todos = get()
        terms = query.lower().split()
        matches = [t for t in todos if any(term in t.get("content", "").lower() for term in terms)]
        results["todos"] = matches[:limit]
    except Exception:
        pass

    return results
