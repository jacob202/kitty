from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from gateway import builder_attempt as ba
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
    path = tmp_path / "builder" / "queue.db"
    bq.init_db(path)
    bi.init_db(path)
    return path


def _manifest() -> dict:
    return {
        "manifest_version": 1,
        "initiative_id": "preflight-test",
        "title": "Preflight test",
        "packets": [{
            "id": "p1",
            "title": "Packet one",
            "objective": "prove preflight",
            "depends_on": [],
            "acceptance_criteria": ["ready is reported"],
            "allowed_paths": ["README.md"],
            "policy": {"max_attempts": 2},
            "validation_commands": ["test -f README.md"],
        }],
    }


def _apply(repo: Path, db_path: Path, manifest: dict | None = None) -> dict:
    return bi.apply_manifest(manifest or _manifest(), db_path=db_path, repo_root=repo)


def test_ready_free_preflight_is_read_only(repo: Path, db_path: Path, tmp_path: Path) -> None:
    applied = _apply(repo, db_path)
    task_id = applied["packets"][0]["task_id"]
    before_task = bq.get_task(task_id, db_path=db_path)
    before_attempts = ba.list_attempts("preflight-test", "p1", db_path=db_path)

    result = bs.preflight_packet(
        "preflight-test", "p1", db_path=db_path, repo_root=repo,
        ledger_db_path=tmp_path / "compute.db",
    )

    assert result["action"] == "run"
    assert result["route"] == "free"
    assert result["estimated_cost_cad"] == 0.0
    assert "not a provider invoice" in result["cost_basis"]
    assert result["reasons"] == []
    assert bq.get_task(task_id, db_path=db_path)["state"] == before_task["state"]
    assert ba.list_attempts("preflight-test", "p1", db_path=db_path) == before_attempts


def test_stale_base_blocks_without_mutation(repo: Path, db_path: Path, tmp_path: Path) -> None:
    _apply(repo, db_path)
    (repo / "README.md").write_text("new\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "new head"], cwd=repo, check=True)

    result = bs.preflight_packet(
        "preflight-test", "p1", db_path=db_path, repo_root=repo,
        ledger_db_path=tmp_path / "compute.db",
    )

    assert result["action"] == "blocked"
    assert any("stale" in reason.lower() for reason in result["reasons"])
    assert ba.list_attempts("preflight-test", "p1", db_path=db_path) == []


def test_missing_packet_is_refused(repo: Path, db_path: Path, tmp_path: Path) -> None:
    _apply(repo, db_path)
    result = bs.preflight_packet(
        "preflight-test", "missing", db_path=db_path, repo_root=repo,
        ledger_db_path=tmp_path / "compute.db",
    )
    assert result["action"] == "refuse"
    assert "not part" in result["reasons"][0]


def test_missing_validation_commands_blocks(repo: Path, db_path: Path, tmp_path: Path) -> None:
    manifest = _manifest()
    manifest["packets"][0]["validation_commands"] = []
    _apply(repo, db_path, manifest)

    result = bs.preflight_packet(
        "preflight-test", "p1", db_path=db_path, repo_root=repo,
        ledger_db_path=tmp_path / "compute.db",
    )

    assert result["action"] == "blocked"
    assert any("validation commands" in reason.lower() for reason in result["reasons"])
