"""KittyBuilder preflight doctor — read-only safety checks.

``run_doctor`` answers one question: is it safe to run KittyBuilder right
now? It never claims, transitions, recovers, or otherwise mutates queue or
initiative state — every check either opens a read-only connection (the same
``builder_queue.connect()`` every read command uses, which idempotently
applies connection pragmas the way ``queue list``/``queue status`` already
do) or shells out to read-only commands (``git rev-parse``, ``ps``,
``shutil.which``). It intentionally never calls ``recover_expired_leases``
or ``recover_interrupted_runs`` — those mutate — and instead re-derives
their liveness decisions by inspection only.

Each check reports PASS (fine), WARN (advisory, does not block), or FAIL
(blocking — the CLI exits 1). See ``gateway/doctor.py`` for the sibling
health-check for the rest of the Kitty stack; this module is KittyBuilder's
own preflight, scoped to the builder queue/initiative/runner subsystem.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from gateway import builder_initiative as bi
from gateway import builder_queue as bq
from gateway.paths import BUILDER_QUEUE_DB

EXPECTED_REPO_NAME = os.environ.get("KITTY_BUILDER_REPO_NAME", "kitty")
EXPECTED_DEFAULT_BRANCH = os.environ.get("KITTY_BUILDER_DEFAULT_BRANCH", "main")
REQUIRED_WORKER_COMMANDS = ("bash", "git", "false")

# Credential vars the runner must never let a worker see (mirrors the
# builder_runner._EXTRA_ENV_BLOCKED sanity check below).
_EXPECTED_BLOCKED_CREDENTIALS = frozenset({"GITHUB_TOKEN", "GH_TOKEN", "SSH_AUTH_SOCK"})


@dataclass
class Check:
    level: str  # PASS | WARN | FAIL
    name: str
    detail: str


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


def _repo_toplevel(repo_root: Path | None) -> subprocess.CompletedProcess[str]:
    cwd = Path(repo_root) if repo_root is not None else Path.cwd()
    return _git(["rev-parse", "--show-toplevel"], cwd=cwd)


def _repository_root(toplevel: Path) -> tuple[Path | None, str | None]:
    """Return the shared repository root for a normal or linked worktree."""
    common_dir = _git(
        ["rev-parse", "--path-format=absolute", "--git-common-dir"], cwd=toplevel
    )
    if common_dir.returncode != 0:
        return None, common_dir.stderr.strip()
    git_dir = Path(common_dir.stdout.strip())
    if git_dir.name != ".git":
        return None, f"unexpected Git common directory: {git_dir}"
    return git_dir.parent, None


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------


def _check_kill_switch() -> list[Check]:
    if os.environ.get("KITTY_BUILDER_QUEUE_ENABLED", "1") == "0":
        return [
            Check(
                "WARN",
                "queue:kill_switch",
                "KITTY_BUILDER_QUEUE_ENABLED=0 — mutating queue/initiative "
                "commands are refused. Unset it or set it to 1 to re-enable.",
            )
        ]
    return [Check("PASS", "queue:kill_switch", "enabled")]


def _check_database(db_path: Path | None) -> list[Check]:
    path = Path(db_path) if db_path is not None else BUILDER_QUEUE_DB
    if not path.exists():
        return [
            Check(
                "WARN",
                "db:open",
                f"no queue DB yet at {path} — created on first queue/initiative write",
            )
        ]
    try:
        conn = bq.connect(db_path)
    except Exception as exc:  # noqa: BLE001  # sqlite raises heterogeneous open errors
        return [
            Check("FAIL", "db:open", f"cannot open {path}: {type(exc).__name__}: {exc}")
        ]
    checks = [Check("PASS", "db:open", str(path))]
    try:
        row = conn.execute("PRAGMA integrity_check").fetchone()
    except Exception as exc:  # noqa: BLE001  # sqlite raises heterogeneous errors
        checks.append(
            Check("FAIL", "db:integrity_check", f"{type(exc).__name__}: {exc}")
        )
    else:
        result = str(row[0]) if row is not None else "no result"
        if result == "ok":
            checks.append(Check("PASS", "db:integrity_check", "ok"))
        else:
            checks.append(Check("FAIL", "db:integrity_check", result))
    finally:
        conn.close()
    return checks


def _check_initiative_pause_state(db_path: Path | None) -> list[Check]:
    try:
        initiatives = bi.list_initiatives(db_path=db_path)
    except Exception as exc:  # noqa: BLE001  # sqlite/JSON errors are heterogeneous
        return [
            Check(
                "FAIL",
                "initiative:pause_state",
                f"cannot list initiatives: {type(exc).__name__}: {exc}",
            )
        ]
    if not initiatives:
        return [Check("PASS", "initiative:pause_state", "no initiatives")]

    paused = [i for i in initiatives if i["state"] == bi.INITIATIVE_PAUSED]
    if not paused:
        return [
            Check(
                "PASS",
                "initiative:pause_state",
                f"{len(initiatives)} initiative(s), none paused",
            )
        ]
    ids = ", ".join(str(i["id"]) for i in paused)
    return [
        Check(
            "WARN",
            "initiative:pause_state",
            f"paused: {ids} — resume with 'kitty builder initiative resume <id>' "
            "when ready",
        )
    ]


def _check_repo_identity(repo_root: Path | None) -> list[Check]:
    top = _repo_toplevel(repo_root)
    if top.returncode != 0:
        cwd = Path(repo_root) if repo_root is not None else Path.cwd()
        return [
            Check(
                "FAIL",
                "repo:identity",
                f"not inside a git repository at {cwd}: {top.stderr.strip()}",
            )
        ]
    toplevel = Path(top.stdout.strip())
    identity_root, identity_error = _repository_root(toplevel)
    checks: list[Check] = []

    if identity_root is None:
        checks.append(
            Check(
                "FAIL",
                "repo:identity",
                f"cannot resolve shared Git repository for {toplevel}: {identity_error}",
            )
        )
    elif identity_root.name != EXPECTED_REPO_NAME:
        checks.append(
            Check(
                "FAIL",
                "repo:identity",
                f"expected repo {EXPECTED_REPO_NAME!r}, found {identity_root.name!r} at "
                f"{identity_root} — confirm you are under ~/Projects/{EXPECTED_REPO_NAME} "
                "before running KittyBuilder",
            )
        )
    else:
        checks.append(Check("PASS", "repo:identity", str(identity_root)))

    local_branch = _git(
        ["rev-parse", "--verify", "--quiet", EXPECTED_DEFAULT_BRANCH], cwd=toplevel
    )
    if local_branch.returncode == 0:
        checks.append(Check("PASS", "repo:default_branch", EXPECTED_DEFAULT_BRANCH))
    else:
        remote_branch = _git(
            ["rev-parse", "--verify", "--quiet", f"origin/{EXPECTED_DEFAULT_BRANCH}"],
            cwd=toplevel,
        )
        if remote_branch.returncode == 0:
            checks.append(
                Check("PASS", "repo:default_branch", f"origin/{EXPECTED_DEFAULT_BRANCH}")
            )
        else:
            checks.append(
                Check(
                    "FAIL",
                    "repo:default_branch",
                    f"neither {EXPECTED_DEFAULT_BRANCH!r} nor "
                    f"'origin/{EXPECTED_DEFAULT_BRANCH}' resolves in {toplevel} — "
                    "worktree/publish base-branch assumptions will fail",
                )
            )
    return checks


def _check_worker_commands() -> list[Check]:
    checks: list[Check] = []
    for cmd in REQUIRED_WORKER_COMMANDS:
        found = shutil.which(cmd)
        if found:
            checks.append(Check("PASS", f"tool:{cmd}", found))
        else:
            checks.append(
                Check(
                    "FAIL",
                    f"tool:{cmd}",
                    f"{cmd!r} not found on PATH — required for worker credential "
                    "isolation and worktree operations",
                )
            )
    return checks


def _check_worktree_root(repo_root: Path | None) -> list[Check]:
    top = _repo_toplevel(repo_root)
    if top.returncode != 0:
        cwd = Path(repo_root) if repo_root is not None else Path.cwd()
        return [Check("FAIL", "worktree:root", f"cannot resolve repo root from {cwd}")]
    toplevel = Path(top.stdout.strip())
    root, identity_error = _repository_root(toplevel)
    if root is None:
        return [
            Check(
                "FAIL",
                "worktree:root",
                f"cannot resolve shared Git repository for {toplevel}: {identity_error}",
            )
        ]
    worktree_root = root / ".worktrees" / "kittybuilder"

    if worktree_root.exists():
        if not worktree_root.is_dir():
            return [
                Check(
                    "FAIL",
                    "worktree:root",
                    f"{worktree_root} exists but is not a directory",
                )
            ]
        if not os.access(worktree_root, os.W_OK | os.X_OK):
            return [Check("FAIL", "worktree:root", f"{worktree_root} is not writable")]
        return [Check("PASS", "worktree:root", str(worktree_root))]

    if not os.access(root, os.W_OK | os.X_OK):
        return [
            Check(
                "FAIL",
                "worktree:root",
                f"{root} is not writable; cannot create {worktree_root}",
            )
        ]
    return [
        Check(
            "WARN",
            "worktree:root",
            f"{worktree_root} does not exist yet — created on first run",
        )
    ]


def _check_runs(db_path: Path | None) -> list[Check]:
    """Inspect leases and active runs the way recovery would, without mutating.

    Re-derives the same SELECTs ``recover_expired_leases`` uses for stale
    leases, and the same liveness decision ``recover_interrupted_runs`` uses
    for active runs (dead pid / mismatched process identity / stale
    claim_version) — but only ever reads. No UPDATE ever runs here.
    """
    path = Path(db_path) if db_path is not None else BUILDER_QUEUE_DB
    if not path.exists():
        return [Check("PASS", "runs:leases", "no queue DB yet — nothing to recover")]

    checks: list[Check] = []

    conn = bq.connect(db_path)
    try:
        stale_claimed = conn.execute(
            """
            SELECT id FROM tasks
            WHERE state = ? AND archived_at IS NULL
              AND lease_expires_at IS NOT NULL
              AND lease_expires_at <= strftime('%Y-%m-%d %H:%M:%f', 'now')
            """,
            (bq.CLAIMED,),
        ).fetchall()
        stale_running = conn.execute(
            """
            SELECT id FROM tasks
            WHERE state = ? AND archived_at IS NULL
              AND lease_expires_at IS NOT NULL
              AND lease_expires_at <= strftime('%Y-%m-%d %H:%M:%f', 'now')
            """,
            (bq.RUNNING,),
        ).fetchall()
    finally:
        conn.close()

    stale_ids = [row["id"] for row in (*stale_claimed, *stale_running)]
    if stale_ids:
        checks.append(
            Check(
                "WARN",
                "runs:stale_leases",
                f"{len(stale_ids)} task(s) with expired leases "
                f"({', '.join(stale_ids)}) — run 'kitty builder queue recover' "
                "to reclaim them",
            )
        )
    else:
        checks.append(Check("PASS", "runs:stale_leases", "no expired leases"))

    active_runs = [
        run for run in bq.list_runs(db_path=db_path) if run["state"] in bq.RUN_ACTIVE_STATES
    ]
    if not active_runs:
        checks.append(Check("PASS", "runs:active", "no active runs"))
        return checks

    alive: list[str] = []
    interrupted: list[str] = []
    conflicting: list[str] = []
    unverifiable: list[str] = []

    for run in active_runs:
        run_id = str(run["id"])
        pid = run.get("pid")

        task = bq.get_task(str(run["task_id"]), db_path=db_path)
        run_claim_version = run.get("claim_version")
        task_claim_version = task.get("claim_version") if task is not None else None
        if (
            task_claim_version is not None
            and run_claim_version is not None
            and int(task_claim_version) != int(run_claim_version)
        ):
            conflicting.append(run_id)
            continue

        if pid is None:
            interrupted.append(run_id)
            continue
        try:
            numeric_pid = int(pid)
        except (TypeError, ValueError):
            unverifiable.append(run_id)
            continue

        try:
            os.kill(numeric_pid, 0)
        except ProcessLookupError:
            interrupted.append(run_id)
            continue
        except PermissionError:
            unverifiable.append(run_id)
            continue

        expected_identity = run.get("process_identity")
        if not expected_identity:
            unverifiable.append(run_id)
            continue
        current_identity = bq.capture_process_identity(numeric_pid)
        if current_identity == expected_identity:
            alive.append(run_id)
        else:
            interrupted.append(run_id)

    if alive:
        checks.append(
            Check("PASS", "runs:active", f"{len(alive)} verified alive: {', '.join(alive)}")
        )
    if interrupted:
        checks.append(
            Check(
                "WARN",
                "runs:interrupted",
                f"{len(interrupted)} run(s) look dead but are still marked active "
                f"({', '.join(interrupted)}) — run 'kitty builder queue recover' "
                "to reconcile",
            )
        )
    if conflicting:
        checks.append(
            Check(
                "WARN",
                "runs:conflicting",
                f"{len(conflicting)} run(s) reference a stale claim_version "
                f"({', '.join(conflicting)}) — run 'kitty builder queue recover' "
                "to reconcile",
            )
        )
    if unverifiable:
        checks.append(
            Check(
                "WARN",
                "runs:unverifiable",
                f"{len(unverifiable)} run(s) could not be verified alive or dead "
                f"({', '.join(unverifiable)}) — inspect manually before assuming safety",
            )
        )
    return checks


def _check_github_boundary() -> list[Check]:
    gh = shutil.which("gh")
    has_token = bool(os.environ.get("GITHUB_TOKEN", "").strip())
    if gh:
        return [Check("PASS", "github:boundary", f"gh at {gh}")]
    if has_token:
        return [
            Check(
                "WARN",
                "github:boundary",
                "GITHUB_TOKEN is set but 'gh' is not on PATH — operator publish needs gh",
            )
        ]
    return [
        Check(
            "WARN",
            "github:boundary",
            "neither 'gh' nor GITHUB_TOKEN found — operator publish (push/PR) will fail",
        )
    ]


def _check_credential_isolation() -> list[Check]:
    try:
        from gateway.builder_runner import _EXTRA_ENV_BLOCKED
    except ImportError as exc:
        return [
            Check(
                "FAIL",
                "runner:credential_isolation",
                f"cannot import builder_runner: {exc}",
            )
        ]
    if not _EXTRA_ENV_BLOCKED:
        return [
            Check(
                "FAIL",
                "runner:credential_isolation",
                "builder_runner._EXTRA_ENV_BLOCKED is empty",
            )
        ]
    missing = _EXPECTED_BLOCKED_CREDENTIALS - set(_EXTRA_ENV_BLOCKED)
    if missing:
        return [
            Check(
                "FAIL",
                "runner:credential_isolation",
                f"_EXTRA_ENV_BLOCKED is missing expected credential var(s): "
                f"{sorted(missing)}",
            )
        ]
    return [
        Check(
            "PASS",
            "runner:credential_isolation",
            f"{len(_EXTRA_ENV_BLOCKED)} credential var(s) blocked from worker env",
        )
    ]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def run_doctor(
    *,
    db_path: Path | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Run every preflight check and return a structured, read-only report."""
    checks: list[Check] = []
    checks.extend(_check_kill_switch())
    checks.extend(_check_database(db_path))
    checks.extend(_check_initiative_pause_state(db_path))
    checks.extend(_check_repo_identity(repo_root))
    checks.extend(_check_worker_commands())
    checks.extend(_check_worktree_root(repo_root))
    checks.extend(_check_runs(db_path))
    checks.extend(_check_github_boundary())
    checks.extend(_check_credential_isolation())

    passes = [c for c in checks if c.level == "PASS"]
    warns = [c for c in checks if c.level == "WARN"]
    fails = [c for c in checks if c.level == "FAIL"]

    return {
        "ok": not fails,
        "summary": {"pass": len(passes), "warn": len(warns), "fail": len(fails)},
        "checks": [asdict(c) for c in checks],
    }
