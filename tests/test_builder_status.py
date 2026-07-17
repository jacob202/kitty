"""Contract tests for the bounded, read-only Builder status projection."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

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
        "findings": [
            {
                "severity": "major",
                "note": "Validation failed in /private/unsafe/build.log",
            }
        ],
    }


def test_empty_snapshot_has_no_fabricated_builder_activity(tmp_path: Path):
    db_path = tmp_path / "builder.db"

    snapshot = builder_status.build_status_snapshot(db_path=db_path)

    assert snapshot["schema_version"] == 2
    assert snapshot["attempt_history_limit"] == 10
    assert snapshot["queue"]["total"] == 0
    assert snapshot["initiatives"] == []


def test_control_plane_summary_does_not_create_a_missing_database(tmp_path: Path):
    db_path = tmp_path / "missing" / "builder.db"

    with pytest.raises(FileNotFoundError, match="does not exist"):
        builder_status.build_control_plane_summary(db_path=db_path)

    assert not db_path.exists()
    assert not db_path.parent.exists()


def test_control_plane_summary_reads_queue_and_initiatives(tmp_path: Path):
    db_path, _repo, _task_id = _apply_manifest(tmp_path)
    before = db_path.read_bytes()

    summary = builder_status.build_control_plane_summary(db_path=db_path)

    assert db_path.read_bytes() == before
    assert summary["schema_version"] == 1
    assert summary["queue"]["total"] == 1
    assert summary["queue"]["queued"] == 1
    assert summary["initiatives"] == [
        {
            "initiative_id": INITIATIVE_ID,
            "title": "Builder UI test initiative",
            "state": "active",
            "pause_reason": None,
            "packet_count": 1,
            "updated_at": summary["initiatives"][0]["updated_at"],
        }
    ]


def test_snapshot_exposes_bounded_attempt_evidence_and_omits_unsafe_fields(tmp_path: Path):
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

    assert packet["attempt_count"] == 2
    assert packet["attempt_history_truncated"] is False
    assert [attempt["id"] for attempt in packet["attempt_history"]] == [
        second_attempt["id"],
        first_attempt["id"],
    ]
    previous = packet["attempt_history"][1]
    assert previous["validation"] == {
        "status": "failed",
        "command_count": 1,
        "failed_command_count": 1,
        "summary": "1 validation command failed (exit 1).",
    }
    assert previous["review"] == {
        "verdict": "reject",
        "summary": "Evidence needs another look.",
        "findings": [
            {
                "severity": "major",
                "note": "Validation failed in [path]",
            }
        ],
        "findings_truncated": False,
    }
    assert previous["counts_toward_budget"] is True
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
    assert packet["investigation"] == {
        "logs": {
            "state": "unavailable",
            "reason": "Safe bounded log delivery is not available yet.",
        },
        "artifacts": {
            "state": "unavailable",
            "reason": "Safe durable artifact delivery is not available yet.",
        },
    }


def test_crashed_attempt_does_not_consume_retry_budget(tmp_path: Path):
    db_path, _repo, _task_id = _apply_manifest(tmp_path)
    crashed = ba.start_attempt(INITIATIVE_ID, PACKET_ID, db_path=db_path)
    ba.close_attempt(crashed["id"], "crashed", db_path=db_path)
    failed = ba.start_attempt(INITIATIVE_ID, PACKET_ID, db_path=db_path)
    ba.close_attempt(failed["id"], "failed", db_path=db_path)

    packet = builder_status.build_status_snapshot(db_path=db_path)["initiatives"][0]["packets"][0]

    assert packet["budget"] == {"used": 1, "max": 2, "exhausted": False}
    assert [attempt["outcome"] for attempt in packet["attempt_history"]] == [
        "failed",
        "crashed",
    ]
    assert [attempt["counts_toward_budget"] for attempt in packet["attempt_history"]] == [
        True,
        False,
    ]


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


def test_attempt_history_is_capped_and_reports_total(tmp_path: Path):
    manifest = _manifest()
    manifest["packets"][0]["policy"]["max_attempts"] = 12
    db_path = tmp_path / "builder.db"
    repo = _git_repo(tmp_path)
    bi.apply_manifest(manifest, db_path=db_path, repo_root=repo)

    for _ in range(12):
        attempt = ba.start_attempt(INITIATIVE_ID, PACKET_ID, db_path=db_path)
        ba.close_attempt(attempt["id"], "failed", db_path=db_path)

    packet = builder_status.build_status_snapshot(db_path=db_path)["initiatives"][0]["packets"][0]

    assert packet["attempt_count"] == 12
    assert packet["attempt_history_truncated"] is True
    assert [attempt["number"] for attempt in packet["attempt_history"]] == list(
        range(12, 2, -1)
    )
    assert packet["budget"] == {"used": 12, "max": 12, "exhausted": True}


def test_malformed_attempt_is_isolated_as_degraded_packet(
    tmp_path: Path, monkeypatch
):
    manifest = _manifest()
    manifest["packets"].append(
        {
            **manifest["packets"][0],
            "id": "BUILDER-UI-2",
            "title": "Keep healthy packet visible",
        }
    )
    db_path = tmp_path / "builder.db"
    repo = _git_repo(tmp_path)
    applied = bi.apply_manifest(manifest, db_path=db_path, repo_root=repo)
    attempt = ba.start_attempt(INITIATIVE_ID, PACKET_ID, db_path=db_path)
    conn = bq.connect(db_path)
    try:
        conn.execute(
            "UPDATE packet_attempts SET implementation_json = ? WHERE id = ?",
            ("{malformed", attempt["id"]),
        )
        conn.commit()
    finally:
        conn.close()

    snapshot = builder_status.build_status_snapshot(db_path=db_path)
    packets = snapshot["initiatives"][0]["packets"]

    assert snapshot["integrity"] == {
        "state": "partial",
        "partial_packets": 1,
        "total_packets": 2,
    }
    assert packets[0]["data_quality"]["state"] == "partial"
    assert packets[0]["attempt_history"][0]["implementation"] is None
    assert "implementation evidence is malformed" in packets[0]["data_quality"]["issues"]
    assert packets[1]["packet_id"] == "BUILDER-UI-2"
    assert packets[1]["data_quality"] == {"state": "complete", "issues": []}
    assert applied["packets"][1]["task_id"] == packets[1]["task_id"]

    def partial_snapshot() -> dict:
        return snapshot

    monkeypatch.setattr(builder_status, "build_status_snapshot", partial_snapshot)
    fact = runtime_manifest._builder_fact(
        observed_at="2026-07-17T03:00:00Z",
        valid_until="2026-07-17T03:00:05Z",
    )
    assert fact["state"] == "degraded"
    assert fact["value"] == snapshot
    assert fact["reason"] == "Builder status includes 1 partial packet record."


@pytest.mark.parametrize(
    ("task_state", "run_state", "attempt", "exhausted", "expected"),
    [
        (bq.FAILED, None, {"implementation_status": "failed"}, False, "implementation"),
        (bq.RUNNING, bq.RUN_LEASE_LOST, None, False, "identity"),
        (bq.RUNNING, bq.RUN_SCOPE_VIOLATION, None, False, "scope"),
        (bq.BLOCKED, None, {"validation_status": "failed"}, False, "validation"),
        (bq.BLOCKED, None, {"review_verdict": "reject"}, False, "review"),
        (bq.BLOCKED, None, {"outcome": "crashed"}, False, "infrastructure"),
        (bq.CANCELLED, None, None, False, "cancelled"),
        (bq.BLOCKED, None, None, False, "blocked"),
        (bq.BLOCKED, None, None, True, "exhausted"),
    ],
)
def test_failure_categories_are_canonical(
    task_state: str,
    run_state: str | None,
    attempt: dict | None,
    exhausted: bool,
    expected: str,
):
    run = {"state": run_state} if run_state else None

    assert builder_status._failure_kind(
        task_state=task_state,
        exhausted=exhausted,
        attempt=attempt,
        run=run,
        run_infrastructure_failure=False,
        last_event=None,
    ) == expected


def test_publication_projection_allows_only_safe_github_links(tmp_path: Path):
    db_path, _repo, task_id = _apply_manifest(tmp_path)
    bq.attach_pr(
        task_id,
        182,
        pr_url="https://github.com/jacob202/kitty/pull/182",
        head_sha="a" * 40,
        checks_state="success",
        review_state="approved",
        db_path=db_path,
    )

    packet = builder_status.build_status_snapshot(db_path=db_path)["initiatives"][0]["packets"][0]

    assert packet["publication"] == {
        "pr_number": 182,
        "pr_url": "https://github.com/jacob202/kitty/pull/182",
        "head_sha": "a" * 40,
        "checks_state": "success",
        "review_state": "approved",
        "merged": False,
        "merged_at": None,
        "updated_at": packet["publication"]["updated_at"],
    }

    conn = bq.connect(db_path)
    try:
        conn.execute(
            "UPDATE pr_links SET pr_url = ? WHERE task_id = ?",
            ("file:///private/unsafe/report.html", task_id),
        )
        conn.commit()
    finally:
        conn.close()

    unsafe_packet = builder_status.build_status_snapshot(db_path=db_path)["initiatives"][0]["packets"][0]
    assert unsafe_packet["publication"]["pr_url"] is None
    assert "publication URL is not a safe GitHub HTTPS link" in unsafe_packet["data_quality"]["issues"]

    conn = bq.connect(db_path)
    try:
        conn.execute(
            "UPDATE pr_links SET pr_url = ? WHERE task_id = ?",
            ("https://github.com/jacob202/kitty/issues/182", task_id),
        )
        conn.commit()
    finally:
        conn.close()

    non_pr_packet = builder_status.build_status_snapshot(db_path=db_path)["initiatives"][0]["packets"][0]
    assert non_pr_packet["publication"]["pr_url"] is None


def test_safe_messages_redact_secrets_paths_and_bound_length():
    message = (
        "authorization: Bearer super-secret-token "
        "token=another-secret /private/unsafe/worker.log "
        + "x" * 700
    )

    projected = builder_status._safe_message(message)

    assert projected is not None
    assert "super-secret-token" not in projected
    assert "another-secret" not in projected
    assert "/private/unsafe/worker.log" not in projected
    assert "[redacted]" in projected
    assert "[path]" in projected
    assert len(projected) == 500


def test_lease_projection_uses_composite_packet_identity(tmp_path: Path):
    db_path, repo, _task_id = _apply_manifest(tmp_path)
    second_manifest = _manifest()
    second_manifest["initiative_id"] = "builder-ui-second"
    second_manifest["title"] = "Second initiative with repeated packet id"
    bi.apply_manifest(second_manifest, db_path=db_path, repo_root=repo)
    durable_base = bi.get_initiative(INITIATIVE_ID, db_path=db_path)["packets"][0]["base_sha"]
    _attempt, lease = ba.claim_and_start_attempt(
        INITIATIVE_ID,
        PACKET_ID,
        worker_id="worker-composite",
        branch="feat/composite-lease",
        worktree_path=str(tmp_path / "composite-worktree"),
        base_sha=durable_base,
        db_path=db_path,
    )

    snapshot = builder_status.build_status_snapshot(db_path=db_path)
    packets = {
        initiative["initiative_id"]: initiative["packets"][0]
        for initiative in snapshot["initiatives"]
    }

    assert packets[INITIATIVE_ID]["lease"]["id"] == lease["lease_id"]
    assert packets["builder-ui-second"]["lease"] is None


def test_snapshot_query_count_is_constant_with_packet_count(tmp_path: Path, monkeypatch):
    real_connect = bq.connect
    select_counts: list[int] = []

    def traced_connect(db_path=None):
        conn = real_connect(db_path)
        conn.set_trace_callback(
            lambda statement: select_counts.append(1)
            if statement.lstrip().upper().startswith(("SELECT", "WITH"))
            else None
        )
        return conn

    def prepare_snapshot(packet_count: int, root: Path) -> Path:
        root.mkdir()
        db_path = root / "builder.db"
        repo = _git_repo(root)
        manifest = _manifest()
        manifest["packets"] = [
            {
                **manifest["packets"][0],
                "id": f"BUILDER-UI-{index}",
                "title": f"Packet {index}",
            }
            for index in range(1, packet_count + 1)
        ]
        bi.apply_manifest(manifest, db_path=db_path, repo_root=repo)
        ba.init_db(db_path)
        return db_path

    one_packet_db = prepare_snapshot(1, tmp_path / "one")
    twelve_packet_db = prepare_snapshot(12, tmp_path / "twelve")
    monkeypatch.setattr(ba, "init_db", lambda _db_path=None: None)
    monkeypatch.setattr(bq, "connect", traced_connect)

    def query_count(db_path: Path) -> int:
        select_counts.clear()
        builder_status.build_status_snapshot(db_path=db_path)
        return len(select_counts)

    one_packet = query_count(one_packet_db)
    twelve_packets = query_count(twelve_packet_db)

    assert one_packet == twelve_packets
    assert one_packet == builder_status.SNAPSHOT_QUERY_COUNT


def test_snapshot_serialization_is_deterministic(tmp_path: Path):
    db_path, _repo, _task_id = _apply_manifest(tmp_path)

    first = json.dumps(builder_status.build_status_snapshot(db_path=db_path), sort_keys=True)
    second = json.dumps(builder_status.build_status_snapshot(db_path=db_path), sort_keys=True)

    assert first == second
