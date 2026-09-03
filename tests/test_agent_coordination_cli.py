from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
BASE_ENV = {"PYTHONPATH": str(ROOT)}


def _registry(path: Path) -> Path:
    payload = {
        "resources": {
            "dest:files": {"paths": ["b/**"]},
            "docs:roadmap": {"paths": ["docs/ROADMAP.md"]},
            "runtime:provenance": {"paths": ["gateway/runtime_manifest.py"]},
            "source:files": {"paths": ["a/**"]},
        }
    }
    path.write_text(yaml.safe_dump(payload, sort_keys=True), encoding="utf-8")
    return path


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.name", "Kitty Test")
    _git(repo, "config", "user.email", "kitty-test@example.invalid")
    (repo / "coordination").mkdir()
    _registry(repo / "coordination" / "resources.yaml")
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-qm", "seed")
    _git(repo, "branch", "-M", "feature")
    return repo


@pytest.fixture
def cli_env(tmp_path: Path) -> dict[str, str]:
    return {
        **os.environ,
        **BASE_ENV,
        "KITTY_DATA_ROOT": str(tmp_path / "data"),
        "KITTY_AGENT_PARTICIPANT": "chatgpt",
        "KITTY_AGENT_SESSION_ID": "session-one",
    }


def _run(repo: Path, env: dict[str, str], *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "gateway.agent_coordination_cli", *args],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
    )


