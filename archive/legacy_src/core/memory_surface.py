"""Surface relevant MCP memory entities into LLM context.

Reads the @modelcontextprotocol/server-memory JSON store and returns
a formatted string of entities relevant to the current query.
Returns empty string (no-op) when the store is absent or no matches found.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

_DEFAULT_STORE = Path.home() / ".config" / "claude-memory" / "memory.json"
_STORE_PATH = Path(os.getenv("MCP_MEMORY_STORE", str(_DEFAULT_STORE)))


def _load_entities() -> list[dict]:
    """Load entities from server-memory JSON store. Returns [] if unavailable."""
    try:
        if not _STORE_PATH.exists():
            return []
        data = json.loads(_STORE_PATH.read_text())
        # server-memory format: {"entities": [...], "relations": [...]}
        # Each entity: {"name": str, "entityType": str, "observations": [str]}
        return data.get("entities", [])
    except Exception:
        return []


def surface_memory(query: str, top_k: int = 5) -> str:
    """Return formatted memory entities relevant to `query`.

    Scores entities by word overlap with the query, boosting exact name matches.
    Returns empty string when no relevant entities are found.
    """
    if not query or not query.strip():
        return ""

    query_lower = query.lower()
    query_words = set(query_lower.split())

    scored: list[tuple[float, dict]] = []
    for entity in _load_entities():
        name = (entity.get("name") or "").lower()
        entity_type = (entity.get("entityType") or "").lower()
        observations = " ".join(entity.get("observations") or []).lower()

        full_text = f"{name} {entity_type} {observations}"
        full_words = set(full_text.split())

        overlap = len(query_words & full_words)
        if name and any(word in query_lower for word in name.split()):
            overlap += 3  # boost exact name matches

        if overlap > 0:
            scored.append((overlap, entity))

    if not scored:
        return ""

    scored.sort(key=lambda x: x[0], reverse=True)

    lines = ["[Memory]"]
    for _, entity in scored[:top_k]:
        name = entity.get("name", "")
        obs = entity.get("observations") or []
        if obs:
            lines.append(f"- {name}: {'; '.join(obs[:2])}")
        else:
            lines.append(f"- {name} ({entity.get('entityType', '')})")

    return "\n".join(lines)
