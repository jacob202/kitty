"""Tests for gateway/builder_doctor.py — read-only KittyBuilder preflight."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from gateway import builder_doctor as doctor
from gateway import builder_initiative as bi
from gateway import builder_queue as bq
from gateway.builder_cli import build_parser, main

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    p = tmp_path / "kittybuilder" / "builder_queue.db"
    bi.init_db(p)
    return p


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A throwaway git repo with a commit on the default branch."""
    root = tmp_path / "kitty"
    root.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)
    (root / "README.md").write_text("hello\n")
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=root, check=True)
    return root


def _set_task_fields(db_path: Path, task_id: str, **fields):
    conn = bq.connect(db_path)
    try:
        assignments = ", ".join(f"{name}=?" for name in fields)
        conn.execute(f"UPDATE tasks SET {assignments} WHERE id=?", (*fields.values(), task_id))
        conn.commit()
    finally:
        conn.close()


def _set_run_fields(db_path: Path, run_id: str, **fields):
    conn = bq.connect(db_path)
    try:
        assignments = ", ".join(f"{name}=?" for name in fields)
        conn.execute(f"UPDATE runs SET {assignments} WHERE id=?", (*fields.values(), run_id))
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Kill switch
# ---------------------------------------------------------------------------


class TestKillSwitch:
    def test_enabled_by_default(self, monkeypatch):
        monkeypatch.delenv("KITTY_BUILDER_QUEUE_ENABLED", raising=False)
        checks = doctor._check_kill_switch()
        assert checks[0].level == "PASS"

    def test_disabled_is_warn_not_fail(self, monkeypatch):
        monkeypatch.setenv("KITTY_BUILDER_QUEUE_ENABLED", "0")
        checks = doctor._check_kill_switch()
        assert checks[0].level == "WARN"
        assert "KITTY_BUILDER_QUEUE_ENABLED=0" in checks[0].detail


# ---------------------------------------------------------------------------
# Database open / integrity
# ---------------------------------------------------------------------------


class TestDatabase:
    def test_missing_db_is_warn(self, tmp_path: Path):
        checks = doctor._check_database(tmp_path / "nope" / "builder_queue.db")
        assert [c.level for c in checks] == ["WARN"]

    def test_healthy_db_passes_open_and_integrity(self, db_path: Path):
        checks = doctor._check_database(db_path)
        levels = {c.name: c.level for c in checks}
        assert levels["db:open"] == "PASS"
        assert levels["db:integrity_check"] == "PASS"

    def test_corrupted_db_fails(self, tmp_path: Path):
        bad = tmp_path / "bad.db"
        bad.write_bytes(b"not a sqlite file at all, definitely corrupt garbage")
        checks = doctor._check_database(bad)
        # SQLite may reject the header as early as connect()'s pragma setup
        # (db:open) or only once PRAGMA integrity_check reads it — either is
        # a legitimate blocking outcome, so accept either check name failing.
        assert any(c.level == "FAIL" for c in checks)

    def test_never_creates_missing_db_file(self, tmp_path: Path):
        target = tmp_path / "never" / "builder_queue.db"
        doctor._check_database(target)
        assert not target.exists()


# ---------------------------------------------------------------------------
# Initiative pause state
# ---------------------------------------------------------------------------


def _manifest(**overrides) -> dict:
    base = {
        "manifest_version": 1,
        "initiative_id": "kitty-doctor-v1",
        "title": "Doctor test initiative",
        "description": "Fixture initiative for doctor tests.",
        "packets": [
            {
                "id": "KB-D1",
                "title": "Only packet",
                "objective": "Do a thing.",
                "depends_on": [],
                "acceptance_criteria": ["it works"],
                "allowed_paths": ["gateway/a.py"],
            },
        ],
    }
    base.update(overrides)
    return base


class TestInitiativePauseState:
    def test_no_initiatives_passes(self, db_path: Path):
        checks = doctor._check_initiative_pause_state(db_path)
        assert checks == [doctor.Check("PASS", "initiative:pause_state", "no initiatives")]

    def test_active_initiative_passes(self, db_path: Path):
        bi.apply_manifest(_manifest(), db_path=db_path)
        checks = doctor._check_initiative_pause_state(db_path)
        assert checks[0].level == "PASS"

    def test_paused_initiative_warns_with_id(self, db_path: Path):
        bi.apply_manifest(_manifest(), db_path=db_path)
        bi.pause_initiative("kitty-doctor-v1", "operator halt", db_path=db_path)
        checks = doctor._check_initiative_pause_state(db_path)
        assert checks[0].level == "WARN"
        assert "kitty-doctor-v1" in checks[0].detail


# ---------------------------------------------------------------------------
# Repo identity + default branch
# ---------------------------------------------------------------------------


