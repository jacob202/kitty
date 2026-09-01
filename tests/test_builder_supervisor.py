"""Tests for gateway/builder_supervisor.py — autonomous campaign supervisor.

Integration-style: isolated git repo + queue DB, monkeypatched _launch_run to
avoid spawning real detached processes. Always pass db_path so the supervisor
never touches the production queue (CI-safe).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from gateway import builder_initiative as bi
from gateway import builder_queue as bq
from gateway import builder_supervisor as bs
from gateway.builder_queue_runs import RUN_ACTIVE_STATES


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
) -> dict[str, Any]:
    manifest = {
        "manifest_version": 1,
        "initiative_id": initiative_id,
        "title": f"Initiative {initiative_id}",
        "packets": packets,
    }
    return bi.apply_manifest(manifest, db_path=db_path, repo_root=repo_root)


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
        bs.tick(db_path=db_path, repo_root=repo, max_runs=2)

    assert len(launched_first) == 1

    with patch.object(bs, "_launch_run", _fake_launch2):
        receipt2 = bs.tick(db_path=db_path, repo_root=repo, max_runs=2)

    assert receipt2["status"] == "ok"
    assert len(receipt2["launched"]) == 0
    assert len(launched_second) == 0



def test_selects_only_one_next_packet_per_initiative(repo: Path, db_path: Path) -> None:
    _apply(db_path, "test-init-1", [_packet("p1"), _packet("p2")], repo_root=repo)
    selected, _skipped = bs._select_packets(db_path, max_runs=2)
    assert [item["packet_id"] for item in selected] == ["p1"]



def test_select_packets_accepts_blocked_recovery_candidate(db_path: Path) -> None:
    packet = {"initiative_id": "test-init-1", "packet_id": "p1", "task_id": "task-1", "seq": 1}
    initiative = {"id": "test-init-1", "health_summary": {"state": bi.INITIATIVE_ACTIVE}}
    with patch.object(bs, "active_initiatives", return_value=[initiative]):
        with patch.object(bi, "next_packet", return_value=packet):
            with patch.object(bq, "get_task", return_value={"id": "task-1", "state": bq.BLOCKED}):
                with patch.object(bq, "list_runs", return_value=[]):
                    with patch.object(bs.ba, "list_stale_attempts", return_value=[{"id": "att-1"}]):
                        selected, skipped = bs._select_packets(db_path, max_runs=1)
    assert selected == [packet]
    assert skipped == []


def test_blocked_without_a_stale_attempt_needs_operator_release(db_path: Path) -> None:
    # run_packet refuses this exact case ("operator release is required"), so
    # dispatching it would burn one tick per packet forever while the receipt
    # claimed a launch. The supervisor must skip it with a nameable reason.
    packet = {"initiative_id": "test-init-1", "packet_id": "p1", "task_id": "task-1", "seq": 1}
    initiative = {"id": "test-init-1", "state": bi.INITIATIVE_ACTIVE}
    with patch.object(bi, "list_initiative_gates", return_value=[initiative]):
        with patch.object(bs, "active_initiatives", return_value=[initiative]):
            with patch.object(bi, "next_packet", return_value=packet):
                with patch.object(bq, "get_task", return_value={"id": "task-1", "state": bq.BLOCKED}):
                    with patch.object(bq, "list_runs", return_value=[]):
                        with patch.object(bs.ba, "list_stale_attempts", return_value=[]):
                            selected, skipped = bs._select_packets(db_path, max_runs=1)
                            counts = bs.dispatchable_counts(db_path)

    assert selected == []
    assert [s["reason"] for s in skipped] == ["needs_operator_release"]
    assert counts == {"now": 0, "on_hold": 0}

def test_rejects_max_runs_above_hard_ceiling(db_path: Path) -> None:
    with pytest.raises(ValueError, match="at most"):
        bs.tick(db_path=db_path, max_runs=bs.MAX_RUNS_PER_TICK + 1)


def test_tick_reports_launch_failure(repo: Path, db_path: Path) -> None:
    _apply(db_path, "test-init-1", [_packet("p1")], repo_root=repo)
    with patch.object(bs, "_launch_run", side_effect=RuntimeError("boom")):
        receipt = bs.tick(db_path=db_path, repo_root=repo)
    assert receipt["status"] == "error"
    assert receipt["launched"][0]["error"] == "RuntimeError: boom"


def test_lock_propagates_non_contention_oserror(db_path: Path) -> None:
    import errno
    with patch("fcntl.flock", side_effect=OSError(errno.EIO, "io failure")):
        with pytest.raises(OSError, match="io failure"):
            with bs.SupervisorLock(db_path):
                pass


def test_direct_module_tick_honors_queue_kill_switch(db_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KITTY_BUILDER_QUEUE_ENABLED", "0")
    with patch.object(bs, "default_db_path", return_value=db_path):
        with patch.object(bs, "tick") as tick_mock:
            rc = bs.main(["tick"])
    assert rc == 1
    tick_mock.assert_not_called()


def test_launch_run_detaches_canonical_packet_loop(repo: Path, db_path: Path) -> None:
    kitty = repo / "kitty"
    kitty.write_text("#!/bin/sh\n", encoding="utf-8")
    kitty.chmod(0o755)
    result_apply = _apply(db_path, "test-init-1", [_packet("p1")], repo_root=repo)
    task_id = result_apply["packets"][0]["task_id"]
    packet = {"initiative_id": "test-init-1", "packet_id": "p1", "task_id": task_id}

    with patch("gateway.builder_supervisor.subprocess.Popen") as popen, patch.object(
        bs, "_wait_for_durable_claim", return_value={"claim_version": 1}
    ):
        popen.return_value.pid = 4321
        result = bs._launch_run(packet, repo_root=repo, db_path=db_path)

    argv = popen.call_args.args[0]
    assert argv == [str(kitty), "builder", "initiative", "run-packet", "test-init-1", "p1", "--paid", "--tier", "cheap", "--json"]
    assert popen.call_args.kwargs["start_new_session"] is True
    assert popen.call_args.kwargs["shell"] is False
    assert len(popen.call_args.kwargs["pass_fds"]) == 1
    assert result["status"] == "dispatched"
    assert result["launcher_pid"] == 4321
    assert result["task_id"] == task_id


def test_launch_run_refuses_when_task_already_claimed(repo: Path, db_path: Path) -> None:
    """_launch_run must not launch if the task left dispatchable state."""
    kitty = repo / "kitty"
    kitty.write_text("#!/bin/sh\n", encoding="utf-8")
    kitty.chmod(0o755)
    result_apply = _apply(db_path, "test-init-1", [_packet("p1")], repo_root=repo)
    task_id = result_apply["packets"][0]["task_id"]
    # Claim the task so it is no longer dispatchable
    bq.claim_task(task_id, "other-worker", db_path=db_path)
    packet = {"initiative_id": "test-init-1", "packet_id": "p1", "task_id": task_id}

    with pytest.raises(bs.SupervisorError, match="not dispatchable"):
        bs._launch_run(packet, repo_root=repo, db_path=db_path)



def test_wait_for_durable_claim_timeout_terminates_the_detached_process_group(monkeypatch) -> None:
    class FakeProcess:
        pid = 4321
        def poll(self):
            return None
        def wait(self, timeout=None):
            self.wait_timeout = timeout
            return 0

    process = FakeProcess()
    monkeypatch.setattr(bs.bq, "get_task", lambda *_args, **_kwargs: {"id": "task-1", "state": bq.QUEUED, "claim_version": 3})
    clock = iter([0.0, 2.0])
    monkeypatch.setattr(bs.time, "monotonic", lambda: next(clock))
    killed = []
    monkeypatch.setattr(bs.os, "killpg", lambda pgid, sig: killed.append((pgid, sig)))

    with pytest.raises(bs.SupervisorError, match="did not durably claim"):
        bs._wait_for_durable_claim(
            "task-1", process, initial_claim_version=3, db_path=None, timeout_seconds=1.0
        )

    assert killed == [(4321, bs.signal.SIGTERM)]
    assert process.wait_timeout == 2.0


def test_wait_for_durable_claim_requires_claim_version_to_advance(monkeypatch) -> None:
    class FakeProcess:
        pid = 4321
        def poll(self):
            return None
        def terminate(self):
            raise AssertionError("claimed child must not be terminated")

    rows = iter([
        {"id": "task-1", "state": bq.QUEUED, "claim_version": 3},
        {"id": "task-1", "state": bq.CLAIMED, "claim_version": 4},
    ])
    monkeypatch.setattr(bs.bq, "get_task", lambda *_args, **_kwargs: next(rows))
    monkeypatch.setattr(bs.time, "sleep", lambda _seconds: None)

    claim = bs._wait_for_durable_claim(
        "task-1", FakeProcess(), initial_claim_version=3, db_path=None, timeout_seconds=1.0
    )
    assert claim["claim_version"] == 4


def test_scheduler_state_comes_from_loaded_launchd_job(monkeypatch) -> None:
    class Result:
        returncode = 0
        stderr = ""
    monkeypatch.delenv("KITTY_BUILDER_QUEUE_ENABLED", raising=False)
    monkeypatch.setattr(bs.subprocess, "run", lambda *args, **kwargs: Result())
    assert bs._scheduler_enabled() is True


def test_scheduler_state_is_false_when_queue_kill_switch_is_off(monkeypatch) -> None:
    monkeypatch.setenv("KITTY_BUILDER_QUEUE_ENABLED", "0")
    assert bs._scheduler_enabled() is False


def test_scheduler_state_is_unknown_when_launchctl_is_unavailable(monkeypatch) -> None:
    monkeypatch.delenv("KITTY_BUILDER_QUEUE_ENABLED", raising=False)
    monkeypatch.setattr(bs.subprocess, "run", lambda *args, **kwargs: (_ for _ in ()).throw(FileNotFoundError()))
    assert bs._scheduler_enabled() is None



def test_task_dispatch_lock_handoff_stays_held_until_child_exits(db_path: Path) -> None:
    with bs.TaskDispatchLock("task-1", db_path) as lock:
        assert lock.acquired
        child = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(0.6)"],
            pass_fds=(lock.fileno,),
            close_fds=True,
        )
        lock.handoff_to_child()

    with bs.TaskDispatchLock("task-1", db_path) as contender:
        assert contender.acquired is False

    child.wait(timeout=3)
    with bs.TaskDispatchLock("task-1", db_path) as contender:
        assert contender.acquired is True


def test_dispatch_candidate_skips_live_supervisor_child_fence(db_path: Path) -> None:
    packet = {"initiative_id": "init-1", "packet_id": "p1", "task_id": "task-1", "seq": 1}
    initiative = {"id": "init-1", "state": bi.INITIATIVE_ACTIVE}
    with patch.object(bs, "active_initiatives", return_value=[initiative]):
        with patch.object(bi, "next_packet", return_value=packet):
            with patch.object(bq, "get_task", return_value={"id": "task-1", "state": bq.QUEUED}):
                with bs.TaskDispatchLock("task-1", db_path):
                    selected, skipped = bs._select_packets(db_path, max_runs=1)

    assert selected == []
    assert [entry["reason"] for entry in skipped] == ["dispatch_in_progress"]

def test_supervisor_launcher_defaults_to_repo_venv() -> None:
    launcher = (Path(__file__).parents[1] / "scripts" / "start_builder_supervisor.sh").read_text()
    assert 'PYTHON="${KITTYBUILDER_PYTHON:-${REPO_ROOT}/venv/bin/python}"' in launcher


def test_supervisor_launcher_loads_canonical_env_with_safe_loader() -> None:
    launcher = (Path(__file__).parents[1] / "scripts" / "start_builder_supervisor.sh").read_text()
    assert 'source "${REPO_ROOT}/gateway/lib/load_env_safe.sh"' in launcher
    assert 'ENV_ROOT="${KITTY_BUILDER_REPO_ROOT:-${REPO_ROOT}}"' in launcher
    assert 'load_env_assignments "${ENV_ROOT}/.env"' in launcher

def test_budget_summary_initializes_an_empty_compute_ledger(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ledger = tmp_path / "compute-governor.db"
    monkeypatch.setenv("KITTY_COMPUTE_GOVERNOR_DB", str(ledger))

    summary = bs.budget_summary()

    assert summary["weekly_budget_cad"] == 6.0
    assert summary["estimated_spend_cad"] == 0.0
    assert summary["runs"] == 0
    assert ledger.exists()


def test_control_plane_summary_disables_scheduler_actions_when_contract_is_unhealthy(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(bs, "dispatchable_counts", lambda _db=None: {"now": 1, "on_hold": 0})
    monkeypatch.setattr(bs, "active_runs_summary", lambda _db=None: [])
    monkeypatch.setattr(bs, "budget_summary", lambda: {})
    monkeypatch.setattr(bs, "_scheduler_enabled", lambda: True)
    monkeypatch.setattr(bs, "scheduler_status", lambda: {"healthy": False, "loaded": True, "installed": True})
    monkeypatch.setattr(bs, "_lock_path", lambda _db=None: tmp_path / "supervisor.lock")

    summary = bs.control_plane_summary()

    assert summary["scheduler_enabled"] is False
    assert summary["scheduler"]["healthy"] is False


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




def test_scheduler_status_reads_installed_launchagent(repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bs.sys, "platform", "darwin")
    plist_path = tmp_path / "com.kitty.builder.supervisor.plist"
    plist_path.write_bytes(bs.render_supervisor_plist_bytes(repo))

    class Completed:
        returncode = 0
        stdout = "pid = 123\nlast exit code = 0\n"
        stderr = ""

    monkeypatch.setattr(bs.subprocess, "run", lambda *args, **kwargs: Completed())
    result = bs.scheduler_status(repo, plist_path=plist_path)

    assert result["installed"] is True
    assert result["loaded"] is True
    assert result["healthy"] is True
    assert result["start_interval_seconds"] == 900
    assert result["pid"] == 123
    assert result["last_exit_status"] == 0
    assert result["last_tick_at"] is None
    assert result["next_run_at"] is None


def test_scheduler_status_reports_missing_plist(repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bs.sys, "platform", "darwin")
    result = bs.scheduler_status(repo, plist_path=tmp_path / "missing.plist")
    assert result["installed"] is False
    assert result["healthy"] is False
    assert "not installed" in result["reason"]

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


def test_dispatchable_counts_matches_what_a_tick_would_launch(
    repo: Path, db_path: Path
) -> None:
    _apply(db_path, "init-active", [_packet("p1")], repo_root=repo)
    counts = bs.dispatchable_counts(db_path)
    selected, _skipped = bs._select_packets(db_path, max_runs=1)
    assert counts == {"now": 1, "on_hold": 0}
    assert len(selected) == 1


def test_dispatchable_counts_parks_paused_initiatives(repo: Path, db_path: Path) -> None:
    _apply(db_path, "init-paused", [_packet("p1")], repo_root=repo)
    bi.pause_initiative("init-paused", reason="operator", db_path=db_path)

    counts = bs.dispatchable_counts(db_path)
    selected, _skipped = bs._select_packets(db_path, max_runs=1)

    # Dispatchable in every respect except its initiative, so a tick will never
    # take it — that is exactly the difference on_hold reports.
    assert counts == {"now": 0, "on_hold": 1}
    assert selected == []


def test_dispatchable_counts_include_blocked_recovery_work(db_path: Path) -> None:
    # The count and the launcher must agree that a BLOCKED packet is a
    # recovery candidate. Counting only queued work under-reports what
    # pressing "Start Builder" actually starts.
    packet = {"initiative_id": "init-1", "packet_id": "p1", "task_id": "task-1", "seq": 1}
    initiative = {"id": "init-1", "state": bi.INITIATIVE_ACTIVE}
    with patch.object(bi, "list_initiative_gates", return_value=[initiative]):
        with patch.object(bs, "active_initiatives", return_value=[initiative]):
            with patch.object(bi, "next_packet", return_value=packet):
                with patch.object(bq, "get_task", return_value={"id": "task-1", "state": bq.BLOCKED}):
                    with patch.object(bq, "list_runs", return_value=[]):
                        with patch.object(bs.ba, "list_stale_attempts", return_value=[{"id": "att-1"}]):
                            counts = bs.dispatchable_counts(db_path)
                            selected, _ = bs._select_packets(db_path, max_runs=1)

    assert counts["now"] == 1
    assert len(selected) == 1


def test_dispatchable_counts_exclude_work_already_running(db_path: Path) -> None:
    packet = {"initiative_id": "init-1", "packet_id": "p1", "task_id": "task-1", "seq": 1}
    initiative = {"id": "init-1", "state": bi.INITIATIVE_ACTIVE}
    running = [{"id": "run-1", "state": sorted(RUN_ACTIVE_STATES)[0]}]
    with patch.object(bi, "list_initiative_gates", return_value=[initiative]):
        with patch.object(bs, "active_initiatives", return_value=[initiative]):
            with patch.object(bi, "next_packet", return_value=packet):
                with patch.object(bq, "get_task", return_value={"id": "task-1", "state": bq.QUEUED}):
                    with patch.object(bq, "list_runs", return_value=running):
                        counts = bs.dispatchable_counts(db_path)
                        selected, _ = bs._select_packets(db_path, max_runs=1)

    assert counts == {"now": 0, "on_hold": 0}
    assert selected == []


def test_superseded_initiative_is_not_launchable_or_counted_on_hold(repo: Path, db_path: Path) -> None:
    _apply(db_path, "old-init", [_packet("p1")], repo_root=repo)
    bi.supersede_initiative("old-init", "KITTY-RECOVERY-001", db_path=db_path)

    counts = bs.dispatchable_counts(db_path)
    selected, _ = bs._select_packets(db_path, max_runs=1)

    assert counts == {"now": 0, "on_hold": 0}
    assert selected == []


def test_tick_skips_packet_when_current_main_changed_its_allowed_path(
    repo: Path, db_path: Path
) -> None:
    _apply(db_path, "stale-init", [_packet("p1")], repo_root=repo)
    (repo / "done.txt").write_text("new main behavior\n", encoding="utf-8")
    subprocess.run(["git", "add", "done.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "touch packet path"], cwd=repo, check=True)

    with patch.object(bs, "_launch_run") as launch:
        with patch.object(bs, "github_truth_snapshot", return_value={"available": True, "by_head": {}, "error": None}):
            receipt = bs.tick(db_path=db_path, repo_root=repo, max_runs=1)

    launch.assert_not_called()
    assert receipt["launched"] == []
    assert receipt["skipped"][0]["reason"] == "preflight_blocked"
    assert receipt["skipped"][0]["freshness"]["relevant_paths_changed"] == ["done.txt"]


def test_tick_skips_packet_when_builder_branch_already_has_open_pr(
    repo: Path, db_path: Path
) -> None:
    applied = _apply(db_path, "pr-init", [_packet("p1")], repo_root=repo)
    task_id = applied["packets"][0]["task_id"]
    from gateway.builder_brief import default_branch_name
    task = bq.get_task(task_id, db_path=db_path)
    assert task is not None
    branch = default_branch_name(task)
    truth = {
        "available": True,
        "error": None,
        "by_head": {branch: {"number": 999, "state": "OPEN", "mergedAt": None, "headRefName": branch}},
    }

    with patch.object(bs, "github_truth_snapshot", return_value=truth):
        with patch.object(bs, "_launch_run") as launch:
            receipt = bs.tick(db_path=db_path, repo_root=repo, max_runs=1)

    launch.assert_not_called()
    assert receipt["launched"] == []
    assert receipt["skipped"][0]["reason"] == "github_pr_already_exists"
    assert receipt["skipped"][0]["pr_number"] == 999


def test_status_exposes_read_only_autonomy_projection(repo: Path, db_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _apply(db_path, "autonomy-status", [_packet("p1")], repo_root=repo)
    before = bq.get_task(bi.get_initiative("autonomy-status", db_path=db_path)["packets"][0]["task_id"], db_path=db_path)
    monkeypatch.setattr(bs, "github_truth_snapshot", lambda _root: {"available": True, "error": None, "by_head": {}, "pr_count": 0})

    projection = bs.status(db_path=db_path, repo_root=repo)

    autonomy = projection["autonomy"]
    assert autonomy["reconciliation"]["github_available"] is True
    assert autonomy["runway"]["counts"]["safe_backend_runnable"] == 1
    assert autonomy["refill"]["needed"] is True
    assert autonomy["publication_inbox"] == []
    after = bq.get_task(before["id"], db_path=db_path)
    assert after["state"] == before["state"]
    assert after["claim_version"] == before["claim_version"]


def test_status_scopes_autonomy_projection_by_initiative_prefix(
    repo: Path, db_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _apply(db_path, "campaign-v1", [_packet("p1")], repo_root=repo)
    _apply(db_path, "historical-v1", [_packet("p2")], repo_root=repo)
    monkeypatch.setattr(
        bs,
        "github_truth_snapshot",
        lambda _root: {"available": True, "error": None, "by_head": {}, "pr_count": 0},
    )

    projection = bs.status(
        db_path=db_path, repo_root=repo, initiative_prefix="campaign-v"
    )

    runway = projection["autonomy"]["runway"]
    assert runway["counts"]["safe_backend_runnable"] == 1
    assert [item["initiative_id"] for item in runway["buckets"]["safe_backend_runnable"]] == ["campaign-v1"]
    assert projection["autonomy"]["publication_inbox"] == []


def test_github_truth_snapshot_requests_deep_history(repo: Path) -> None:
    calls: list[list[str]] = []

    class Result:
        returncode = 0
        stdout = "[]"
        stderr = ""

    def runner(args, **_kwargs):
        calls.append(args)
        return Result()

    truth = bs.github_truth_snapshot(repo, run_cmd=runner)

    assert truth["available"] is True
    args = calls[0]
    assert args[args.index("--limit") + 1] == str(bs.GITHUB_PR_SNAPSHOT_LIMIT)
    assert bs.GITHUB_PR_SNAPSHOT_LIMIT >= 1000


def test_tick_fails_closed_when_github_truth_is_unavailable(
    repo: Path, db_path: Path
) -> None:
    _apply(db_path, "truth-init", [_packet("p1")], repo_root=repo)
    unavailable = {"available": False, "error": "gh unavailable", "by_head": {}}

    with patch.object(bs, "github_truth_snapshot", return_value=unavailable):
        with patch.object(bs, "_launch_run") as launch:
            receipt = bs.tick(db_path=db_path, repo_root=repo, max_runs=1)

    launch.assert_not_called()
    assert receipt["launched"] == []
    assert receipt["skipped"][0]["reason"] == "github_truth_unavailable"
    assert receipt["reconciliation"]["github_available"] is False


def test_github_truth_snapshot_marks_limit_hit_incomplete(repo: Path) -> None:
    rows = [
        {"number": i + 1, "state": "CLOSED", "mergedAt": None, "headRefName": f"branch-{i}"}
        for i in range(bs.GITHUB_PR_SNAPSHOT_LIMIT)
    ]

    class Result:
        returncode = 0
        stdout = json.dumps(rows)
        stderr = ""

    truth = bs.github_truth_snapshot(repo, run_cmd=lambda *_args, **_kwargs: Result())

    assert truth["available"] is False
    assert truth["complete"] is False
    assert "limit" in truth["error"]


def test_github_truth_snapshot_prefers_open_pr_for_reused_branch(repo: Path) -> None:
    rows = [
        {"number": 10, "state": "CLOSED", "mergedAt": None, "headRefName": "kittybuilder/task"},
        {"number": 11, "state": "OPEN", "mergedAt": None, "headRefName": "kittybuilder/task"},
    ]

    class Result:
        returncode = 0
        stdout = json.dumps(rows)
        stderr = ""

    truth = bs.github_truth_snapshot(repo, run_cmd=lambda *_args, **_kwargs: Result())

    assert truth["available"] is True
    assert truth["by_head"]["kittybuilder/task"]["number"] == 11


def test_tick_uses_one_fresh_main_snapshot_for_multiple_packets(
    repo: Path, db_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _apply(db_path, "snapshot-a", [_packet("p1")], repo_root=repo)
    _apply(db_path, "snapshot-b", [_packet("p2")], repo_root=repo)
    real_fresh = bs._fresh_main_sha
    calls = 0

    def counted_fresh(root: Path) -> str:
        nonlocal calls
        calls += 1
        return real_fresh(root)

    monkeypatch.setattr(bs, "_fresh_main_sha", counted_fresh)
    monkeypatch.setattr(
        bs,
        "github_truth_snapshot",
        lambda _root: {"available": True, "complete": True, "error": None, "by_head": {}, "pr_count": 0},
    )
    monkeypatch.setattr(
        bs,
        "_launch_run",
        lambda packet, **_kwargs: {"status": "dispatched", "task_id": packet["task_id"]},
    )

    receipt = bs.tick(db_path=db_path, repo_root=repo, max_runs=2)

    assert receipt["status"] == "ok"
    assert len(receipt["launched"]) == 2
    assert calls == 1


def test_direct_supervisor_status_forwards_initiative_prefix(capsys) -> None:
    projection = {
        "lock": {"path": "/tmp/lock"},
        "initiatives": [],
        "active_runs": [],
        "scheduler_enabled": True,
        "autonomy": {},
    }
    with patch.object(bs, "status", return_value=projection) as status_mock:
        rc = bs.main(["status", "--initiative-prefix", "campaign-v"])

    assert rc == 0
    status_mock.assert_called_once_with(initiative_prefix="campaign-v")
    assert json.loads(capsys.readouterr().out) == projection


def test_status_registry_count_respects_initiative_prefix(
    repo: Path, db_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from gateway import builder_autonomy as bau

    monkeypatch.setattr(
        bs,
        "github_truth_snapshot",
        lambda _root: {"available": True, "complete": True, "error": None, "by_head": {}, "pr_count": 0},
    )
    monkeypatch.setattr(
        bau,
        "load_packet_registry",
        lambda _root: [
            {"initiative_id": "campaign-v1", "packet_id": "UI-1", "lane": "interactive", "status": "unresolved"},
            {"initiative_id": "history-v1", "packet_id": "UI-OLD", "lane": "interactive", "status": "unresolved"},
        ],
    )

    projection = bs.status(
        db_path=db_path, repo_root=repo, initiative_prefix="campaign-v"
    )

    assert projection["autonomy"]["registry_contracts"] == 1
    assert projection["autonomy"]["runway"]["counts"]["interactive_frontend"] == 1


def test_paths_overlap_treats_repo_root_as_wildcard() -> None:
    assert bs._paths_overlap(".", "gateway/state_composer.py") is True
    assert bs._paths_overlap("gateway/state_composer.py", ".") is True


def test_changed_paths_reports_both_sides_of_rename(repo: Path) -> None:
    old = repo / "old-name.txt"
    old.write_text("before\n", encoding="utf-8")
    subprocess.run(["git", "add", "old-name.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "add old name"], cwd=repo, check=True)
    base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()
    subprocess.run(["git", "mv", "old-name.txt", "new-name.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "rename"], cwd=repo, check=True)
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()

    assert set(bs._changed_paths(repo, base, head)) == {"old-name.txt", "new-name.txt"}


def test_preflight_allows_blocked_task_with_fenced_stale_attempt(
    repo: Path, db_path: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    applied = _apply(db_path, "recover-init", [_packet("p1")], repo_root=repo)
    task_id = applied["packets"][0]["task_id"]
    real_task = bq.get_task(task_id, db_path=db_path)
    assert real_task is not None
    monkeypatch.setattr(bs.bq, "get_task", lambda *_args, **_kwargs: {**real_task, "state": bq.BLOCKED})
    monkeypatch.setattr(bs.ba, "list_stale_attempts", lambda *_args, **_kwargs: [{"id": "stale-1"}])
    monkeypatch.setattr(
        bs.bi,
        "derive_packet_eligibility",
        lambda **_kwargs: {"state": "not_queued", "blocked_by": []},
    )

    result = bs.preflight_packet(
        "recover-init", "p1", db_path=db_path,
        ledger_db_path=tmp_path / "governor.db",
    )

    assert result["action"] == bs.PREFLIGHT_RUN


def test_dispatchable_counts_with_live_truth_applies_same_preflight_as_tick(repo: Path, db_path: Path, monkeypatch):
    _apply(db_path, "live-count", [_packet("p1")], repo_root=repo)
    monkeypatch.setattr(bs, "preflight_packet", lambda *_a, **_k: {"action": bs.PREFLIGHT_BLOCKED, "reasons": ["budget"]})
    counts = bs.dispatchable_counts(
        db_path,
        repo_root=repo,
        github_truth={"available": True, "by_head": {}, "error": None},
        current_main_sha=subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True).stdout.strip(),
    )
    assert counts["now"] == 0


def test_replenishment_reports_low_water_without_config(repo: Path, db_path: Path, monkeypatch) -> None:
    monkeypatch.delenv(bs.SLATE_AUTHOR_ARGV_ENV, raising=False)
    result = bs.replenish_runway_if_needed(usable_runway=2, target=6, repo_root=repo, db_path=db_path)
    assert result["replenishment_needed"] is True
    assert result["launched"] is False
    assert result["reason"] == "no_author_configured"


def test_replenishment_rejects_author_outside_trusted_repo(repo: Path, db_path: Path, monkeypatch) -> None:
    monkeypatch.setenv(bs.SLATE_AUTHOR_ARGV_ENV, json.dumps(["/bin/echo", "nope"]))
    result = bs.replenish_runway_if_needed(usable_runway=0, target=6, repo_root=repo, db_path=db_path)
    assert result["replenishment_needed"] is True
    assert result["launched"] is False
    assert result["reason"] == "invalid_author_config"


def test_replenishment_is_single_flight_and_receipt_redacts_argv(repo: Path, db_path: Path, monkeypatch) -> None:
    scripts = repo / "scripts"
    scripts.mkdir()
    author = scripts / "author.sh"
    author.write_text("#!/bin/sh\nsleep 30\n", encoding="utf-8")
    author.chmod(0o755)
    monkeypatch.setenv(bs.SLATE_AUTHOR_ARGV_ENV, json.dumps(["scripts/author.sh", "--secret", "do-not-log"]))

    first = bs.replenish_runway_if_needed(usable_runway=1, target=6, repo_root=repo, db_path=db_path)
    try:
        assert first["launched"] is True
        assert first["reason"] == "low_water_launched"
        assert first["pid"] > 0
        second = bs.replenish_runway_if_needed(usable_runway=1, target=6, repo_root=repo, db_path=db_path)
        assert second["launched"] is False
        assert second["reason"] == "author_in_flight"
        assert second["pid"] == first["pid"]
        receipt = json.loads(bs.replenisher_receipt_path(db_path).read_text(encoding="utf-8"))
        assert receipt["argv_count"] == 3
        assert receipt["executable"] == "scripts/author.sh"
        assert "do-not-log" not in json.dumps(receipt)
    finally:
        try:
            os.kill(int(first.get("pid") or 0), 9)
        except (OSError, ValueError):
            pass


def test_replenishment_healthy_never_launches(repo: Path, db_path: Path, monkeypatch) -> None:
    monkeypatch.setenv(bs.SLATE_AUTHOR_ARGV_ENV, "not-json")
    result = bs.replenish_runway_if_needed(usable_runway=6, target=6, repo_root=repo, db_path=db_path)
    assert result == {
        "replenishment_needed": False,
        "launched": False,
        "reason": "runway_healthy",
        "usable_runway": 6,
        "target": 6,
    }
