"""Autonomous campaign supervisor — stateless tick/status control plane.

The supervisor is a thin, stateless dispatcher for the existing KittyBuilder
machinery. It does not own a second state machine: eligibility, initiative
rollups, packet selection, leases, worktrees, attempts, validation, review and
publication all stay in their existing durable owners (``builder_initiative``,
``builder_queue``, ``builder_attempt``, ``builder_runner``). The supervisor
only decides *when* to dispatch canonical runs and returns truthful receipts
about what it did.

Walking-skeleton contract:

- A ``tick()`` holds exactly one OS lock (``fcntl.flock`` on a lockfile next
  to the queue DB) for the whole pass, deterministically selects eligible
  *active* initiatives (derived state ``active``, ordered by initiative id),
  picks each one's next eligible packet via ``builder_initiative.next_packet``
  (deterministic ``seq`` order), and detaches **no more than**
  :data:`MAX_RUNS_PER_TICK` canonical ``initiative run-packet`` loops.
- Duplicate ticks do nothing: a concurrent tick cannot acquire the lock and
  returns a ``locked`` receipt with no launches; a sequential re-tick finds
  the already-claimed tasks no longer ``queued`` and launches nothing.
- The launchd service never installs itself: :func:`render_supervisor_plist`
  is a pure renderer and the launcher only prints the plist to stdout.

Only two CLI verbs exist on the ``supervisor`` group (``tick``, ``status``).
launchd generation lives in the launcher script (``scripts/start_builder_supervisor.sh``),
not in the CLI, so the CLI surface stays fixed.
"""

from __future__ import annotations

import errno
import json
import os
import plistlib
import subprocess
import sys
from pathlib import Path
from typing import Any

from gateway import builder_initiative as bi
from gateway import builder_queue as bq
from gateway.builder_queue_runs import RUN_ACTIVE_STATES
from gateway.paths import BUILDER_QUEUE_DB

# One tick launches at most this many canonical runs. Bounded by contract;
# duplicate or concurrent ticks never exceed it.
MAX_RUNS_PER_TICK = 2

# Canonical worker identity recorded by the packet attempt loop.
SUPERVISOR_WORKER = "autonomous-supervisor"

# launchd registration for the periodic supervisor tick.
SUPERVISOR_LABEL = "com.kitty.builder.supervisor"
SUPERVISOR_START_INTERVAL = 900  # seconds between ticks; no KeepAlive
LOGIN_SAFE_PATH = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

# The canonical run is the free OpenCode worker adapter; it is the only
# executable the supervisor may dispatch. The env mirrors the free route's
# adapter env (see builder_cli._free_adapter_env) without importing the CLI.
_FREE_ADAPTER_SCRIPT = "scripts/kittybuilder_opencode_worker.sh"
_FREE_REVIEWER_SCRIPT = "scripts/kittybuilder_opencode_reviewer.sh"


class SupervisorError(RuntimeError):
    """Raised when a supervisor operation cannot run safely."""


def default_db_path() -> Path:
    return BUILDER_QUEUE_DB


def _lock_path(db_path: Path | None) -> Path:
    """One OS lock per Builder data dir, alongside the queue DB."""
    queue_db = Path(db_path) if db_path is not None else default_db_path()
    return queue_db.parent / "supervisor.lock"


class SupervisorLock:
    """Non-blocking exclusive flock over the supervisor lockfile.

    Exactly one OS lock per tick: acquiring it fails fast when another tick
    (or a test-held lock) is already running, which is what makes duplicate
    concurrent ticks a truthful no-op.
    """

    def __init__(self, db_path: Path | None = None) -> None:
        self._path = _lock_path(db_path)
        self._fh: Any = None
        self.acquired = False

    @property
    def path(self) -> Path:
        return self._path

    def __enter__(self) -> "SupervisorLock":
        import fcntl

        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(self._path, "a+", encoding="utf-8")
        try:
            fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.acquired = True
        except OSError as exc:
            self._fh.close()
            self._fh = None
            if exc.errno not in {errno.EAGAIN, errno.EACCES}:
                raise
        return self

    def __exit__(self, *_exc_info: Any) -> None:
        if self._fh is not None:
            import fcntl

            try:
                fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
            finally:
                self._fh.close()
                self._fh = None