class TestRepoIdentity:
    def test_matching_repo_and_branch_pass(self, repo: Path, monkeypatch):
        monkeypatch.setattr(doctor, "EXPECTED_REPO_NAME", "kitty")
        monkeypatch.setattr(doctor, "EXPECTED_DEFAULT_BRANCH", "main")
        checks = doctor._check_repo_identity(repo)
        levels = {c.name: c.level for c in checks}
        assert levels["repo:identity"] == "PASS"
        assert levels["repo:default_branch"] == "PASS"

    def test_wrong_repo_name_fails(self, repo: Path, monkeypatch):
        monkeypatch.setattr(doctor, "EXPECTED_REPO_NAME", "some-other-repo")
        checks = doctor._check_repo_identity(repo)
        levels = {c.name: c.level for c in checks}
        assert levels["repo:identity"] == "FAIL"

    def test_missing_default_branch_fails(self, repo: Path, monkeypatch):
        monkeypatch.setattr(doctor, "EXPECTED_REPO_NAME", "kitty")
        monkeypatch.setattr(doctor, "EXPECTED_DEFAULT_BRANCH", "does-not-exist")
        checks = doctor._check_repo_identity(repo)
        levels = {c.name: c.level for c in checks}
        assert levels["repo:default_branch"] == "FAIL"

    def test_not_a_git_repo_fails(self, tmp_path: Path):
        not_repo = tmp_path / "not-a-repo"
        not_repo.mkdir()
        checks = doctor._check_repo_identity(not_repo)
        assert len(checks) == 1
        assert checks[0].level == "FAIL"
        assert checks[0].name == "repo:identity"


# ---------------------------------------------------------------------------
# Required worker commands
# ---------------------------------------------------------------------------


class TestWorkerCommands:
    def test_all_present_pass(self):
        checks = doctor._check_worker_commands()
        assert all(c.level == "PASS" for c in checks)
        assert {c.name for c in checks} == {"tool:bash", "tool:git", "tool:false"}

    def test_missing_tool_fails(self, monkeypatch):
        real_which = doctor.shutil.which

        def fake_which(cmd):
            if cmd == "false":
                return None
            return real_which(cmd)

        monkeypatch.setattr(doctor.shutil, "which", fake_which)
        checks = doctor._check_worker_commands()
        levels = {c.name: c.level for c in checks}
        assert levels["tool:false"] == "FAIL"
        assert levels["tool:bash"] == "PASS"


# ---------------------------------------------------------------------------
# Worktree root
# ---------------------------------------------------------------------------


class TestWorktreeRoot:
    def test_absent_but_creatable_warns(self, repo: Path):
        checks = doctor._check_worktree_root(repo)
        assert checks[0].level == "WARN"

    def test_present_directory_passes(self, repo: Path):
        (repo / ".worktrees" / "kittybuilder").mkdir(parents=True)
        checks = doctor._check_worktree_root(repo)
        assert checks[0].level == "PASS"

    def test_present_as_file_fails(self, repo: Path):
        (repo / ".worktrees").mkdir()
        (repo / ".worktrees" / "kittybuilder").write_text("not a directory")
        checks = doctor._check_worktree_root(repo)
        assert checks[0].level == "FAIL"


# ---------------------------------------------------------------------------
# Active / stale / interrupted runs (read-only twin of recovery inspection)
# ---------------------------------------------------------------------------


