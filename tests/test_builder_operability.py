from __future__ import annotations

from pathlib import Path

import pytest

from gateway import builder_operability as bo


def test_same_invocation_returns_durable_success_without_reexecuting(tmp_path: Path):
    db = tmp_path / "builder.db"
    calls = 0

    def execute() -> dict[str, bool]:
        nonlocal calls
        calls += 1
        return {"written": True}

    first = bo.execute_invocation(
        db_path=db,
        operation="test.write",
        idempotency_key="same-request",
        effect_class=bo.EFFECT_RECONCILABLE,
        request={"target": "artifact"},
        execute=execute,
        verify=lambda _: bo.Verification(state=bo.VERIFICATION_UNKNOWN),
    )
    second = bo.execute_invocation(
        db_path=db,
        operation="test.write",
        idempotency_key="same-request",
        effect_class=bo.EFFECT_RECONCILABLE,
        request={"target": "artifact"},
        execute=execute,
        verify=lambda _: bo.Verification(state=bo.VERIFICATION_UNKNOWN),
    )

    assert first["result"] == {"written": True}
    assert first["status"] == bo.STATUS_SUCCEEDED
    assert second == first
    assert calls == 1
    assert bo.get_invocation(first["invocation_id"], db_path=db)["status"] == bo.STATUS_SUCCEEDED


def test_idempotency_key_cannot_be_reused_for_different_request(tmp_path: Path):
    db = tmp_path / "builder.db"
    bo.request_invocation(
        db_path=db,
        operation="test.write",
        idempotency_key="stable-key",
        effect_class=bo.EFFECT_RECONCILABLE,
        request={"target": "one"},
    )

    with pytest.raises(bo.InvocationConflictError, match="different request"):
        bo.request_invocation(
            db_path=db,
            operation="test.write",
            idempotency_key="stable-key",
            effect_class=bo.EFFECT_RECONCILABLE,
            request={"target": "two"},
        )


def test_committed_effect_with_lost_response_is_reconciled_after_restart(tmp_path: Path):
    db = tmp_path / "builder.db"
    marker = tmp_path / "effect.txt"
    calls = 0

    def execute() -> dict[str, str]:
        nonlocal calls
        calls += 1
        marker.write_text("committed", encoding="utf-8")
        raise bo.OutcomeUnknownError("effect committed but response was lost")

    def verify(_: dict[str, object]) -> bo.Verification:
        if marker.exists():
            return bo.Verification(
                state=bo.VERIFICATION_APPLIED,
                result={"path": str(marker)},
                evidence="marker exists with committed content",
            )
        return bo.Verification(state=bo.VERIFICATION_NOT_APPLIED, evidence="marker absent")

    with pytest.raises(bo.OutcomeUnknownError, match="response was lost"):
        bo.execute_invocation(
            db_path=db,
            operation="test.external-effect",
            idempotency_key="lost-response",
            effect_class=bo.EFFECT_RECONCILABLE,
            request={"path": str(marker)},
            execute=execute,
            verify=verify,
        )

    unknown = bo.get_invocation_by_key(
        "test.external-effect", "lost-response", db_path=db
    )
    assert unknown["status"] == bo.STATUS_UNKNOWN

    recovered = bo.execute_invocation(
        db_path=db,
        operation="test.external-effect",
        idempotency_key="lost-response",
        effect_class=bo.EFFECT_RECONCILABLE,
        request={"path": str(marker)},
        execute=execute,
        verify=verify,
    )

    assert calls == 1
    assert marker.read_text(encoding="utf-8") == "committed"
    assert recovered["result"]["path"] == str(marker)
    final = bo.get_invocation_by_key("test.external-effect", "lost-response", db_path=db)
    assert final["status"] == bo.STATUS_SUCCEEDED
    assert final["verification"]["state"] == bo.VERIFICATION_APPLIED


def test_unknown_effect_is_not_retried_when_postcondition_is_still_unknown(tmp_path: Path):
    db = tmp_path / "builder.db"
    calls = 0

    def execute() -> None:
        nonlocal calls
        calls += 1
        raise bo.OutcomeUnknownError("timeout after dispatch")

    verifier = lambda _: bo.Verification(state=bo.VERIFICATION_UNKNOWN, evidence="provider unavailable")

    with pytest.raises(bo.OutcomeUnknownError):
        bo.execute_invocation(
            db_path=db,
            operation="test.at-most-once",
            idempotency_key="ambiguous",
            effect_class=bo.EFFECT_AT_MOST_ONCE,
            request={"message": "send once"},
            execute=execute,
            verify=verifier,
        )

    with pytest.raises(bo.InvocationUnresolvedError, match="postcondition remains unknown"):
        bo.execute_invocation(
            db_path=db,
            operation="test.at-most-once",
            idempotency_key="ambiguous",
            effect_class=bo.EFFECT_AT_MOST_ONCE,
            request={"message": "send once"},
            execute=execute,
            verify=verifier,
        )

    assert calls == 1
