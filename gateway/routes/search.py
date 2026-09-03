"""Search endpoint for Kitty UI.

The normalized search semantics live in ``gateway.search``.  This route keeps
the current flat HTTP response for compatibility while adapting that one
canonical grouped result into transport rows.
"""

from __future__ import annotations

from fastapi import APIRouter

from gateway import chat_search
from gateway import search as unified_search

router = APIRouter(tags=["search"])

_SECTION_TO_STORE = {
    "projects": "projects",
    "memories": "memory",
    "knowledge": "knowledge",
    "journal": "journal",
    "traces": "traces",
    "todos": "todos",
    "inbox": "inbox",
    "signals": "signals",
    "chats": "chats",
}


@router.get("/search")
async def search(q: str = "", limit: int = 5):
    """Search across Kitty stores through the canonical search normalizer."""
    if not q:
        return {"query": "", "results": [], "stores": [], "errors": [], "degraded_stores": []}

    grouped = await unified_search.async_search(q, limit=limit)
    rows_by_store = []
    for section, store in _SECTION_TO_STORE.items():
        store_rows = []
        for hit in grouped.get(section, []):
            store_rows.append({
                "store": store,
                "kind": hit.get("kind"),
                "source": hit.get("source"),
                "title": hit.get("title"),
                "content": hit.get("text", ""),
                "score": hit.get("score") or 0,
                "metadata": hit.get("metadata", {}),
            })
        if store_rows:
            rows_by_store.append(store_rows)

    rows: list[dict[str, object]] = []
    depth = 0
    while len(rows) < limit and any(depth < len(store_rows) for store_rows in rows_by_store):
        for store_rows in rows_by_store:
            if depth < len(store_rows):
                rows.append(store_rows[depth])
                if len(rows) == limit:
                    break
        depth += 1
    return {
        "query": q,
        "results": rows[:limit],
        "stores": grouped.get("stores", []),
        "errors": grouped.get("errors", []),
        "degraded_stores": grouped.get("degraded_stores", []),
    }


@router.post("/chat/search")
async def chat_search_endpoint(body: dict):
    """Search across all chat messages using FTS5 keyword search.

    Request body:
        q (str): The search query (FTS5 syntax supported).
        limit (int): Max results (default 10).

    Returns:
        Matching messages with chat context (chat title, snippet, role,
        timestamp) ranked by relevance.
    """
    q = (body.get("q") or "").strip()
    limit = min(int(body.get("limit", 10)), 100)

    if not q:
        return {"query": "", "results": []}

    results = chat_search.search_chat_messages(q, limit=limit)
    return {
        "query": q,
        "results": results,
    }
