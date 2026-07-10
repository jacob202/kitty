"""KB-S4 — operator-gated branch push and PR create/update.

Shadow workers never gain GitHub credentials. This module is the only
publish surface: it runs under the operator CLI with host git/gh auth,
never force-pushes, and never merges.
"""

from __future__ import annotations

import json
import logging
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
    env = dict(__import__("os").environ)
    # gh must use keyring auth, never an ambient/stale token inherited by the
    # worker process (repo AGENTS.md requirement).
    env.pop("GITHUB_TOKEN", None)
    env.pop("GH_TOKEN", None)
    return subprocess.run(
        args,
        cwd=str(cwd) if cwd is not None else None,
        capture_output=True,
        text=True,
        check=check,
        timeout=120,
        env=env,
    )


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
