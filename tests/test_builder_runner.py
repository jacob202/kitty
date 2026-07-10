"""Phase 1C-alpha tests for gateway/builder_runner.py — shadow-mode runner.

Uses a real throwaway git repo per test (worktree behavior can't be mocked
honestly) and a tmp queue DB. Worker commands are tiny shell scripts.
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

import pytest

from gateway import builder_queue as bq
from gateway import builder_runner as br


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


def _queued_task(db_path: Path, **kwargs) -> dict:
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

    def test_reuses_clean_worktree(self, repo: Path):
        p1 = br.ensure_worktree("kb_t2_aaaa", "kittybuilder/kb_t2_aaaa", repo_root=repo)
        p2 = br.ensure_worktree("kb_t2_aaaa", "kittybuilder/kb_t2_aaaa", repo_root=repo)
        assert p1 == p2

    def test_refuses_dirty_worktree(self, repo: Path):
        path = br.ensure_worktree("kb_t3_aaaa", "kittybuilder/kb_t3_aaaa", repo_root=repo)
        (path / "junk.txt").write_text("partial progress")
        with pytest.raises(br.RunnerError, match="dirty"):
            br.ensure_worktree("kb_t3_aaaa", "kittybuilder/kb_t3_aaaa", repo_root=repo)

    def test_refuses_wrong_branch(self, repo: Path):
        br.ensure_worktree("kb_t4_aaaa", "kittybuilder/kb_t4_aaaa", repo_root=repo)
        with pytest.raises(br.RunnerError, match="refusing to reuse"):
            br.ensure_worktree("kb_t4_aaaa", "some/other-branch", repo_root=repo)

    def test_remove_clean_worktree(self, repo: Path):
        path = br.ensure_worktree("kb_t5_aaaa", "kittybuilder/kb_t5_aaaa", repo_root=repo)
        removed = br.remove_worktree("kb_t5_aaaa", repo_root=repo)
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

        refreshed = bq.get_task(task["id"], db_path=db_path)
        assert refreshed["state"] == "blocked"
        report = json.loads(refreshed["final_report_json"])
        assert report["outcome"] == bq.RUN_EXITED
        assert report["run_id"] == run["id"]
        # Partial progress discoverable: worktree + log survive.
        assert Path(run["worktree_path"]).exists()
        assert (Path(run["worktree_path"]) / "result.txt").exists()
        assert "did work" in Path(run["log_path"]).read_text()
        # Brief was written for the worker.
        assert (Path(run["worktree_path"]) / ".kittybuilder" / "brief.md").exists()

        events = [e["type"] for e in bq.list_events(task["id"], db_path=db_path)]
        assert "run_started" in events
        assert "run_exited" in events

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

    def test_timeout_terminates_and_blocks(self, repo: Path, db_path: Path):
        task = _queued_task(db_path)
        start = time.monotonic()
        run = br.run_worker(
            task["id"],
            ["sleep", "60"],
            timeout_seconds=2,
            heartbeat_seconds=1,
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
            ["sh", "-c", 'echo "gh=[${GITHUB_TOKEN:-unset}] ght=[${GH_TOKEN:-unset}]"'],
            timeout_seconds=30,
            heartbeat_seconds=1,
            repo_root=repo,
            db_path=db_path,
        )
        log = Path(run["log_path"]).read_text()
        assert "gh=[unset]" in log
        assert "ght=[unset]" in log

    def test_claim_conflict_raises(self, repo: Path, db_path: Path):
        task = _queued_task(db_path)
        bq.claim_task(task["id"], "someone-else", db_path=db_path)
        with pytest.raises(bq.LeaseConflictError):
            br.run_worker(
                task["id"], ["true"], repo_root=repo, db_path=db_path
            )

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

    def test_heartbeat_renews_lease_during_run(self, repo: Path, db_path: Path):
        task = _queued_task(db_path)
        run = br.run_worker(
            task["id"],
            ["sleep", "3"],
            timeout_seconds=30,
            lease_seconds=2,  # would expire mid-run without heartbeat
            heartbeat_seconds=1,
            repo_root=repo,
            db_path=db_path,
        )
        # Lease survived (run completed and could still record its outcome).
        assert run["state"] == bq.RUN_EXITED
        assert run["last_heartbeat_at"] is not None
        refreshed = bq.get_task(task["id"], db_path=db_path)
        assert refreshed["state"] == "blocked"


# ---------------------------------------------------------------------------
# Cancellation
# ---------------------------------------------------------------------------


class TestRequestCancel:
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

    def test_cancel_inactive_run_rejected(self, db_path: Path):
        task = _queued_task(db_path)
        run = bq.create_run(task["id"], ["true"], db_path=db_path)
        bq.update_run(run["id"], state=bq.RUN_EXITED, db_path=db_path)
        with pytest.raises(ValueError, match="not active"):
            br.request_cancel(run["id"], db_path=db_path)

    def test_cancel_unknown_run(self, db_path: Path):
        with pytest.raises(bq.RunNotFoundError):
            br.request_cancel("run_nope_0000", db_path=db_path)
