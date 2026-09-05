"""Phase 1C-alpha tests for gateway/builder_runner.py — shadow-mode runner.

Uses a real throwaway git repo per test (worktree behavior can't be mocked
honestly) and a tmp queue DB. Worker commands are tiny shell scripts.
"""

from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from gateway import agent_coordination as ac
from gateway import builder_queue as bq
from gateway import builder_runner as br

pytestmark = pytest.mark.integration


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A git repo with one commit on main."""
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
    subprocess.run(
        ["git", "config", "user.email", "t@t"], cwd=root, check=True
    )
    subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)
    (root / "README.md").write_text("hello\n")
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "init"], cwd=root, check=True
    )
    return root


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    p = tmp_path / "queue" / "builder_queue.db"
    bq.init_db(p)
    return p


@pytest.fixture(autouse=True)
def isolated_runner_kx(tmp_path: Path, monkeypatch) -> None:
    registry = tmp_path / "runner-kx-resources.yaml"
    registry.write_text(
        "resources:\n  test:all:\n    paths:\n      - '**'\n",
        encoding="utf-8",
    )
    coordination_db = tmp_path / "runner-kx.db"
    kitty_data_root = tmp_path / "kitty-data"
    workspace_db = kitty_data_root / "kitty" / "kitty.db"
    monkeypatch.setattr(ac, "DEFAULT_REGISTRY_PATH", registry)
    monkeypatch.setattr(ac, "default_db_path", lambda: coordination_db)
    monkeypatch.setattr(ac.agent_workspace, "WORKSPACE_DB_FILE", workspace_db)
    monkeypatch.setenv("KITTY_DATA_ROOT", str(kitty_data_root))
    monkeypatch.setenv("KITTY_COORDINATION_DB_PATH", str(coordination_db))
    monkeypatch.setenv("KITTY_COORDINATION_REGISTRY_PATH", str(registry))



def _queued_task(db_path: Path, **kwargs) -> dict:
    if "allowed_paths" not in kwargs:
        kwargs["allowed_paths"] = ["."]
    return bq.create_task("runner test task", db_path=db_path, **kwargs)


# ---------------------------------------------------------------------------
# Worktree management
# ---------------------------------------------------------------------------


class TestEnsureWorktree:
    def test_creates_worktree_on_branch(self, repo: Path):
        path = br.ensure_worktree("kb_t1_aaaa", "kittybuilder/kb_t1_aaaa", repo_root=repo)
        assert path.exists()
        head = subprocess.run(
            ["git", "symbolic-ref", "--short", "HEAD"],
            cwd=path, capture_output=True, text=True,
        )
        assert head.stdout.strip() == "kittybuilder/kb_t1_aaaa"

    def test_worktree_add_allows_checkout_longer_than_generic_git_timeout(self, repo: Path):
        real_run = subprocess.run
        observed_timeouts = []

        def guarded_run(args, *positional, **kwargs):
            if list(args[:3]) == ["git", "worktree", "add"]:
                observed_timeouts.append(kwargs.get("timeout"))
                if (kwargs.get("timeout") or 0) <= 15:
                    raise subprocess.TimeoutExpired(args, kwargs.get("timeout"))
            return real_run(args, *positional, **kwargs)

        with patch.object(br.subprocess, "run", side_effect=guarded_run):
            path = br.ensure_worktree(
                "kb_slow_checkout", "kittybuilder/kb_slow_checkout", repo_root=repo
            )

        assert path.exists()
        assert observed_timeouts and observed_timeouts[0] > 15

    def test_worktree_add_timeout_removes_partial_initializing_tree(self, repo: Path):
        real_run = subprocess.run
        task_id = "kb_partial_timeout"
        path = repo / ".worktrees" / "kittybuilder" / task_id

        def timed_out_run(args, *positional, **kwargs):
            if list(args[:3]) == ["git", "worktree", "add"]:
                path.mkdir(parents=True, exist_ok=True)
                (path / "partial.txt").write_text("incomplete checkout\n")
                raise subprocess.TimeoutExpired(args, kwargs.get("timeout"))
            return real_run(args, *positional, **kwargs)

        with patch.object(br.subprocess, "run", side_effect=timed_out_run):
            with pytest.raises(br.RunnerError, match="worktree add timed out"):
                br.ensure_worktree(
                    task_id, f"kittybuilder/{task_id}", repo_root=repo
                )

        assert not path.exists()

    def test_reuses_clean_worktree(self, repo: Path):
        p1 = br.ensure_worktree("kb_t2_aaaa", "kittybuilder/kb_t2_aaaa", repo_root=repo)
        p2 = br.ensure_worktree("kb_t2_aaaa", "kittybuilder/kb_t2_aaaa", repo_root=repo)
        assert p1 == p2

    def test_reuses_worktree_with_opencode_continuation_residue(self, repo: Path):
        path = br.ensure_worktree("kb_t2_omo", "kittybuilder/kb_t2_omo", repo_root=repo)
        continuation = path / ".omo" / "run-continuation" / "session.json"
        continuation.parent.mkdir(parents=True)
        continuation.write_text("runtime receipt\n")

        reused = br.ensure_worktree(
            "kb_t2_omo", "kittybuilder/kb_t2_omo", repo_root=repo
        )

        assert reused == path

    def test_refuses_dirty_worktree(self, repo: Path):
        path = br.ensure_worktree("kb_t3_aaaa", "kittybuilder/kb_t3_aaaa", repo_root=repo)
        (path / "junk.txt").write_text("partial progress")
        with pytest.raises(br.RunnerError, match="dirty"):
            br.ensure_worktree("kb_t3_aaaa", "kittybuilder/kb_t3_aaaa", repo_root=repo)

    def test_refuses_wrong_branch(self, repo: Path):
        br.ensure_worktree("kb_t4_aaaa", "kittybuilder/kb_t4_aaaa", repo_root=repo)
        with pytest.raises(br.RunnerError, match="refusing to reuse"):
            br.ensure_worktree("kb_t4_aaaa", "some/other-branch", repo_root=repo)

    def test_reuse_dirty_accepts_truthful_dirty(self, repo: Path):
        path = br.ensure_worktree(
            "kb_reuse_dirty_t1", "kittybuilder/kb_reuse_dirty_t1", repo_root=repo
        )
        (path / "retained.txt").write_text("repair input")
        reused = br.ensure_worktree(
            "kb_reuse_dirty_t1",
            "kittybuilder/kb_reuse_dirty_t1",
            repo_root=repo,
            reuse_dirty=True,
        )
        assert reused == path

    def test_reuse_dirty_still_raises_on_status_failure(self, repo: Path):
        path = br.ensure_worktree(
            "kb_reuse_dirty_t2", "kittybuilder/kb_reuse_dirty_t2", repo_root=repo
        )
        (path / "junk.txt").write_text("whatever")
        real_git = br._git

        def flaky_status(args, cwd):
            result = real_git(args, cwd=cwd)
            if args and args[0] == "status":
                return subprocess.CompletedProcess(
                    args=args,
                    returncode=128,
                    stdout="",
                    stderr="fatal: not a git repository",
                )
            return result

        with patch.object(br, "_git", side_effect=flaky_status):
            with pytest.raises(br.RunnerError, match="git status failed"):
                br.ensure_worktree(
                    "kb_reuse_dirty_t2",
                    "kittybuilder/kb_reuse_dirty_t2",
                    repo_root=repo,
                    reuse_dirty=True,
                )

    def test_archive_reset_returns_committed_changes_to_durable_base(
        self, repo: Path, tmp_path: Path
    ):
        base_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        path = br.ensure_worktree(
            "kb_reset_base", "kittybuilder/kb_reset_base", repo_root=repo
        )
        (path / "committed.txt").write_text("must not leak into retry\n")
        subprocess.run(["git", "add", "committed.txt"], cwd=path, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "worker commit"], cwd=path, check=True)
        assert br.worktree_head(path) != base_sha

        evidence = tmp_path / "attempt-evidence"
        result = br.archive_and_reset_worktree(
            path, evidence, reset_sha=base_sha
        )

        assert result["state"] == "archived_and_reset"
        assert br.worktree_head(path) == base_sha
        assert not (path / "committed.txt").exists()
        assert "committed.txt" in (evidence / "crashed-worktree.patch").read_text()
        assert subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=path,
            capture_output=True,
            text=True,
            check=True,
        ).stdout == ""

    def test_remove_clean_worktree(self, repo: Path):
        path = br.ensure_worktree("kb_t5_aaaa", "kittybuilder/kb_t5_aaaa", repo_root=repo)
        removed = br.remove_worktree("kb_t5_aaaa", repo_root=repo)
        assert removed == path
        assert not path.exists()

    def test_remove_allows_only_ephemeral_done_marker(self, repo: Path):
        path = br.ensure_worktree("kb_t5_done", "kittybuilder/kb_t5_done", repo_root=repo)
        (path / "done.txt").write_text("ok\n")

        removed = br.remove_worktree(
            "kb_t5_done", repo_root=repo, discard_done_marker=True
        )

        assert removed == path
        assert not path.exists()

    def test_remove_refuses_dirty(self, repo: Path):
        path = br.ensure_worktree("kb_t6_aaaa", "kittybuilder/kb_t6_aaaa", repo_root=repo)
        (path / "junk.txt").write_text("keep me")
        with pytest.raises(br.RunnerError, match="dirty"):
            br.remove_worktree("kb_t6_aaaa", repo_root=repo)
        assert path.exists()

    def test_remove_missing_worktree(self, repo: Path):
        with pytest.raises(br.RunnerError, match="no worktree"):
            br.remove_worktree("kb_missing_0000", repo_root=repo)


# ---------------------------------------------------------------------------
# run_worker end-to-end
# ---------------------------------------------------------------------------


class TestRunWorker:
    @pytest.mark.parametrize(
        ("kwargs", "message"),
        [
            ({"timeout_seconds": 0}, "timeout_seconds must be positive"),
            ({"lease_seconds": 0}, "lease_seconds must be positive"),
            ({"heartbeat_seconds": 0}, "heartbeat_seconds must be positive"),
            (
                {"lease_seconds": 5, "heartbeat_seconds": 5},
                "heartbeat_seconds must be shorter than lease_seconds",
            ),
        ],
    )
    def test_invalid_timing_is_rejected_before_claim(
        self,
        repo: Path,
        db_path: Path,
        kwargs: dict,
        message: str,
    ):
        task = _queued_task(db_path)

        with pytest.raises(ValueError, match=message):
            br.run_worker(
                task["id"],
                ["true"],
                repo_root=repo,
                db_path=db_path,
                **kwargs,
            )

        refreshed = bq.get_task(task["id"], db_path=db_path)
        assert refreshed is not None
        assert refreshed["state"] == bq.QUEUED
        assert bq.list_runs(task_id=task["id"], db_path=db_path) == []

    def test_worker_uses_repo_validation_venv_python(self, repo: Path, db_path: Path):
        venv_bin = repo / "venv" / "bin"
        venv_bin.mkdir(parents=True)
        python = venv_bin / "python"
        python.write_text("#!/bin/sh\necho repo-validation-python\n")
        python.chmod(0o755)

        task = _queued_task(db_path)
        run = br.run_worker(
            task["id"],
            ["sh", "-c", "python --version"],
            worker="test-worker",
            timeout_seconds=30,
            heartbeat_seconds=1,
            repo_root=repo,
            db_path=db_path,
        )

        assert run["state"] == bq.RUN_EXITED
        log = Path(run["log_path"]).read_text()
        assert "repo-validation-python" in log

    def test_successful_run_blocks_task_with_report(self, repo: Path, db_path: Path):
        task = _queued_task(db_path)
        run = br.run_worker(
            task["id"],
            ["sh", "-c", "echo did work; echo done > result.txt"],
            worker="test-worker",
            model="test-model",
            timeout_seconds=30,
            heartbeat_seconds=1,
            repo_root=repo,
            db_path=db_path,
        )
        assert run["state"] == bq.RUN_EXITED
        assert run["exit_code"] == 0
        assert run["pid"]
        assert run["final_report"]["outcome"] == bq.RUN_EXITED

        refreshed = bq.get_task(task["id"], db_path=db_path)
        assert refreshed["state"] == "blocked"
        assert refreshed["blocked_reason"] == "shadow_run_complete"
        report = json.loads(refreshed["final_report_json"])
        assert report["outcome"] == bq.RUN_EXITED
        assert report["run_id"] == run["id"]
        assert len(report["diff_sha256"]) == 64
        # Partial progress discoverable: worktree + log survive.
        assert Path(run["worktree_path"]).exists()
        assert (Path(run["worktree_path"]) / "result.txt").exists()
        assert "did work" in Path(run["log_path"]).read_text()
        # Runner control artifacts stay outside the git worktree.
        assert (Path(run["log_path"]).parent / "brief.md").exists()

        events = bq.list_events(task["id"], db_path=db_path)
        run_events = [e for e in events if e["type"].startswith("run_")]
        assert "run_started" in [event["type"] for event in run_events]
        assert "run_exited" in [event["type"] for event in run_events]
        assert all(event["run_id"] == run["id"] for event in run_events)


    def test_dsh_run_self_publishes_presence_lifecycle(self, repo: Path, db_path: Path, monkeypatch):
        task = _queued_task(db_path)
        calls: list[tuple[str, str]] = []

        def check_in(**kwargs):
            calls.append(("checkin", kwargs["session_id"]))
            return kwargs

        def heartbeat(session_id, participant_id):
            calls.append(("heartbeat", session_id))
            assert participant_id == "dsh"
            return {"session_id": session_id}

        def checkout(session_id, participant_id):
            calls.append(("checkout", session_id))
            assert participant_id == "dsh"
            return {"session_id": session_id}

        monkeypatch.setattr(br.agent_workspace, "check_in", check_in)
        monkeypatch.setattr(br.agent_workspace, "heartbeat", heartbeat)
        monkeypatch.setattr(br.agent_workspace, "checkout", checkout)

        run = br.run_worker(
            task["id"],
            ["sh", "-c", "sleep 0.25"],
            worker="dsh-free",
            model="openrouter/free",
            timeout_seconds=10,
            lease_seconds=2,
            heartbeat_seconds=0.05,
            repo_root=repo,
            db_path=db_path,
        )

        session_id = f"builder-{run['id']}"
        assert calls[0] == ("checkin", session_id)
        assert any(kind == "heartbeat" for kind, _ in calls)
        assert calls[-1] == ("checkout", session_id)
        assert run["final_report"]["presence_issues"] == []

    def test_dsh_presence_failure_never_becomes_execution_authority(self, repo: Path, db_path: Path, monkeypatch):
        task = _queued_task(db_path)
        monkeypatch.setattr(
            br.agent_workspace,
            "check_in",
            lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("room unavailable")),
        )

        run = br.run_worker(
            task["id"],
            ["true"],
            worker="dsh-free",
            timeout_seconds=10,
            heartbeat_seconds=1,
            repo_root=repo,
            db_path=db_path,
        )

        assert run["state"] == bq.RUN_EXITED
        assert run["final_report"]["presence_issues"]
        assert run["final_report"]["presence_issues"][0].startswith("checkin:RuntimeError")

    def test_failed_run_blocks_with_worker_failed(self, repo: Path, db_path: Path):
        task = _queued_task(db_path)
        run = br.run_worker(
            task["id"],
            ["sh", "-c", "echo boom >&2; exit 3"],
            timeout_seconds=30,
            heartbeat_seconds=1,
            repo_root=repo,
            db_path=db_path,
        )
        assert run["state"] == bq.RUN_FAILED
        assert run["exit_code"] == 3
        refreshed = bq.get_task(task["id"], db_path=db_path)
        assert refreshed["state"] == "blocked"
        events = bq.list_events(task["id"], db_path=db_path)
        blocked = [e for e in events if e["type"] == "blocked"][-1]
        assert blocked["payload"]["reason"] == "worker_failed"

    def test_out_of_scope_change_is_recorded_as_scope_violation(
        self, repo: Path, db_path: Path
    ):
        task = _queued_task(db_path, allowed_paths=["gateway/"])

        run = br.run_worker(
            task["id"],
            ["sh", "-c", "echo nope > outside.txt"],
            timeout_seconds=30,
            heartbeat_seconds=1,
            repo_root=repo,
            db_path=db_path,
        )

        assert run["state"] == bq.RUN_SCOPE_VIOLATION
        assert run["final_report"]["scope_violations"] == ["outside.txt"]
        refreshed = bq.get_task(task["id"], db_path=db_path)
        assert refreshed is not None
        assert refreshed["state"] == bq.BLOCKED
        assert refreshed["blocked_reason"] == "scope_violation"

    def test_in_flight_scope_breach_is_stopped_during_execution(
        self, repo: Path, db_path: Path
    ):
        """A long-running worker that breaches scope is killed at the next
        heartbeat, not left running until it exits or times out."""
        task = _queued_task(db_path, allowed_paths=["gateway/"])
        start = time.monotonic()

        run = br.run_worker(
            task["id"],
            ["sh", "-c", "echo nope > outside.txt; sleep 60"],
            timeout_seconds=120,
            heartbeat_seconds=0.1,
            repo_root=repo,
            db_path=db_path,
        )

        elapsed = time.monotonic() - start
        assert elapsed < 5
        assert run["state"] == bq.RUN_SCOPE_VIOLATION
        assert run["final_report"]["scope_violations"] == ["outside.txt"]
        refreshed = bq.get_task(task["id"], db_path=db_path)
        assert refreshed is not None
        assert refreshed["blocked_reason"] == "scope_violation"

    def test_session_state_residue_is_not_a_scope_violation(
        self, repo: Path, db_path: Path
    ):
        task = _queued_task(db_path, allowed_paths=["gateway/"])
        command = [
            "sh",
            "-c",
            "mkdir -p gateway .claude && echo ok > gateway/ok.py && "
            "echo residue > .claude/STATE.md",
        ]

        run = br.run_worker(
            task["id"],
            command,
            timeout_seconds=30,
            heartbeat_seconds=1,
            repo_root=repo,
            db_path=db_path,
        )

        assert run["state"] == bq.RUN_EXITED
        assert ".claude/STATE.md" in run["final_report"]["changed_paths"]
        assert run["final_report"]["scope_violations"] == []

    def test_worker_staging_residue_is_not_a_scope_violation(
        self, repo: Path, db_path: Path
    ):
        """CP-08 dogfood finding: the --free worker adapter stages
        .kittybuilder-{bundle,context,result}-<attempt>.json at the worktree
        root so the model can read them; the live heartbeat scope check must
        not treat the runner's own staging files as a violation."""
        task = _queued_task(db_path, allowed_paths=["gateway/"])
        command = [
            "sh",
            "-c",
            "mkdir -p gateway && echo ok > gateway/ok.py && "
            "echo staged > .kittybuilder-bundle-1.json && "
            "echo staged > .kittybuilder-context-1.json && "
            "echo staged > .kittybuilder-result-1.json",
        ]

        run = br.run_worker(
            task["id"],
            command,
            timeout_seconds=30,
            heartbeat_seconds=1,
            repo_root=repo,
            db_path=db_path,
        )

        assert run["state"] == bq.RUN_EXITED
        assert run["final_report"]["scope_violations"] == []
        assert ".kittybuilder-bundle-1.json" in run["final_report"]["changed_paths"]

    def test_opencode_continuation_residue_is_not_a_scope_violation(
        self, repo: Path, db_path: Path
    ):
        """OpenCode writes this run-continuation receipt outside packet scope."""
        task = _queued_task(db_path, allowed_paths=["gateway/"])
        command = [
            "sh",
            "-c",
            "mkdir -p gateway .omo/run-continuation && "
            "echo ok > gateway/ok.py && "
            "echo continuation > .omo/run-continuation/session.json",
        ]

        run = br.run_worker(
            task["id"],
            command,
            timeout_seconds=30,
            heartbeat_seconds=1,
            repo_root=repo,
            db_path=db_path,
        )

        assert run["state"] == bq.RUN_EXITED
        assert ".omo/run-continuation/session.json" in run["final_report"]["changed_paths"]
        assert run["final_report"]["scope_violations"] == []

    def test_worker_staging_residue_does_not_mask_a_real_violation(
        self, repo: Path, db_path: Path
    ):
        task = _queued_task(db_path, allowed_paths=["gateway/"])
        command = [
            "sh",
            "-c",
            "echo staged > .kittybuilder-bundle-1.json && echo nope > outside.txt",
        ]

        run = br.run_worker(
            task["id"],
            command,
            timeout_seconds=30,
            heartbeat_seconds=1,
            repo_root=repo,
            db_path=db_path,
        )

        assert run["state"] == bq.RUN_SCOPE_VIOLATION
        assert run["final_report"]["scope_violations"] == ["outside.txt"]

    @pytest.mark.skipif(__import__("sys").platform != "darwin", reason="Seatbelt proof is macOS-specific")
    def test_worker_cannot_commit_shared_git_metadata(
        self, repo: Path, db_path: Path
    ):
        task = _queued_task(db_path, allowed_paths=["gateway/"])
        run = br.run_worker(
            task["id"],
            [
                "sh",
                "-c",
                "mkdir -p gateway && echo ok > gateway/ok.py && "
                "git add gateway/ok.py && "
                "git -c user.email=test@example.com -c user.name=test "
                "commit -q -m worker-change",
            ],
            timeout_seconds=30,
            heartbeat_seconds=1,
            repo_root=repo,
            db_path=db_path,
        )

        assert run["state"] == bq.RUN_FAILED
        assert run["final_report"]["changed_paths"] == ["gateway/ok.py"]
        assert run["final_report"]["scope_violations"] == []
        log = Path(run["final_report"]["log_path"]).read_text()
        assert "Operation not permitted" in log

    def test_scope_check_rejects_prefix_confusion(
        self, repo: Path, db_path: Path
    ):
        # An allowlist entry of gateway/foo.py must NOT match
        # gateway/foo.py.backup — the matcher must use a path boundary, not a
        # bare string prefix, so the backup file is recorded as out of scope.
        task = _queued_task(db_path, allowed_paths=["gateway/foo.py"])

        run = br.run_worker(
            task["id"],
            [
                "sh",
                "-c",
                "mkdir -p gateway && echo ok > gateway/foo.py.backup",
            ],
            timeout_seconds=30,
            heartbeat_seconds=1,
            repo_root=repo,
            db_path=db_path,
        )

        assert run["state"] == bq.RUN_SCOPE_VIOLATION
        assert run["final_report"]["scope_violations"] == [
            "gateway/foo.py.backup"
        ]

    def test_scope_rejects_absolute_paths(self, repo: Path, db_path: Path):
        """allowed_paths containing an absolute path must raise RunnerError."""
        task = _queued_task(db_path, allowed_paths=["/etc/passwd"])
        with pytest.raises(br.RunnerError, match="invalid allowed path"):
            br.run_worker(
                task["id"], ["true"],
                timeout_seconds=10, heartbeat_seconds=1,
                repo_root=repo, db_path=db_path,
            )

    def test_scope_rejects_dotdot_paths(self, repo: Path, db_path: Path):
        """allowed_paths containing '..' must raise RunnerError."""
        task = _queued_task(db_path, allowed_paths=["../outside"])
        with pytest.raises(br.RunnerError, match="invalid allowed path"):
            br.run_worker(
                task["id"], ["true"],
                timeout_seconds=10, heartbeat_seconds=1,
                repo_root=repo, db_path=db_path,
            )

    def test_scope_dot_grant_allows_whole_repo(self, repo: Path, db_path: Path):
        """allowed_paths=['.'] grants access to the entire repository."""
        task = _queued_task(db_path, allowed_paths=["."])
        run = br.run_worker(
            task["id"],
            ["sh", "-c", "echo ok > anywhere.txt"],
            timeout_seconds=10, heartbeat_seconds=1,
            repo_root=repo, db_path=db_path,
        )
        assert run["state"] == bq.RUN_EXITED
        assert run["final_report"]["scope_violations"] == []

    def test_blocked_reason_on_timeout(self, repo: Path, db_path: Path):
        task = _queued_task(db_path)
        run = br.run_worker(
            task["id"], ["sleep", "60"],
            timeout_seconds=0.25, heartbeat_seconds=0.05,
            repo_root=repo, db_path=db_path,
        )
        assert run["state"] == bq.RUN_TIMEOUT
        refreshed = bq.get_task(task["id"], db_path=db_path)
        assert refreshed["state"] == "blocked"
        assert refreshed["blocked_reason"] == "run_timeout"

    def test_blocked_reason_on_monitoring_failure(self, repo: Path, db_path: Path, monkeypatch):
        task = _queued_task(db_path)
        real_get_run = bq.get_run

        def fail_after_activation(run_id: str, db_path: Path | None = None):
            run = real_get_run(run_id, db_path=db_path)
            if run is not None and run["state"] == bq.RUN_RUNNING:
                raise RuntimeError("queue read failed")
            return run

        monkeypatch.setattr(bq, "get_run", fail_after_activation)

        with pytest.raises(br.RunnerError, match="monitoring failed"):
            br.run_worker(
                task["id"], ["sleep", "2"],
                timeout_seconds=30, lease_seconds=5, heartbeat_seconds=0.1,
                repo_root=repo, db_path=db_path,
            )

        run = bq.list_runs(task_id=task["id"], db_path=db_path)[0]
        assert run["state"] == bq.RUN_FAILED
        refreshed = bq.get_task(task["id"], db_path=db_path)
        assert refreshed["state"] == "blocked"
        assert refreshed["blocked_reason"] == "runner_control_failed"

    def test_blocked_reason_on_scope_violation(self, repo: Path, db_path: Path):
        task = _queued_task(db_path, allowed_paths=["allowed/"])
        run = br.run_worker(
            task["id"],
            ["sh", "-c", "mkdir -p outside && echo nope > outside/secret.txt"],
            timeout_seconds=10, heartbeat_seconds=1,
            repo_root=repo, db_path=db_path,
        )
        assert run["state"] == bq.RUN_SCOPE_VIOLATION
        refreshed = bq.get_task(task["id"], db_path=db_path)
        assert refreshed["state"] == "blocked"
        assert refreshed["blocked_reason"] == "scope_violation"

    def test_post_loop_lease_renewal_failure_is_captured(
        self, repo: Path, db_path: Path, monkeypatch
    ):
        task = _queued_task(db_path)
        call_count = [0]
        real_renew = bq.renew_lease

        def fail_renew(task_id, lease_token, claim_version, *,
                        lease_seconds=300, db_path=None):
            call_count[0] += 1
            # With a command that exits immediately and a long heartbeat
            # interval, call 1 is the prelaunch freshening and call 2 is the
            # post-process fence this test is specifically exercising.
            if call_count[0] == 2:
                raise RuntimeError("post-loop renewal failure")
            return real_renew(
                task_id, lease_token, claim_version,
                lease_seconds=lease_seconds, db_path=db_path,
            )

        monkeypatch.setattr(bq, "renew_lease", fail_renew)

        with pytest.raises(br.RunnerError, match="monitoring failed"):
            br.run_worker(
                task["id"], ["true"],
                timeout_seconds=30, lease_seconds=30, heartbeat_seconds=10,
                repo_root=repo, db_path=db_path,
            )

        run = bq.list_runs(task_id=task["id"], db_path=db_path)[0]
        assert run["state"] == bq.RUN_FAILED
        assert "RuntimeError" in run["final_report"].get("error", "")
        refreshed = bq.get_task(task["id"], db_path=db_path)
        assert refreshed["state"] == "blocked"
        assert refreshed["blocked_reason"] == "runner_control_failed"

    def test_control_error_preserved_when_start_sha_missing(
        self, repo: Path, db_path: Path, monkeypatch
    ):
        """A missing start_sha must never overwrite an existing control_error."""
        task = _queued_task(db_path)

        # Inject a control_error during the heartbeat loop.
        real_get_run = bq.get_run

        def fail_heartbeat(run_id: str, db_path: Path | None = None):
            run = real_get_run(run_id, db_path=db_path)
            if run is not None and run["state"] == bq.RUN_RUNNING:
                raise RuntimeError("original heartbeat error")
            return run

        monkeypatch.setattr(bq, "get_run", fail_heartbeat)

        # Also make the run's start_sha appear empty by returning "" from .get()
        orig_create_run = bq.create_run

        def create_run_no_sha(*args, **kwargs):
            run = orig_create_run(*args, **kwargs)
            del run["start_sha"]
            run["start_sha"] = ""
            return run

        monkeypatch.setattr(bq, "create_run", create_run_no_sha)

        with pytest.raises(br.RunnerError, match="monitoring failed"):
            br.run_worker(
                task["id"], ["sleep", "2"],
                timeout_seconds=30, lease_seconds=5, heartbeat_seconds=0.1,
                repo_root=repo, db_path=db_path,
            )

        run = bq.list_runs(task_id=task["id"], db_path=db_path)[0]
        # The heartbeat error is preserved — "no recorded start SHA" is
        # NOT present because the guard (control_error is None) suppressed it.
        error_msg = run["final_report"].get("error", "")
        assert "original heartbeat error" in error_msg
        assert "no recorded start SHA" not in error_msg
        refreshed = bq.get_task(task["id"], db_path=db_path)
        assert refreshed is not None
        assert refreshed["state"] == "blocked"
        assert refreshed["blocked_reason"] == "runner_control_failed"

    def test_timeout_terminates_and_blocks(self, repo: Path, db_path: Path):
        task = _queued_task(db_path)
        start = time.monotonic()
        run = br.run_worker(
            task["id"],
            ["sleep", "60"],
            timeout_seconds=0.25,
            heartbeat_seconds=0.05,
            repo_root=repo,
            db_path=db_path,
        )
        elapsed = time.monotonic() - start
        assert run["state"] == bq.RUN_TIMEOUT
        assert elapsed < 30
        refreshed = bq.get_task(task["id"], db_path=db_path)
        assert refreshed["state"] == "blocked"
        events = bq.list_events(task["id"], db_path=db_path)
        blocked = [e for e in events if e["type"] == "blocked"][-1]
        assert blocked["payload"]["reason"] == "run_timeout"

    def test_worker_env_has_task_context(self, repo: Path, db_path: Path):
        task = _queued_task(db_path)
        run = br.run_worker(
            task["id"],
            ["sh", "-c", "echo task=$KB_TASK_ID brief=$KB_BRIEF_PATH; test -f \"$KB_BRIEF_PATH\""],
            timeout_seconds=30,
            heartbeat_seconds=1,
            repo_root=repo,
            db_path=db_path,
        )
        assert run["state"] == bq.RUN_EXITED
        log = Path(run["log_path"]).read_text()
        assert f"task={task['id']}" in log

    def test_github_tokens_stripped_from_worker_env(
        self, repo: Path, db_path: Path, monkeypatch
    ):
        monkeypatch.setenv("GITHUB_TOKEN", "leak-me")
        monkeypatch.setenv("GH_TOKEN", "leak-me-too")
        task = _queued_task(db_path)
        run = br.run_worker(
            task["id"],
            [
                "sh",
                "-c",
                """
                echo "gh=[${GITHUB_TOKEN:-unset}] ght=[${GH_TOKEN:-unset}]"
                echo "gh_config=$GH_CONFIG_DIR"
                echo "git_global=$GIT_CONFIG_GLOBAL git_system=$GIT_CONFIG_SYSTEM"
                echo "git_interactive=$(git config --get credential.interactive)"
                """,
            ],
            timeout_seconds=30,
            heartbeat_seconds=1,
            repo_root=repo,
            db_path=db_path,
        )
        log = Path(run["log_path"]).read_text()
        assert "gh=[unset]" in log
        assert "ght=[unset]" in log
        assert f"gh_config={Path(run['log_path']).parent / 'gh-config'}" in log
        assert f"git_global={Path('/dev/null')} git_system={Path('/dev/null')}" in log
        assert "git_interactive=never" in log

    def test_ssh_credentials_stripped_from_worker_env(
        self, repo: Path, db_path: Path, monkeypatch
    ):
        monkeypatch.setenv("SSH_AUTH_SOCK", "/tmp/fake-agent.sock")
        monkeypatch.setenv("SSH_AGENT_PID", "99999")
        monkeypatch.setenv("GIT_SSH_COMMAND", "ssh -i /secret/key")
        monkeypatch.setenv("GIT_SSH", "ssh -i /another/secret")
        task = _queued_task(db_path)
        run = br.run_worker(
            task["id"],
            [
                "sh",
                "-c",
                """
                echo "ssh_sock=[${SSH_AUTH_SOCK:-unset}]"
                echo "ssh_pid=[${SSH_AGENT_PID:-unset}]"
                echo "git_ssh_cmd=[${GIT_SSH_COMMAND:-unset}]"
                echo "git_ssh=[${GIT_SSH:-unset}]"
                echo "credential_helper=$(git config --get credential.helper 2>&1 || true)"
                """,
            ],
            timeout_seconds=30,
            heartbeat_seconds=1,
            repo_root=repo,
            db_path=db_path,
        )
        log = Path(run["log_path"]).read_text()
        assert "ssh_sock=[unset]" in log
        assert "ssh_pid=[unset]" in log
        assert "git_ssh_cmd=[unset]" in log
        assert "git_ssh=[unset]" in log
        # Empty credential.helper output (the "" value from GIT_CONFIG_COUNT
        # overrides) means no helper is configured.
        assert "credential_helper=" in log

    def test_claim_conflict_raises(self, repo: Path, db_path: Path):
        task = _queued_task(db_path)
        bq.claim_task(task["id"], "someone-else", db_path=db_path)
        with pytest.raises(bq.LeaseConflictError):
            br.run_worker(
                task["id"], ["true"], repo_root=repo, db_path=db_path
            )

    def test_worker_launch_failure_is_durable_and_explicit(
        self, repo: Path, db_path: Path
    ):
        task = _queued_task(db_path)

        with pytest.raises(br.RunnerError, match="worker launch failed"):
            br.run_worker(
                task["id"],
                ["/definitely/not/a/real/worker"],
                repo_root=repo,
                db_path=db_path,
            )

        run = bq.list_runs(task_id=task["id"], db_path=db_path)[0]
        assert run["state"] == bq.RUN_FAILED
        assert "No such file" in run["final_report"]["error"]
        refreshed = bq.get_task(task["id"], db_path=db_path)
        assert refreshed is not None
        assert refreshed["state"] == bq.BLOCKED
        assert refreshed["blocked_reason"] == "worker_launch_failed"

    def test_prelaunch_setup_failure_releases_claim_and_closes_run(
        self, repo: Path, db_path: Path, monkeypatch
    ):
        task = _queued_task(db_path)

        def fail_brief(*_args, **_kwargs):
            raise RuntimeError("brief renderer exploded")

        monkeypatch.setattr(br, "render_worker_brief", fail_brief)

        with pytest.raises(br.RunnerError, match="prelaunch setup failed"):
            br.run_worker(task["id"], ["true"], repo_root=repo, db_path=db_path)

        run = bq.list_runs(task_id=task["id"], db_path=db_path)[0]
        assert run["state"] == bq.RUN_FAILED
        assert "brief renderer exploded" in run["final_report"]["error"]
        refreshed = bq.get_task(task["id"], db_path=db_path)
        assert refreshed is not None
        assert refreshed["state"] == bq.QUEUED
        assert refreshed["lease_token"] is None

    def test_worktree_failure_releases_claim(self, repo: Path, db_path: Path):
        task = _queued_task(db_path)
        # Pre-dirty the worktree so ensure_worktree refuses.
        branch = f"kittybuilder/{task['id']}"
        path = br.ensure_worktree(task["id"], branch, repo_root=repo)
        (path / "junk.txt").write_text("dirty")
        with pytest.raises(br.RunnerError):
            br.run_worker(task["id"], ["true"], repo_root=repo, db_path=db_path)
        refreshed = bq.get_task(task["id"], db_path=db_path)
        assert refreshed["state"] == "queued"

    def test_task_repo_mismatch_releases_claim(self, repo: Path, db_path: Path):
        task = _queued_task(db_path, repo_path=str(repo.parent / "other-repo"))

        with pytest.raises(br.RunnerError, match="targets repo"):
            br.run_worker(task["id"], ["true"], repo_root=repo, db_path=db_path)

        refreshed = bq.get_task(task["id"], db_path=db_path)
        assert refreshed is not None
        assert refreshed["state"] == bq.QUEUED
        assert bq.list_runs(task_id=task["id"], db_path=db_path) == []

    def test_prelaunch_setup_heartbeats_lease_before_worker_start(
        self, repo: Path, db_path: Path, monkeypatch
    ):
        task = _queued_task(db_path)
        real_ensure = br.ensure_worktree

        def slow_ensure(*args, **kwargs):
            path = real_ensure(*args, **kwargs)
            time.sleep(1.2)
            return path

        monkeypatch.setattr(br, "ensure_worktree", slow_ensure)
        run = br.run_worker(
            task["id"],
            ["true"],
            timeout_seconds=30,
            lease_seconds=1,
            heartbeat_seconds=0.1,
            repo_root=repo,
            db_path=db_path,
        )

        assert run["state"] == bq.RUN_EXITED
        assert run["last_heartbeat_at"] is not None

    def test_heartbeat_renews_lease_during_run(self, repo: Path, db_path: Path):
        task = _queued_task(db_path)
        run = br.run_worker(
            task["id"],
            ["sleep", "2.5"],
            timeout_seconds=30,
            lease_seconds=2,  # would expire mid-run without heartbeat
            heartbeat_seconds=0.2,
            repo_root=repo,
            db_path=db_path,
        )
        # Lease survived (run completed and could still record its outcome).
        assert run["state"] == bq.RUN_EXITED
        assert run["last_heartbeat_at"] is not None
        refreshed = bq.get_task(task["id"], db_path=db_path)
        assert refreshed["state"] == "blocked"

    def test_monitoring_failure_terminates_worker_and_is_durable(
        self, repo: Path, db_path: Path, monkeypatch
    ):
        task = _queued_task(db_path)
        real_get_run = bq.get_run

        def fail_after_activation(run_id: str, db_path: Path | None = None):
            run = real_get_run(run_id, db_path=db_path)
            if run is not None and run["state"] == bq.RUN_RUNNING:
                raise RuntimeError("queue read failed during heartbeat")
            return run

        monkeypatch.setattr(bq, "get_run", fail_after_activation)

        with pytest.raises(br.RunnerError, match="monitoring failed"):
            br.run_worker(
                task["id"],
                ["sleep", "2"],
                timeout_seconds=30,
                lease_seconds=5,
                heartbeat_seconds=0.1,
                repo_root=repo,
                db_path=db_path,
            )

        run = bq.list_runs(task_id=task["id"], db_path=db_path)[0]
        assert run["state"] == bq.RUN_FAILED
        assert "queue read failed" in run["final_report"]["error"]
        assert run["exit_code"] is not None
        refreshed = bq.get_task(task["id"], db_path=db_path)
        assert refreshed is not None
        assert refreshed["state"] == bq.BLOCKED

    def test_noop_run_leaves_worktree_clean_and_removable(
        self, repo: Path, db_path: Path
    ):
        task = _queued_task(db_path)
        run = br.run_worker(
            task["id"],
            ["true"],
            timeout_seconds=30,
            heartbeat_seconds=1,
            repo_root=repo,
            db_path=db_path,
        )

        worktree = Path(run["worktree_path"])
        status = subprocess.run(
            ["git", "status", "--porcelain=v1", "--untracked-files=all"],
            cwd=worktree,
            capture_output=True,
            text=True,
            check=True,
        )
        assert status.stdout == ""
        assert not (worktree / ".kittybuilder" / "brief.md").exists()

        removed = br.remove_worktree(task["id"], repo_root=repo)
        assert removed == worktree
        assert not worktree.exists()


