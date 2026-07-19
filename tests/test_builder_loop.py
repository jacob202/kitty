"""Tests for gateway/builder_loop.py — KB-S3b bounded repair loop.

Integration-style: real git repo, real run_worker executions with tiny shell
workers that write (or fail to write) contract files. No LLMs, no network.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from gateway import builder_attempt as ba
from gateway import builder_initiative as bi
from gateway import builder_loop as bl
from gateway import builder_queue as bq

INITIATIVE = "loop-test"
PACKET = "LP-1"

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)
    (root / "README.md").write_text("hello\n")
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=root, check=True)
    return root


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    p = tmp_path / "kittybuilder" / "builder_queue.db"
    ba.init_db(p)
    return p


def _apply(db_path: Path, *, max_attempts: int = 2,
           validation_commands: list[str] | None = None,
           repo_root: Path | None = None) -> str:
    """Apply a one-packet manifest; returns the packet's task_id."""
    manifest = {
        "manifest_version": 1,
        "initiative_id": INITIATIVE,
        "title": "Loop test",
        "packets": [
            {
                "id": PACKET,
                "title": "Loop packet",
                "objective": "Produce done.txt.",
                "acceptance_criteria": ["done.txt exists"],
                "allowed_paths": ["done.txt"],
                "policy": {"max_attempts": max_attempts},
                "validation_commands":
                    validation_commands
                    if validation_commands is not None
                    else ["test -f done.txt"],
            }
        ],
    }
    result = bi.apply_manifest(manifest, db_path=db_path, repo_root=repo_root)
    return result["packets"][0]["task_id"]


_GOOD_IMPL = json.dumps(
    {"contract_version": 1, "status": "completed", "summary": "did it"}
)
_APPROVE = json.dumps(
    {"contract_version": 1, "verdict": "approve", "summary": "fine"}
)


def _script(tmp_path: Path, name: str, body: str) -> list[str]:
    path = tmp_path / name
    path.write_text("#!/bin/bash\nset -e\n" + body, encoding="utf-8")
    path.chmod(0o755)
    return ["bash", str(path)]


def _good_worker(tmp_path: Path) -> list[str]:
    return _script(
        tmp_path,
        "worker.sh",
        f"echo ok > done.txt\ncat > \"$KB_RESULT_PATH\" <<'EOF'\n{_GOOD_IMPL}\nEOF\n",
    )


def _approve_reviewer(tmp_path: Path) -> list[str]:
    # Enforce the same required-env contract as
    # scripts/kittybuilder_opencode_reviewer.sh so a wiring regression in
    # _run_review_command's env_extra fails loudly in every reviewer test.
    return _script(
        tmp_path,
        "reviewer.sh",
        ': "${KB_TASK_ID:?KB_TASK_ID is required}"\n'
        ': "${KB_ATTEMPT_ID:?KB_ATTEMPT_ID is required}"\n'
        ': "${KB_CONTEXT_MANIFEST_PATH:?KB_CONTEXT_MANIFEST_PATH is required}"\n'
        f"cat > \"$KB_REVIEW_RESULT_PATH\" <<'EOF'\n{_APPROVE}\nEOF\n",
    )


# ---------------------------------------------------------------------------
# Loop behavior
# ---------------------------------------------------------------------------


