"""KB-S4 — operator-gated branch push and PR create/update.

Shadow workers never gain GitHub credentials. This module is the only
publish surface: it runs under the operator CLI with host git/gh auth,
never force-pushes, and — as of CP-06 — merges only behind the evidence
gate in ``merge_and_verify`` (owner decision 2026-07-21, ADR 0018):
declared validation green + reviewer approve + scope clean, with an
automatic post-merge revalidation and revert on red. See
``docs/plans/KITTYBUILDER_DAILY_DRIVER_PLAN.md`` §4.1 for the rails.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Callable

from gateway import builder_queue as bq
from gateway.builder_brief import default_branch_name
from gateway.builder_runner import worktree_path

logger = logging.getLogger("kitty.builder_publish")

RunCmd = Callable[..., subprocess.CompletedProcess[str]]


class PublishError(RuntimeError):
    """Raised when a publish precondition fails or git/gh return an error."""


def _default_run(
    args: list[str],
    *,
    cwd: Path | None = None,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    # gh must use keyring auth, never an ambient/stale token inherited by the
    # worker process (repo AGENTS.md requirement).
    env.pop("GITHUB_TOKEN", None)
    env.pop("GH_TOKEN", None)
    try:
        return subprocess.run(
            args,
            cwd=str(cwd) if cwd is not None else None,
            capture_output=True,
            text=True,
            check=check,
            timeout=120,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        raise PublishError(f"command timed out after 120s: {args!r}") from exc
    except OSError as exc:
        raise PublishError(f"command failed to launch {args!r}: {exc}") from exc


def _require_task(task_id: str, db_path: Path | None) -> dict[str, Any]:
    task = bq.get_task(task_id, db_path=db_path)
    if task is None:
        raise bq.TaskNotFoundError(f"task not found: {task_id}")
    return task


def _assert_publishable_state(task: dict[str, Any]) -> None:
    state = str(task["state"])
    allowed = {
        bq.BLOCKED,
        bq.RUNNING,
        bq.PR_OPENED,
        bq.AWAITING_REVIEW,
    }
    if state not in allowed:
        raise PublishError(
            f"task state {state!r} cannot be published "
            f"(need one of {sorted(allowed)})"
        )
    if state in {bq.BLOCKED, bq.RUNNING}:
        report = task.get("final_report")
        if not isinstance(report, dict):
            raw = task.get("final_report_json")
            if isinstance(raw, str) and raw.strip():
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError as exc:
                    raise PublishError(
                        f"task {task['id']} has invalid final report JSON: {exc}"
                    ) from exc
                report = parsed
        if not isinstance(report, dict) or not report:
            raise PublishError(
                f"task {task['id']} has no completed shadow final report"
            )
        outcome = report.get("outcome")
        if outcome in {
            bq.RUN_FAILED,
            bq.RUN_TIMEOUT,
            bq.RUN_CANCELLED,
            bq.RUN_SCOPE_VIOLATION,
            bq.RUN_LEASE_LOST,
        }:
            raise PublishError(
                f"task {task['id']} shadow run is not publishable: {outcome}"
            )
        if report.get("scope_violations"):
            raise PublishError(
                f"task {task['id']} shadow run reported scope violations"
            )


def _worktree_ready(
    task_id: str,
    branch: str,
    repo_root: Path | None,
    run_cmd: RunCmd,
) -> Path:
    path = worktree_path(task_id, repo_root=repo_root)
    if not path.is_dir():
        raise PublishError(
            f"worktree missing at {path}; run a worker or ensure_worktree first"
        )
    head = run_cmd(
        ["git", "symbolic-ref", "--quiet", "--short", "HEAD"], cwd=path
    )
    current = head.stdout.strip()
    if head.returncode != 0 or current != branch:
        raise PublishError(
            f"worktree {path} is on {current or 'detached HEAD'!r}, "
            f"expected branch {branch!r}"
        )
    status = run_cmd(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=path,
    )
    if status.returncode != 0:
        raise PublishError(f"git status failed in {path}: {status.stderr.strip()}")
    if status.stdout.strip():
        raise PublishError(
            f"worktree {path} is dirty; commit or discard local changes before push"
        )
    return path


def _push_branch(
    path: Path,
    branch: str,
    *,
    remote: str,
    dry_run: bool,
    run_cmd: RunCmd,
) -> dict[str, Any]:
    args = ["git", "push", "-u", remote, f"HEAD:refs/heads/{branch}"]
    if dry_run:
        return {"command": args, "dry_run": True, "stdout": "", "stderr": ""}
    result = run_cmd(args, cwd=path, check=False)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip() or "no output"
        raise PublishError(
            f"git push failed (exit {result.returncode}): {detail}"
        )
    return {
        "command": args,
        "dry_run": False,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def _existing_pr_number(
    branch: str,
    *,
    base: str,
    cwd: Path,
    run_cmd: RunCmd,
) -> int | None:
    result = run_cmd(
        [
            "gh",
            "pr",
            "list",
            "--head",
            branch,
            "--base",
            base,
            "--json",
            "number,url",
            "--limit",
            "1",
        ],
        cwd=cwd,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise PublishError(f"gh pr list failed: {detail}")
    try:
        rows = json.loads(result.stdout or "[]")
    except json.JSONDecodeError as exc:
        raise PublishError(f"gh pr list returned non-JSON: {result.stdout!r}") from exc
    if not rows:
        return None
    number = rows[0].get("number")
    if not isinstance(number, int) or number <= 0:
        raise PublishError(f"gh pr list returned invalid number: {rows[0]!r}")
    return number


def _pr_body(task: dict[str, Any]) -> str:
    report: Any = task.get("final_report")
    if not isinstance(report, dict):
        raw = task.get("final_report_json")
        if isinstance(raw, str) and raw.strip():
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, dict):
                report = parsed
    if isinstance(report, dict) and report:
        body = (
            f"## KittyBuilder task `{task['id']}`\n\n"
            f"**Title:** {task['title']}\n\n"
            f"## Final report\n\n```json\n"
            f"{json.dumps(report, indent=2, default=str)}\n```\n"
        )
    else:
        body = (
            f"## KittyBuilder task `{task['id']}`\n\n"
            f"**Title:** {task['title']}\n\n"
            f"_No final_report_json on the task yet._\n"
        )
    if task.get("description"):
        body = f"{body}\n## Description\n\n{task['description']}\n"
    return body


def _open_or_update_pr(
    *,
    branch: str,
    base: str,
    title: str,
    body: str,
    dry_run: bool,
    cwd: Path,
    run_cmd: RunCmd,
) -> dict[str, Any]:
    existing = None if dry_run else _existing_pr_number(
        branch, base=base, cwd=cwd, run_cmd=run_cmd
    )
    if existing is None:
        args = [
            "gh",
            "pr",
            "create",
            "--head",
            branch,
            "--base",
            base,
            "--title",
            title,
            "--body",
            body,
        ]
        if dry_run:
            return {
                "action": "create",
                "command": args,
                "dry_run": True,
                "pr_number": None,
                "pr_url": None,
            }
        result = run_cmd(args, cwd=cwd, check=False)
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            raise PublishError(f"gh pr create failed: {detail}")
        url = (result.stdout or "").strip().splitlines()[-1] if result.stdout else ""
        pr_number = _pr_number_from_url(url) or _existing_pr_number(
            branch, base=base, cwd=cwd, run_cmd=run_cmd
        )
        if pr_number is None:
            raise PublishError(
                f"gh pr create succeeded but PR number could not be parsed "
                f"from output {result.stdout!r}"
            )
        return {
            "action": "create",
            "command": args[:8] + ["--body", "<omitted>"],
            "dry_run": False,
            "pr_number": pr_number,
            "pr_url": url or None,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }

    args = ["gh", "pr", "edit", str(existing), "--title", title, "--body", body]
    if dry_run:
        return {
            "action": "update",
            "command": args,
            "dry_run": True,
            "pr_number": existing,
            "pr_url": None,
        }
    result = run_cmd(args, cwd=cwd, check=False)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise PublishError(f"gh pr edit failed: {detail}")
    view = run_cmd(
        ["gh", "pr", "view", str(existing), "--json", "url"],
        cwd=cwd,
        check=False,
    )
    edited_url: str | None = None
    if view.returncode == 0:
        try:
            parsed = json.loads(view.stdout).get("url")
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, str):
            edited_url = parsed
    return {
        "action": "update",
        "command": ["gh", "pr", "edit", str(existing), "--title", title, "--body", "<omitted>"],
        "dry_run": False,
        "pr_number": existing,
        "pr_url": edited_url,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


_PR_URL_RE = re.compile(r"/pull/(\d+)\s*$")


def _pr_number_from_url(url: str) -> int | None:
    match = _PR_URL_RE.search(url.strip())
    if not match:
        return None
    return int(match.group(1))


def _advance_task_for_pr(
    task_id: str,
    state: str,
    *,
    db_path: Path | None,
    dry_run: bool,
) -> list[str]:
    """Move task toward awaiting_review after a successful publish."""
    if dry_run:
        return []
    transitions: list[str] = []
    current = state
    if current == bq.BLOCKED:
        bq.transition_task(task_id, bq.PR_OPENED, db_path=db_path)
        transitions.append(f"{bq.BLOCKED}->{bq.PR_OPENED}")
        current = bq.PR_OPENED
    elif current == bq.RUNNING:
        bq.transition_task(task_id, bq.PR_OPENED, db_path=db_path)
        transitions.append(f"{bq.RUNNING}->{bq.PR_OPENED}")
        current = bq.PR_OPENED
    if current == bq.PR_OPENED:
        bq.transition_task(task_id, bq.AWAITING_REVIEW, db_path=db_path)
        transitions.append(f"{bq.PR_OPENED}->{bq.AWAITING_REVIEW}")
    return transitions


def publish_task(
    task_id: str,
    *,
    repo_root: Path | None = None,
    db_path: Path | None = None,
    remote: str = "origin",
    base: str = "main",
    title: str | None = None,
    dry_run: bool = False,
    run_cmd: RunCmd | None = None,
) -> dict[str, Any]:
    """Push the task branch and create/update its PR (operator-gated).

    Never force-pushes. Never merges. Updates ``pr_links`` and advances the
    task to ``awaiting_review`` when starting from ``blocked`` or ``running``.
    """
    runner = run_cmd or _default_run
    if remote.strip() == "" or any(ch.isspace() for ch in remote):
        raise PublishError(f"invalid remote name: {remote!r}")
    if base.strip() == "" or any(ch.isspace() for ch in base) or ".." in base:
        raise PublishError(f"invalid base branch: {base!r}")

    task = _require_task(task_id, db_path)
    _assert_publishable_state(task)
    branch = default_branch_name(task)
    pr_title = title or f"kittybuilder: {task['title']}"
    body = _pr_body(task)

    def _run(
        args: list[str],
        *,
        cwd: Path | None = None,
        check: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        return runner(args, cwd=cwd, check=check)

    path = _worktree_ready(task_id, branch, repo_root, _run)
    push_info = _push_branch(
        path, branch, remote=remote, dry_run=dry_run, run_cmd=_run
    )
    pr_info = _open_or_update_pr(
        branch=branch,
        base=base,
        title=pr_title,
        body=body,
        dry_run=dry_run,
        cwd=path,
        run_cmd=_run,
    )

    pr_number = pr_info.get("pr_number")
    link: dict[str, Any] | None = None
    transitions: list[str] = []
    if not dry_run:
        if not isinstance(pr_number, int) or pr_number <= 0:
            raise PublishError("publish produced no PR number")
        head = _run(["git", "rev-parse", "HEAD"], cwd=path, check=False)
        head_sha = head.stdout.strip() if head.returncode == 0 else None
        link = bq.attach_pr(
            task_id,
            pr_number,
            pr_url=pr_info.get("pr_url"),
            head_sha=head_sha,
            db_path=db_path,
        )
        transitions = _advance_task_for_pr(
            task_id, str(task["state"]), db_path=db_path, dry_run=False
        )
        bq.append_event(
            task_id,
            "published",
            payload={
                "branch": branch,
                "remote": remote,
                "base": base,
                "pr_number": pr_number,
                "pr_url": pr_info.get("pr_url"),
                "action": pr_info.get("action"),
                "transitions": transitions,
            },
            db_path=db_path,
        )

    return {
        "task_id": task_id,
        "branch": branch,
        "remote": remote,
        "base": base,
        "title": pr_title,
        "push": push_info,
        "pr": pr_info,
        "pr_link": link,
        "transitions": transitions,
        "dry_run": dry_run,
    }


# ---------------------------------------------------------------------------
# CP-06 — evidence-gated auto-merge + auto-revert (ADR 0018)
# ---------------------------------------------------------------------------

AUTO_MERGE_OUTCOME_EVENT = "auto_merge_outcome"
# "≥2 of the last 10 auto-merges were reverted" — the plan's own tripwire.
# Stateless by design: once an old revert ages out of the window the
# tripwire clears itself, no reset command needed.
TRIPWIRE_WINDOW = 10
TRIPWIRE_THRESHOLD = 2


class MergeError(RuntimeError):
    """Raised when a merge precondition fails or git/gh return an error."""


def _merge_check_worktree_path(repo_root: Path, task_id: str) -> Path:
    # Deliberately separate from the packet's own worktree
    # (.worktrees/kittybuilder/<task_id>) — post-merge revalidation runs
    # against main, not the packet branch, and must never touch a worktree
    # a worker or reviewer might still be inspecting.
    return repo_root / ".worktrees" / "kittybuilder-merge-check" / task_id


def _gh_pr_merge(
    pr_number: int, *, cwd: Path, run_cmd: RunCmd
) -> dict[str, Any]:
    args = ["gh", "pr", "merge", str(pr_number), "--merge", "--delete-branch=false"]
    result = run_cmd(args, cwd=cwd, check=False)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip() or "no output"
        raise MergeError(f"gh pr merge failed (exit {result.returncode}): {detail}")

    view = run_cmd(
        ["gh", "pr", "view", str(pr_number), "--json", "mergeCommit"],
        cwd=cwd,
        check=False,
    )
    merge_commit_sha: str | None = None
    if view.returncode == 0:
        try:
            parsed = json.loads(view.stdout or "{}")
            merge_commit_sha = (parsed.get("mergeCommit") or {}).get("oid")
        except json.JSONDecodeError:
            merge_commit_sha = None
    if not merge_commit_sha:
        raise MergeError(
            f"gh pr merge for #{pr_number} reported success but no merge "
            f"commit sha could be resolved from `gh pr view`"
        )
    return {"merged": True, "pr_number": pr_number, "merge_commit_sha": merge_commit_sha}


def _prepare_main_worktree(
    repo_root: Path, task_id: str, *, remote: str, run_cmd: RunCmd
) -> Path:
    """Ensure a worktree tracking the latest ``<remote>/main`` for revalidation."""
    path = _merge_check_worktree_path(repo_root, task_id)
    fetch = run_cmd(["git", "fetch", remote, "main"], cwd=repo_root, check=False)
    if fetch.returncode != 0:
        detail = (fetch.stderr or fetch.stdout or "").strip()
        raise MergeError(f"git fetch {remote} main failed: {detail}")

    if path.is_dir():
        reset = run_cmd(
            ["git", "reset", "--hard", f"{remote}/main"], cwd=path, check=False
        )
        if reset.returncode != 0:
            detail = (reset.stderr or reset.stdout or "").strip()
            raise MergeError(f"git reset --hard in {path} failed: {detail}")
        return path

    path.parent.mkdir(parents=True, exist_ok=True)
    add = run_cmd(
        ["git", "worktree", "add", "--detach", str(path), f"{remote}/main"],
        cwd=repo_root,
        check=False,
    )
    if add.returncode != 0:
        detail = (add.stderr or add.stdout or "").strip()
        raise MergeError(f"git worktree add {path} failed: {detail}")
    return path


def _revalidate_on_main(
    repo_root: Path,
    task_id: str,
    validation_commands: list[str],
    *,
    remote: str,
    run_cmd: RunCmd,
) -> dict[str, Any]:
    """Re-run the packet's declared validation commands against fresh main.

    Independent of whatever the worktree-scoped validation already claimed —
    this is the evidence gate's own check, on the code that actually landed.
    """
    path = _prepare_main_worktree(repo_root, task_id, remote=remote, run_cmd=run_cmd)
    results: list[dict[str, Any]] = []
    for command in validation_commands:
        result = run_cmd(["bash", "-lc", command], cwd=path, check=False)
        results.append(
            {
                "command": command,
                "exit_code": result.returncode,
                "passed": result.returncode == 0,
                "output_tail": ((result.stdout or "") + (result.stderr or ""))[-2000:],
            }
        )
    passed = all(r["passed"] for r in results) if results else True
    return {"passed": passed, "commands": results, "worktree": str(path)}


def _revert_merge_commit(
    repo_root: Path,
    task_id: str,
    merge_commit_sha: str,
    *,
    remote: str,
    run_cmd: RunCmd,
) -> dict[str, Any]:
    """Revert the merge on ``main`` and push. Archive's rule verbatim: never
    hotfix on main after a red post-merge check — revert immediately."""
    path = _merge_check_worktree_path(repo_root, task_id)
    revert = run_cmd(
        ["git", "revert", "-m", "1", "--no-edit", merge_commit_sha],
        cwd=path,
        check=False,
    )
    if revert.returncode != 0:
        detail = (revert.stderr or revert.stdout or "").strip()
        raise MergeError(f"git revert of {merge_commit_sha} failed: {detail}")

    push = run_cmd(
        ["git", "push", remote, "HEAD:refs/heads/main"], cwd=path, check=False
    )
    if push.returncode != 0:
        detail = (push.stderr or push.stdout or "").strip()
        raise MergeError(f"git push of revert commit failed: {detail}")

    head = run_cmd(["git", "rev-parse", "HEAD"], cwd=path, check=False)
    revert_sha = head.stdout.strip() if head.returncode == 0 else None
    return {"reverted": True, "revert_commit_sha": revert_sha}


def _cleanup_merge_check_worktree(
    repo_root: Path, task_id: str, *, run_cmd: RunCmd
) -> None:
    path = _merge_check_worktree_path(repo_root, task_id)
    run_cmd(["git", "worktree", "remove", "--force", str(path)], cwd=repo_root, check=False)


def _recent_auto_merge_outcomes(
    db_path: Path | None, limit: int = TRIPWIRE_WINDOW
) -> list[str]:
    """Outcomes ("merged"/"reverted") of the last N auto-merge attempts,
    newest first, across *all* tasks — the tripwire is global, not
    per-initiative, per the plan's own wording."""
    conn = bq.connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT payload_json FROM events
            WHERE type = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (AUTO_MERGE_OUTCOME_EVENT, limit),
        ).fetchall()
    finally:
        conn.close()
    outcomes = []
    for row in rows:
        try:
            payload = json.loads(row["payload_json"] or "{}")
        except json.JSONDecodeError:
            payload = {}
        outcome = payload.get("outcome")
        if outcome:
            outcomes.append(outcome)
    return outcomes


