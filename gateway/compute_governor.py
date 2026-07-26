"""Compute governor — stop paying twice for work that has not changed.

The failure this exists to prevent: an agent plans a task, reviews the plan,
reviews the review, re-audits the same tree, and re-runs all of it on the next
wake-up, while the artifact and the head SHA are byte-identical to last time.
None of those passes is individually wrong, so nothing stops them.

The governor is a decision seam in front of dispatch, not a scheduler:

* every dispatch must declare a concrete artifact, acceptance tests, allowed
  scope, exclusions, risk class, and a stopping condition;
* one planning pass and one independent review are permitted per unchanged
  ``(task_type, subject_ref, head_sha)``, recorded as a durable receipt;
* a changed head SHA, changed requirements, or an explicit human override
  reauthorizes the work — nothing else does;
* routine work routes to the cheapest configured model, and a frontier route
  needs a stated, verified reason.

Model routing policy itself lives in ADR 0021 and `docs/FREE_WORKERS.md`; this
module decides *whether* to spend and at what tier, then defers to the existing
ladder for which model that means.

Usage is a **local estimate** derived from Kitty's own token ledger. It is not
a provider meter and must never be presented as one.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from gateway.paths import COMPUTE_GOVERNOR_DB

# Dispatch classes the governor understands. A planning pass and an independent
# review are separately budgeted; implementation is gated by the same receipt
# rule so a rerun on an unchanged SHA is also caught.
TASK_TYPES = frozenset({"plan", "review", "implement"})

# Work whose output is another opinion rather than a changed artifact. Declaring
# one of these is a rejection, not a downgrade: there is no cheap way to do work
# that should not happen.
REJECTED_WORK_KINDS: dict[str, str] = {
    "analysis_only": "produces no artifact change; write the finding into an existing doc instead",
    "prompt_polishing": "rewriting instructions is not delivery",
    "repeat_audit": "a broad re-audit of unchanged code repeats a finished pass",
    "review_of_review": "reviewing a review adds an opinion, not evidence",
    "duplicate_packet": "the same packet already exists; execute it or amend it",
    "speculative_cleanup": "cleanup without a named defect is unbounded scope",
}

ACCEPTED_WORK_KINDS = frozenset({
    "implementation",
    "verified_repair",
    "planning_pass",
    "independent_review",
})

RISK_CLASSES = frozenset({"routine", "risky", "blocker"})

# Only these justify a frontier model. Everything else is routine by default.
_FRONTIER_RISK_CLASSES = frozenset({"risky", "blocker"})

ROUTE_FREE = "free"
ROUTE_FRONTIER = "frontier"

ACTION_RUN = "run"
ACTION_DEFER = "defer"
ACTION_DOWNGRADE = "downgrade"
ACTION_REJECT = "reject"

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS work_receipts (
    receipt_id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_type TEXT NOT NULL,
    subject_ref TEXT NOT NULL,
    head_sha TEXT NOT NULL,
    dispatch_hash TEXT NOT NULL,
    work_kind TEXT NOT NULL,
    risk_class TEXT NOT NULL,
    route TEXT NOT NULL,
    model TEXT,
    provider TEXT,
    outcome TEXT NOT NULL,
    retries INTEGER NOT NULL DEFAULT 0,
    estimated_usage_cad REAL NOT NULL DEFAULT 0.0,
    override_reason TEXT,
    created_at TEXT NOT NULL
);

-- One completed pass per task type per unchanged subject+SHA. A retry that
-- ended in failure does not consume the allowance; a settled pass does.
CREATE UNIQUE INDEX IF NOT EXISTS idx_receipts_settled_pass
    ON work_receipts(task_type, subject_ref, head_sha)
    WHERE outcome = 'settled';

CREATE INDEX IF NOT EXISTS idx_receipts_created ON work_receipts(created_at);
"""