# ---------------------------------------------------------------------------
# Cancellation
# ---------------------------------------------------------------------------


class TestRequestCancel:
    def test_cancel_requested_while_starting_is_not_overwritten(
        self, repo: Path, db_path: Path, monkeypatch
    ):
        import threading

        task = _queued_task(db_path)
        entered_popen = threading.Event()
        allow_popen = threading.Event()
        real_popen = subprocess.Popen
        result: dict = {}

        def delayed_popen(*args, **kwargs):
            if kwargs.get("start_new_session"):
                entered_popen.set()
                assert allow_popen.wait(timeout=10)
            return real_popen(*args, **kwargs)

        monkeypatch.setattr(br.subprocess, "Popen", delayed_popen)

        def _run():
            try:
                result["run"] = br.run_worker(
                    task["id"],
                    ["sleep", "2"],
                    timeout_seconds=30,
                    heartbeat_seconds=1,
                    repo_root=repo,
                    db_path=db_path,
                )
            except Exception as exc:  # assertion below requires no hidden failure
                result["error"] = exc

        thread = threading.Thread(target=_run)
        thread.start()
        assert entered_popen.wait(timeout=10)

        run = bq.list_runs(task_id=task["id"], db_path=db_path)[0]
        assert run["state"] == bq.RUN_STARTING
        cancelled = br.request_cancel(run["id"], db_path=db_path)
        assert cancelled["state"] == bq.RUN_CANCEL_REQUESTED

        allow_popen.set()
        thread.join(timeout=20)
        assert not thread.is_alive()
        assert "error" not in result
        assert result["run"]["state"] == bq.RUN_CANCELLED

    def test_cancel_flag_and_dead_process_detected(self, repo: Path, db_path: Path):
        import threading

        task = _queued_task(db_path)
        result: dict = {}

        def _run():
            result["run"] = br.run_worker(
                task["id"],
                ["sleep", "60"],
                timeout_seconds=120,
                heartbeat_seconds=1,
                repo_root=repo,
                db_path=db_path,
            )

        t = threading.Thread(target=_run)
        t.start()
        # Wait for the run row to go live.
        run_row = None
        for _ in range(100):
            runs = bq.list_runs(task_id=task["id"], db_path=db_path)
            if runs and runs[0]["state"] == bq.RUN_RUNNING and runs[0]["pid"]:
                run_row = runs[0]
                break
            time.sleep(0.1)
        assert run_row is not None, "run never reached running state"

        br.request_cancel(run_row["id"], db_path=db_path)
        t.join(timeout=30)
        assert not t.is_alive()
        assert result["run"]["state"] == bq.RUN_CANCELLED
        refreshed = bq.get_task(task["id"], db_path=db_path)
        assert refreshed["state"] == "blocked"
        events = bq.list_events(task["id"], db_path=db_path)
        blocked = [e for e in events if e["type"] == "blocked"][-1]
        assert blocked["payload"]["reason"] == "run_cancelled"

    def test_lease_loss_has_priority_over_concurrent_cancel(
        self, repo: Path, db_path: Path
    ):
        import threading

        task = _queued_task(db_path)
        result: dict = {}

        def _run():
            result["run"] = br.run_worker(
                task["id"],
                ["sleep", "60"],
                timeout_seconds=120,
                heartbeat_seconds=5,
                repo_root=repo,
                db_path=db_path,
            )

        thread = threading.Thread(target=_run)
        thread.start()
        run_row = None
        for _ in range(100):
            runs = bq.list_runs(task_id=task["id"], db_path=db_path)
            if runs and runs[0]["state"] == bq.RUN_RUNNING and runs[0]["pid"]:
                run_row = runs[0]
                break
            time.sleep(0.1)
        assert run_row is not None, "run never reached running state"

        # Deterministically simulate an operator takeover before cancellation.
        with bq.connect(db_path) as conn:
            conn.execute(
                """
                UPDATE tasks
                SET lease_token = 'replacement-token',
                    claim_version = claim_version + 1,
                    lease_expires_at = strftime('%Y-%m-%d %H:%M:%f', 'now', '+60 seconds')
                WHERE id = ?
                """,
                (task["id"],),
            )
            conn.commit()

        br.request_cancel(run_row["id"], db_path=db_path)
        thread.join(timeout=30)
        assert not thread.is_alive()
        assert result["run"]["state"] == bq.RUN_LEASE_LOST
        events = bq.list_events(task["id"], db_path=db_path)
        assert any(event["type"] == "run_lease_lost" for event in events)

    def test_cancel_inactive_run_rejected(self, db_path: Path):
        task = _queued_task(db_path)
        claimed = bq.claim_task(task["id"], "runner", db_path=db_path)
        run = bq.create_run(
            task["id"],
            ["true"],
            lease_token=claimed["lease_token"],
            claim_version=claimed["claim_version"],
            db_path=db_path,
        )
        bq.update_run(run["id"], state=bq.RUN_EXITED, db_path=db_path)
        with pytest.raises(ValueError, match="not active"):
            br.request_cancel(run["id"], db_path=db_path)

    def test_cancel_allows_same_pid_after_exec_changes_command(
        self, db_path: Path, monkeypatch
    ):
        import os

        task = _queued_task(db_path)
        claimed = bq.claim_task(task["id"], "runner", db_path=db_path)
        run = bq.create_run(
            task["id"],
            ["sleep", "60"],
            lease_token=claimed["lease_token"],
            claim_version=claimed["claim_version"],
            db_path=db_path,
        )
        started = "Mon Aug 31 17:43:26 2026"
        bq.update_run(
            run["id"],
            state=bq.RUN_RUNNING,
            pid=os.getpid(),
            process_identity=f"{started} /usr/bin/sandbox-exec -p profile bash worker.sh",
            db_path=db_path,
        )
        monkeypatch.setattr(
            bq,
            "capture_process_identity",
            lambda _pid: f"{started} bash worker.sh",
        )
        signals: list[tuple[int, int]] = []
        monkeypatch.setattr(
            br.os, "killpg", lambda pid, sig: signals.append((pid, sig))
        )

        cancelled = br.request_cancel(run["id"], db_path=db_path)

        assert cancelled["state"] == bq.RUN_CANCEL_REQUESTED
        assert cancelled["signal_sent"] is True
        assert cancelled["signal_status"] == "signal_sent"
        assert len(signals) == 1
        assert signals[0][0] == os.getpid()

    def test_cancel_refuses_to_signal_reused_pid(
        self, db_path: Path, monkeypatch
    ):
        import os

        task = _queued_task(db_path)
        claimed = bq.claim_task(task["id"], "runner", db_path=db_path)
        run = bq.create_run(
            task["id"],
            ["sleep", "60"],
            lease_token=claimed["lease_token"],
            claim_version=claimed["claim_version"],
            db_path=db_path,
        )
        bq.update_run(
            run["id"],
            state=bq.RUN_RUNNING,
            pid=os.getpid(),
            process_identity="a different process started here",
            db_path=db_path,
        )
        signals: list[tuple[int, int]] = []
        monkeypatch.setattr(
            br.os, "killpg", lambda pid, sig: signals.append((pid, sig))
        )

        cancelled = br.request_cancel(run["id"], db_path=db_path)

        assert cancelled["state"] == bq.RUN_CANCEL_REQUESTED
        assert cancelled["signal_sent"] is False
        assert cancelled["signal_status"] == "process_identity_mismatch"
        assert signals == []

    def test_cancel_unknown_run(self, db_path: Path):
        with pytest.raises(bq.RunNotFoundError):
            br.request_cancel("run_nope_0000", db_path=db_path)


