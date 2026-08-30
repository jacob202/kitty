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

    def verifier(_: dict[str, object]) -> bo.Verification:
        return bo.Verification(
            state=bo.VERIFICATION_UNKNOWN, evidence="provider unavailable"
        )

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


def test_status_transition_is_compare_and_set_under_concurrency(tmp_path: Path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier, Lock

    db = tmp_path / "builder.db"
    receipt = bo.request_invocation(
        db_path=db,
        operation="test.concurrent",
        idempotency_key="one-logical-effect",
        effect_class=bo.EFFECT_RECONCILABLE,
        request={"value": 1},
    )
    real_get = bo.get_invocation
    barrier = Barrier(2)
    guard = Lock()
    synchronized_reads = 0

    def synchronized_get(invocation_id: str, *, db_path: Path | None = None):
        nonlocal synchronized_reads
        current = real_get(invocation_id, db_path=db_path)
        should_wait = False
        with guard:
            if current["status"] == bo.STATUS_REQUESTED and synchronized_reads < 2:
                synchronized_reads += 1
                should_wait = True
        if should_wait:
            barrier.wait(timeout=5)
        return current

    monkeypatch.setattr(bo, "get_invocation", synchronized_get)

    def accept_once():
        return bo._transition(  # noqa: SLF001 - intentional CAS failure injection
            receipt["invocation_id"], bo.STATUS_ACCEPTED, db_path=db
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(accept_once) for _ in range(2)]
        outcomes = []
        for future in futures:
            try:
                outcomes.append(("ok", future.result()))
            except bo.InvocationUnresolvedError as exc:
                outcomes.append(("lost_race", str(exc)))

    assert [kind for kind, _ in outcomes].count("ok") == 1
    assert [kind for kind, _ in outcomes].count("lost_race") == 1
    assert real_get(receipt["invocation_id"], db_path=db)["status"] == bo.STATUS_ACCEPTED


def test_confirmed_runner_loss_reconciles_a_still_running_effect_without_replay(tmp_path: Path):
    from gateway import builder_queue as bq

    db = tmp_path / "builder.db"
    marker = tmp_path / "committed.txt"
    marker.write_text("done", encoding="utf-8")
    receipt = bo.request_invocation(
        db_path=db,
        operation="test.crash-after-effect",
        idempotency_key="crashed-runner",
        effect_class=bo.EFFECT_RECONCILABLE,
        request={"path": str(marker)},
    )
    # Failure injection: model the process dying after the external effect but
    # before it can turn RUNNING into UNKNOWN/SUCCEEDED.
    with bq.connect(db) as conn:
        conn.execute(
            "UPDATE operation_receipts SET status = ?, started_at = CURRENT_TIMESTAMP "
            "WHERE invocation_id = ?",
            (bo.STATUS_RUNNING, receipt["invocation_id"]),
        )
        conn.commit()

    def verify(_: dict[str, object]) -> bo.Verification:
        return bo.Verification(
            state=bo.VERIFICATION_APPLIED,
            result={"path": str(marker)},
            evidence="postcondition exists after confirmed runner death",
        )

    recovered = bo.reconcile_interrupted_invocation(
        receipt["invocation_id"], verify=verify, db_path=db
    )

    assert recovered["status"] == bo.STATUS_SUCCEEDED
    assert recovered["result"] == {"path": str(marker)}
    assert marker.read_text(encoding="utf-8") == "done"


def test_confirmed_runner_loss_with_no_effect_becomes_failed_and_retryable(tmp_path: Path):
    from gateway import builder_queue as bq

    db = tmp_path / "builder.db"
    receipt = bo.request_invocation(
        db_path=db,
        operation="test.crash-before-effect",
        idempotency_key="dead-before-effect",
        effect_class=bo.EFFECT_RECONCILABLE,
        request={"target": "missing"},
    )
    with bq.connect(db) as conn:
        conn.execute(
            "UPDATE operation_receipts SET status = ? WHERE invocation_id = ?",
            (bo.STATUS_RUNNING, receipt["invocation_id"]),
        )
        conn.commit()

    recovered = bo.reconcile_interrupted_invocation(
        receipt["invocation_id"],
        verify=lambda _: bo.Verification(
            state=bo.VERIFICATION_NOT_APPLIED,
            evidence="postcondition absent after confirmed runner death",
        ),
        db_path=db,
    )

    assert recovered["status"] == bo.STATUS_FAILED
    assert recovered["verification"]["state"] == bo.VERIFICATION_NOT_APPLIED


def test_confirmed_runner_loss_with_ambiguous_effect_preserves_verification(tmp_path: Path):
    from gateway import builder_queue as bq

    db = tmp_path / "builder.db"
    receipt = bo.request_invocation(
        db_path=db,
        operation="test.crash-ambiguous",
        idempotency_key="dead-ambiguous",
        effect_class=bo.EFFECT_AT_MOST_ONCE,
        request={"target": "external"},
    )
    with bq.connect(db) as conn:
        conn.execute(
            "UPDATE operation_receipts SET status = ? WHERE invocation_id = ?",
            (bo.STATUS_RUNNING, receipt["invocation_id"]),
        )
        conn.commit()

    with pytest.raises(bo.InvocationUnresolvedError, match="refusing replay"):
        bo.reconcile_interrupted_invocation(
            receipt["invocation_id"],
            verify=lambda _: bo.Verification(
                state=bo.VERIFICATION_UNKNOWN,
                evidence="provider audit endpoint unavailable",
            ),
            db_path=db,
        )

    unresolved = bo.get_invocation(receipt["invocation_id"], db_path=db)
    assert unresolved["status"] == bo.STATUS_UNKNOWN
    assert unresolved["verification"] == {
        "state": bo.VERIFICATION_UNKNOWN,
        "result": None,
        "evidence": "provider audit endpoint unavailable",
    }
