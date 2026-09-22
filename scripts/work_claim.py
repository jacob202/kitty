#!/usr/bin/env python3
"""Tiny local ownership claims for Kitty worktrees.

Claims live under the shared Git common directory, so linked worktrees see the
same state. There is no daemon, database, heartbeat service, or remote protocol.
An expired claim is stale and no longer blocks new work.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import subprocess
import sys
import time
import uuid
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from typing import Iterator

DEFAULT_TTL_MINUTES = 120.0
CLAIM_DIR_NAME = "kitty-work-claims"


class ClaimError(RuntimeError):
    """A truthful ownership/preflight failure."""
def _git(cwd: Path, *args: str, required: bool = True) -> str:
    result = subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True, text=True, check=False,
    )
    if required and result.returncode != 0:
        raise ClaimError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip() if result.returncode == 0 else ""


def _context(cwd: Path | None = None) -> dict[str, str | Path]:
    start = Path(cwd or Path.cwd()).resolve()
    root = Path(_git(start, "rev-parse", "--show-toplevel")).resolve()
    common = Path(
        _git(root, "rev-parse", "--path-format=absolute", "--git-common-dir")
    ).resolve()
    branch = _git(root, "branch", "--show-current", required=False) or (
        "detached@" + _git(root, "rev-parse", "--short=12", "HEAD")
    )
    return {"root": root, "common": common, "branch": branch}


def _normalize_path(raw: str) -> str:
    value = raw.strip().replace("\\", "/")
    if value in {"", "."}:
        return "."
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts:
        raise ClaimError(f"claim path must be repository-relative: {raw!r}")
    normalized = path.as_posix().strip("/")
    return normalized or "."


def _overlaps(left: str, right: str) -> bool:
    if "." in {left, right}:
        return True
    return (
        left == right
        or left.startswith(right + "/")
        or right.startswith(left + "/")
    )


def _covers(scope: str, path: str) -> bool:
    return scope == "." or scope == path or path.startswith(scope + "/")


def _claim_dir(common: Path) -> Path:
    return common / CLAIM_DIR_NAME


@contextmanager
def _locked(common: Path) -> Iterator[Path]:
    directory = _claim_dir(common)
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    lock_path = directory / ".lock"
    with lock_path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield directory
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _read_claims(directory: Path, now: float | None = None) -> list[dict]:
    moment = time.time() if now is None else now
    claims: list[dict] = []
    for path in sorted(directory.glob("*.json")):
        try:
            claim = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ClaimError(f"unreadable claim file {path}: {exc}") from exc
        claim["_file"] = str(path)
        claim["state"] = (
            "active" if float(claim["expires_at"]) > moment else "stale"
        )
        claims.append(claim)
    return claims


def _write_claim(directory: Path, claim: dict) -> None:
    target = directory / f"{claim['claim_id']}.json"
    temp = directory / f".{claim['claim_id']}.{uuid.uuid4().hex}.tmp"
    temp.write_text(json.dumps(claim, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(target)
def _claim(args: argparse.Namespace) -> dict:
    ctx = _context()
    owner = args.owner.strip()
    task = args.task.strip()
    if not owner or not task:
        raise ClaimError("owner and task must be non-empty")
    if args.ttl_minutes <= 0:
        raise ClaimError("ttl-minutes must be greater than zero")
    paths = sorted({_normalize_path(value) for value in args.path})
    if not paths:
        raise ClaimError("at least one --path is required")
    now = time.time()
    with _locked(Path(ctx["common"])) as directory:
        existing = _read_claims(directory, now)
        for claim in existing:
            if claim["state"] != "active":
                continue
            if claim["worktree"] == str(ctx["root"]):
                raise ClaimError(
                    f"worktree already owned by {claim['owner']} "
                    f"for {claim['task']} (claim {claim['claim_id']})"
                )
            if any(_overlaps(a, b) for a in paths for b in claim["paths"]):
                raise ClaimError(
                    f"ownership conflict with {claim['owner']} on "
                    f"{claim['paths']} (claim {claim['claim_id']})"
                )
        claim = {
            "schema_version": 1,
            "claim_id": uuid.uuid4().hex[:12],
            "owner": owner,
            "task": task,
            "worktree": str(ctx["root"]),
            "branch": str(ctx["branch"]),
            "paths": paths,
            "created_at": now,
            "expires_at": now + (args.ttl_minutes * 60.0),
        }
        _write_claim(directory, claim)
    return claim


def _find_current_claim(claims: list[dict], root: Path) -> dict | None:
    current = [c for c in claims if c["worktree"] == str(root)]
    active = [c for c in current if c["state"] == "active"]
    if len(active) > 1:
        raise ClaimError(f"multiple active claims exist for {root}")
    return active[0] if active else None


def _status(_args: argparse.Namespace) -> dict:
    ctx = _context()
    with _locked(Path(ctx["common"])) as directory:
        claims = _read_claims(directory)
    for claim in claims:
        claim.pop("_file", None)
    return {"claims": claims}
def _renew(args: argparse.Namespace) -> dict:
    ctx = _context()
    if args.ttl_minutes <= 0:
        raise ClaimError("ttl-minutes must be greater than zero")
    now = time.time()
    with _locked(Path(ctx["common"])) as directory:
        claim = _find_current_claim(_read_claims(directory, now), Path(ctx["root"]))
        if claim is None:
            raise ClaimError("this worktree has no active claim; claim it again")
        claim.pop("_file", None)
        claim.pop("state", None)
        claim["expires_at"] = now + (args.ttl_minutes * 60.0)
        _write_claim(directory, claim)
    return claim


def _release(_args: argparse.Namespace) -> dict:
    ctx = _context()
    with _locked(Path(ctx["common"])) as directory:
        claims = _read_claims(directory)
        current = [c for c in claims if c["worktree"] == str(ctx["root"])]
        if not current:
            raise ClaimError("this worktree has no claim to release")
        removed = []
        for claim in current:
            Path(claim["_file"]).unlink(missing_ok=True)
            removed.append(claim["claim_id"])
    return {"released": removed}


def _reap(_args: argparse.Namespace) -> dict:
    ctx = _context()
    with _locked(Path(ctx["common"])) as directory:
        claims = _read_claims(directory)
        stale = [c for c in claims if c["state"] == "stale"]
        for claim in stale:
            Path(claim["_file"]).unlink(missing_ok=True)
    return {"reaped": [c["claim_id"] for c in stale]}


def _staged_paths(root: Path) -> list[str]:
    output = _git(
        root, "diff", "--cached", "--name-only", "--no-renames",
        "--diff-filter=ACMRD", "HEAD",
    )
    return [_normalize_path(line) for line in output.splitlines() if line.strip()]


def _preflight(args: argparse.Namespace) -> dict:
    ctx = _context()
    paths = _staged_paths(Path(ctx["root"])) if args.staged else []
    if not paths:
        return {"ok": True, "paths": [], "reason": "nothing staged"}
    with _locked(Path(ctx["common"])) as directory:
        claim = _find_current_claim(_read_claims(directory), Path(ctx["root"]))
    if claim is None:
        raise ClaimError(
            "staged mutation has no active worktree claim; run "
            "python3 scripts/work_claim.py claim --owner <id> --task <task> --path <scope>"
        )
    uncovered = [p for p in paths if not any(_covers(scope, p) for scope in claim["paths"])]
    if uncovered:
        raise ClaimError(
            f"staged paths are outside claim {claim['claim_id']}: {uncovered}"
        )
    return {"ok": True, "claim_id": claim["claim_id"], "paths": paths}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="work_claim.py")
    sub = parser.add_subparsers(dest="command", required=True)

    claim = sub.add_parser("claim")
    claim.add_argument("--owner", required=True)
    claim.add_argument("--task", required=True)
    claim.add_argument("--path", action="append", default=[])
    claim.add_argument("--ttl-minutes", type=float, default=DEFAULT_TTL_MINUTES)

    sub.add_parser("status")
    renew = sub.add_parser("renew")
    renew.add_argument("--ttl-minutes", type=float, default=DEFAULT_TTL_MINUTES)
    sub.add_parser("release")
    sub.add_parser("reap")
    preflight = sub.add_parser("preflight")
    preflight.add_argument("--staged", action="store_true", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    handlers = {
        "claim": _claim,
        "status": _status,
        "renew": _renew,
        "release": _release,
        "reap": _reap,
        "preflight": _preflight,
    }
    try:
        result = handlers[args.command](args)
    except ClaimError as exc:
        print(f"CLAIM BLOCKED: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
