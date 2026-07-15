"""KittyBuilder — pre-execution scope validation and escalation.

Implements the mandatory "Validate Scope" Builder Loop stage (Builder
Operating Model §5/§6) and the STOP → Escalate → Return Control decision
boundary (§4).

Scope is validated against the packet contract that already exists at
execution time — no new schema fields are introduced. The contract fields
(objective, acceptance_criteria, allowed_paths, validation_commands) are
produced by ``builder_attempt.build_context_bundle`` and are sufficient to
decide whether the work is clear, measurable, bounded, and free of
architectural judgment.

Escalation is return-control only: it raises EscalationError with a structured
artifact and leaves the task untouched. It does NOT add a new workflow state and
does NOT persist a Knowledge Model object (Finding / Knowledge / Receipt have no
runtime representation yet — ADR-0019).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

# Paths whose modification requires architectural judgment (Builder Operating
# Model §4: not allowed to reinterpret doctrine, replace architectural patterns,
# or change architecture/governance without an ADR — see AGENTS.md). A packet
# whose allowed_paths reaches any of these must demonstrate sufficient
# architectural authority (objective/acceptance explicitly authorizing the path
# or referencing the governing ADR) — otherwise escalate. Touching a protected
# zone is not itself forbidden; doing so WITHOUT ratified authority is.
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


UNMEASURABLE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(make|get)\s+it\s+better\b"),
    re.compile(r"\b(is|are)\s+(better|good|great|clean|nice|fast|well|fine)\b\s*$"),
    re.compile(r"^\s*better\s*$"),
    re.compile(r"^\s*improved?\s*$"),
)


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


def _protected_zone(normalized: str) -> str | None:
    """Classify a normalized path's protected zone.

    Returns ``"file"`` for a top-level protected governance document, the
    matched protected prefix (e.g. ``"docs/adr/"``) for a protected directory,
    or ``None`` when the path is not protected.
    """
    lowered = normalized.lower()
    if lowered in PROTECTED_FILES:
        return "file"
    for prefix in PROTECTED_PREFIXES:
        if lowered.startswith(prefix):
            return prefix
    return None


def _touches_protected_zone(normalized: str) -> bool:
    return _protected_zone(normalized) is not None


def _has_authority_for_protected_path(
    packet: dict[str, Any], normalized_path: str
) -> bool:
    """Check whether the packet explicitly authorizes the protected path.

    Authority is never inferred from vague textual cues (an ADR mention, the
    word "constitution", generic phrasing). It must be stated by the contract
    itself:

      - The exact protected file is named in the objective or acceptance
        criteria (bounded, explicit work), OR
      - For a protected *directory* (e.g. ``docs/adr/``), that directory is
        named explicitly in the objective or acceptance criteria.

    Anything else escalates — including a generic objective that merely
    references a ratified ADR without naming the file it touches.
    """
    zone = _protected_zone(normalized_path)
    if zone is None:
        return False
    objective = packet.get("objective") or ""
    acceptance = " ".join(
        str(a) for a in (packet.get("acceptance_criteria") or [])
    )
    contract_text = f"{objective}\n{acceptance}"

    # Exact protected file named in the contract → explicit authority.
    if normalized_path in contract_text:
        return True
    # For a protected directory, naming the directory (not the whole repo)
    # bounds the work to that area.
    if zone != "file" and zone in contract_text:
        return True
    return False


def _criterion_is_measurable(criterion: str) -> bool:
    lowered = criterion.strip().lower()
    if not lowered:
        return False

    if re.search(
        r"\b(test|check|verify|assert|measure|file|exists|pass|fail|build|run|"
        r"output|returns?|contain|no longer|lint|create|remove|add|update|delete|"
        r"install|deploy|migrate|commit)\b",
        lowered,
    ):
        return True

    for pattern in UNMEASURABLE_PATTERNS:
        if pattern.search(lowered):
            return False

    return True


def validate_scope(packet: dict[str, Any]) -> list[ScopeFinding]:
    """Validate a packet contract before execution.

    Returns an empty list when the contract is clear, measurable, bounded, and
    free of architectural judgment. Otherwise returns one finding per problem.
    """
    findings: list[ScopeFinding] = []

    objective = (packet.get("objective") or "").strip()
    acceptance = packet.get("acceptance_criteria") or []
    allowed = packet.get("allowed_paths") or []
    forbidden = packet.get("forbidden_changes") or []

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
    else:
        for i, criterion in enumerate(acceptance):
            if not _criterion_is_measurable(str(criterion)):
                findings.append(
                    ScopeFinding(
                        "incomplete_contract",
                        "acceptance_criteria",
                        f"acceptance_criteria[{i}] is not measurable: {criterion!r} "
                        f"— must describe a testable, observable condition",
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
            elif _touches_protected_zone(normalized):
                if not _has_authority_for_protected_path(packet, normalized):
                    findings.append(
                        ScopeFinding(
                            "architectural_judgment_required",
                            "allowed_paths",
                            f"allowed_paths reaches a protected architecture/governance "
                            f"zone that requires an ADR/architecture decision: {raw!r}. "
                            f"To proceed, the objective or acceptance criteria must "
                            f"explicitly name this path or reference the governing ADR.",
                        )
                    )

    if forbidden:
        allowed_norm = set()
        for raw in allowed:
            n = _normalize_allowed_path(raw)
            if n:
                allowed_norm.add(n)
        for raw in forbidden:
            n = _normalize_allowed_path(raw)
            if n is None:
                findings.append(
                    ScopeFinding(
                        "unbounded_scope",
                        "forbidden_changes",
                        f"forbidden_changes entry is not a repo-relative safe path: {raw!r}",
                    )
                )
            elif n in allowed_norm:
                findings.append(
                    ScopeFinding(
                        "scope_conflict",
                        "forbidden_changes",
                        f"forbidden_changes path {raw!r} is also in allowed_paths; "
                        f"worker cannot be authorized to modify a forbidden path",
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
            "Builder does not guess or expand scope. Resolve the contract (or obtain "
            "an ADR/architecture decision) and re-submit the packet."
        ),
    }