def tripwire_active(db_path: Path | None = None) -> bool:
    """True when ≥ TRIPWIRE_THRESHOLD of the last TRIPWIRE_WINDOW auto-merges
    reverted — auto-merge disables itself and degrades to shadow-mode
    (awaiting_review parking) until enough clean merges age the reverts out."""
    recent = _recent_auto_merge_outcomes(db_path)
    return recent.count("reverted") >= TRIPWIRE_THRESHOLD


def merge_and_verify(
    task_id: str,
    *,
    validation_commands: list[str],
    repo_root: Path | None = None,
    db_path: Path | None = None,
    remote: str = "origin",
    run_cmd: RunCmd | None = None,
) -> dict[str, Any]:
    """CP-06 evidence-gated auto-merge: merge the task's PR, revalidate on
    fresh ``main``, auto-revert on red. Never called unless the caller has
    already confirmed the evidence gate (validation green + reviewer
    approve + scope clean) — this function's own job is the merge and the
    post-merge safety net, not re-judging the packet.

    Returns ``outcome`` of ``merged``, ``reverted``, or ``skipped_tripwire``.
    """
    runner = run_cmd or _default_run
    root = _repo_root_or(repo_root)
    _require_task(task_id, db_path)  # existence check only
    pr_links = bq.get_pr_links(task_id, db_path=db_path)
    if not pr_links:
        raise MergeError(f"task {task_id} has no linked PR to merge")
    pr_number = int(pr_links[-1]["pr_number"])

    if tripwire_active(db_path):
        return {
            "outcome": "skipped_tripwire",
            "task_id": task_id,
            "pr_number": pr_number,
        }

    merge_info = _gh_pr_merge(pr_number, cwd=root, run_cmd=runner)
    merge_commit_sha = merge_info["merge_commit_sha"]

    try:
        revalidation = _revalidate_on_main(
            root, task_id, validation_commands, remote=remote, run_cmd=runner
        )
        if revalidation["passed"]:
            bq._mark_pr_merged(task_id, pr_number, db_path)
            bq._promote_merged_task(task_id, db_path)
            bq.append_event(
                task_id,
                AUTO_MERGE_OUTCOME_EVENT,
                payload={
                    "outcome": "merged",
                    "pr_number": pr_number,
                    "merge_commit_sha": merge_commit_sha,
                },
                db_path=db_path,
            )
            return {
                "outcome": "merged",
                "task_id": task_id,
                "pr_number": pr_number,
                "merge_commit_sha": merge_commit_sha,
                "revalidation": revalidation,
            }

        revert_info = _revert_merge_commit(
            root, task_id, merge_commit_sha, remote=remote, run_cmd=runner
        )
        bq.append_event(
            task_id,
            AUTO_MERGE_OUTCOME_EVENT,
            payload={
                "outcome": "reverted",
                "pr_number": pr_number,
                "merge_commit_sha": merge_commit_sha,
                "revert_commit_sha": revert_info.get("revert_commit_sha"),
                "revalidation": revalidation,
            },
            db_path=db_path,
        )
        return {
            "outcome": "reverted",
            "task_id": task_id,
            "pr_number": pr_number,
            "merge_commit_sha": merge_commit_sha,
            "revalidation": revalidation,
            "revert": revert_info,
        }
    finally:
        _cleanup_merge_check_worktree(root, task_id, run_cmd=runner)


def _repo_root_or(repo_root: Path | None) -> Path:
    if repo_root is not None:
        return repo_root
    from gateway.builder_runner import _repo_root

    return _repo_root(None)
