from __future__ import annotations

import os
from pathlib import Path

from gateway import builder_attempt as ba
from gateway import builder_initiative as bi
from gateway import builder_loop as bl
from gateway import builder_queue as bq
from gateway import builder_run as br

# Regression evidence was captured RED before the production fix.


def test_interrupted_run_projects_recovery_needed_not_in_progress(tmp_path: Path) -> None:
    db_path = tmp_path / "kittybuilder" / "builder_queue.db"
    manifest = {
        "manifest_version": 1,
        "initiative_id": "interrupted-projection",
        "title": "Interrupted projection regression",
        "packets": [
            {
                "id": "IP-1",
                "title": "Recover interrupted packet",
                "objective": "Prove interrupted work is reclaimable.",
                "depends_on": [],
                "acceptance_criteria": ["state is truthful"],
                "allowed_paths": ["gateway/builder_initiative.py"],
                "policy": {"max_attempts": 2},
            }
        ],
    }
    applied = bi.apply_manifest(manifest, db_path=db_path)
    task_id = applied["packets"][0]["task_id"]
    stale_attempt = ba.start_attempt(
        "interrupted-projection", "IP-1", db_path=db_path
    )

    claimed = bq.claim_task(task_id, "crashed-runner", db_path=db_path)
    run = bq.create_run(
        task_id,
        ["worker"],
        lease_token=claimed["lease_token"],
        claim_version=claimed["claim_version"],
        db_path=db_path,
    )
    bq.worker_transition_task(
        task_id,
        bq.RUNNING,
        claimed["lease_token"],
        claimed["claim_version"],
        db_path=db_path,
    )
    bq.update_run(
        run["id"],
        state=bq.RUN_RUNNING,
        pid=os.getpid(),
        process_identity="different-process-identity",
        mark_started=True,
        expected_states=frozenset({bq.RUN_STARTING}),
        db_path=db_path,
    )

    recovered = bq.recover_interrupted_runs(db_path=db_path)
    assert run["id"] in recovered["run_ids"]
    assert bq.get_task(task_id, db_path=db_path)["state"] == bq.BLOCKED
    assert ba.list_stale_attempts(
        "interrupted-projection", "IP-1", db_path=db_path
    ) == [stale_attempt]

    status = bi.initiative_status("interrupted-projection", db_path=db_path)
    assert status["recovery_needed"] == ["IP-1"]
    assert status["in_progress"] == []
    assert status["eligible"] == []
    assert status["next_packet"] == "IP-1"
    assert status["next_packet_task_id"] == task_id
    assert status["state"] == bi.INITIATIVE_PAUSED


def test_paused_initiative_reconciles_interrupted_attempt_before_pause_gate(
    tmp_path: Path, monkeypatch
) -> None:
    db_path = tmp_path / "kittybuilder" / "builder_queue.db"
    base_sha = "a" * 40
    manifest = {
        "manifest_version": 1,
        "initiative_id": "paused-interrupted",
        "title": "Paused interrupted recovery",
        "packets": [
            {
                "id": "P1",
                "title": "Recover only",
                "objective": "Reconcile without dispatch.",
                "depends_on": [],
                "acceptance_criteria": ["recovery is durable"],
                "allowed_paths": ["gateway/builder_run.py"],
                "policy": {"max_attempts": 2},
            }
        ],
    }
    applied = bi.apply_manifest(manifest, db_path=db_path, base_sha=base_sha)
    task_id = applied["packets"][0]["task_id"]
    branch = bl.default_branch_name({"id": task_id})
    expected_worktree = bl.worktree_path(task_id, repo_root=tmp_path)
    attempt, lease = ba.claim_and_start_attempt(
        "paused-interrupted",
        "P1",
        worker_id="dead-packet-worker",
        branch=branch,
        worktree_path=str(expected_worktree),
        base_sha=base_sha,
        db_path=db_path,
    )

    claimed = bq.claim_task(task_id, "crashed-runner", db_path=db_path)
    run = bq.create_run(
        task_id,
        ["worker"],
        lease_token=claimed["lease_token"],
        claim_version=claimed["claim_version"],
        db_path=db_path,
    )
    bq.worker_transition_task(
        task_id,
        bq.RUNNING,
        claimed["lease_token"],
        claimed["claim_version"],
        db_path=db_path,
    )
    bq.update_run(
        run["id"],
        state=bq.RUN_RUNNING,
        pid=os.getpid(),
        process_identity="different-process-identity",
        mark_started=True,
        expected_states=frozenset({bq.RUN_STARTING}),
        db_path=db_path,
    )
    bq.recover_interrupted_runs(db_path=db_path)
    bi.pause_initiative("paused-interrupted", "operator hold", db_path=db_path)

    def no_dispatch(*args, **kwargs):
        raise AssertionError("paused recovery housekeeping must not dispatch a worker")

    monkeypatch.setattr(br.bl, "run_packet", no_dispatch)
    result = br.run_initiative(
        "paused-interrupted",
        worker_command=["false"],
        repo_root=tmp_path,
        db_path=db_path,
        effectiveness_guard=False,
    )

    assert result["outcome"] == "paused"
    closed = ba.get_attempt(attempt["id"], db_path=db_path)
    assert closed is not None and closed["outcome"] == ba.ATTEMPT_CRASHED
    assert bq.get_branch_lease(lease["lease_id"], db_path=db_path) is None
    task = bq.get_task(task_id, db_path=db_path)
    assert task is not None and task["state"] == bq.QUEUED
    assert task["blocked_reason"] is None
    assert bq.get_run(run["id"], db_path=db_path)["state"] == bq.RUN_INTERRUPTED
    status = bi.initiative_status("paused-interrupted", db_path=db_path)
    assert status["state"] == bi.INITIATIVE_PAUSED
    assert status["recovery_needed"] == []
    assert status["eligible"] == ["P1"]
    assert status["next_packet"] == "P1"


