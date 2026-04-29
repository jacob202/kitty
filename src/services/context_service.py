"""Context service — bridges specialists to KB, memory, and dev monitor data."""

import logging
from typing import Any
from src.memory.kitty_memory_enhanced import KittyMemoryEnhanced

logger = logging.getLogger(__name__)

_memory_instance = None
_lightrag_stores: dict[str, Any] = {}
_kb_cache: dict[str, str] = {}
_KB_CACHE_MAX_SIZE = 500
_AI_DEV_SUMMARY_CACHE: str = ""


def _get_memory():
    global _memory_instance
    if _memory_instance is None:
        _memory_instance = KittyMemoryEnhanced()
    return _memory_instance

def _get_lightrag_for_domain(domain: str):
    global _lightrag_stores
    if domain not in _lightrag_stores:
        try:
            from src.memory.lightrag_store import LightRAGStore
            _lightrag_stores[domain] = LightRAGStore(domain=domain)
        except Exception as e:
            logger.warning("LightRAG unavailable for domain %s: %s", domain, e)
            _lightrag_stores[domain] = None
    return _lightrag_stores[domain]

def query_knowledge_base(question: str, domain: str) -> str:
    """Query LightRAG or ChromaDB for domain-relevant context."""
    cache_key = f"{domain}:{question[:100]}"
    if cache_key in _kb_cache:
        return _kb_cache[cache_key]

    store = _get_lightrag_for_domain(domain)
    try:
        if store:
            result = store.search(question)
            if result and not _is_empty_lightrag_result(result):
                _kb_cache[cache_key] = result[:3000]
                if len(_kb_cache) > _KB_CACHE_MAX_SIZE:
                    oldest_key = next(iter(_kb_cache))
                    del _kb_cache[oldest_key]
                return _kb_cache[cache_key]
    except Exception as e:
        logger.debug(f"LightRAG unavailable for domain {domain}: {e}")

    try:
        mem = _get_memory()
        context = mem.retrieve_context(question, n_conversations=0, n_facts=0, n_documents=5, domain=domain)
        docs = context.get("documents", [])
        if docs:
            content = "\n---\n".join(docs)[:3000]
            _kb_cache[cache_key] = content
            if len(_kb_cache) > _KB_CACHE_MAX_SIZE:
                oldest_key = next(iter(_kb_cache))
                del _kb_cache[oldest_key]
            return content
    except Exception as e:
        logger.debug(f"ChromaDB unavailable: {e}")

    return ""

def _is_empty_lightrag_result(result: str) -> bool:
    """Return True when LightRAG has no usable context and Chroma should be tried."""
    result_lower = result.lower()
    return any(
        marker in result_lower
        for marker in (
            "not found",
            "no-context",
            "no relevant document chunks",
            "lightrag search error",
        )
    )

def query_ai_dev_context(question: str, tag: str | None = None) -> str:
    """Query the AI development monitor for context relevant to a specialist's question.

    Args:
        question: The specialist's query or context
        tag: Optional filter ("standout", "relevant", "general")

    Returns:
        Formatted string of relevant AI dev items or empty string.
    """
    try:
        from src.services.ai_dev_monitor import get_monitor
        monitor = get_monitor()
        items = monitor.get_items(tag=tag, limit=10)

        if not items:
            return ""

        lines = ["## Recent AI Developments\n"]
        for item in items:
            lines.append(f"- [{item.tag}] {item.title}")
            lines.append(f"  {item.reason}")
            lines.append(f"  {item.url}\n")

        result = "\n".join(lines)
        global _AI_DEV_SUMMARY_CACHE
        _AI_DEV_SUMMARY_CACHE = result
        return result[:3000]
    except Exception as e:
        logger.debug(f"AI dev context unavailable: {e}")
        return ""

def get_ai_dev_summary_cache() -> str:
    """Return cached AI dev summary for fast access."""
    global _AI_DEV_SUMMARY_CACHE
    if not _AI_DEV_SUMMARY_CACHE:
        return query_ai_dev_context("latest AI developments")
    return _AI_DEV_SUMMARY_CACHE