# Outcomes. Only 'settled' consumes the per-SHA allowance; a failed or abandoned
# pass leaves the work still owed, which is the honest reading.
OUTCOME_SETTLED = "settled"
OUTCOME_FAILED = "failed"
OUTCOME_ABANDONED = "abandoned"
_OUTCOMES = frozenset({OUTCOME_SETTLED, OUTCOME_FAILED, OUTCOME_ABANDONED})


class GovernorError(RuntimeError):
    """Raised when the governor cannot make an honest decision."""


@dataclass(frozen=True)
class Dispatch:
    """A proposed unit of agent work, fully described before it is paid for."""

    task_type: str
    work_kind: str
    subject_ref: str
    head_sha: str
    artifact: str
    acceptance_tests: tuple[str, ...]
    allowed_scope: tuple[str, ...]
    exclusions: tuple[str, ...]
    risk_class: str
    stopping_condition: str
    blocker_evidence: str | None = None

    def fingerprint(self) -> str:
        """Stable hash of everything that would change the work itself.

        Excludes ``blocker_evidence``: naming a new reason to escalate must not
        by itself look like a changed requirement.
        """
        payload = json.dumps(
            {
                "task_type": self.task_type,
                "work_kind": self.work_kind,
                "subject_ref": self.subject_ref,
                "head_sha": self.head_sha,
                "artifact": self.artifact,
                "acceptance_tests": sorted(self.acceptance_tests),
                "allowed_scope": sorted(self.allowed_scope),
                "exclusions": sorted(self.exclusions),
                "risk_class": self.risk_class,
                "stopping_condition": self.stopping_condition,
            },
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ReserveState:
    """What is left to spend this week, and the floors that protect it.

    ``estimated_spend_cad`` is Kitty's own arithmetic over its token ledger. It
    is not the provider's meter.
    """

    weekly_budget_cad: float
    estimated_spend_cad: float
    frontier_floor_ratio: float = 0.25
    hard_floor_ratio: float = 0.05

    @property
    def remaining_cad(self) -> float:
        return self.weekly_budget_cad - self.estimated_spend_cad

    @property
    def remaining_ratio(self) -> float:
        if self.weekly_budget_cad <= 0:
            raise GovernorError("weekly_budget_cad must be positive to compute a reserve ratio")
        return self.remaining_cad / self.weekly_budget_cad


@dataclass(frozen=True)
class Decision:
    """Why a dispatch would run, defer, downgrade, or be rejected."""

    action: str
    route: str | None
    reasons: tuple[str, ...]
    dispatch_hash: str
    errors: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "route": self.route,
            "reasons": list(self.reasons),
            "dispatch_hash": self.dispatch_hash,
            "errors": list(self.errors),
        }


def validate_dispatch(dispatch: Dispatch) -> list[str]:
    """Return every reason this dispatch is not concrete enough to pay for."""
    errors: list[str] = []
    if dispatch.task_type not in TASK_TYPES:
        errors.append(f"task_type must be one of {sorted(TASK_TYPES)}, got {dispatch.task_type!r}")
    if dispatch.risk_class not in RISK_CLASSES:
        errors.append(f"risk_class must be one of {sorted(RISK_CLASSES)}, got {dispatch.risk_class!r}")
    if dispatch.work_kind not in ACCEPTED_WORK_KINDS and dispatch.work_kind not in REJECTED_WORK_KINDS:
        errors.append(
            f"work_kind {dispatch.work_kind!r} is not declared; accepted kinds are "
            f"{sorted(ACCEPTED_WORK_KINDS)}"
        )
    for name in ("subject_ref", "head_sha", "artifact", "stopping_condition"):
        value = getattr(dispatch, name)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{name} is required and must be a non-empty string")
    for name in ("acceptance_tests", "allowed_scope"):
        value = getattr(dispatch, name)
        if not value or not all(isinstance(item, str) and item.strip() for item in value):
            errors.append(f"{name} must name at least one non-empty entry")
    if dispatch.exclusions and not all(isinstance(i, str) and i.strip() for i in dispatch.exclusions):
        errors.append("exclusions entries must be non-empty strings")
    if dispatch.risk_class == "blocker" and not (dispatch.blocker_evidence or "").strip():
        errors.append("risk_class 'blocker' requires blocker_evidence naming the verified failure")
    return errors


