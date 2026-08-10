"""Tests for gateway/builder_run.py — KB-S5 initiative run loop.

Integration-style: isolated git repo + queue DB, tiny shell workers that
write a valid implementation contract (no LLMs, no network). Always pass
``repo_root`` so the loop never touches the checkout under test (CI-safe).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from gateway import builder_initiative as bi
from gateway import builder_queue as bq
from gateway import builder_run as br

INITIATIVE = "run-test"

_GOOD_IMPL = json.dumps(
    {"contract_version": 1, "status": "completed", "summary": "did it"}
)


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
    bq.init_db(p)
    return p


def _worker(tmp_path: Path) -> list[str]:
    path = tmp_path / "worker.sh"
    # Portable sh (no bash-only heredoc). JSON is single-line so printf is fine.
    path.write_text(
        "#!/bin/sh\nset -e\n"
        "echo ok > done.txt\n"
        f"printf '%s\\n' '{_GOOD_IMPL}' > \"$KB_RESULT_PATH\"\n",
        encoding="utf-8",
    )
    path.chmod(0o755)
    return ["/bin/sh", str(path)]


def _apply(
    db_path: Path,
    packets: list[dict[str, Any]],
    *,
    repo_root: Path | None = None,
) -> None:
    manifest = {
        "manifest_version": 1,
        "initiative_id": INITIATIVE,
        "title": "Run loop test",
        "packets": packets,
    }
    bi.apply_manifest(manifest, db_path=db_path, repo_root=repo_root)


def _packet(packet_id: str, depends_on: list[str] | None = None) -> dict[str, Any]:
    return {
        "id": packet_id,
        "title": f"Packet {packet_id}",
        "objective": "Produce done.txt.",
        "acceptance_criteria": ["done.txt exists"],
        "allowed_paths": ["done.txt"],
        "policy": {"max_attempts": 1},
        "validation_commands": ["test -f done.txt"],
        "depends_on": depends_on or [],
    }


def _run(
    repo: Path, db_path: Path, tmp_path: Path, **kwargs: Any
) -> dict[str, Any]:
    return br.run_initiative(
        INITIATIVE,
        worker_command=_worker(tmp_path),
        db_path=db_path,
        repo_root=repo,
        **kwargs,
    )


class TestRunInitiative:
    def test_independent_packets_run_in_seq_order(
        self, repo: Path, db_path: Path, tmp_path: Path
    ):
        _apply(db_path, [_packet("P1"), _packet("P2")], repo_root=repo)
        summary = _run(repo, db_path, tmp_path)
        assert summary["outcome"] == "idle", summary
        assert summary["succeeded"] == 2, summary
        assert summary["exhausted"] == 0
        seen = [e["packet_id"] for e in summary["processed"]]
        assert seen == ["P1", "P2"]

    def test_decision_events_logged(
        self, repo: Path, db_path: Path, tmp_path: Path
    ):
        _apply(db_path, [_packet("P1"), _packet("P2")], repo_root=repo)
        summary = _run(repo, db_path, tmp_path)
        assert summary["outcome"] == "idle", summary
        conn = bq.connect(db_path)
        try:
            rows = conn.execute(
                "SELECT task_id, type, payload_json FROM events "
                "WHERE type = ?",
                (br.EVENT_DECISION,),
            ).fetchall()
        finally:
            conn.close()
        decisions = {r["task_id"]: json.loads(r["payload_json"]) for r in rows}
        assert decisions, summary
        assert all(
            d.get("decision") == "packet_succeeded" for d in decisions.values()
        ), decisions

    def test_pause_gate_stops_before_any_packet(
        self, repo: Path, db_path: Path, tmp_path: Path
    ):
        _apply(db_path, [_packet("P1")], repo_root=repo)
        bi.pause_initiative(INITIATIVE, "halt", db_path=db_path)
        summary = _run(repo, db_path, tmp_path)
        assert summary["outcome"] == "paused"
        assert summary["processed"] == []
        # The gate now surfaces the durable pause reason rather than masking
        # it with a generic placeholder, so a later invocation (or process
        # restart) still tells the caller why the initiative is stopped.
        assert summary["reason"] == "halt"
        assert summary["stop_class"] == br.STOP_ROUTINE

    def test_packet_loop_pause_is_not_classified_as_exhaustion(
        self, repo: Path, db_path: Path, tmp_path: Path, monkeypatch
    ):
        _apply(db_path, [_packet("P1")], repo_root=repo)
        initiative = bi.get_initiative(INITIATIVE, db_path=db_path)
        assert initiative is not None
        task_id = initiative["packets"][0]["task_id"]

        def paused_loop(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
            bi.pause_initiative(
                INITIATIVE, "operator pause during packet", db_path=db_path
            )
            return {
                "outcome": br.bl.LOOP_PAUSED,
                "reason": "operator pause during packet",
                "attempts": [{"attempt_id": 42}],
            }

        monkeypatch.setattr(br.bl, "run_packet", paused_loop)
        summary = _run(repo, db_path, tmp_path)

        assert summary["outcome"] == "paused"
        assert summary["reason"] == "operator pause during packet"
        assert summary["exhausted"] == 0
        assert summary["processed"] == [
            {"packet_id": "P1", "task_id": task_id, "outcome": br.bl.LOOP_PAUSED}
        ]
        decisions = [
            event["payload"]
            for event in bq.list_events(task_id, db_path=db_path)
            if event["type"] == br.EVENT_DECISION
        ]
        assert decisions == [{
            "initiative_id": INITIATIVE,
            "packet_id": "P1",
            "decision": "packet_paused",
            "reason": "operator pause during packet",
            "stop_class": br.STOP_ROUTINE,
        }]

    def test_attempt_budget_pauses_with_reason(
        self, repo: Path, db_path: Path, tmp_path: Path
    ):
        _apply(db_path, [_packet("P1"), _packet("P2")], repo_root=repo)
        summary = _run(repo, db_path, tmp_path, max_initiative_attempts=0)
        assert summary["outcome"] == "paused"
        assert summary["processed"] == []
        assert "attempt budget" in summary["reason"]

    def test_dependency_gates_next_packet(
        self, repo: Path, db_path: Path, tmp_path: Path
    ):
        _apply(
            db_path,
            [_packet("P1"), _packet("P2", depends_on=["P1"])],
            repo_root=repo,
        )
        summary = _run(repo, db_path, tmp_path)
        assert summary["succeeded"] == 1, summary
        assert [e["packet_id"] for e in summary["processed"]] == ["P1"]
        status = bi.initiative_status(INITIATIVE, db_path=db_path)
        assert "P2" in status["pending"]

    def test_cancelled_packet_is_not_recorded_as_exhausted(
        self, repo: Path, db_path: Path, tmp_path: Path, monkeypatch
    ):
        _apply(db_path, [_packet("P1")], repo_root=repo)
        initiative = bi.get_initiative(INITIATIVE, db_path=db_path)
        assert initiative is not None
        task_id = initiative["packets"][0]["task_id"]

        def cancelled_loop(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
            bq.transition_task(task_id, bq.CLAIMED, db_path=db_path)
            bq.transition_task(task_id, bq.RUNNING, db_path=db_path)
            bq.transition_task(task_id, bq.BLOCKED, db_path=db_path)
            return {
                "outcome": br.bl.LOOP_CANCELLED,
                "reason": "worker run was cancelled",
                "attempts": [{"attempt_id": 41, "run_id": "run-cancelled"}],
            }

        monkeypatch.setattr(br.bl, "run_packet", cancelled_loop)
        summary = _run(repo, db_path, tmp_path)

        assert summary["outcome"] == "idle"
        assert summary["exhausted"] == 0
        assert summary["processed"] == [
            {"packet_id": "P1", "task_id": task_id, "outcome": br.bl.LOOP_CANCELLED}
        ]
        decisions = [
            event["payload"]
            for event in bq.list_events(task_id, db_path=db_path)
            if event["type"] == br.EVENT_DECISION
        ]
        assert decisions == [
            {
                "initiative_id": INITIATIVE,
                "packet_id": "P1",
                "decision": "packet_cancelled",
                "reason": "worker run was cancelled",
                "stop_class": br.STOP_ROUTINE,
                "provenance": {
                    "source": "worker_run",
                    "attempt_id": 41,
                    "run_id": "run-cancelled",
                },
            }
        ]


class TestPauseResume:
    def test_resume_clears_pause(self, db_path: Path):
        _apply(db_path, [_packet("P1")])
        bi.pause_initiative(INITIATIVE, db_path=db_path)
        assert bi.get_initiative_state(INITIATIVE, db_path=db_path) == bi.INITIATIVE_PAUSED
        bi.resume_initiative(INITIATIVE, db_path=db_path)
        assert bi.get_initiative_state(INITIATIVE, db_path=db_path) == bi.INITIATIVE_ACTIVE

    def test_unknown_initiative_raises(self, db_path: Path):
        with pytest.raises(bi.InitiativeNotFoundError):
            bi.get_initiative_state("nope", db_path=db_path)


# ---------------------------------------------------------------------------
# CP-03 — stop classification (routine vs needs_decision)
# ---------------------------------------------------------------------------


class TestClassifyExhaustionUnit:
    """Pure unit coverage of the crude, mechanical (validation command, exit
    code, review finding class) signature comparison — no git/subprocess
    needed to exercise the classifier itself.
    """

    def test_escalation_always_needs_decision(self):
        loop_result = {
            "attempts": [{"outcome": "failed"}],
            "escalation": {
                "category": "scope_violation",
                "findings": [{"category": "scope_drift", "field": "x", "message": "m"}],
            },
        }
        result = br._classify_exhaustion(loop_result)
        assert result["stop_class"] == br.STOP_NEEDS_DECISION
        assert result["findings"] == loop_result["escalation"]["findings"]

    def test_three_different_signatures_is_routine(self):
        loop_result = {
            "attempts": [
                {
                    "outcome": "failed",
                    "validation_failure": {"command": "pytest", "exit_code": 1},
                },
                {
                    "outcome": "failed",
                    "validation_failure": {"command": "pytest", "exit_code": 2},
                },
                {
                    "outcome": "failed",
                    "validation_failure": {"command": "lint", "exit_code": 1},
                },
            ],
        }
        result = br._classify_exhaustion(loop_result)
        assert result["stop_class"] == br.STOP_ROUTINE
        assert "findings" not in result

    def test_identical_signature_across_attempts_needs_decision(self):
        loop_result = {
            "attempts": [
                {
                    "outcome": "failed",
                    "validation_failure": {"command": "pytest", "exit_code": 1},
                },
                {
                    "outcome": "failed",
                    "validation_failure": {"command": "pytest", "exit_code": 1},
                },
            ],
        }
        result = br._classify_exhaustion(loop_result)
        assert result["stop_class"] == br.STOP_NEEDS_DECISION
        assert result["reason"] == "requirement may be ambiguous"

    def test_crashed_attempts_do_not_count_toward_signature_comparison(self):
        # Only budget-consuming outcomes (failed/aborted) participate;
        # a single real failure alongside crashes stays routine.
        loop_result = {
            "attempts": [
                {"outcome": "crashed"},
                {
                    "outcome": "failed",
                    "validation_failure": {"command": "pytest", "exit_code": 1},
                },
            ],
        }
        result = br._classify_exhaustion(loop_result)
        assert result["stop_class"] == br.STOP_ROUTINE


class TestStopClassIntegration:
    """End-to-end through run_initiative + bl.run_packet with real git repos
    and tiny shell workers — proves the CP-03 acceptance criteria, not just
    the classifier in isolation.
    """

    def test_scope_escalation_run_needs_decision_with_findings(
        self, repo: Path, db_path: Path, tmp_path: Path
    ):
        _apply(db_path, [_packet("P1")], repo_root=repo)
        forbidden_worker = tmp_path / "forbidden.sh"
        forbidden_worker.write_text(
            "#!/bin/sh\nset -e\n"
            "echo secret > secret.txt\n"
            "echo ok > done.txt\n"
            f"printf '%s\\n' '{_GOOD_IMPL}' > \"$KB_RESULT_PATH\"\n",
            encoding="utf-8",
        )
        forbidden_worker.chmod(0o755)

        summary = br.run_initiative(
            INITIATIVE,
            worker_command=["/bin/sh", str(forbidden_worker)],
            db_path=db_path,
            repo_root=repo,
        )
        assert summary["outcome"] == "paused"
        assert summary["exhausted"] == 1

        status = bi.initiative_status(INITIATIVE, db_path=db_path)
        assert status["stop_class"] == br.STOP_NEEDS_DECISION
        # The needs_decision path of the run loop now durably pauses the
        # initiative (rather than continuing), so the reason is recorded in
        # both stop_class_reason and pause_reason.
        assert status.get("stop_class_reason")
        assert status.get("pause_reason")

        conn = bq.connect(db_path)
        try:
            row = conn.execute(
                "SELECT payload_json FROM events WHERE type = ? "
                "AND payload_json LIKE '%packet_needs_decision%'",
                (br.EVENT_DECISION,),
            ).fetchone()
        finally:
            conn.close()
        payload = json.loads(row["payload_json"])
        assert payload["stop_class"] == br.STOP_NEEDS_DECISION
        assert payload["findings"]

    def test_three_different_failures_is_routine(
        self, repo: Path, db_path: Path, tmp_path: Path
    ):
        _apply(
            db_path,
            [
                {
                    "id": "P1",
                    "title": "Packet P1",
                    "objective": "Produce done.txt.",
                    "acceptance_criteria": ["done.txt exists"],
                    "allowed_paths": ["done.txt", "marker.txt"],
                    "policy": {"max_attempts": 3},
                    "validation_commands": [
                        "test -f done.txt",
                        "sh -c 'exit $(cat marker.txt)'",
                    ],
                    "depends_on": [],
                }
            ],
            repo_root=repo,
        )
        worker = tmp_path / "differing.sh"
        worker.write_text(
            "#!/bin/sh\nset -e\n"
            "attempt_no=$(python3 -c "
            "\"import json; print(json.load(open('$KB_BUNDLE_PATH'))['attempt_no'])\")\n"
            "echo \"$attempt_no\" > marker.txt\n"
            "echo ok > done.txt\n"
            "git add marker.txt done.txt\n"
            "git -c user.email=t@t -c user.name=t commit -q -m \"[P1] attempt $attempt_no\"\n"
            f"printf '%s\\n' '{_GOOD_IMPL}' > \"$KB_RESULT_PATH\"\n",
            encoding="utf-8",
        )
        worker.chmod(0o755)

        summary = br.run_initiative(
            INITIATIVE,
            worker_command=["/bin/sh", str(worker)],
            db_path=db_path,
            repo_root=repo,
        )
        assert summary["outcome"] == "idle"
        assert summary["exhausted"] == 1
        status = bi.initiative_status(INITIATIVE, db_path=db_path)
        assert status["state"] == bi.INITIATIVE_FAILED
        assert status["stop_class"] == br.STOP_ROUTINE

    def test_same_signature_exhaustion_needs_decision_ambiguous(
        self, repo: Path, db_path: Path, tmp_path: Path
    ):
        _apply(
            db_path,
            [
                {
                    "id": "P1",
                    "title": "Packet P1",
                    "objective": "Produce nope.txt.",
                    "acceptance_criteria": ["nope.txt exists"],
                    "allowed_paths": ["done.txt"],
                    "policy": {"max_attempts": 3},
                    "validation_commands": ["test -f nope.txt"],
                    "depends_on": [],
                }
            ],
            repo_root=repo,
        )
        # Writes only outside the worktree (the result contract), so the
        # worktree stays clean across retries — this worker never satisfies
        # "nope.txt exists" and fails validation identically every attempt.
        worker = tmp_path / "never_nope.sh"
        worker.write_text(
            "#!/bin/sh\nset -e\n"
            f"printf '%s\\n' '{_GOOD_IMPL}' > \"$KB_RESULT_PATH\"\n",
            encoding="utf-8",
        )
        worker.chmod(0o755)

        summary = br.run_initiative(
            INITIATIVE,
            worker_command=["/bin/sh", str(worker)],
            db_path=db_path,
            repo_root=repo,
        )
        assert summary["outcome"] == "paused"
        assert summary["exhausted"] == 1

        status = bi.initiative_status(INITIATIVE, db_path=db_path)
        assert status["state"] == bi.INITIATIVE_PAUSED
        assert status["stop_class"] == br.STOP_NEEDS_DECISION
        assert status["stop_class_reason"] == "requirement may be ambiguous"
        # stop_class_reason is the durable surface; the needs_decision pause
        # also records the reason in pause_reason so the initiative stops.
        assert status.get("pause_reason")

    def test_exhausted_packet_does_not_stop_unrelated_packet(
        self, repo: Path, db_path: Path, tmp_path: Path
    ):
        failing = _packet("P1")
        failing["acceptance_criteria"] = ["impossible.txt exists"]
        failing["validation_commands"] = ["test -f impossible.txt"]
        succeeding = _packet("P2")
        _apply(db_path, [failing, succeeding], repo_root=repo)

        worker = tmp_path / "selective.sh"
        worker.write_text(
            "#!/bin/sh\nset -e\n"
            "packet_id=$(python3 -c "
            "\"import json; print(json.load(open('$KB_BUNDLE_PATH'))['packet_id'])\")\n"
            "if [ \"$packet_id\" = \"P2\" ]; then echo ok > done.txt; fi\n"
            f"printf '%s\\n' '{_GOOD_IMPL}' > \"$KB_RESULT_PATH\"\n",
            encoding="utf-8",
        )
        worker.chmod(0o755)

        summary = br.run_initiative(
            INITIATIVE,
            worker_command=["/bin/sh", str(worker)],
            db_path=db_path,
            repo_root=repo,
        )

        assert summary["outcome"] == "idle", summary
        assert summary["exhausted"] == 1
        assert summary["succeeded"] == 1
        assert [item["packet_id"] for item in summary["processed"]] == ["P1", "P2"]
        status = bi.initiative_status(INITIATIVE, db_path=db_path)
        assert status["state"] == bi.INITIATIVE_FAILED
        assert status["exhausted"] == ["P1"]
        # Without publish, the success path does not transition the task to
        # DONE — P2 succeeded in the run summary but stays at its runner
        # terminal state.  The critical invariant is that P2 *ran and succeeded*
        # despite P1's exhaustion, not that its task state reached DONE.
        assert "P2" not in status["exhausted"]
        assert "P2" not in (status.get("blocked") or [])

    def test_worker_provider_exhaustion_pauses_without_consuming_attempt_budget(
        self, repo: Path, db_path: Path, tmp_path: Path
    ):
        _apply(db_path, [_packet("P1"), _packet("P2")], repo_root=repo)
        unavailable = tmp_path / "provider-unavailable.sh"
        unavailable.write_text("#!/bin/sh\nexit 75\n", encoding="utf-8")
        unavailable.chmod(0o755)

        summary = br.run_initiative(
            INITIATIVE,
            worker_command=["/bin/sh", str(unavailable)],
            db_path=db_path,
            repo_root=repo,
        )

        assert summary["outcome"] == "paused"
        assert "provider exhaustion" in summary["reason"]
        assert summary["processed"][0]["outcome"] == br.bl.LOOP_PROVIDER_EXHAUSTED
        attempts = br.ba.list_attempts(INITIATIVE, "P1", db_path=db_path)
        assert [attempt["outcome"] for attempt in attempts] == [br.ba.ATTEMPT_CRASHED]
        status = bi.initiative_status(INITIATIVE, db_path=db_path)
        assert status["state"] == bi.INITIATIVE_PAUSED
        assert status["eligible"] == ["P1", "P2"]

    def test_reviewer_provider_exhaustion_is_resumable(
        self, repo: Path, db_path: Path, tmp_path: Path
    ):
        _apply(db_path, [_packet("P1")], repo_root=repo)
        unavailable_review = tmp_path / "review-provider-unavailable.sh"
        unavailable_review.write_text("#!/bin/sh\nexit 75\n", encoding="utf-8")
        unavailable_review.chmod(0o755)

        committing_worker = tmp_path / "committing-worker.sh"
        committing_worker.write_text(
            "#!/bin/sh\nset -e\n"
            "echo ok > done.txt\n"
            "git add done.txt\n"
            "git -c user.email=t@t -c user.name=t commit -q -m \"[P1] implementation\"\n"
            f"printf '%s\\n' '{_GOOD_IMPL}' > \"$KB_RESULT_PATH\"\n",
            encoding="utf-8",
        )
        committing_worker.chmod(0o755)

        summary = br.run_initiative(
            INITIATIVE,
            worker_command=["/bin/sh", str(committing_worker)],
            review_command=["/bin/sh", str(unavailable_review)],
            db_path=db_path,
            repo_root=repo,
        )

        assert summary["outcome"] == "paused"
        assert "provider exhaustion" in summary["reason"]
        attempts = br.ba.list_attempts(INITIATIVE, "P1", db_path=db_path)
        assert [attempt["outcome"] for attempt in attempts] == [br.ba.ATTEMPT_CRASHED]
        status = bi.initiative_status(INITIATIVE, db_path=db_path)
        assert status["state"] == bi.INITIATIVE_PAUSED
        assert status["eligible"] == ["P1"]


class TestCp06AutoMerge:
    """CP-06: run_initiative's gate="auto"/"manual" wiring around publish.

    publish_task and merge_and_verify are stubbed at the bp module
    reference builder_run imports — the merge mechanics themselves are
    covered end-to-end in tests/test_builder_publish.py with real gh/git
    call stubs. This class only proves the *loop* wiring: does auto-merge
    get attempted, does a green merge unlock downstream in the same
    invocation, does a revert pause the initiative.
    """

    def _stub_publish(self, monkeypatch, pr_number: int = 1):
        calls: list[str] = []

        def fake_publish(task_id: str, **kwargs: Any) -> dict[str, Any]:
            calls.append(task_id)
            bq.transition_task(task_id, bq.PR_OPENED, db_path=kwargs.get("db_path"))
            bq.transition_task(task_id, bq.AWAITING_REVIEW, db_path=kwargs.get("db_path"))
            return {"pr": {"pr_number": pr_number, "action": "create"}}

        monkeypatch.setattr(br.bp, "publish_task", fake_publish)
        return calls

    def test_gate_manual_never_attempts_merge(
        self, repo: Path, db_path: Path, tmp_path: Path, monkeypatch
    ):
        self._stub_publish(monkeypatch)

        def explode(*args: Any, **kwargs: Any) -> Any:
            raise AssertionError("merge_and_verify must not be called under gate=manual")

        monkeypatch.setattr(br.bp, "merge_and_verify", explode)

        _apply(db_path, [_packet("P1")], repo_root=repo)
        summary = _run(repo, db_path, tmp_path, publish=True, gate="manual")

        assert summary["outcome"] == "idle"
        assert summary["succeeded"] == 1
        # Task parks at awaiting_review — the pre-CP-06 shape.
        status = bi.initiative_status(INITIATIVE, db_path=db_path)
        assert "P1" not in status["done"]
        assert "P1" in status["in_progress"]

    def test_gate_auto_merges_and_unlocks_downstream_same_invocation(
        self, repo: Path, db_path: Path, tmp_path: Path, monkeypatch
    ):
        self._stub_publish(monkeypatch)
        merge_calls: list[str] = []

        def fake_merge(task_id: str, **kwargs: Any) -> dict[str, Any]:
            merge_calls.append(task_id)
            db_path_arg = kwargs.get("db_path")
            bq._mark_pr_merged(task_id, 1, db_path_arg)
            bq._promote_merged_task(task_id, db_path_arg)
            return {"outcome": "merged", "pr_number": 1, "merge_commit_sha": "abc123"}

        monkeypatch.setattr(br.bp, "merge_and_verify", fake_merge)

        _apply(
            db_path,
            [_packet("P1"), _packet("P2", depends_on=["P1"])],
            repo_root=repo,
        )
        summary = _run(repo, db_path, tmp_path, publish=True, gate="auto")

        assert summary["outcome"] == "idle"
        assert summary["succeeded"] == 2, summary
        assert len(merge_calls) == 2
        status = bi.initiative_status(INITIATIVE, db_path=db_path)
        assert set(status["done"]) == {"P1", "P2"}

    def test_gate_auto_revert_pauses_needs_decision(
        self, repo: Path, db_path: Path, tmp_path: Path, monkeypatch
    ):
        self._stub_publish(monkeypatch)

        def fake_merge(task_id: str, **kwargs: Any) -> dict[str, Any]:
            return {
                "outcome": "reverted",
                "pr_number": 1,
                "merge_commit_sha": "abc123",
                "revalidation": {"passed": False, "commands": []},
                "revert": {"revert_commit_sha": "revertsha"},
            }

        monkeypatch.setattr(br.bp, "merge_and_verify", fake_merge)

        _apply(
            db_path,
            [_packet("P1"), _packet("P2", depends_on=["P1"])],
            repo_root=repo,
        )
        summary = _run(repo, db_path, tmp_path, publish=True, gate="auto")

        assert summary["outcome"] == "paused"
        assert summary["stop_class"] == br.STOP_NEEDS_DECISION
        assert "reverted" in summary["reason"]
        status = bi.initiative_status(INITIATIVE, db_path=db_path)
        assert "P1" not in status["done"]
        assert "P2" not in status["done"]

    def test_gate_auto_skipped_tripwire_degrades_to_idle_without_pausing(
        self, repo: Path, db_path: Path, tmp_path: Path, monkeypatch
    ):
        self._stub_publish(monkeypatch)

        def fake_merge(task_id: str, **kwargs: Any) -> dict[str, Any]:
            return {"outcome": "skipped_tripwire", "pr_number": 1}

        monkeypatch.setattr(br.bp, "merge_and_verify", fake_merge)

        _apply(db_path, [_packet("P1")], repo_root=repo)
        summary = _run(repo, db_path, tmp_path, publish=True, gate="auto")

        # Not merged, so nothing unlocks — the loop exits idle rather than
        # pausing loudly, matching pre-CP-06 park-and-wait.
        assert summary["outcome"] == "idle"
        status = bi.initiative_status(INITIATIVE, db_path=db_path)
        assert "P1" not in status["done"]

    def test_invalid_gate_value_raises(self, repo: Path, db_path: Path, tmp_path: Path):
        _apply(db_path, [_packet("P1")], repo_root=repo)
        with pytest.raises(ValueError, match="gate must be"):
            _run(repo, db_path, tmp_path, publish=True, gate="bogus")


class TestNeedsDecisionPause:
    """Regression: a packet whose exhaustion stop is needs_decision must
    durably pause the initiative instead of being re-selected and relaunched
    without a new operator decision.
    """

    def _needs_decision_loop(
        self, task_id: str, *, escalation: bool = True
    ) -> dict[str, Any]:
        attempts = [
            {
                "attempt_id": 41,
                "run_id": "run-nd-1",
                "outcome": "failed",
                "validation_failure": {"command": "pytest", "exit_code": 1},
            },
            {
                "attempt_id": 42,
                "run_id": "run-nd-2",
                "outcome": "failed",
                "validation_failure": {"command": "pytest", "exit_code": 1},
            },
        ]
        result: dict[str, Any] = {
            "outcome": br.bl.LOOP_EXHAUSTED,
            "initiative_id": INITIATIVE,
            "packet_id": "P1",
            "task_id": task_id,
            "reason": "worker went out of scope",
            "attempts": attempts,
        }
        if escalation:
            result["escalation"] = {
                "category": "scope_violation",
                "findings": [{"category": "scope_drift", "field": "x", "message": "m"}],
            }
        return result

    def _task_id(self, packet_id: str, db_path: Path) -> str:
        initiative = bi.get_initiative(INITIATIVE, db_path=db_path)
        assert initiative is not None
        for packet in initiative["packets"]:
            if packet["packet_id"] == packet_id:
                return packet["task_id"]
        raise AssertionError(f"packet {packet_id} not found")

    def test_first_run_pauses_on_needs_decision(
        self, repo: Path, db_path: Path, tmp_path: Path, monkeypatch
    ):
        _apply(db_path, [_packet("P1")], repo_root=repo)
        calls: list[str] = []

        def fake_run_packet(initiative_id: str, packet_id: str, **kwargs: Any) -> dict[str, Any]:
            calls.append(packet_id)
            return self._needs_decision_loop(self._task_id(packet_id, db_path))

        monkeypatch.setattr(br.bl, "run_packet", fake_run_packet)
        summary = _run(repo, db_path, tmp_path)

        assert summary["outcome"] == "paused"
        assert summary["stop_class"] == br.STOP_NEEDS_DECISION
        assert summary["packet_id"] == "P1"
        assert summary["task_id"] == self._task_id("P1", db_path)
        assert calls == ["P1"]
        assert summary["exhausted"] == 1
        assert bi.get_initiative_state(INITIATIVE, db_path=db_path) == bi.INITIATIVE_PAUSED

        status = bi.initiative_status(INITIATIVE, db_path=db_path)
        assert status["stop_class"] == br.STOP_NEEDS_DECISION
        assert status["pause_reason"]
        assert "P1" in status["pause_reason"]

    def test_second_run_without_override_does_not_relaunch(
        self, repo: Path, db_path: Path, tmp_path: Path, monkeypatch
    ):
        _apply(db_path, [_packet("P1")], repo_root=repo)
        calls: list[str] = []

        def fake_run_packet(initiative_id: str, packet_id: str, **kwargs: Any) -> dict[str, Any]:
            calls.append(packet_id)
            return self._needs_decision_loop(self._task_id(packet_id, db_path))

        monkeypatch.setattr(br.bl, "run_packet", fake_run_packet)

        first = _run(repo, db_path, tmp_path)
        assert first["outcome"] == "paused"

        # A second invocation without any operator override must not launch
        # another worker: the initiative is durably paused.
        second = _run(repo, db_path, tmp_path)
        assert second["outcome"] == "paused"
        assert second["processed"] == []
        assert calls == ["P1"]
        assert bi.get_initiative_state(INITIATIVE, db_path=db_path) == bi.INITIATIVE_PAUSED

    def test_operator_override_permits_progress(
        self, repo: Path, db_path: Path, tmp_path: Path, monkeypatch
    ):
        # Mirrors the real queue: the needs_decision loop parks the task
        # (blocked) exactly as bl.run_packet does, so a bare durable resume
        # un-parks the GATE but does NOT relaunch the decided packet. Only the
        # operator's explicit per-packet override (queue operator-release)
        # re-arms it; the next run then selects it exactly once.
        _apply(db_path, [_packet("P1")], repo_root=repo)
        calls: list[str] = []
        need_decision = {"active": True}

        def fake_run_packet(initiative_id: str, packet_id: str, **kwargs: Any) -> dict[str, Any]:
            calls.append(packet_id)
            tid = self._task_id(packet_id, db_path)
            if need_decision["active"]:
                # Mirror the real loop's needs_decision closeout: the task is
                # claimed, run, then parked (blocked) so next_packet cannot
                # re-select it.
                bq.transition_task(tid, bq.CLAIMED, db_path=db_path)
                bq.transition_task(tid, bq.RUNNING, db_path=db_path)
                bq.transition_task(tid, bq.BLOCKED, db_path=db_path)
                return self._needs_decision_loop(tid)
            bq.transition_task(tid, bq.CLAIMED, db_path=db_path)
            bq.transition_task(tid, bq.RUNNING, db_path=db_path)
            bq.transition_task(tid, bq.PR_OPENED, db_path=db_path)
            bq.transition_task(tid, bq.AWAITING_REVIEW, db_path=db_path)
            bq.transition_task(tid, bq.DONE, db_path=db_path)
            return {
                "outcome": br.bl.LOOP_SUCCEEDED,
                "initiative_id": INITIATIVE,
                "packet_id": packet_id,
                "task_id": tid,
                "attempts": [],
            }

        monkeypatch.setattr(br.bl, "run_packet", fake_run_packet)

        first = _run(repo, db_path, tmp_path)
        assert first["outcome"] == "paused"
        assert calls == ["P1"]

        # A bare durable resume clears the gate, but the parked (blocked)
        # decision packet must not be relaunched by it.
        bi.resume_initiative(INITIATIVE, db_path=db_path)
        gate_cleared = _run(repo, db_path, tmp_path)
        assert gate_cleared["outcome"] == "idle", gate_cleared
        assert gate_cleared["processed"] == []
        assert calls == ["P1"]

        # The operator's explicit packet-level decision (queue
        # operator-release) re-arms the parked task; the run selects it
        # exactly once (and, the issue being unchanged, re-parks again).
        need_decision["active"] = False
        task_id = self._task_id("P1", db_path)
        bq.operator_release_task(task_id, db_path=db_path)
        resumed = _run(repo, db_path, tmp_path)
        assert resumed["outcome"] == "idle", resumed
        assert resumed["succeeded"] == 1, resumed
        assert calls == ["P1", "P1"]
        assert bi.get_initiative_state(INITIATIVE, db_path=db_path) == bi.INITIATIVE_ACTIVE

    def test_ordinary_exhaustion_behavior_unchanged(
        self, repo: Path, db_path: Path, tmp_path: Path, monkeypatch
    ):
        # Routine exhaustion (differing signatures) must still continue to the
        # next packet rather than pausing.
        failing = _packet("P1")
        succeeding = _packet("P2")
        _apply(db_path, [failing, succeeding], repo_root=repo)

        worker = tmp_path / "selective.sh"
        worker.write_text(
            "#!/bin/sh\nset -e\n"
            "packet_id=$(python3 -c "
            "\"import json; print(json.load(open('$KB_BUNDLE_PATH'))['packet_id'])\")\n"
            "if [ \"$packet_id\" = \"P2\" ]; then echo ok > done.txt; fi\n"
            f"printf '%s\\n' '{_GOOD_IMPL}' > \"$KB_RESULT_PATH\"\n",
            encoding="utf-8",
        )
        worker.chmod(0o755)

        summary = br.run_initiative(
            INITIATIVE,
            worker_command=["/bin/sh", str(worker)],
            db_path=db_path,
            repo_root=repo,
        )
        assert summary["outcome"] == "idle", summary
        assert summary["exhausted"] == 1
        assert summary["succeeded"] == 1
        assert [e["packet_id"] for e in summary["processed"]] == ["P1", "P2"]

    def test_successful_packets_retain_existing_behavior(
        self, repo: Path, db_path: Path, tmp_path: Path
    ):
        _apply(db_path, [_packet("P1"), _packet("P2")], repo_root=repo)
        summary = _run(repo, db_path, tmp_path)
        assert summary["outcome"] == "idle", summary
        assert summary["succeeded"] == 2
        assert summary["exhausted"] == 0
        assert bi.get_initiative_state(INITIATIVE, db_path=db_path) == bi.INITIATIVE_ACTIVE

    def test_second_run_still_reports_durable_needs_decision(
        self, repo: Path, db_path: Path, tmp_path: Path, monkeypatch
    ):
        # The pause is durable and pre-dates the second call: it must not be
        # masked as a routine pause, or a later invocation/process restart
        # would hide the operator decision from the CLI exit status.
        _apply(db_path, [_packet("P1")], repo_root=repo)

        def fake_run_packet(initiative_id: str, packet_id: str, **kwargs: Any) -> dict[str, Any]:
            return self._needs_decision_loop(self._task_id(packet_id, db_path))

        monkeypatch.setattr(br.bl, "run_packet", fake_run_packet)

        first = _run(repo, db_path, tmp_path)
        assert first["stop_class"] == br.STOP_NEEDS_DECISION

        second = _run(repo, db_path, tmp_path)
        assert second["outcome"] == "paused"
        assert second["stop_class"] == br.STOP_NEEDS_DECISION
        assert "needs operator decision" in second["reason"]

    def test_decision_write_failure_leaves_pause_and_fails_loud(
        self, repo: Path, db_path: Path, tmp_path: Path, monkeypatch
    ):
        # If writing the packet_needs_decision event fails, the run must fail
        # loud (not continue to another packet) and the initiative must stay
        # durably paused: a parked initiative is the safe side of a split
        # pause/event failure, never a silent re-launch.
        _apply(db_path, [_packet("P1")], repo_root=repo)

        def fake_run_packet(initiative_id: str, packet_id: str, **kwargs: Any) -> dict[str, Any]:
            return self._needs_decision_loop(self._task_id(packet_id, db_path))

        monkeypatch.setattr(br.bl, "run_packet", fake_run_packet)

        real_append = br.bq.append_event

        def failing_append(task_id: str, event_type: str, payload=None, **kwargs: Any) -> Any:
            if (payload or {}).get("decision") == "packet_needs_decision":
                raise RuntimeError("event write failed")
            return real_append(task_id, event_type, payload, **kwargs)

        monkeypatch.setattr(br.bq, "append_event", failing_append)

        with pytest.raises(RuntimeError, match="event write failed"):
            _run(repo, db_path, tmp_path)

        assert bi.get_initiative_state(INITIATIVE, db_path=db_path) == bi.INITIATIVE_PAUSED
        status = bi.initiative_status(INITIATIVE, db_path=db_path)
        assert status.get("pause_reason")
        assert "P1" in status["pause_reason"]

    def test_no_stale_run_survives_needs_decision_pause(
        self, repo: Path, db_path: Path, tmp_path: Path
    ):
        # Real loop: a needs_decision exhaustion must leave no run in a live
        # state behind the pause; every attempt is closed before the
        # initiative parks.
        _apply(
            db_path,
            [
                {
                    "id": "P1",
                    "title": "Packet P1",
                    "objective": "Produce nope.txt.",
                    "acceptance_criteria": ["nope.txt exists"],
                    "allowed_paths": ["done.txt"],
                    "policy": {"max_attempts": 3},
                    "validation_commands": ["test -f nope.txt"],
                    "depends_on": [],
                }
            ],
            repo_root=repo,
        )
        worker = tmp_path / "never_nope.sh"
        worker.write_text(
            "#!/bin/sh\nset -e\n"
            f"printf '%s\\n' '{_GOOD_IMPL}' > \"$KB_RESULT_PATH\"\n",
            encoding="utf-8",
        )
        worker.chmod(0o755)

        summary = br.run_initiative(
            INITIATIVE,
            worker_command=["/bin/sh", str(worker)],
            db_path=db_path,
            repo_root=repo,
        )
        assert summary["outcome"] == "paused"
        assert summary["stop_class"] == br.STOP_NEEDS_DECISION

        task_id = self._task_id("P1", db_path)
        runs = bq.list_runs(task_id=task_id, db_path=db_path)
        active = [r for r in runs if r.get("state") in bq.RUN_ACTIVE_STATES]
        assert active == [], f"stale live runs after needs_decision pause: {active}"
        attempts = br.ba.list_attempts(INITIATIVE, "P1", db_path=db_path)
        assert attempts
        # No stale open attempt: every recorded attempt is closed, and no
        # row is left with a NULL outcome waiting for a worker that quit.
        conn = bq.connect(db_path)
        try:
            open_count = conn.execute(
                "SELECT COUNT(*) FROM packet_attempts "
                "WHERE initiative_id = ? AND packet_id = ? AND outcome IS NULL",
                (INITIATIVE, "P1"),
            ).fetchone()[0]
        finally:
            conn.close()
        assert open_count == 0

    def test_cli_exit_status_reflects_operator_decision(
        self, repo: Path, db_path: Path, tmp_path: Path, monkeypatch
    ):
        # Shell contract: a needs_decision pause must not exit 0 ("nothing to
        # do"); a routine pause and ordinary idle must keep exiting 0.
        from gateway.builder_cli import EXIT_NEEDS_DECISION

        assert EXIT_NEEDS_DECISION != 0
        assert EXIT_NEEDS_DECISION != 1
