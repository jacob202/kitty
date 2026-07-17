"""Contract tests for the bounded, read-only Builder status projection."""

from __future__ import annotations

import subprocess
from pathlib import Path

from gateway import builder_attempt as ba
from gateway import builder_initiative as bi
from gateway import builder_queue as bq
from gateway import builder_status, runtime_manifest

INITIATIVE_ID = "builder-ui-test"
PACKET_ID = "BUILDER-UI-1"


def _git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    for args in (
        ["git", "init"],
        ["git", "config", "user.email", "tests@example.invalid"],
        ["git", "config", "user.name", "Builder Status Tests"],
    ):
        subprocess.run(args, cwd=repo, check=True, capture_output=True, text=True)
    (repo / "README.md").write_text("# Builder status test repo\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "commit", "-m", "test: create durable base"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(["git", "branch", "-M", "main"], cwd=repo, check=True, capture_output=True, text=True)
    return repo


def _manifest() -> dict:
    return {
        "manifest_version": 1,
        "initiative_id": INITIATIVE_ID,
        "title": "Builder UI test initiative",
        "packets": [
            {
                "id": PACKET_ID,
                "title": "Expose truthful Builder status",
                "objective": "Render a safe read-only status surface.",
                "acceptance_criteria": ["The status projection is bounded."],
                "allowed_paths": ["gateway/builder_status.py"],
                "policy": {"max_attempts": 2},
                "validation_commands": ["false"],
            }
        ],
    }


def _apply_manifest(tmp_path: Path) -> tuple[Path, Path, str]:
    db_path = tmp_path / "builder.db"
    repo = _git_repo(tmp_path)
    result = bi.apply_manifest(_manifest(), db_path=db_path, repo_root=repo)
    return db_path, repo, result["packets"][0]["task_id"]


def _implementation_result() -> dict:
    return {
        "contract_version": 1,
        "status": "completed",
        "summary": "Implemented the read-only status projection.",
        "validation": {"passed": True, "output": "1 passed"},
    }


def _review_result() -> dict:
    return {
        "contract_version": 1,
        "verdict": "reject",
        "summary": "Evidence needs another look.",
    }


def test_empty_snapshot_has_no_fabricated_builder_activity(tmp_path: Path):
    db_path = tmp_path / "builder.db"

    snapshot = builder_status.build_status_snapshot(db_path=db_path)

    assert snapshot["schema_version"] == 1
    assert snapshot["queue"]["total"] == 0
    assert snapshot["initiatives"] == []


def test_snapshot_uses_latest_two_attempts_and_omits_unsafe_fields(tmp_path: Path):
    db_path, repo, task_id = _apply_manifest(tmp_path)
    first_attempt = ba.start_attempt(INITIATIVE_ID, PACKET_ID, db_path=db_path)
    ba.record_implementation_result(first_attempt["id"], _implementation_result(), db_path=db_path)
    ba.run_validation(first_attempt["id"], cwd=repo, db_path=db_path)
    ba.record_review_result(first_attempt["id"], _review_result(), db_path=db_path)
    ba.close_attempt(first_attempt["id"], "failed", db_path=db_path)

    durable_base = bi.get_initiative(INITIATIVE_ID, db_path=db_path)["packets"][0]["base_sha"]
    second_attempt, lease = ba.claim_and_start_attempt(
        INITIATIVE_ID,
        PACKET_ID,
        worker_id="worker-status",
        branch="feat/status-surface",
        worktree_path=str(tmp_path / "unsafe-worktree"),
        base_sha=durable_base,
        db_path=db_path,
    )
    claimed = bq.claim_task(task_id, "worker-status", db_path=db_path)
    run = bq.create_run(
        task_id,
        ["unsafe", "command"],
        lease_token=claimed["lease_token"],
        claim_version=claimed["claim_version"],
        worker="worker-status",
        log_path="/private/unsafe/worker.log",
        db_path=db_path,
    )
    bq.update_run(run["id"], state=bq.RUN_RUNNING, mark_started=True, db_path=db_path)
    bq.append_event(
        task_id,
        "infrastructure_failed",
        payload={"reason": "worker could not read /private/unsafe/worker.log"},
        db_path=db_path,
    )

    snapshot = builder_status.build_status_snapshot(db_path=db_path)
    packet = snapshot["initiatives"][0]["packets"][0]

    assert packet["attempt"]["id"] == second_attempt["id"]
    assert packet["previous_attempt"]["id"] == first_attempt["id"]
    assert packet["previous_attempt"]["validation_status"] == "failed"
    assert packet["previous_attempt"]["review_verdict"] == "reject"
    assert packet["lease"] == {
        "id": lease["lease_id"],
        "worker_id": "worker-status",
        "branch": "feat/status-surface",
        "base_sha": durable_base,
        "created_at": lease["created_at"],
    }
    assert packet["run"]["state"] == "running"
    assert packet["last_event"]["type"] == "infrastructure_failed"
    assert packet["last_event"]["reason"] == "worker could not read [path]"
    assert packet["failure_kind"] == "infrastructure"
    assert "worktree_path" not in packet["lease"]
    assert "command" not in packet["run"]
    assert "log_path" not in packet["run"]


def test_crashed_attempt_does_not_consume_retry_budget(tmp_path: Path):
    db_path, _repo, _task_id = _apply_manifest(tmp_path)
    crashed = ba.start_attempt(INITIATIVE_ID, PACKET_ID, db_path=db_path)
    ba.close_attempt(crashed["id"], "crashed", db_path=db_path)
    failed = ba.start_attempt(INITIATIVE_ID, PACKET_ID, db_path=db_path)
    ba.close_attempt(failed["id"], "failed", db_path=db_path)

    packet = builder_status.build_status_snapshot(db_path=db_path)["initiatives"][0]["packets"][0]

    assert packet["budget"] == {"used": 1, "max": 2, "exhausted": False}
    assert packet["attempt"]["outcome"] == "failed"
    assert packet["previous_attempt"]["outcome"] == "crashed"


def test_cancelled_task_is_not_presented_as_an_implementation_failure(tmp_path: Path):
    db_path, _repo, task_id = _apply_manifest(tmp_path)
    bq.transition_task(task_id, bq.CANCELLED, db_path=db_path)

    packet = builder_status.build_status_snapshot(db_path=db_path)["initiatives"][0]["packets"][0]

    assert packet["task_state"] == "cancelled"
    assert packet["failure_kind"] == "cancelled"


def test_runtime_manifest_reports_a_disabled_builder_without_fabricating_state(monkeypatch):
    monkeypatch.setenv("KITTY_BUILDER_QUEUE_ENABLED", "0")

    fact = runtime_manifest._builder_fact(
        observed_at="2026-07-17T03:00:00Z",
        valid_until="2026-07-17T03:00:05Z",
    )

    assert fact["state"] == "unavailable"
    assert fact["value"] is None
    assert fact["reason"] == "KITTY_BUILDER_QUEUE_ENABLED disables the Builder queue"


def test_runtime_manifest_surfaces_builder_read_failures(monkeypatch):
    monkeypatch.delenv("KITTY_BUILDER_QUEUE_ENABLED", raising=False)

    def unavailable_projection() -> dict:
        raise ValueError("attempt implementation contains invalid JSON")

    monkeypatch.setattr(builder_status, "build_status_snapshot", unavailable_projection)

    fact = runtime_manifest._builder_fact(
        observed_at="2026-07-17T03:00:00Z",
        valid_until="2026-07-17T03:00:05Z",
    )

    assert fact["state"] == "unknown"
    assert fact["value"] is None
    assert fact["source"] == "builder_status"
    assert fact["reason"] == "Builder state read failed: attempt implementation contains invalid JSON"
