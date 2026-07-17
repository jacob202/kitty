"""KittyBuilder execution control-plane CLI.

Primary command groups:
  brief <task>             print the repo brief for a task
  contract validate <path>  check a builder contract file
  queue <subcommand> ...    manage the durable builder queue and worker runs
  initiative <subcommand>   apply and execute bounded initiative packets

The legacy top-level ``run``, ``loop``, ``repl``, and ``delegate`` names remain
as fail-loud tombstones. Governed execution lives under ``queue`` and
``initiative``; the tombstones never imply that Builder execution is absent.

The command surface is declared once in ``COMMANDS`` (a declarative registry);
``build_parser`` turns that table into the argparse tree and attaches each
handler via ``set_defaults``, so there is a single source of truth for what a
command is and how it is wired. Adding a command is a table row, not a new
function plus a new ``add_parser`` block plus a new ``_dispatch`` entry.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

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


_FREE_ADAPTER_SCRIPTS = (
    "scripts/kittybuilder_opencode_worker.sh",
    "scripts/kittybuilder_opencode_reviewer.sh",
)


def _free_adapter_commands() -> tuple[list[str], list[str]]:
    """Resolve the free OpenCode adapter scripts in this checkout."""
    root = Path(__file__).resolve().parents[1]
    commands: list[list[str]] = []
    for rel in _FREE_ADAPTER_SCRIPTS:
        script = root / rel
        if not script.is_file():
            raise ValueError(f"free adapter script missing: {script}")
        commands.append(["bash", str(script)])
    return commands[0], commands[1]


def _resolve_loop_commands(
    args: argparse.Namespace,
) -> tuple[list[str], list[str] | None]:
    """Turn --free or --worker-command/--review-command into loop commands."""
    if args.free:
        if args.worker_command or args.review_command:
            raise ValueError(
                "--free already selects the OpenCode adapter scripts; "
                "drop --worker-command/--review-command or drop --free"
            )
        if args.model:
            # The ladder in the adapter honours a forced single model.
            os.environ["KITTYBUILDER_MODEL"] = args.model
        return _free_adapter_commands()
    worker_command = _parse_json_array(args.worker_command)
    review_command = _parse_json_array(args.review_command)
    if not worker_command:
        raise ValueError(
            "provide --free or a non-empty --worker-command JSON array"
        )
    return worker_command, review_command


# ---------------------------------------------------------------------------
# Retired top-level command handler
# ---------------------------------------------------------------------------


def _cmd_not_enabled(args: argparse.Namespace) -> int:
    print(
        f"'{args.command}' is a retired top-level KittyBuilder command and does not execute work.",
        file=sys.stderr,
    )
    print(
        "Use the fenced queue and initiative commands; for packet execution, "
        "run './kitty builder initiative run-packet --help'.",
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
    if status["exhausted"]:
        print("  exhausted (attempt budget spent, not runnable):")
        for pid in status["exhausted"]:
            print(f"    - {pid}")
    if status["blocked"]:
        print("  blocked (unreachable):")
        for pid in status["blocked"]:
            print(f"    - {pid}")
    if status["failed"]:
        print(f"  failed:   {', '.join(status['failed'])}")
    for packet_id, evidence in status.get("evidence", {}).items():
        binding = evidence.get("review_binding") or {}
        review_sha = binding.get("review_sha", "-")
        print(
            f"  evidence {packet_id}: attempts={evidence['attempts_used']} "
            f"worker_failed={evidence['worker_failed']} "
            f"infra_failures={evidence['infrastructure_failures']} "
            f"operator_completed={evidence['operator_completed']} "
            f"review_approved={evidence['review_approved']} "
            f"pr_opened={evidence['pr_opened']} done={evidence['done']} "
            f"review_sha={review_sha}"
        )
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
        worker_command, review_command = _resolve_loop_commands(args)
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    worker = args.worker
    if args.free and worker == "packet-loop":
        worker = "opencode-free"

    if args.watch and not args.json:
        print(f"watch: starting {args.id}/{args.packet}")

    try:
        result = run_packet(
            args.id,
            args.packet,
            worker_command=worker_command,
            review_command=review_command,
            worker=worker,
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
            if args.watch:
                print(f"    manifest: {entry.get('manifest_path', '-')}")
                if entry.get("run_id"):
                    print(f"    run:      {entry['run_id']} ({entry.get('run_state', '-')})")
        if args.watch:
            print(f"watch: finished with {result['outcome']}")
    return 0 if result["outcome"] == "succeeded" else 1


def _cmd_initiative_run(args: argparse.Namespace) -> int:
    from gateway.builder_run import run_initiative

    try:
        worker_command, review_command = _resolve_loop_commands(args)
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    worker = args.worker
    if args.free and worker == "packet-loop":
        worker = "opencode-free"

    try:
        summary = run_initiative(
            args.id,
            worker_command=worker_command,
            review_command=review_command,
            worker=worker,
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


def _cmd_initiative_doctor(args: argparse.Namespace) -> int:
    from gateway.builder_doctor import run_doctor

    result = run_doctor()

    if args.json:
        print(json.dumps(result, indent=2, default=str))
        return 0 if result["ok"] else 1

    for check in result["checks"]:
        print(f"{check['level']:4}  {check['name']:<28}  {check['detail']}")
    print()
    summary = result["summary"]
    if result["ok"]:
        print(
            f"OK — safe to run KittyBuilder "
            f"(pass={summary['pass']} warn={summary['warn']})"
        )
    else:
        print(
            f"NOT SAFE — {summary['fail']} blocking problem(s); "
            f"pass={summary['pass']} warn={summary['warn']} fail={summary['fail']}"
        )
    return 0 if result["ok"] else 1


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


# ---------------------------------------------------------------------------
# Command registry (declarative)
# ---------------------------------------------------------------------------
#
# One row per subcommand. ``build_parser`` turns this table into the argparse
# tree and attaches each handler via ``set_defaults``, so the parser shape and
# the dispatch are derived from a single source instead of three places
# (manual ``add_parser`` blocks + a ``_dispatch`` dict + a resolver).
# ---------------------------------------------------------------------------


@dataclass
class ArgSpec:
    """One ``add_argument`` entry for a command."""

    name: str
    help: str = ""
    kwargs: dict[str, Any] = field(default_factory=dict)


@dataclass
class CommandSpec:
    """One CLI subcommand: where it lives, its args, and its handler."""

    key: str
    group: str | None  # None | "queue" | "initiative" | "contract"
    name: str
    help: str
    handler: Callable[[argparse.Namespace], int]
    args: list[ArgSpec] = field(default_factory=list)


_GROUP_HELP = {
    "queue": "durable builder queue commands",
    "initiative": "initiative manifest commands",
    "contract": "builder contract commands",
}

_GROUP_SUBPARSER_DEST = {
    "queue": "queue_command",
    "initiative": "initiative_command",
    "contract": "contract_command",
}


def _a(name: str, help: str = "", **kwargs: Any) -> ArgSpec:
    """Shorthand for an ``ArgSpec``."""
    return ArgSpec(name=name, help=help, kwargs=kwargs)


COMMANDS: list[CommandSpec] = [
    # -- retired top-level names ---------------------------------------------
    CommandSpec("run", None, "run", "retired; use initiative run",
                _cmd_not_enabled, [_a("goal", "goal for the builder", nargs="+")]),
    CommandSpec("loop", None, "loop", "retired; no interactive Builder shell",
                _cmd_not_enabled, [_a("goal", "goal for the builder", nargs="+")]),
    CommandSpec("repl", None, "repl", "retired alias for loop",
                _cmd_not_enabled, [_a("goal", "goal for the builder", nargs="+")]),
    CommandSpec("delegate", None, "delegate", "retired; use initiative run-packet",
                _cmd_not_enabled,
                [_a("cli", "worker CLI alias (e.g. opencode)"),
                 _a("task", "task description", nargs="+")]),
    # -- brief ----------------------------------------------------------------
    CommandSpec("brief", None, "brief", "print the repo brief for a task",
                _cmd_brief,
                [_a("task", "task description", nargs="+"),
                 _a("--packet", "optional packet JSON file")]),
    # -- contract -------------------------------------------------------------
    CommandSpec("contract", "contract", "validate", "validate a contract file",
                _cmd_contract_validate,
                [_a("path", "path to JSON or markdown contract")]),
    # -- queue group ----------------------------------------------------------
    CommandSpec("queue-add", "queue", "add", "add a task to the queue",
                _cmd_queue_add,
                [_a("title", "task title"),
                 _a("--description", "task description"),
                 _a("--acceptance", "JSON array of acceptance criteria, e.g. '[\"criterion\"]'", default=None),
                 _a("--priority", "priority (higher = sooner)", type=int, default=0),
                 _a("--allowed-paths", "JSON array of allowed file paths, e.g. '[\"path\"]'", default=None),
                 _a("--json", "output JSON", action="store_true")]),
    CommandSpec("queue-edit", "queue", "edit", "edit a queued task's fields",
                _cmd_queue_edit,
                [_a("id", "task ID"),
                 _a("--title", "new title"),
                 _a("--description", "new description"),
                 _a("--priority", "new priority", type=int),
                 _a("--acceptance", "JSON array of acceptance criteria, e.g. '[\"criterion\"]'", default=None),
                 _a("--allowed-paths", "JSON array of allowed file paths, e.g. '[\"path\"]'", default=None),
                 _a("--json", "output JSON", action="store_true")]),
    CommandSpec("queue-list", "queue", "list", "list tasks in the queue",
                _cmd_queue_list,
                [_a("--state", "filter by state"),
                 _a("--include-archived", "include archived tasks", action="store_true"),
                 _a("--json", "output JSON", action="store_true")]),
    CommandSpec("queue-show", "queue", "show", "show task details",
                _cmd_queue_show,
                [_a("id", "task ID"), _a("--json", "output JSON", action="store_true")]),
    CommandSpec("queue-claim", "queue", "claim", "claim a specific task",
                _cmd_queue_claim,
                [_a("id", "task ID"),
                 _a("--worker", "worker name", required=True),
                 _a("--lease-seconds", "lease duration", type=int, default=1800),
                 _a("--json", "output JSON", action="store_true")]),
    CommandSpec("queue-claim-next", "queue", "claim-next", "claim the highest-priority queued task",
                _cmd_queue_claim_next,
                [_a("--worker", "worker name", required=True),
                 _a("--lease-seconds", "lease duration", type=int, default=1800),
                 _a("--json", "output JSON", action="store_true")]),
    CommandSpec("queue-release", "queue", "release", "release a claimed task back to queued (worker)",
                _cmd_queue_release,
                [_a("id", "task ID"),
                 _a("--worker", "worker name", required=True),
                 _a("--lease-token", "lease token from claim", required=True),
                 _a("--claim-version", "claim version from claim", type=int, required=True),
                 _a("--json", "output JSON", action="store_true")]),
    CommandSpec("queue-operator-release", "queue", "operator-release", "operator-forced release of a task",
                _cmd_queue_operator_release,
                [_a("id", "task ID"),
                 _a("--reason", "reason for release", default=None),
                 _a("--json", "output JSON", action="store_true")]),
    CommandSpec("queue-transition", "queue", "transition", "transition a task to a new state (worker-fenced)",
                _cmd_queue_transition,
                [_a("id", "task ID"),
                 _a("state", "target state"),
                 _a("--lease-token", "lease token from claim", required=True),
                 _a("--claim-version", "claim version from claim", type=int, required=True),
                 _a("--payload-json", "JSON object payload"),
                 _a("--json", "output JSON", action="store_true")]),
    CommandSpec("queue-events", "queue", "events", "list events for a task",
                _cmd_queue_events,
                [_a("id", "task ID"), _a("--json", "output JSON", action="store_true")]),
    CommandSpec("queue-status", "queue", "status", "queue summary per state",
                _cmd_queue_status, [_a("--json", "output JSON", action="store_true")]),
    CommandSpec("queue-archive", "queue", "archive", "soft-archive terminal tasks by state and age",
                _cmd_queue_archive,
                [_a("--state", "terminal state to archive (done, failed, cancelled)", required=True),
                 _a("--older-than", "archive tasks older than this many days", type=int, required=True),
                 _a("--json", "output JSON", action="store_true")]),
    CommandSpec("queue-brief", "queue", "brief", "render a complete worker brief for a task",
                _cmd_queue_brief,
                [_a("id", "task ID"),
                 _a("--branch", "branch name override (default kittybuilder/<task_id>)"),
                 _a("--json", "output JSON", action="store_true")]),
    CommandSpec("queue-attach-report", "queue", "attach-report", "attach a structured final report to a task",
                _cmd_queue_attach_report,
                [_a("id", "task ID"),
                 _a("--report-json", "report as a JSON object string"),
                 _a("--report-file", "path to a JSON report file"),
                 _a("--lease-token", "lease token (worker mode)"),
                 _a("--claim-version", "claim version (worker mode)", type=int),
                 _a("--operator-reason", "operator mode: reason for attaching without a lease"),
                 _a("--json", "output JSON", action="store_true")]),
    CommandSpec("queue-attach-pr", "queue", "attach-pr", "attach/update advisory PR metadata for a task",
                _cmd_queue_attach_pr,
                [_a("id", "task ID"),
                 _a("--pr", "PR number", type=int, required=True),
                 _a("--url", "PR URL"),
                 _a("--head-sha", "PR head commit SHA"),
                 _a("--checks-state", "CI checks state summary"),
                 _a("--review-state", "review state summary"),
                 _a("--json", "output JSON", action="store_true")]),
    CommandSpec("queue-sync-pr", "queue", "sync-pr",
                "advisory CI/review reconciliation into pr_links (no task mutation)",
                _cmd_queue_sync_pr, [_a("--json", "output JSON", action="store_true")]),
    CommandSpec("queue-reconcile-merges", "queue", "reconcile-merges",
                "promote tasks to done whose linked PR has merged (unlocks dependents)",
                _cmd_queue_reconcile_merges, [_a("--json", "output JSON", action="store_true")]),
    CommandSpec("queue-publish", "queue", "publish",
                "operator-gated: push task branch and create/update PR (never merges)",
                _cmd_queue_publish,
                [_a("id", "task ID"),
                 _a("--remote", "git remote (default: origin)", default="origin"),
                 _a("--base", "PR base branch (default: main)", default="main"),
                 _a("--title", "PR title (default: kittybuilder: <task title>)"),
                 _a("--dry-run", "print planned git/gh commands without executing", action="store_true"),
                 _a("--json", "output JSON", action="store_true")]),
    CommandSpec("queue-recover", "queue", "recover",
                "recovery scan: expired claimed → queued, expired running → blocked",
                _cmd_queue_recover, [_a("--json", "output JSON", action="store_true")]),
    CommandSpec("queue-operator-cancel", "queue", "operator-cancel",
                "operator cancel of a task without a lease (e.g. queued/blocked)",
                _cmd_queue_operator_cancel,
                [_a("id", "task ID"),
                 _a("--reason", "reason for cancellation"),
                 _a("--json", "output JSON", action="store_true")]),
    CommandSpec("queue-run", "queue", "run",
                "claim a task and run a worker command in its isolated worktree "
                "(shadow mode: no push, no PR)",
                _cmd_queue_run,
                [_a("id", "task ID"),
                 _a("--worker", "worker name", default="local-runner"),
                 _a("--model", "model identifier (metadata)"),
                 _a("--provider", "provider identifier (metadata)"),
                 _a("--timeout", "worker timeout in seconds", type=int, default=3600),
                 _a("--lease-seconds", "heartbeat lease duration", type=int, default=60),
                 _a("--heartbeat-seconds", "heartbeat interval", type=int, default=10),
                 _a("--json", "output JSON", action="store_true"),
                 _a("worker_command", "worker command after --", nargs="*")]),
    CommandSpec("queue-runs", "queue", "runs", "list run records",
                _cmd_queue_runs,
                [_a("--task", "filter by task ID"),
                 _a("--state", "filter by run state"),
                 _a("--json", "output JSON", action="store_true")]),
    CommandSpec("queue-show-run", "queue", "show-run", "show one run record",
                _cmd_queue_show_run,
                [_a("run_id", "run ID"),
                 _a("--log-tail", "print last N log lines", type=int, default=0),
                 _a("--json", "output JSON", action="store_true")]),
    CommandSpec("queue-cancel-run", "queue", "cancel-run", "request cancellation of an active run",
                _cmd_queue_cancel_run,
                [_a("run_id", "run ID"),
                 _a("--kill", "escalate to SIGKILL", action="store_true"),
                 _a("--json", "output JSON", action="store_true")]),
    CommandSpec("queue-clean-worktree", "queue", "clean-worktree", "remove a task worktree (refuses if dirty)",
                _cmd_queue_clean_worktree, [_a("id", "task ID")]),
    # -- initiative group ------------------------------------------------------
    CommandSpec("initiative-validate", "initiative", "validate", "validate an initiative manifest file",
                _cmd_initiative_validate,
                [_a("manifest", "path to the manifest JSON file")]),
    CommandSpec("initiative-apply", "initiative", "apply",
                "apply a manifest: create the initiative and one queue task per packet",
                _cmd_initiative_apply,
                [_a("manifest", "path to the manifest JSON file"),
                 _a("--dry-run", "validate and report without mutating", action="store_true"),
                 _a("--json", "output JSON", action="store_true")]),
    CommandSpec("initiative-list", "initiative", "list", "list initiatives",
                _cmd_initiative_list, [_a("--json", "output JSON", action="store_true")]),
    CommandSpec("initiative-show", "initiative", "show", "show an initiative and its packet-to-task mappings",
                _cmd_initiative_show,
                [_a("id", "initiative ID"), _a("--json", "output JSON", action="store_true")]),
    CommandSpec("initiative-status", "initiative", "status",
                "roll up packet eligibility and initiative status (KB-S1B)",
                _cmd_initiative_status,
                [_a("id", "initiative ID"), _a("--json", "output JSON", action="store_true")]),
    CommandSpec("initiative-attempts", "initiative", "attempts", "list packet attempts for an initiative",
                _cmd_initiative_attempts,
                [_a("id", "initiative ID"),
                 _a("packet", "packet ID (optional)", nargs="?"),
                 _a("--json", "output JSON", action="store_true")]),
    CommandSpec("initiative-start-attempt", "initiative", "start-attempt",
                "open the next attempt for a packet and persist its context bundle",
                _cmd_initiative_start_attempt,
                [_a("id", "initiative ID"),
                 _a("packet", "packet ID"),
                 _a("--json", "output JSON", action="store_true")]),
    CommandSpec("initiative-record-implementation", "initiative", "record-implementation",
                "attach a validated implementation result",
                _cmd_initiative_record,
                [_a("attempt_id", "attempt ID", type=int),
                 _a("--file", "path to the result JSON file", required=True),
                 _a("--json", "output JSON", action="store_true")]),
    CommandSpec("initiative-record-review", "initiative", "record-review",
                "attach a validated review result",
                _cmd_initiative_record,
                [_a("attempt_id", "attempt ID", type=int),
                 _a("--file", "path to the result JSON file", required=True),
                 _a("--json", "output JSON", action="store_true")]),
    CommandSpec("initiative-run-packet", "initiative", "run-packet",
                "drive one packet through the bounded implement/validate/review "
                "repair loop (shadow mode: no push, no PR)",
                _cmd_initiative_run_packet,
                [_a("id", "initiative ID"),
                 _a("packet", "packet ID"),
                 _a("--free", "use the free OpenCode adapter scripts as worker and reviewer; --model then forces one free model", action="store_true"),
                 _a("--worker-command", "worker command as a JSON array, e.g. '[\"opencode\", \"run\"]' (or use --free)", default=None),
                 _a("--review-command", "optional reviewer command as a JSON array (omit = validation-gated only)", default=None),
                 _a("--worker", "worker name", default="packet-loop"),
                 _a("--model", "model identifier (metadata)"),
                 _a("--provider", "provider identifier (metadata)"),
                 _a("--timeout", "worker timeout in seconds", type=int, default=3600),
                 _a("--watch", "print launch, attempt, artifact, and final state updates", action="store_true"),
                 _a("--json", "output JSON", action="store_true")]),
    CommandSpec("initiative-run-validation", "initiative", "run-validation",
                "run the packet's declared validation commands and record the verdict",
                _cmd_initiative_run_validation,
                [_a("attempt_id", "attempt ID", type=int),
                 _a("--cwd", "directory to run in (default: the task's runner worktree)"),
                 _a("--timeout", "per-command timeout in seconds", type=int, default=600),
                 _a("--json", "output JSON", action="store_true")]),
    CommandSpec("initiative-close-attempt", "initiative", "close-attempt", "close an open attempt with a terminal outcome",
                _cmd_initiative_close_attempt,
                [_a("attempt_id", "attempt ID", type=int),
                 _a("outcome", "succeeded | failed | aborted"),
                 _a("--json", "output JSON", action="store_true")]),
    CommandSpec("initiative-run", "initiative", "run",
                "drive an initiative to completion: loop eligible packets through "
                "implement/validate/review (S3b) then operator-gated publish (S4b)",
                _cmd_initiative_run,
                [_a("id", "initiative ID"),
                 _a("--free", "use the free OpenCode adapter scripts as worker and reviewer; --model then forces one free model", action="store_true"),
                 _a("--worker-command", "worker command as a JSON array, e.g. '[\"opencode\", \"run\"]' (or use --free)", default=None),
                 _a("--review-command", "optional reviewer command as a JSON array (omit = validation-gated only)", default=None),
                 _a("--worker", "worker name", default="packet-loop"),
                 _a("--model", "model identifier (metadata)"),
                 _a("--provider", "provider identifier (metadata)"),
                 _a("--timeout", "worker timeout in seconds", type=int, default=3600),
                 _a("--publish", "run KB-S4b publish (operator-gated push + PR) on each succeeded packet", action="store_true"),
                 _a("--max-attempts", "per-initiative attempt budget; exceeding it pauses the initiative", type=int, default=None),
                 _a("--max-runtime", "per-initiative wall-clock budget (seconds); exceeding it pauses the initiative", type=int, default=None),
                 _a("--json", "output JSON", action="store_true")]),
    CommandSpec("initiative-pause", "initiative", "pause", "pause the run loop for an initiative (operator gate)",
                _cmd_initiative_pause,
                [_a("id", "initiative ID"),
                 _a("--reason", "advisory pause reason", default=None)]),
    CommandSpec("initiative-resume", "initiative", "resume", "clear a pause so the run loop may proceed",
                 _cmd_initiative_resume, [_a("id", "initiative ID")]),
    CommandSpec("initiative-doctor", "initiative", "doctor",
                "read-only preflight: is it safe to run KittyBuilder right now?",
                _cmd_initiative_doctor, [_a("--json", "output JSON", action="store_true")]),
]


def build_parser() -> argparse.ArgumentParser:
    """Build the argparse tree from the declarative ``COMMANDS`` table."""
    parser = argparse.ArgumentParser(
        prog="kitty builder",
        description="KittyBuilder execution control plane with fenced queue and initiative workflows.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    group_subs: dict[str, argparse._SubParsersAction] = {}
    for spec in COMMANDS:
        if spec.group is None:
            p = sub.add_parser(spec.name, help=spec.help)
        else:
            if spec.group not in group_subs:
                gp = sub.add_parser(spec.group, help=_GROUP_HELP[spec.group])
                group_subs[spec.group] = gp.add_subparsers(
                    dest=_GROUP_SUBPARSER_DEST[spec.group], required=True
                )
            p = group_subs[spec.group].add_parser(spec.name, help=spec.help)
        for arg in spec.args:
            p.add_argument(arg.name, help=arg.help, **arg.kwargs)
        p.set_defaults(func=spec.handler)
    return parser


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


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

    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
