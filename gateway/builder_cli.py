"""Kitty Builder CLI — Layer 1A (coordination only).

Safe commands:
  brief <task>             print the repo brief for a task
  contract validate <path>  check a builder contract file
  queue <subcommand> ...    manage the durable builder queue

Commands intentionally disabled in Layer 1A:
  run, loop, repl, delegate — each prints a clear "not enabled" message.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# JSON argument parsers (strict)
# ---------------------------------------------------------------------------


def _parse_json_array(value: str | None) -> list[str] | None:
    """Parse a JSON array of strings. Returns None if value is None or empty."""
    if value is None:
        return None
    parsed = json.loads(value)
    if not isinstance(parsed, list):
        raise ValueError("value must be a JSON array")
    for item in parsed:
        if not isinstance(item, str):
            raise ValueError("all items in the array must be strings")
    return parsed


def _parse_json_object(value: str | None) -> dict[str, Any] | None:
    """Parse a JSON object. Returns None if value is None or empty."""
    if value is None:
        return None
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise ValueError("value must be a JSON object")
    return parsed


# ---------------------------------------------------------------------------
# Not-enabled handler (preserved from Layer 1A)
# ---------------------------------------------------------------------------


def _cmd_not_enabled(args: argparse.Namespace) -> int:
    print(
        f"'{args.command}' is not enabled in Kitty Builder Layer 1A.",
        file=sys.stderr,
    )
    print(
        "This layer provides coordination-only commands: brief, contract validate, queue.",
        file=sys.stderr,
    )
    return 1


# ---------------------------------------------------------------------------
# Brief
# ---------------------------------------------------------------------------


def _cmd_brief(args: argparse.Namespace) -> int:
    from gateway.brief import build_worker_brief

    packet: dict[str, Any] = {}
    if args.packet:
        packet = json.loads(Path(args.packet).read_text(encoding="utf-8"))
    print(build_worker_brief(" ".join(args.task), packet))
    return 0


# ---------------------------------------------------------------------------
# Contract validate
# ---------------------------------------------------------------------------


def _cmd_contract_validate(args: argparse.Namespace) -> int:
    from gateway.builder_contract import ContractError, load_contract, run_contract

    try:
        spec = load_contract(Path(args.path))
    except ContractError as exc:
        print(f"contract load error: {exc}", file=sys.stderr)
        return 1

    try:
        result = run_contract(spec)
    except ContractError as exc:
        print(f"contract error: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2))
    return 0 if result.get("passed") else 1


# ---------------------------------------------------------------------------
# Queue — add
# ---------------------------------------------------------------------------


def _cmd_queue_add(args: argparse.Namespace) -> int:
    from gateway.builder_queue import create_task

    try:
        acceptance = _parse_json_array(args.acceptance)
        allowed_paths = _parse_json_array(args.allowed_paths)
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    try:
        task = create_task(
            args.title,
            description=args.description,
            acceptance_criteria=acceptance,
            priority=args.priority,
            allowed_paths=allowed_paths,
        )

        if args.json:
            print(json.dumps(task, indent=2, default=str))
        else:
            _print_task_summary(task)
        return 0
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


# ---------------------------------------------------------------------------
# Queue — edit
# ---------------------------------------------------------------------------


def _cmd_queue_edit(args: argparse.Namespace) -> int:
    from gateway.builder_queue import (
        IllegalTransitionError,
        TaskNotFoundError,
        edit_task,
    )

    kwargs: dict[str, Any] = {}

    if args.title is not None:
        kwargs["title"] = args.title
    if args.description is not None:
        kwargs["description"] = args.description
    if args.priority is not None:
        kwargs["priority"] = args.priority
    if args.acceptance is not None:
        try:
            kwargs["acceptance_criteria"] = _parse_json_array(args.acceptance)
        except (json.JSONDecodeError, ValueError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
    if args.allowed_paths is not None:
        try:
            kwargs["allowed_paths"] = _parse_json_array(args.allowed_paths)
        except (json.JSONDecodeError, ValueError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

    try:
        task = edit_task(args.id, **kwargs)
        if args.json:
            print(json.dumps(task, indent=2, default=str))
        else:
            print(f"Edited task {task['id']}")
            _print_task_summary(task)
        return 0
    except (ValueError, TaskNotFoundError, IllegalTransitionError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


# ---------------------------------------------------------------------------
# Queue — list
# ---------------------------------------------------------------------------


def _cmd_queue_list(args: argparse.Namespace) -> int:
    from gateway.builder_queue import list_tasks

    tasks = list_tasks(state=args.state, include_archived=args.include_archived)

    if args.json:
        print(json.dumps(tasks, indent=2, default=str))
    else:
        if not tasks:
            print("No tasks found.")
            return 0
        for t in tasks:
            _print_task_summary(t)
    return 0


# ---------------------------------------------------------------------------
# Queue — show
# ---------------------------------------------------------------------------


def _cmd_queue_show(args: argparse.Namespace) -> int:
    from gateway.builder_queue import get_task

    task = get_task(args.id)
    if task is None:
        print(f"error: task not found: {args.id}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(task, indent=2, default=str))
    else:
        _print_task_summary(task, verbose=True)
    return 0


# ---------------------------------------------------------------------------
# Queue — claim
# ---------------------------------------------------------------------------


def _cmd_queue_claim(args: argparse.Namespace) -> int:
    from gateway.builder_queue import (
        IllegalTransitionError,
        LeaseConflictError,
        TaskNotFoundError,
        claim_task,
    )

    try:
        task = claim_task(
            args.id,
            args.worker,
            lease_seconds=args.lease_seconds,
        )
        if args.json:
            print(json.dumps(task, indent=2, default=str))
        else:
            print(f"Claimed task {task['id']} for {args.worker}")
            _print_task_summary(task)
        return 0
    except (TaskNotFoundError, LeaseConflictError, IllegalTransitionError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


# ---------------------------------------------------------------------------
# Queue — claim-next
# ---------------------------------------------------------------------------


def _cmd_queue_claim_next(args: argparse.Namespace) -> int:
    from gateway.builder_queue import claim_next

    try:
        task = claim_next(
            args.worker,
            lease_seconds=args.lease_seconds,
        )
        if task is None:
            if args.json:
                print(json.dumps({"task": None, "message": "No eligible queued tasks."}))
            else:
                print("No eligible queued tasks.")
            return 1

        if args.json:
            print(json.dumps(task, indent=2, default=str))
        else:
            print(f"Claimed next task {task['id']} for {args.worker}")
            _print_task_summary(task)
        return 0
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


# ---------------------------------------------------------------------------
# Queue — release (worker)
# ---------------------------------------------------------------------------


def _cmd_queue_release(args: argparse.Namespace) -> int:
    from gateway.builder_queue import (
        LeaseConflictError,
        TaskNotFoundError,
        worker_release_task,
    )

    try:
        task = worker_release_task(
            args.id,
            args.lease_token,
            args.claim_version,
        )
        if args.json:
            print(json.dumps(task, indent=2, default=str))
        else:
            print(f"Released task {task['id']}")
            _print_task_summary(task)
        return 0
    except (TaskNotFoundError, LeaseConflictError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


# ---------------------------------------------------------------------------
# Queue — operator-release
# ---------------------------------------------------------------------------


def _cmd_queue_operator_release(args: argparse.Namespace) -> int:
    from gateway.builder_queue import (
        IllegalTransitionError,
        TaskNotFoundError,
        operator_release_task,
    )

    try:
        task = operator_release_task(args.id, reason=args.reason)
        if args.json:
            print(json.dumps(task, indent=2, default=str))
        else:
            print(f"Operator-released task {task['id']}")
            _print_task_summary(task)
        return 0
    except (TaskNotFoundError, IllegalTransitionError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


# ---------------------------------------------------------------------------
# Queue — transition
# ---------------------------------------------------------------------------


def _cmd_queue_transition(args: argparse.Namespace) -> int:
    from gateway.builder_queue import (
        IllegalTransitionError,
        LeaseConflictError,
        TaskNotFoundError,
        worker_transition_task,
    )

    payload: dict[str, Any] | None = None
    if args.payload_json is not None:
        try:
            payload = _parse_json_object(args.payload_json)
        except (json.JSONDecodeError, ValueError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

    try:
        task = worker_transition_task(
            args.id,
            args.state,
            args.lease_token,
            args.claim_version,
            payload=payload,
        )
        if args.json:
            print(json.dumps(task, indent=2, default=str))
        else:
            print(f"Transitioned task {task['id']} to {task['state']}")
            _print_task_summary(task)
        return 0
    except (TaskNotFoundError, LeaseConflictError, IllegalTransitionError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


# ---------------------------------------------------------------------------
# Queue — events
# ---------------------------------------------------------------------------


def _cmd_queue_events(args: argparse.Namespace) -> int:
    from gateway.builder_queue import TaskNotFoundError, list_events

    try:
        events = list_events(args.id)
    except TaskNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(events, indent=2, default=str))
    else:
        if not events:
            print("No events for this task.")
            return 0
        for ev in events:
            ts = ev.get("created_at", "")
            etype = ev.get("type", "")
            payload = ev.get("payload")
            payload_str = f" {json.dumps(payload)}" if payload else ""
            print(f"{ts}  {etype}{payload_str}")
    return 0


# ---------------------------------------------------------------------------
# Queue — status
# ---------------------------------------------------------------------------


def _warn_if_backup_stale(total_tasks: int) -> None:
    """Warn on stderr when the newest queue backup is missing or >48h old.

    Skipped for an empty queue — nothing worth backing up yet. Warning-only
    by design (arch doc §11.2): no backup daemon, no auto-backup.
    """
    if total_tasks == 0:
        return

    from gateway.paths import BUILDER_QUEUE_DB

    backup_dir = BUILDER_QUEUE_DB.parent / "backups"
    backups = sorted(
        backup_dir.glob("builder_queue_*.db"),
        key=lambda p: p.stat().st_mtime,
    )
    hint = (
        "Back up with: sqlite3 " + str(BUILDER_QUEUE_DB)
        + ' "VACUUM INTO \'' + str(backup_dir) + "/builder_queue_"
        + _dt.date.today().strftime("%Y%m%d") + ".db'\""
    )
    if not backups:
        print("WARNING: no queue backups found.", file=sys.stderr)
        print(hint, file=sys.stderr)
        return

    age_hours = (_dt.datetime.now().timestamp() - backups[-1].stat().st_mtime) / 3600
    if age_hours > 48:
        print(
            f"WARNING: newest queue backup is {age_hours / 24:.1f} days old "
            f"({backups[-1].name}).",
            file=sys.stderr,
        )
        print(hint, file=sys.stderr)


def _cmd_queue_status(args: argparse.Namespace) -> int:
    from gateway.builder_queue import queue_status

    status = queue_status()
    _warn_if_backup_stale(status["total"])
    if args.json:
        print(json.dumps(status, indent=2, default=str))
    else:
        print(f"Queue status ({status['total']} active tasks):")
        for state_key in (
            "queued",
            "claimed",
            "running",
            "blocked",
            "pr_opened",
            "awaiting_review",
            "done",
            "failed",
            "cancelled",
        ):
            count = status["per_state"].get(state_key, 0)
            if count > 0 or state_key == "queued":
                print(f"  {state_key}: {count}")
    return 0


# ---------------------------------------------------------------------------
# Queue — archive
# ---------------------------------------------------------------------------


def _cmd_queue_archive(args: argparse.Namespace) -> int:
    from gateway.builder_queue import archive_tasks

    try:
        result = archive_tasks(args.state, older_than_days=args.older_than)
        if args.json:
            print(json.dumps(result, indent=2, default=str))
        else:
            n = result["tasks_archived"]
            print(f"Archived {n} {args.state} task{'s' if n != 1 else ''}.")
        return 0
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


# ---------------------------------------------------------------------------
# Queue — brief (Phase 1B)
# ---------------------------------------------------------------------------


def _cmd_queue_brief(args: argparse.Namespace) -> int:
    from gateway.builder_brief import render_worker_brief
    from gateway.builder_queue import get_pr_links, get_task, list_events

    task = get_task(args.id)
    if task is None:
        print(f"error: task not found: {args.id}", file=sys.stderr)
        return 1

    events = list_events(args.id)
    pr_links = get_pr_links(args.id)
    brief = render_worker_brief(task, events, pr_links, branch=args.branch)

    if args.json:
        print(json.dumps({"task_id": args.id, "brief": brief}, indent=2))
    else:
        print(brief)
    return 0


# ---------------------------------------------------------------------------
# Queue — attach-report (Phase 1B)
# ---------------------------------------------------------------------------


def _cmd_queue_attach_report(args: argparse.Namespace) -> int:
    from gateway.builder_queue import (
        IllegalTransitionError,
        LeaseConflictError,
        TaskNotFoundError,
        attach_final_report,
    )

    if (args.report_json is None) == (args.report_file is None):
        print(
            "error: provide exactly one of --report-json or --report-file",
            file=sys.stderr,
        )
        return 1

    raw = args.report_json
    if args.report_file is not None:
        try:
            raw = Path(args.report_file).read_text()
        except OSError as exc:
            print(f"error: cannot read report file: {exc}", file=sys.stderr)
            return 1

    try:
        report = _parse_json_object(raw)
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    try:
        task = attach_final_report(
            args.id,
            report or {},
            lease_token=args.lease_token,
            claim_version=args.claim_version,
            operator_reason=args.operator_reason,
        )
        if args.json:
            print(json.dumps(task, indent=2, default=str))
        else:
            print(f"Attached final report to task {task['id']}")
        return 0
    except (
        ValueError,
        TaskNotFoundError,
        LeaseConflictError,
        IllegalTransitionError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


# ---------------------------------------------------------------------------
# Queue — attach-pr (Phase 1B)
# ---------------------------------------------------------------------------


def _cmd_queue_attach_pr(args: argparse.Namespace) -> int:
    from gateway.builder_queue import TaskNotFoundError, attach_pr

    try:
        link = attach_pr(
            args.id,
            args.pr,
            pr_url=args.url,
            head_sha=args.head_sha,
            checks_state=args.checks_state,
            review_state=args.review_state,
        )
        if args.json:
            print(json.dumps(link, indent=2, default=str))
        else:
            print(f"Attached PR #{link['pr_number']} to task {args.id}")
        return 0
    except (ValueError, TaskNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def _cmd_queue_sync_pr(args: argparse.Namespace) -> int:
    from gateway.builder_queue import sync_pr_status

    result = sync_pr_status()
    if args.json:
        print(json.dumps(result, indent=2, default=str))
        return 0 if not result["errors"] else 1
    if result["errors"]:
        for err in result["errors"]:
            print(f"  error PR #{err['pr_number']}: {err['error']}", file=sys.stderr)
    if not result["synced"]:
        print("No PR links to sync.")
    else:
        print(f"Synced {len(result['synced'])} PR link(s).")
    return 0 if not result["errors"] else 1


def _cmd_queue_reconcile_merges(args: argparse.Namespace) -> int:
    from gateway.builder_queue import detect_merged_prs

    result = detect_merged_prs()
    if args.json:
        print(json.dumps(result, indent=2, default=str))
        return 0 if not result["errors"] else 1
    if result["promoted"]:
        for task_id in result["promoted"]:
            print(f"  promoted: {task_id} -> done (PR merged)")
    if result["already_merged"]:
        print(f"  already merged: {len(result['already_merged'])} task(s)")
    if result["errors"]:
        for err in result["errors"]:
            print(f"  error {err['task_id']}: {err['error']}", file=sys.stderr)
    if not result["promoted"] and not result["already_merged"]:
        print("No merged PRs detected.")
    return 0 if not result["errors"] else 1


def _cmd_queue_publish(args: argparse.Namespace) -> int:
    """Operator-gated push + PR create/update (KB-S4). Never merges."""
    from gateway.builder_publish import PublishError, publish_task
    from gateway.builder_queue import TaskNotFoundError

    try:
        result = publish_task(
            args.id,
            remote=args.remote,
            base=args.base,
            title=args.title,
            dry_run=args.dry_run,
        )
    except (PublishError, TaskNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, indent=2, default=str))
        return 0

    if result["dry_run"]:
        print(f"dry-run publish for {result['task_id']} branch {result['branch']}")
        print(f"  push: {' '.join(result['push']['command'])}")
        print(f"  pr:   {result['pr']['action']} #{result['pr'].get('pr_number')}")
        return 0

    pr = result["pr"]
    print(
        f"Published {result['task_id']} → {result['branch']} "
        f"(PR #{pr.get('pr_number')} {pr.get('action')})"
    )
    if pr.get("pr_url"):
        print(f"  url: {pr['pr_url']}")
    for step in result.get("transitions") or []:
        print(f"  transition: {step}")
    return 0


# ---------------------------------------------------------------------------
# Queue — recover (Phase 1B)
# ---------------------------------------------------------------------------


def _cmd_queue_recover(args: argparse.Namespace) -> int:
    from gateway.builder_queue import (
        recover_expired_leases,
        recover_interrupted_runs,
    )

    result = recover_expired_leases()
    runs_result = recover_interrupted_runs()
    if args.json:
        print(json.dumps({**result, **runs_result}, indent=2, default=str))
    else:
        print(
            f"Recovered {result['total']} task(s): "
            f"{result['claimed_requeued']} claimed → queued, "
            f"{result['running_blocked']} running → blocked (stale_heartbeat)"
        )
        print(
            f"Marked {runs_result['runs_interrupted']} dead run(s) as interrupted"
        )
        reconciled_blocked = runs_result.get("running_tasks_blocked", 0)
        reconciled_requeued = runs_result.get("claimed_tasks_requeued", 0)
        if reconciled_blocked or reconciled_requeued:
            print(
                "Reconciled interrupted-run tasks: "
                f"{reconciled_requeued} claimed → queued, "
                f"{reconciled_blocked} running → blocked (run_interrupted)"
            )
        deferred_ids = runs_result.get("starting_run_ids", [])
        if deferred_ids:
            print(
                "Deferred fresh starting run(s) until the recovery grace "
                f"window expires: {', '.join(deferred_ids)}"
            )
        unverified_runs = runs_result.get("unverified_runs", [])
        for run in unverified_runs:
            print(
                "WARNING: left active run "
                f"{run['run_id']} unchanged because its process could not be "
                f"verified ({run['reason']})"
            )
    return 0


# ---------------------------------------------------------------------------
# Queue — operator-cancel (Phase 1B)
# ---------------------------------------------------------------------------


def _cmd_queue_operator_cancel(args: argparse.Namespace) -> int:
    from gateway.builder_queue import (
        IllegalTransitionError,
        TaskNotFoundError,
        transition_task,
    )

    payload: dict[str, Any] = {"operator": True}
    if args.reason:
        payload["reason"] = args.reason

    try:
        task = transition_task(args.id, "cancelled", payload=payload)
        if args.json:
            print(json.dumps(task, indent=2, default=str))
        else:
            print(f"Cancelled task {task['id']}")
        return 0
    except (ValueError, TaskNotFoundError, IllegalTransitionError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


# ---------------------------------------------------------------------------
# Queue — run / runs / show-run / cancel-run / clean-worktree (Phase 1C-alpha)
# ---------------------------------------------------------------------------


def _cmd_queue_run(args: argparse.Namespace) -> int:
    from gateway.builder_queue import (
        IllegalTransitionError,
        LeaseConflictError,
        TaskNotFoundError,
    )
    from gateway.builder_runner import RunnerError, run_worker

    command = list(args.worker_command or [])
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        print(
            "error: provide the worker command after --, e.g. "
            "queue run <id> -- opencode run --auto '...'",
            file=sys.stderr,
        )
        return 1

    try:
        run = run_worker(
            args.id,
            command,
            worker=args.worker,
            model=args.model,
            provider=args.provider,
            timeout_seconds=args.timeout,
            lease_seconds=args.lease_seconds,
            heartbeat_seconds=args.heartbeat_seconds,
        )
    except (
        TaskNotFoundError,
        LeaseConflictError,
        IllegalTransitionError,
        RunnerError,
        ValueError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(run, indent=2, default=str))
    else:
        _print_run_summary(run, verbose=True)
    return 0 if run.get("state") == "exited" else 1


def _cmd_queue_runs(args: argparse.Namespace) -> int:
    from gateway.builder_queue import list_runs

    runs = list_runs(task_id=args.task, state=args.state)
    if args.json:
        print(json.dumps(runs, indent=2, default=str))
    else:
        if not runs:
            print("No runs found.")
            return 0
        for run in runs:
            _print_run_summary(run)
    return 0


def _cmd_queue_show_run(args: argparse.Namespace) -> int:
    from gateway.builder_queue import get_run

    run = get_run(args.run_id)
    if run is None:
        print(f"error: run not found: {args.run_id}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(run, indent=2, default=str))
        return 0

    _print_run_summary(run, verbose=True)
    if args.log_tail and run.get("log_path"):
        log_file = Path(run["log_path"])
        if log_file.exists():
            print(f"--- log tail ({args.log_tail} lines) ---")
            lines = log_file.read_text(errors="replace").splitlines()
            for line in lines[-args.log_tail:]:
                print(line)
        else:
            print(f"error: log file missing: {log_file}", file=sys.stderr)
            return 1
    return 0


def _cmd_queue_cancel_run(args: argparse.Namespace) -> int:
    from gateway.builder_queue import RunNotFoundError
    from gateway.builder_runner import RunnerError, request_cancel

    try:
        run = request_cancel(args.run_id, kill=args.kill)
    except (RunNotFoundError, RunnerError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(run, indent=2, default=str))
    elif run.get("signal_sent"):
        print(
            f"Cancellation requested for run {args.run_id}; signal sent to "
            f"pid {run.get('pid')}. The runner records the outcome within "
            "one heartbeat."
        )
    else:
        print(
            f"Cancellation recorded for run {args.run_id}; signal not sent "
            f"({run.get('signal_status', 'unknown_reason')}). The runner will "
            "honor the durable flag if it is still active."
        )
    return 0


def _cmd_queue_clean_worktree(args: argparse.Namespace) -> int:
    from gateway.builder_runner import RunnerError, remove_worktree

    try:
        path = remove_worktree(args.id)
    except RunnerError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"Removed clean worktree {path}")
    return 0


def _print_run_summary(run: dict[str, Any], verbose: bool = False) -> None:
    if verbose:
        print(f"Run:        {run['id']}")
        print(f"Task:       {run['task_id']}")
        print(f"State:      {run['state']}")
        cmd = run.get("command")
        if cmd:
            print(f"Command:    {' '.join(cmd)}")
        for label, key in (
            ("Worker", "worker"),
            ("Model", "model"),
            ("Provider", "provider"),
            ("PID", "pid"),
            ("Branch", "branch"),
            ("Worktree", "worktree_path"),
            ("Log", "log_path"),
            ("Exit code", "exit_code"),
            ("Started", "started_at"),
            ("Ended", "ended_at"),
            ("Heartbeat", "last_heartbeat_at"),
        ):
            value = run.get(key)
            if value is not None and value != "":
                print(f"{label + ':':<12}{value}")
    else:
        print(
            f"  [{run['state']}] {run['id']}  task={run['task_id']}  "
            f"exit={run.get('exit_code')}"
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _print_task_summary(
    task: dict[str, Any],
    verbose: bool = False,
) -> None:
    """Print a compact human-readable task summary."""
    tid = task["id"]
    title = task.get("title", "")
    state = task.get("state", "")
    prio = task.get("priority", 0)
    owner = task.get("lease_owner") or "-"
    ts = task.get("updated_at", "") or task.get("created_at", "") or ""

    if verbose:
        print(f"Task:       {tid}")
        print(f"Title:      {title}")
        print(f"State:      {state}")
        print(f"Priority:   {prio}")
        print(f"Owner:      {owner}")
        print(f"Updated:    {ts}")
        desc = task.get("description")
        if desc:
            print(f"Description: {desc}")
        ac = task.get("acceptance_criteria")
        if ac:
            print(f"Acceptance: {json.dumps(ac)}")
        ap = task.get("allowed_paths")
        if ap:
            print(f"Paths:      {json.dumps(ap)}")
        cv = task.get("claim_version")
        lt = task.get("lease_token")
        if lt:
            print(f"Lease token: {lt}")
        if cv is not None:
            print(f"Claim version: {cv}")
        le = task.get("lease_expires_at")
        if le:
            print(f"Lease expiry: {le}")
        br = task.get("blocked_reason")
        if br:
            print(f"Blocked reason: {br}")
        err = task.get("last_error")
        if err:
            print(f"Last error: {err}")
    else:
        print(f"  [{state}] {tid}  pri={prio}  owner={owner}  \"{title}\"")


# ---------------------------------------------------------------------------
# Initiative (KB-S1A)
# ---------------------------------------------------------------------------


def _cmd_initiative_validate(args: argparse.Namespace) -> int:
    from gateway.builder_initiative import (
        ManifestError,
        load_manifest,
        manifest_sha256,
        validate_manifest,
    )

    try:
        manifest = load_manifest(Path(args.manifest))
    except ManifestError as exc:
        for error in exc.errors:
            print(f"error: {error}", file=sys.stderr)
        return 1

    errors = validate_manifest(manifest)
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 1

    print(
        f"OK: initiative {manifest['initiative_id']!r}, "
        f"{len(manifest['packets'])} packet(s), "
        f"sha256 {manifest_sha256(manifest)}"
    )
    return 0


def _cmd_initiative_apply(args: argparse.Namespace) -> int:
    from gateway.builder_initiative import (
        InitiativeConflictError,
        ManifestError,
        apply_manifest,
        load_manifest,
    )

    try:
        manifest = load_manifest(Path(args.manifest))
        result = apply_manifest(manifest, dry_run=args.dry_run)
    except ManifestError as exc:
        for error in exc.errors:
            print(f"error: {error}", file=sys.stderr)
        return 1
    except InitiativeConflictError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, indent=2, default=str))
        return 0

    print(
        f"{result['status']}: initiative {result['initiative_id']!r} "
        f"({len(result['packets'])} packet(s), "
        f"sha256 {result['manifest_sha256'][:12]}…)"
    )
    for mapping in result["packets"]:
        task = mapping["task_id"] or "(dry run — no task created)"
        print(f"  {mapping['packet_id']} -> {task}")
    return 0


def _cmd_initiative_list(args: argparse.Namespace) -> int:
    from gateway.builder_initiative import list_initiatives

    initiatives = list_initiatives()
    if args.json:
        print(json.dumps(initiatives, indent=2, default=str))
        return 0
    if not initiatives:
        print("No initiatives found.")
        return 0
    for item in initiatives:
        print(
            f"{item['id']}  [{item['state']}]  {item['title']}  "
            f"({item['packet_count']} packet(s))"
        )
    return 0


def _cmd_initiative_show(args: argparse.Namespace) -> int:
    from gateway.builder_initiative import get_initiative

    initiative = get_initiative(args.id)
    if initiative is None:
        print(f"error: initiative not found: {args.id}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(initiative, indent=2, default=str))
        return 0

    print(f"{initiative['id']}  [{initiative['state']}]  {initiative['title']}")
    print(f"  manifest sha256: {initiative['manifest_sha256']}")
    print(f"  created: {initiative['created_at']}")
    for packet in initiative["packets"]:
        deps = ", ".join(packet["depends_on"]) if packet["depends_on"] else "-"
        print(f"  {packet['packet_id']}  task={packet['task_id']}  deps: {deps}")
        print(f"    {packet['title']}")
    return 0


def _cmd_initiative_status(args: argparse.Namespace) -> int:
    from gateway.builder_initiative import (
        InitiativeNotFoundError,
        initiative_status,
    )

    try:
        status = initiative_status(args.id)
    except InitiativeNotFoundError as exc:
        print(f"error: initiative not found: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(status, indent=2, default=str))
        return 0

    print(f"{status['initiative_id']}  [{status['state']}]")
    print(f"  packets: {status['total_packets']}")
    if status["next_packet"]:
        print(
            f"  next:    {status['next_packet']} (task {status['next_packet_task_id']})"
        )
    else:
        print("  next:    -")
    print(f"  eligible: {', '.join(status['eligible']) or '-'}")
    print(f"  done:     {', '.join(status['done']) or '-'}")
    print(f"  in flight: {', '.join(status['in_progress']) or '-'}")
    print(f"  pending:  {', '.join(status['pending']) or '-'}")
    if status["blocked"]:
        print("  blocked (unreachable):")
        for pid in status["blocked"]:
            print(f"    - {pid}")
    if status["failed"]:
        print(f"  failed:   {', '.join(status['failed'])}")
    return 0


def _cmd_initiative_attempts(args: argparse.Namespace) -> int:
    from gateway.builder_attempt import list_attempts

    attempts = list_attempts(args.id, args.packet)
    if args.json:
        print(json.dumps(attempts, indent=2, default=str))
        return 0
    if not attempts:
        print("No attempts found.")
        return 0
    for a in attempts:
        impl = (a["implementation"] or {}).get("status", "-")
        review = (a["review"] or {}).get("verdict", "-")
        print(
            f"#{a['id']}  {a['packet_id']}  attempt {a['attempt_no']}  "
            f"outcome={a['outcome'] or 'open'}  impl={impl}  review={review}"
        )
    return 0


def _cmd_initiative_start_attempt(args: argparse.Namespace) -> int:
    from gateway.builder_attempt import AttemptError, start_attempt

    try:
        attempt = start_attempt(args.id, args.packet)
    except AttemptError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(attempt, indent=2, default=str))
    else:
        print(
            f"started attempt {attempt['attempt_no']} (id {attempt['id']}) "
            f"for {attempt['initiative_id']}/{attempt['packet_id']}"
        )
    return 0


def _load_result_file(path: str) -> dict[str, Any]:
    parsed = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError("result file must contain a JSON object")
    return parsed


def _cmd_initiative_record(args: argparse.Namespace) -> int:
    from gateway.builder_attempt import (
        AttemptError,
        ResultContractError,
        record_implementation_result,
        record_review_result,
    )

    record = (
        record_implementation_result
        if args.initiative_command == "record-implementation"
        else record_review_result
    )
    try:
        result = _load_result_file(args.file)
        attempt = record(args.attempt_id, result)
    except ResultContractError as exc:
        for error in exc.errors:
            print(f"error: {error}", file=sys.stderr)
        return 1
    except (OSError, ValueError, json.JSONDecodeError, AttemptError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(attempt, indent=2, default=str))
    else:
        print(f"recorded on attempt {attempt['id']}")
    return 0


def _cmd_initiative_run_packet(args: argparse.Namespace) -> int:
    from gateway.builder_attempt import AttemptError
    from gateway.builder_loop import LoopError, run_packet
    from gateway.builder_runner import RunnerError

    try:
        worker_command = _parse_json_array(args.worker_command)
        review_command = _parse_json_array(args.review_command)
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if not worker_command:
        print("error: --worker-command must be a non-empty JSON array", file=sys.stderr)
        return 1

    try:
        result = run_packet(
            args.id,
            args.packet,
            worker_command=worker_command,
            review_command=review_command,
            worker=args.worker,
            model=args.model,
            provider=args.provider,
            timeout_seconds=args.timeout,
        )
    except (LoopError, RunnerError, AttemptError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        print(
            f"{result['outcome']}: {result['initiative_id']}/{result['packet_id']} "
            f"after {len(result['attempts'])} attempt(s)"
        )
        for entry in result["attempts"]:
            detail = entry.get("failure") or "ok"
            print(f"  attempt {entry['attempt_no']}: {entry['outcome']} — {detail}")
    return 0 if result["outcome"] == "succeeded" else 1


def _cmd_initiative_run(args: argparse.Namespace) -> int:
    from gateway.builder_run import run_initiative

    try:
        worker_command = _parse_json_array(args.worker_command)
        review_command = _parse_json_array(args.review_command)
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if not worker_command:
        print("error: --worker-command must be a non-empty JSON array", file=sys.stderr)
        return 1

    try:
        summary = run_initiative(
            args.id,
            worker_command=worker_command,
            review_command=review_command,
            worker=args.worker,
            model=args.model,
            provider=args.provider,
            timeout_seconds=args.timeout,
            publish=args.publish,
            max_initiative_attempts=args.max_attempts,
            max_runtime_seconds=args.max_runtime,
        )
    except (ValueError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(summary, indent=2, default=str))
    else:
        print(
            f"{summary['outcome']}: {args.id} "
            f"succeeded={summary['succeeded']} exhausted={summary['exhausted']}"
        )
        if summary.get("reason"):
            print(f"  reason: {summary['reason']}")
        for entry in summary["processed"]:
            print(
                f"  {entry['outcome']}: {args.id}/{entry['packet_id']}"
            )
    return 0 if summary["outcome"] in {"idle", "paused"} else 1


def _cmd_initiative_pause(args: argparse.Namespace) -> int:
    from gateway.builder_initiative import pause_initiative

    try:
        pause_initiative(args.id, args.reason)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"paused: {args.id}" + (f" ({args.reason})" if args.reason else ""))
    return 0


def _cmd_initiative_resume(args: argparse.Namespace) -> int:
    from gateway.builder_initiative import resume_initiative

    try:
        resume_initiative(args.id)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"resumed: {args.id}")
    return 0


def _cmd_initiative_run_validation(args: argparse.Namespace) -> int:
    from gateway.builder_attempt import AttemptError, run_validation

    try:
        attempt = run_validation(
            args.attempt_id,
            cwd=Path(args.cwd) if args.cwd else None,
            timeout_seconds=args.timeout,
        )
    except AttemptError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    validation = attempt["validation"]
    if args.json:
        print(json.dumps(attempt, indent=2, default=str))
    else:
        print(f"validation {validation['status']} (attempt {attempt['id']})")
        for r in validation["commands"]:
            marker = "ok " if r["passed"] else "FAIL"
            print(f"  [{marker}] {r['command']} ({r['duration_s']}s)")
    return 0 if validation["status"] != "failed" else 1


def _cmd_initiative_close_attempt(args: argparse.Namespace) -> int:
    from gateway.builder_attempt import AttemptError, close_attempt

    try:
        attempt = close_attempt(args.attempt_id, args.outcome)
    except AttemptError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(attempt, indent=2, default=str))
    else:
        print(f"attempt {attempt['id']} closed: {attempt['outcome']}")
    return 0


def _init_queue_db() -> None:
    """Initialize the queue DB safely before command dispatch."""
    from gateway.builder_queue import init_db

    init_db()


def _init_initiative_db() -> None:
    """Initialize queue + initiative schema before initiative dispatch."""
    from gateway.builder_initiative import init_db

    init_db()


_dispatch: dict[str, Any] = {
    "run": _cmd_not_enabled,
    "loop": _cmd_not_enabled,
    "repl": _cmd_not_enabled,
    "delegate": _cmd_not_enabled,
    "brief": _cmd_brief,
    "contract": _cmd_contract_validate,
    "queue-add": _cmd_queue_add,
    "queue-edit": _cmd_queue_edit,
    "queue-list": _cmd_queue_list,
    "queue-show": _cmd_queue_show,
    "queue-claim": _cmd_queue_claim,
    "queue-claim-next": _cmd_queue_claim_next,
    "queue-release": _cmd_queue_release,
    "queue-operator-release": _cmd_queue_operator_release,
    "queue-transition": _cmd_queue_transition,
    "queue-events": _cmd_queue_events,
    "queue-status": _cmd_queue_status,
    "queue-archive": _cmd_queue_archive,
    "queue-brief": _cmd_queue_brief,
    "queue-attach-report": _cmd_queue_attach_report,
    "queue-attach-pr": _cmd_queue_attach_pr,
    "queue-sync-pr": _cmd_queue_sync_pr,
    "queue-reconcile-merges": _cmd_queue_reconcile_merges,
    "queue-publish": _cmd_queue_publish,
    "queue-recover": _cmd_queue_recover,
    "queue-operator-cancel": _cmd_queue_operator_cancel,
    "queue-run": _cmd_queue_run,
    "queue-runs": _cmd_queue_runs,
    "queue-show-run": _cmd_queue_show_run,
    "queue-cancel-run": _cmd_queue_cancel_run,
    "queue-clean-worktree": _cmd_queue_clean_worktree,
    "initiative-validate": _cmd_initiative_validate,
    "initiative-apply": _cmd_initiative_apply,
    "initiative-list": _cmd_initiative_list,
    "initiative-show": _cmd_initiative_show,
    "initiative-status": _cmd_initiative_status,
    "initiative-attempts": _cmd_initiative_attempts,
    "initiative-start-attempt": _cmd_initiative_start_attempt,
    "initiative-record-implementation": _cmd_initiative_record,
    "initiative-record-review": _cmd_initiative_record,
    "initiative-run-validation": _cmd_initiative_run_validation,
    "initiative-run-packet": _cmd_initiative_run_packet,
    "initiative-close-attempt": _cmd_initiative_close_attempt,
    "initiative-run": _cmd_initiative_run,
    "initiative-pause": _cmd_initiative_pause,
    "initiative-resume": _cmd_initiative_resume,
}


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kitty builder",
        description="Kitty Builder control-plane (Layer 1A — coordination only).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="[NOT ENABLED] start a build session")
    run_p.add_argument("goal", nargs="+", help="goal for the builder")

    loop_p = sub.add_parser("loop", help="[NOT ENABLED] start an interactive session")
    loop_p.add_argument("goal", nargs="+", help="goal for the builder")

    repl_p = sub.add_parser("repl", help="[NOT ENABLED] alias for 'loop'")
    repl_p.add_argument("goal", nargs="+", help="goal for the builder")

    del_p = sub.add_parser(
        "delegate", help="[NOT ENABLED] hand a task to a worker CLI"
    )
    del_p.add_argument("cli", help="worker CLI alias (e.g. opencode)")
    del_p.add_argument("task", nargs="+", help="task description")

    brief_p = sub.add_parser("brief", help="print the repo brief for a task")
    brief_p.add_argument("task", nargs="+", help="task description")
    brief_p.add_argument("--packet", help="optional packet JSON file")

    contract_p = sub.add_parser("contract", help="builder contract commands")
    contract_sub = contract_p.add_subparsers(dest="contract_command", required=True)
    validate_p = contract_sub.add_parser("validate", help="validate a contract file")
    validate_p.add_argument("path", help="path to JSON or markdown contract")

    # -- queue subcommand group -----------------------------------------------

    queue_p = sub.add_parser("queue", help="durable builder queue commands")
    queue_sub = queue_p.add_subparsers(dest="queue_command", required=True)

    # queue add
    add_p = queue_sub.add_parser("add", help="add a task to the queue")
    add_p.add_argument("title", help="task title")
    add_p.add_argument("--description", help="task description")
    add_p.add_argument(
        "--acceptance",
        help='JSON array of acceptance criteria, e.g. \'["criterion"]\'',
        default=None,
    )
    add_p.add_argument("--priority", type=int, default=0, help="priority (higher = sooner)")
    add_p.add_argument(
        "--allowed-paths",
        help='JSON array of allowed file paths, e.g. \'["path"]\'',
        default=None,
    )
    add_p.add_argument("--json", action="store_true", help="output JSON")

    # queue edit
    edit_p = queue_sub.add_parser("edit", help="edit a queued task's fields")
    edit_p.add_argument("id", help="task ID")
    edit_p.add_argument("--title", help="new title")
    edit_p.add_argument("--description", help="new description")
    edit_p.add_argument("--priority", type=int, help="new priority")
    edit_p.add_argument(
        "--acceptance",
        help='JSON array of acceptance criteria, e.g. \'["criterion"]\'',
        default=None,
    )
    edit_p.add_argument(
        "--allowed-paths",
        help='JSON array of allowed file paths, e.g. \'["path"]\'',
        default=None,
    )
    edit_p.add_argument("--json", action="store_true", help="output JSON")

    # queue list
    list_p = queue_sub.add_parser("list", help="list tasks in the queue")
    list_p.add_argument("--state", help="filter by state")
    list_p.add_argument(
        "--include-archived", action="store_true", help="include archived tasks"
    )
    list_p.add_argument("--json", action="store_true", help="output JSON")

    # queue show
    show_p = queue_sub.add_parser("show", help="show task details")
    show_p.add_argument("id", help="task ID")
    show_p.add_argument("--json", action="store_true", help="output JSON")

    # queue claim
    claim_p = queue_sub.add_parser("claim", help="claim a specific task")
    claim_p.add_argument("id", help="task ID")
    claim_p.add_argument("--worker", required=True, help="worker name")
    claim_p.add_argument("--lease-seconds", type=int, default=1800, help="lease duration")
    claim_p.add_argument("--json", action="store_true", help="output JSON")

    # queue claim-next
    claim_next_p = queue_sub.add_parser(
        "claim-next", help="claim the highest-priority queued task"
    )
    claim_next_p.add_argument("--worker", required=True, help="worker name")
    claim_next_p.add_argument(
        "--lease-seconds", type=int, default=1800, help="lease duration"
    )
    claim_next_p.add_argument("--json", action="store_true", help="output JSON")

    # queue release (worker)
    release_p = queue_sub.add_parser(
        "release", help="release a claimed task back to queued (worker)"
    )
    release_p.add_argument("id", help="task ID")
    release_p.add_argument("--worker", required=True, help="worker name")
    release_p.add_argument("--lease-token", required=True, help="lease token from claim")
    release_p.add_argument(
        "--claim-version", type=int, required=True, help="claim version from claim"
    )
    release_p.add_argument("--json", action="store_true", help="output JSON")

    # queue operator-release
    op_rel_p = queue_sub.add_parser(
        "operator-release", help="operator-forced release of a task"
    )
    op_rel_p.add_argument("id", help="task ID")
    op_rel_p.add_argument("--reason", default=None, help="reason for release")
    op_rel_p.add_argument("--json", action="store_true", help="output JSON")

    # queue transition
    trans_p = queue_sub.add_parser(
        "transition", help="transition a task to a new state (worker-fenced)"
    )
    trans_p.add_argument("id", help="task ID")
    trans_p.add_argument("state", help="target state")
    trans_p.add_argument("--lease-token", required=True, help="lease token from claim")
    trans_p.add_argument(
        "--claim-version", type=int, required=True, help="claim version from claim"
    )
    trans_p.add_argument("--payload-json", help="JSON object payload")
    trans_p.add_argument("--json", action="store_true", help="output JSON")

    # queue events
    events_p = queue_sub.add_parser("events", help="list events for a task")
    events_p.add_argument("id", help="task ID")
    events_p.add_argument("--json", action="store_true", help="output JSON")

    # queue status
    status_p = queue_sub.add_parser("status", help="queue summary per state")
    status_p.add_argument("--json", action="store_true", help="output JSON")

    # queue archive
    archive_p = queue_sub.add_parser(
        "archive", help="soft-archive terminal tasks by state and age"
    )
    archive_p.add_argument(
        "--state",
        required=True,
        help="terminal state to archive (done, failed, cancelled)",
    )
    archive_p.add_argument(
        "--older-than",
        type=int,
        required=True,
        help="archive tasks older than this many days",
    )
    archive_p.add_argument("--json", action="store_true", help="output JSON")

    # queue brief (Phase 1B)
    brief_q_p = queue_sub.add_parser(
        "brief", help="render a complete worker brief for a task"
    )
    brief_q_p.add_argument("id", help="task ID")
    brief_q_p.add_argument(
        "--branch", help="branch name override (default kittybuilder/<task_id>)"
    )
    brief_q_p.add_argument("--json", action="store_true", help="output JSON")

    # queue attach-report (Phase 1B)
    att_rep_p = queue_sub.add_parser(
        "attach-report", help="attach a structured final report to a task"
    )
    att_rep_p.add_argument("id", help="task ID")
    att_rep_p.add_argument("--report-json", help="report as a JSON object string")
    att_rep_p.add_argument("--report-file", help="path to a JSON report file")
    att_rep_p.add_argument("--lease-token", help="lease token (worker mode)")
    att_rep_p.add_argument(
        "--claim-version", type=int, help="claim version (worker mode)"
    )
    att_rep_p.add_argument(
        "--operator-reason",
        help="operator mode: reason for attaching without a lease",
    )
    att_rep_p.add_argument("--json", action="store_true", help="output JSON")

    # queue attach-pr (Phase 1B)
    att_pr_p = queue_sub.add_parser(
        "attach-pr", help="attach/update advisory PR metadata for a task"
    )
    att_pr_p.add_argument("id", help="task ID")
    att_pr_p.add_argument("--pr", type=int, required=True, help="PR number")
    att_pr_p.add_argument("--url", help="PR URL")
    att_pr_p.add_argument("--head-sha", help="PR head commit SHA")
    att_pr_p.add_argument("--checks-state", help="CI checks state summary")
    att_pr_p.add_argument("--review-state", help="review state summary")
    att_pr_p.add_argument("--json", action="store_true", help="output JSON")

    # queue sync-pr / reconcile-merges (KB-S4)
    sync_pr_p = queue_sub.add_parser(
        "sync-pr",
        help="advisory CI/review reconciliation into pr_links (no task mutation)",
    )
    sync_pr_p.add_argument("--json", action="store_true", help="output JSON")
    reconcile_p = queue_sub.add_parser(
        "reconcile-merges",
        help="promote tasks to done whose linked PR has merged (unlocks dependents)",
    )
    reconcile_p.add_argument("--json", action="store_true", help="output JSON")

    # queue publish (KB-S4 push + PR)
    pub_p = queue_sub.add_parser(
        "publish",
        help="operator-gated: push task branch and create/update PR (never merges)",
    )
    pub_p.add_argument("id", help="task ID")
    pub_p.add_argument("--remote", default="origin", help="git remote (default: origin)")
    pub_p.add_argument("--base", default="main", help="PR base branch (default: main)")
    pub_p.add_argument("--title", help="PR title (default: kittybuilder: <task title>)")
    pub_p.add_argument(
        "--dry-run",
        action="store_true",
        help="print planned git/gh commands without executing",
    )
    pub_p.add_argument("--json", action="store_true", help="output JSON")

    # queue recover (Phase 1B)
    recover_p = queue_sub.add_parser(
        "recover",
        help="recovery scan: expired claimed → queued, expired running → blocked",
    )
    recover_p.add_argument("--json", action="store_true", help="output JSON")

    # queue operator-cancel (Phase 1B)
    op_cancel_p = queue_sub.add_parser(
        "operator-cancel",
        help="operator cancel of a task without a lease (e.g. queued/blocked)",
    )
    op_cancel_p.add_argument("id", help="task ID")
    op_cancel_p.add_argument("--reason", help="reason for cancellation")
    op_cancel_p.add_argument("--json", action="store_true", help="output JSON")

    # queue run (Phase 1C-alpha shadow mode)
    run_q_p = queue_sub.add_parser(
        "run",
        help="claim a task and run a worker command in its isolated worktree "
        "(shadow mode: no push, no PR)",
    )
    run_q_p.add_argument("id", help="task ID")
    run_q_p.add_argument("--worker", default="local-runner", help="worker name")
    run_q_p.add_argument("--model", help="model identifier (metadata)")
    run_q_p.add_argument("--provider", help="provider identifier (metadata)")
    run_q_p.add_argument(
        "--timeout", type=int, default=3600, help="worker timeout in seconds"
    )
    run_q_p.add_argument(
        "--lease-seconds", type=int, default=60, help="heartbeat lease duration"
    )
    run_q_p.add_argument(
        "--heartbeat-seconds", type=int, default=10, help="heartbeat interval"
    )
    run_q_p.add_argument("--json", action="store_true", help="output JSON")
    run_q_p.add_argument(
        "worker_command",
        nargs="*",
        help="worker command after --",
    )

    # queue runs
    runs_p = queue_sub.add_parser("runs", help="list run records")
    runs_p.add_argument("--task", help="filter by task ID")
    runs_p.add_argument("--state", help="filter by run state")
    runs_p.add_argument("--json", action="store_true", help="output JSON")

    # queue show-run
    show_run_p = queue_sub.add_parser("show-run", help="show one run record")
    show_run_p.add_argument("run_id", help="run ID")
    show_run_p.add_argument(
        "--log-tail", type=int, default=0, help="print last N log lines"
    )
    show_run_p.add_argument("--json", action="store_true", help="output JSON")

    # queue cancel-run
    cancel_run_p = queue_sub.add_parser(
        "cancel-run", help="request cancellation of an active run"
    )
    cancel_run_p.add_argument("run_id", help="run ID")
    cancel_run_p.add_argument(
        "--kill", action="store_true", help="escalate to SIGKILL"
    )
    cancel_run_p.add_argument("--json", action="store_true", help="output JSON")

    # queue clean-worktree
    clean_wt_p = queue_sub.add_parser(
        "clean-worktree", help="remove a task worktree (refuses if dirty)"
    )
    clean_wt_p.add_argument("id", help="task ID")

    # -- initiative subcommand group (KB-S1A) ----------------------------------

    initiative_p = sub.add_parser(
        "initiative", help="initiative manifest commands"
    )
    initiative_sub = initiative_p.add_subparsers(
        dest="initiative_command", required=True
    )

    ini_validate_p = initiative_sub.add_parser(
        "validate", help="validate an initiative manifest file"
    )
    ini_validate_p.add_argument("manifest", help="path to the manifest JSON file")

    ini_apply_p = initiative_sub.add_parser(
        "apply",
        help="apply a manifest: create the initiative and one queue task per packet",
    )
    ini_apply_p.add_argument("manifest", help="path to the manifest JSON file")
    ini_apply_p.add_argument(
        "--dry-run", action="store_true", help="validate and report without mutating"
    )
    ini_apply_p.add_argument("--json", action="store_true", help="output JSON")

    ini_list_p = initiative_sub.add_parser("list", help="list initiatives")
    ini_list_p.add_argument("--json", action="store_true", help="output JSON")

    ini_show_p = initiative_sub.add_parser(
        "show", help="show an initiative and its packet-to-task mappings"
    )
    ini_show_p.add_argument("id", help="initiative ID")
    ini_show_p.add_argument("--json", action="store_true", help="output JSON")

    ini_status_p = initiative_sub.add_parser(
        "status", help="roll up packet eligibility and initiative status (KB-S1B)"
    )
    ini_status_p.add_argument("id", help="initiative ID")
    ini_status_p.add_argument("--json", action="store_true", help="output JSON")

    # -- attempt lifecycle (KB-S2) ---------------------------------------------

    ini_attempts_p = initiative_sub.add_parser(
        "attempts", help="list packet attempts for an initiative"
    )
    ini_attempts_p.add_argument("id", help="initiative ID")
    ini_attempts_p.add_argument("packet", nargs="?", help="packet ID (optional)")
    ini_attempts_p.add_argument("--json", action="store_true", help="output JSON")

    ini_start_att_p = initiative_sub.add_parser(
        "start-attempt",
        help="open the next attempt for a packet and persist its context bundle",
    )
    ini_start_att_p.add_argument("id", help="initiative ID")
    ini_start_att_p.add_argument("packet", help="packet ID")
    ini_start_att_p.add_argument("--json", action="store_true", help="output JSON")

    for name, help_text in (
        ("record-implementation", "attach a validated implementation result"),
        ("record-review", "attach a validated review result"),
    ):
        rec_p = initiative_sub.add_parser(name, help=help_text)
        rec_p.add_argument("attempt_id", type=int, help="attempt ID")
        rec_p.add_argument("--file", required=True, help="path to the result JSON file")
        rec_p.add_argument("--json", action="store_true", help="output JSON")

    ini_run_pkt_p = initiative_sub.add_parser(
        "run-packet",
        help="drive one packet through the bounded implement/validate/review "
        "repair loop (shadow mode: no push, no PR)",
    )
    ini_run_pkt_p.add_argument("id", help="initiative ID")
    ini_run_pkt_p.add_argument("packet", help="packet ID")
    ini_run_pkt_p.add_argument(
        "--worker-command",
        required=True,
        help='worker command as a JSON array, e.g. \'["opencode", "run"]\'',
    )
    ini_run_pkt_p.add_argument(
        "--review-command",
        default=None,
        help="optional reviewer command as a JSON array (omit = validation-gated only)",
    )
    ini_run_pkt_p.add_argument("--worker", default="packet-loop", help="worker name")
    ini_run_pkt_p.add_argument("--model", help="model identifier (metadata)")
    ini_run_pkt_p.add_argument("--provider", help="provider identifier (metadata)")
    ini_run_pkt_p.add_argument(
        "--timeout", type=int, default=3600, help="worker timeout in seconds"
    )
    ini_run_pkt_p.add_argument("--json", action="store_true", help="output JSON")

    ini_run_val_p = initiative_sub.add_parser(
        "run-validation",
        help="run the packet's declared validation commands and record the verdict",
    )
    ini_run_val_p.add_argument("attempt_id", type=int, help="attempt ID")
    ini_run_val_p.add_argument(
        "--cwd", help="directory to run in (default: the task's runner worktree)"
    )
    ini_run_val_p.add_argument(
        "--timeout", type=int, default=600, help="per-command timeout in seconds"
    )
    ini_run_val_p.add_argument("--json", action="store_true", help="output JSON")

    ini_close_att_p = initiative_sub.add_parser(
        "close-attempt", help="close an open attempt with a terminal outcome"
    )
    ini_close_att_p.add_argument("attempt_id", type=int, help="attempt ID")
    ini_close_att_p.add_argument(
        "outcome", help="succeeded | failed | aborted"
    )
    ini_close_att_p.add_argument("--json", action="store_true", help="output JSON")

    # -- run loop (KB-S5) ------------------------------------------------------

    ini_run_p = initiative_sub.add_parser(
        "run",
        help="drive an initiative to completion: loop eligible packets through "
        "implement/validate/review (S3b) then operator-gated publish (S4b)",
    )
    ini_run_p.add_argument("id", help="initiative ID")
    ini_run_p.add_argument(
        "--worker-command",
        required=True,
        help='worker command as a JSON array, e.g. \'["opencode", "run"]\'',
    )
    ini_run_p.add_argument(
        "--review-command",
        default=None,
        help="optional reviewer command as a JSON array (omit = validation-gated only)",
    )
    ini_run_p.add_argument("--worker", default="packet-loop", help="worker name")
    ini_run_p.add_argument("--model", help="model identifier (metadata)")
    ini_run_p.add_argument("--provider", help="provider identifier (metadata)")
    ini_run_p.add_argument(
        "--timeout", type=int, default=3600, help="worker timeout in seconds"
    )
    ini_run_p.add_argument(
        "--publish",
        action="store_true",
        help="run KB-S4b publish (operator-gated push + PR) on each succeeded packet",
    )
    ini_run_p.add_argument(
        "--max-attempts",
        type=int,
        default=None,
        help="per-initiative attempt budget; exceeding it pauses the initiative",
    )
    ini_run_p.add_argument(
        "--max-runtime",
        type=int,
        default=None,
        help="per-initiative wall-clock budget (seconds); exceeding it pauses the initiative",
    )
    ini_run_p.add_argument("--json", action="store_true", help="output JSON")

    ini_pause_p = initiative_sub.add_parser(
        "pause", help="pause the run loop for an initiative (operator gate)"
    )
    ini_pause_p.add_argument("id", help="initiative ID")
    ini_pause_p.add_argument("--reason", default=None, help="advisory pause reason")

    ini_resume_p = initiative_sub.add_parser(
        "resume", help="clear a pause so the run loop may proceed"
    )
    ini_resume_p.add_argument("id", help="initiative ID")

    return parser


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def _resolve_func(args: argparse.Namespace) -> Any:
    """Resolve the handler function based on args.

    Queue subcommands have ``queue_command`` set; other commands have
    ``command`` set. The dispatch dict uses composite keys for queue commands.
    """
    if args.command == "queue":
        return _dispatch.get(f"queue-{args.queue_command}", _cmd_not_enabled)
    if args.command == "initiative":
        return _dispatch.get(
            f"initiative-{args.initiative_command}", _cmd_not_enabled
        )
    return _dispatch.get(args.command, _cmd_not_enabled)


# Queue commands that write to the DB; gated by the kill switch (§11.3).
_MUTATING_QUEUE_COMMANDS = frozenset(
    {
        "add",
        "edit",
        "claim",
        "claim-next",
        "release",
        "operator-release",
        "transition",
        "archive",
        "attach-report",
        "attach-pr",
        "sync-pr",
        "reconcile-merges",
        "publish",
        "recover",
        "operator-cancel",
        "run",
        "cancel-run",
        "clean-worktree",
    }
)


_MUTATING_INITIATIVE_COMMANDS = frozenset(
    {
        "apply",
        "start-attempt",
        "record-implementation",
        "record-review",
        "run-validation",
        "run-packet",
        "close-attempt",
        "run",
        "pause",
        "resume",
    }
)


def _queue_disabled() -> bool:
    return os.environ.get("KITTY_BUILDER_QUEUE_ENABLED", "1") == "0"


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    # Workaround for Python 3.11 argparse bug: `--` followed by positional
    # args with nargs="*" doesn't work in deeply nested subparsers.  Extract
    # everything after `--` before argparse, then restore it on the namespace.
    post_dash: list[str] | None = None
    if argv is not None and "--" in argv:
        idx = argv.index("--")
        post_dash = argv[idx + 1:]
        argv = argv[:idx]
    args = parser.parse_args(argv)
    if post_dash is not None:
        if args.command == "queue" and args.queue_command == "run":
            args.worker_command = post_dash

    if args.command == "queue":
        # Kill switch: refuse mutations before touching the DB. Read-only
        # commands keep working so the operator can inspect a frozen queue.
        if args.queue_command in _MUTATING_QUEUE_COMMANDS and _queue_disabled():
            print(
                "error: KittyBuilder queue is disabled "
                "(KITTY_BUILDER_QUEUE_ENABLED=0); refusing to modify the queue. "
                "Unset the variable or set it to 1 to re-enable.",
                file=sys.stderr,
            )
            return 1
        # Initialize the queue DB on every invocation (safe/idempotent).
        _init_queue_db()

    if args.command == "initiative":
        # Mutating initiative commands honor the same kill switch as the queue.
        if (
            args.initiative_command in _MUTATING_INITIATIVE_COMMANDS
            and _queue_disabled()
        ):
            print(
                "error: KittyBuilder queue is disabled "
                "(KITTY_BUILDER_QUEUE_ENABLED=0); refusing to modify "
                "initiative state. Unset the variable or set it to 1 to "
                "re-enable.",
                file=sys.stderr,
            )
            return 1
        if args.initiative_command != "validate":
            _init_initiative_db()

    func = _resolve_func(args)
    return func(args)


if __name__ == "__main__":
    raise SystemExit(main())
