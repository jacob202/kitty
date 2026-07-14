"""Tests for gateway/builder_loop.py — KB-S3b bounded repair loop.

Integration-style: real git repo, real run_worker executions with tiny shell
workers that write (or fail to write) contract files. No LLMs, no network.
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

INITIATIVE = "loop-test"
PACKET = "LP-1"

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


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


def _apply(db_path: Path, *, max_attempts: int = 2,
           validation_commands: list[str] | None = None) -> str:
    """Apply a one-packet manifest; returns the packet's task_id."""
    manifest = {
        "manifest_version": 1,
        "initiative_id": INITIATIVE,
        "title": "Loop test",
        "packets": [
            {
                "id": PACKET,
                "title": "Loop packet",
                "objective": "Produce done.txt.",
                "acceptance_criteria": ["done.txt exists"],
                "allowed_paths": ["done.txt"],
                "policy": {"max_attempts": max_attempts},
                "validation_commands":
                    validation_commands
                    if validation_commands is not None
                    else ["test -f done.txt"],
            }
        ],
    }
    result = bi.apply_manifest(manifest, db_path=db_path)
    return result["packets"][0]["task_id"]


_GOOD_IMPL = json.dumps(
    {"contract_version": 1, "status": "completed", "summary": "did it"}
)
_APPROVE = json.dumps(
    {"contract_version": 1, "verdict": "approve", "summary": "fine"}
)


def _script(tmp_path: Path, name: str, body: str) -> list[str]:
    path = tmp_path / name
    path.write_text("#!/bin/bash\nset -e\n" + body, encoding="utf-8")
    path.chmod(0o755)
    return ["bash", str(path)]


def _good_worker(tmp_path: Path) -> list[str]:
    return _script(
        tmp_path,
        "worker.sh",
        f"echo ok > done.txt\ncat > \"$KB_RESULT_PATH\" <<'EOF'\n{_GOOD_IMPL}\nEOF\n",
    )


def _approve_reviewer(tmp_path: Path) -> list[str]:
    # Enforce the same required-env contract as
    # scripts/kittybuilder_opencode_reviewer.sh so a wiring regression in
    # _run_review_command's env_extra fails loudly in every reviewer test.
    return _script(
        tmp_path,
        "reviewer.sh",
        ': "${KB_TASK_ID:?KB_TASK_ID is required}"\n'
        ': "${KB_ATTEMPT_ID:?KB_ATTEMPT_ID is required}"\n'
        ': "${KB_CONTEXT_MANIFEST_PATH:?KB_CONTEXT_MANIFEST_PATH is required}"\n'
        f"cat > \"$KB_REVIEW_RESULT_PATH\" <<'EOF'\n{_APPROVE}\nEOF\n",
    )


# ---------------------------------------------------------------------------
# Loop behavior
# ---------------------------------------------------------------------------