class TestRunPacket:
    def test_preflight_failure_does_not_consume_attempt_budget(
        self, repo: Path, db_path: Path, tmp_path: Path, monkeypatch
    ):
        task_id = _apply(db_path, repo_root=repo)

        def fail_preflight(*args, **kwargs):
            from gateway.builder_runner import RunnerError

            raise RunnerError("worktree root is not writable")

        monkeypatch.setattr(bl, "preflight_worktree", fail_preflight, raising=False)

        with pytest.raises(bl.LoopError, match="preflight failed"):
            bl.run_packet(
                INITIATIVE,
                PACKET,
                worker_command=["false"],
                repo_root=repo,
                db_path=db_path,
            )

        assert ba.list_attempts(INITIATIVE, PACKET, db_path=db_path) == []
        assert bq.get_task(task_id, db_path=db_path)["state"] == bq.QUEUED
        events = bq.list_events(task_id, db_path=db_path)
        failure = next(event for event in events if event["type"] == "infrastructure_failed")
        assert failure["payload"]["counts_toward_budget"] is False

    def test_stale_attempt_reconciled_on_entry(
        self, repo: Path, db_path: Path, tmp_path: Path
    ):
        """Open attempts from a previous crash are closed as crashed on entry."""
        task_id = _apply(db_path, repo_root=repo)
        # Simulate a stale attempt: open one, close it already crashed with budget
        # exclusion, then open another and leave it in flight (outcome IS NULL).
        first = ba.start_attempt(INITIATIVE, PACKET, db_path=db_path)
        ba.close_attempt(first["id"], ba.ATTEMPT_FAILED, db_path=db_path)
        stale = ba.start_attempt(INITIATIVE, PACKET, db_path=db_path)

        # Now run_packet should reconcile the stale attempt before proceeding.
        result = bl.run_packet(
            INITIATIVE, PACKET,
            worker_command=_good_worker(tmp_path),
            repo_root=repo, db_path=db_path,
        )
        assert result["outcome"] == "succeeded"

        # The stale attempt is now closed as crashed.
        closed = ba.get_attempt(stale["id"], db_path=db_path)
        assert closed is not None
        assert closed["outcome"] == ba.ATTEMPT_CRASHED

        # Run-manifest was written with crashed outcome.
        attempt_dir = db_path.parent / "attempts" / task_id / str(stale["id"])
        manifest_path = attempt_dir / "run-manifest.json"
        assert manifest_path.exists()
        manifest = json.loads(manifest_path.read_text())
        assert manifest["outcome"] == "crashed"
        assert manifest["failure"]["sha256"]

        # infrastructure_failed event was logged.
        events = bq.list_events(task_id, db_path=db_path)
        stale_events = [
            e
            for e in events
            if e["type"] == "infrastructure_failed"
            and e.get("payload", {}).get("phase") == "stale_attempt_reconciliation"
        ]
        assert len(stale_events) == 1
        assert (
            stale_events[0]["payload"]["counts_toward_budget"] is False
        )

    def test_blocked_task_with_bound_stale_attempt_recovers_once(
        self, repo: Path, db_path: Path, tmp_path: Path
    ):
        """A crashed runner's paired task and branch leases recover together."""
        task_id = _apply(db_path, repo_root=repo)
        claimed = bq.claim_task(task_id, "dead-worker", db_path=db_path)
        bq.worker_transition_task(
            task_id,
            bq.RUNNING,
            claimed["lease_token"],
            claimed["claim_version"],
            db_path=db_path,
        )
        bq.worker_transition_task(
            task_id,
            bq.BLOCKED,
            claimed["lease_token"],
            claimed["claim_version"],
            payload={"reason": "runner_process_lost"},
            db_path=db_path,
        )

        from gateway.builder_brief import default_branch_name

        stale, lease = ba.claim_and_start_attempt(
            INITIATIVE,
            PACKET,
            worker_id="dead-packet-worker",
            branch=default_branch_name({"id": task_id}),
            worktree_path=str(
                repo / ".worktrees" / "kittybuilder" / task_id
            ),
            base_sha=ba.get_packet_base_sha(
                INITIATIVE, PACKET, db_path=db_path
            ),
            db_path=db_path,
        )

        result = bl.run_packet(
            INITIATIVE,
            PACKET,
            worker_command=_good_worker(tmp_path),
            repo_root=repo,
            db_path=db_path,
        )

        assert result["outcome"] == bl.LOOP_SUCCEEDED
        closed = ba.get_attempt(stale["id"], db_path=db_path)
        assert closed is not None
        assert closed["outcome"] == ba.ATTEMPT_CRASHED
        assert bq.get_branch_lease(lease["lease_id"], db_path=db_path) is None
        events = bq.list_events(task_id, db_path=db_path)
        assert sum(event["type"] == "operator_released" for event in events) == 1

    def test_crashed_attempt_does_not_consume_budget(
        self, repo: Path, db_path: Path, tmp_path: Path
    ):
        """A crashed attempt preserves budget for real retries."""
        _apply(db_path, max_attempts=2, repo_root=repo)

        # Simulate two crashed attempts — neither should consume budget.
        for _ in range(2):
            a = ba.start_attempt(INITIATIVE, PACKET, db_path=db_path)
            ba.close_attempt(a["id"], ba.ATTEMPT_CRASHED, db_path=db_path)

        # Budget not exhausted (0/2 consumed) — attempt 3 is allowed.
        third = ba.start_attempt(INITIATIVE, PACKET, db_path=db_path)
        assert third["attempt_no"] == 3
        # Close it as real failure — this consumes 1 of the 2 budget.
        ba.close_attempt(third["id"], ba.ATTEMPT_FAILED, db_path=db_path)

        # Budget still not exhausted (1/2 consumed) — attempt 4 is allowed.
        fourth = ba.start_attempt(INITIATIVE, PACKET, db_path=db_path)
        assert fourth["attempt_no"] == 4

        # Close fourth as crashed too — budget still 1/2.
        ba.close_attempt(fourth["id"], ba.ATTEMPT_CRASHED, db_path=db_path)

        # Run a real loop — should use attempt 5 and succeed.
        result = bl.run_packet(
            INITIATIVE, PACKET,
            worker_command=_good_worker(tmp_path),
            repo_root=repo, db_path=db_path,
        )
        assert result["outcome"] == "succeeded"
        assert result["attempts"][0]["attempt_no"] == 5

    def test_success_first_attempt(self, repo: Path, db_path: Path, tmp_path: Path):
        task_id = _apply(db_path, repo_root=repo)
        result = bl.run_packet(
            INITIATIVE, PACKET,
            worker_command=_good_worker(tmp_path),
            review_command=_approve_reviewer(tmp_path),
            repo_root=repo, db_path=db_path,
        )
        assert result["outcome"] == "succeeded"
        assert len(result["attempts"]) == 1
        entry = result["attempts"][0]
        assert entry["implementation_status"] == "completed"
        assert entry["validation_status"] == "passed"
        assert entry["review_verdict"] == "approve"
        manifest_path = Path(entry["manifest_path"])
        assert manifest_path.parts[-4:-1] == ("attempts", task_id, "1")
        manifest = json.loads((manifest_path).read_text())
        assert manifest["outcome"] == "succeeded"
        assert manifest["worker_run"]["run_id"] == entry["run_id"]
        assert manifest["bundle_sha256"]
        assert manifest["context_manifest"]["sha256"]
        assert manifest["context_manifest"]["task_id"] == task_id
        assert manifest["context_manifest"]["attempt_id"] == entry["attempt_id"]
        assert manifest["validation"]["commands"][0]["command_sha256"]
        assert "output_tail" not in manifest["validation"]["commands"][0]
        assert manifest["review"]["summary"]["sha256"]
        assert "fine" not in json.dumps(manifest)
        assert entry["worktree_cleanup"] == "removed"
        assert not (repo / ".worktrees" / "kittybuilder" / task_id).exists()

        attempt = ba.get_attempt(entry["attempt_id"], db_path=db_path)
        assert attempt["outcome"] == "succeeded"
        assert attempt["implementation"]["summary"] == "did it"
        assert attempt["review"]["verdict"] == "approve"
        # Shadow mode: the task ends blocked for the operator/KB-S4.
        assert bq.get_task(task_id, db_path=db_path)["state"] == bq.BLOCKED

    def test_validation_only_when_no_reviewer(
        self, repo: Path, db_path: Path, tmp_path: Path
    ):
        _apply(db_path, repo_root=repo)
        result = bl.run_packet(
            INITIATIVE, PACKET,
            worker_command=_good_worker(tmp_path),
            repo_root=repo, db_path=db_path,
        )
        assert result["outcome"] == "succeeded"
        assert "review_verdict" not in result["attempts"][0]
        assert result["attempts"][0]["worktree_cleanup"] == "removed"

    def test_success_without_done_marker_keeps_worktree_for_inspection(
        self, repo: Path, db_path: Path, tmp_path: Path
    ):
        _apply(db_path, validation_commands=[], repo_root=repo)
        worker = _script(
            tmp_path,
            "no_marker.sh",
            f"cat > \"$KB_RESULT_PATH\" <<'EOF'\n{_GOOD_IMPL}\nEOF\n",
        )

        result = bl.run_packet(
            INITIATIVE, PACKET,
            worker_command=worker,
            repo_root=repo, db_path=db_path,
        )

        task_id = result["task_id"]
        assert result["outcome"] == "succeeded"
        assert result["attempts"][0]["worktree_cleanup"] == "kept_no_done_marker"
        assert (repo / ".worktrees" / "kittybuilder" / task_id).exists()

    def test_repair_retry_then_success(
        self, repo: Path, db_path: Path, tmp_path: Path
    ):
        """First attempt fails validation; the loop retries and succeeds."""
        _apply(db_path, repo_root=repo)
        marker = tmp_path / "second_try_marker"
        worker = _script(
            tmp_path,
            "flaky.sh",
            (
                f"if [ -f \"{marker}\" ]; then echo ok > done.txt; fi\n"
                f"touch \"{marker}\"\n"
                f"cat > \"$KB_RESULT_PATH\" <<'EOF'\n{_GOOD_IMPL}\nEOF\n"
            ),
        )
        result = bl.run_packet(
            INITIATIVE, PACKET,
            worker_command=worker,
            repo_root=repo, db_path=db_path,
        )
        assert result["outcome"] == "succeeded"
        assert [e["outcome"] for e in result["attempts"]] == ["failed", "succeeded"]
        assert result["attempts"][0]["failure"] == "deterministic validation failed"
        # Second attempt's bundle carried the first attempt's digest.
        second = ba.get_attempt(result["attempts"][1]["attempt_id"], db_path=db_path)
        assert second["bundle"]["prior_attempts"][0]["outcome"] == "failed"

    def test_budget_exhaustion_leaves_task_blocked(
        self, repo: Path, db_path: Path, tmp_path: Path
    ):
        task_id = _apply(db_path, max_attempts=2, repo_root=repo)
        worker = _script(
            tmp_path,
            "alwaysfail.sh",
            f"cat > \"$KB_RESULT_PATH\" <<'EOF'\n{_GOOD_IMPL}\nEOF\n",
        )  # never creates done.txt → validation always fails
        result = bl.run_packet(
            INITIATIVE, PACKET,
            worker_command=worker,
            repo_root=repo, db_path=db_path,
        )
        assert result["outcome"] == "exhausted"
        assert "2/2" in result["reason"]
        assert [e["outcome"] for e in result["attempts"]] == ["failed", "failed"]
        assert bq.get_task(task_id, db_path=db_path)["state"] == bq.BLOCKED

    def test_missing_result_file_fails_attempt(
        self, repo: Path, db_path: Path, tmp_path: Path
    ):
        _apply(db_path, max_attempts=1, repo_root=repo)
        worker = _script(tmp_path, "silent.sh", "echo ok > done.txt\n")
        result = bl.run_packet(
            INITIATIVE, PACKET,
            worker_command=worker,
            repo_root=repo, db_path=db_path,
        )
        assert result["outcome"] == "exhausted"
        assert "did not write" in result["attempts"][0]["failure"]
        task_id = result["task_id"]
        assert (repo / ".worktrees" / "kittybuilder" / task_id).exists()

    def test_invalid_contract_fails_attempt_and_stores_nothing(
        self, repo: Path, db_path: Path, tmp_path: Path
    ):
        _apply(db_path, max_attempts=1, repo_root=repo)
        worker = _script(
            tmp_path,
            "badcontract.sh",
            "echo '{\"status\": \"shipped\"}' > \"$KB_RESULT_PATH\"\n",
        )
        result = bl.run_packet(
            INITIATIVE, PACKET,
            worker_command=worker,
            repo_root=repo, db_path=db_path,
        )
        assert result["outcome"] == "exhausted"
        entry = result["attempts"][0]
        assert "contract invalid" in entry["failure"]
        attempt = ba.get_attempt(entry["attempt_id"], db_path=db_path)
        assert attempt["implementation"] is None

    def test_review_rejection_fails_attempt(
        self, repo: Path, db_path: Path, tmp_path: Path
    ):
        _apply(db_path, max_attempts=1, repo_root=repo)
        reviewer = _script(
            tmp_path,
            "reject.sh",
            "cat > \"$KB_REVIEW_RESULT_PATH\" <<'EOF'\n"
            + json.dumps(
                {
                    "contract_version": 1,
                    "verdict": "request_changes",
                    "summary": "not enough",
                }
            )
            + "\nEOF\n",
        )
        result = bl.run_packet(
            INITIATIVE, PACKET,
            worker_command=_good_worker(tmp_path),
            review_command=reviewer,
            repo_root=repo, db_path=db_path,
        )
        assert result["outcome"] == "exhausted"
        assert "request_changes" in result["attempts"][0]["failure"]

    def test_reviewer_cannot_approve_a_changed_diff(
        self, repo: Path, db_path: Path, tmp_path: Path
    ):
        _apply(db_path, max_attempts=1, repo_root=repo)
        reviewer = _script(
            tmp_path,
            "drifting-reviewer.sh",
            f"echo drift >> done.txt\n"
            f"cat > \"$KB_REVIEW_RESULT_PATH\" <<'EOF'\n{_APPROVE}\nEOF\n",
        )
        result = bl.run_packet(
            INITIATIVE,
            PACKET,
            worker_command=_good_worker(tmp_path),
            review_command=reviewer,
            repo_root=repo,
            db_path=db_path,
        )
        assert result["outcome"] == "exhausted"
        assert "review evidence invalid" in result["attempts"][0]["failure"]

    def test_refuses_non_queued_task(self, repo: Path, db_path: Path, tmp_path: Path):
        task_id = _apply(db_path, repo_root=repo)
        bq.claim_task(task_id, "someone-else", db_path=db_path)
        with pytest.raises(bl.LoopError, match="claimed"):
            bl.run_packet(
                INITIATIVE, PACKET,
                worker_command=_good_worker(tmp_path),
                repo_root=repo, db_path=db_path,
            )

    def test_runner_error_is_recorded_before_re_raising(
        self, repo: Path, db_path: Path, tmp_path: Path, monkeypatch
    ):
        task_id = _apply(db_path, repo_root=repo)

        def fail_runner(*args, **kwargs):
            raise RuntimeError("runner exploded")

        monkeypatch.setattr(bl, "run_worker", fail_runner)
        with pytest.raises(bl.LoopError, match="runner exploded"):
            bl.run_packet(
                INITIATIVE, PACKET,
                worker_command=_good_worker(tmp_path),
                repo_root=repo, db_path=db_path,
            )

        attempt = ba.get_attempt(1, db_path=db_path)
        assert attempt is not None
        assert attempt["outcome"] == ba.ATTEMPT_CRASHED
        manifest_path = db_path.parent / "attempts" / task_id / "1" / "run-manifest.json"
        manifest = json.loads(manifest_path.read_text())
        assert manifest["outcome"] == "crashed"
        assert manifest["failure"]["sha256"]
        assert "runner exploded" not in json.dumps(manifest)
        assert bq.verify_branch_lease(PACKET, db_path=db_path) is None
        event = next(
            event
            for event in bq.list_events(task_id, db_path=db_path)
            if event["type"] == "infrastructure_failed"
        )
        assert event["payload"]["counts_toward_budget"] is False

    def test_cancelled_run_aborts_once_and_releases_lease(
        self, repo: Path, db_path: Path, tmp_path: Path, monkeypatch
    ):
        _apply(db_path, repo_root=repo)

        def cancelled_runner(*args, **kwargs):
            return {
                "id": "run-cancelled",
                "state": bq.RUN_CANCELLED,
                "exit_code": -15,
                "final_report": {
                    "branch": "unused-after-cancel",
                    "worktree": "unused-after-cancel",
                    "start_sha": "unused-after-cancel",
                    "changed_paths": [],
                    "scope_violations": [],
                },
            }

        monkeypatch.setattr(bl, "run_worker", cancelled_runner)
        result = bl.run_packet(
            INITIATIVE,
            PACKET,
            worker_command=_good_worker(tmp_path),
            repo_root=repo,
            db_path=db_path,
        )

        assert result["outcome"] == bl.LOOP_CANCELLED
        assert len(result["attempts"]) == 1
        attempt = ba.get_attempt(
            result["attempts"][0]["attempt_id"], db_path=db_path
        )
        assert attempt is not None
        assert attempt["outcome"] == ba.ATTEMPT_ABORTED
        assert bq.verify_branch_lease(PACKET, db_path=db_path) is None

    def test_extra_env_cannot_override_credential_isolation(self, db_path: Path):
        from gateway.builder_runner import run_worker

        with pytest.raises(ValueError, match="credential isolation"):
            run_worker(
                "kb_whatever_0000",
                ["true"],
                extra_env={"GITHUB_TOKEN": "sneaky"},
                db_path=db_path,
            )