# ---------------------------------------------------------------------------
# Durable detached execution (B7-detached-execution-durable)
# ---------------------------------------------------------------------------


class TestDetachedExecution:
    def _wait_status(self, task_id, db_path, want, timeout=25.0):
        start = time.monotonic()
        while time.monotonic() - start < timeout:
            status = br.detached_worker_status(task_id=task_id, db_path=db_path)
            if status["status"] == want:
                return status
            time.sleep(0.2)
        raise AssertionError(
            f"status never became {want!r}; last={br.detached_worker_status(task_id=task_id, db_path=db_path)}"
        )

    def test_dispatch_is_non_blocking_and_worker_completes_with_attribution(
        self, repo: Path, db_path: Path, tmp_path: Path
    ):
        """run_worker_detached returns before the worker finishes, and the
        worker's output is durably attributed to its run (criteria: survive
        the caller, reconnect, attribute output)."""
        task = _queued_task(db_path)
        worker_cmd = ["sh", "-c", "echo detached > detached.txt; sleep 0.5"]

        dispatch = br.run_worker_detached(
            task["id"],
            worker_cmd,
            timeout_seconds=30,
            heartbeat_seconds=1,
            lease_seconds=5,
            repo_root=repo,
            db_path=db_path,
            spec_dir=tmp_path / "detached",
        )

        # The caller returns immediately, owning nothing — the supervisor is a
        # distinct process in its own session.
        assert dispatch["status"] == "dispatched"
        assert dispatch["supervisor_pid"] and dispatch["supervisor_pid"] != 0
        assert dispatch["supervisor_pid"] != os.getpid()
        assert Path(dispatch["spec_path"]).is_file()

        completed = self._wait_status(task["id"], db_path, "completed")
        assert completed["reconnectable"] is True
        assert completed["final_report"]["outcome"] == bq.RUN_EXITED
        worktree = Path(completed["worktree_path"])
        assert (worktree / "detached.txt").is_file()
        assert "detached" in (worktree / "detached.txt").read_text()

        # The supervisor left a durable completion status beside its spec.
        status_file = Path(dispatch["spec_path"]).with_suffix(".status.json")
        assert status_file.is_file()
        saved = json.loads(status_file.read_text())
        assert saved["ok"] is True

    def test_detached_worker_survives_caller_exit(
        self, repo: Path, db_path: Path, tmp_path: Path
    ):
        """A worker is not stranded when the process that dispatched it dies
        immediately (terminal disconnect / watcher death). The detached
        supervisor keeps ownership and the run still completes."""
        task = _queued_task(db_path)
        spec_dir = tmp_path / "detached"
        dispatch = br.run_worker_detached(
            task["id"],
            ["sh", "-c", "echo survivor > survivor.txt; sleep 1.0"],
            timeout_seconds=30,
            heartbeat_seconds=1,
            lease_seconds=5,
            repo_root=repo,
            db_path=db_path,
            spec_dir=spec_dir,
        )
        supervisor_pid = dispatch["supervisor_pid"]

        # The supervisor lives in its own session, so it is not killed when the
        # process that launched it (the loop / watcher / terminal) dies.
        assert os.getpgid(supervisor_pid) != os.getpgid(os.getpid())

        # The dispatcher is already gone from this call's perspective; the run
        # still completes under the detached supervisor's ownership.
        completed = self._wait_status(task["id"], db_path, "completed", timeout=30)
        assert completed["final_report"]["outcome"] == bq.RUN_EXITED
        worktree = Path(completed["worktree_path"])
        assert (worktree / "survivor.txt").is_file()

    def test_status_distinguishes_running_from_crashed_and_completed(
        self, repo: Path, db_path: Path
    ):
        running_task = _queued_task(db_path)
        claimed = bq.claim_task(running_task["id"], "runner", db_path=db_path)
        running_run = bq.create_run(
            running_task["id"],
            ["sleep", "60"],
            lease_token=claimed["lease_token"],
            claim_version=claimed["claim_version"],
            db_path=db_path,
        )
        bq.update_run(
            running_run["id"],
            state=bq.RUN_RUNNING,
            pid=os.getpid(),
            process_identity=bq.capture_process_identity(os.getpid()),
            db_path=db_path,
        )
        running_status = br.detached_worker_status(
            run_id=running_run["id"], db_path=db_path
        )
        assert running_status["status"] == "running"
        assert running_status["reconnectable"] is True

        # A dead pid behind an "active" run row is a crashed worker.
        crashed_task = _queued_task(db_path)
        claimed2 = bq.claim_task(crashed_task["id"], "runner", db_path=db_path)
        crashed_run = bq.create_run(
            crashed_task["id"],
            ["sleep", "60"],
            lease_token=claimed2["lease_token"],
            claim_version=claimed2["claim_version"],
            db_path=db_path,
        )
        bq.update_run(
            crashed_run["id"],
            state=bq.RUN_RUNNING,
            pid=999999999,
            process_identity="some recorded identity",
            db_path=db_path,
        )
        crashed_status = br.detached_worker_status(
            run_id=crashed_run["id"], db_path=db_path
        )
        assert crashed_status["status"] == "crashed"
        assert crashed_status["reason"] == "process_not_running"

        # A terminal run is completed and its output is attributable.
        done_task = _queued_task(db_path)
        run = br.run_worker(
            done_task["id"],
            ["sh", "-c", "echo ok > ok.txt"],
            timeout_seconds=30,
            heartbeat_seconds=1,
            repo_root=repo,
            db_path=db_path,
        )
        done_status = br.detached_worker_status(run_id=run["id"], db_path=db_path)
        assert done_status["status"] == "completed"
        assert done_status["outcome"] == bq.RUN_EXITED
        assert done_status["reconnectable"] is True

    def test_reap_kills_orphaned_worker_and_skips_live_owner(
        self, repo: Path, db_path: Path
    ):
        """A worker whose owner died (lease stale while the process is still
        alive) is reaped; a worker with a live, current lease is left alone —
        no orphaned workers accumulate across detach/restart cycles."""
        # Real workers are spawned in their own session (pgid == pid), so model
        # them the same way here for honest killpg + liveness behavior.
        orphan_proc = subprocess.Popen(["sleep", "300"], start_new_session=True)
        live_proc = subprocess.Popen(["sleep", "300"], start_new_session=True)
        try:
            orphan_task = _queued_task(db_path)
            claimed = bq.claim_task(orphan_task["id"], "runner", db_path=db_path)
            orphan_run = bq.create_run(
                orphan_task["id"],
                ["sleep", "300"],
                lease_token=claimed["lease_token"],
                claim_version=claimed["claim_version"],
                db_path=db_path,
            )
            bq.update_run(
                orphan_run["id"],
                state=bq.RUN_RUNNING,
                pid=orphan_proc.pid,
                process_identity=bq.capture_process_identity(orphan_proc.pid),
                db_path=db_path,
            )
            # Force the task's lease to have expired long ago -> owner is gone.
            with bq.connect(db_path) as conn:
                conn.execute(
                    """
                    UPDATE tasks SET lease_expires_at = '2000-01-01 00:00:00'
                    WHERE id = ?
                    """,
                    (orphan_task["id"],),
                )
                conn.commit()

            # A second worker whose lease is still current must NOT be reaped.
            live_task = _queued_task(db_path)
            claimed2 = bq.claim_task(live_task["id"], "runner", db_path=db_path)
            live_run = bq.create_run(
                live_task["id"],
                ["sleep", "300"],
                lease_token=claimed2["lease_token"],
                claim_version=claimed2["claim_version"],
                db_path=db_path,
            )
            bq.update_run(
                live_run["id"],
                state=bq.RUN_RUNNING,
                pid=live_proc.pid,
                process_identity=bq.capture_process_identity(live_proc.pid),
                db_path=db_path,
            )

            result = br.reap_detached_workers(db_path=db_path, grace_seconds=0)
        finally:
            for proc in (orphan_proc, live_proc):
                try:
                    proc.terminate()
                except Exception:
                    pass

        assert orphan_run["id"] in result["reaped"]
        assert live_run["id"] not in result["reaped"]
        assert live_run["id"] in result["skipped"]
        # The orphan's process group was actually reclaimed (it terminated).
        assert orphan_proc.poll() is not None

    def test_detached_rejects_bad_timing_before_spawn(
        self, repo: Path, db_path: Path
    ):
        task = _queued_task(db_path)
        with pytest.raises(ValueError, match="heartbeat_seconds must be shorter"):
            br.run_worker_detached(
                task["id"],
                ["true"],
                lease_seconds=5,
                heartbeat_seconds=5,
                repo_root=repo,
                db_path=db_path,
            )
        with pytest.raises(ValueError, match="timeout_seconds must be positive"):
            br.run_worker_detached(
                task["id"],
                ["true"],
                timeout_seconds=0,
                repo_root=repo,
                db_path=db_path,
            )
        refreshed = bq.get_task(task["id"], db_path=db_path)
        assert refreshed is not None and refreshed["state"] == bq.QUEUED


