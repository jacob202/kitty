"""
Memory layer for Kitty.

Two-tier system:
  1. User profile — structured facts, always injected (JSON in memory store)
  2. Episodic memory — semantic search over past conversations (vector store)

Uses mem0 when API key is set, falls back to in-process dict for local dev.
"""

import json
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from mem0 import MemoryClient
    MEM0_AVAILABLE = True
except ImportError:
    MEM0_AVAILABLE = False

from .config import settings

_LOCAL_STORE: dict[str, list[dict]] = {}
_PROFILE_PATH = Path(__file__).parent.parent / "config" / "user_profile.json"
_PROFILE_LOCK = threading.Lock()


def _load_profile() -> dict:
    """Load user profile JSON; returns empty dict on missing file or parse error."""
    if not _PROFILE_PATH.exists():
        return {}
    try:
        return json.loads(_PROFILE_PATH.read_text())
    except json.JSONDecodeError:
        return {}


def _save_profile(profile: dict) -> None:
    """Persist the user profile JSON to disk."""
    _PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _PROFILE_PATH.write_text(json.dumps(profile, indent=2))


def get_user_profile() -> dict:
    """Return the current structured user profile."""
    return _load_profile()


def update_user_profile(updates: dict) -> None:
    """Merge *updates* into the stored user profile and persist it (thread-safe)."""
    with _PROFILE_LOCK:
        profile = _load_profile()
        profile.update(updates)
        profile["last_updated"] = datetime.utcnow().isoformat()
        _save_profile(profile)


def format_profile_injection(profile: dict) -> str:
    """Format the user profile as a markdown block for system-prompt injection."""
    if not profile:
        return ""
    lines = ["## What Kitty knows about you"]
    for key, value in profile.items():
        if key == "last_updated":
            continue
        lines.append(f"- **{key.replace('_', ' ').title()}**: {value}")
    return "\n".join(lines)


def search_memories(query: str, limit: int = 5) -> list[dict]:
    """Retrieve relevant past memories for the current query."""
    user_id = settings.user_id

    if MEM0_AVAILABLE and settings.mem0_api_key:
        try:
            client = MemoryClient(api_key=settings.mem0_api_key)
            results = client.search(query, user_id=user_id, limit=limit)
            return results.get("results", [])
        except Exception:
            logger.warning("mem0 search failed, falling back to local store", exc_info=True)

    # Local fallback — simple recency-based retrieval (no semantic search)
    memories = _LOCAL_STORE.get(user_id, [])
    return memories[-limit:]


def add_memory(conversation: list[dict], metadata: Optional[dict] = None) -> None:
    """Store a conversation turn for future retrieval."""
    user_id = settings.user_id

    if MEM0_AVAILABLE and settings.mem0_api_key:
        try:
            client = MemoryClient(api_key=settings.mem0_api_key)
            client.add(conversation, user_id=user_id, metadata=metadata or {})
            return
        except Exception:
            logger.warning("mem0 add failed, falling back to local store", exc_info=True)

    # Local fallback
    if user_id not in _LOCAL_STORE:
        _LOCAL_STORE[user_id] = []
    _LOCAL_STORE[user_id].append({
        "conversation": conversation,
        "metadata": metadata or {},
        "timestamp": datetime.utcnow().isoformat(),
    })


def format_memory_injection(memories: list[dict]) -> str:
    """Format retrieved memories as a markdown block for system-prompt injection."""
    if not memories:
        return ""
    lines = ["## Relevant memories from past conversations"]
    for m in memories:
        memory_text = m.get("memory", m.get("text", str(m)))
        lines.append(f"- {memory_text}")
    return "\n".join(lines)
