"""Durable, agent-operable receipts for side-effecting Builder operations.

A model must be able to distinguish "the effect did not happen" from "the effect
may have happened but the response was lost". This module gives one logical
operation a stable identity across retries and refuses to replay ambiguous
side effects until a postcondition verifier resolves them.

The rows live in Builder's existing queue SQLite database. They are execution
evidence, not a second task queue or scheduler.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from gateway import builder_queue as bq
from gateway._id_helpers import generate_id_with_base36

EFFECT_NONE = "none"
EFFECT_IDEMPOTENT = "idempotent"
EFFECT_RECONCILABLE = "reconcilable"
EFFECT_AT_MOST_ONCE = "at_most_once"
_EFFECT_CLASSES = frozenset(
    {EFFECT_NONE, EFFECT_IDEMPOTENT, EFFECT_RECONCILABLE, EFFECT_AT_MOST_ONCE}
)

STATUS_REQUESTED = "requested"
STATUS_ACCEPTED = "accepted"
STATUS_RUNNING = "running"
STATUS_SUCCEEDED = "succeeded"
STATUS_FAILED = "failed"
STATUS_UNKNOWN = "unknown"

VERIFICATION_APPLIED = "applied"
VERIFICATION_NOT_APPLIED = "not_applied"
VERIFICATION_UNKNOWN = "unknown"
_VERIFICATION_STATES = frozenset(
    {VERIFICATION_APPLIED, VERIFICATION_NOT_APPLIED, VERIFICATION_UNKNOWN}
)

_ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    STATUS_REQUESTED: frozenset({STATUS_ACCEPTED}),
    STATUS_ACCEPTED: frozenset({STATUS_RUNNING}),
    STATUS_RUNNING: frozenset({STATUS_SUCCEEDED, STATUS_FAILED, STATUS_UNKNOWN}),
    STATUS_FAILED: frozenset({STATUS_ACCEPTED}),
    STATUS_UNKNOWN: frozenset({STATUS_ACCEPTED, STATUS_SUCCEEDED}),
    STATUS_SUCCEEDED: frozenset(),
}


class OperabilityError(RuntimeError):
    """Base error for durable invocation contract violations."""


class InvocationConflictError(OperabilityError):
    """An idempotency key was reused for a different logical request."""


class InvocationUnresolvedError(OperabilityError):
    """An ambiguous effect could not be safely reconciled."""


class OutcomeUnknownError(OperabilityError):
    """Execution returned no trustworthy answer about whether its effect happened."""


@dataclass(frozen=True)
class Verification:
    """Postcondition evidence for an invocation whose outcome is ambiguous."""

    state: str
    result: Any = None
    evidence: str | None = None

    def to_dict(self) -> dict[str, Any]:
        if self.state not in _VERIFICATION_STATES:
            raise OperabilityError(
                f"verification state must be one of {sorted(_VERIFICATION_STATES)}, "
                f"got {self.state!r}"
            )
        return {"state": self.state, "result": self.result, "evidence": self.evidence}


def _canonical_json(value: Any, *, label: str) -> str:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise OperabilityError(f"{label} must be JSON-serializable: {exc}") from exc


def _fingerprint(request: Mapping[str, Any]) -> tuple[str, str]:
    encoded = _canonical_json(dict(request), label="request")
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest(), encoded


def _require_text(value: str, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise OperabilityError(f"{label} must be a non-empty string")
    return value.strip()


def _row_to_invocation(row: Any) -> dict[str, Any]:
    def decode(name: str) -> Any:
        raw = row[name]
        return json.loads(raw) if raw is not None else None

    return {
        "invocation_id": row["invocation_id"],
        "operation": row["operation"],
        "idempotency_key": row["idempotency_key"],
        "request_fingerprint": row["request_fingerprint"],
        "request": decode("request_json"),
        "effect_class": row["effect_class"],
        "status": row["status"],
        "result": decode("result_json"),
        "verification": decode("verification_json"),
        "last_error": row["last_error"],
        "started_at": row["started_at"],
        "ended_at": row["ended_at"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _init(db_path: Path | None) -> None:
    bq.init_db(db_path)


def get_invocation(invocation_id: str, *, db_path: Path | None = None) -> dict[str, Any]:
    _init(db_path)
    with bq.connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM operation_receipts WHERE invocation_id = ?", (invocation_id,)
        ).fetchone()
    if row is None:
        raise OperabilityError(f"invocation not found: {invocation_id}")
    return _row_to_invocation(row)


def get_invocation_by_key(
    operation: str,
    idempotency_key: str,
    *,
    db_path: Path | None = None,
) -> dict[str, Any]:
    operation = _require_text(operation, label="operation")
    idempotency_key = _require_text(idempotency_key, label="idempotency_key")
    _init(db_path)
    with bq.connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM operation_receipts WHERE operation = ? AND idempotency_key = ?",
            (operation, idempotency_key),
        ).fetchone()
    if row is None:
        raise OperabilityError(
            f"invocation not found for operation={operation!r} "
            f"idempotency_key={idempotency_key!r}"
        )
    return _row_to_invocation(row)


def request_invocation(
    *,
    operation: str,
    idempotency_key: str,
    effect_class: str,
    request: Mapping[str, Any],
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Create or recover the durable identity for one logical operation."""
    operation = _require_text(operation, label="operation")
    idempotency_key = _require_text(idempotency_key, label="idempotency_key")
    if effect_class not in _EFFECT_CLASSES:
        raise OperabilityError(
            f"effect_class must be one of {sorted(_EFFECT_CLASSES)}, got {effect_class!r}"
        )
    fingerprint, request_json = _fingerprint(request)
    _init(db_path)
    with bq.connect(db_path) as conn:
        existing = conn.execute(
            "SELECT * FROM operation_receipts WHERE operation = ? AND idempotency_key = ?",
            (operation, idempotency_key),
        ).fetchone()
        if existing is not None:
            if (
                existing["request_fingerprint"] != fingerprint
                or existing["effect_class"] != effect_class
            ):
                raise InvocationConflictError(
                    f"idempotency key {idempotency_key!r} for {operation!r} was reused "
                    "for a different request or effect class"
                )
            return _row_to_invocation(existing)

        invocation_id = generate_id_with_base36("inv")
        conn.execute(
            "INSERT INTO operation_receipts "
            "(invocation_id, operation, idempotency_key, request_fingerprint, request_json, "
            "effect_class, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                invocation_id,
                operation,
                idempotency_key,
                fingerprint,
                request_json,
                effect_class,
                STATUS_REQUESTED,
            ),
        )
        conn.commit()
    return get_invocation(invocation_id, db_path=db_path)