def test_run_worker_detached_serializes_coordination_locations(
    repo: Path, db_path: Path, tmp_path: Path, monkeypatch
) -> None:
    task = _queued_task(db_path)
    coordination_db = tmp_path / "coordination.db"
    registry = tmp_path / "resources.yaml"

    class FakeProcess:
        pid = 424242

    monkeypatch.setattr(br.subprocess, "Popen", lambda *args, **kwargs: FakeProcess())

    dispatch = br.run_worker_detached(
        task["id"],
        ["/usr/bin/true"],
        repo_root=repo,
        db_path=db_path,
        coordination_db_path=coordination_db,
        coordination_registry_path=registry,
        spec_dir=tmp_path / "detached",
    )

    payload = json.loads(Path(dispatch["spec_path"]).read_text(encoding="utf-8"))
    assert payload["coordination_db_path"] == str(coordination_db)
    assert payload["coordination_registry_path"] == str(registry)


def test_detached_supervisor_forwards_coordination_locations(tmp_path: Path, monkeypatch) -> None:
    coordination_db = tmp_path / "coordination.db"
    registry = tmp_path / "resources.yaml"
    repo = tmp_path / "repo"
    repo.mkdir()
    queue_db = tmp_path / "queue.db"
    spec = br._detached_spec_payload(
        "task-1",
        ["/usr/bin/true"],
        worker="worker",
        model=None,
        provider=None,
        timeout_seconds=30,
        lease_seconds=5,
        heartbeat_seconds=1,
        repo_root=repo,
        db_path=queue_db,
        coordination_db_path=coordination_db,
        coordination_registry_path=registry,
        extra_env=None,
        base_sha=None,
        inject_context=False,
        reuse_dirty_worktree=False,
    )
    spec_path = tmp_path / "detached.spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    captured: dict[str, object] = {}

    def fake_run_worker(task_id, command, **kwargs):
        captured.update({"task_id": task_id, "command": command, **kwargs})
        return {"id": "run-1", "state": bq.RUN_EXITED, "final_report": {"outcome": bq.RUN_EXITED}}

    monkeypatch.setattr(br, "run_worker", fake_run_worker)

    assert br._supervise_worker(spec_path) == 0
    assert captured["coordination_db_path"] == coordination_db
    assert captured["coordination_registry_path"] == registry


