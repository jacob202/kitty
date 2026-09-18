"""CLI for KX-COORD-01 agent ownership claims."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

from gateway import agent_coordination


def _json_flag(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", dest="as_json")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kitty agent")
    sub = parser.add_subparsers(dest="command", required=True)

    claim = sub.add_parser("claim")
    claim.add_argument("--resource", required=True)
    claim.add_argument("--role", required=True, choices=sorted(agent_coordination.VALID_ROLES))
    claim.add_argument("--paths", action="append", default=[])
    claim.add_argument("--task", dest="task_id")
    claim.add_argument("--lane")
    _json_flag(claim)

    renew = sub.add_parser("renew")
    _json_flag(renew)
    release = sub.add_parser("release")
    _json_flag(release)
    status = sub.add_parser("status")
    _json_flag(status)

    forced = sub.add_parser("force-release")
    forced.add_argument("--session", required=True)
    forced.add_argument("--reason", required=True)
    _json_flag(forced)

    preflight = sub.add_parser("preflight")
    preflight.add_argument("--staged", action="store_true", required=True)
    _json_flag(preflight)
    return parser


def _git(cwd: Path, *args: str, required: bool = True) -> str:
    result = subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if required and result.returncode != 0:
        raise agent_coordination.CoordinationClaimError(
            f"git {' '.join(args)} failed: {result.stderr.strip()}"
        )
    return result.stdout.strip() if result.returncode == 0 else ""


def _repo_context(cwd: Path | None = None) -> dict[str, Any]:
    start = Path(cwd or Path.cwd()).resolve()
    worktree = Path(_git(start, "rev-parse", "--show-toplevel")).resolve()
    branch = _git(worktree, "symbolic-ref", "--quiet", "--short", "HEAD", required=False)
    if not branch:
        branch = f"detached@{_git(worktree, 'rev-parse', '--short=12', 'HEAD')}"
    base = _git(
        worktree,
        "merge-base",
        "HEAD",
        "refs/remotes/origin/main",
        required=False,
    ) or _git(worktree, "rev-parse", "HEAD")
    git_dir = Path(_git(worktree, "rev-parse", "--path-format=absolute", "--git-dir")).resolve()
    common = Path(
        _git(worktree, "rev-parse", "--path-format=absolute", "--git-common-dir")
    ).resolve()
    return {
        "worktree": worktree,
        "branch": branch,
        "base_sha": base,
        "git_dir": git_dir,
        "canonical": git_dir == common,
    }


def _coordination_paths(context: dict[str, Any]) -> tuple[Path, Path]:
    worktree = Path(context["worktree"])
    db_path = agent_coordination.canonical_repo_root(worktree) / agent_coordination.DB_FILENAME
    registry_path = worktree / "coordination" / "resources.yaml"
    return db_path, registry_path


def _participant() -> str:
    """Return the declaring participant, or refuse to guess one.

    This used to fall back to "chatgpt", which silently filed one agent's claim
    under another agent's name. The damage is delayed and confusing: the real
    agent then cannot commit, because its own mutation is checked against a lease
    it never held. Identity is authority here, so an unset identity must stop the
    mutation instead of borrowing a name.
    """
    participant = os.environ.get("KITTY_AGENT_PARTICIPANT", "").strip()
    if not participant:
        raise agent_coordination.CoordinationClaimError(
            "KITTY_AGENT_PARTICIPANT is not set: refusing to attribute this claim to "
            "another agent. Export your own participant id, e.g. "
            "KITTY_AGENT_PARTICIPANT=claude."
        )
    return participant


def _session_file(context: dict[str, Any]) -> Path:
    return Path(context["git_dir"]) / "kitty-agent-session"


def _session_id(
    context: dict[str, Any] | None = None,
    *,
    create: bool = True,
    rotate_if_inactive: bool = False,
) -> str:
    override = os.environ.get("KITTY_AGENT_SESSION_ID")
    if override and override.strip():
        return override.strip()
    ctx = context or _repo_context()
    session_file = _session_file(ctx)
    if session_file.exists():
        existing = session_file.read_text(encoding="utf-8").strip()
        if existing:
            if not rotate_if_inactive:
                return existing
            db_path, _ = _coordination_paths(ctx)
            active = agent_coordination.list_claims(active_only=True, db_path=db_path)
            if any(claim["session_id"] == existing for claim in active):
                return existing
            session_file.unlink(missing_ok=True)
    if not create:
        raise agent_coordination.CoordinationClaimError(
            "no Kitty agent session is established for this worktree; run kitty agent claim first"
        )
    created = f"{_participant()}-{uuid.uuid4().hex}"
    session_file.write_text(created + "\n", encoding="utf-8")
    return created


def _retire_session_binding(context: dict[str, Any], session_id: str) -> None:
    """Drop this worktree's binding once the session it names is gone.

    The env override used to skip this entirely, so a release performed with
    KITTY_AGENT_SESSION_ID exported left the binding file pointing at a released
    session. The next command to read the file then failed against a lease that no
    longer existed. Unlinking only when the file names the session being retired
    is safe regardless of where that session id came from.
    """
    session_file = _session_file(context)
    if not session_file.exists():
        return
    if session_file.read_text(encoding="utf-8").strip() == session_id:
        session_file.unlink(missing_ok=True)


def _claim_paths(values: list[str]) -> list[str]:
    paths: list[str] = []
    for value in values:
        paths.extend(item.strip() for item in value.split(",") if item.strip())
    return paths


def _emit(value: Any, *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(value, sort_keys=True))
    elif isinstance(value, dict):
        print(json.dumps(value, sort_keys=True))
    else:
        print(value)


def _status_rows(*, db_path: Path) -> list[dict[str, Any]]:
    rows = []
    for claim in agent_coordination.list_claims(db_path=db_path):
        rows.append(
            {
                "agent": claim.get("participant") or claim["session_id"],
                "session_id": claim["session_id"],
                "role": claim["role"],
                "lane": claim.get("lane"),
                "task_or_pr": claim.get("task_id") or claim.get("branch"),
                "semantic_scope": claim["resource_id"],
                "paths": claim["paths"],
                "base": claim["base_sha"],
                "branch": claim.get("branch"),
                "worktree": claim.get("worktree"),
                "lease": claim["expires_at"],
                "expires_at": claim["expires_at"],
                "state": claim["state"],
            }
        )
    return rows


def _print_status_table(rows: list[dict[str, Any]]) -> None:
    headings = [
        "Agent", "Role", "Lane", "Task/PR", "Semantic scope",
        "Paths", "Base", "Worktree", "Lease", "State",
    ]
    print(" | ".join(headings))
    print(" | ".join("-" * len(item) for item in headings))
    for row in rows:
        values = [
            row["agent"],
            row["role"],
            row["lane"] or "-",
            row["task_or_pr"] or "-",
            row["semantic_scope"],
            ",".join(row["paths"]),
            row["base"],
            row["worktree"] or "-",
            row["lease"],
            row["state"],
        ]
        print(" | ".join(str(value) for value in values))


def _staged_paths(context: dict[str, Any]) -> list[str]:
    """Return the paths this commit is responsible for.

    During a merge the index holds everything the merged branch brings in, so
    diffing against HEAD asked an agent to own every file it was merging: a
    main-merge staged 613 paths resolving to six resources, which made every
    concurrent main-merge fleet-wide serialise on the same bundle. Diffing
    against MERGE_HEAD instead yields the branch's own work — plus any conflict
    resolution, which by definition differs from both sides. Content arriving
    from the merged branch was not authored here and is not fenced.
    """
    worktree = Path(context["worktree"])
    merge_head = _git(
        worktree, "rev-parse", "--verify", "--quiet", "MERGE_HEAD", required=False
    )
    base = "MERGE_HEAD" if merge_head.strip() else "HEAD"
    output = _git(
        worktree,
        "diff",
        "--cached",
        "--name-only",
        "--no-renames",
        "--diff-filter=ACMRD",
        base,
    )
    return [line for line in output.splitlines() if line.strip()]


def _dispatch(args: argparse.Namespace) -> tuple[Any, int]:
    if args.command == "claim":
        context = _repo_context()
        db_path, registry_path = _coordination_paths(context)
        result = agent_coordination.acquire(
            session_id=_session_id(context, rotate_if_inactive=True),
            participant=_participant(),
            role=args.role,
            resource_id=args.resource,
            lane=args.lane,
            task_id=args.task_id,
            branch=context["branch"],
            worktree=str(context["worktree"]),
            base_sha=context["base_sha"],
            paths=_claim_paths(args.paths),
            db_path=db_path,
            registry_path=registry_path,
        )
        if result["status"] == "CONFLICT":
            holder = result["holder"]
            print(
                "CONFLICT: holder "
                f"session={holder['session_id']} role={holder['role']} "
                f"branch={holder.get('branch') or '-'} expires={holder['expires_at']}",
                file=sys.stderr,
            )
            return result, 2
        return result, 0

    if args.command == "renew":
        context = _repo_context()
        db_path, _ = _coordination_paths(context)
        return agent_coordination.renew(_session_id(context, create=False), db_path=db_path), 0
    if args.command == "release":
        context = _repo_context()
        session = _session_id(context, create=False)
        db_path, _ = _coordination_paths(context)
        result = agent_coordination.release(session, db_path=db_path)
        _retire_session_binding(context, session)
        return result, 0

    if args.command == "force-release":
        context = _repo_context()
        db_path, _ = _coordination_paths(context)
        result = agent_coordination.force_release(
            args.session,
            args.reason,
            participant=_participant(),
            db_path=db_path,
        )
        _retire_session_binding(context, args.session)
        return result, 0

    if args.command == "status":
        context = _repo_context()
        db_path, _ = _coordination_paths(context)
        rows = _status_rows(db_path=db_path)
        return {"claims": rows}, 0

    if args.command == "preflight":
        context = _repo_context()
        required_role = "INTEGRATE" if context["canonical"] else None
        db_path, registry_path = _coordination_paths(context)
        result = agent_coordination.preflight_mutation(
            # Keep this check non-destructive: claim acquisition may be concurrently
            # establishing the binding, so stale bindings are rotated by claim.
            _session_id(context, create=False),
            _staged_paths(context),
            required_role=required_role,
            db_path=db_path,
            registry_path=registry_path,
        )
        if not result["ok"]:
            reason = result["reason"]
            # "session X has no active claim" is true and useless: the session in
            # the message is a dead id read out of the worktree binding, so the
            # reader goes looking for a lease that was released rather than
            # claiming one. Rotating the binding here would say it better but
            # makes a read-only check destructive and races claim acquisition,
            # so name the next move in the message instead.
            if "has no active claim" in reason:
                reason = f"{reason}; run kitty agent claim first"
            print(f"MUTATION BLOCKED: {reason}", file=sys.stderr)
            return result, 2
        return result, 0

    raise AssertionError(f"unknown command {args.command}")


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        value, rc = _dispatch(args)
    except (agent_coordination.CoordinationClaimError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if args.command == "status" and not args.as_json:
        _print_status_table(value["claims"])
    elif rc == 0:
        _emit(value, as_json=args.as_json)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
