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
  to the queue DB) for the whole pass, deterministically scans operator-active
  initiatives (stored state ``active``, ordered by initiative id), then asks
  ``builder_initiative.next_packet`` for each initiative's canonical runnable
  or fenced recovery candidate and detaches **no more than**
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
import hashlib
import json
import os
import plistlib
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from gateway import builder_attempt as ba
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


def _task_dispatch_lock_path(task_id: str, db_path: Path | None) -> Path:
    """Stable per-task lock path used only to fence duplicate supervisor spawns."""
    queue_db = Path(db_path) if db_path is not None else default_db_path()
    digest = hashlib.sha256(task_id.encode("utf-8")).hexdigest()[:24]
    return queue_db.parent / "dispatch-locks" / f"{digest}.lock"


class TaskDispatchLock:
    """Process-lifetime fence for one supervisor-dispatched task.

    The parent acquires this before Popen and passes the descriptor to the
    detached Kitty process. The parent then closes its copy; the child keeps
    the lock until the packet CLI exits. This prevents a later supervisor tick
    from spawning the same task while durable Builder startup is still in
    progress, without inventing a second queue state machine.
    """

    def __init__(self, task_id: str, db_path: Path | None = None) -> None:
        self._path = _task_dispatch_lock_path(task_id, db_path)
        self._fh: Any = None
        self.acquired = False

    @property
    def path(self) -> Path:
        return self._path

    @property
    def fileno(self) -> int:
        if self._fh is None:
            raise RuntimeError("dispatch lock is not open")
        return self._fh.fileno()

    def __enter__(self) -> "TaskDispatchLock":
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

    def handoff_to_child(self) -> None:
        """Close only the parent fd after Popen; the child keeps the flock."""
        if self._fh is None or not self.acquired:
            raise RuntimeError("cannot hand off an unacquired dispatch lock")
        self._fh.close()
        self._fh = None
        self.acquired = False

    def __exit__(self, *_exc_info: Any) -> None:
        if self._fh is not None:
            import fcntl
            try:
                fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
            finally:
                self._fh.close()
            self._fh = None


def _task_dispatch_is_locked(task_id: str, db_path: Path | None) -> bool:
    """Return whether another live supervisor child owns this task fence."""
    with TaskDispatchLock(task_id, db_path) as lock:
        return not lock.acquired


def _scheduler_enabled() -> bool | None:
    """Return launchd scheduler truth: loaded, absent/disabled, or unknown."""
    if os.environ.get("KITTY_BUILDER_QUEUE_ENABLED", "1") == "0":
        return False
    try:
        result = subprocess.run(
            ["launchctl", "print", f"gui/{os.getuid()}/{SUPERVISOR_LABEL}"],
            capture_output=True, text=True, timeout=2, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode == 0:
        return True
    detail = (result.stderr or "").lower()
    if "could not find service" in detail or "not found" in detail:
        return False
    return None


def _wait_for_durable_claim(
    task_id: str, process: subprocess.Popen[Any], *, initial_claim_version: int,
    db_path: Path | None, timeout_seconds: float = 10.0,
) -> dict[str, Any]:
    """Wait until the detached child has durably claimed its queue task."""
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        task = bq.get_task(task_id, db_path=db_path)
        if task is not None and int(task.get("claim_version") or 0) > initial_claim_version:
            return task
        if process.poll() is not None:
            raise SupervisorError(f"Builder child {process.pid} exited before durably claiming task {task_id}")
        time.sleep(0.05)
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    else:
        try:
            process.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=2.0)
    raise SupervisorError(f"Builder child {process.pid} did not durably claim task {task_id} within {timeout_seconds:g}s")


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
    """Deterministically ordered initiatives whose operator state is ``active``.

    Stored initiative state is the operator-owned execution gate. Derived
    health is intentionally not a dispatch gate: it can be ``paused`` when
    ordinary eligibility is empty even though ``next_packet`` exposes a fenced
    recovery candidate. Packet runnability stays owned by ``next_packet``.
    """
    initiatives = bi.list_initiative_gates(db_path)
    active = [
        initiative
        for initiative in initiatives
        if initiative.get("state") == bi.INITIATIVE_ACTIVE
        and not initiative.get("superseded_by")
    ]
    return sorted(active, key=lambda i: str(i["id"]))


def _validate_max_runs(max_runs: int) -> None:
    if max_runs < 1 or max_runs > MAX_RUNS_PER_TICK:
        raise ValueError(f"max_runs must be between 1 and at most {MAX_RUNS_PER_TICK}")