def connect(db_path: Path | str = COMPUTE_GOVERNOR_DB) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: Path | str = COMPUTE_GOVERNOR_DB) -> None:
    with connect(db_path) as conn:
        conn.executescript(_SCHEMA_SQL)


def find_settled_receipt(
    db_path: Path | str,
    *,
    task_type: str,
    subject_ref: str,
    head_sha: str,
) -> dict[str, Any] | None:
    """Return the settled pass for this exact subject and SHA, if one exists."""
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM work_receipts WHERE task_type = ? AND subject_ref = ? "
            "AND head_sha = ? AND outcome = ? LIMIT 1",
            (task_type, subject_ref, head_sha, OUTCOME_SETTLED),
        ).fetchone()
    return dict(row) if row else None


def count_retries(
    db_path: Path | str,
    *,
    task_type: str,
    subject_ref: str,
    head_sha: str,
) -> int:
    """Total recorded retries across every attempt at this subject and SHA."""
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(retries), 0) AS total, COUNT(*) AS attempts "
            "FROM work_receipts WHERE task_type = ? AND subject_ref = ? AND head_sha = ?",
            (task_type, subject_ref, head_sha),
        ).fetchone()
    return int(row["total"]) + max(int(row["attempts"]) - 1, 0)


def record_receipt(
    db_path: Path | str,
    dispatch: Dispatch,
    *,
    outcome: str,
    route: str,
    model: str | None = None,
    provider: str | None = None,
    retries: int = 0,
    estimated_usage_cad: float = 0.0,
    override_reason: str | None = None,
    now: datetime | None = None,
) -> int:
    """Persist what was actually spent. Raises on a duplicate settled pass."""
    if outcome not in _OUTCOMES:
        raise GovernorError(f"outcome must be one of {sorted(_OUTCOMES)}, got {outcome!r}")
    if retries < 0:
        raise GovernorError("retries must not be negative")
    stamp = (now or datetime.now(timezone.utc)).isoformat()
    with connect(db_path) as conn:
        try:
            cursor = conn.execute(
                "INSERT INTO work_receipts (task_type, subject_ref, head_sha, dispatch_hash, "
                "work_kind, risk_class, route, model, provider, outcome, retries, "
                "estimated_usage_cad, override_reason, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    dispatch.task_type,
                    dispatch.subject_ref,
                    dispatch.head_sha,
                    dispatch.fingerprint(),
                    dispatch.work_kind,
                    dispatch.risk_class,
                    route,
                    model,
                    provider,
                    outcome,
                    retries,
                    estimated_usage_cad,
                    override_reason,
                    stamp,
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise GovernorError(
                f"a settled {dispatch.task_type} pass already exists for "
                f"{dispatch.subject_ref} at {dispatch.head_sha}; nothing changed, so nothing is owed"
            ) from exc
    return int(cursor.lastrowid)


def decide(
    db_path: Path | str,
    dispatch: Dispatch,
    *,
    reserve: ReserveState,
    override_reason: str | None = None,
) -> Decision:
    """Decide whether to spend on this dispatch, and explain why either way.

    Pure and read-only: the same call is the dry-run explainer and the gate.
    """
    fingerprint = dispatch.fingerprint()

    errors = validate_dispatch(dispatch)
    if errors:
        return Decision(
            action=ACTION_REJECT,
            route=None,
            reasons=("dispatch is not concrete enough to authorize",),
            dispatch_hash=fingerprint,
            errors=tuple(errors),
        )

    if dispatch.work_kind in REJECTED_WORK_KINDS:
        return Decision(
            action=ACTION_REJECT,
            route=None,
            reasons=(f"{dispatch.work_kind}: {REJECTED_WORK_KINDS[dispatch.work_kind]}",),
            dispatch_hash=fingerprint,
        )

    settled = find_settled_receipt(
        db_path,
        task_type=dispatch.task_type,
        subject_ref=dispatch.subject_ref,
        head_sha=dispatch.head_sha,
    )
    if settled is not None:
        if not (override_reason or "").strip():
            return Decision(
                action=ACTION_REJECT,
                route=None,
                reasons=(
                    f"a {dispatch.task_type} pass settled on {dispatch.subject_ref} at "
                    f"{dispatch.head_sha[:12]} on {settled['created_at']}",
                    "nothing changed since: push a commit, change the requirements, or override",
                ),
                dispatch_hash=fingerprint,
            )
        reasons: list[str] = [f"human override: {override_reason.strip()}"]
    else:
        reasons = [
            f"no settled {dispatch.task_type} pass for {dispatch.subject_ref} at "
            f"{dispatch.head_sha[:12]}"
        ]

    wants_frontier = dispatch.risk_class in _FRONTIER_RISK_CLASSES
    if not wants_frontier:
        reasons.append("routine risk class routes to the cheapest configured model")
        return Decision(
            action=ACTION_RUN,
            route=ROUTE_FREE,
            reasons=tuple(reasons),
            dispatch_hash=fingerprint,
        )

    reasons.append(
        f"risk class {dispatch.risk_class!r} justifies a frontier route"
        + (f": {dispatch.blocker_evidence.strip()}" if dispatch.blocker_evidence else "")
    )

    remaining_ratio = reserve.remaining_ratio
    if remaining_ratio <= reserve.hard_floor_ratio:
        reasons.append(
            f"estimated reserve {remaining_ratio:.0%} is at or below the hard floor "
            f"{reserve.hard_floor_ratio:.0%}; deferring rather than spending the last of it"
        )
        return Decision(
            action=ACTION_DEFER,
            route=None,
            reasons=tuple(reasons),
            dispatch_hash=fingerprint,
        )
    if remaining_ratio <= reserve.frontier_floor_ratio:
        reasons.append(
            f"estimated reserve {remaining_ratio:.0%} is at or below the frontier floor "
            f"{reserve.frontier_floor_ratio:.0%}; downgrading to the free route"
        )
        return Decision(
            action=ACTION_DOWNGRADE,
            route=ROUTE_FREE,
            reasons=tuple(reasons),
            dispatch_hash=fingerprint,
        )

    reasons.append(f"estimated reserve {remaining_ratio:.0%} is above the frontier floor")
    return Decision(
        action=ACTION_RUN,
        route=ROUTE_FRONTIER,
        reasons=tuple(reasons),
        dispatch_hash=fingerprint,
    )


def _week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


def weekly_ledger(
    db_path: Path | str,
    *,
    week_of: date | None = None,
) -> dict[str, Any]:
    """Local weekly rollup of what agent work cost, by run type and model.

    ``estimated_usage_cad`` is Kitty's own arithmetic over its token ledger. It
    is an estimate and is labelled as one; it is not a provider invoice.
    """
    start = _week_start(week_of or datetime.now(timezone.utc).date())
    end = start + timedelta(days=7)
    with connect(db_path) as conn:
        rows = conn.execute(
            "SELECT task_type, work_kind, route, model, provider, subject_ref, head_sha, "
            "outcome, retries, estimated_usage_cad, created_at FROM work_receipts "
            "WHERE created_at >= ? AND created_at < ? ORDER BY created_at",
            (start.isoformat(), end.isoformat()),
        ).fetchall()

    entries = [dict(row) for row in rows]
    by_route: dict[str, float] = {}
    for entry in entries:
        by_route[entry["route"]] = by_route.get(entry["route"], 0.0) + float(entry["estimated_usage_cad"])
    return {
        "week_start": start.isoformat(),
        "week_end": end.isoformat(),
        "basis": "local estimate from Kitty's own token ledger — NOT a provider meter",
        "runs": len(entries),
        "retries": sum(int(entry["retries"]) for entry in entries),
        "estimated_usage_cad": round(sum(float(e["estimated_usage_cad"]) for e in entries), 4),
        "estimated_usage_cad_by_route": {k: round(v, 4) for k, v in sorted(by_route.items())},
        "entries": entries,
    }


DEFAULT_RESERVE_CONFIG: dict[str, float] = {
    "weekly_budget_cad": 20.0,
    "frontier_floor_ratio": 0.25,
    "hard_floor_ratio": 0.05,
}


def load_reserve_config(config_path: Path | str) -> dict[str, float]:
    """Read reserve thresholds. A malformed file fails loud rather than defaulting."""
    path = Path(config_path)
    if not path.exists():
        return dict(DEFAULT_RESERVE_CONFIG)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise GovernorError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise GovernorError(f"{path} must contain a JSON object")
    config = dict(DEFAULT_RESERVE_CONFIG)
    for key in DEFAULT_RESERVE_CONFIG:
        if key not in payload:
            continue
        value = payload[key]
        if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
            raise GovernorError(f"{path}:{key} must be a positive number, got {value!r}")
        config[key] = float(value)
    if config["hard_floor_ratio"] >= config["frontier_floor_ratio"]:
        raise GovernorError(
            f"{path}: hard_floor_ratio must sit below frontier_floor_ratio "
            f"({config['hard_floor_ratio']} >= {config['frontier_floor_ratio']})"
        )
    return config


def reserve_from_ledger(
    db_path: Path | str,
    config: dict[str, float],
    *,
    week_of: date | None = None,
) -> ReserveState:
    """Build the reserve from what this week's receipts already estimate spent."""
    ledger = weekly_ledger(db_path, week_of=week_of)
    return ReserveState(
        weekly_budget_cad=config["weekly_budget_cad"],
        estimated_spend_cad=float(ledger["estimated_usage_cad"]),
        frontier_floor_ratio=config["frontier_floor_ratio"],
        hard_floor_ratio=config["hard_floor_ratio"],
    )


def dispatch_from_mapping(payload: dict[str, Any]) -> Dispatch:
    """Build a Dispatch from JSON. Missing fields fail loud, not silently."""
    if not isinstance(payload, dict):
        raise GovernorError("dispatch payload must be a JSON object")

    def _tuple(name: str) -> tuple[str, ...]:
        value = payload.get(name, [])
        if isinstance(value, str) or not isinstance(value, Iterable):
            raise GovernorError(f"{name} must be a list of strings")
        return tuple(str(item) for item in value)

    missing = [k for k in ("task_type", "work_kind", "subject_ref", "head_sha") if not payload.get(k)]
    if missing:
        raise GovernorError(f"dispatch payload is missing required keys: {sorted(missing)}")
    return Dispatch(
        task_type=str(payload["task_type"]),
        work_kind=str(payload["work_kind"]),
        subject_ref=str(payload["subject_ref"]),
        head_sha=str(payload["head_sha"]),
        artifact=str(payload.get("artifact", "")),
        acceptance_tests=_tuple("acceptance_tests"),
        allowed_scope=_tuple("allowed_scope"),
        exclusions=_tuple("exclusions"),
        risk_class=str(payload.get("risk_class", "")),
        stopping_condition=str(payload.get("stopping_condition", "")),
        blocker_evidence=payload.get("blocker_evidence"),
    )


def explain(decision: Decision) -> str:
    """Human-readable dry-run explanation."""
    lines = [f"{decision.action.upper()}" + (f" via {decision.route}" if decision.route else "")]
    lines.extend(f"  - {reason}" for reason in decision.reasons)
    if decision.errors:
        lines.append("  missing from the dispatch:")
        lines.extend(f"    - {error}" for error in decision.errors)
    return "\n".join(lines)


def summarize_receipts(entries: Sequence[dict[str, Any]]) -> str:
    """One line per receipt, for CLI listing."""
    return "\n".join(
        f"{e['created_at']}  {e['task_type']:<9} {e['outcome']:<9} {e['route']:<8} "
        f"{e['subject_ref']}@{str(e['head_sha'])[:12]}  retries={e['retries']}"
        for e in entries
    )
