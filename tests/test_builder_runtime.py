"""Tests for gateway/builder_runtime.py — enhanced runtime snapshot."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from gateway import builder_attempt as ba
from gateway import builder_initiative as bi
from gateway import builder_queue as bq
from gateway.builder_runtime import (
    SCHEMA_VERSION,
    _infer_worker_state,
    _safe_isoformat,
    _safe_list,
    build_runtime_snapshot,
)
from gateway.builder_worker_session import WorkerState

INITIATIVE = "runtime-test"
PACKET = "RT-1"


# ---------------------------------------------------------------------------
# Fixtures
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
def db_path(tmp_path: Path, repo: Path) -> Path:
    """Create a queue DB with one initiative and one packet."""
    db = tmp_path / "test_runtime.db"
    bq.init_db(db)
    ba.init_db(db)
    bi.init_db(db)

    manifest = {
        "manifest_version": 1,
        "initiative_id": INITIATIVE,
        "title": "Test Runtime Initiative",
        "packets": [
            {
                "id": PACKET,
                "title": "Test Packet",
                "objective": "Run tests",
                "acceptance_criteria": ["Tests pass"],
                "allowed_paths": ["gateway/"],
                "policy": {"max_attempts": 2},
                "validation_commands": ["true"],
            }
        ],
    }
    bi.apply_manifest(manifest, db_path=db, repo_root=repo)
    return db


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRuntimeSnapshot:
    def test_produces_valid_snapshot(self, db_path: Path, repo: Path) -> None:
        snap = build_runtime_snapshot(db_path=db_path, repo_root=repo)
        assert snap["schema_version"] >= SCHEMA_VERSION
        assert "integrity" in snap
        assert "queue" in snap
        assert "initiatives" in snap
        assert "worker_sessions" in snap
        assert "generated_at" in snap
        assert snap["generated_at"] > 0

    def test_includes_git_state(self, db_path: Path, repo: Path) -> None:
        snap = build_runtime_snapshot(db_path=db_path, repo_root=repo)
        for initiative in snap["initiatives"]:
            for packet in initiative["packets"]:
                assert "git_state" in packet
                gs = packet["git_state"]
                assert "branch" in gs
                assert "head_sha" in gs
                assert "dirty" in gs
                assert "changed_paths" in gs
                assert "base_sha" in gs

    def test_includes_worker_session(self, db_path: Path, repo: Path) -> None:
        snap = build_runtime_snapshot(db_path=db_path, repo_root=repo)
        for initiative in snap["initiatives"]:
            for packet in initiative["packets"]:
                ws = packet.get("worker_session")
                assert ws is not None
                assert "session_id" in ws
                assert "backend" in ws
                assert "state" in ws
                assert "connected" in ws
                assert "model" in ws
                assert "provider" in ws

    def test_empty_database_does_not_crash(self) -> None:
        snap = build_runtime_snapshot()
        assert isinstance(snap, dict)
        assert "initiatives" in snap
        assert "worker_sessions" in snap

    def test_worker_sessions_summary(self, db_path: Path, repo: Path) -> None:
        snap = build_runtime_snapshot(db_path=db_path, repo_root=repo)
        ws = snap["worker_sessions"]
        assert "total" in ws
        assert "connected" in ws
        assert isinstance(ws["total"], int)

    def test_snapshot_stable_under_no_change(self, db_path: Path, repo: Path) -> None:
        snap1 = build_runtime_snapshot(db_path=db_path, repo_root=repo)
        snap1.pop("generated_at", None)
        snap2 = build_runtime_snapshot(db_path=db_path, repo_root=repo)
        snap2.pop("generated_at", None)
        assert snap1 == snap2


class TestWorkerStateInference:
    def test_starting(self) -> None:
        assert _infer_worker_state("starting", 12345, None, None) == WorkerState.STARTING

    def test_running_alive(self) -> None:
        assert _infer_worker_state("running", os.getpid(), None, None) == WorkerState.RUNNING

    def test_running_dead(self) -> None:
        assert _infer_worker_state("running", 99999, None, None) == WorkerState.FAILED

    def test_exited_success(self) -> None:
        assert _infer_worker_state("exited", None, 0, None) == WorkerState.COMPLETED

    def test_exited_failure(self) -> None:
        assert _infer_worker_state("exited", None, 1, None) == WorkerState.FAILED

    def test_cancelled(self) -> None:
        assert _infer_worker_state("cancelled", None, None, None) == WorkerState.CANCELLED

    def test_unknown_empty(self) -> None:
        assert _infer_worker_state("", None, None, None) == WorkerState.DISPOSED

    def test_failed(self) -> None:
        assert _infer_worker_state("failed", None, 1, None) == WorkerState.FAILED


class TestSafeHelpers:
    def test_isoformat_none(self) -> None:
        assert _safe_isoformat(None) is None

    def test_isoformat_string(self) -> None:
        assert _safe_isoformat("2024-01-01") == "2024-01-01"

    def test_list_normal(self) -> None:
        assert _safe_list(["a", "b"]) == ["a", "b"]

    def test_list_none(self) -> None:
        assert _safe_list(None) == []

    def test_list_non_list(self) -> None:
        assert _safe_list("not a list") == []


def test_default_connection_uses_canonical_builder_path(tmp_path, monkeypatch):
    from gateway import builder_runtime as runtime
    from gateway import paths

    expected = tmp_path / "isolated" / "builder_queue.db"
    expected.parent.mkdir(parents=True)
    monkeypatch.setattr(paths, "BUILDER_QUEUE_DB", expected)
    monkeypatch.chdir(tmp_path)

    conn = runtime._connect(None)
    try:
        actual = Path(conn.execute("PRAGMA database_list").fetchone()[2]).resolve()
    finally:
        conn.close()

    assert actual == expected.resolve()
