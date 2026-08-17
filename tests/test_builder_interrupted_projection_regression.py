from __future__ import annotations

import os
from pathlib import Path

from gateway import builder_attempt as ba
from gateway import builder_initiative as bi
from gateway import builder_queue as bq

# TDD RED probe: this file intentionally lands before the production fix.


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
    assert status["state"] == bi.INITIATIVE_ACTIVE
