"""Read-only proof that OpenCode actually executed the session-end contract.

A skill file or duplicate-skill warning is not execution evidence.  This audit
uses Kitty's canonical hash-chain receipt parser and workflow-signal parser, then
requires both records to describe the same Builder-owned OpenCode session.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

from gateway.paths import ROOT
from scripts.kb_effectiveness import ReceiptError, load_receipts
from scripts.session_learning import SignalError, load_signals

CANONICAL_SKILL = ROOT / ".agents/skills/session-end/SKILL.md"
DEFAULT_SKILL_CANDIDATES = (
    Path.home() / ".config/opencode/skills/session-end/SKILL.md",
    Path.home() / ".agents/skills/session-end/SKILL.md",
    Path.home() / ".claude/skills/session-end/SKILL.md",
)
DEFAULT_LOG_CANDIDATES = (
    Path.home() / ".local/share/opencode/log",
    Path.home() / ".cache/opencode",
    Path.home() / ".config/opencode",
    Path.home() / "Library/Logs",
    Path.home() / "Library/Application Support/opencode",
    Path.home() / "Library/Application Support/orca/opencode-hooks",
    ROOT,
)
_REQUIRED_CAMPAIGN_MEASUREMENTS = (
    "elapsed_seconds",
    "attempts",
    "repair_commits",
    "regressions",
    "total_tokens",
    "estimated_cost_usd",
)
_RELEVANT_SIGNAL_CATEGORIES = frozenset(
    {"paid_waste", "queue_integrity", "runtime_failure", "tool_failure"}
)
_LOG_POSITIVE_TERMS = ("loaded", "discovered", "resolved", "invoke", "using skill")
_LOG_NEGATIVE_TERMS = ("duplicate", "conflict", "shadow", "warning", "disabled")


class SessionEndAuditError(ValueError):
    """The audit evidence is corrupt or cannot support a claim."""


@dataclass(frozen=True)
class AuditFinding:
    check: str
    status: str
    detail: str
    evidence: str | None = None


@dataclass(frozen=True)
class SessionEndAudit:
    status: str
    findings: tuple[AuditFinding, ...]
    latest_receipt: dict[str, Any] | None = None
    matching_signal: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "findings": [asdict(item) for item in self.findings],
            "latest_receipt": self.latest_receipt,
            "matching_signal": self.matching_signal,
        }


def audit_session_end(
    *,
    canonical_skill: Path = CANONICAL_SKILL,
    skill_candidates: Iterable[Path] = DEFAULT_SKILL_CANDIDATES,
    log_candidates: Iterable[Path] = DEFAULT_LOG_CANDIDATES,
    receipt_store: Path | None = None,
    signal_root: Path | None = None,
) -> SessionEndAudit:
    """Return proof state without modifying skills, logs, receipts, or signals."""

    findings: list[AuditFinding] = []
    canonical_hash = _file_hash(canonical_skill)
    if canonical_hash is None:
        findings.append(
            AuditFinding(
                "canonical_skill",
                "fail",
                "the repository session-end skill is missing",
                str(canonical_skill),
            )
        )
    else:
        findings.append(
            AuditFinding(
                "canonical_skill",
                "pass",
                "the canonical session-end skill exists",
                f"{canonical_skill} sha256={canonical_hash}",
            )
        )
    findings.extend(_installed_skill_findings(skill_candidates, canonical_hash))
    findings.append(_log_finding(log_candidates))

    receipts_path = receipt_store or Path.home() / "kb/metrics/kb-effectiveness.jsonl"
    try:
        stored_receipts = load_receipts(receipts_path)
    except ReceiptError as exc:
        raise SessionEndAuditError(f"invalid effectiveness receipt store: {exc}") from exc
    receipt = _latest_builder_opencode_receipt(stored_receipts)
    if receipt is None:
        findings.append(
            AuditFinding(
                "builder_opencode_receipt",
                "fail",
                "no validated Builder-owned OpenCode effectiveness receipt was found",
                str(receipts_path),
            )
        )
    else:
        findings.append(
            AuditFinding(
                "builder_opencode_receipt",
                "pass",
                "a hash-chain-validated Builder-owned OpenCode receipt exists",
                f"{receipts_path} session={receipt.get('session_id')}",
            )
        )
        findings.append(_receipt_completeness_finding(receipt))

    signals_path = signal_root or Path.home() / "kb/workflow-signals"
    try:
        signals = load_signals(signals_path)
    except SignalError as exc:
        raise SessionEndAuditError(f"invalid workflow-signal store: {exc}") from exc
    matching_signal = _matching_session_signal(signals, receipt)
    if receipt is None:
        findings.append(
            AuditFinding(
                "workflow_signal",
                "fail",
                "a workflow signal cannot be attributed without a Builder-owned OpenCode receipt",
                str(signals_path),
            )
        )
    elif matching_signal is None:
        findings.append(
            AuditFinding(
                "workflow_signal",
                "fail",
                "no validated workflow signal records the effectiveness failure for the same session",
                f"{signals_path} source_session={receipt.get('session_id')}",
            )
        )
    else:
        findings.append(
            AuditFinding(
                "workflow_signal",
                "pass",
                "a validated workflow signal records the Builder effectiveness failure for the same session",
                f"{matching_signal.get('id')} {matching_signal.get('stable_key')}",
            )
        )

    required_checks = {
        "canonical_skill",
        "builder_opencode_receipt",
        "receipt_completeness",
        "workflow_signal",
    }
    failed = {
        item.check
        for item in findings
        if item.status == "fail" and item.check in required_checks
    }
    return SessionEndAudit(
        status="verified" if not failed else "unverified",
        findings=tuple(findings),
        latest_receipt=receipt,
        matching_signal=matching_signal,
    )


def _receipt_completeness_finding(receipt: dict[str, Any]) -> AuditFinding:
    missing = [key for key in _REQUIRED_CAMPAIGN_MEASUREMENTS if receipt.get(key) is None]
    identity_missing = [
        key
        for key in ("initiative_id", "packet_id", "result_id")
        if receipt.get(key) is None
    ]
    notes = str(receipt.get("notes") or "").casefold()
    model_evidence = "model" in notes and "provider" in notes
    pieces: list[str] = []
    if missing:
        pieces.append(f"measurements missing: {', '.join(missing)}")
    if identity_missing:
        pieces.append(f"Builder identity missing: {', '.join(identity_missing)}")
    if not model_evidence:
        pieces.append("notes contain no explicit model and provider evidence")
    if pieces:
        return AuditFinding(
            "receipt_completeness",
            "fail",
            "; ".join(pieces),
            f"session={receipt.get('session_id')}",
        )
    return AuditFinding(
        "receipt_completeness",
        "pass",
        "receipt includes campaign economics, Builder identity, and explicit model/provider evidence",
        f"session={receipt.get('session_id')}",
    )


def _installed_skill_findings(
    candidates: Iterable[Path], canonical_hash: str | None
) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    for path in candidates:
        digest = _file_hash(path)
        if digest is None:
            continue
        if canonical_hash is not None and digest == canonical_hash:
            findings.append(
                AuditFinding(
                    "installed_skill_copy",
                    "pass",
                    "an installed session-end copy matches the repository authority",
                    f"{path} sha256={digest}",
                )
            )
        else:
            findings.append(
                AuditFinding(
                    "installed_skill_copy",
                    "warn",
                    "an installed session-end copy diverges from the repository authority",
                    f"{path} sha256={digest}",
                )
            )
    if not findings:
        findings.append(
            AuditFinding(
                "installed_skill_copy",
                "info",
                "no global copy was found; OpenCode may load the repository .agents skill",
                None,
            )
        )
    return findings


def _log_finding(candidates: Iterable[Path]) -> AuditFinding:
    inspected: list[str] = []
    for path in _candidate_log_files(candidates):
        inspected.append(str(path))
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as exc:
            inspected[-1] += f" (unreadable: {exc})"
            continue
        for raw_line in lines:
            line = raw_line.casefold()
            if "session-end" not in line and "session_end" not in line:
                continue
            if any(term in line for term in _LOG_NEGATIVE_TERMS):
                continue
            if any(term in line for term in _LOG_POSITIVE_TERMS):
                return AuditFinding(
                    "opencode_skill_log",
                    "pass",
                    "OpenCode log evidence shows session-end discovery or invocation",
                    f"{path}: {raw_line.strip()[:240]}",
                )
    return AuditFinding(
        "opencode_skill_log",
        "warn",
        "no inspected OpenCode log proves discovery or invocation; validated outputs remain the execution gate",
        ", ".join(inspected) if inspected else "no candidate log exists",
    )


def _candidate_log_files(candidates: Iterable[Path]) -> list[Path]:
    files: set[Path] = set()
    for path in candidates:
        if path.is_file():
            files.add(path)
        elif path.is_dir():
            files.update(item for item in path.rglob("*.log") if item.is_file())
    return sorted(files)


def _latest_builder_opencode_receipt(
    stored_receipts: Iterable[dict[str, Any]],
) -> dict[str, Any] | None:
    matches = [
        item["receipt"]
        for item in stored_receipts
        if item["receipt"].get("execution_owner") == "builder"
        and str(item["receipt"].get("tool") or "").casefold() == "opencode"
    ]
    if not matches:
        return None
    return max(matches, key=lambda item: str(item.get("recorded_at") or ""))


def _matching_session_signal(
    signals: Iterable[dict[str, Any]], receipt: dict[str, Any] | None
) -> dict[str, Any] | None:
    if receipt is None:
        return None
    session_id = receipt.get("session_id")
    matches: list[dict[str, Any]] = []
    for signal in signals:
        if signal.get("source_session") != session_id:
            continue
        category = str(signal.get("category") or "")
        searchable = " ".join(
            str(signal.get(key) or "")
            for key in ("stable_key", "summary", "evidence", "impact", "suggested_change")
        ).casefold()
        if category in _RELEVANT_SIGNAL_CATEGORIES and "builder" in searchable and any(
            term in searchable
            for term in ("slow", "throughput", "metadata", "packet", "24 hour", "24-hour")
        ):
            matches.append(signal)
    if not matches:
        return None
    return max(matches, key=lambda item: str(item.get("recorded_at") or ""))


def _file_hash(path: Path) -> str | None:
    try:
        data = path.read_bytes()
    except OSError:
        return None
    return hashlib.sha256(data).hexdigest()


__all__ = [
    "AuditFinding",
    "SessionEndAudit",
    "SessionEndAuditError",
    "audit_session_end",
]
