"""KittyBuilder KB-S2 — packet attempts: context bundles + result contracts.

An *attempt* is one execution try for an initiative packet. Each attempt
carries a bounded context bundle (packet objective/criteria/paths plus
truncated summaries of prior attempts) built at start time and persisted, so
retries see what attempt N-1 did and why it failed even across restarts.

Attempts record two structured contracts: the implementation result (from the
worker) and the review result (from an independent reviewer). Both are
validated with hard size caps on every free-text field — a worker cannot blow
up the durable store or the next attempt's context with an unbounded dump.

Scope boundaries (KB-S2): storage and validation only. No worker execution,
no repair-loop driving (KB-S3), no push/PR (KB-S4). The queue task state
machine is untouched; attempts are rows in the same DB keyed to the packet's
task, with audit entries in the existing append-only events table.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from gateway import builder_initiative as bi
from gateway import builder_queue as bq

BUNDLE_VERSION = 1
CONTRACT_VERSION = 1

# ponytail: fixed caps, no config. Raise them in code if a real packet needs it.
DEFAULT_MAX_ATTEMPTS = 2
PRIOR_ATTEMPT_WINDOW = 3
SUMMARY_CAP = 4000
OUTPUT_CAP = 8000
NOTE_CAP = 2000
CLAIM_CAP = 1000
MAX_CLAIMS = 20
MAX_FINDINGS = 50

ATTEMPT_SUCCEEDED = "succeeded"
ATTEMPT_FAILED = "failed"
ATTEMPT_ABORTED = "aborted"
_OUTCOMES = frozenset({ATTEMPT_SUCCEEDED, ATTEMPT_FAILED, ATTEMPT_ABORTED})

_IMPL_STATUSES = frozenset({"completed", "failed", "aborted"})
_REVIEW_VERDICTS = frozenset({"approve", "request_changes", "reject"})
_FINDING_SEVERITIES = frozenset({"critical", "major", "minor"})

_IMPL_KEYS = frozenset(
    {"contract_version", "status", "summary", "diff_summary", "validation", "claims"}
)
_VALIDATION_KEYS = frozenset({"passed", "output"})
_REVIEW_KEYS = frozenset({"contract_version", "verdict", "summary", "findings"})
_FINDING_KEYS = frozenset({"severity", "note"})


class AttemptError(ValueError):
    """Base error for attempt operations."""


class AttemptNotFoundError(AttemptError):
    """Raised when an attempt ID does not exist."""


class AttemptLimitError(AttemptError):
    """Raised when the packet's max_attempts budget is exhausted."""


class AttemptStateError(AttemptError):
    """Raised on operations illegal for the attempt's current state."""


class ResultContractError(ValueError):
    """Raised when a result payload fails contract validation."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS packet_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    initiative_id TEXT NOT NULL,
    packet_id TEXT NOT NULL,
    attempt_no INTEGER NOT NULL,
    task_id TEXT NOT NULL,
    bundle_json TEXT NOT NULL,
    implementation_json TEXT,
    review_json TEXT,
    outcome TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (initiative_id, packet_id, attempt_no),
    FOREIGN KEY (initiative_id, packet_id)
        REFERENCES initiative_packets(initiative_id, packet_id),
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);
"""


def init_db(db_path: Path | None = None) -> None:
    """Ensure initiative schema plus the attempts table exist. Idempotent."""
    bi.init_db(db_path)
    conn = bq.connect(db_path)
    try:
        conn.executescript(_SCHEMA_SQL)
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Result contract validation
# ---------------------------------------------------------------------------


def _check_capped_str(
    value: Any, label: str, cap: int, errors: list[str], *, required: bool
) -> None:
    if value is None:
        if required:
            errors.append(f"{label} is required and must be a non-empty string")
        return
    if not isinstance(value, str) or (required and not value.strip()):
        errors.append(f"{label} must be a non-empty string")
        return
    if len(value) > cap:
        errors.append(f"{label} exceeds {cap} characters ({len(value)})")