def test_reconciled_crash_still_projects_recovery_until_task_is_requeued(
    tmp_path: Path
) -> None:
    db_path = tmp_path / "kittybuilder" / "builder_queue.db"
    base_sha = "b" * 40
    manifest = {
        "manifest_version": 1,
        "initiative_id": "reconciled-blocked",
        "title": "Reconciled but blocked",
        "packets": [
            {
                "id": "P1",
                "title": "Finish recovery",
                "objective": "Release only after durable crash reconciliation.",
                "depends_on": [],
                "acceptance_criteria": ["task is reclaimable"],
                "allowed_paths": ["gateway/builder_loop.py"],
                "policy": {"max_attempts": 2},
            }
        ],
    }
    applied = bi.apply_manifest(manifest, db_path=db_path, base_sha=base_sha)
    task_id = applied["packets"][0]["task_id"]
    branch = bl.default_branch_name({"id": task_id})
    attempt, _lease = ba.claim_and_start_attempt(
        "reconciled-blocked",
        "P1",
        worker_id="dead-packet-worker",
        branch=branch,
        worktree_path=str(bl.worktree_path(task_id, repo_root=tmp_path)),
        base_sha=base_sha,
        db_path=db_path,
    )
    claimed = bq.claim_task(task_id, "crashed-runner", db_path=db_path)
    run = bq.create_run(
        task_id, ["worker"],
        lease_token=claimed["lease_token"],
        claim_version=claimed["claim_version"],
        db_path=db_path,
    )
    bq.worker_transition_task(
        task_id, bq.RUNNING, claimed["lease_token"], claimed["claim_version"], db_path=db_path
    )
    bq.update_run(
        run["id"], state=bq.RUN_RUNNING, pid=os.getpid(),
        process_identity="different-process-identity", mark_started=True,
        expected_states=frozenset({bq.RUN_STARTING}), db_path=db_path,
    )
    bq.recover_interrupted_runs(db_path=db_path)

    reconciled = bl._reconcile_stale_attempts(
        "reconciled-blocked", "P1", db_path=db_path, repo_root=tmp_path
    )
    assert [item["id"] for item in reconciled] == [attempt["id"]]
    assert ba.get_attempt(attempt["id"], db_path=db_path)["outcome"] == ba.ATTEMPT_CRASHED
    assert bq.get_task(task_id, db_path=db_path)["state"] == bq.BLOCKED

    status = bi.initiative_status("reconciled-blocked", db_path=db_path)
    assert status["recovery_needed"] == ["P1"]
    assert status["in_progress"] == []
    assert status["next_packet"] == "P1"

    bl.reconcile_interrupted_packet(
        "reconciled-blocked", "P1", db_path=db_path, repo_root=tmp_path
    )
    task = bq.get_task(task_id, db_path=db_path)
    assert task is not None and task["state"] == bq.QUEUED
    assert bi.initiative_status("reconciled-blocked", db_path=db_path)["recovery_needed"] == []