# ---------------------------------------------------------------------------
# P027 — truthful closeout after a crash-recovery cycle
# ---------------------------------------------------------------------------


class TestTruthfulCloseout:
    def test_rollup_reports_recovered_success_truthfully(
        self, repo: Path, db_path: Path, tmp_path: Path
    ):
        """After crash + recovery + success, the rollup tells the whole story:
        the crash is visible as an infrastructure failure, the attempt ledger
        shows crashed → succeeded, and the packet awaits operator review
        rather than reading as stuck in progress."""
        _apply(db_path, repo_root=repo)
        ba.start_attempt(INITIATIVE, PACKET, db_path=db_path)  # stale crash

        result = bl.run_packet(
            INITIATIVE, PACKET,
            worker_command=_good_worker(tmp_path),
            repo_root=repo, db_path=db_path,
        )
        assert result["outcome"] == bl.LOOP_SUCCEEDED

        status = bi.initiative_status(INITIATIVE, db_path=db_path)
        assert status["in_progress"] == [PACKET]
        assert status["failed"] == []
        assert status["exhausted"] == []

        evidence = status["evidence"][PACKET]
        assert evidence["infrastructure_failures"] == 1
        assert evidence["next_action"] == "operator_review"

        attempts = ba.list_attempts(INITIATIVE, PACKET, db_path=db_path)
        assert [a["outcome"] for a in attempts] == [
            ba.ATTEMPT_CRASHED,
            ba.ATTEMPT_SUCCEEDED,
        ]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