def validate_implementation_result(result: Any) -> list[str]:
    """Validate an implementation-result contract. Empty list = valid."""
    errors: list[str] = []
    if not isinstance(result, dict):
        return ["implementation result must be a JSON object"]
    unknown = set(result) - _IMPL_KEYS
    if unknown:
        errors.append(f"unknown keys: {sorted(unknown)}")
    if result.get("contract_version") != CONTRACT_VERSION:
        errors.append(f"contract_version must be {CONTRACT_VERSION}")
    if result.get("status") not in _IMPL_STATUSES:
        errors.append(f"status must be one of {sorted(_IMPL_STATUSES)}")
    _check_capped_str(result.get("summary"), "summary", SUMMARY_CAP, errors, required=True)
    _check_capped_str(
        result.get("diff_summary"), "diff_summary", SUMMARY_CAP, errors, required=False
    )

    validation = result.get("validation")
    if validation is not None:
        if not isinstance(validation, dict):
            errors.append("validation must be a JSON object")
        else:
            unknown = set(validation) - _VALIDATION_KEYS
            if unknown:
                errors.append(f"validation: unknown keys: {sorted(unknown)}")
            if not isinstance(validation.get("passed"), bool):
                errors.append("validation.passed must be a boolean")
            _check_capped_str(
                validation.get("output"), "validation.output", OUTPUT_CAP,
                errors, required=False,
            )

    claims = result.get("claims")
    if claims is not None:
        if not isinstance(claims, list) or len(claims) > MAX_CLAIMS:
            errors.append(f"claims must be an array of at most {MAX_CLAIMS} strings")
        else:
            for i, claim in enumerate(claims):
                _check_capped_str(claim, f"claims[{i}]", CLAIM_CAP, errors, required=True)
    return errors


def validate_review_result(result: Any) -> list[str]:
    """Validate a review-result contract. Empty list = valid."""
    errors: list[str] = []
    if not isinstance(result, dict):
        return ["review result must be a JSON object"]
    unknown = set(result) - _REVIEW_KEYS
    if unknown:
        errors.append(f"unknown keys: {sorted(unknown)}")
    if result.get("contract_version") != CONTRACT_VERSION:
        errors.append(f"contract_version must be {CONTRACT_VERSION}")
    if result.get("verdict") not in _REVIEW_VERDICTS:
        errors.append(f"verdict must be one of {sorted(_REVIEW_VERDICTS)}")
    _check_capped_str(result.get("summary"), "summary", SUMMARY_CAP, errors, required=True)

    findings = result.get("findings")
    if findings is not None:
        if not isinstance(findings, list) or len(findings) > MAX_FINDINGS:
            errors.append(f"findings must be an array of at most {MAX_FINDINGS} objects")
        else:
            for i, finding in enumerate(findings):
                if not isinstance(finding, dict):
                    errors.append(f"findings[{i}] must be a JSON object")
                    continue
                unknown = set(finding) - _FINDING_KEYS
                if unknown:
                    errors.append(f"findings[{i}]: unknown keys: {sorted(unknown)}")
                if finding.get("severity") not in _FINDING_SEVERITIES:
                    errors.append(
                        f"findings[{i}]: severity must be one of "
                        f"{sorted(_FINDING_SEVERITIES)}"
                    )
                _check_capped_str(
                    finding.get("note"), f"findings[{i}].note", NOTE_CAP,
                    errors, required=True,
                )
    return errors


# ---------------------------------------------------------------------------
# Context bundle
# ---------------------------------------------------------------------------


def _clip(text: str | None, cap: int) -> str | None:
    if text is None or len(text) <= cap:
        return text
    return text[: cap - 12] + " …[clipped]"


def _prior_attempt_summary(row: sqlite3.Row) -> dict[str, Any]:
    """Bounded digest of a closed attempt for the next attempt's bundle."""
    digest: dict[str, Any] = {
        "attempt_no": row["attempt_no"],
        "outcome": row["outcome"],
        "implementation": None,
        "review": None,
    }
    if row["implementation_json"]:
        impl = json.loads(row["implementation_json"])
        digest["implementation"] = {
            "status": impl.get("status"),
            "summary": _clip(impl.get("summary"), NOTE_CAP),
        }
    if row["review_json"]:
        review = json.loads(row["review_json"])
        digest["review"] = {
            "verdict": review.get("verdict"),
            "summary": _clip(review.get("summary"), NOTE_CAP),
        }
    return digest


def _packet_row(
    conn: sqlite3.Connection, initiative_id: str, packet_id: str
) -> sqlite3.Row:
    row = conn.execute(
        """
        SELECT * FROM initiative_packets
        WHERE initiative_id = ? AND packet_id = ?
        """,
        (initiative_id, packet_id),
    ).fetchone()
    if row is None:
        raise AttemptError(f"unknown packet {initiative_id}/{packet_id}")
    return row


