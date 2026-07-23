"""Search endpoint for Kitty UI."""

from __future__ import annotations

from fastapi import APIRouter

import gateway.search

router = APIRouter(tags=["search"])


@router.get("/search")
async def search(q: str = "", limit: int = 5):
    """Search across memory, knowledge, and journal."""
    if not q:
        return {"query": "", "memories": [], "knowledge": [], "journal": [], "todos": [], "inbox": []}

    if not q:
        return {"results": [], "query": ""}

    results = await search_all(q)

    all_items = []
    for store_name, items in results.results.items():
        for item in items[:limit]:
            all_items.append({
                "store": store_name,
                "content": item.text,
                "score": item.score or 0,
            })

    all_items.sort(key=lambda x: x["score"], reverse=True)

    return {
        "query": q,
        "results": all_items[:limit],
        "stores": list(results.results.keys()),
        "errors": results.errors,
    }
