from __future__ import annotations

from src.memory.retrieval_adapter import (
    CurrentStackRetrievalAdapter,
    LanceDBPrototypeRetrievalAdapter,
    RetrievalHit,
)
from src.memory.storage_router import StorageRouter


class _NoopLedger:
    def quarantine_candidate(self, **kwargs):  # pragma: no cover - not used here
        return kwargs

    def promote_candidate(self, **kwargs):  # pragma: no cover - not used here
        return kwargs

    def retire_candidate(self, **kwargs):  # pragma: no cover - not used here
        return kwargs


def test_current_stack_adapter_returns_lightrag_hit_with_provenance():
    adapter = CurrentStackRetrievalAdapter(
        lightrag_search=lambda _q: "lightrag context",
        memory_search=lambda _q, _d: "",
        is_empty_lightrag_result=lambda _r: False,
    )

    hits = adapter.query("question", "code")

    assert len(hits) == 1
    assert isinstance(hits[0], RetrievalHit)
    assert hits[0].source_store == "lightrag"
    assert hits[0].domain == "code"


def test_current_stack_adapter_falls_back_to_unscoped_for_general_gap():
    def memory_search(_question: str, scoped_domain: str | None) -> str:
        if scoped_domain == "general":
            return ""
        if scoped_domain is None:
            return "untagged doc"
        return ""

    adapter = CurrentStackRetrievalAdapter(
        lightrag_search=lambda _q: "[no-context]",
        memory_search=memory_search,
        is_empty_lightrag_result=lambda result: "no-context" in result,
    )

    hits = adapter.query("question", "general")

    assert len(hits) == 1
    assert hits[0].source_store == "chromadb"
    assert hits[0].domain is None
    assert hits[0].metadata["fallback_from_domain"] == "general"


def test_router_accepts_adapter_contract_without_route_changes():
    adapter = CurrentStackRetrievalAdapter(
        lightrag_search=lambda _q: "",
        memory_search=lambda _q, _d: "memory fallback",
        is_empty_lightrag_result=lambda _r: True,
    )
    router = StorageRouter(source_ledger=_NoopLedger())

    result = router.query_knowledge(question="q", domain="general", adapter=adapter)

    assert result == "memory fallback"
    assert router.events()[-1].operation == "query"
    assert router.events()[-1].selected_store == "chromadb"


def test_lancedb_prototype_adapter_matches_contract():
    adapter = LanceDBPrototypeRetrievalAdapter()

    hits = adapter.query("question", "code")

    assert adapter.backend_name == "lancedb-prototype"
    assert hits == []
