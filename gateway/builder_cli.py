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


def _init_queue_db() -> None:
    """Initialize the queue DB safely before command dispatch."""
    from gateway.builder_queue import init_db

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
    }
)


def _queue_disabled() -> bool:
    return os.environ.get("KITTY_BUILDER_QUEUE_ENABLED", "1") == "0"


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

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

    func = _resolve_func(args)
    return func(args)


if __name__ == "__main__":
    raise SystemExit(main())
