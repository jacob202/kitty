"""KittyBuilder — pre-execution scope validation and escalation.

Implements the mandatory "Validate Scope" Builder Loop stage (Builder
Operating Model §5/§6) and the STOP → Escalate → Return Control decision
boundary (§4).

Scope is validated against the packet contract at execution time. The contract
fields (objective, acceptance_criteria, allowed_paths, validation_commands,
and optional forbidden_changes) decide whether the work is clear, measurable,
bounded, and free of architectural judgment.

Escalation is return-control only: it raises EscalationError with a structured
artifact and leaves the task untouched. It does NOT add a new workflow state and
does NOT persist a Knowledge Model object (Finding / Knowledge / Receipt have no
runtime representation yet — ADR-0019).
"""

from __future__ import annotations

import posixpath
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
    if cleaned.startswith("/") or "\\" in cleaned:
        return None
    normalized = posixpath.normpath(cleaned)
    if normalized in {"", ".", ".."}:
        return None
    if normalized.startswith("/") or normalized.startswith("../"):
        return None
    return normalized


def _touches_protected_zone(normalized: str) -> bool:
    lowered = normalized.lower()
    if lowered in PROTECTED_FILES:
        return True
    return any(lowered.startswith(prefix) for prefix in PROTECTED_PREFIXES)


def _paths_overlap(first: str, second: str) -> bool:
    """Return whether two normalized file-or-directory paths overlap."""
    return (
        first == second
        or first.startswith(f"{second.rstrip('/')}/")
        or second.startswith(f"{first.rstrip('/')}/")
    )


def _has_authority_for_protected_path(
    packet: dict[str, Any], normalized_path: str
) -> bool:
    """Check whether the packet has ratified authority to modify a protected path.

    A packet touching a protected architecture/governance path does NOT escalate
    when it explicitly authorizes that work and references the governing authority.

    Proceed when:
      - The objective or acceptance criteria explicitly names this path or the
        containing area, AND the work is clearly bounded (not generic).
      - The packet objective references a ratified ADR or canonical contract.

    Escalate when:
      - The path is protected but the objective is generic ("improve docs").
      - The path is constitutional and no governing ADR is referenced.
    """
    objective = (packet.get("objective") or "").lower()
    acceptance = " ".join(
        str(a).lower() for a in (packet.get("acceptance_criteria") or [])
    )
    combined = f"{objective} {acceptance}"
    path_lower = normalized_path.lower()

    # Explicit path reference: objective or acceptance names the exact file
    # or its parent directory (e.g. "update docs/adr/0001-db-scope.md" or
    # "fix frontmatter in docs/adr/")
    if path_lower in combined or path_lower.strip("docs/") in combined:
        return True
    parent = path_lower.rsplit("/", 1)[0] + "/" if "/" in path_lower else ""
    if parent and parent in combined:
        return True

    # ADR reference: objective cites a ratified decision
    if "adr-" in combined or "adr " in combined or "adr/" in combined:
        return True

    return False


def validate_scope(packet: dict[str, Any]) -> list[ScopeFinding]:
    """Validate a packet contract before execution.

    Returns an empty list when the contract is clear, measurable, bounded, and
    free of architectural judgment. Otherwise returns one finding per problem.
    """
    findings: list[ScopeFinding] = []

    objective = (packet.get("objective") or "").strip()
    acceptance = packet.get("acceptance_criteria") or []
    allowed = packet.get("allowed_paths") or []
    forbidden = packet.get("forbidden_changes")
    normalized_allowed: list[str] = []

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
            else:
                normalized_allowed.append(normalized)
                if _touches_protected_zone(normalized):
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

    # P1-05 validates the contract declaration. P3-02 owns detecting an
    # actual worker modification after execution begins.
    if "forbidden_changes" in packet:
        if not isinstance(forbidden, list) or not all(
            isinstance(path, str) for path in forbidden
        ):
            findings.append(
                ScopeFinding(
                    "incomplete_contract",
                    "forbidden_changes",
                    "forbidden_changes must be a list of repo-relative paths",
                )
            )
        else:
            normalized_forbidden: list[str] = []
            for raw in forbidden:
                normalized = _normalize_allowed_path(raw)
                if normalized is None:
                    findings.append(
                        ScopeFinding(
                            "incomplete_contract",
                            "forbidden_changes",
                            f"forbidden_changes entry is not a repo-relative safe path: {raw!r}",
                        )
                    )
                else:
                    normalized_forbidden.append(normalized)
            for allowed_path in normalized_allowed:
                for forbidden_path in normalized_forbidden:
                    if _paths_overlap(allowed_path, forbidden_path):
                        findings.append(
                            ScopeFinding(
                                "forbidden_change",
                                "forbidden_changes",
                                f"allowed_paths permits forbidden path {forbidden_path!r} "
                                f"through {allowed_path!r}",
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