def _build_bundle_on_conn(
    conn: sqlite3.Connection,
    packet: sqlite3.Row,
    attempt_no: int,
) -> dict[str, Any]:
    priors = conn.execute(
        """
        SELECT * FROM packet_attempts
        WHERE initiative_id = ? AND packet_id = ? AND outcome IS NOT NULL
        ORDER BY attempt_no DESC LIMIT ?
        """,
        (packet["initiative_id"], packet["packet_id"], PRIOR_ATTEMPT_WINDOW),
    ).fetchall()
    return {
        "bundle_version": BUNDLE_VERSION,
        "initiative_id": packet["initiative_id"],
        "packet_id": packet["packet_id"],
        "task_id": packet["task_id"],
        "attempt_no": attempt_no,
        "objective": packet["objective"],
        "acceptance_criteria": json.loads(packet["acceptance_criteria_json"]),
        "allowed_paths": json.loads(packet["allowed_paths_json"]),
        "policy": json.loads(packet["policy_json"]) if packet["policy_json"] else {},
        "prior_attempts": [
            _prior_attempt_summary(r) for r in reversed(priors)
        ],
    }


def build_context_bundle(
    initiative_id: str, packet_id: str, db_path: Path | None = None
) -> dict[str, Any]:
    """Preview the bundle the NEXT attempt would receive. Read-only."""
    init_db(db_path)
    conn = bq.connect(db_path)
    try:
        packet = _packet_row(conn, initiative_id, packet_id)
        next_no = _attempt_count(conn, initiative_id, packet_id) + 1
        return _build_bundle_on_conn(conn, packet, next_no)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Attempt lifecycle
# ---------------------------------------------------------------------------


def _attempt_count(
    conn: sqlite3.Connection, initiative_id: str, packet_id: str
) -> int:
    row = conn.execute(
        """
        SELECT COUNT(*) FROM packet_attempts
        WHERE initiative_id = ? AND packet_id = ?
        """,
        (initiative_id, packet_id),
    ).fetchone()
    return int(row[0])


def _row_to_attempt(row: sqlite3.Row) -> dict[str, Any]:
    attempt = dict(row)
    for column, key in (
        ("bundle_json", "bundle"),
        ("implementation_json", "implementation"),
        ("review_json", "review"),
    ):
        raw = attempt.get(column)
        attempt[key] = json.loads(raw) if raw else None
    return attempt


