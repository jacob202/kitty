"""Regression tests for supervisor recovery dispatch boundaries."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from gateway import builder_attempt as ba
from gateway import builder_initiative as bi
from gateway import builder_queue as bq
from gateway import builder_supervisor as bs
from gateway.builder_brief import default_branch_name

INITIATIVE = "supervisor-recovery"
PACKET = "P1"


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)
    (root / "README.md").write_text("hello\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=root, check=True)
    return root


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "kittybuilder" / "builder_queue.db"
    ba.init_db(path)
    return path


def _apply(repo: Path, db_path: Path) -> str:
    result = bi.apply_manifest(
        {
            "manifest_version": 1,
            "initiative_id": INITIATIVE,
            "title": "Supervisor recovery",
            "packets": [
                {
                    "id": PACKET,
                    "title": "Recover interrupted packet",
                    "objective": "Produce done.txt.",
                    "acceptance_criteria": ["done.txt exists"],
                    "allowed_paths": ["done.txt"],
                    "policy": {"max_attempts": 2},
                    "validation_commands": ["test -f done.txt"],
                }
            ],
        },
        db_path=db_path,
        repo_root=repo,
    )
    return str(result["packets"][0]["task_id"])


def _record_interrupted_run(task_id: str, db_path: Path) -> None:
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


def _make_recovery_candidate(repo: Path, db_path: Path) -> str:
    task_id = _apply(repo, db_path)
    ba.claim_and_start_attempt(
        INITIATIVE,
        PACKET,
        worker_id="dead-packet-worker",
        branch=default_branch_name({"id": task_id}),
        worktree_path=str(repo / ".worktrees" / "kittybuilder" / task_id),
        base_sha=ba.get_packet_base_sha(INITIATIVE, PACKET, db_path=db_path),
        db_path=db_path,
    )
    _record_interrupted_run(task_id, db_path)

    assert bq.get_task(task_id, db_path=db_path)["state"] == bq.BLOCKED
    assert bi.get_initiative_state(INITIATIVE, db_path=db_path) == bi.INITIATIVE_ACTIVE
    assert bi.initiative_status(INITIATIVE, db_path=db_path)["state"] == bi.INITIATIVE_PAUSED
    candidate = bi.next_packet(INITIATIVE, db_path=db_path)
    assert candidate is not None
    assert candidate["packet_id"] == PACKET
    return task_id


def test_supervisor_selects_fenced_recovery_candidate_when_operator_state_active(
    repo: Path, db_path: Path
) -> None:
    task_id = _make_recovery_candidate(repo, db_path)

    selected, skipped = bs._select_packets(db_path, max_runs=1)

    assert skipped == []
    assert [(item["packet_id"], item["task_id"]) for item in selected] == [
        (PACKET, task_id)
    ]


def test_operator_pause_still_excludes_fenced_recovery_candidate(
    repo: Path, db_path: Path
) -> None:
    _make_recovery_candidate(repo, db_path)
    bi.pause_initiative(INITIATIVE, "operator hold", db_path=db_path)

    assert bi.next_packet(INITIATIVE, db_path=db_path) is not None
    selected, _skipped = bs._select_packets(db_path, max_runs=1)
    assert selected == []
