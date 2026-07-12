"""Search endpoint for Kitty UI."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["search"])


@router.get("/search")
async def search(query: str = "", limit: int = 5):
    """Search across memory, knowledge, and journal."""
    from gateway.search import async_search

    if not query:
        return {"query": "", "memories": [], "knowledge": [], "journal": [], "todos": [], "inbox": []}

    return await async_search(query, limit=limit)
