"""Regression tests for publication infrastructure failure classification."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from gateway import builder_attempt as ba
from gateway import builder_initiative as bi
from gateway import builder_loop as bl
from gateway import builder_queue as bq

INITIATIVE = "publication-infra"
PACKET = "PI-1"
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
    (root / "README.md").write_text("hello\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=root, check=True)
    return root


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "kittybuilder" / "builder_queue.db"
    ba.init_db(path)
    return path


def _apply(db_path: Path, repo: Path) -> str:
    result = bi.apply_manifest(
        {
            "manifest_version": 1,
            "initiative_id": INITIATIVE,
            "title": "Publication infrastructure",
            "packets": [
                {
                    "id": PACKET,
                    "title": "Prove infrastructure classification",
                    "objective": "Produce done.txt.",
                    "acceptance_criteria": ["done.txt exists"],
                    "allowed_paths": ["done.txt"],
                    "policy": {"max_attempts": 1},
                    "validation_commands": ["test -f done.txt"],
                }
            ],
        },
        db_path=db_path,
        repo_root=repo,
    )
    return str(result["packets"][0]["task_id"])


def _worker(tmp_path: Path, marker: Path | None = None) -> list[str]:
    script = tmp_path / "worker.sh"
    marker_line = f"echo ran > {marker!s}\n" if marker is not None else ""
    script.write_text(
        "#!/bin/bash\nset -e\n"
        + marker_line
        + "echo ok > done.txt\n"
        + f"cat > \"$KB_RESULT_PATH\" <<'EOF'\n{_GOOD_IMPL}\nEOF\n",
        encoding="utf-8",
    )
    script.chmod(0o755)
    return ["bash", str(script)]


def _install_gate(repo: Path, body: str) -> None:
    hook = repo / "scripts" / "hooks" / "pre-push"
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text("#!/bin/bash\nset -e\n" + body, encoding="utf-8")
    hook.chmod(0o755)
    subprocess.run(["git", "add", str(hook.relative_to(repo))], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "test gate"], cwd=repo, check=True)


def _stub_janitor(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        bl.bj,
        "apply_safe_repairs",
        lambda worktree, allowed_paths=None, commit_marker=None: {
            "changed": False,
            "changed_paths": [],
            "commit_sha": None,
            "ruff_exit_code": 0,
        },
    )


def test_publication_environment_preflight_stops_before_attempt(
    repo: Path, db_path: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_gate(
        repo,
        'if [[ "${1:-}" == "--preflight" ]]; then echo "missing publication dependency" >&2; exit 75; fi\nexit 0\n',
    )
    task_id = _apply(db_path, repo)
    marker = tmp_path / "worker-ran"
    _stub_janitor(monkeypatch)

    result = bl.run_packet(
        INITIATIVE,
        PACKET,
        worker_command=_worker(tmp_path, marker),
        repo_root=repo,
        db_path=db_path,
        publication_preflight=True,
    )

    assert result["outcome"] == bl.LOOP_INFRASTRUCTURE_BLOCKED
    assert ba.list_attempts(INITIATIVE, PACKET, db_path=db_path) == []
    assert not marker.exists(), "worker must not run when publication environment is unavailable"
    assert bq.get_task(task_id, db_path=db_path)["state"] == bq.QUEUED
    infra = [
        event
        for event in bq.list_events(task_id, db_path=db_path)
        if event["type"] == "infrastructure_failed"
    ]
    assert len(infra) == 1
    assert infra[0]["payload"]["phase"] == "publication_preflight"
    assert infra[0]["payload"]["counts_toward_budget"] is False


def test_late_publication_infrastructure_failure_is_crashed_not_failed(
    repo: Path, db_path: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_gate(
        repo,
        'if [[ "${1:-}" == "--preflight" ]]; then exit 0; fi\necho "publication network unavailable" >&2\nexit 75\n',
    )
    task_id = _apply(db_path, repo)
    _stub_janitor(monkeypatch)

    result = bl.run_packet(
        INITIATIVE,
        PACKET,
        worker_command=_worker(tmp_path),
        repo_root=repo,
        db_path=db_path,
        publication_preflight=True,
    )

    assert result["outcome"] == bl.LOOP_INFRASTRUCTURE_BLOCKED
    attempts = ba.list_attempts(INITIATIVE, PACKET, db_path=db_path)
    assert [attempt["outcome"] for attempt in attempts] == [ba.ATTEMPT_CRASHED]
    assert bq.get_task(task_id, db_path=db_path)["state"] == bq.QUEUED
    infra = [
        event
        for event in bq.list_events(task_id, db_path=db_path)
        if event["type"] == "infrastructure_failed"
    ]
    assert len(infra) == 1
    assert infra[0]["payload"]["phase"] == "publication_gate"
    assert infra[0]["payload"]["counts_toward_budget"] is False

    # max_attempts=1, but a crashed infrastructure attempt must leave the one
    # real implementation-failure budget slot available.
    second = ba.start_attempt(INITIATIVE, PACKET, db_path=db_path)
    assert second["attempt_no"] == 2
