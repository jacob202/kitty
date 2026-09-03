"""CLI for Kitty's interactive coordination-claim safety layer."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from gateway import agent_coordination, agent_workspace


def _json_flag(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", dest="as_json")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kitty agent")
    sub = parser.add_subparsers(dest="command", required=True)

    claim = sub.add_parser("claim")
    claim.add_argument("--as", dest="participant_id", required=True)
    claim.add_argument("--session-id", required=True)
    claim.add_argument("--role", required=True, choices=sorted(agent_coordination.VALID_ROLES))
    claim.add_argument("--lane", dest="lane_id", required=True)
    claim.add_argument("--base-sha", required=True)
    claim.add_argument("--branch", required=True)
    claim.add_argument("--worktree", dest="worktree_path", required=True)
    claim.add_argument("--path", dest="paths", action="append", default=[])
    claim.add_argument("--resource", dest="resources", action="append", default=[])
    claim.add_argument("--lease-seconds", type=int, default=1800)
    _json_flag(claim)

    renew = sub.add_parser("renew")
    renew.add_argument("claim_id")
    renew.add_argument("--session-id", required=True)
    renew.add_argument("--lease-seconds", type=int, default=1800)
    _json_flag(renew)

    release = sub.add_parser("release")
    release.add_argument("claim_id")
    release.add_argument("--session-id", required=True)
    _json_flag(release)

    status = sub.add_parser("status")
    status.add_argument("--all", action="store_true", dest="include_all")
    _json_flag(status)

    guard = sub.add_parser("guard")
    guard.add_argument("--worktree", dest="worktree_path")
    guard.add_argument("--path", dest="paths", action="append", default=[])
    guard.add_argument("--staged", action="store_true")
    _json_flag(guard)
    return parser


def _emit(value: Any, *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(value, sort_keys=True))
    else:
        print(json.dumps(value, indent=2, sort_keys=True))


def _project(claim: dict[str, Any], *, released: bool = False) -> dict[str, Any]:
    action = "RELEASED" if released else "ACQUIRED"
    kind = "result" if released else "status"
    content = (
        f"COORDINATION CLAIM {action}\n"
        f"claim={claim['claim_id']}\n"
        f"role={claim['role']} lane={claim['lane_id']} session={claim['session_id']}\n"
        f"base={claim['base_sha']} branch={claim['branch']}\n"
        f"worktree={claim['worktree_path']}\n"
        f"paths={','.join(claim['paths'])}\n"
        f"resources={','.join(claim['resources'])}"
    )
    try:
        message = agent_workspace.post_global_message(
            sender_id=claim["participant_id"],
            content=content,
            message_kind=kind,
        )
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "message_id": message["id"]}


def _project_conflict(args: argparse.Namespace, error: Exception) -> None:
    content = (
        "COORDINATION CLAIM CONFLICT\n"
        f"requested_by={args.participant_id} lane={args.lane_id} session={args.session_id}\n"
        f"branch={args.branch} worktree={args.worktree_path}\n"
        f"reason={error}"
    )
    try:
        agent_workspace.post_global_message(
            sender_id=args.participant_id,
            content=content,
            message_kind="status",
        )
    except Exception:
        return


def _git_output(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise agent_coordination.CoordinationClaimError(
            result.stderr.strip() or f"git {' '.join(args)} failed"
        )
    return result.stdout.strip()


def _is_canonical_worktree(worktree: str) -> bool:
    root = Path(worktree)
    git_dir = Path(_git_output(root, "rev-parse", "--path-format=absolute", "--git-dir")).resolve()
    common_dir = Path(
        _git_output(root, "rev-parse", "--path-format=absolute", "--git-common-dir")
    ).resolve()
    return git_dir == common_dir


def _guard_inputs(args: argparse.Namespace) -> tuple[str, list[str]]:
    cwd = Path.cwd()
    worktree = args.worktree_path
    paths = list(args.paths)
    if args.staged:
        root = _git_output(cwd, "rev-parse", "--show-toplevel")
        worktree = worktree or root
        staged = _git_output(cwd, "diff", "--cached", "--name-only", "--diff-filter=ACMR")
        paths.extend(line for line in staged.splitlines() if line.strip())
    if worktree is None:
        worktree = _git_output(cwd, "rev-parse", "--show-toplevel")
    return worktree, paths


def _dispatch(args: argparse.Namespace) -> Any:
    if args.command == "claim":
        claim = agent_coordination.claim(
            participant_id=args.participant_id,
            session_id=args.session_id,
            role=args.role,
            lane_id=args.lane_id,
            base_sha=args.base_sha,
            branch=args.branch,
            worktree_path=args.worktree_path,
            paths=args.paths,
            resources=args.resources,
            lease_seconds=args.lease_seconds,
        )
        return {"claim": claim, "gar_projection": _project(claim)}
    if args.command == "renew":
        return {"claim": agent_coordination.renew(
            args.claim_id, args.session_id, lease_seconds=args.lease_seconds
        )}
    if args.command == "release":
        claim = agent_coordination.release(args.claim_id, args.session_id)
        return {"claim": claim, "gar_projection": _project(claim, released=True)}
    if args.command == "status":
        return {
            "claims": agent_coordination.list_claims(active_only=not args.include_all),
            "builder_claims": agent_coordination.list_builder_claims(),
        }
    if args.command == "guard":
        worktree, paths = _guard_inputs(args)
        result = agent_coordination.guard_paths(worktree, paths)
        if args.staged and _is_canonical_worktree(worktree) and result["claim"]["role"] != "INTEGRATE":
            raise agent_coordination.CoordinationClaimError(
                "canonical checkout requires an INTEGRATE claim for staged mutation"
            )
        return result
    raise agent_coordination.CoordinationClaimError(f"unsupported command {args.command}")


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = _dispatch(args)
    except agent_coordination.CoordinationConflictError as exc:
        if args.command == "claim":
            _project_conflict(args, exc)
        print(str(exc), file=sys.stderr)
        return 2
    except (agent_coordination.CoordinationClaimError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    _emit(result, as_json=args.as_json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