class TestCli:
    def test_run_packet_cli(
        self, repo: Path, db_path: Path, tmp_path: Path, capsys, monkeypatch
    ):
        from gateway import builder_loop
        from gateway.builder_cli import main

        monkeypatch.setattr(bq, "BUILDER_QUEUE_DB", db_path)
        _apply(db_path, repo_root=repo)

        # Route the loop at the test repo without threading a CLI flag through.
        real_run_packet = builder_loop.run_packet

        def patched(*args, **kwargs):
            kwargs["repo_root"] = repo
            return real_run_packet(*args, **kwargs)

        monkeypatch.setattr(builder_loop, "run_packet", patched)

        worker = _good_worker(tmp_path)
        assert main(
            ["initiative", "run-packet", INITIATIVE, PACKET,
             "--worker-command", json.dumps(worker)]
        ) == 0
        out = capsys.readouterr().out
        assert "succeeded" in out

    def test_run_packet_cli_rejects_bad_command_json(self, capsys):
        from gateway.builder_cli import main

        assert main(
            ["initiative", "run-packet", INITIATIVE, PACKET,
             "--worker-command", "not-json"]
        ) == 1
        assert "error" in capsys.readouterr().err

    def test_run_packet_cli_accepts_watch_flag(
        self, repo: Path, db_path: Path, tmp_path: Path, capsys, monkeypatch
    ):
        from gateway import builder_loop
        from gateway.builder_cli import main

        monkeypatch.setattr(bq, "BUILDER_QUEUE_DB", db_path)
        _apply(db_path, repo_root=repo)
        real_run_packet = builder_loop.run_packet

        def patched(*args, **kwargs):
            kwargs["repo_root"] = repo
            return real_run_packet(*args, **kwargs)

        monkeypatch.setattr(builder_loop, "run_packet", patched)
        assert main(
            [
                "initiative",
                "run-packet",
                INITIATIVE,
                PACKET,
                "--worker-command",
                json.dumps(_good_worker(tmp_path)),
                "--watch",
            ]
        ) == 0
        assert "manifest" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# Phase 2 integration — lease + identity end-to-end scenarios
