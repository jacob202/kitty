"""Read-only proof that OpenCode actually loaded and executed session-end.

A skill file existing in the repository is not execution evidence.  This audit
checks four independent layers: discoverability/log evidence, a Builder-owned
OpenCode effectiveness receipt, the measurements that receipt was required to
capture, and a workflow signal for an economically bad campaign.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

from gateway.paths import ROOT

CANONICAL_SKILL = ROOT / ".agents/skills/session-end/SKILL.md"
DEFAULT_SKILL_CANDIDATES = (
    Path.home() / ".config/opencode/skills/session-end/SKILL.md",
    Path.home() / ".agents/skills/session-end/SKILL.md",
    Path.home() / ".claude/skills/session-end/SKILL.md",
)
DEFAULT_LOG_CANDIDATES = (
    Path.home() / ".local/share/opencode/log/opencode.log",
    Path.home() / ".cache/opencode/opencode.log",
    Path.home() / ".config/opencode/opencode.log",
    Path.home() / "Library/Logs/opencode.log",
    ROOT / "opencode.log",
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


class SessionEndAuditError(ValueError):
    """The audit source exists but is corrupt or cannot support a claim."""


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

    installed = _installed_skill_findings(skill_candidates, canonical_hash)
    findings.extend(installed)
    log_finding = _log_finding(log_candidates)
    findings.append(log_finding)

    receipts_path = receipt_store or (
        Path.home() / "kb/metrics/kb-effectiveness.jsonl"
    )
    receipts = _load_receipts(receipts_path)
    receipt = _latest_builder_opencode_receipt(receipts)
    if receipt is None:
        findings.append(
            AuditFinding(
                "builder_opencode_receipt",
                "fail",
                "no Builder-owned OpenCode effectiveness receipt was found",
                str(receipts_path),
            )
        )
    else:
        findings.append(
            AuditFinding(
                "builder_opencode_receipt",
                "pass",
                "a Builder-owned OpenCode effectiveness receipt exists",
                f"{receipts_path} session={receipt.get('session_id')}",
            )
        )
        missing = [key for key in _REQUIRED_CAMPAIGN_MEASUREMENTS if receipt.get(key) is None]
        identity_missing = [
            key
            for key in ("initiative_id", "packet_id", "result_id")
            if receipt.get(key) is None
        ]
        notes = str(receipt.get("notes") or "").casefold()
        model_evidence = "model" in notes and (
            "deepseek" in notes or "provider" in notes or "openrouter" in notes
        )
        if missing or identity_missing or not model_evidence:
            pieces = []
            if missing:
                pieces.append(f"measurements missing: {', '.join(missing)}")
            if identity_missing:
                pieces.append(f"Builder identity missing: {', '.join(identity_missing)}")
            if not model_evidence:
                pieces.append("notes contain no model/provider evidence")
            findings.append(
                AuditFinding(
                    "receipt_completeness",
                    "fail",
                    "; ".join(pieces),
                    f"session={receipt.get('session_id')}",
                )
            )
        else:
            findings.append(
                AuditFinding(
                    "receipt_completeness",
                    "pass",
                    "receipt includes campaign economics, Builder identity, and model/provider evidence",
                    f"session={receipt.get('session_id')}",
                )
            )

    signals_path = signal_root or (Path.home() / "kb/workflow-signals")
    signals = _load_signals(signals_path)
    matching_signal = _latest_builder_effectiveness_signal(signals)
    if matching_signal is None:
        findings.append(
            AuditFinding(
                "workflow_signal",
                "fail",
                "no workflow signal records the slow or metadata-heavy Builder campaign",
                str(signals_path),
            )
        )
    else:
        findings.append(
            AuditFinding(
                "workflow_signal",
                "pass",
                "a workflow signal records the Builder effectiveness failure",
                f"{matching_signal.get('id')} {matching_signal.get('stable_key')}",
            )
        )

    # A log mention is useful evidence of discovery, but execution requires the
    # receipt and signal.  Global skill copies are optional because OpenCode may
    # load the repository's .agents skill directly.
    required_checks = {
        "canonical_skill",
        "opencode_skill_log",
        "builder_opencode_receipt",
        "receipt_completeness",
        "workflow_signal",
    }
    failed = {
        item.check
        for item in findings
        if item.status == "fail" and item.check in required_checks
    }
    status = "verified" if not failed else "unverified"
    return SessionEndAudit(
        status=status,
        findings=tuple(findings),
        latest_receipt=receipt,
        matching_signal=matching_signal,
    )


def _installed_skill_findings(
    candidates: Iterable[Path], canonical_hash: str | None
) -> list[AuditFinding]:
    found: list[AuditFinding] = []
    for path in candidates:
        digest = _file_hash(path)
        if digest is None:
            continue
        if canonical_hash is not None and digest == canonical_hash:
            found.append(
                AuditFinding(
                    "installed_skill_copy",
                    "pass",
                    "an installed session-end copy matches the repository authority",
                    f"{path} sha256={digest}",
                )
            )
        else:
            found.append(
                AuditFinding(
                    "installed_skill_copy",
                    "warn",
                    "an installed session-end copy diverges from the repository authority",
                    f"{path} sha256={digest}",
                )
            )
    if not found:
        found.append(
            AuditFinding(
                "installed_skill_copy",
                "info",
                "no global copy was found; OpenCode may still load the repository .agents skill",
                None,
            )
        )
    return found


def _log_finding(candidates: Iterable[Path]) -> AuditFinding:
    inspected: list[str] = []
    for path in candidates:
        if not path.is_file():
            continue
        inspected.append(str(path))
        try:
            text = path.read_text(encoding="utf-8", errors="replace").casefold()
        except OSError as exc:
            inspected[-1] += f" (unreadable: {exc})"
            continue
        if "session-end" in text or "session_end" in text:
            return AuditFinding(
                "opencode_skill_log",
                "pass",
                "OpenCode log evidence mentions session-end",
                str(path),
            )
    return AuditFinding(
        "opencode_skill_log",
        "fail",
        "no inspected OpenCode log proves that session-end was discovered or invoked",
        ", ".join(inspected) if inspected else "no candidate log exists",
    )


def _load_receipts(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    if not path.is_file():
        raise SessionEndAuditError(f"receipt store is not a file: {path}")
    receipts: list[dict[str, Any]] = []
    for line_no, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw_line.strip():
            raise SessionEndAuditError(f"blank receipt line at {path}:{line_no}")
        try:
            item = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            raise SessionEndAuditError(
                f"invalid receipt JSON at {path}:{line_no}: {exc}"
            ) from exc
        receipt = item.get("receipt") if isinstance(item, dict) else None
        if not isinstance(receipt, dict):
            raise SessionEndAuditError(f"receipt payload missing at {path}:{line_no}")
        receipts.append(receipt)
    return receipts


def _latest_builder_opencode_receipt(
    receipts: Iterable[dict[str, Any]],
) -> dict[str, Any] | None:
    matches = [
        receipt
        for receipt in receipts
        if str(receipt.get("tool") or "").casefold() == "opencode"
        and receipt.get("execution_owner") == "builder"
    ]
    if not matches:
        return None
    return max(matches, key=lambda item: str(item.get("recorded_at") or ""))


def _load_signals(root: Path) -> list[dict[str, Any]]:
    if not root.exists():
        return []
    if not root.is_dir():
        raise SessionEndAuditError(f"workflow signal store is not a directory: {root}")
    signals: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SessionEndAuditError(f"invalid workflow signal {path}: {exc}") from exc
        if not isinstance(payload, dict):
            raise SessionEndAuditError(f"workflow signal must be an object: {path}")
        signals.append(payload)
    return signals


def _latest_builder_effectiveness_signal(
    signals: Iterable[dict[str, Any]],
) -> dict[str, Any] | None:
    matches: list[dict[str, Any]] = []
    for signal in signals:
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
