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
        _apply(db_path, [_packet("P1"), _packet("P2")])
        summary = _run(repo, db_path, tmp_path)
        assert summary["outcome"] == "idle", summary
        assert summary["succeeded"] == 2, summary
        assert summary["exhausted"] == 0
        seen = [e["packet_id"] for e in summary["processed"]]
        assert seen == ["P1", "P2"]

    def test_decision_events_logged(
        self, repo: Path, db_path: Path, tmp_path: Path
    ):
        _apply(db_path, [_packet("P1"), _packet("P2")])
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
        _apply(db_path, [_packet("P1")])
        bi.pause_initiative(INITIATIVE, "halt", db_path=db_path)
        summary = _run(repo, db_path, tmp_path)
        assert summary["outcome"] == "paused"
        assert summary["processed"] == []
        assert "paused" in summary["reason"]

    def test_attempt_budget_pauses_with_reason(
        self, repo: Path, db_path: Path, tmp_path: Path
    ):
        _apply(db_path, [_packet("P1"), _packet("P2")])
        summary = _run(repo, db_path, tmp_path, max_initiative_attempts=0)
        assert summary["outcome"] == "paused"
        assert summary["processed"] == []
        assert "attempt budget" in summary["reason"]

    def test_dependency_gates_next_packet(
        self, repo: Path, db_path: Path, tmp_path: Path
    ):
        _apply(db_path, [_packet("P1"), _packet("P2", depends_on=["P1"])])
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
