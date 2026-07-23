"""Tests for KB-S4 operator-gated publish (push + PR)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from gateway import builder_publish as bp
from gateway import builder_queue as bq
from gateway.builder_brief import default_branch_name


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    p = tmp_path / "builder_queue.db"
    bq.init_db(p)
    return p


def _make_blocked_task(db_path: Path) -> dict[str, Any]:
    task = bq.create_task("ship me", description="do the thing", db_path=db_path)
    claimed = bq.claim_task(task["id"], "worker", db_path=db_path)
    bq.worker_transition_task(
        task["id"],
        bq.RUNNING,
        lease_token=claimed["lease_token"],
        claim_version=claimed["claim_version"],
        db_path=db_path,
    )
    bq.transition_task(task["id"], bq.BLOCKED, db_path=db_path)
    bq.attach_final_report(
        task["id"],
        {"status": "completed", "summary": "ok"},
        operator_reason="operator post-mortem",
        db_path=db_path,
    )
    return bq.get_task(task["id"], db_path=db_path)


def _init_worktree(tmp_path: Path, task: dict[str, Any]) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "t@example.com"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "t"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    (root / "README").write_text("hi\n")
    subprocess.run(["git", "add", "README"], cwd=root, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init"], cwd=root, check=True, capture_output=True
    )
    branch = default_branch_name(task)
    wt = root / ".worktrees" / "kittybuilder" / task["id"]
    wt.parent.mkdir(parents=True)
    subprocess.run(
        ["git", "worktree", "add", "-b", branch, str(wt)],
        cwd=root,
        check=True,
        capture_output=True,
    )
    return root


class TestPublishTask:
    def test_dry_run_does_not_mutate_or_call_side_effects(
        self, tmp_path: Path, db_path: Path
    ):
        task = _make_blocked_task(db_path)
        root = _init_worktree(tmp_path, task)
        calls: list[list[str]] = []

        def spy(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
            calls.append(list(args))
            # allow readiness checks
            if args[:3] == ["git", "symbolic-ref", "--quiet"]:
                return subprocess.CompletedProcess(
                    args, 0, stdout=default_branch_name(task) + "\n", stderr=""
                )
            if args[:2] == ["git", "status"]:
                return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
            raise AssertionError(f"unexpected call during dry-run: {args}")

        result = bp.publish_task(
            task["id"],
            repo_root=root,
            db_path=db_path,
            dry_run=True,
            run_cmd=spy,
        )
        assert result["dry_run"] is True
        assert result["push"]["dry_run"] is True
        assert "git" in result["push"]["command"] and "push" in result["push"]["command"]
        assert "--force" not in result["push"]["command"]
        assert bq.get_task(task["id"], db_path=db_path)["state"] == bq.BLOCKED
        # only readiness gits
        assert all(c[0] == "git" and c[1] != "push" for c in calls)

    def test_publish_pushes_creates_pr_attaches_and_advances_state(
        self, tmp_path: Path, db_path: Path
    ):
        task = _make_blocked_task(db_path)
        root = _init_worktree(tmp_path, task)
        branch = default_branch_name(task)
        seen: list[list[str]] = []

        def fake(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
            seen.append(list(args))
            if args[:3] == ["git", "symbolic-ref", "--quiet"]:
                return subprocess.CompletedProcess(
                    args, 0, stdout=branch + "\n", stderr=""
                )
            if args[:2] == ["git", "status"]:
                return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
            if args[:2] == ["git", "push"]:
                assert "-u" in args
                assert "--force" not in args
                assert f"HEAD:refs/heads/{branch}" in args
                return subprocess.CompletedProcess(args, 0, stdout="ok\n", stderr="")
            if args[:3] == ["gh", "pr", "list"]:
                return subprocess.CompletedProcess(args, 0, stdout="[]\n", stderr="")
            if args[:3] == ["gh", "pr", "create"]:
                return subprocess.CompletedProcess(
                    args,
                    0,
                    stdout="https://github.com/example/kitty/pull/99\n",
                    stderr="",
                )
            if args[:2] == ["git", "rev-parse"]:
                return subprocess.CompletedProcess(
                    args, 0, stdout="deadbeef\n", stderr=""
                )
            raise AssertionError(f"unexpected command: {args}")

        result = bp.publish_task(
            task["id"],
            repo_root=root,
            db_path=db_path,
            run_cmd=fake,
        )
        assert result["pr"]["action"] == "create"
        assert result["pr"]["pr_number"] == 99
        assert bq.get_task(task["id"], db_path=db_path)["state"] == bq.AWAITING_REVIEW
        links = bq.get_pr_links(task["id"], db_path=db_path)
        assert links[0]["pr_number"] == 99
        assert links[0]["head_sha"] == "deadbeef"
        assert "published" in {
            e["type"] for e in bq.list_events(task["id"], db_path=db_path)
        }

    def test_publish_updates_existing_pr(self, tmp_path: Path, db_path: Path):
        task = _make_blocked_task(db_path)
        root = _init_worktree(tmp_path, task)
        branch = default_branch_name(task)

        def fake(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
            if args[:3] == ["git", "symbolic-ref", "--quiet"]:
                return subprocess.CompletedProcess(
                    args, 0, stdout=branch + "\n", stderr=""
                )
            if args[:2] == ["git", "status"]:
                return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
            if args[:2] == ["git", "push"]:
                return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
            if args[:3] == ["gh", "pr", "list"]:
                return subprocess.CompletedProcess(
                    args,
                    0,
                    stdout=json.dumps([{"number": 7, "url": "u"}]) + "\n",
                    stderr="",
                )
            if args[:3] == ["gh", "pr", "edit"]:
                return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
            if args[:3] == ["gh", "pr", "view"]:
                return subprocess.CompletedProcess(
                    args, 0, stdout=json.dumps({"url": "https://x/pull/7"}), stderr=""
                )
            if args[:2] == ["git", "rev-parse"]:
                return subprocess.CompletedProcess(args, 0, stdout="abc\n", stderr="")
            raise AssertionError(args)

        result = bp.publish_task(
            task["id"], repo_root=root, db_path=db_path, run_cmd=fake
        )
        assert result["pr"]["action"] == "update"
        assert result["pr"]["pr_number"] == 7

    def test_refuses_dirty_worktree(self, tmp_path: Path, db_path: Path):
        task = _make_blocked_task(db_path)
        root = _init_worktree(tmp_path, task)
        branch = default_branch_name(task)

        def dirty(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
            if args[:3] == ["git", "symbolic-ref", "--quiet"]:
                return subprocess.CompletedProcess(
                    args, 0, stdout=branch + "\n", stderr=""
                )
            if args[:2] == ["git", "status"]:
                return subprocess.CompletedProcess(
                    args, 0, stdout=" M file.py\n", stderr=""
                )
            raise AssertionError(args)

        with pytest.raises(bp.PublishError, match="dirty"):
            bp.publish_task(
                task["id"], repo_root=root, db_path=db_path, run_cmd=dirty
            )

    def test_refuses_queued_task(self, db_path: Path):
        task = bq.create_task("nope", db_path=db_path)
        with pytest.raises(bp.PublishError, match="cannot be published"):
            bp.publish_task(task["id"], db_path=db_path, dry_run=True)


# ---------------------------------------------------------------------------
# CP-06 — evidence-gated auto-merge + auto-revert
# ---------------------------------------------------------------------------


def _make_pr_opened_task(db_path: Path, tmp_path: Path, *, pr_number: int = 42) -> dict[str, Any]:
    task = _make_blocked_task(db_path)
    bq.transition_task(task["id"], bq.PR_OPENED, db_path=db_path)
    bq.transition_task(task["id"], bq.AWAITING_REVIEW, db_path=db_path)
    bq.attach_pr(task["id"], pr_number, pr_url=f"https://x/pull/{pr_number}", db_path=db_path)
    return bq.get_task(task["id"], db_path=db_path)


def _merge_stub(*, revalidate_ok: bool = True, merge_commit_sha: str = "deadbeef00"):
    calls: list[list[str]] = []

    def fake(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(list(args))
        if args[:3] == ["gh", "pr", "merge"]:
            return subprocess.CompletedProcess(args, 0, stdout="merged\n", stderr="")
        if args[:3] == ["gh", "pr", "view"]:
            return subprocess.CompletedProcess(
                args, 0,
                stdout=json.dumps({"mergeCommit": {"oid": merge_commit_sha}}),
                stderr="",
            )
        if args[:2] == ["git", "fetch"]:
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
        if args[:3] == ["git", "worktree", "add"]:
            Path(args[4]).mkdir(parents=True, exist_ok=True)
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
        if args[:2] == ["git", "reset"]:
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
        if args[:2] == ["bash", "-lc"]:
            code = 0 if revalidate_ok else 1
            return subprocess.CompletedProcess(args, code, stdout="", stderr="")
        if args[:2] == ["git", "revert"]:
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
        if args[:2] == ["git", "push"]:
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
        if args[:2] == ["git", "rev-parse"]:
            return subprocess.CompletedProcess(args, 0, stdout="revertsha01\n", stderr="")
        if args[:3] == ["git", "worktree", "remove"]:
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
        raise AssertionError(f"unexpected call: {args}")

    return fake, calls


class TestMergeAndVerify:
    def test_merges_and_promotes_on_green_revalidation(self, tmp_path: Path, db_path: Path):
        task = _make_pr_opened_task(db_path, tmp_path)
        fake, calls = _merge_stub(revalidate_ok=True)

        result = bp.merge_and_verify(
            task["id"],
            validation_commands=["true"],
            repo_root=tmp_path,
            db_path=db_path,
            run_cmd=fake,
        )

        assert result["outcome"] == "merged"
        assert result["merge_commit_sha"] == "deadbeef00"
        assert bq.get_task(task["id"], db_path=db_path)["state"] == bq.DONE
        assert any(c[:3] == ["gh", "pr", "merge"] for c in calls)
        assert not any(c[:2] == ["git", "revert"] for c in calls)
        events = {e["type"] for e in bq.list_events(task["id"], db_path=db_path)}
        assert bp.AUTO_MERGE_OUTCOME_EVENT in events

    def test_reverts_and_does_not_promote_on_red_revalidation(self, tmp_path: Path, db_path: Path):
        task = _make_pr_opened_task(db_path, tmp_path)
        fake, calls = _merge_stub(revalidate_ok=False)

        result = bp.merge_and_verify(
            task["id"],
            validation_commands=["false"],
            repo_root=tmp_path,
            db_path=db_path,
            run_cmd=fake,
        )

        assert result["outcome"] == "reverted"
        assert result["revert"]["revert_commit_sha"] == "revertsha01"
        assert bq.get_task(task["id"], db_path=db_path)["state"] != bq.DONE
        assert any(c[:2] == ["git", "revert"] for c in calls)
        assert any(c[:2] == ["git", "push"] for c in calls)
        payloads = [
            e["payload"] for e in bq.list_events(task["id"], db_path=db_path)
            if e["type"] == bp.AUTO_MERGE_OUTCOME_EVENT
        ]
        assert payloads[-1]["outcome"] == "reverted"

    def test_no_validation_commands_treated_as_passed(self, tmp_path: Path, db_path: Path):
        task = _make_pr_opened_task(db_path, tmp_path)
        fake, _ = _merge_stub()

        result = bp.merge_and_verify(
            task["id"], validation_commands=[], repo_root=tmp_path, db_path=db_path, run_cmd=fake,
        )
        assert result["outcome"] == "merged"

    def test_raises_when_no_pr_linked(self, db_path: Path):
        task = _make_blocked_task(db_path)
        with pytest.raises(bp.MergeError, match="no linked PR"):
            bp.merge_and_verify(task["id"], validation_commands=[], db_path=db_path)

    def test_raises_when_gh_merge_fails(self, tmp_path: Path, db_path: Path):
        task = _make_pr_opened_task(db_path, tmp_path)

        def fake(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
            if args[:3] == ["gh", "pr", "merge"]:
                return subprocess.CompletedProcess(args, 1, stdout="", stderr="conflict")
            raise AssertionError(f"unexpected call: {args}")

        with pytest.raises(bp.MergeError, match="gh pr merge failed"):
            bp.merge_and_verify(
                task["id"], validation_commands=[], repo_root=tmp_path, db_path=db_path, run_cmd=fake,
            )
        assert bq.get_task(task["id"], db_path=db_path)["state"] != bq.DONE

    def test_tripwire_skips_merge_after_two_reverts_in_window(self, tmp_path: Path, db_path: Path):
        # Two unrelated prior tasks whose auto-merge reverted.
        for i in range(2):
            other = _make_pr_opened_task(db_path, tmp_path, pr_number=100 + i)
            bq.append_event(
                other["id"], bp.AUTO_MERGE_OUTCOME_EVENT,
                payload={"outcome": "reverted"}, db_path=db_path,
            )

        assert bp.tripwire_active(db_path) is True

        task = _make_pr_opened_task(db_path, tmp_path, pr_number=200)

        def explode(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
            raise AssertionError(f"tripwire should have short-circuited before {args}")

        result = bp.merge_and_verify(
            task["id"], validation_commands=[], repo_root=tmp_path, db_path=db_path, run_cmd=explode,
        )
        assert result["outcome"] == "skipped_tripwire"
        assert bq.get_task(task["id"], db_path=db_path)["state"] != bq.DONE

    def test_tripwire_not_triggered_by_a_single_revert(self, tmp_path: Path, db_path: Path):
        other = _make_pr_opened_task(db_path, tmp_path, pr_number=300)
        bq.append_event(
            other["id"], bp.AUTO_MERGE_OUTCOME_EVENT,
            payload={"outcome": "reverted"}, db_path=db_path,
        )
        assert bp.tripwire_active(db_path) is False