def canonical_worker_command(repo_root: Path | None = None) -> list[str]:
    """The single canonical worker command the supervisor may launch."""
    root = (repo_root or repo_root_default()).resolve()
    script = root / _FREE_ADAPTER_SCRIPT
    if not script.is_file():
        raise SupervisorError(f"canonical worker adapter missing: {script}")
    return ["bash", str(script)]


def canonical_reviewer_command(repo_root: Path | None = None) -> list[str]:
    """The canonical free reviewer command used by the packet loop."""
    root = (repo_root or repo_root_default()).resolve()
    script = root / _FREE_REVIEWER_SCRIPT
    if not script.is_file():
        raise SupervisorError(f"canonical reviewer adapter missing: {script}")
    return ["bash", str(script)]


def canonical_adapter_env(model: str | None = None) -> dict[str, str]:
    """Child-only adapter env for the canonical free OpenCode worker."""
    return {
        "KITTYBUILDER_AGENT": "free-builder",
        "KITTYBUILDER_REVIEW_AGENT": "free-reviewer",
        "KITTYBUILDER_MODEL": model or "",
        "KITTYBUILDER_REVIEW_MODEL": "",
        "KITTYBUILDER_MODELS": "",
        "KITTYBUILDER_REVIEW_MODELS": "",
    }


def repo_root_default() -> Path:
    """Canonical repo root: gateway/ -> kitty/."""
    return Path(__file__).resolve().parents[1]


def active_initiatives(db_path: Path | None = None) -> list[dict[str, Any]]:
    """Deterministically ordered initiatives whose derived state is ``active``.

    Uses the read-only rollup from ``builder_initiative.list_initiatives``
    (which derives state over durable task state) and sorts by initiative id
    so selection is stable across ticks regardless of insertion order.
    """
    initiatives = bi.list_initiatives(db_path)
    active = [
        initiative
        for initiative in initiatives
        if (initiative.get("health_summary") or {}).get("state")
        == bi.INITIATIVE_ACTIVE
    ]
    return sorted(active, key=lambda i: str(i["id"]))


def _validate_max_runs(max_runs: int) -> None:
    if max_runs < 1 or max_runs > MAX_RUNS_PER_TICK:
        raise ValueError(f"max_runs must be between 1 and at most {MAX_RUNS_PER_TICK}")