def test_repo_root_honors_builder_runtime_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    canonical = tmp_path / "canonical"
    canonical.mkdir()
    monkeypatch.setenv("KITTY_BUILDER_REPO_ROOT", str(canonical))

    assert br._repo_root(None) == canonical


def test_run_worker_persists_creation_time_ownership_manifest(
    repo: Path, db_path: Path
) -> None:
    task = _queued_task(db_path, allowed_paths=["README.md"])

    run = br.run_worker(
        task["id"],
        ["/usr/bin/true"],
        repo_root=repo,
        db_path=db_path,
        heartbeat_seconds=1,
        lease_seconds=5,
    )

    ownership_path = db_path.parent / "runs" / run["id"] / "ownership.json"
    assert ownership_path.exists()
    payload = json.loads(ownership_path.read_text(encoding="utf-8"))
    assert payload["version"] == 1
    assert payload["run_id"] == run["id"]
    assert payload["task_id"] == task["id"]
    assert payload["kx_session_id"] == f"builder-run:{run['id']}"
    assert payload["declared_paths"] == ["README.md"]
    assert payload["worktree_identity"]["base_commit"] == run["start_sha"]
    assert payload["worktree_identity"]["worktree_device"] >= 0
    assert payload["worktree_identity"]["worktree_inode"] > 0


