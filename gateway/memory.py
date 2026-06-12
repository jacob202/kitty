"""Mem0 memory wrapper for Kitty Gateway."""
from __future__ import annotations
import os
import logging
import threading
from typing import Optional

logger = logging.getLogger("kitty.memory")

from gateway.paths import DATA_DIR
MEM0_DATA_DIR = DATA_DIR / "mem0"
USER_ID = "jacob"

# Soft-import mem0 once at module load. If missing (or init fails — e.g. the
# embedder host is down), we cache that fact and turn every public function
# into a quiet no-op instead of warning on every call.
try:
    from mem0 import Memory as _Mem0Memory

    _MEM0_IMPORT_OK = True
except ImportError:
    _Mem0Memory = None  # type: ignore[assignment]
    _MEM0_IMPORT_OK = False
    logger.info(
        "mem0ai not installed — memory features disabled. "
        "Run `pip install -r requirements.txt` to enable."
    )

_MEMORY_INSTANCE = None
_MEMORY_INIT_FAILED = False
_MEMORY_INIT_LOCK = threading.Lock()


def _build_mem0_config() -> dict:
    """Build Mem0 config at runtime using the routing system."""
    from gateway.llm_client import route_model
    model = os.environ.get("KITTY_MEMORY_MODEL") or route_model("memory context building")
    return {
        "llm": {
            "provider": "litellm",
            "config": {
                "model": model,
                "api_key": os.environ.get("OPENROUTER_API_KEY", ""),
            },
        },
        "embedder": {
            "provider": "ollama",
            "config": {
                "model": "nomic-embed-text",
                "ollama_base_url": "http://localhost:11434",
            },
        },
        "vector_store": {
            "provider": "chroma",
            "config": {
                "collection_name": "kitty_memory",
                "path": str(MEM0_DATA_DIR),
            },
        },
    }


def _get_memory():
    """Lazy-init Mem0. Caches both success and failure so we don't retry-and-warn forever."""
    global _MEMORY_INSTANCE, _MEMORY_INIT_FAILED
    if not _MEM0_IMPORT_OK or _MEMORY_INIT_FAILED:
        return None
    if _MEMORY_INSTANCE is not None:
        return _MEMORY_INSTANCE
    with _MEMORY_INIT_LOCK:
        if _MEMORY_INSTANCE is not None:
            return _MEMORY_INSTANCE
        if _MEMORY_INIT_FAILED:
            return None
        try:
            MEM0_DATA_DIR.mkdir(parents=True, exist_ok=True)
            config = _build_mem0_config()
            _MEMORY_INSTANCE = _Mem0Memory.from_config(config)
            return _MEMORY_INSTANCE
        except Exception as e:
            _MEMORY_INIT_FAILED = True
            logger.warning(
                "mem0 init failed (memory features disabled until restart): %s", e
            )
            return None


def add_memory(text: str, namespace: str = "facts", metadata: Optional[dict] = None) -> None:
    """Store a memory for Jacob. namespace: facts | patterns"""
    try:
        mem = _get_memory()
        if mem is None:
            return
        meta = {"namespace": namespace, **(metadata or {})}
        mem.add(text, user_id=USER_ID, metadata=meta)
        logger.info("Memory stored [%s]: %s", namespace, text[:80])
    except Exception as e:
        logger.warning("Memory add failed (non-fatal): %s", e)


def search_memory(query: str, limit: int = 5, namespace: Optional[str] = None) -> list[dict]:
    """Search memories relevant to query. Returns list of {memory, score} dicts."""
    try:
        mem = _get_memory()
        if mem is None:
            return []
        results = mem.search(query, filters={"user_id": USER_ID}, limit=limit)
        memories = results.get("results", []) if isinstance(results, dict) else results
        if namespace:
            memories = [m for m in memories if m.get("metadata", {}).get("namespace") == namespace]
        return memories
    except Exception as e:
        logger.warning("Memory search failed (non-fatal): %s", e)
        return []


def get_context_block(query: str, limit: int = 5) -> str:
    """Return a formatted context block to inject into the system prompt."""
    memories = search_memory(query, limit=limit)
    if not memories:
        return ""
    lines = ["## What Kitty knows about Jacob (from memory):"]
    for m in memories:
        text = m.get("memory", m.get("text", ""))
        if text:
            lines.append(f"- {text}")
    return "\n".join(lines)



def list_memories(namespace: Optional[str] = None, limit: int = 50) -> list[dict]:
    """List all stored memories. Optionally filter by namespace."""
    try:
        mem = _get_memory()
        if mem is None:
            return []
        results = mem.get(user_id=USER_ID)
        memories = results.get("results", []) if isinstance(results, dict) else results
        if namespace:
            memories = [m for m in memories if m.get("metadata", {}).get("namespace") == namespace]
        return memories[:limit]
    except Exception as e:
        logger.warning("Memory list failed (non-fatal): %s", e)
        return []


def delete_memory(memory_id: str) -> bool:
    """Delete a specific memory by ID."""
    try:
        mem = _get_memory()
        if mem is None:
            return False
        mem.delete(memory_id=memory_id)
        logger.info("Memory deleted: %s", memory_id)
        return True
    except Exception as e:
        logger.warning("Memory delete failed (non-fatal): %s", e)
        return False


def consolidate_session(session_id: str, messages: list[dict]) -> bool:
    """Best-effort close-session hook until richer consolidation lands."""
    try:
        logger.info(
            "Session close requested: %s (%d messages)",
            session_id or "<anonymous>",
            len(messages),
        )
        return True
    except Exception as e:
        logger.warning("Session consolidation failed (non-fatal): %s", e)
        return False
