"""Retrieval adapter contract for backend-swappable knowledge retrieval."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, Callable


@dataclass
class RetrievalHit:
    text: str
    source_store: str
    domain: str | None
    metadata: dict[str, Any] = field(default_factory=dict)


class RetrievalAdapter(Protocol):
    backend_name: str

    def query(self, question: str, domain: str | None) -> list[RetrievalHit]:
        ...


class CurrentStackRetrievalAdapter:
    """Adapter for current LightRAG + Chroma retrieval stack."""

    backend_name = "current-stack"

    def __init__(
        self,
        *,
        lightrag_search: Callable[[str], str],
        memory_search: Callable[[str, str | None], str],
        is_empty_lightrag_result: Callable[[str], bool],
    ):
        self._lightrag_search = lightrag_search
        self._memory_search = memory_search
        self._is_empty_lightrag_result = is_empty_lightrag_result

    def query(self, question: str, domain: str | None) -> list[RetrievalHit]:
        lightrag_result = self._lightrag_search(question)
        if lightrag_result and not self._is_empty_lightrag_result(lightrag_result):
            return [
                RetrievalHit(
                    text=lightrag_result,
                    source_store="lightrag",
                    domain=domain,
                )
            ]

        for fallback_domain in self._fallback_domains(domain):
            memory_result = self._memory_search(question, fallback_domain)
            if memory_result:
                return [
                    RetrievalHit(
                        text=memory_result,
                        source_store="chromadb",
                        domain=fallback_domain,
                        metadata={"fallback_from_domain": domain},
                    )
                ]

        return []

    @staticmethod
    def _fallback_domains(domain: str | None) -> list[str | None]:
        if domain is None:
            return [None]
        if domain == "general":
            return ["general", None]
        return [domain]


class LanceDBPrototypeRetrievalAdapter:
    """Prototype-only stub for future LanceDB integration."""

    backend_name = "lancedb-prototype"

    def query(self, question: str, domain: str | None) -> list[RetrievalHit]:
        _ = question
        _ = domain
        return []
