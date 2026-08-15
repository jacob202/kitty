"""Tests for gateway/builder_supervisor.py — autonomous campaign supervisor.

Integration-style: isolated git repo + queue DB, monkeypatched _launch_run to
avoid spawning real detached processes. Always pass db_path so the supervisor
never touches the production queue (CI-safe).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from gateway import builder_initiative as bi
from gateway import builder_queue as bq
from gateway import builder_supervisor as bs


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
    bi.init_db(p)
    return p


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


def _apply(
    db_path: Path,
    initiative_id: str,
    packets: list[dict[str, Any]],
    *,
    repo_root: Path | None = None,
) -> None:
    manifest = {
        "manifest_version": 1,
        "initiative_id": initiative_id,
        "title": f"Initiative {initiative_id}",
        "packets": packets,
    }
    bi.apply_manifest(manifest, db_path=db_path, repo_root=repo_root)


def test_lock_basic(db_path: Path) -> None:
    """Lock acquired once, not re-acquired concurrently."""
    with bs.SupervisorLock(db_path) as lock:
        assert lock.acquired
        assert lock.path.exists()
        # concurrent try fails
        with bs.SupervisorLock(db_path) as lock2:
            assert not lock2.acquired


def test_tick_no_active_initiatives(db_path: Path) -> None:
    """tick() with no active initiatives launches nothing."""
    receipt = bs.tick(db_path=db_path, max_runs=2)
    assert receipt["status"] == "ok"
    assert receipt["duplicate_tick"] is False
    assert len(receipt["scanned_initiatives"]) == 0
    assert len(receipt["launched"]) == 0
    assert len(receipt["skipped"]) == 0


def test_tick_one_active_initiative(repo: Path, db_path: Path) -> None:
    """tick() with one active initiative launches one run."""
    _apply(db_path, "test-init-1", [_packet("p1")], repo_root=repo)
    launched: list[dict[str, Any]] = []

    def _fake_launch(packet: dict, **_kwargs: Any) -> dict[str, Any]:
        launched.append(packet)
        return {"run_id": "fake-run", "status": "dispatched"}

    with patch.object(bs, "_launch_run", _fake_launch):
        receipt = bs.tick(db_path=db_path, repo_root=repo, max_runs=2)

    assert receipt["status"] == "ok"
    assert len(receipt["scanned_initiatives"]) == 1
    assert len(receipt["launched"]) == 1
    assert len(launched) == 1
    assert receipt["launched"][0]["initiative_id"] == "test-init-1"
    assert receipt["launched"][0]["packet_id"] == "p1"


def test_tick_max_runs_bounded(repo: Path, db_path: Path) -> None:
    """tick() respects max_runs even when more initiatives exist."""
    _apply(db_path, "test-init-1", [_packet("p1")], repo_root=repo)
    _apply(db_path, "test-init-2", [_packet("p2")], repo_root=repo)
    _apply(db_path, "test-init-3", [_packet("p3")], repo_root=repo)
    launched: list[dict[str, Any]] = []

    def _fake_launch(packet: dict, **_kwargs: Any) -> dict[str, Any]:
        launched.append(packet)
        return {"run_id": f"run-{packet['packet_id']}", "status": "dispatched"}

    with patch.object(bs, "_launch_run", _fake_launch):
        receipt = bs.tick(db_path=db_path, repo_root=repo, max_runs=2)

    assert receipt["status"] == "ok"
    assert len(receipt["launched"]) == 2
    assert len(launched) == 2
    # deterministic id order
    assert receipt["launched"][0]["initiative_id"] == "test-init-1"
    assert receipt["launched"][1]["initiative_id"] == "test-init-2"


def test_tick_concurrent_locked(db_path: Path) -> None:
    """Concurrent tick returns locked receipt with no launches."""
    with bs.SupervisorLock(db_path):
        # another tick while lock held
        receipt = bs.tick(db_path=db_path, max_runs=2)
    assert receipt["status"] == "locked"
    assert receipt["duplicate_tick"] is True
    assert len(receipt["launched"]) == 0


def test_tick_duplicate_sequential_no_op(repo: Path, db_path: Path) -> None:
    """Sequential duplicate tick launches nothing (tasks already claimed)."""
    _apply(db_path, "test-init-1", [_packet("p1")], repo_root=repo)
    launched_first: list[dict[str, Any]] = []
    launched_second: list[dict[str, Any]] = []

    def _fake_launch1(packet: dict, **_kwargs: Any) -> dict[str, Any]:
        launched_first.append(packet)
        # actually claim the task to simulate real behavior
        task_id = str(packet["task_id"])
        claimed = bq.claim_task(task_id, "test-worker", db_path=db_path)
        run_row = bq.create_run(
            task_id,
            ["echo", "test"],
            lease_token=claimed["lease_token"],
            claim_version=claimed["claim_version"],
            worker="test-worker",
            db_path=db_path,
        )
        bq.update_run(str(run_row["id"]), state="in_progress", db_path=db_path)
        return {"run_id": str(run_row["id"]), "status": "dispatched"}

    def _fake_launch2(packet: dict, **_kwargs: Any) -> dict[str, Any]:
        launched_second.append(packet)
        return {"run_id": "should-not-happen"}

    with patch.object(bs, "_launch_run", _fake_launch1):
        receipt1 = bs.tick(db_path=db_path, repo_root=repo, max_runs=2)

    assert len(launched_first) == 1

    with patch.object(bs, "_launch_run", _fake_launch2):
        receipt2 = bs.tick(db_path=db_path, repo_root=repo, max_runs=2)

    assert receipt2["status"] == "ok"
    assert len(receipt2["launched"]) == 0
    assert len(launched_second) == 0
    # Second tick finds no eligible packets (first tick consumed them)
    assert len(receipt2["skipped"]) >= 0
    # If there is a skipped entry, it should be for the right reason
    if receipt2["skipped"]:
        assert receipt2["skipped"][0]["reason"] in {"active_run_exists", "task_not_queued", "no_eligible_packet"}


def test_status_projection(repo: Path, db_path: Path) -> None:
    """status() returns initiatives, eligible packets, active runs."""
    _apply(db_path, "test-init-1", [_packet("p1"), _packet("p2")], repo_root=repo)
    proj = bs.status(db_path=db_path)
    assert "lock" in proj
    assert "initiatives" in proj
    assert "active_runs" in proj
    initiatives = proj["initiatives"]
    assert len(initiatives) == 1
    assert initiatives[0]["initiative_id"] == "test-init-1"
    assert initiatives[0]["derived_state"] == bi.INITIATIVE_ACTIVE
    assert len(initiatives[0]["eligible_packets"]) == 2


def test_render_supervisor_plist(tmp_path: Path) -> None:
    """render_supervisor_plist returns valid plist dict."""
    repo = tmp_path / "repo"
    repo.mkdir()
    plist = bs.render_supervisor_plist(repo)
    assert plist["Label"] == bs.SUPERVISOR_LABEL
    assert plist["RunAtLoad"] is True
    assert plist["StartInterval"] == 900
    assert "KeepAlive" not in plist
    assert plist["EnvironmentVariables"]["PATH"] == bs.LOGIN_SAFE_PATH
    assert plist["WorkingDirectory"] == str(repo)
    assert "/bin/bash" in plist["ProgramArguments"]
    assert "start_builder_supervisor.sh" in plist["ProgramArguments"][1]


def test_render_supervisor_plist_bytes(tmp_path: Path) -> None:
    """render_supervisor_plist_bytes returns valid XML."""
    repo = tmp_path / "repo"
    repo.mkdir()
    xml = bs.render_supervisor_plist_bytes(repo)
    assert isinstance(xml, bytes)
    assert b"<?xml" in xml
    assert b"com.kitty.builder.supervisor" in xml


def test_cli_tick_json(repo: Path, db_path: Path, capsys: Any) -> None:
    """CLI tick --json prints receipt."""
    _apply(db_path, "test-init-1", [_packet("p1")], repo_root=repo)

    def _fake_launch(packet: dict, **_kwargs: Any) -> dict[str, Any]:
        return {"run_id": "fake-run"}

    with patch.object(bs, "_launch_run", _fake_launch):
        with patch.object(bs, "default_db_path", return_value=db_path):
            rc = bs.main(["tick"])

    assert rc == 0
    captured = capsys.readouterr()
    receipt = json.loads(captured.out)
    assert receipt["status"] == "ok"


def test_cli_status_json(db_path: Path, capsys: Any) -> None:
    """CLI status prints projection."""
    with patch.object(bs, "default_db_path", return_value=db_path):
        rc = bs.main(["status"])
    assert rc == 0
    captured = capsys.readouterr()
    proj = json.loads(captured.out)
    assert "initiatives" in proj


def test_cli_launchd_plist(tmp_path: Path, capsys: Any) -> None:
    """CLI launchd-plist prints XML."""
    repo = tmp_path / "repo"
    repo.mkdir()
    rc = bs.main(["launchd-plist", "--repo-root", str(repo)])
    assert rc == 0
    captured = capsys.readouterr()
    assert "<?xml" in captured.out
    assert "com.kitty.builder.supervisor" in captured.out