def _dispatch_candidate(
    initiative_id: str, db_path: Path | None
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """The one packet a tick would dispatch for this initiative, or why not.

    Single definition of "dispatchable", shared by the launching path and by
    the read-only projection. Two definitions drift, and a projection that
    disagrees with the launcher tells the operator one number while the tick
    does something else — which is exactly what a supervisor must never do.

    Note that ``BLOCKED`` is dispatchable: ``next_packet`` returns fenced
    recovery candidates, and re-running them is how blocked work recovers.
    """
    packet = bi.next_packet(initiative_id, db_path=db_path)
    if packet is None:
        return None, {
            "initiative_id": initiative_id, "packet_id": None,
            "task_id": None, "reason": "no_eligible_packet",
        }
    task = bq.get_task(str(packet["task_id"]), db_path=db_path)
    if task is None:
        return None, {
            "initiative_id": initiative_id, "packet_id": str(packet["packet_id"]),
            "task_id": str(packet["task_id"]), "reason": "task_missing",
        }
    task_state = str(task["state"])
    if _task_dispatch_is_locked(str(packet["task_id"]), db_path):
        return None, {
            "initiative_id": initiative_id,
            "packet_id": str(packet["packet_id"]),
            "task_id": str(packet["task_id"]),
            "reason": "dispatch_in_progress",
        }
    if task_state not in {bq.QUEUED, bq.BLOCKED}:
        return None, {
            "initiative_id": initiative_id, "packet_id": str(packet["packet_id"]),
            "task_id": str(packet["task_id"]),
            "reason": "task_state_not_dispatchable",
            "task_state": task_state,
        }
    # builder_loop.run_packet accepts a BLOCKED task only when a stale open
    # attempt paired with a dead runner explains the block; anything else it
    # refuses with "operator release is required". Dispatching those anyway
    # burns a tick per packet forever while the receipt claims a launch, so
    # the same precondition is asked here instead of discovered in a log.
    if task_state == bq.BLOCKED and not ba.list_stale_attempts(
        initiative_id, str(packet["packet_id"]), db_path=db_path
    ):
        return None, {
            "initiative_id": initiative_id, "packet_id": str(packet["packet_id"]),
            "task_id": str(packet["task_id"]),
            "reason": "needs_operator_release",
            "task_state": task_state,
        }
    active_runs = [
        run for run in bq.list_runs(str(packet["task_id"]), db_path=db_path)
        if run["state"] in RUN_ACTIVE_STATES
    ]
    if active_runs:
        return None, {
            "initiative_id": initiative_id, "packet_id": str(packet["packet_id"]),
            "task_id": str(packet["task_id"]), "reason": "active_run_exists",
            "run_id": str(active_runs[0]["id"]),
        }
    return packet, None


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
        packet, skip = _dispatch_candidate(str(initiative["id"]), db_path)
        if packet is None:
            skipped.append(skip)  # type: ignore[arg-type]
            continue
        selected.append(packet)
    return selected, skipped


def dispatchable_counts(db_path: Path | None = None) -> dict[str, int]:
    """How much work a tick could start now, and how much its project blocks.

    ``now`` is what ticks would actually dispatch if they ran until nothing
    was left; ``on_hold`` is work that is dispatchable in every respect except
    that its initiative is paused, so no tick will ever pick it up. Both use
    :func:`_dispatch_candidate`, so these numbers cannot disagree with what a
    tick does.
    """
    now = 0
    on_hold = 0
    for initiative in bi.list_initiative_gates(db_path):
        if initiative.get("superseded_by"):
            continue
        stored_state = initiative.get("state")
        if stored_state not in (bi.INITIATIVE_ACTIVE, bi.INITIATIVE_PAUSED):
            continue
        packet, _ = _dispatch_candidate(str(initiative["id"]), db_path)
        if packet is None:
            continue
        if stored_state == bi.INITIATIVE_ACTIVE:
            now += 1
        else:
            on_hold += 1
    return {"now": now, "on_hold": on_hold}


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

    Before launching, verifies the task is still in a dispatchable state.
    The supervisor holds an exclusive lock during this check-and-launch
    window, so no other tick can change the task state concurrently.
    """
    del worker, model  # the canonical free CLI owns worker/model routing
    root = (repo_root or repo_root_default()).resolve()
    kitty = root / "kitty"
    if not kitty.is_file():
        raise SupervisorError(f"Kitty launcher missing: {kitty}")

    initiative_id = str(packet["initiative_id"])
    packet_id = str(packet["packet_id"])
    task_id = str(packet["task_id"])

    task = bq.get_task(task_id, db_path=db_path)
    if task is None:
        raise SupervisorError(
            f"task {task_id} disappeared before launch"
        )
    task_state = str(task["state"])
    initial_claim_version = int(task.get("claim_version") or 0)
    if task_state not in {bq.QUEUED, bq.BLOCKED}:
        raise SupervisorError(
            f"task {task_id} is {task_state}, not dispatchable; "
            "another process claimed it"
        )
    if task_state == bq.BLOCKED and not ba.list_stale_attempts(
        initiative_id, packet_id, db_path=db_path
    ):
        raise SupervisorError(
            f"blocked task {task_id} has no stale attempt; "
            "operator release is required"
        )

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
    with TaskDispatchLock(task_id, db_path) as dispatch_lock:
        if not dispatch_lock.acquired:
            raise SupervisorError(
                f"task {task_id} already has a supervisor dispatch in progress"
            )
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
                pass_fds=(dispatch_lock.fileno,),
            )
        dispatch_lock.handoff_to_child()
    claimed = _wait_for_durable_claim(
        task_id, process, initial_claim_version=initial_claim_version, db_path=db_path
    )
    return {
        "status": "dispatched",
        "launcher_pid": process.pid,
        "claim_version": int(claimed["claim_version"]),
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


def active_runs_summary(db_path: Path | None = None) -> list[dict[str, Any]]:
    """Return only currently-active run facts without scanning initiatives."""
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
    return active_runs


def budget_summary(ledger_db_path: Path | str | None = None) -> dict[str, Any]:
    """Expose the existing compute-governor weekly ledger for Builder UI."""
    from gateway import compute_governor as cg

    config = cg.load_reserve_config(cg.ROOT_CONFIG_PATH)
    ledger_path = Path(ledger_db_path) if ledger_db_path is not None else cg.default_db_path()
    cg.init_db(ledger_path)
    ledger = cg.weekly_ledger(ledger_path)
    budget = float(config["weekly_budget_cad"])
    spent = float(ledger["estimated_usage_cad"])
    return {
        "weekly_budget_cad": budget,
        "estimated_spend_cad": spent,
        "remaining_cad": max(budget - spent, 0.0),
        "runs": int(ledger["runs"]),
        "retries": int(ledger["retries"]),
        "basis": ledger["basis"],
    }


# ---------------------------------------------------------------------------
# Preflight — read-only pre-launch review of the next packet.
# ---------------------------------------------------------------------------

PREFLIGHT_RUN = "run"
PREFLIGHT_BLOCKED = "blocked"
PREFLIGHT_REFUSE = "refuse"


def _repo_head(repo_root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=10,
    )
    sha = result.stdout.strip()
    if result.returncode != 0 or len(sha) != 40:
        detail = result.stderr.strip() or result.stdout.strip() or "HEAD unavailable"
        raise SupervisorError(f"cannot resolve current repo HEAD: {detail}")
    return sha


def _packet_route(packet: dict[str, Any], cg: Any) -> str:
    policy = packet.get("policy") or {}
    routing = policy.get("routing") or {}
    explicit = routing.get("route")
    if explicit in cg.ROUTE_MODELS:
        return str(explicit)
    configured_model = routing.get("model")
    for route, model in cg.ROUTE_MODELS.items():
        if configured_model == model:
            return route
    return cg.ROUTE_FREE


def preflight_packet(
    initiative_id: str,
    packet_id: str,
    *,
    db_path: Path | None = None,
    repo_root: Path | None = None,
    ledger_db_path: Path | str | None = None,
) -> dict[str, Any]:
    """Read-only packet review before Builder creates an attempt or run.

    This deliberately reuses the durable initiative packet, manifest validator,
    eligibility derivation, retry accounting, and compute governor. It never
    changes task/run/attempt state.
    """
    from gateway import compute_governor as cg

    initiative = bi.get_initiative(initiative_id, db_path=db_path)
    if initiative is None:
        return {
            "action": PREFLIGHT_REFUSE,
            "route": None,
            "estimated_cost_cad": 0.0,
            "cost_basis": "local estimate — not a provider invoice",
            "reasons": [f"Initiative {initiative_id} no longer exists."],
            "packet": {"initiative_id": initiative_id, "packet_id": packet_id},
            "budget": budget_summary(ledger_db_path),
            "eligibility": {"state": "unavailable", "blocked_by": []},
            "data_quality": {"state": "invalid", "issues": ["initiative missing"]},
        }

    target = next(
        (packet for packet in initiative.get("packets", []) if packet.get("packet_id") == packet_id),
        None,
    )
    if target is None:
        return {
            "action": PREFLIGHT_REFUSE,
            "route": None,
            "estimated_cost_cad": 0.0,
            "cost_basis": "local estimate — not a provider invoice",
            "reasons": [f"Packet {packet_id} is not part of initiative {initiative_id}."],
            "packet": {"initiative_id": initiative_id, "packet_id": packet_id},
            "budget": budget_summary(ledger_db_path),
            "eligibility": {"state": "unavailable", "blocked_by": []},
            "data_quality": {"state": "invalid", "issues": ["packet missing"]},
        }

    issues: list[str] = []
    manifest_errors = bi.validate_manifest(initiative.get("manifest") or {})
    issues.extend(f"manifest: {error}" for error in manifest_errors)
    if not target.get("task_id"):
        issues.append("packet has no durable task id")
    if not target.get("base_sha"):
        issues.append("packet has no immutable base SHA")
    if not target.get("acceptance_criteria"):
        issues.append("packet has no acceptance criteria")
    if not target.get("allowed_paths"):
        issues.append("packet has no allowed paths")
    if not target.get("validation_commands"):
        issues.append("packet has no declared validation commands")

    task_id = target.get("task_id")
    task = bq.get_task(task_id, db_path=db_path) if task_id else None
    if task_id and task is None:
        issues.append(f"durable task {task_id} is missing")

    packet_states = bi._read_packets_with_states(initiative_id, db_path)
    by_id = {packet["packet_id"]: packet for packet in packet_states}
    state_packet = by_id.get(packet_id)
    exhausted = bi._exhausted_packet_ids(initiative_id, packet_states, db_path=db_path)
    eligibility = bi.derive_packet_eligibility(
        packet_id=packet_id,
        task_state=(state_packet or {}).get("state"),
        depends_on=(state_packet or target).get("depends_on") or [],
        task_states={pid: packet.get("state") for pid, packet in by_id.items()},
        exhausted_packet_ids=exhausted,
    )

    reasons: list[str] = []
    stored_state = str(initiative.get("state") or bi.INITIATIVE_ACTIVE)
    if stored_state != bi.INITIATIVE_ACTIVE:
        reason = initiative.get("pause_reason") if stored_state == bi.INITIATIVE_PAUSED else None
        reasons.append(
            f"Initiative is {stored_state}." + (f" {reason}" if reason else "")
        )
    if issues:
        reasons.extend(f"Unsafe packet input: {issue}." for issue in issues)
    if eligibility.get("state") != "eligible":
        blocked_by = eligibility.get("blocked_by") or []
        if blocked_by:
            reasons.append(
                f"Packet is {eligibility.get('state')}; blocked by {', '.join(map(str, blocked_by[:5]))}."
            )
        else:
            reasons.append(f"Packet is {eligibility.get('state')}." )

    base_sha = target.get("base_sha")
    current_head: str | None = None
    if repo_root is not None and base_sha:
        try:
            current_head = _repo_head(Path(repo_root).resolve())
        except Exception as exc:
            reasons.append(f"Could not verify packet freshness: {exc}.")
        else:
            if current_head != base_sha:
                reasons.append(
                    f"Packet base {str(base_sha)[:12]} is stale; current code is {current_head[:12]}."
                )

    requested_route = _packet_route(target, cg)
    cost = cg.preflight_route_and_cost(
        requested_route=requested_route,
        db_path=ledger_db_path,
    )
    if requested_route != cg.ROUTE_FREE and not cost["within_budget"]:
        reasons.append(
            f"Estimated CAD {cost['estimated_cost_cad']:.4f} exceeds the remaining weekly budget "
            f"of CAD {cost['remaining_cad']:.4f}."
        )

    fatal_missing = task is None or bool(manifest_errors)
    if fatal_missing:
        action = PREFLIGHT_REFUSE
    elif reasons:
        action = PREFLIGHT_BLOCKED
    else:
        action = PREFLIGHT_RUN

    dispatch_hash = hashlib.sha256(
        f"{initiative_id}/{packet_id}/{base_sha or 'none'}".encode("utf-8")
    ).hexdigest()
    return {
        "action": action,
        "route": cost["projected_route"],
        "estimated_cost_cad": cost["estimated_cost_cad"],
        "cost_basis": cost["estimated_cost_cad_label"],
        "reasons": reasons,
        "packet": {
            "initiative_id": initiative_id,
            "packet_id": packet_id,
            "task_id": task_id,
            "base_sha": base_sha,
            "current_head": current_head,
        },
        "budget": {
            "weekly_budget_cad": cost["weekly_budget_cad"],
            "remaining_cad": cost["remaining_cad"],
            "within_budget": cost["within_budget"],
            "basis": "local estimate — not a provider invoice",
        },
        "eligibility": eligibility,
        "data_quality": {
            "state": "complete" if not issues else ("invalid" if manifest_errors else "partial"),
            "issues": issues,
        },
        "dispatch_hash": dispatch_hash,
    }


def scheduler_status(
    repo_root: Path | None = None, *, plist_path: Path | None = None
) -> dict[str, Any]:
    """Read the supported macOS LaunchAgent state without mutating it.

    ``installed`` means the expected plist exists. ``loaded`` comes from
    ``launchctl print`` for the current GUI session. ``healthy`` additionally
    requires the installed plist to match Kitty's canonical scheduler contract.
    We intentionally do not invent last-tick or next-run timestamps: launchd
    does not provide either as durable Kitty evidence.
    """
    root = (repo_root or repo_root_default()).resolve()
    agent_path = plist_path or (
        Path.home() / "Library" / "LaunchAgents" / f"{SUPERVISOR_LABEL}.plist"
    )
    result: dict[str, Any] = {
        "supported": sys.platform == "darwin",
        "installed": agent_path.exists(),
        "loaded": False,
        "healthy": False,
        "label": SUPERVISOR_LABEL,
        "plist_path": str(agent_path),
        "start_interval_seconds": None,
        "run_at_load": None,
        "last_exit_status": None,
        "pid": None,
        "last_tick_at": None,
        "next_run_at": None,
        "reason": None,
    }
    if sys.platform != "darwin":
        result["reason"] = "scheduled Builder execution is supported on macOS launchd only"
        return result
    if not agent_path.exists():
        result["reason"] = "Builder LaunchAgent plist is not installed"
        return result
    try:
        installed = plistlib.loads(agent_path.read_bytes())
    except Exception as exc:
        result["reason"] = f"Builder LaunchAgent plist is unreadable: {exc}"
        return result

    result["start_interval_seconds"] = installed.get("StartInterval")
    result["run_at_load"] = installed.get("RunAtLoad")
    expected = render_supervisor_plist(root)
    contract_keys = ("Label", "ProgramArguments", "WorkingDirectory", "RunAtLoad", "StartInterval")
    contract_ok = all(installed.get(key) == expected.get(key) for key in contract_keys) and "KeepAlive" not in installed

    domain = f"gui/{os.getuid()}/{SUPERVISOR_LABEL}"
    try:
        proc = subprocess.run(
            ["launchctl", "print", domain], capture_output=True, text=True, timeout=5
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        result["reason"] = f"could not inspect LaunchAgent: {exc}"
        return result
    if proc.returncode == 0:
        result["loaded"] = True
        for raw in proc.stdout.splitlines():
            line = raw.strip()
            if line.startswith("pid = "):
                try:
                    result["pid"] = int(line.split("=", 1)[1].strip())
                except ValueError:
                    pass
            elif line.startswith("last exit code = "):
                try:
                    result["last_exit_status"] = int(line.split("=", 1)[1].strip())
                except ValueError:
                    pass
    if not contract_ok:
        result["reason"] = "installed LaunchAgent does not match Kitty's supported scheduler contract"
    elif not result["loaded"]:
        result["reason"] = "Builder LaunchAgent is installed but not loaded"
    elif result["last_exit_status"] not in (None, 0):
        result["reason"] = f"Builder LaunchAgent last exited with status {result['last_exit_status']}"
    else:
        result["healthy"] = True
    return result


def control_plane_summary(db_path: Path | None = None) -> dict[str, Any]:
    """Cheap-enough Work poll projection without the full initiative rollup.

    The old HTTP route called ``status()`` and then ``dispatchable_counts()``,
    performing two independent per-initiative scans every ten seconds. Work only
    needs active runs, launchable counts, lock identity, and budget truth.
    """
    counts = dispatchable_counts(db_path)
    return {
        "active_runs": active_runs_summary(db_path),
        "eligible_now": counts["now"],
        "on_hold": counts["on_hold"],
        "lock_path": str(_lock_path(db_path)),
        "budget": budget_summary(),
        # Work needs the compact boolean for existing action semantics and the
        # detailed projection for truthful scheduler observability.
        "scheduler_enabled": _scheduler_enabled(),
        "scheduler": scheduler_status(),
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
    active_runs = active_runs_summary(db_path)
    return {
        "lock": {"path": str(_lock_path(db_path))},
        "initiatives": rollup,
        "active_runs": active_runs,
        "scheduler_enabled": _scheduler_enabled(),
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
