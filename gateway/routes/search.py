"""Search endpoint for Kitty UI."""

from __future__ import annotations

from fastapi import APIRouter

import gateway.search

router = APIRouter(tags=["search"])


@router.get("/search")
async def search(query: str = "", limit: int = 5):
    """Search across memory, knowledge, and journal."""
    if not query:
        return {"query": "", "memories": [], "knowledge": [], "journal": [], "todos": [], "inbox": []}

    return await gateway.search.async_search(query, limit=limit)
