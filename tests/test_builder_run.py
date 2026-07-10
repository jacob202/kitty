"""Tests for gateway/builder_run.py — KB-S5 initiative run loop.

Integration-style: real git repo + real queue DB, with tiny shell workers that
write a valid implementation contract (no LLMs, no network). Exercises the
loop driver, the operator pause gate, and the per-initiative budgets.
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
    path.write_text(
        "#!/bin/bash\nset -e\n"
        f"echo ok > done.txt\ncat > \"$KB_RESULT_PATH\" <<'EOF'\n{_GOOD_IMPL}\nEOF\n",
        encoding="utf-8",
    )
    path.chmod(0o755)
    return ["bash", str(path)]


def _apply(db_path: Path, packets: list[dict[str, Any]]) -> None:
    manifest = {
        "manifest_version": 1,
        "initiative_id": INITIATIVE,
        "title": "Run loop test",
        "packets": packets,
    }
    bi.apply_manifest(manifest, db_path=db_path)


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


# ---------------------------------------------------------------------------
# Loop behavior
# ---------------------------------------------------------------------------


class TestRunInitiative:
    def test_independent_packets_run_in_seq_order(
        self, repo: Path, db_path: Path, tmp_path: Path
    ):
        _apply(
            db_path,
            [_packet("P1"), _packet("P2")],
        )
        summary = br.run_initiative(
            INITIATIVE, worker_command=_worker(tmp_path), db_path=db_path
        )
        assert summary["outcome"] == "idle"
        assert summary["succeeded"] == 2
        assert summary["exhausted"] == 0
        seen = [e["packet_id"] for e in summary["processed"]]
        assert seen == ["P1", "P2"]

    def test_decision_events_logged(
        self, repo: Path, db_path: Path, tmp_path: Path
    ):
        _apply(db_path, [_packet("P1"), _packet("P2")])
        br.run_initiative(
            INITIATIVE, worker_command=_worker(tmp_path), db_path=db_path
        )
        # Events are written against the packet task ids; both should have a
        # packet_succeeded decision.
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
        assert decisions
        assert all(d.get("decision") == "packet_succeeded" for d in decisions.values())

    def test_pause_gate_stops_before_any_packet(
        self, repo: Path, db_path: Path, tmp_path: Path
    ):
        _apply(db_path, [_packet("P1")])
        bi.pause_initiative(INITIATIVE, "halt", db_path=db_path)
        summary = br.run_initiative(
            INITIATIVE, worker_command=_worker(tmp_path), db_path=db_path
        )
        assert summary["outcome"] == "paused"
        assert summary["processed"] == []
        assert "paused" in summary["reason"]

    def test_attempt_budget_pauses_with_reason(
        self, repo: Path, db_path: Path, tmp_path: Path
    ):
        _apply(db_path, [_packet("P1"), _packet("P2")])
        summary = br.run_initiative(
            INITIATIVE,
            worker_command=_worker(tmp_path),
            db_path=db_path,
            max_initiative_attempts=0,
        )
        assert summary["outcome"] == "paused"
        assert summary["processed"] == []
        assert "attempt budget" in summary["reason"]

    def test_dependency_gates_next_packet(
        self, repo: Path, db_path: Path, tmp_path: Path
    ):
        # P2 depends on P1; until P1's task is done (via merge), P2 is not
        # eligible, so one run processes exactly one packet.
        _apply(db_path, [_packet("P1"), _packet("P2", depends_on=["P1"])])
        summary = br.run_initiative(
            INITIATIVE, worker_command=_worker(tmp_path), db_path=db_path
        )
        assert summary["succeeded"] == 1
        assert [e["packet_id"] for e in summary["processed"]] == ["P1"]
        # P2 is still queued, waiting on P1's (blocked) task.
        status = bi.initiative_status(INITIATIVE, db_path=db_path)
        assert "P2" in status["pending"]


# ---------------------------------------------------------------------------
# Pause / resume helpers
# ---------------------------------------------------------------------------


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