def test_run_worker_rejects_worktree_registration_tamper_before_launch(
    repo: Path, db_path: Path
) -> None:
    task = _queued_task(db_path, allowed_paths=["README.md"])
    real_write = br._write_json_atomic
    launched = False

    def write_then_tamper(path: Path, payload: dict) -> None:
        real_write(path, payload)
        if path.name == "ownership.json":
            worktree = Path(payload["worktree"])
            attacker = repo.parent / "attacker-worktree"
            subprocess.run(
                ["git", "-C", str(repo), "worktree", "add", "--detach", str(attacker), "HEAD"],
                check=True,
                capture_output=True,
                text=True,
            )
            (worktree / ".git").write_text(
                (attacker / ".git").read_text(encoding="utf-8"),
                encoding="utf-8",
            )

    real_popen = br.subprocess.Popen

    def guarded_popen(*args, **kwargs):
        nonlocal launched
        command = args[0] if args else kwargs.get("args")
        executable = command[0] if isinstance(command, (list, tuple)) and command else command
        if isinstance(executable, str) and Path(executable).name == "git":
            return real_popen(*args, **kwargs)
        launched = True
        raise AssertionError("worker process must not launch after identity tamper")

    with patch.object(br, "_write_json_atomic", side_effect=write_then_tamper), patch.object(
        br.subprocess, "Popen", side_effect=guarded_popen
    ):
        with pytest.raises(br.RunnerError, match="identity|git"):
            br.run_worker(
                task["id"],
                ["/usr/bin/true"],
                repo_root=repo,
                db_path=db_path,
                heartbeat_seconds=1,
                lease_seconds=5,
            )

    assert launched is False



def _coordination_fixture(tmp_path: Path) -> tuple[Path, Path]:
    registry = tmp_path / "coordination-resources.yaml"
    registry.write_text(
        """resources:
  docs:roadmap:
    paths:
      - README.md
  runtime:provenance:
    paths:
      - gateway/**
""",
        encoding="utf-8",
    )
    return tmp_path / "coordination.db", registry


def test_run_worker_rejects_missing_allowed_paths_before_launch(
    repo: Path, db_path: Path
) -> None:
    task = _queued_task(db_path, allowed_paths=None)

    with pytest.raises(br.RunnerError, match="allowed_paths|mutation scope|scope"):
        br.run_worker(
            task["id"],
            ["/usr/bin/true"],
            repo_root=repo,
            db_path=db_path,
            heartbeat_seconds=1,
            lease_seconds=5,
        )

    runs = bq.list_runs(task_id=task["id"], db_path=db_path)
    assert len(runs) == 1
    assert runs[0]["state"] == bq.RUN_FAILED
    assert runs[0]["final_report"]["worker_started"] is False


def test_run_worker_rejects_blank_allowed_path_before_launch(
    repo: Path, db_path: Path
) -> None:
    task = _queued_task(db_path, allowed_paths=["   "])

    with pytest.raises(br.RunnerError, match="allowed path|scope"):
        br.run_worker(
            task["id"],
            ["/usr/bin/true"],
            repo_root=repo,
            db_path=db_path,
            heartbeat_seconds=1,
            lease_seconds=5,
        )

    runs = bq.list_runs(task_id=task["id"], db_path=db_path)
    assert len(runs) == 1
    assert runs[0]["state"] == bq.RUN_FAILED
    assert runs[0]["final_report"]["worker_started"] is False


def test_run_worker_ignores_coordination_env_overrides_outside_test_mode(
    repo: Path, db_path: Path, tmp_path: Path, monkeypatch
) -> None:
    canonical_root = tmp_path / "canonical"
    canonical_root.mkdir()
    canonical_db, canonical_registry = _coordination_fixture(canonical_root)
    rogue_db = tmp_path / "rogue" / "coordination.db"
    rogue_registry = tmp_path / "rogue" / "resources.yaml"
    monkeypatch.setattr(ac, "default_db_path", lambda: canonical_db)
    monkeypatch.setattr(ac, "DEFAULT_REGISTRY_PATH", canonical_registry)
    monkeypatch.setenv("KITTY_ENV", "development")
    monkeypatch.setenv("KITTY_COORDINATION_DB_PATH", str(rogue_db))
    monkeypatch.setenv("KITTY_COORDINATION_REGISTRY_PATH", str(rogue_registry))
    task = _queued_task(db_path, allowed_paths=["README.md"])

    run = br.run_worker(
        task["id"],
        ["/usr/bin/true"],
        repo_root=repo,
        db_path=db_path,
        heartbeat_seconds=1,
        lease_seconds=5,
    )

    assert run["final_report"]["outcome"] == bq.RUN_EXITED
    assert canonical_db.exists()
    assert not rogue_db.exists()


def test_run_worker_binds_resolved_kx_resources_and_releases_on_exit(
    repo: Path, db_path: Path, tmp_path: Path
) -> None:
    coordination_db, registry = _coordination_fixture(tmp_path)
    task = _queued_task(db_path, allowed_paths=["README.md"])

    run = br.run_worker(
        task["id"],
        ["/usr/bin/true"],
        repo_root=repo,
        db_path=db_path,
        coordination_db_path=coordination_db,
        coordination_registry_path=registry,
        heartbeat_seconds=1,
        lease_seconds=5,
    )

    ownership_path = db_path.parent / "runs" / run["id"] / "ownership.json"
    payload = json.loads(ownership_path.read_text(encoding="utf-8"))
    assert payload["required_resources"] == ["docs:roadmap"]
    assert ac.list_claims(db_path=coordination_db, active_only=True) == []


