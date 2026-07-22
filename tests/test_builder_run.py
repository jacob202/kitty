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
        assert "paused" in summary["reason"]

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
        assert summary["stop_class"] == br.STOP_NEEDS_DECISION

        status = bi.initiative_status(INITIATIVE, db_path=db_path)
        assert status["stop_class"] == br.STOP_NEEDS_DECISION
        assert "needs_decision" in status["pause_reason"]

        conn = bq.connect(db_path)
        try:
            row = conn.execute(
                "SELECT payload_json FROM events WHERE type = ? "
                "AND payload_json LIKE '%packet_exhausted%'",
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
        assert summary["outcome"] == "paused"
        assert summary["stop_class"] == br.STOP_ROUTINE
        status = bi.initiative_status(INITIATIVE, db_path=db_path)
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
        assert summary["stop_class"] == br.STOP_NEEDS_DECISION

        status = bi.initiative_status(INITIATIVE, db_path=db_path)
        assert status["stop_class"] == br.STOP_NEEDS_DECISION
        assert status["stop_class_reason"] == "requirement may be ambiguous"
        assert "requirement may be ambiguous" in status["pause_reason"]
