"""Unified cache for memory operations to eliminate duplication."""

from __future__ import annotations

# Knowledge Base Cache
_KB_CACHE: dict[str, str] = {}
_KB_CACHE_MAX = 500

# AI Development Summary Cache (single value)
_AI_DEV_CACHE: str = ""


def kb_cache_get(key: str) -> str | None:
    """Get a value from the KB cache."""
    return _KB_CACHE.get(key)


def kb_cache_set(key: str, value: str) -> None:
    """Set a value in the KB cache, evicting oldest if over limit."""
    _KB_CACHE[key] = value
    if len(_KB_CACHE) > _KB_CACHE_MAX:
        # Remove the first inserted item (FIFO)
        _KB_CACHE.pop(next(iter(_KB_CACHE)))


def ai_dev_cache_get() -> str:
    """Get the cached AI development summary."""
    return _AI_DEV_CACHE


def ai_dev_cache_set(value: str) -> None:
    """Set the AI development summary cache."""
    global _AI_DEV_CACHE
    _AI_DEV_CACHE = value


def clear_caches() -> None:
    """Clear all caches (useful for testing)."""
    _KB_CACHE.clear()
    global _AI_DEV_CACHE
    _AI_DEV_CACHE = ""