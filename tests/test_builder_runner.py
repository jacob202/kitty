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

    def test_scope_check_includes_commits_since_start_sha(
        self, repo: Path, db_path: Path
    ):
        task = _queued_task(db_path, allowed_paths=["gateway/"])
        command = [
            "sh",
            "-c",
            "mkdir -p gateway && echo ok > gateway/ok.py && "
            "git add gateway/ok.py && "
            "git -c user.email=test@example.com -c user.name=test "
            "commit -q -m worker-change",
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
        assert run["final_report"]["changed_paths"] == ["gateway/ok.py"]
        assert run["final_report"]["scope_violations"] == []

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
            timeout_seconds=2, heartbeat_seconds=1,
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
                timeout_seconds=30, lease_seconds=5, heartbeat_seconds=1,
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

        def fail_renew(task_id, lease_token, claim_version, *,
                        lease_seconds=300, db_path=None):
            call_count[0] += 1
            if call_count[0] > 3:
                raise RuntimeError("post-loop renewal failure")
            return bq.renew_lease(
                task_id, lease_token, claim_version,
                lease_seconds=lease_seconds, db_path=db_path,
            )

        monkeypatch.setattr(bq, "renew_lease", fail_renew)

        with pytest.raises(br.RunnerError, match="monitoring failed"):
            br.run_worker(
                task["id"], ["sleep", "2"],
                timeout_seconds=30, lease_seconds=10, heartbeat_seconds=1,
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
                timeout_seconds=30, lease_seconds=5, heartbeat_seconds=1,
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
                heartbeat_seconds=1,
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