def _claim(repo: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return _run(
        repo,
        env,
        "claim",
        "--resource",
        "runtime:provenance",
        "--role",
        "OWN",
        "--paths",
        "gateway/**",
        "--task",
        "KX-COORD-01",
        "--lane",
        "coordination",
        "--json",
    )


def test_claim_auto_resolves_git_identity_and_status_json(
    repo: Path, cli_env: dict[str, str]
) -> None:
    head = _git(repo, "rev-parse", "HEAD")
    result = _claim(repo, cli_env)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    claim = payload["claim"]
    assert claim["session_id"] == "session-one"
    assert claim["participant"] == "chatgpt"
    assert claim["branch"] == "feature"
    assert claim["worktree"] == str(repo.resolve())
    assert claim["base_sha"] == head
    assert claim["resource_id"] == "runtime:provenance"
    assert claim["paths"] == ["gateway/**"]

    status = _run(repo, cli_env, "status", "--json")
    assert status.returncode == 0, status.stderr
    row = json.loads(status.stdout)["claims"][0]
    assert row["agent"] == "chatgpt"
    assert row["semantic_scope"] == "runtime:provenance"
    assert row["task_or_pr"] == "KX-COORD-01"
    assert row["base"] == head
    assert row["worktree"] == str(repo.resolve())
    assert row["state"] == "active"


def test_conflict_is_nonzero_and_names_holding_session(
    repo: Path, cli_env: dict[str, str]
) -> None:
    assert _claim(repo, cli_env).returncode == 0
    contender = {**cli_env, "KITTY_AGENT_SESSION_ID": "session-two"}
    result = _claim(repo, contender)
    assert result.returncode != 0
    assert "CONFLICT" in result.stderr
    assert "session-one" in result.stderr
    assert "OWN" in result.stderr
    assert "feature" in result.stderr
    assert "expires" in result.stderr.lower()


def test_renew_and_release_use_current_session(
    repo: Path, cli_env: dict[str, str]
) -> None:
    assert _claim(repo, cli_env).returncode == 0
    renewed = _run(repo, cli_env, "renew", "--json")
    assert renewed.returncode == 0, renewed.stderr
    assert json.loads(renewed.stdout)["renewed"] == 1

    released = _run(repo, cli_env, "release", "--json")
    assert released.returncode == 0, released.stderr
    assert json.loads(released.stdout)["released"] == 1
    status = _run(repo, cli_env, "status", "--json")
    assert json.loads(status.stdout)["claims"][0]["state"] == "released"


def test_force_release_targets_session_and_frees_resource(
    repo: Path, cli_env: dict[str, str]
) -> None:
    assert _claim(repo, cli_env).returncode == 0
    operator = {**cli_env, "KITTY_AGENT_SESSION_ID": "operator-session"}
    forced = _run(
        repo,
        operator,
        "force-release",
        "--session",
        "session-one",
        "--reason",
        "owner disappeared",
        "--json",
    )
    assert forced.returncode == 0, forced.stderr
    assert json.loads(forced.stdout)["released"] == 1
    contender = {**cli_env, "KITTY_AGENT_SESSION_ID": "session-two"}
    assert _claim(repo, contender).returncode == 0


def test_human_status_has_required_columns(repo: Path, cli_env: dict[str, str]) -> None:
    assert _claim(repo, cli_env).returncode == 0
    result = _run(repo, cli_env, "status")
    assert result.returncode == 0, result.stderr
    for heading in (
        "Agent", "Role", "Lane", "Task/PR", "Semantic scope",
        "Paths", "Base", "Worktree", "Lease", "State",
    ):
        assert heading in result.stdout


def test_release_retires_worktree_session_binding(repo: Path, cli_env: dict[str, str]) -> None:
    env = {k: v for k, v in cli_env.items() if k != "KITTY_AGENT_SESSION_ID"}
    first = _claim(repo, env)
    assert first.returncode == 0, first.stderr
    first_session = json.loads(first.stdout)["claim"]["session_id"]
    released = _run(repo, env, "release", "--json")
    assert released.returncode == 0, released.stderr
    second = _claim(repo, env)
    assert second.returncode == 0, second.stderr
    second_session = json.loads(second.stdout)["claim"]["session_id"]
    assert second_session != first_session


def _seed_rename(repo: Path) -> None:
    (repo / "a").mkdir()
    (repo / "b").mkdir()
    (repo / "a" / "file.txt").write_text("source\n", encoding="utf-8")
    (repo / "b" / ".keep").write_text("keep\n", encoding="utf-8")
    _git(repo, "add", "a", "b")
    _git(repo, "commit", "-qm", "seed rename paths")
    _git(repo, "mv", "a/file.txt", "b/file.txt")


def test_preflight_rename_requires_source_and_destination_resources(
    repo: Path, cli_env: dict[str, str]
) -> None:
    _seed_rename(repo)
    claim = _run(
        repo, cli_env, "claim", "--resource", "dest:files", "--role", "INTEGRATE",
        "--paths", "a/**,b/**", "--json",
    )
    assert claim.returncode == 0, claim.stderr
    result = _run(repo, cli_env, "preflight", "--staged", "--json")
    assert result.returncode != 0
    assert "source:files" in result.stderr


def test_preflight_rename_passes_when_both_resources_are_owned(
    repo: Path, cli_env: dict[str, str]
) -> None:
    _seed_rename(repo)
    for resource in ("source:files", "dest:files"):
        claim = _run(
            repo, cli_env, "claim", "--resource", resource, "--role", "INTEGRATE",
            "--paths", "a/**,b/**", "--json",
        )
        assert claim.returncode == 0, claim.stderr
    result = _run(repo, cli_env, "preflight", "--staged", "--json")
    assert result.returncode == 0, result.stderr


def test_expired_binding_rotates_before_new_claim(repo: Path, cli_env: dict[str, str]) -> None:
    env = {k: v for k, v in cli_env.items() if k != "KITTY_AGENT_SESSION_ID"}
    first = _claim(repo, env)
    assert first.returncode == 0, first.stderr
    first_session = json.loads(first.stdout)["claim"]["session_id"]
    with sqlite3.connect(repo / ".kitty-coordination.db") as conn:
        conn.execute(
            "UPDATE claims SET expires_at='2000-01-01T00:00:00+00:00' "
            "WHERE session_id=? AND state='active'",
            (first_session,),
        )
        conn.commit()
    second = _claim(repo, env)
    assert second.returncode == 0, second.stderr
    second_session = json.loads(second.stdout)["claim"]["session_id"]
    assert second_session != first_session