class TestRunPacket:
    def test_success_first_attempt(self, repo: Path, db_path: Path, tmp_path: Path):
        task_id = _apply(db_path)
        result = bl.run_packet(
            INITIATIVE, PACKET,
            worker_command=_good_worker(tmp_path),
            review_command=_approve_reviewer(tmp_path),
            repo_root=repo, db_path=db_path,
        )
        assert result["outcome"] == "succeeded"
        assert len(result["attempts"]) == 1
        entry = result["attempts"][0]
        assert entry["implementation_status"] == "completed"
        assert entry["validation_status"] == "passed"
        assert entry["review_verdict"] == "approve"
        manifest_path = Path(entry["manifest_path"])
        assert manifest_path.parts[-4:-1] == ("attempts", task_id, "1")
        manifest = json.loads((manifest_path).read_text())
        assert manifest["outcome"] == "succeeded"
        assert manifest["worker_run"]["run_id"] == entry["run_id"]
        assert manifest["bundle_sha256"]
        assert manifest["validation"]["commands"][0]["command_sha256"]
        assert "output_tail" not in manifest["validation"]["commands"][0]
        assert manifest["review"]["summary"]["sha256"]
        assert "fine" not in json.dumps(manifest)
        assert entry["worktree_cleanup"] == "removed"
        assert not (repo / ".worktrees" / "kittybuilder" / task_id).exists()

        attempt = ba.get_attempt(entry["attempt_id"], db_path=db_path)
        assert attempt["outcome"] == "succeeded"
        assert attempt["implementation"]["summary"] == "did it"
        assert attempt["review"]["verdict"] == "approve"
        # Shadow mode: the task ends blocked for the operator/KB-S4.
        assert bq.get_task(task_id, db_path=db_path)["state"] == bq.BLOCKED

    def test_validation_only_when_no_reviewer(
        self, repo: Path, db_path: Path, tmp_path: Path
    ):
        _apply(db_path)
        result = bl.run_packet(
            INITIATIVE, PACKET,
            worker_command=_good_worker(tmp_path),
            repo_root=repo, db_path=db_path,
        )
        assert result["outcome"] == "succeeded"
        assert "review_verdict" not in result["attempts"][0]
        assert result["attempts"][0]["worktree_cleanup"] == "removed"

    def test_success_without_done_marker_keeps_worktree_for_inspection(
        self, repo: Path, db_path: Path, tmp_path: Path
    ):
        _apply(db_path, validation_commands=[])
        worker = _script(
            tmp_path,
            "no_marker.sh",
            f"cat > \"$KB_RESULT_PATH\" <<'EOF'\n{_GOOD_IMPL}\nEOF\n",
        )

        result = bl.run_packet(
            INITIATIVE, PACKET,
            worker_command=worker,
            repo_root=repo, db_path=db_path,
        )

        task_id = result["task_id"]
        assert result["outcome"] == "succeeded"
        assert result["attempts"][0]["worktree_cleanup"] == "kept_no_done_marker"
        assert (repo / ".worktrees" / "kittybuilder" / task_id).exists()

    def test_repair_retry_then_success(
        self, repo: Path, db_path: Path, tmp_path: Path
    ):
        """First attempt fails validation; the loop retries and succeeds."""
        _apply(db_path)
        marker = tmp_path / "second_try_marker"
        worker = _script(
            tmp_path,
            "flaky.sh",
            (
                f"if [ -f \"{marker}\" ]; then echo ok > done.txt; fi\n"
                f"touch \"{marker}\"\n"
                f"cat > \"$KB_RESULT_PATH\" <<'EOF'\n{_GOOD_IMPL}\nEOF\n"
            ),
        )
        result = bl.run_packet(
            INITIATIVE, PACKET,
            worker_command=worker,
            repo_root=repo, db_path=db_path,
        )
        assert result["outcome"] == "succeeded"
        assert [e["outcome"] for e in result["attempts"]] == ["failed", "succeeded"]
        assert result["attempts"][0]["failure"] == "deterministic validation failed"
        # Second attempt's bundle carried the first attempt's digest.
        second = ba.get_attempt(result["attempts"][1]["attempt_id"], db_path=db_path)
        assert second["bundle"]["prior_attempts"][0]["outcome"] == "failed"

    def test_budget_exhaustion_leaves_task_blocked(
        self, repo: Path, db_path: Path, tmp_path: Path
    ):
        task_id = _apply(db_path, max_attempts=2)
        worker = _script(
            tmp_path,
            "alwaysfail.sh",
            f"cat > \"$KB_RESULT_PATH\" <<'EOF'\n{_GOOD_IMPL}\nEOF\n",
        )  # never creates done.txt → validation always fails
        result = bl.run_packet(
            INITIATIVE, PACKET,
            worker_command=worker,
            repo_root=repo, db_path=db_path,
        )
        assert result["outcome"] == "exhausted"
        assert "2/2" in result["reason"]
        assert [e["outcome"] for e in result["attempts"]] == ["failed", "failed"]
        assert bq.get_task(task_id, db_path=db_path)["state"] == bq.BLOCKED

    def test_missing_result_file_fails_attempt(
        self, repo: Path, db_path: Path, tmp_path: Path
    ):
        _apply(db_path, max_attempts=1)
        worker = _script(tmp_path, "silent.sh", "echo ok > done.txt\n")
        result = bl.run_packet(
            INITIATIVE, PACKET,
            worker_command=worker,
            repo_root=repo, db_path=db_path,
        )
        assert result["outcome"] == "exhausted"
        assert "did not write" in result["attempts"][0]["failure"]
        task_id = result["task_id"]
        assert (repo / ".worktrees" / "kittybuilder" / task_id).exists()

    def test_invalid_contract_fails_attempt_and_stores_nothing(
        self, repo: Path, db_path: Path, tmp_path: Path
    ):
        _apply(db_path, max_attempts=1)
        worker = _script(
            tmp_path,
            "badcontract.sh",
            "echo '{\"status\": \"shipped\"}' > \"$KB_RESULT_PATH\"\n",
        )
        result = bl.run_packet(
            INITIATIVE, PACKET,
            worker_command=worker,
            repo_root=repo, db_path=db_path,
        )
        assert result["outcome"] == "exhausted"
        entry = result["attempts"][0]
        assert "contract invalid" in entry["failure"]
        attempt = ba.get_attempt(entry["attempt_id"], db_path=db_path)
        assert attempt["implementation"] is None

    def test_review_rejection_fails_attempt(
        self, repo: Path, db_path: Path, tmp_path: Path
    ):
        _apply(db_path, max_attempts=1)
        reviewer = _script(
            tmp_path,
            "reject.sh",
            "cat > \"$KB_REVIEW_RESULT_PATH\" <<'EOF'\n"
            + json.dumps(
                {
                    "contract_version": 1,
                    "verdict": "request_changes",
                    "summary": "not enough",
                }
            )
            + "\nEOF\n",
        )
        result = bl.run_packet(
            INITIATIVE, PACKET,
            worker_command=_good_worker(tmp_path),
            review_command=reviewer,
            repo_root=repo, db_path=db_path,
        )
        assert result["outcome"] == "exhausted"
        assert "request_changes" in result["attempts"][0]["failure"]

    def test_refuses_non_queued_task(self, repo: Path, db_path: Path, tmp_path: Path):
        task_id = _apply(db_path)
        bq.claim_task(task_id, "someone-else", db_path=db_path)
        with pytest.raises(bl.LoopError, match="claimed"):
            bl.run_packet(
                INITIATIVE, PACKET,
                worker_command=_good_worker(tmp_path),
                repo_root=repo, db_path=db_path,
            )

    def test_runner_error_is_recorded_before_re_raising(
        self, repo: Path, db_path: Path, tmp_path: Path, monkeypatch
    ):
        task_id = _apply(db_path)

        def fail_runner(*args, **kwargs):
            raise RuntimeError("runner exploded")

        monkeypatch.setattr(bl, "run_worker", fail_runner)
        with pytest.raises(RuntimeError, match="runner exploded"):
            bl.run_packet(
                INITIATIVE, PACKET,
                worker_command=_good_worker(tmp_path),
                repo_root=repo, db_path=db_path,
            )

        attempt = ba.get_attempt(1, db_path=db_path)
        assert attempt is not None
        assert attempt["outcome"] == ba.ATTEMPT_FAILED
        manifest_path = db_path.parent / "attempts" / task_id / "1" / "run-manifest.json"
        manifest = json.loads(manifest_path.read_text())
        assert manifest["outcome"] == "failed"
        assert manifest["failure"]["sha256"]
        assert "runner exploded" not in json.dumps(manifest)

    def test_extra_env_cannot_override_credential_isolation(self, db_path: Path):
        from gateway.builder_runner import run_worker

        _apply(db_path)
        with pytest.raises(ValueError, match="credential isolation"):
            run_worker(
                "kb_whatever_0000",
                ["true"],
                extra_env={"GITHUB_TOKEN": "sneaky"},
                db_path=db_path,
            )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


class TestCli:
    def test_run_packet_cli(
        self, repo: Path, db_path: Path, tmp_path: Path, capsys, monkeypatch
    ):
        from gateway import builder_loop
        from gateway.builder_cli import main

        monkeypatch.setattr(bq, "BUILDER_QUEUE_DB", db_path)
        _apply(db_path)

        # Route the loop at the test repo without threading a CLI flag through.
        real_run_packet = builder_loop.run_packet

        def patched(*args, **kwargs):
            kwargs["repo_root"] = repo
            return real_run_packet(*args, **kwargs)

        monkeypatch.setattr(builder_loop, "run_packet", patched)

        worker = _good_worker(tmp_path)
        assert main(
            ["initiative", "run-packet", INITIATIVE, PACKET,
             "--worker-command", json.dumps(worker)]
        ) == 0
        out = capsys.readouterr().out
        assert "succeeded" in out

    def test_run_packet_cli_rejects_bad_command_json(self, capsys):
        from gateway.builder_cli import main

        assert main(
            ["initiative", "run-packet", INITIATIVE, PACKET,
             "--worker-command", "not-json"]
        ) == 1
        assert "error" in capsys.readouterr().err