# ---------------------------------------------------------------------------


class TestLeaseIdentityIntegration:
    """End-to-end tests for the branch lease and identity verification wiring."""

    def test_two_packets_cannot_claim_same_branch(
        self, repo: Path, db_path: Path, tmp_path: Path
    ):
        """Two packets targeting the same branch/worker can't run concurrently."""
        _task1 = _apply(db_path, repo_root=repo, max_attempts=2)

        manifest2 = {
            "manifest_version": 1,
            "initiative_id": "loop-test-2",
            "title": "Second packet",
            "packets": [
                {
                    "id": "LP-2",
                    "title": "Second",
                    "objective": "Do something else.",
                    "acceptance_criteria": ["result.txt exists"],
                    "allowed_paths": ["result.txt"],
                    "policy": {"max_attempts": 2},
                    "validation_commands": ["test -f result.txt"],
                }
            ],
        }
        bi.apply_manifest(manifest2, db_path=db_path, repo_root=repo)

        result1 = bl.run_packet(
            INITIATIVE, PACKET,
            worker_command=_good_worker(tmp_path),
            repo_root=repo, db_path=db_path,
        )
        assert result1["outcome"] == "succeeded"

        good_worker2 = _script(
            tmp_path, "worker2.sh",
            "echo ok > result.txt\n"
            f"cat > \"$KB_RESULT_PATH\" <<'EOF'\n{_GOOD_IMPL}\nEOF\n",
        )
        result2 = bl.run_packet(
            "loop-test-2", "LP-2",
            worker_command=good_worker2,
            repo_root=repo, db_path=db_path,
        )
        assert result2["outcome"] == "succeeded"

    def test_wrong_branch_execution_rejected_by_identity(
        self, repo: Path, db_path: Path, tmp_path: Path
    ):
        """Worker that makes unsigned commits is caught by post-worker identity."""
        _task_id = _apply(db_path, repo_root=repo)

        unsigned_worker = _script(
            tmp_path,
            "unsigned.sh",
            "git config user.email 'bot@test'\n"
            "git config user.name 'bot'\n"
            "echo ok > done.txt\n"
            "git add done.txt\n"
            "git commit -m 'unsigned commit'\n"
            f"cat > \"$KB_RESULT_PATH\" <<'EOF'\n{_GOOD_IMPL}\nEOF\n",
        )
        result = bl.run_packet(
            INITIATIVE, PACKET,
            worker_command=unsigned_worker,
            repo_root=repo, db_path=db_path,
        )
        assert result["outcome"] == "exhausted"
        assert bq.verify_branch_lease(PACKET, db_path=db_path) is None
        assert result["attempts"][0]["identity_findings"][0]["field"] == "commits"

    def test_actual_branch_mismatch_rejected_by_identity(
        self, repo: Path, db_path: Path, tmp_path: Path
    ):
        """A worker detaching from the leased branch cannot be accepted."""
        _task_id = _apply(db_path, repo_root=repo, max_attempts=1)
        detached_worker = _script(
            tmp_path,
            "detached.sh",
            "git checkout --detach\n"
            "echo ok > done.txt\n"
            f"cat > \"$KB_RESULT_PATH\" <<'EOF'\n{_GOOD_IMPL}\nEOF\n",
        )

        result = bl.run_packet(
            INITIATIVE,
            PACKET,
            worker_command=detached_worker,
            repo_root=repo,
            db_path=db_path,
        )

        assert result["outcome"] == "exhausted"
        assert any(
            finding["field"] == "branch"
            for finding in result["attempts"][0]["identity_findings"]
        )
        assert bq.verify_branch_lease(PACKET, db_path=db_path) is None

    def test_forbidden_path_modification_escalates(
        self, repo: Path, db_path: Path, tmp_path: Path
    ):
        """Worker modifying files outside allowed_paths triggers escalation."""
        _task_id = _apply(db_path, repo_root=repo, max_attempts=1)

        forbidden_worker = _script(
            tmp_path,
            "forbidden.sh",
            "echo secret > secret.txt\n"
            "echo ok > done.txt\n"
            f"cat > \"$KB_RESULT_PATH\" <<'EOF'\n{_GOOD_IMPL}\nEOF\n",
        )
        result = bl.run_packet(
            INITIATIVE, PACKET,
            worker_command=forbidden_worker,
            repo_root=repo, db_path=db_path,
        )
        assert result["outcome"] == "exhausted"

    def test_foreign_commits_rejected(
        self, repo: Path, db_path: Path, tmp_path: Path
    ):
        """Worker that commits without packet marker is rejected."""
        _task_id = _apply(db_path, repo_root=repo)

        foreign_commit_worker = _script(
            tmp_path,
            "foreign.sh",
            "git config user.email 'evil@evil.com'\n"
            "git config user.name 'Evil'\n"
            "echo foreign > done.txt\n"
            "git add done.txt\n"
            "git commit -m 'no marker here'\n"
            f"cat > \"$KB_RESULT_PATH\" <<'EOF'\n{_GOOD_IMPL}\nEOF\n",
        )
        result = bl.run_packet(
            INITIATIVE, PACKET,
            worker_command=foreign_commit_worker,
            repo_root=repo, db_path=db_path,
        )
        assert result["outcome"] == "exhausted"
        assert bq.verify_branch_lease(PACKET, db_path=db_path) is None

    def test_crash_recovery_reconciles_lease(
        self, repo: Path, db_path: Path, tmp_path: Path
    ):
        """Stale lease from a crash is reconciled on next run_packet entry."""
        task_id = _apply(db_path, repo_root=repo)

        from gateway.builder_brief import default_branch_name
        wt_path = repo / ".worktrees" / "kittybuilder" / task_id
        branch = default_branch_name({"id": task_id})
        base_sha = ba.get_packet_base_sha(INITIATIVE, PACKET, db_path=db_path)

        attempt, lease = ba.claim_and_start_attempt(
            INITIATIVE, PACKET,
            worker_id="crashed-worker",
            branch=branch,
            worktree_path=str(wt_path),
            base_sha=base_sha,
            db_path=db_path,
        )

        # Reconcile the stale attempt+lease.
        reconciled = bl._reconcile_stale_attempts(
            INITIATIVE, PACKET, db_path=db_path, repo_root=repo,
        )
        assert len(reconciled) == 1

        # Now a normal run should succeed.
        result = bl.run_packet(
            INITIATIVE, PACKET,
            worker_command=_good_worker(tmp_path),
            repo_root=repo, db_path=db_path,
        )
        assert result["outcome"] == "succeeded"

    def test_owner_can_release_unrelated_packets_cannot(
        self, repo: Path, db_path: Path, tmp_path: Path
    ):
        """Only the lease owner can release; unrelated packets are rejected."""
        task_id = _apply(db_path, repo_root=repo)

        from gateway.builder_brief import default_branch_name
        wt_path = repo / ".worktrees" / "kittybuilder" / task_id
        branch = default_branch_name({"id": task_id})
        base_sha = ba.get_packet_base_sha(INITIATIVE, PACKET, db_path=db_path)

        attempt, lease = ba.claim_and_start_attempt(
            INITIATIVE, PACKET,
            worker_id="worker-A",
            branch=branch,
            worktree_path=str(wt_path),
            base_sha=base_sha,
            db_path=db_path,
        )

        with pytest.raises(bq.BranchLeaseConflictError):
            bq.release_branch_lease(
                lease["lease_id"], packet_id=PACKET,
                worker_id="worker-B", db_path=db_path,
            )

        bq.release_branch_lease(
            lease["lease_id"], packet_id=PACKET,
            worker_id="worker-A", db_path=db_path,
        )
        ba.close_attempt(attempt["id"], ba.ATTEMPT_CRASHED, db_path=db_path)

    def test_clean_in_scope_execution_succeeds(
        self, repo: Path, db_path: Path, tmp_path: Path
    ):
        """Clean in-scope execution reaches validation and review normally."""
        _task_id = _apply(db_path, repo_root=repo)
        reviewer = _approve_reviewer(tmp_path)

        result = bl.run_packet(
            INITIATIVE, PACKET,
            worker_command=_good_worker(tmp_path),
            review_command=reviewer,
            repo_root=repo, db_path=db_path,
        )
        assert result["outcome"] == "succeeded"

        attempts = ba.list_attempts(INITIATIVE, PACKET, db_path=db_path)
        assert len(attempts) == 1
        attempt = attempts[0]
        assert attempt["outcome"] == ba.ATTEMPT_SUCCEEDED
        assert attempt["lease_id"] is not None
        assert attempt["validation"] is not None
        assert attempt["review"] is not None
        assert bq.verify_branch_lease(PACKET, db_path=db_path) is None