class TestRuns:
    def test_no_db_yet_passes(self, tmp_path: Path):
        checks = doctor._check_runs(tmp_path / "no" / "builder_queue.db")
        assert checks == [doctor.Check("PASS", "runs:leases", "no queue DB yet — nothing to recover")]

    def test_no_active_runs_passes(self, db_path: Path):
        checks = doctor._check_runs(db_path)
        levels = {c.name: c.level for c in checks}
        assert levels["runs:stale_leases"] == "PASS"
        assert levels["runs:active"] == "PASS"

    def test_stale_claimed_lease_warns(self, db_path: Path):
        task = bq.create_task("t", db_path=db_path)
        claimed = bq.claim_task(task["id"], "worker", lease_seconds=1800, db_path=db_path)
        _set_task_fields(db_path, claimed["id"], lease_expires_at="2000-01-01 00:00:00.000")

        checks = doctor._check_runs(db_path)
        levels = {c.name: c.level for c in checks}
        assert levels["runs:stale_leases"] == "WARN"
        assert claimed["id"] in [c.detail for c in checks if c.name == "runs:stale_leases"][0]

    def test_active_run_with_dead_pid_reports_interrupted(self, db_path: Path):
        task = bq.create_task("t", db_path=db_path)
        claimed = bq.claim_task(task["id"], "worker", lease_seconds=1800, db_path=db_path)
        run = bq.create_run(
            task["id"],
            ["true"],
            lease_token=claimed["lease_token"],
            claim_version=claimed["claim_version"],
            db_path=db_path,
        )
        bq.update_run(
            run["id"],
            state=bq.RUN_RUNNING,
            pid=999_999_999,  # near-certainly not a live process
            process_identity="fake-identity",
            mark_started=True,
            mark_heartbeat=True,
            expected_states=frozenset({bq.RUN_STARTING}),
            db_path=db_path,
        )

        checks = doctor._check_runs(db_path)
        levels = {c.name: c.level for c in checks}
        assert levels["runs:interrupted"] == "WARN"
        assert run["id"] in [c.detail for c in checks if c.name == "runs:interrupted"][0]

    def test_matching_zero_claim_versions_is_not_a_false_conflict(self, db_path: Path):
        """claim_version=0 is a valid, matching value — falsy-zero must not
        be mistaken for "missing" and coerced into a spurious mismatch."""
        task = bq.create_task("t", db_path=db_path)
        claimed = bq.claim_task(task["id"], "worker", lease_seconds=1800, db_path=db_path)
        run = bq.create_run(
            task["id"],
            ["true"],
            lease_token=claimed["lease_token"],
            claim_version=claimed["claim_version"],
            db_path=db_path,
        )
        bq.update_run(
            run["id"],
            state=bq.RUN_RUNNING,
            pid=999_999_999,
            process_identity="fake-identity",
            mark_started=True,
            mark_heartbeat=True,
            expected_states=frozenset({bq.RUN_STARTING}),
            db_path=db_path,
        )
        _set_task_fields(db_path, task["id"], claim_version=0)
        _set_run_fields(db_path, run["id"], claim_version=0)

        checks = doctor._check_runs(db_path)
        names = {c.name for c in checks}
        assert "runs:conflicting" not in names
        levels = {c.name: c.level for c in checks}
        assert levels["runs:interrupted"] == "WARN"

    def test_never_mutates_task_or_run_state(self, db_path: Path):
        task = bq.create_task("t", db_path=db_path)
        claimed = bq.claim_task(task["id"], "worker", lease_seconds=1800, db_path=db_path)
        run = bq.create_run(
            task["id"],
            ["true"],
            lease_token=claimed["lease_token"],
            claim_version=claimed["claim_version"],
            db_path=db_path,
        )
        bq.update_run(
            run["id"],
            state=bq.RUN_RUNNING,
            pid=999_999_999,
            process_identity="fake-identity",
            mark_started=True,
            mark_heartbeat=True,
            expected_states=frozenset({bq.RUN_STARTING}),
            db_path=db_path,
        )

        doctor._check_runs(db_path)

        task_after = bq.get_task(task["id"], db_path=db_path)
        run_after = bq.get_run(run["id"], db_path=db_path)
        assert task_after["state"] == bq.CLAIMED
        assert run_after["state"] == bq.RUN_RUNNING


# ---------------------------------------------------------------------------
# GitHub boundary
# ---------------------------------------------------------------------------


class TestGithubBoundary:
    def test_gh_present_passes_without_leaking_token(self, monkeypatch):
        monkeypatch.setattr(doctor.shutil, "which", lambda cmd: "/usr/bin/gh" if cmd == "gh" else None)
        monkeypatch.setenv("GITHUB_TOKEN", "super-secret-value")
        checks = doctor._check_github_boundary()
        assert checks[0].level == "PASS"
        assert "super-secret-value" not in checks[0].detail

    def test_neither_present_warns(self, monkeypatch):
        monkeypatch.setattr(doctor.shutil, "which", lambda cmd: None)
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        checks = doctor._check_github_boundary()
        assert checks[0].level == "WARN"

    def test_token_without_gh_warns_and_does_not_leak(self, monkeypatch):
        monkeypatch.setattr(doctor.shutil, "which", lambda cmd: None)
        monkeypatch.setenv("GITHUB_TOKEN", "super-secret-value")
        checks = doctor._check_github_boundary()
        assert checks[0].level == "WARN"
        assert "super-secret-value" not in checks[0].detail


# ---------------------------------------------------------------------------
# Credential isolation
# ---------------------------------------------------------------------------


class TestCredentialIsolation:
    def test_real_blocklist_passes(self):
        checks = doctor._check_credential_isolation()
        assert checks[0].level == "PASS"

    def test_empty_blocklist_fails(self, monkeypatch):
        from gateway import builder_runner

        monkeypatch.setattr(builder_runner, "_EXTRA_ENV_BLOCKED", frozenset())
        checks = doctor._check_credential_isolation()
        assert checks[0].level == "FAIL"

    def test_missing_expected_var_fails(self, monkeypatch):
        from gateway import builder_runner

        monkeypatch.setattr(builder_runner, "_EXTRA_ENV_BLOCKED", frozenset({"SSH_AUTH_SOCK"}))
        checks = doctor._check_credential_isolation()
        assert checks[0].level == "FAIL"
        assert "GITHUB_TOKEN" in checks[0].detail


