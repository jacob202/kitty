"""Storage routing contract for memory ingestion, retrieval, and lifecycle actions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from src.memory.retrieval_adapter import RetrievalAdapter
from src.memory.source_ledger import SourceLedger


@dataclass
class RoutingEvent:
    operation: str
    status: str
    requested_store: str | None = None
    selected_store: str | None = None
    data_kind: str | None = None
    reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class StorageRouter:
    """Enforce store-routing policy and provide retrieval fallback orchestration."""

    _INGEST_POLICY = {
        "knowledge": "lightrag",
        "journal": "journaldb",
    }

    def __init__(self, source_ledger: SourceLedger | None = None):
        self.source_ledger = source_ledger or SourceLedger()
        self._events: list[RoutingEvent] = []

    def events(self) -> list[RoutingEvent]:
        return list(self._events)

    def record(self, event: RoutingEvent) -> None:
        self._events.append(event)

    def ingest(
        self,
        *,
        data_kind: str,
        target_store: str,
        writer: Callable[..., Any],
        **writer_kwargs: Any,
    ) -> Any:
        required_store = self._INGEST_POLICY.get(data_kind)
        if required_store is None:
            self.record(
                RoutingEvent(
                    operation="ingest",
                    status="blocked",
                    requested_store=target_store,
                    data_kind=data_kind,
                    reason="unknown data_kind",
                )
            )
            raise ValueError(f"unknown data_kind: {data_kind}")

        if target_store != required_store:
            self.record(
                RoutingEvent(
                    operation="ingest",
                    status="blocked",
                    requested_store=target_store,
                    selected_store=required_store,
                    data_kind=data_kind,
                    reason="wrong-store write blocked",
                )
            )
            raise ValueError(
                f"wrong-store write blocked: data_kind '{data_kind}' must use '{required_store}', "
                f"not '{target_store}'"
            )

        result = writer(**writer_kwargs)
        self.record(
            RoutingEvent(
                operation="ingest",
                status="routed",
                requested_store=target_store,
                selected_store=required_store,
                data_kind=data_kind,
            )
        )
        return result

    def query_knowledge(
        self,
        *,
        question: str,
        domain: str | None,
        adapter: RetrievalAdapter | None = None,
        lightrag_search: Callable[[str], str] | None = None,
        memory_search: Callable[[str, str | None], str] | None = None,
        is_empty_lightrag_result: Callable[[str], bool] | None = None,
    ) -> str:
        if adapter is not None:
            hits = adapter.query(question, domain)
            if hits:
                first_hit = hits[0]
                status = "routed" if first_hit.source_store == "lightrag" else "fallback"
                self.record(
                    RoutingEvent(
                        operation="query",
                        status=status,
                        requested_store="lightrag",
                        selected_store=first_hit.source_store,
                        data_kind="knowledge",
                        metadata={
                            "domain": domain,
                            "resolved_domain": first_hit.domain,
                            "backend": getattr(adapter, "backend_name", "unknown"),
                        },
                    )
                )
                return first_hit.text
            self.record(
                RoutingEvent(
                    operation="query",
                    status="empty",
                    requested_store="lightrag",
                    selected_store="chromadb",
                    data_kind="knowledge",
                    metadata={
                        "domain": domain,
                        "backend": getattr(adapter, "backend_name", "unknown"),
                    },
                )
            )
            return ""

        if lightrag_search is None or memory_search is None or is_empty_lightrag_result is None:
            raise ValueError("query_knowledge requires either an adapter or all legacy search callbacks")

        lightrag_result = lightrag_search(question)
        if lightrag_result and not is_empty_lightrag_result(lightrag_result):
            self.record(
                RoutingEvent(
                    operation="query",
                    status="routed",
                    selected_store="lightrag",
                    data_kind="knowledge",
                    metadata={"domain": domain},
                )
            )
            return lightrag_result

        fallback_domains = self._fallback_domains(domain)
        for fallback_domain in fallback_domains:
            result = memory_search(question, fallback_domain)
            if result:
                self.record(
                    RoutingEvent(
                        operation="query",
                        status="fallback",
                        requested_store="lightrag",
                        selected_store="chromadb",
                        data_kind="knowledge",
                        metadata={
                            "domain": domain,
                            "fallback_domain": fallback_domain,
                        },
                    )
                )
                return result

        self.record(
            RoutingEvent(
                operation="query",
                status="empty",
                requested_store="lightrag",
                selected_store="chromadb",
                data_kind="knowledge",
                metadata={"domain": domain},
            )
        )
        return ""

    def quarantine_candidate(
        self,
        candidate_id: int,
        *,
        reason: str,
        quarantined_at: str | None = None,
        conflicting_candidate_id: int | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        result = self.source_ledger.quarantine_candidate(
            candidate_id=candidate_id,
            reason=reason,
            quarantined_at=quarantined_at,
            conflicting_candidate_id=conflicting_candidate_id,
            notes=notes,
        )
        self.record(
            RoutingEvent(
                operation="quarantine",
                status="routed",
                selected_store="source_ledger",
                data_kind="candidate",
            )
        )
        return result

    def promote_candidate(
        self,
        candidate_id: int,
        *,
        promoted_at: str | None = None,
        confidence: float | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        result = self.source_ledger.promote_candidate(
            candidate_id=candidate_id,
            promoted_at=promoted_at,
            confidence=confidence,
            notes=notes,
        )
        self.record(
            RoutingEvent(
                operation="promote",
                status="routed",
                selected_store="source_ledger",
                data_kind="candidate",
            )
        )
        return result

    def retire_candidate(
        self,
        candidate_id: int,
        *,
        retired_at: str | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        result = self.source_ledger.retire_candidate(
            candidate_id=candidate_id,
            retired_at=retired_at,
            notes=notes,
        )
        self.record(
            RoutingEvent(
                operation="retire",
                status="routed",
                selected_store="source_ledger",
                data_kind="candidate",
            )
        )
        return result

    @staticmethod
    def _fallback_domains(domain: str | None) -> list[str | None]:
        if domain is None:
            return [None]
        if domain == "general":
            # Known retrieval gap: some document chunks have no domain metadata.
            return ["general", None]
        return [domain]