# ---------------------------------------------------------------------------
# Blocker 1 — durable base SHA authority
# ---------------------------------------------------------------------------


class TestDurableBaseSHA:
    """Tests proving the base SHA is stored durably and never recomputed."""

    def test_packet_stores_base_sha_at_creation(
        self, repo: Path, db_path: Path
    ):
        """A packet stores its base SHA (full 40-char SHA) at creation time."""
        _task_id = _apply(db_path, repo_root=repo)
        conn = bq.connect(db_path)
        try:
            row = conn.execute(
                "SELECT base_sha FROM initiative_packets "
                "WHERE initiative_id = ? AND packet_id = ?",
                (INITIATIVE, PACKET),
            ).fetchone()
        finally:
            conn.close()
        assert row is not None
        base_sha = row["base_sha"]
        assert base_sha is not None
        assert len(base_sha) == 40
        assert all(c in "0123456789abcdef" for c in base_sha)
        expected = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo,
            capture_output=True, text=True,
        ).stdout.strip()
        assert base_sha == expected

    def test_main_advances_after_creation_uses_original_sha(
        self, repo: Path, db_path: Path, tmp_path: Path
    ):
        """Execution after main advances still uses the original stored SHA."""
        _task_id = _apply(db_path, repo_root=repo)
        original_sha = ba.get_packet_base_sha(INITIATIVE, PACKET, db_path=db_path)

        (repo / "newfile.txt").write_text("advance\n")
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(
            ["git", "commit", "-q", "-m", "advance main"], cwd=repo, check=True,
        )

        assert ba.get_packet_base_sha(INITIATIVE, PACKET, db_path=db_path) == original_sha

        result = bl.run_packet(
            INITIATIVE, PACKET,
            worker_command=_good_worker(tmp_path),
            repo_root=repo, db_path=db_path,
        )
        assert result["outcome"] == "succeeded"

    def test_fresh_run_packet_after_interruption_uses_same_stored_sha(
        self, repo: Path, db_path: Path, tmp_path: Path
    ):
        """A fresh run_packet() call after crash uses the same stored SHA."""
        _task_id = _apply(db_path, repo_root=repo)
        original_sha = ba.get_packet_base_sha(INITIATIVE, PACKET, db_path=db_path)

        stale = ba.start_attempt(INITIATIVE, PACKET, db_path=db_path)
        ba.close_attempt(stale["id"], ba.ATTEMPT_CRASHED, db_path=db_path)

        result = bl.run_packet(
            INITIATIVE, PACKET,
            worker_command=_good_worker(tmp_path),
            repo_root=repo, db_path=db_path,
        )
        assert result["outcome"] == "succeeded"
        assert ba.get_packet_base_sha(INITIATIVE, PACKET, db_path=db_path) == original_sha

    def test_missing_base_sha_fails_closed(
        self, repo: Path, db_path: Path, tmp_path: Path
    ):
        """A packet with no base_sha fails closed before worker execution."""
        _task_id = _apply(db_path, repo_root=repo)

        conn = bq.connect(db_path)
        try:
            conn.execute(
                "UPDATE initiative_packets SET base_sha = NULL "
                "WHERE initiative_id = ? AND packet_id = ?",
                (INITIATIVE, PACKET),
            )
            conn.commit()
        finally:
            conn.close()

        with pytest.raises(bl.LoopError, match="branch lease claim failed"):
            bl.run_packet(
                INITIATIVE, PACKET,
                worker_command=_good_worker(tmp_path),
                repo_root=repo, db_path=db_path,
            )

        assert ba.list_attempts(INITIATIVE, PACKET, db_path=db_path) == []