# ---------------------------------------------------------------------------
# run_doctor() integration
# ---------------------------------------------------------------------------


class TestRunDoctor:
    def test_healthy_setup_is_ok(self, db_path: Path, repo: Path, monkeypatch):
        monkeypatch.setattr(doctor, "EXPECTED_REPO_NAME", "kitty")
        monkeypatch.setattr(doctor, "EXPECTED_DEFAULT_BRANCH", "main")
        monkeypatch.delenv("KITTY_BUILDER_QUEUE_ENABLED", raising=False)

        result = doctor.run_doctor(db_path=db_path, repo_root=repo)

        assert result["ok"] is True
        assert result["summary"]["fail"] == 0
        assert isinstance(result["checks"], list) and result["checks"]

    def test_blocking_problem_flips_ok_false(self, db_path: Path, repo: Path, monkeypatch):
        monkeypatch.setattr(doctor, "EXPECTED_REPO_NAME", "not-this-repo")
        monkeypatch.setattr(doctor, "EXPECTED_DEFAULT_BRANCH", "main")

        result = doctor.run_doctor(db_path=db_path, repo_root=repo)

        assert result["ok"] is False
        assert result["summary"]["fail"] >= 1

    def test_result_is_json_serializable(self, db_path: Path, repo: Path, monkeypatch):
        monkeypatch.setattr(doctor, "EXPECTED_REPO_NAME", "kitty")
        monkeypatch.setattr(doctor, "EXPECTED_DEFAULT_BRANCH", "main")

        result = doctor.run_doctor(db_path=db_path, repo_root=repo)

        json.dumps(result)  # must not raise


# ---------------------------------------------------------------------------
# CLI wiring
# ---------------------------------------------------------------------------


@pytest.fixture
def cli_db(tmp_path: Path, monkeypatch) -> Path:
    """Point the module-level default DB at a tmp path for end-to-end CLI runs."""
    p = tmp_path / "kittybuilder" / "builder_queue.db"
    monkeypatch.setattr(bq, "BUILDER_QUEUE_DB", p)
    return p


class TestCLI:
    def test_parser_accepts_doctor(self):
        parser = build_parser()
        args = parser.parse_args(["initiative", "doctor"])
        assert args.initiative_command == "doctor"
        assert args.json is False

    def test_parser_accepts_doctor_json_flag(self):
        parser = build_parser()
        args = parser.parse_args(["initiative", "doctor", "--json"])
        assert args.json is True

    def test_main_returns_zero_when_healthy(self, cli_db, monkeypatch, capsys):
        monkeypatch.setattr(
            "gateway.builder_doctor.run_doctor",
            lambda **kwargs: {
                "ok": True,
                "summary": {"pass": 5, "warn": 0, "fail": 0},
                "checks": [{"level": "PASS", "name": "x", "detail": "fine"}],
            },
        )
        rc = main(["initiative", "doctor"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "OK" in out

    def test_main_returns_one_when_blocking(self, cli_db, monkeypatch, capsys):
        monkeypatch.setattr(
            "gateway.builder_doctor.run_doctor",
            lambda **kwargs: {
                "ok": False,
                "summary": {"pass": 0, "warn": 0, "fail": 1},
                "checks": [{"level": "FAIL", "name": "x", "detail": "broken"}],
            },
        )
        rc = main(["initiative", "doctor"])
        assert rc == 1
        out = capsys.readouterr().out
        assert "NOT SAFE" in out

    def test_main_json_output_is_parseable(self, cli_db, monkeypatch, capsys):
        payload = {
            "ok": True,
            "summary": {"pass": 1, "warn": 0, "fail": 0},
            "checks": [{"level": "PASS", "name": "x", "detail": "fine"}],
        }
        monkeypatch.setattr("gateway.builder_doctor.run_doctor", lambda **kwargs: payload)
        rc = main(["initiative", "doctor", "--json"])
        assert rc == 0
        printed = json.loads(capsys.readouterr().out)
        assert printed == payload

    def test_doctor_runs_even_when_kill_switch_active(self, cli_db, monkeypatch, capsys):
        monkeypatch.setenv("KITTY_BUILDER_QUEUE_ENABLED", "0")
        monkeypatch.setattr(
            "gateway.builder_doctor.run_doctor",
            lambda **kwargs: {
                "ok": True,
                "summary": {"pass": 1, "warn": 1, "fail": 0},
                "checks": [{"level": "WARN", "name": "queue:kill_switch", "detail": "active"}],
            },
        )
        rc = main(["initiative", "doctor"])
        assert rc == 0

    def test_doctor_not_in_mutating_commands(self):
        from gateway.builder_cli import _MUTATING_INITIATIVE_COMMANDS

        assert "doctor" not in _MUTATING_INITIATIVE_COMMANDS