def start_attempt(
    initiative_id: str, packet_id: str, db_path: Path | None = None
) -> dict[str, Any]:
    """Open attempt N+1 for a packet, persisting its context bundle.

    Refuses when a prior attempt is still open (one attempt at a time) or the
    packet's ``policy.max_attempts`` budget (default 2) is exhausted.
    """
    init_db(db_path)
    conn = bq.connect(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        packet = _packet_row(conn, initiative_id, packet_id)

        open_row = conn.execute(
            """
            SELECT attempt_no FROM packet_attempts
            WHERE initiative_id = ? AND packet_id = ? AND outcome IS NULL
            """,
            (initiative_id, packet_id),
        ).fetchone()
        if open_row is not None:
            raise AttemptStateError(
                f"attempt {open_row['attempt_no']} for {initiative_id}/"
                f"{packet_id} is still open; close it before starting another"
            )

        policy = json.loads(packet["policy_json"]) if packet["policy_json"] else {}
        max_attempts = policy.get("max_attempts", DEFAULT_MAX_ATTEMPTS)
        used = _attempt_count(conn, initiative_id, packet_id)
        if used >= max_attempts:
            raise AttemptLimitError(
                f"{initiative_id}/{packet_id} has used {used}/{max_attempts} "
                "attempts; operator intervention required"
            )

        attempt_no = used + 1
        bundle = _build_bundle_on_conn(conn, packet, attempt_no)
        cursor = conn.execute(
            """
            INSERT INTO packet_attempts
                (initiative_id, packet_id, attempt_no, task_id, bundle_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                initiative_id,
                packet_id,
                attempt_no,
                packet["task_id"],
                json.dumps(bundle),
            ),
        )
        attempt_id = cursor.lastrowid
        bq.append_event(
            packet["task_id"],
            "attempt_started",
            payload={"attempt_id": attempt_id, "attempt_no": attempt_no},
            conn=conn,
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM packet_attempts WHERE id = ?", (attempt_id,)
        ).fetchone()
        return _row_to_attempt(row)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _open_attempt_row(conn: sqlite3.Connection, attempt_id: int) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM packet_attempts WHERE id = ?", (attempt_id,)
    ).fetchone()
    if row is None:
        raise AttemptNotFoundError(f"attempt {attempt_id} not found")
    if row["outcome"] is not None:
        raise AttemptStateError(
            f"attempt {attempt_id} is closed ({row['outcome']})"
        )
    return row


def record_implementation_result(
    attempt_id: int, result: dict[str, Any], db_path: Path | None = None
) -> dict[str, Any]:
    """Attach a validated implementation result to an open attempt. Write-once."""
    errors = validate_implementation_result(result)
    if errors:
        raise ResultContractError(errors)
    init_db(db_path)
    conn = bq.connect(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = _open_attempt_row(conn, attempt_id)
        if row["implementation_json"] is not None:
            raise AttemptStateError(
                f"attempt {attempt_id} already has an implementation result"
            )
        conn.execute(
            """
            UPDATE packet_attempts
            SET implementation_json = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (json.dumps(result), attempt_id),
        )
        bq.append_event(
            row["task_id"],
            "attempt_implementation_recorded",
            payload={"attempt_id": attempt_id, "status": result["status"]},
            conn=conn,
        )
        conn.commit()
        updated = conn.execute(
            "SELECT * FROM packet_attempts WHERE id = ?", (attempt_id,)
        ).fetchone()
        return _row_to_attempt(updated)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def record_review_result(
    attempt_id: int, result: dict[str, Any], db_path: Path | None = None
) -> dict[str, Any]:
    """Attach a validated review result. Requires the implementation first."""
    errors = validate_review_result(result)
    if errors:
        raise ResultContractError(errors)
    init_db(db_path)
    conn = bq.connect(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = _open_attempt_row(conn, attempt_id)
        if row["implementation_json"] is None:
            raise AttemptStateError(
                f"attempt {attempt_id} has no implementation result to review"
            )
        if row["review_json"] is not None:
            raise AttemptStateError(
                f"attempt {attempt_id} already has a review result"
            )
        conn.execute(
            """
            UPDATE packet_attempts
            SET review_json = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (json.dumps(result), attempt_id),
        )
        bq.append_event(
            row["task_id"],
            "attempt_review_recorded",
            payload={"attempt_id": attempt_id, "verdict": result["verdict"]},
            conn=conn,
        )
        conn.commit()
        updated = conn.execute(
            "SELECT * FROM packet_attempts WHERE id = ?", (attempt_id,)
        ).fetchone()
        return _row_to_attempt(updated)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def close_attempt(
    attempt_id: int, outcome: str, db_path: Path | None = None
) -> dict[str, Any]:
    """Close an open attempt with a terminal outcome."""
    if outcome not in _OUTCOMES:
        raise AttemptError(f"outcome must be one of {sorted(_OUTCOMES)}")
    init_db(db_path)
    conn = bq.connect(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = _open_attempt_row(conn, attempt_id)
        conn.execute(
            """
            UPDATE packet_attempts
            SET outcome = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (outcome, attempt_id),
        )
        bq.append_event(
            row["task_id"],
            "attempt_closed",
            payload={"attempt_id": attempt_id, "outcome": outcome},
            conn=conn,
        )
        conn.commit()
        updated = conn.execute(
            "SELECT * FROM packet_attempts WHERE id = ?", (attempt_id,)
        ).fetchone()
        return _row_to_attempt(updated)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_attempt(
    attempt_id: int, db_path: Path | None = None
) -> dict[str, Any] | None:
    """Return one attempt with decoded bundle/results, or None."""
    init_db(db_path)
    conn = bq.connect(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM packet_attempts WHERE id = ?", (attempt_id,)
        ).fetchone()
        return _row_to_attempt(row) if row else None
    finally:
        conn.close()


def list_attempts(
    initiative_id: str,
    packet_id: str | None = None,
    db_path: Path | None = None,
) -> list[dict[str, Any]]:
    """List attempts for an initiative (optionally one packet), oldest first."""
    init_db(db_path)
    conn = bq.connect(db_path)
    try:
        if packet_id is not None:
            rows = conn.execute(
                """
                SELECT * FROM packet_attempts
                WHERE initiative_id = ? AND packet_id = ?
                ORDER BY attempt_no
                """,
                (initiative_id, packet_id),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM packet_attempts
                WHERE initiative_id = ?
                ORDER BY packet_id, attempt_no
                """,
                (initiative_id,),
            ).fetchall()
        return [_row_to_attempt(r) for r in rows]
    finally:
        conn.close()