# ---------------------------------------------------------------------------
# Blocker 2 — crash-safe lease recovery
# ---------------------------------------------------------------------------


class TestCrashSafeLeaseRecovery:
    """Tests for atomic lease+attempt creation and stale lease reconciliation."""

    def test_atomic_lease_attempt_success(
        self, repo: Path, db_path: Path, tmp_path: Path
    ):
        """claim_and_start_attempt atomically creates both lease and attempt."""
        task_id = _apply(db_path, repo_root=repo)
        from gateway.builder_brief import default_branch_name
        wt_path = repo / ".worktrees" / "kittybuilder" / task_id
        branch = default_branch_name({"id": task_id})
        base_sha = ba.get_packet_base_sha(INITIATIVE, PACKET, db_path=db_path)

        attempt, lease = ba.claim_and_start_attempt(
            INITIATIVE, PACKET,
            worker_id="test-worker",
            branch=branch,
            worktree_path=str(wt_path),
            base_sha=base_sha,
            db_path=db_path,
        )
        assert attempt["lease_id"] == lease["lease_id"]
        assert lease["packet_id"] == PACKET
        assert lease["worker_id"] == "test-worker"

        with pytest.raises(bq.BranchLeaseConflictError):
            ba.close_attempt_and_release_lease(
                attempt["id"],
                ba.ATTEMPT_CRASHED,
                lease_id=lease["lease_id"],
                packet_id=PACKET,
                worker_id="wrong-worker",
                db_path=db_path,
            )
        assert ba.get_attempt(attempt["id"], db_path=db_path)["outcome"] is None
        assert bq.verify_branch_lease(PACKET, db_path=db_path) is not None

        ba.close_attempt_and_release_lease(
            attempt["id"],
            ba.ATTEMPT_CRASHED,
            lease_id=lease["lease_id"],
            packet_id=PACKET,
            worker_id="test-worker",
            db_path=db_path,
        )
        assert bq.verify_branch_lease(PACKET, db_path=db_path) is None

    def test_atomic_claim_rejects_non_durable_base_sha(
        self, repo: Path, db_path: Path
    ):
        """Caller-provided base metadata cannot override the packet authority."""
        task_id = _apply(db_path, repo_root=repo)
        from gateway.builder_brief import default_branch_name

        with pytest.raises(ba.AttemptStateError, match="durable packet base_sha"):
            ba.claim_and_start_attempt(
                INITIATIVE,
                PACKET,
                worker_id="test-worker",
                branch=default_branch_name({"id": task_id}),
                worktree_path=str(
                    repo / ".worktrees" / "kittybuilder" / task_id
                ),
                base_sha="f" * 40,
                db_path=db_path,
            )

        assert ba.list_attempts(INITIATIVE, PACKET, db_path=db_path) == []
        assert bq.verify_branch_lease(PACKET, db_path=db_path) is None

    def test_no_committed_lease_without_attempt(
        self, repo: Path, db_path: Path, tmp_path: Path
    ):
        """No lease can exist without its attempt through the atomic API."""
        task_id = _apply(db_path, repo_root=repo, max_attempts=1)
        from gateway.builder_brief import default_branch_name
        wt_path = repo / ".worktrees" / "kittybuilder" / task_id
        branch = default_branch_name({"id": task_id})
        base_sha = ba.get_packet_base_sha(INITIATIVE, PACKET, db_path=db_path)

        a = ba.start_attempt(INITIATIVE, PACKET, db_path=db_path)
        ba.close_attempt(a["id"], ba.ATTEMPT_FAILED, db_path=db_path)

        with pytest.raises(ba.AttemptLimitError):
            ba.claim_and_start_attempt(
                INITIATIVE, PACKET,
                worker_id="test-worker",
                branch=branch,
                worktree_path=str(wt_path),
                base_sha=base_sha,
                db_path=db_path,
            )

        conn = bq.connect(db_path)
        try:
            rows = conn.execute(
                "SELECT * FROM branch_leases WHERE packet_id = ?", (PACKET,)
            ).fetchall()
        finally:
            conn.close()
        assert len(rows) == 0

    def test_stale_attempt_with_lease_is_reconciled_and_lease_released(
        self, repo: Path, db_path: Path, tmp_path: Path
    ):
        """A stale attempt with a lease is closed as crashed and lease released."""
        task_id = _apply(db_path, repo_root=repo)
        from gateway.builder_brief import default_branch_name
        wt_path = repo / ".worktrees" / "kittybuilder" / task_id
        branch = default_branch_name({"id": task_id})
        base_sha = ba.get_packet_base_sha(INITIATIVE, PACKET, db_path=db_path)

        attempt, lease = ba.claim_and_start_attempt(
            INITIATIVE, PACKET,
            worker_id="crashed-worker",
            branch=branch,
            worktree_path=str(wt_path),
            base_sha=base_sha,
            db_path=db_path,
        )

        reconciled = bl._reconcile_stale_attempts(
            INITIATIVE, PACKET, db_path=db_path, repo_root=repo,
        )
        assert len(reconciled) == 1
        assert reconciled[0]["id"] == attempt["id"]

        closed = ba.get_attempt(attempt["id"], db_path=db_path)
        assert closed["outcome"] == ba.ATTEMPT_CRASHED

        conn = bq.connect(db_path)
        try:
            rows = conn.execute(
                "SELECT * FROM branch_leases WHERE lease_id = ?",
                (lease["lease_id"],),
            ).fetchall()
        finally:
            conn.close()
        assert len(rows) == 0

    def test_reconciliation_is_idempotent(
        self, repo: Path, db_path: Path, tmp_path: Path
    ):
        """Running reconciliation twice on the same stale attempt is idempotent."""
        task_id = _apply(db_path, repo_root=repo)
        from gateway.builder_brief import default_branch_name
        wt_path = repo / ".worktrees" / "kittybuilder" / task_id
        branch = default_branch_name({"id": task_id})
        base_sha = ba.get_packet_base_sha(INITIATIVE, PACKET, db_path=db_path)

        attempt, lease = ba.claim_and_start_attempt(
            INITIATIVE, PACKET,
            worker_id="crashed-worker",
            branch=branch,
            worktree_path=str(wt_path),
            base_sha=base_sha,
            db_path=db_path,
        )

        r1 = bl._reconcile_stale_attempts(
            INITIATIVE, PACKET, db_path=db_path, repo_root=repo,
        )
        assert len(r1) == 1

        r2 = bl._reconcile_stale_attempts(
            INITIATIVE, PACKET, db_path=db_path, repo_root=repo,
        )
        assert len(r2) == 0

    def test_reconciliation_cannot_release_other_packets_lease(
        self, repo: Path, db_path: Path, tmp_path: Path
    ):
        """Releasing a lease with wrong packet_id is rejected (ownership check)."""
        task_id = _apply(db_path, repo_root=repo)
        from gateway.builder_brief import default_branch_name
        wt_path = repo / ".worktrees" / "kittybuilder" / task_id
        branch = default_branch_name({"id": task_id})
        base_sha = ba.get_packet_base_sha(INITIATIVE, PACKET, db_path=db_path)

        attempt, lease = ba.claim_and_start_attempt(
            INITIATIVE, PACKET,
            worker_id="crashed-worker",
            branch=branch,
            worktree_path=str(wt_path),
            base_sha=base_sha,
            db_path=db_path,
        )

        with pytest.raises(bq.BranchLeaseConflictError):
            bq.release_branch_lease(
                lease["lease_id"],
                packet_id="wrong-packet",
                worker_id="crashed-worker",
                db_path=db_path,
            )

        conn = bq.connect(db_path)
        try:
            rows = conn.execute(
                "SELECT * FROM branch_leases WHERE lease_id = ?",
                (lease["lease_id"],),
            ).fetchall()
        finally:
            conn.close()
        assert len(rows) == 1

        bq.release_branch_lease(
            lease["lease_id"], packet_id=PACKET,
            worker_id="crashed-worker", db_path=db_path,
        )
        ba.close_attempt(attempt["id"], ba.ATTEMPT_CRASHED, db_path=db_path)

    def test_live_lease_is_not_stolen(
        self, repo: Path, db_path: Path, tmp_path: Path
    ):
        """A live attempt prevents contradictory second-attempt ownership."""
        task_id = _apply(db_path, repo_root=repo)
        from gateway.builder_brief import default_branch_name
        wt_path = repo / ".worktrees" / "kittybuilder" / task_id
        branch = default_branch_name({"id": task_id})
        base_sha = ba.get_packet_base_sha(INITIATIVE, PACKET, db_path=db_path)

        attempt1, lease1 = ba.claim_and_start_attempt(
            INITIATIVE, PACKET,
            worker_id="worker-A",
            branch=branch,
            worktree_path=str(wt_path),
            base_sha=base_sha,
            db_path=db_path,
        )

        with pytest.raises(ba.AttemptStateError, match="still open"):
            ba.claim_and_start_attempt(
                INITIATIVE, PACKET,
                worker_id="worker-B",
                branch=branch,
                worktree_path=str(wt_path) + "-other",
                base_sha=base_sha,
                db_path=db_path,
            )

        conn = bq.connect(db_path)
        try:
            row = conn.execute(
                "SELECT * FROM branch_leases WHERE lease_id = ?",
                (lease1["lease_id"],),
            ).fetchone()
        finally:
            conn.close()
        assert row is not None
        assert row["worker_id"] == "worker-A"

        bq.release_branch_lease(
            lease1["lease_id"], packet_id=PACKET,
            worker_id="worker-A", db_path=db_path,
        )
        ba.close_attempt(attempt1["id"], ba.ATTEMPT_CRASHED, db_path=db_path)

    def test_packet_can_reclaim_after_stale_reconciliation(
        self, repo: Path, db_path: Path, tmp_path: Path
    ):
        """After stale-attempt reconciliation, the packet can claim and execute."""
        task_id = _apply(db_path, repo_root=repo)
        from gateway.builder_brief import default_branch_name
        wt_path = repo / ".worktrees" / "kittybuilder" / task_id
        branch = default_branch_name({"id": task_id})
        base_sha = ba.get_packet_base_sha(INITIATIVE, PACKET, db_path=db_path)

        attempt, lease = ba.claim_and_start_attempt(
            INITIATIVE, PACKET,
            worker_id="crashed-worker",
            branch=branch,
            worktree_path=str(wt_path),
            base_sha=base_sha,
            db_path=db_path,
        )

        reconciled = bl._reconcile_stale_attempts(
            INITIATIVE, PACKET, db_path=db_path, repo_root=repo,
        )
        assert len(reconciled) == 1

        result = bl.run_packet(
            INITIATIVE, PACKET,
            worker_command=_good_worker(tmp_path),
            repo_root=repo, db_path=db_path,
        )
        assert result["outcome"] == "succeeded"

    def test_base_sha_unchanged_throughout_recovery(
        self, repo: Path, db_path: Path, tmp_path: Path
    ):
        """The packet's durable base SHA remains unchanged through crash recovery."""
        task_id = _apply(db_path, repo_root=repo)
        original_sha = ba.get_packet_base_sha(INITIATIVE, PACKET, db_path=db_path)

        from gateway.builder_brief import default_branch_name
        wt_path = repo / ".worktrees" / "kittybuilder" / task_id
        branch = default_branch_name({"id": task_id})

        attempt, lease = ba.claim_and_start_attempt(
            INITIATIVE, PACKET,
            worker_id="crashed-worker",
            branch=branch,
            worktree_path=str(wt_path),
            base_sha=original_sha,
            db_path=db_path,
        )

        bl._reconcile_stale_attempts(
            INITIATIVE, PACKET, db_path=db_path, repo_root=repo,
        )

        assert ba.get_packet_base_sha(INITIATIVE, PACKET, db_path=db_path) == original_sha

        result = bl.run_packet(
            INITIATIVE, PACKET,
            worker_command=_good_worker(tmp_path),
            repo_root=repo, db_path=db_path,
        )
        assert result["outcome"] == "succeeded"
        assert ba.get_packet_base_sha(INITIATIVE, PACKET, db_path=db_path) == original_sha
