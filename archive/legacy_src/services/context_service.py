"""Context service — bridges specialists to KB, memory, and dev monitor data."""

import logging
from typing import Any
from src.memory.orchestrator import get_memory
from src.memory.unified_cache import kb_cache_get, kb_cache_set, ai_dev_cache_get, ai_dev_cache_set

logger = logging.getLogger(__name__)

# Compatibility shims for legacy tests/callers that still touch module globals.
_KB_CACHE: dict[str, str] = {}
_KB_CACHE_MAX = 500
_AI_DEV_SUMMARY_CACHE = ""


def _get_memory():
    return get_memory()


def query_knowledge_base(question: str, domain: str | None) -> str:
    """Query LightRAG or ChromaDB for domain-relevant context."""
    cache_key = f"{domain}:{question[:100]}"
    cached = _KB_CACHE.get(cache_key)
    if cached is not None:
        return cached

    cached = kb_cache_get(cache_key)
    if cached is not None:
        _KB_CACHE[cache_key] = cached
        return cached

    orchestrator = get_memory()
    content = orchestrator.query_knowledge(question, domain)

    if content:
        _KB_CACHE[cache_key] = content
        if len(_KB_CACHE) > _KB_CACHE_MAX:
            _KB_CACHE.pop(next(iter(_KB_CACHE)))
        kb_cache_set(cache_key, content)
    return content


def query_ai_dev_context(question: str, tag: str | None = None) -> str:
    """Query the AI development monitor for context."""
    global _AI_DEV_SUMMARY_CACHE
    # Check cache first
    cached = ai_dev_cache_get()
    if cached:
        _AI_DEV_SUMMARY_CACHE = cached
        return cached
        
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
        ai_dev_cache_set(result)
        _AI_DEV_SUMMARY_CACHE = result
        return result[:3000]
    except Exception as e:
        logger.debug(f"AI dev context unavailable: {e}")
        return ""


def get_ai_dev_summary_cache() -> str:
    global _AI_DEV_SUMMARY_CACHE
    if not _AI_DEV_SUMMARY_CACHE:
        return query_ai_dev_context("latest AI developments")
    return _AI_DEV_SUMMARY_CACHE


def query_domain_news(domain: str, limit: int = 3) -> str:
    try:
        from src.services.domain_news_monitor import get_domain_news_monitor
        monitor = get_domain_news_monitor()
        items = monitor.get_news(domain, limit=limit)
        if not items:
            return ""
        lines = [f"## Recent {domain.capitalize()} News\n"]
        for item in items:
            lines.append(f"- {item.title}")
            lines.append(f"  {item.url}\n")
        return "\n".join(lines)[:2000]
    except Exception as e:
        logger.debug(f"Domain news context unavailable for {domain}: {e}")
        return ""
