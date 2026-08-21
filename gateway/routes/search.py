"""Search endpoint for Kitty UI.

The normalized search semantics live in ``gateway.search``.  This route keeps
the current flat HTTP response for compatibility while adapting that one
canonical grouped result into transport rows.
"""

from __future__ import annotations

from fastapi import APIRouter

from gateway import search as unified_search

router = APIRouter(tags=["search"])

_SECTION_TO_STORE = {
    "memories": "memory",
    "knowledge": "knowledge",
    "journal": "journal",
    "todos": "todos",
    "inbox": "inbox",
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

    rows = []
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
