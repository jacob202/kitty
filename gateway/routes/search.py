"""Search endpoint for Kitty UI."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["search"])


@router.get("/search")
async def search(query: str = "", limit: int = 5):
    """Search across memory, knowledge, and journal."""
    from gateway.memory_graph import search_all

    if not query:
        return {"results": [], "query": ""}

    results = await search_all(query)

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
        "query": query,
        "results": all_items[:limit],
        "stores": list(results.results.keys()),
        "errors": results.errors,
    }