def test_run_worker_kx_conflict_prevents_worker_launch(
    repo: Path, db_path: Path, tmp_path: Path
) -> None:
    coordination_db, registry = _coordination_fixture(tmp_path)
    task = _queued_task(db_path, allowed_paths=["README.md"])
    base = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    owner = ac.acquire(
        session_id="other-owner",
        role="OWN",
        resource_id="docs:roadmap",
        base_sha=base,
        paths=["README.md"],
        db_path=coordination_db,
        registry_path=registry,
        lease_seconds=60,
    )
    assert owner["status"] == "ACQUIRED"
    launched = False
    real_popen = br.subprocess.Popen

    def guard_worker(*args, **kwargs):
        nonlocal launched
        command = args[0] if args else kwargs.get("args")
        executable = command[0] if isinstance(command, (list, tuple)) and command else command
        if isinstance(executable, str) and Path(executable).name == "git":
            return real_popen(*args, **kwargs)
        launched = True
        raise AssertionError("worker must not launch without KX ownership")

    with patch.object(br.subprocess, "Popen", side_effect=guard_worker):
        with pytest.raises(br.RunnerError, match="KX|coordination|claim|ownership"):
            br.run_worker(
                task["id"],
                ["/usr/bin/true"],
                repo_root=repo,
                db_path=db_path,
                coordination_db_path=coordination_db,
                coordination_registry_path=registry,
                heartbeat_seconds=1,
                lease_seconds=5,
            )
    assert launched is False
    active = ac.list_claims(db_path=coordination_db, active_only=True)
    assert [claim["session_id"] for claim in active] == ["other-owner"]



def test_run_worker_reclaims_kx_from_interrupted_prior_run_of_same_task(
    repo: Path, db_path: Path, tmp_path: Path
) -> None:
    coordination_db, registry = _coordination_fixture(tmp_path)
    task = _queued_task(db_path, allowed_paths=["README.md"])
    base = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    claimed = bq.claim_task(task["id"], "crashed-runner", db_path=db_path)
    prior = bq.create_run(
        task["id"], ["worker"], lease_token=claimed["lease_token"],
        claim_version=claimed["claim_version"], branch="prior",
        worktree_path=str(repo), start_sha=base, db_path=db_path,
    )
    bq.worker_transition_task(
        task["id"], bq.RUNNING, claimed["lease_token"],
        claimed["claim_version"], db_path=db_path,
    )
    bq.update_run(
        prior["id"], state=bq.RUN_RUNNING, pid=os.getpid(),
        process_identity="different-process-identity", mark_started=True,
        expected_states=frozenset({bq.RUN_STARTING}), db_path=db_path,
    )
    prior_kx = ac.acquire_many(
        f"builder-run:{prior['id']}", role="OWN",
        resource_ids=["docs:roadmap"], base_sha=base, paths=["README.md"],
        participant="kitty", lane="builder-run", task_id=task["id"],
        branch="prior", worktree=str(repo), lease_seconds=60,
        db_path=coordination_db, registry_path=registry,
    )
    assert prior_kx["status"] == "ACQUIRED"
    recovered = bq.recover_interrupted_runs(db_path=db_path)
    assert prior["id"] in recovered["run_ids"]
    assert bq.get_run(prior["id"], db_path=db_path)["state"] == bq.RUN_INTERRUPTED
    bq.operator_release_task(task["id"], reason="retry interrupted run", db_path=db_path)

    run = br.run_worker(
        task["id"], ["/usr/bin/true"], repo_root=repo, db_path=db_path,
        coordination_db_path=coordination_db,
        coordination_registry_path=registry, heartbeat_seconds=1, lease_seconds=5,
    )
    assert run["final_report"]["outcome"] == bq.RUN_EXITED
    assert ac.list_claims(db_path=coordination_db, active_only=True) == []


def test_terminal_builder_kx_reclaim_refuses_other_task(
    db_path: Path, tmp_path: Path
) -> None:
    coordination_db, registry = _coordination_fixture(tmp_path)
    current_task = _queued_task(db_path, allowed_paths=["README.md"])
    holder_task = _queued_task(db_path, allowed_paths=["README.md"])
    claimed = bq.claim_task(holder_task["id"], "holder", db_path=db_path)
    prior = bq.create_run(
        holder_task["id"], ["worker"], lease_token=claimed["lease_token"],
        claim_version=claimed["claim_version"], branch="holder",
        worktree_path="/tmp/holder", start_sha="a" * 40, db_path=db_path,
    )
    bq.update_run(
        prior["id"], state=bq.RUN_FAILED, mark_ended=True,
        expected_states=frozenset({bq.RUN_STARTING}), db_path=db_path,
    )
    acquired = ac.acquire_many(
        f"builder-run:{prior['id']}", role="OWN",
        resource_ids=["docs:roadmap"], base_sha="a" * 40, paths=["README.md"],
        participant="kitty", lane="builder-run", task_id=holder_task["id"],
        branch="holder", worktree="/tmp/holder", lease_seconds=60,
        db_path=coordination_db, registry_path=registry,
    )
    assert acquired["status"] == "ACQUIRED"
    holders = ac.list_claims(active_only=True, db_path=coordination_db)

    assert br._release_terminal_builder_kx_conflicts(
        holders, task_id=current_task["id"], queue_db_path=db_path,
        coordination_db_path=coordination_db,
    ) == []
    assert [row["session_id"] for row in ac.list_claims(
        active_only=True, db_path=coordination_db
    )] == [f"builder-run:{prior['id']}"]


def test_terminal_builder_kx_reclaim_refuses_nonterminal_same_task(
    db_path: Path, tmp_path: Path
) -> None:
    coordination_db, registry = _coordination_fixture(tmp_path)
    task = _queued_task(db_path, allowed_paths=["README.md"])
    claimed = bq.claim_task(task["id"], "holder", db_path=db_path)
    prior = bq.create_run(
        task["id"], ["worker"], lease_token=claimed["lease_token"],
        claim_version=claimed["claim_version"], branch="holder",
        worktree_path="/tmp/holder", start_sha="a" * 40, db_path=db_path,
    )
    acquired = ac.acquire_many(
        f"builder-run:{prior['id']}", role="OWN",
        resource_ids=["docs:roadmap"], base_sha="a" * 40, paths=["README.md"],
        participant="kitty", lane="builder-run", task_id=task["id"],
        branch="holder", worktree="/tmp/holder", lease_seconds=60,
        db_path=coordination_db, registry_path=registry,
    )
    assert acquired["status"] == "ACQUIRED"
    holders = ac.list_claims(active_only=True, db_path=coordination_db)

    assert br._release_terminal_builder_kx_conflicts(
        holders, task_id=task["id"], queue_db_path=db_path,
        coordination_db_path=coordination_db,
    ) == []
    assert [row["session_id"] for row in ac.list_claims(
        active_only=True, db_path=coordination_db
    )] == [f"builder-run:{prior['id']}"]


def test_terminal_builder_kx_reclaim_refuses_identity_mismatch(
    db_path: Path, tmp_path: Path
) -> None:
    coordination_db, registry = _coordination_fixture(tmp_path)
    task = _queued_task(db_path, allowed_paths=["README.md"])
    claimed = bq.claim_task(task["id"], "holder", db_path=db_path)
    prior = bq.create_run(
        task["id"], ["worker"], lease_token=claimed["lease_token"],
        claim_version=claimed["claim_version"], branch="expected",
        worktree_path="/tmp/expected", start_sha="a" * 40, db_path=db_path,
    )
    bq.update_run(
        prior["id"], state=bq.RUN_FAILED, mark_ended=True,
        expected_states=frozenset({bq.RUN_STARTING}), db_path=db_path,
    )
    acquired = ac.acquire_many(
        f"builder-run:{prior['id']}", role="OWN",
        resource_ids=["docs:roadmap"], base_sha="a" * 40, paths=["README.md"],
        participant="kitty", lane="builder-run", task_id=task["id"],
        branch="spoofed", worktree="/tmp/expected", lease_seconds=60,
        db_path=coordination_db, registry_path=registry,
    )
    assert acquired["status"] == "ACQUIRED"
    holders = ac.list_claims(active_only=True, db_path=coordination_db)

    assert br._release_terminal_builder_kx_conflicts(
        holders, task_id=task["id"], queue_db_path=db_path,
        coordination_db_path=coordination_db,
    ) == []
    assert [row["session_id"] for row in ac.list_claims(
        active_only=True, db_path=coordination_db
    )] == [f"builder-run:{prior['id']}"]


def test_terminal_builder_kx_reclaim_refuses_session_with_extra_mismatched_claim(
    db_path: Path, tmp_path: Path
) -> None:
    coordination_db, registry = _coordination_fixture(tmp_path)
    task = _queued_task(db_path, allowed_paths=["README.md"])
    claimed = bq.claim_task(task["id"], "holder", db_path=db_path)
    prior = bq.create_run(
        task["id"], ["worker"], lease_token=claimed["lease_token"],
        claim_version=claimed["claim_version"], branch="expected",
        worktree_path="/tmp/expected", start_sha="a" * 40, db_path=db_path,
    )
    bq.update_run(
        prior["id"], state=bq.RUN_FAILED, mark_ended=True,
        expected_states=frozenset({bq.RUN_STARTING}), db_path=db_path,
    )
    session_id = f"builder-run:{prior['id']}"
    first = ac.acquire(
        session_id=session_id, role="OWN", resource_id="docs:roadmap",
        base_sha="a" * 40, paths=["README.md"], participant="kitty",
        lane="builder-run", task_id=task["id"], branch="expected",
        worktree="/tmp/expected", lease_seconds=60, db_path=coordination_db,
        registry_path=registry,
    )
    assert first["status"] == "ACQUIRED"
    second = ac.acquire(
        session_id=session_id, role="OWN", resource_id="runtime:provenance",
        base_sha="a" * 40, paths=["gateway/**"], participant="kitty",
        lane="builder-run", task_id=task["id"], branch="spoofed",
        worktree="/tmp/expected", lease_seconds=60, db_path=coordination_db,
        registry_path=registry,
    )
    assert second["status"] == "ACQUIRED"
    active = ac.list_claims(active_only=True, db_path=coordination_db)
    holders = [row for row in active if row["resource_id"] == "docs:roadmap"]

    assert br._release_terminal_builder_kx_conflicts(
        holders, task_id=task["id"], queue_db_path=db_path,
        coordination_db_path=coordination_db,
    ) == []
    assert sorted(row["resource_id"] for row in ac.list_claims(
        active_only=True, db_path=coordination_db
    )) == ["docs:roadmap", "runtime:provenance"]


def test_run_worker_rejects_file_scope_only_overlapped_by_unrelated_wildcard(
    repo: Path, db_path: Path, tmp_path: Path
) -> None:
    registry = tmp_path / "wildcard-resources.yaml"
    registry.write_text(
        "resources:\n  docs:roadmap:\n    paths:\n      - '*.md'\n",
        encoding="utf-8",
    )
    task = _queued_task(db_path, allowed_paths=["gateway/new_feature.py"])

    with pytest.raises(br.RunnerError, match="no registered KX resource"):
        br.run_worker(
            task["id"], ["/usr/bin/true"], repo_root=repo, db_path=db_path,
            coordination_db_path=tmp_path / "coordination.db",
            coordination_registry_path=registry, heartbeat_seconds=1, lease_seconds=5,
        )

    runs = bq.list_runs(task_id=task["id"], db_path=db_path)
    assert len(runs) == 1
    assert runs[0]["final_report"]["worker_started"] is False


