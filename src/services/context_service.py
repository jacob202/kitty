import logging
from typing import Any
from src.memory.kitty_memory_enhanced import KittyMemoryEnhanced

logger = logging.getLogger(__name__)

_memory_instance = None
_lightrag_stores: dict[str, Any] = {}
_kb_cache: dict[str, str] = {}
_KB_CACHE_MAX_SIZE = 500

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
            if result and "not found" not in result.lower():
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
