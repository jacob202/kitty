"""KittyBench: Builder queue state machine regression.

Exercises the full state machine: create → claim → run → block → recover.
Each test exercises one end-to-end chain.

Packet: KB-S1 (queue state machine)
"""

from gateway import builder_queue as bq


def test_full_lifecycle_queued_to_blocked(db_path):
    task = bq.create_task(
        "bench: lifecycle test",
        description="Verify the full lifecycle",
        acceptance_criteria=["tests pass"],
        db_path=db_path,
    )
    task_id = task["id"]
    assert bq.get_task(task_id, db_path=db_path)["state"] == bq.QUEUED

    claim = bq.claim_task(task_id, "bench-worker-1", db_path=db_path)
    assert claim["state"] == bq.CLAIMED

    bq.worker_transition_task(
        task_id, bq.RUNNING,
        claim["lease_token"], claim["claim_version"],
        db_path=db_path,
    )
    assert bq.get_task(task_id, db_path=db_path)["state"] == bq.RUNNING

    bq.worker_transition_task(
        task_id, bq.BLOCKED,
        claim["lease_token"], claim["claim_version"],
        db_path=db_path,
    )
    assert bq.get_task(task_id, db_path=db_path)["state"] == bq.BLOCKED


def test_lease_fencing_rejects_stale_worker(db_path):
    task_id = bq.create_task(
        "bench: lease fence",
        acceptance_criteria=["lease holds"],
        db_path=db_path,
    )["id"]

    claim_1 = bq.claim_task(task_id, "worker-a", db_path=db_path)
    bq.worker_transition_task(
        task_id, bq.RUNNING,
        claim_1["lease_token"], claim_1["claim_version"],
        db_path=db_path,
    )

    # Must block before releasing
    bq.worker_transition_task(
        task_id, bq.BLOCKED,
        claim_1["lease_token"], claim_1["claim_version"],
        db_path=db_path,
    )
    bq.operator_release_task(task_id, db_path=db_path)
    claim_2 = bq.claim_task(task_id, "worker-b", db_path=db_path)

    try:
        bq.worker_transition_task(
            task_id, bq.RUNNING,
            claim_1["lease_token"], claim_1["claim_version"],
            db_path=db_path,
        )
        assert False, "stale lease should have been rejected"
    except bq.LeaseConflictError:
        pass


def test_illegal_transition_raises(db_path):
    task_id = bq.create_task(
        "bench: illegal transition",
        acceptance_criteria=["must fail"],
        db_path=db_path,
    )["id"]

    try:
        bq.transition_task(task_id, bq.DONE, db_path=db_path)
        assert False, "illegal transition should raise"
    except bq.IllegalTransitionError:
        pass


def test_events_are_append_only(db_path):
    task_id = bq.create_task(
        "bench: events",
        acceptance_criteria=["event trail"],
        db_path=db_path,
    )["id"]

    claim = bq.claim_task(task_id, "bench-events", db_path=db_path)
    bq.worker_transition_task(
        task_id, bq.RUNNING,
        claim["lease_token"], claim["claim_version"],
        db_path=db_path,
    )
    bq.worker_transition_task(
        task_id, bq.BLOCKED,
        claim["lease_token"], claim["claim_version"],
        db_path=db_path,
    )

    events = bq.list_events(task_id, db_path=db_path)
    assert len(events) >= 4


def test_task_not_found_returns_none(db_path):
    result = bq.get_task("kb_nonexistent_0000", db_path=db_path)
    assert result is None


def test_renew_lease_extends_timeout(db_path):
    task_id = bq.create_task(
        "bench: lease renew",
        acceptance_criteria=["lease stays"],
        db_path=db_path,
    )["id"]

    claim = bq.claim_task(task_id, "lease-worker", db_path=db_path)
    bq.worker_transition_task(
        task_id, bq.RUNNING,
        claim["lease_token"], claim["claim_version"],
        db_path=db_path,
    )

    result = bq.renew_lease(
        task_id, claim["lease_token"], claim["claim_version"],
        db_path=db_path,
    )
    assert result["state"] == bq.RUNNING
    assert result.get("lease_expires_at") is not None
