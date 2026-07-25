"""Search endpoint for Kitty UI."""

from __future__ import annotations

from fastapi import APIRouter

from gateway import memory_graph

from pydantic import BaseModel, Field
from typing import Any


class SearchResultItem(BaseModel):
    id: str
    title: str
    category: str
    score: float
    snippet: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResultItem]
    count: int


router = APIRouter(tags=["search"])


@router.get("/search", response_model=SearchResponse)
async def search(q: str = "", limit: int = 5):
    """Search across memory, knowledge, and journal."""
    if not q:
        return {"query": "", "memories": [], "knowledge": [], "journal": [], "todos": [], "inbox": []}

    # Resolved on the module, not imported by name, so the storage layer stays
    # patchable and reads keep going through memory_graph (see CLAUDE.md).
    results = await memory_graph.search_all(q)

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
