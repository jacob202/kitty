"""Runtime integration tests for the Builder pre-execution Validate Scope stage.

Exercises the STOP -> Escalate -> Return Control path end to end through
``run_packet`` and the CLI, against a real git repo. No LLMs, no network.

Kept separate from ``test_builder_loop.py`` so the runtime-scope commit does
not inherit the campaign/event test additions that live on other branches.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from gateway import builder_attempt as ba
from gateway import builder_initiative as bi
from gateway import builder_loop as bl
from gateway import builder_queue as bq

INITIATIVE = "scope-rt"
PACKET = "SR-1"


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
    ba.init_db(p)
    return p


def _apply(db_path: Path, *, objective: str, acceptance: list[str],
           allowed_paths: list[str]) -> str:
    """Apply a one-packet manifest; returns the packet's task_id."""
    manifest = {
        "manifest_version": 1,
        "initiative_id": INITIATIVE,
        "title": "Scope runtime test",
        "packets": [
            {
                "id": PACKET,
                "title": "Scope packet",
                "objective": objective,
                "acceptance_criteria": acceptance,
                "allowed_paths": allowed_paths,
                "policy": {"max_attempts": 2},
                "validation_commands": ["test -f done.txt"],
            }
        ],
    }
    result = bi.apply_manifest(manifest, db_path=db_path)
    return result["packets"][0]["task_id"]


def _apply_protected(db_path: Path) -> str:
    """A packet whose scope reaches a protected architecture/governance zone.

    Generic objective, no explicit naming of the protected file. Must escalate
    at execution time, before any worktree or attempt exists.
    """
    return _apply(
        db_path,
        objective="Edit an ADR.",
        acceptance=["adr updated"],
        allowed_paths=["docs/adr/0020-x.md"],
    )


def _good_worker(tmp_path: Path) -> list[str]:
    path = tmp_path / "worker.sh"
    path.write_text(
        "#!/bin/bash\nset -e\necho ok > done.txt\n"
        'cat > "$KB_RESULT_PATH" <<\'EOF\'\n'
        '{"contract_version": 1, "status": "completed", "summary": "did it"}\n'
        "EOF\n",
        encoding="utf-8",
    )
    path.chmod(0o755)
    return ["bash", str(path)]


class TestRunPacket:
    def test_scope_validation_escalates_before_any_attempt(
        self, repo: Path, db_path: Path, tmp_path: Path
    ):
        """A packet requiring architectural judgment escalates and returns
        control without creating a worktree or attempt."""
        task_id = _apply_protected(db_path)
        with pytest.raises(bl.EscalationError):
            bl.run_packet(
                INITIATIVE, PACKET,
                worker_command=_good_worker(tmp_path),
                repo_root=repo, db_path=db_path,
            )
        # No attempt was created; the task is untouched and still queued.
        assert ba.list_attempts(INITIATIVE, PACKET, db_path=db_path) == []
        assert bq.get_task(task_id, db_path=db_path)["state"] == bq.QUEUED
        # No worktree was created.
        assert not (repo / ".worktrees" / "kittybuilder" / task_id).exists()


class TestCli:
    def test_run_packet_cli_escalates_on_protected_scope(
        self, repo: Path, db_path: Path, tmp_path: Path, capsys, monkeypatch
    ):
        from gateway.builder_cli import main

        monkeypatch.setattr(bq, "BUILDER_QUEUE_DB", db_path)
        _apply_protected(db_path)
        real_run_packet = bl.run_packet

        def patched(*args, **kwargs):
            kwargs["repo_root"] = repo
            return real_run_packet(*args, **kwargs)

        monkeypatch.setattr(bl, "run_packet", patched)

        rc = main(
            ["initiative", "run-packet", INITIATIVE, PACKET,
             "--worker-command", json.dumps(_good_worker(tmp_path))]
        )
        assert rc == 1
        err = capsys.readouterr().err
        assert "scope_escalation" in err