def _select_packets(
    db_path: Path | None = None, *, max_runs: int = MAX_RUNS_PER_TICK
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Pick at most one next packet per active initiative, deterministically."""
    _validate_max_runs(max_runs)
    selected: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for initiative in active_initiatives(db_path):
        if len(selected) >= max_runs:
            break
        initiative_id = str(initiative["id"])
        packet = bi.next_packet(initiative_id, db_path=db_path)
        if packet is None:
            skipped.append({
                "initiative_id": initiative_id, "packet_id": None,
                "task_id": None, "reason": "no_eligible_packet",
            })
            continue
        task = bq.get_task(str(packet["task_id"]), db_path=db_path)
        if task is None:
            skipped.append({
                "initiative_id": initiative_id, "packet_id": str(packet["packet_id"]),
                "task_id": str(packet["task_id"]), "reason": "task_missing",
            })
            continue
        # ``next_packet`` is the canonical eligibility oracle. It may return a
        # fenced BLOCKED packet with a stale attempt specifically so run_packet
        # can reconcile/recover it; do not re-derive eligibility from task state.
        active_runs = [
            run for run in bq.list_runs(str(packet["task_id"]), db_path=db_path)
            if run["state"] in RUN_ACTIVE_STATES
        ]
        if active_runs:
            skipped.append({
                "initiative_id": initiative_id, "packet_id": str(packet["packet_id"]),
                "task_id": str(packet["task_id"]), "reason": "active_run_exists",
                "run_id": str(active_runs[0]["id"]),
            })
            continue
        selected.append(packet)
    return selected, skipped


def _launch_run(
    packet: dict[str, Any],
    *,
    repo_root: Path | None = None,
    db_path: Path | None = None,
    worker: str = SUPERVISOR_WORKER,
    model: str | None = None,
) -> dict[str, Any]:
    """Detach one packet through the canonical Builder run-packet CLI.

    The detached child owns ``builder_loop.run_packet`` and therefore creates
    the attempt bundle, validation evidence, reviewer binding, and durable run
    state. The supervisor owns only dispatch and returns promptly.
    """
    del worker, model  # the canonical free CLI owns worker/model routing
    root = (repo_root or repo_root_default()).resolve()
    kitty = root / "kitty"
    if not kitty.is_file():
        raise SupervisorError(f"Kitty launcher missing: {kitty}")

    initiative_id = str(packet["initiative_id"])
    packet_id = str(packet["packet_id"])
    task_id = str(packet["task_id"])
    command = [
        str(kitty), "builder", "initiative", "run-packet",
        initiative_id, packet_id, "--free", "--json",
    ]
    log_dir = root / "data" / "kittybuilder" / "supervisor-launch"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{initiative_id}-{packet_id}.log"
    child_env = os.environ.copy()
    if db_path is not None:
        child_env["KITTY_BUILDER_DATA_DIR"] = str(Path(db_path).resolve().parent)
    with log_path.open("ab") as log_handle:
        process = subprocess.Popen(
            command,
            cwd=str(root),
            stdin=subprocess.DEVNULL,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            env=child_env,
            shell=False,
            start_new_session=True,
            close_fds=True,
        )
    return {
        "status": "dispatched",
        "launcher_pid": process.pid,
        "initiative_id": initiative_id,
        "packet_id": packet_id,
        "task_id": task_id,
        "log_path": str(log_path),
    }


def tick(
    *,
    db_path: Path | None = None,
    repo_root: Path | None = None,
    worker: str = SUPERVISOR_WORKER,
    model: str | None = None,
    max_runs: int = MAX_RUNS_PER_TICK,
) -> dict[str, Any]:
    """Run one supervisor tick under a single OS lock and return a receipt.

    The receipt is truthful about the lock, every scanned initiative, every
    launched run, and every skipped candidate with its reason. A duplicate
    concurrent tick returns ``status: "locked"`` with no launches.
    """
    _validate_max_runs(max_runs)
    with SupervisorLock(db_path) as lock:
        if not lock.acquired:
            return {
                "status": "locked",
                "lock": {"acquired": False, "path": str(lock.path)},
                "max_runs": max_runs,
                "scanned_initiatives": [],
                "launched": [],
                "skipped": [],
                "duplicate_tick": True,
            }
        scanned = [
            {"initiative_id": str(initiative["id"]), "state": bi.INITIATIVE_ACTIVE}
            for initiative in active_initiatives(db_path)
        ]
        selected, skipped = _select_packets(db_path, max_runs=max_runs)
        launched: list[dict[str, Any]] = []
        for packet in selected:
            entry: dict[str, Any] = {
                "initiative_id": str(packet["initiative_id"]),
                "packet_id": str(packet["packet_id"]),
                "task_id": str(packet["task_id"]),
            }
            try:
                dispatch = _launch_run(
                    packet,
                    repo_root=repo_root,
                    db_path=db_path,
                    worker=worker,
                    model=model,
                )
            except Exception as exc:  # fail loud, but keep other launches going
                entry["dispatch"] = None
                entry["error"] = f"{type(exc).__name__}: {exc}"
            else:
                entry["dispatch"] = dispatch
            launched.append(entry)
        return {
            "status": "error" if any("error" in item for item in launched) else "ok",
            "lock": {"acquired": True, "path": str(lock.path)},
            "max_runs": max_runs,
            "scanned_initiatives": scanned,
            "launched": launched,
            "skipped": skipped,
            "duplicate_tick": False,
        }


def status(db_path: Path | None = None) -> dict[str, Any]:
    """Read-only projection: initiatives, eligible work, active runs, lock."""
    initiatives = bi.list_initiatives(db_path)
    rollup: list[dict[str, Any]] = []
    for initiative in initiatives:
        initiative_id = str(initiative["id"])
        derived_state = (initiative.get("health_summary") or {}).get("state")
        eligible = bi.eligible_packets(initiative_id, db_path=db_path)
        rollup.append(
            {
                "initiative_id": initiative_id,
                "stored_state": initiative.get("state"),
                "derived_state": derived_state,
                "eligible_packets": [
                    {
                        "packet_id": str(p["packet_id"]),
                        "task_id": str(p["task_id"]),
                        "seq": p["seq"],
                    }
                    for p in eligible
                ],
            }
        )
    active_runs: list[dict[str, Any]] = []
    for state in sorted(RUN_ACTIVE_STATES):
        for run in bq.list_runs(state=state, db_path=db_path):
            active_runs.append(
                {
                    "run_id": str(run["id"]),
                    "task_id": str(run["task_id"]),
                    "state": run["state"],
                    "worker": run.get("worker"),
                }
            )
    return {
        "lock": {"path": str(_lock_path(db_path))},
        "initiatives": rollup,
        "active_runs": active_runs,
    }


# ---------------------------------------------------------------------------
# launchd plist rendering (pure; never installs)
# ---------------------------------------------------------------------------


def render_supervisor_plist(repo_root: Path | None = None) -> dict:
    """Render the launchd plist dict for the periodic supervisor tick.

    Contract (matches the walking-skeleton criteria):

    - ``RunAtLoad`` True, ``StartInterval`` 900, and **no** ``KeepAlive``.
    - ``PATH`` is a fixed login-safe value; no secrets and no env passthrough.
    - ``WorkingDirectory`` is the canonical repo root.
    - stdout/stderr go to fixed logs under ``logs/builder/``.
    - ``ProgramArguments`` is the fixed launcher: ``start_builder_supervisor.sh tick``.
    """
    root = (repo_root or repo_root_default()).resolve()
    out_log = root / "logs" / "builder" / "supervisor.log"
    err_log = root / "logs" / "builder" / "supervisor.err.log"
    return {
        "Label": SUPERVISOR_LABEL,
        "ProgramArguments": [
            "/bin/bash",
            str(root / "scripts" / "start_builder_supervisor.sh"),
            "tick",
        ],
        "WorkingDirectory": str(root),
        "EnvironmentVariables": {"PATH": LOGIN_SAFE_PATH},
        "RunAtLoad": True,
        "StartInterval": SUPERVISOR_START_INTERVAL,
        "StandardOutPath": str(out_log),
        "StandardErrorPath": str(err_log),
    }


def render_supervisor_plist_bytes(repo_root: Path | None = None) -> bytes:
    """Serialize the supervisor plist to XML bytes (never writes a file)."""
    return plistlib.dumps(render_supervisor_plist(repo_root))


def main(argv: list[str] | None = None) -> int:
    """Internal launcher entrypoint (used by start_builder_supervisor.sh).

    Only ``launchd-plist`` prints the rendered plist to stdout; there is no
    install/bootout/status launchctl surface here — the tests and the design
    both forbid the service from installing itself.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "launchd-plist":
        sys.stdout.buffer.write(render_supervisor_plist_bytes(args.repo_root))
        sys.stdout.buffer.write(b"\n")
        return 0
    if args.command == "tick":
        if os.environ.get("KITTY_BUILDER_QUEUE_ENABLED", "1") == "0":
            print("error: KittyBuilder queue is disabled; refusing supervisor tick", file=sys.stderr)
            return 1
        receipt = tick(max_runs=args.max_runs)
        print(json.dumps(receipt, indent=2, default=str, sort_keys=True))
        return 0 if receipt["status"] in {"ok", "locked"} else 1
    if args.command == "status":
        print(json.dumps(status(), indent=2, default=str, sort_keys=True))
        return 0
    return 2


def _build_parser() -> Any:
    import argparse

    parser = argparse.ArgumentParser(
        prog="python -m gateway.builder_supervisor",
        description="Autonomous supervisor launcher (tick/status/launchd-plist).",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    tick = sub.add_parser("tick", help="run one supervisor tick")
    tick.add_argument(
        "--max-runs",
        type=int,
        default=MAX_RUNS_PER_TICK,
        help=f"max canonical runs per tick (default: {MAX_RUNS_PER_TICK})",
    )
    sub.add_parser("status", help="read-only supervisor projection")
    launchd = sub.add_parser("launchd-plist", help="print the launchd plist XML")
    launchd.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="canonical repo root (default: this checkout)",
    )
    return parser


if __name__ == "__main__":
    os.environ.setdefault("KITTY_BUILDER_QUEUE_ENABLED", "1")
    raise SystemExit(main())