def _transition(
    invocation_id: str,
    target: str,
    *,
    db_path: Path | None,
    result: Any = None,
    verification: Verification | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    current = get_invocation(invocation_id, db_path=db_path)
    if target not in _ALLOWED_TRANSITIONS[current["status"]]:
        raise OperabilityError(
            f"illegal invocation transition {current['status']!r} -> {target!r} "
            f"for {invocation_id}"
        )
    result_json = _canonical_json(result, label="result") if target == STATUS_SUCCEEDED else None
    verification_json = (
        _canonical_json(verification.to_dict(), label="verification")
        if verification is not None
        else None
    )
    with bq.connect(db_path) as conn:
        if target == STATUS_RUNNING:
            conn.execute(
                "UPDATE operation_receipts SET status = ?, "
                "started_at = COALESCE(started_at, CURRENT_TIMESTAMP), last_error = NULL, "
                "updated_at = CURRENT_TIMESTAMP WHERE invocation_id = ?",
                (target, invocation_id),
            )
        elif target in {STATUS_SUCCEEDED, STATUS_FAILED}:
            conn.execute(
                "UPDATE operation_receipts SET status = ?, result_json = ?, "
                "verification_json = COALESCE(?, verification_json), last_error = ?, "
                "ended_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP "
                "WHERE invocation_id = ?",
                (target, result_json, verification_json, error, invocation_id),
            )
        elif target == STATUS_UNKNOWN:
            conn.execute(
                "UPDATE operation_receipts SET status = ?, last_error = ?, ended_at = NULL, "
                "updated_at = CURRENT_TIMESTAMP WHERE invocation_id = ?",
                (target, error, invocation_id),
            )
        else:
            conn.execute(
                "UPDATE operation_receipts SET status = ?, "
                "verification_json = COALESCE(?, verification_json), last_error = NULL, "
                "ended_at = NULL, updated_at = CURRENT_TIMESTAMP WHERE invocation_id = ?",
                (target, verification_json, invocation_id),
            )
        conn.commit()
    return get_invocation(invocation_id, db_path=db_path)


def _response(receipt: dict[str, Any]) -> dict[str, Any]:
    return {
        "invocation_id": receipt["invocation_id"],
        "status": receipt["status"],
        "result": receipt["result"],
        "verification": receipt["verification"],
    }


def execute_invocation(
    *,
    operation: str,
    idempotency_key: str,
    effect_class: str,
    request: Mapping[str, Any],
    execute: Callable[[], Any],
    verify: Callable[[dict[str, Any]], Verification],
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Execute once, reconciling an ambiguous prior effect before any retry."""
    receipt = request_invocation(
        operation=operation,
        idempotency_key=idempotency_key,
        effect_class=effect_class,
        request=request,
        db_path=db_path,
    )
    if receipt["status"] == STATUS_SUCCEEDED:
        return _response(receipt)
    if receipt["status"] == STATUS_RUNNING:
        raise InvocationUnresolvedError(
            f"invocation {receipt['invocation_id']} is still marked running; "
            "refusing concurrent replay"
        )
    if receipt["status"] == STATUS_UNKNOWN:
        verification = verify(receipt)
        verification.to_dict()
        if verification.state == VERIFICATION_APPLIED:
            recovered = _transition(
                receipt["invocation_id"],
                STATUS_SUCCEEDED,
                db_path=db_path,
                result=verification.result,
                verification=verification,
            )
            return _response(recovered)
        if verification.state == VERIFICATION_UNKNOWN:
            with bq.connect(db_path) as conn:
                conn.execute(
                    "UPDATE operation_receipts SET verification_json = ?, "
                    "updated_at = CURRENT_TIMESTAMP WHERE invocation_id = ?",
                    (
                        _canonical_json(verification.to_dict(), label="verification"),
                        receipt["invocation_id"],
                    ),
                )
                conn.commit()
            raise InvocationUnresolvedError(
                f"invocation {receipt['invocation_id']} postcondition remains unknown; "
                "refusing to replay a possibly committed effect"
            )
        receipt = _transition(
            receipt["invocation_id"],
            STATUS_ACCEPTED,
            db_path=db_path,
            verification=verification,
        )
    elif receipt["status"] in {STATUS_REQUESTED, STATUS_FAILED}:
        receipt = _transition(receipt["invocation_id"], STATUS_ACCEPTED, db_path=db_path)

    receipt = _transition(receipt["invocation_id"], STATUS_RUNNING, db_path=db_path)
    try:
        result = execute()
    except OutcomeUnknownError as exc:
        _transition(
            receipt["invocation_id"], STATUS_UNKNOWN, db_path=db_path, error=str(exc)
        )
        raise
    except Exception as exc:
        _transition(
            receipt["invocation_id"], STATUS_FAILED, db_path=db_path, error=str(exc)
        )
        raise
    succeeded = _transition(
        receipt["invocation_id"], STATUS_SUCCEEDED, db_path=db_path, result=result
    )
    return _response(succeeded)
