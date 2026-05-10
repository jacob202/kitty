from __future__ import annotations

from src.memory.orchestrator import MemoryOrchestrator
from src.services import context_service


class _FakeOrchestrator:
    def __init__(self):
        self.calls: list[tuple[str, str | None]] = []

    def query_knowledge(self, question: str, domain: str | None = None) -> str:
        self.calls.append((question, domain))
        if domain == "code":
            return "code-domain-doc"
        if domain == "general":
            return ""
        if domain is None:
            return "untagged-general-doc"
        return ""

    def retrieve_context(self, *args, **kwargs):
        return {"documents": [], "facts": [], "conversations": []}


def _setup(monkeypatch):
    fake = _FakeOrchestrator()
    context_service._KB_CACHE.clear()
    monkeypatch.setattr(context_service, "get_memory", lambda: fake)
    return fake


def test_general_domain_falls_back_to_unscoped_retrieval(monkeypatch):
    fake = _setup(monkeypatch)
    result = context_service.query_knowledge_base("what did we store?", "general")
    assert result == ""
    assert fake.calls == [("what did we store?", "general")]


def test_none_domain_uses_unscoped_once(monkeypatch):
    fake = _setup(monkeypatch)
    result = context_service.query_knowledge_base("anything recent?", None)
    assert result == "untagged-general-doc"
    assert fake.calls == [("anything recent?", None)]


def test_specific_domain_keeps_domain_scope_when_docs_exist(monkeypatch):
    fake = _setup(monkeypatch)
    result = context_service.query_knowledge_base("show code memory", "code")
    assert result == "code-domain-doc"
    assert fake.calls == [("show code memory", "code")]