def test_run_worker_explicit_future_directory_scope_resolves_by_prefix(
    repo: Path, db_path: Path, tmp_path: Path
) -> None:
    registry = tmp_path / "future-directory-resources.yaml"
    registry.write_text(
        "resources:\n  future:feature:\n    paths:\n      - future/**\n",
        encoding="utf-8",
    )
    assert not (repo / "future").exists()
    task = _queued_task(db_path, allowed_paths=["future/"])

    run = br.run_worker(
        task["id"], ["/usr/bin/true"], repo_root=repo, db_path=db_path,
        coordination_db_path=tmp_path / "coordination.db",
        coordination_registry_path=registry, heartbeat_seconds=1, lease_seconds=5,
    )
    ownership = json.loads(
        (db_path.parent / "runs" / run["id"] / "ownership.json").read_text()
    )
    assert ownership["required_resources"] == ["future:feature"]


def test_run_worker_directory_scope_claims_all_nested_semantic_resources(
    repo: Path, db_path: Path, tmp_path: Path
) -> None:
    (repo / "gateway").mkdir()
    registry = tmp_path / "directory-resources.yaml"
    registry.write_text(
        """resources:
  runtime:provenance:
    paths:
      - gateway/**
  ui:action-grammar:
    paths:
      - gateway/ui/**
""",
        encoding="utf-8",
    )
    task = _queued_task(db_path, allowed_paths=["gateway/"])

    run = br.run_worker(
        task["id"], ["/usr/bin/true"], repo_root=repo, db_path=db_path,
        coordination_db_path=tmp_path / "coordination.db",
        coordination_registry_path=registry, heartbeat_seconds=1, lease_seconds=5,
    )
    ownership = json.loads(
        (db_path.parent / "runs" / run["id"] / "ownership.json").read_text()
    )
    assert ownership["required_resources"] == [
        "runtime:provenance", "ui:action-grammar"
    ]


def test_run_worker_unmapped_scope_fails_setup_without_kx_leak(
    repo: Path, db_path: Path, tmp_path: Path
) -> None:
    coordination_db, registry = _coordination_fixture(tmp_path)
    task = _queued_task(db_path, allowed_paths=["unmapped/"])

    with pytest.raises(br.RunnerError, match="no registered KX resource"):
        br.run_worker(
            task["id"], ["/usr/bin/true"], repo_root=repo, db_path=db_path,
            coordination_db_path=coordination_db,
            coordination_registry_path=registry, heartbeat_seconds=1, lease_seconds=5,
        )

    runs = bq.list_runs(task_id=task["id"], db_path=db_path)
    assert len(runs) == 1 and runs[0]["state"] == bq.RUN_FAILED
    assert runs[0]["final_report"]["worker_started"] is False
    assert ac.list_claims(db_path=coordination_db, active_only=True) == []



def test_run_worker_post_acquisition_setup_failure_releases_kx(
    repo: Path, db_path: Path, tmp_path: Path, monkeypatch
) -> None:
    coordination_db, registry = _coordination_fixture(tmp_path)
    task = _queued_task(db_path, allowed_paths=["README.md"])
    monkeypatch.setattr(
        br,
        "inject_worker_context",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("context boom")),
    )

    with pytest.raises(br.RunnerError, match="context boom"):
        br.run_worker(
            task["id"],
            ["/usr/bin/true"],
            repo_root=repo,
            db_path=db_path,
            coordination_db_path=coordination_db,
            coordination_registry_path=registry,
            heartbeat_seconds=1,
            lease_seconds=5,
            inject_context=True,
        )

    runs = bq.list_runs(task_id=task["id"], db_path=db_path)
    assert len(runs) == 1
    assert runs[0]["state"] == bq.RUN_FAILED
    assert runs[0]["final_report"]["worker_started"] is False
    assert "context boom" in runs[0]["final_report"]["error"]
    assert ac.list_claims(db_path=coordination_db, active_only=True) == []


def test_run_worker_launch_failure_releases_kx(
    repo: Path, db_path: Path, tmp_path: Path, monkeypatch
) -> None:
    coordination_db, registry = _coordination_fixture(tmp_path)
    task = _queued_task(db_path, allowed_paths=["README.md"])
    monkeypatch.setattr(br.beb, "wrap_command", lambda *a, **k: (_ for _ in ()).throw(OSError("boundary boom")))

    with pytest.raises(br.RunnerError, match="boundary boom"):
        br.run_worker(
            task["id"], ["/usr/bin/true"], repo_root=repo, db_path=db_path,
            coordination_db_path=coordination_db,
            coordination_registry_path=registry, heartbeat_seconds=1, lease_seconds=5,
        )

    assert ac.list_claims(db_path=coordination_db, active_only=True) == []


def test_run_worker_failure_and_timeout_release_kx(
    repo: Path, db_path: Path, tmp_path: Path
) -> None:
    coordination_db, registry = _coordination_fixture(tmp_path)
    failed_task = _queued_task(db_path, allowed_paths=["README.md"])
    failed = br.run_worker(
        failed_task["id"], ["/usr/bin/false"], repo_root=repo, db_path=db_path,
        coordination_db_path=coordination_db, coordination_registry_path=registry,
        heartbeat_seconds=0.1, lease_seconds=2, timeout_seconds=5,
    )
    assert failed["final_report"]["outcome"] == bq.RUN_FAILED
    assert ac.list_claims(db_path=coordination_db, active_only=True) == []

    timeout_task = _queued_task(db_path, allowed_paths=["README.md"])
    timed_out = br.run_worker(
        timeout_task["id"], ["/bin/sleep", "2"], repo_root=repo, db_path=db_path,
        coordination_db_path=coordination_db, coordination_registry_path=registry,
        heartbeat_seconds=0.1, lease_seconds=2, timeout_seconds=0.25,
    )
    assert timed_out["final_report"]["outcome"] == bq.RUN_TIMEOUT
    assert ac.list_claims(db_path=coordination_db, active_only=True) == []


def test_run_worker_cancellation_releases_kx(
    repo: Path, db_path: Path, tmp_path: Path
) -> None:
    coordination_db, registry = _coordination_fixture(tmp_path)
    task = _queued_task(db_path, allowed_paths=["README.md"])
    result: dict[str, object] = {}

    def run() -> None:
        try:
            result["run"] = br.run_worker(
                task["id"], ["/bin/sleep", "5"], repo_root=repo, db_path=db_path,
                coordination_db_path=coordination_db,
                coordination_registry_path=registry,
                heartbeat_seconds=0.1, lease_seconds=2, timeout_seconds=10,
            )
        except Exception as exc:
            result["error"] = exc

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    run_row = None
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        runs = bq.list_runs(task_id=task["id"], db_path=db_path)
        if runs and runs[-1]["state"] == bq.RUN_RUNNING:
            run_row = runs[-1]
            break
        time.sleep(0.02)
    assert run_row is not None

    br.request_cancel(str(run_row["id"]), db_path=db_path)
    thread.join(timeout=3)
    assert not thread.is_alive()
    assert "error" not in result
    final = result["run"]
    assert isinstance(final, dict)
    assert final["final_report"]["outcome"] == bq.RUN_CANCELLED
    assert ac.list_claims(db_path=coordination_db, active_only=True) == []


def test_run_worker_stops_when_kx_renewal_returns_partial_resource_set(
    repo: Path, db_path: Path, tmp_path: Path, monkeypatch
) -> None:
    coordination_db, registry = _coordination_fixture(tmp_path)
    task = _queued_task(db_path, allowed_paths=["README.md", "gateway/"])
    real_renew = ac.renew
    heartbeat_at_authority_loss: str | None = None

    def partial_when_worker_running(session_id, **kwargs):
        nonlocal heartbeat_at_authority_loss
        result = real_renew(session_id, **kwargs)
        runs = bq.list_runs(task_id=task["id"], db_path=db_path)
        running = next((run for run in runs if run["state"] == bq.RUN_RUNNING), None)
        if running is not None:
            heartbeat_at_authority_loss = running["last_heartbeat_at"]
            result["claims"] = result["claims"][:1]
            result["renewed"] = 1
        return result

    monkeypatch.setattr(ac, "renew", partial_when_worker_running)
    started = time.monotonic()
    run = br.run_worker(
        task["id"],
        ["/bin/sleep", "2"],
        repo_root=repo,
        db_path=db_path,
        coordination_db_path=coordination_db,
        coordination_registry_path=registry,
        heartbeat_seconds=0.1,
        lease_seconds=2,
        timeout_seconds=5,
    )

    assert time.monotonic() - started < 1.5
    assert run["final_report"]["outcome"] == bq.RUN_LEASE_LOST
    task_after = bq.get_task(task["id"], db_path=db_path)
    assert task_after is not None
    assert task_after["blocked_reason"] == "run_lease_lost"
    final_run = bq.get_run(str(run["id"]), db_path=db_path)
    assert final_run is not None
    assert heartbeat_at_authority_loss is not None
    assert final_run["last_heartbeat_at"] == heartbeat_at_authority_loss
    assert ac.list_claims(db_path=coordination_db, active_only=True) == []


def test_run_worker_stops_when_persisted_worktree_identity_changes_live(
    repo: Path, db_path: Path
) -> None:
    task = _queued_task(db_path, allowed_paths=["README.md"])
    attacker = repo.parent / "attacker-live-worktree"
    subprocess.run(
        ["git", "-C", str(repo), "worktree", "add", "--detach", str(attacker), "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    result: dict[str, object] = {}

    def run() -> None:
        try:
            result["run"] = br.run_worker(
                task["id"],
                ["/bin/sleep", "2"],
                repo_root=repo,
                db_path=db_path,
                heartbeat_seconds=0.1,
                lease_seconds=2,
                timeout_seconds=5,
            )
        except Exception as exc:
            result["error"] = exc

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    run_row = None
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        runs = bq.list_runs(task_id=task["id"], db_path=db_path)
        if runs and runs[-1].get("state") == bq.RUN_RUNNING:
            run_row = runs[-1]
            break
        time.sleep(0.02)
    assert run_row is not None
    victim = Path(str(run_row["worktree_path"]))
    (victim / ".git").write_text(
        (attacker / ".git").read_text(encoding="utf-8"), encoding="utf-8"
    )

    thread.join(timeout=0.8)
    stopped_early = not thread.is_alive()
    if thread.is_alive():
        br.request_cancel(str(run_row["id"]), db_path=db_path)
        thread.join(timeout=2)

    assert stopped_early is True
    assert isinstance(result.get("error"), br.RunnerError)
    assert "identity" in str(result["error"]).lower() or "git" in str(result["error"]).lower()
