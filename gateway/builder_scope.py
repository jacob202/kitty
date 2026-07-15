"""KittyBuilder — pre-execution scope validation and escalation.

Implements the mandatory "Validate Scope" Builder Loop stage (Builder
Operating Model §5/§6) and the STOP → Escalate → Return Control decision
boundary (§4).

The rule is authority-based, not path-based. A protected path in a packet's
``allowed_paths`` escalates unless the *exact* path is explicitly named by the
packet contract (its ``objective`` and/or ``acceptance_criteria``). Naming the
path is the bounded authority: it proves the packet intentionally authorized
that specific work rather than drifting into protected ground. The response is
uniform for every protected path — ADR, constitution, knowledge, or architecture
— so the policy does not encode repository-specific governance into the runtime
and does not have to change when protected areas move.

Scope is validated against the packet contract that already exists at execution
time — no new schema fields are introduced. The contract fields (objective,
acceptance_criteria, allowed_paths, validation_commands) are produced by
``builder_attempt.build_context_bundle``.

Escalation is return-control only: it raises EscalationError with a structured
artifact and leaves the task untouched. It does NOT add a new workflow state and
does NOT persist a Knowledge Model object (Finding / Knowledge / Receipt have no
runtime representation yet — ADR-0019).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Paths considered protected: Builder may not touch them without explicit,
# bounded authority from the packet contract. This set is the *boundary* only;
# the escalation response is uniform for every entry (see validate_scope).
PROTECTED_PREFIXES: tuple[str, ...] = (
    "docs/adr/",
    "docs/architecture/",
    "docs/knowledge/",
    "docs/governance/",
)
PROTECTED_FILES: frozenset[str] = frozenset(
    {
        "docs/constitution.md",
        "docs/vision.md",
        "docs/index.md",
        "docs/governance.md",
        "docs/reference_architecture.md",
    }
)


@dataclass
class ScopeFinding:
    category: str
    field: str
    message: str


class EscalationError(RuntimeError):
    """Raised when scope validation fails or architectural judgment is required.

    This is return-control, not a failure of execution: no worktree or attempt
    is created and the task is left in its pre-execution state. The structured
    ``artifact`` lets the caller surface the decision to the operator.
    """

    def __init__(
        self,
        findings: list[ScopeFinding],
        *,
        evidence: dict[str, Any] | None = None,
        artifact: dict[str, Any] | None = None,
    ) -> None:
        message = "; ".join(f.message for f in findings) or "scope validation failed"
        super().__init__(message)
        self.findings: list[ScopeFinding] = list(findings)
        self.evidence: dict[str, Any] = evidence or {}
        self.artifact: dict[str, Any] = artifact or {}


def _normalize_allowed_path(raw: str) -> str | None:
    """Return a repo-relative normalized path, or None if it escapes the repo."""
    if not isinstance(raw, str):
        return None
    cleaned = raw.strip()
    if not cleaned:
        return None
    if cleaned.startswith("~"):
        return None
    if cleaned.startswith("/") or cleaned.startswith("\\"):
        return None
    if cleaned.startswith("./"):
        cleaned = cleaned[2:]
    if ".." in cleaned.split("/"):
        return None
    return cleaned


def _in_protected_zone(normalized: str) -> bool:
    lowered = normalized.lower()
    if lowered in PROTECTED_FILES:
        return True
    return any(lowered.startswith(prefix) for prefix in PROTECTED_PREFIXES)


def _contract_names_path(
    objective: str, acceptance: list[str], normalized: str
) -> bool:
    """True when the exact protected path is explicitly authorized by the contract.

    Bounded authority exists only when the path string appears verbatim in the
    objective or in one of the acceptance criteria. This is deterministic and
    explainable: the packet named the specific work it intends to do.
    """
    haystack = (objective or "") + "\n" + "\n".join(acceptance or [])
    return normalized in haystack or normalized.rstrip("/") in haystack


def validate_scope(packet: dict[str, Any]) -> list[ScopeFinding]:
    """Validate a packet contract before execution.

    Returns an empty list when the contract is clear, measurable, bounded, and
    free of architectural judgment. Otherwise returns one finding per problem.
    """
    findings: list[ScopeFinding] = []

    objective = (packet.get("objective") or "").strip()
    acceptance = packet.get("acceptance_criteria") or []
    allowed = packet.get("allowed_paths") or []

    if not objective:
        findings.append(
            ScopeFinding(
                "incomplete_contract",
                "objective",
                "objective is empty or missing; contract intent is unclear",
            )
        )
    if not acceptance:
        findings.append(
            ScopeFinding(
                "incomplete_contract",
                "acceptance_criteria",
                "acceptance_criteria is empty or missing; success is not measurable",
            )
        )

    if not allowed:
        findings.append(
            ScopeFinding(
                "unbounded_scope",
                "allowed_paths",
                "allowed_paths is empty; scope is not bounded",
            )
        )
    else:
        for raw in allowed:
            normalized = _normalize_allowed_path(raw)
            if normalized is None:
                findings.append(
                    ScopeFinding(
                        "unbounded_scope",
                        "allowed_paths",
                        f"allowed_paths entry is not a repo-relative safe path: {raw!r}",
                    )
                )
            elif _in_protected_zone(normalized):
                # Authority-based check: a protected path is permitted only when
                # the exact path is explicitly named by the contract. Otherwise
                # the packet lacks bounded authority and must escalate.
                if not _contract_names_path(objective, acceptance, normalized):
                    findings.append(
                        ScopeFinding(
                            "architectural_judgment_required",
                            "allowed_paths",
                            f"protected path lacks bounded authority from the "
                            f"contract (name {normalized!r} in objective/"
                            f"acceptance_criteria to authorize it): {raw!r}",
                        )
                    )

    return findings


def build_scope_escalation_artifact(
    initiative_id: str,
    packet_id: str,
    task_id: str,
    findings: list[ScopeFinding],
) -> dict[str, Any]:
    """Assemble the structured escalation artifact returned to the operator."""
    return {
        "type": "scope_escalation",
        "action": "stop_escalate_return_control",
        "initiative_id": initiative_id,
        "packet_id": packet_id,
        "task_id": task_id,
        "findings": [
            {"category": f.category, "field": f.field, "message": f.message}
            for f in findings
        ],
        "guidance": (
            "Scope validation failed or architectural judgment would be required. "
            "Builder does not guess or expand scope. A protected path may be "
            "authorized only when the exact path is named in the packet contract "
            "(objective/acceptance_criteria). Otherwise resolve the contract (or "
            "obtain an ADR/architecture decision) and re-submit the packet."
        ),
    }
