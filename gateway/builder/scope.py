"""Shared fail-closed scope primitives for KittyBuilder packet execution.

The queue runner also supports generic tasks whose allowlist may be absent.
Packet identity verification is stricter: initiative packets always carry a
non-empty, repo-relative allowlist, and corrupt durable scope data must stop
execution instead of widening it.
"""

from __future__ import annotations

import posixpath
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ScopeFinding:
    """One structured reason execution must stop or return control."""

    category: str
    field: str
    message: str


class EscalationError(RuntimeError):
    """Return control with structured findings instead of guessing scope."""

    def __init__(
        self,
        findings: list[ScopeFinding],
        *,
        evidence: dict[str, Any] | None = None,
        artifact: dict[str, Any] | None = None,
    ) -> None:
        message = "; ".join(finding.message for finding in findings)
        super().__init__(message or "scope validation failed")
        self.findings = list(findings)
        self.evidence = evidence or {}
        self.artifact = artifact or {}


def normalize_allowed_path(raw: str) -> str:
    """Return a bounded repo-relative path or raise ``ValueError``."""
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("allowed path must be a non-empty string")
    cleaned = raw.strip()
    if cleaned.startswith(("/", "~", "\\")) or "\\" in cleaned:
        raise ValueError(f"allowed path must be repo-relative: {raw!r}")
    normalized = posixpath.normpath(cleaned)
    if normalized in {"", ".", ".."} or normalized.startswith("../"):
        raise ValueError(f"allowed path is unbounded or escapes the repo: {raw!r}")
    return normalized.rstrip("/")


def normalize_allowed_paths(allowed_paths: Any) -> list[str]:
    """Validate a packet allowlist without permitting an empty scope."""
    if not isinstance(allowed_paths, list) or not allowed_paths:
        raise ValueError("allowed_paths must be a non-empty list")
    return [normalize_allowed_path(path) for path in allowed_paths]


# CP-08 dogfood finding: this exemption started as a builder_runner.py-only
# local copy (its own _SESSION_STATE_RESIDUE constant). It's canonical here
# instead, because builder_identity.verify_and_escalate calls
# find_changed_path_violations independently of builder_runner's own live
# scope check and had drifted without it — a worker that dutifully followed
# repo convention (CLAUDE.md "Session State": update .claude/STATE.md
# before stopping) failed identity verification for doing exactly that.
#
# Session-state bookkeeping repo convention requires every worker to write
# before stopping. Residue here finalized two completed packets as
# scope_violation (TH-01 attempt 3, TH-02) before builder_runner.py's own
# check gained this exemption.
SESSION_STATE_RESIDUE = frozenset({".claude/STATE.md", ".claude/HANDOFF.md"})

# The --free worker adapter (scripts/kittybuilder_opencode_worker.sh) stages
# the task bundle/context/result as .kittybuilder-{bundle,context,result}-
# <attempt_id>.json at the worktree root so the model can read them via a
# relative path, and cleans them up before finishing. A run that's killed or
# inspected mid-attempt can still show these as changed paths.
WORKER_STAGING_PREFIXES = (
    ".kittybuilder-bundle-",
    ".kittybuilder-context-",
    ".kittybuilder-result-",
)


def is_expected_residue(path: str) -> bool:
    """True for paths every attempt may legitimately touch outside its
    allowlist — repo session-state convention or the runner's own staging
    files — never for anything the model actually implemented."""
    return path in SESSION_STATE_RESIDUE or path.startswith(WORKER_STAGING_PREFIXES)


def find_changed_path_violations(
    changed_paths: list[str], allowed_paths: Any
) -> list[str]:
    """Return changed repo paths outside a strict packet allowlist."""
    normalized_allowed = normalize_allowed_paths(allowed_paths)

    def is_allowed(path: str) -> bool:
        return any(
            path == prefix or path.startswith(f"{prefix}/")
            for prefix in normalized_allowed
        )

    violations: list[str] = []
    for path in changed_paths:
        normalized_path = normalize_allowed_path(path)
        if not is_allowed(normalized_path) and not is_expected_residue(normalized_path):
            violations.append(normalized_path)
    return violations
