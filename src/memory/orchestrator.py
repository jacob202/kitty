"""MemoryOrchestrator — single entry point for all memory operations.

Owns backends, routing, and the LightRAG→ChromaDB fallback chain.
Replaces module-level singletons in context_service.py and specialist_framework.py.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from src.memory.storage_router import StorageRouter
from src.memory.retrieval_adapter import CurrentStackRetrievalAdapter

logger = logging.getLogger(__name__)


@dataclass
class MemoryResult:
    success: bool
    data: Any = None
    error: str = ""
    metadata: dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class MemoryOrchestrator:
    """Single interface for all memory operations.

    Methods mirror what context_service.py and specialist_framework.py
    already expect, so this is a drop-in replacement for their module-level
    get_memory() singletons.
    """

    def __init__(self):
        self._initialized = False
        self._backends: dict[str, Any] = {}
        self._backend_factories: dict[str, Any] = {}
        self._router = StorageRouter()
        self._lightrag_stores: dict[str, Any] = {}

    _DOMAIN_TARGETS = {
        "knowledge": "lightrag",
        "journal": "journaldb",
        "correction": "corrections",
        "corrections": "corrections",
    }

    def _lazy_init(self):
        if self._initialized:
            return

        from src.memory.lightrag_store import LightRAGStore
        from src.memory.journal_db import JournalDB
        from src.memory.correction_memory import CorrectionMemory
        from src.memory.kitty_memory_enhanced import KittyMemoryEnhanced
        from src.memory.source_ledger import SourceLedger

        self._backend_factories = {
            "lightrag": lambda: LightRAGStore(),
            "journaldb": lambda: JournalDB(),
            "chromadb": lambda: KittyMemoryEnhanced(),
            "corrections": lambda: CorrectionMemory(),
            "source_ledger": lambda: SourceLedger(),
        }
        self._initialized = True

    def _get_backend(self, name: str) -> Any | None:
        self._lazy_init()
        if name in self._backends:
            return self._backends[name]
        factory = self._backend_factories.get(name)
        if factory is None:
            return None
        backend = factory()
        self._backends[name] = backend
        return backend

    @classmethod
    def _resolve_domain_target(cls, domain: str) -> str | None:
        if domain in cls._DOMAIN_TARGETS:
            return cls._DOMAIN_TARGETS[domain]
        # Keep StorageRouter policy as fallback for known routed domains.
        return StorageRouter._INGEST_POLICY.get(domain)

    # ── KB query with LightRAG → ChromaDB fallback ──────────────────

    def query_knowledge(self, question: str, domain: str | None = None) -> str:
        """Query KB with LightRAG→ChromaDB fallback via StorageRouter."""
        self._lazy_init()
        cache_key = f"{domain}:{question[:100]}"
        cached = self._kb_cache_get(cache_key)
        if cached is not None:
            return cached

        adapter = CurrentStackRetrievalAdapter(
            lightrag_search=self._lightrag_search,
            memory_search=self._memory_search,
            is_empty_lightrag_result=self._is_empty_lightrag_result,
        )

        content = self._router.query_knowledge(
            question=question,
            domain=domain,
            adapter=adapter,
        )
        if content:
            self._kb_cache_set(cache_key, content)
        return content

    def _lightrag_search(self, question: str) -> str:
        store = self._get_backend("lightrag")
        if store is None:
            return ""
        try:
            return store.search(question)
        except Exception as e:
            logger.debug("LightRAG search failed: %s", e)
            return ""

    def _memory_search(self, question: str, domain: str | None) -> str:
        store = self._get_backend("chromadb")
        if store is None:
            return ""
        try:
            ctx = store.retrieve_context(
                question,
                n_conversations=0,
                n_facts=0,
                n_documents=5,
                domain=domain,
            )
            docs = ctx.get("documents", [])
            return "\n---\n".join(docs)[:3000] if docs else ""
        except Exception as e:
            logger.debug("ChromaDB search failed: %s", e)
            return ""

    @staticmethod
    def _is_empty_lightrag_result(result: str) -> bool:
        r = result.lower()
        return any(
            m in r
            for m in (
                "not found",
                "no-context",
                "no relevant document chunks",
                "lightrag search error",
            )
        )

    # ── KB cache ────────────────────────────────────────────────────

    _kb_cache: dict[str, str] = {}
    _KB_CACHE_MAX = 500

    @classmethod
    def _kb_cache_get(cls, key: str) -> str | None:
        return cls._kb_cache.get(key)

    @classmethod
    def _kb_cache_set(cls, key: str, value: str) -> None:
        cls._kb_cache[key] = value
        if len(cls._kb_cache) > cls._KB_CACHE_MAX:
            cls._kb_cache.pop(next(iter(cls._kb_cache)))

    # ── Context retrieval (specialist_framework interface) ──────────

    def retrieve_context(
        self,
        query: str,
        n_conversations: int = 0,
        n_facts: int = 0,
        n_documents: int = 5,
        domain: str | None = None,
    ) -> dict[str, Any]:
        """Match KittyMemoryEnhanced.retrieve_context signature."""
        store = self._get_backend("chromadb")
        if store is not None:
            try:
                return store.retrieve_context(
                    query,
                    n_conversations=n_conversations,
                    n_facts=n_facts,
                    n_documents=n_documents,
                    domain=domain,
                )
            except Exception as e:
                logger.debug("ChromaDB retrieve_context failed: %s", e)
        return {"conversations": [], "facts": [], "documents": []}

    # ── Store / retrieve / delete ───────────────────────────────────

    def store(self, item: dict, domain: str = "knowledge") -> MemoryResult:
        """Store with StorageRouter policy enforcement."""
        target = self._resolve_domain_target(domain)
        if not target:
            return MemoryResult(success=False, error=f"unknown domain: {domain}")

        backend = self._get_backend(target)
        if backend is None:
            return MemoryResult(success=False, error=f"no backend for {target}")

        try:
            if hasattr(backend, "add"):
                backend.add(item)
            if domain in StorageRouter._INGEST_POLICY:
                self._router.ingest(
                    data_kind=domain,
                    target_store=target,
                    writer=lambda: None,
                )
            return MemoryResult(success=True, metadata={"domain": domain, "store": target})
        except Exception as e:
            return MemoryResult(success=False, error=str(e))

    def retrieve(self, query: str, domain: str = "knowledge", limit: int = 5) -> MemoryResult:
        target = self._resolve_domain_target(domain)
        if not target:
            return MemoryResult(success=False, error=f"unknown domain: {domain}")
        backend = self._get_backend(target)
        if backend is None:
            return MemoryResult(success=False, error=f"no backend for {target}")
        try:
            if hasattr(backend, "search"):
                results = backend.search(query, limit=limit)
                return MemoryResult(success=True, data=results)
            return MemoryResult(success=False, error="backend has no search")
        except Exception as e:
            return MemoryResult(success=False, error=str(e))

    def get_context(self, query: str, domains: list[str] | None = None) -> MemoryResult:
        """Aggregate context from multiple backends."""
        results = []
        targets = domains or ["lightrag", "journaldb", "corrections"]
        for name in targets:
            backend = self._get_backend(name)
            if backend is None:
                continue
            try:
                if hasattr(backend, "get_relevant_context"):
                    results.append(backend.get_relevant_context(query))
                elif hasattr(backend, "search"):
                    results.append(backend.search(query))
            except Exception as e:
                logger.debug("%s backend get_context failed: %s", name, e)
                continue
        return MemoryResult(
            success=True,
            data="\n\n".join(str(r) for r in results),
            metadata={"domains": targets},
        )

    def delete(self, item_id: str, domain: str = "knowledge") -> MemoryResult:
        target = self._resolve_domain_target(domain)
        if not target:
            return MemoryResult(success=False, error=f"unknown domain: {domain}")
        backend = self._get_backend(target)
        if backend is None:
            return MemoryResult(success=False, error=f"no backend for {target}")
        try:
            if hasattr(backend, "delete"):
                backend.delete(item_id)
            return MemoryResult(success=True)
        except Exception as e:
            return MemoryResult(success=False, error=str(e))


# ── Global singleton (replaces _get_memory() in context_service.py etc.) ──

_instance: MemoryOrchestrator | None = None


def get_memory() -> MemoryOrchestrator:
    global _instance
    if _instance is None:
        _instance = MemoryOrchestrator()
    return _instance
