"""Self-contained quarantine queue for memory candidates."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class QueueState(str, Enum):
    STAGED = "staged"
    REVIEW = "review"
    APPROVED = "approved"
    REJECTED = "rejected"
    RETIRED = "retired"


_QUARANTINE_BY_DEFAULT = frozenset({"sensitive", "personal"})


def is_sensitive_or_personal(category: str | None) -> bool:
    return (category or "").strip().lower() in _QUARANTINE_BY_DEFAULT


def should_default_to_quarantine(candidate: "MemoryCandidate") -> bool:
    return is_sensitive_or_personal(candidate.category) or candidate.conflict_marker


def requires_source_evidence(candidate: "MemoryCandidate") -> bool:
    return bool(candidate.source_evidence)


@dataclass
class MemoryCandidate:
    candidate_id: str
    content: str
    category: str = "general"
    source_evidence: list[str] = field(default_factory=list)
    conflict_marker: bool = False
    state: QueueState = QueueState.STAGED
    promoted: bool = False
    retired: bool = False
    review_note: str | None = None
    decision_reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def copy(self) -> "MemoryCandidate":
        return MemoryCandidate(
            candidate_id=self.candidate_id,
            content=self.content,
            category=self.category,
            source_evidence=list(self.source_evidence),
            conflict_marker=self.conflict_marker,
            state=self.state,
            promoted=self.promoted,
            retired=self.retired,
            review_note=self.review_note,
            decision_reason=self.decision_reason,
            metadata=dict(self.metadata),
        )


class QuarantineQueue:
    """In-memory queue with explicit lifecycle validation."""

    def __init__(self):
        self._items: dict[str, MemoryCandidate] = {}

    def stage(self, candidate: MemoryCandidate) -> MemoryCandidate:
        if not candidate.candidate_id:
            raise ValueError("candidate_id is required")

        item = candidate.copy()
        item.state = QueueState.REVIEW if should_default_to_quarantine(item) else QueueState.STAGED
        item.retired = False
        self._items[item.candidate_id] = item
        return item.copy()

    def review(self, candidate_id: str, note: str | None = None) -> MemoryCandidate:
        item = self._get_active(candidate_id)
        self._ensure_not_retired(item)
        if item.state not in {QueueState.STAGED, QueueState.REVIEW}:
            raise ValueError(f"cannot move {item.state.value} item to review")
        item.state = QueueState.REVIEW
        if note is not None:
            item.review_note = note
        return item.copy()

    def approve(self, candidate_id: str, reason: str | None = None) -> MemoryCandidate:
        item = self._get_active(candidate_id)
        self._ensure_not_retired(item)
        self._ensure_state(item, {QueueState.REVIEW}, "approve")
        if item.conflict_marker:
            raise ValueError("cannot approve a candidate marked with a conflict")
        if not requires_source_evidence(item):
            raise ValueError("source evidence is required before durable promotion")
        item.state = QueueState.APPROVED
        item.promoted = True
        item.decision_reason = reason
        return item.copy()

    def reject(self, candidate_id: str, reason: str | None = None) -> MemoryCandidate:
        item = self._get_active(candidate_id)
        self._ensure_not_retired(item)
        self._ensure_state(item, {QueueState.REVIEW}, "reject")
        item.state = QueueState.REJECTED
        item.promoted = False
        item.decision_reason = reason
        return item.copy()

    def retire(self, candidate_id: str, reason: str | None = None) -> MemoryCandidate:
        item = self._get_active(candidate_id)
        if item.state is QueueState.RETIRED:
            raise ValueError("candidate is already retired")
        item.state = QueueState.RETIRED
        item.retired = True
        item.promoted = False
        item.decision_reason = reason
        return item.copy()

    def mark_conflict(self, candidate_id: str, reason: str | None = None) -> MemoryCandidate:
        item = self._get_active(candidate_id)
        item.conflict_marker = True
        if reason is not None:
            item.decision_reason = reason
        if item.state is QueueState.STAGED:
            item.state = QueueState.REVIEW
        return item.copy()

    def clear_conflict_marker(self, candidate_id: str) -> MemoryCandidate:
        item = self._get_active(candidate_id)
        item.conflict_marker = False
        return item.copy()

    def get(self, candidate_id: str) -> MemoryCandidate:
        return self._get_active(candidate_id).copy()

    def list_items(self) -> list[MemoryCandidate]:
        return [item.copy() for item in self._items.values()]

    def _get_active(self, candidate_id: str) -> MemoryCandidate:
        try:
            return self._items[candidate_id]
        except KeyError as exc:
            raise KeyError(f"candidate not found: {candidate_id}") from exc

    @staticmethod
    def _ensure_not_retired(item: MemoryCandidate) -> None:
        if item.state is QueueState.RETIRED:
            raise ValueError("retired candidates cannot be transitioned")

    @staticmethod
    def _ensure_state(item: MemoryCandidate, allowed: set[QueueState], action: str) -> None:
        if item.state not in allowed:
            allowed_names = ", ".join(sorted(state.value for state in allowed))
            raise ValueError(f"cannot {action} item in state {item.state.value}; allowed: {allowed_names}")

