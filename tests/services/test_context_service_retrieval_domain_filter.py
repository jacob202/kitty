from __future__ import annotations

from src.memory.storage_router import StorageRouter
from src.services import context_service


class FakeLightRAGStore:
    def search(self, _question: str) -> str:
        return "[no-context]"


class FakeMemory:
    def __init__(self):
        self.calls: list[str | None] = []

    def retrieve_context(
        self,
        _question: str,
        *,
        n_conversations: int,
        n_facts: int,
        n_documents: int,
        domain: str | None,
    ):
        self.calls.append(domain)
        if domain == "code":
            return {"documents": ["code-domain-doc"], "facts": [], "conversations": []}
        if domain == "general":
            # Simulate domain-filter gap: no tagged general documents.
            return {"documents": [], "facts": [], "conversations": []}
        if domain is None:
            # Unscoped fallback can still recover untagged docs.
            return {"documents": ["untagged-general-doc"], "facts": [], "conversations": []}
        return {"documents": [], "facts": [], "conversations": []}


class _NoopLedger:
    def quarantine_candidate(self, **kwargs):  # pragma: no cover - not used here
        return kwargs

    def promote_candidate(self, **kwargs):  # pragma: no cover - not used here
        return kwargs

    def retire_candidate(self, **kwargs):  # pragma: no cover - not used here
        return kwargs


def _setup(monkeypatch):
    context_service._kb_cache.clear()
    context_service._lightrag_stores.clear()
    context_service._storage_router = StorageRouter(source_ledger=_NoopLedger())
    fake_memory = FakeMemory()
    monkeypatch.setattr(context_service, "_get_lightrag_for_domain", lambda _domain: FakeLightRAGStore())
    monkeypatch.setattr(context_service, "_get_memory", lambda: fake_memory)
    return fake_memory


def test_general_domain_falls_back_to_unscoped_retrieval(monkeypatch):
    fake_memory = _setup(monkeypatch)

    result = context_service.query_knowledge_base("what did we store?", "general")

    assert result == "untagged-general-doc"
    assert fake_memory.calls == ["general", None]


def test_none_domain_uses_unscoped_once(monkeypatch):
    fake_memory = _setup(monkeypatch)

    result = context_service.query_knowledge_base("anything recent?", None)

    assert result == "untagged-general-doc"
    assert fake_memory.calls == [None]


def test_specific_domain_keeps_domain_scope_when_docs_exist(monkeypatch):
    fake_memory = _setup(monkeypatch)

    result = context_service.query_knowledge_base("show code memory", "code")

    assert result == "code-domain-doc"
    assert fake_memory.calls == ["code"]
