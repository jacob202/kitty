"""Mem0 memory wrapper for Kitty Gateway."""
from __future__ import annotations

import logging
import os
from typing import Optional


class MemoryError(RuntimeError):
    """Raised when a memory read/write operation fails unexpectedly."""

from gateway.paths import DATA_DIR

logger = logging.getLogger("kitty.memory")

MEM0_DATA_DIR = DATA_DIR / "mem0"
USER_ID = "jacob"

# Soft-import mem0 once at module load. If missing (or init fails — e.g. the
# embedder host is down), we cache that fact and turn every public function
# into a quiet no-op instead of warning on every call.
try:
    from mem0 import Memory as _Mem0Memory

    _MEM0_IMPORT_OK = True
except ImportError:
    _Mem0Memory = None
    _MEM0_IMPORT_OK = False
    logger.info(
        "mem0ai not installed — memory features disabled. "
        "Run `pip install -r requirements.txt` to enable."
    )

_MEMORY_INSTANCE = None
_MEMORY_INIT_FAILED = False


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
    """
    Persist a memory entry for the module user.

    Attempts to store `text` in the memory backend under the given `namespace`. This is a best-effort operation: initialization or storage errors are logged as non-fatal warnings and the function returns without raising.

    Parameters:
        text (str): The memory content to store.
        namespace (str): Logical namespace for the memory (default: "facts").
        metadata (Optional[dict]): Additional metadata to attach; merged into the stored metadata with the key `"namespace"` set to the provided `namespace`.
    """
    try:
        mem = _get_memory()
    except Exception as e:
        logger.warning("Memory add failed (non-fatal): %s", e)
        return
    if mem is None:
        return
    try:
        meta = {"namespace": namespace, **(metadata or {})}
        mem.add(text, user_id=USER_ID, metadata=meta)
        logger.info("Memory stored [%s]: %s", namespace, text[:80])
    except Exception as e:
        logger.warning("Memory add failed (non-fatal): %s", e)


def search_memory(query: str, limit: int = 5, namespace: Optional[str] = None) -> list[dict]:
    """Search memories relevant to query. Returns list of {memory, score} dicts.

    Raises MemoryError on unexpected backend failures. Returns [] when mem0
    is not configured (not an error — just unavailable).
    """
    mem = _get_memory()
    if mem is None:
        return []
    try:
        results = mem.search(query, filters={"user_id": USER_ID}, limit=limit)
        memories = results.get("results", []) if isinstance(results, dict) else results
        if namespace:
            memories = [m for m in memories if m.get("metadata", {}).get("namespace") == namespace]
        return memories
    except Exception as exc:
        raise MemoryError(f"memory search failed: {exc}") from exc


def get_context_block(query: str, limit: int = 5) -> str:
    """Return a formatted context block to inject into the system prompt.

    Catches MemoryError so a backend failure never breaks chat — returns ""
    and logs a warning instead of raising.
    """
    try:
        memories = search_memory(query, limit=limit)
    except MemoryError as exc:
        logger.warning("Memory search unavailable (prompt will proceed without context): %s", exc)
        return ""
    if not memories:
        return ""
    lines = ["## What Kitty knows about Jacob (from memory):"]
    for m in memories:
        text = m.get("memory", m.get("text", ""))
        if text:
            lines.append(f"- {text}")
    return "\n".join(lines)



def list_memories(namespace: Optional[str] = None, limit: int = 50) -> list[dict]:
    """List all stored memories. Optionally filter by namespace.

    Raises MemoryError on unexpected backend failures.
    """
    mem = _get_memory()
    if mem is None:
        return []
    try:
        results = mem.get(user_id=USER_ID)
        memories = results.get("results", []) if isinstance(results, dict) else results
        if namespace:
            memories = [m for m in memories if m.get("metadata", {}).get("namespace") == namespace]
        return memories[:limit]
    except Exception as exc:
        raise MemoryError(f"memory list failed: {exc}") from exc


def delete_memory(memory_id: str) -> bool:
    """Delete a specific memory by ID.

    Raises MemoryError on unexpected backend failures.
    """
    mem = _get_memory()
    if mem is None:
        return False
    try:
        mem.delete(memory_id=memory_id)
        logger.info("Memory deleted: %s", memory_id)
        return True
    except Exception as exc:
        raise MemoryError(f"memory delete failed for {memory_id!r}: {exc}") from exc


def consolidate_session(session_id: str, messages: list[dict]) -> bool:
    """Extract key facts from a closed session and persist to long-term memory.

    Reads user messages from the session, creates a summary, and stores
    it via add_memory(). Returns True if facts were stored, False on
    backend failure or empty session.
    """
    if not messages:
        logger.info("Session %s closed with no messages — nothing to consolidate", session_id or "<anonymous>")
        return False

    user_msgs = [m.get("content", "") for m in messages if m.get("role") == "user" and m.get("content")]
    if not user_msgs:
        logger.info("Session %s closed with no user messages — nothing to consolidate", session_id or "<anonymous>")
        return False

    # Build a concise session summary from user messages
    joined = "\n".join(f"- {msg[:120]}" for msg in user_msgs[-20:])
    session_summary = (
        f"[session {session_id or 'anonymous'}] "
        f"Key topics discussed:\n{joined}"
    )

    try:
        add_memory(
            session_summary,
            namespace="sessions",
            metadata={
                "session_id": session_id or "anonymous",
                "message_count": len(messages),
                "user_message_count": len(user_msgs),
            },
        )
        logger.info(
            "Session %s consolidated: %d user messages stored",
            session_id or "<anonymous>",
            len(user_msgs),
        )
        return True
    except Exception as e:
        logger.warning("Session consolidation failed for %s: %s", session_id, e)
        return False
