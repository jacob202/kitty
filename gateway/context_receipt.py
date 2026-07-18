"""Deterministic repository context receipts and continuity validation.

The receipt is a read-side projection over Git, canonical documents, strict
checkpoint metadata, and the existing Builder status projection. It owns no
durable state and never fetches remotes or repairs stale data.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from gateway import builder_status

SCHEMA_VERSION = 1
DEFAULT_RECENT_COMMITS = 5
DEFAULT_MAX_CHECKPOINT_AGE = timedelta(days=7)
EXPECTED_CANONICAL_CHECKOUT = Path.home() / "Projects" / "kitty"
ROOT = Path(__file__).resolve().parent.parent

AUTHORITY_MAP_PATH = Path("docs/AUTHORITY_MAP.md")
START_HERE_PATH = Path("START_HERE.md")
ACTIVE_MISSION_PATH = Path("docs/ACTIVE_MISSION.md")
STATE_PATH = Path(".claude/STATE.md")
HANDOFF_PATH = Path(".claude/HANDOFF.md")

_CHECKPOINT_PATHS = {STATE_PATH.as_posix(), HANDOFF_PATH.as_posix()}
_REQUIRED_CHECKPOINT_KEYS = {
    "schema_version",
    "updated_at",
    "head_sha",
    "branch",
    "worktree",
    "status",
    "completed_items",
    "blockers",
    "next_action",
    "invalidation_conditions",
    "active_mission",
    "pull_request",
}
_REQUIRED_MISSION_KEYS = {
    "schema_version",
    "mission_id",
    "status",
    "approved_at",
    "approved_by",
    "base_sha",
    "authority",
}
_ACTIVE_CHECKPOINT_STATUSES = {"in_progress", "blocked", "awaiting_review"}
_TERMINAL_CHECKPOINT_STATUSES = {"complete", "cancelled", "superseded"}
_MISSION_STATUSES = {
    "proposed",
    "awaiting_approval",
    "approved",
    "accepted",
    "running",
    "blocked",
    "succeeded",
    "failed",
    "cancelled",
    "superseded",
}
_TERMINAL_MISSION_STATUSES = {"succeeded", "failed", "cancelled", "superseded"}
_READING_ORDER_BLOCK = re.compile(
    r"<!-- kitty-reading-order:start -->(.*?)<!-- kitty-reading-order:end -->",
    re.DOTALL,
)
_MARKDOWN_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
_AUTHORITY_ROW = re.compile(
    r"^\|\s*`(?P<concern>[^`]+)`\s*\|\s*`(?P<authority>[^`]+)`\s*\|",
    re.MULTILINE,
)
_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_DUPLICATE_AUTHORITY_PATTERNS = (
    re.compile(r"^##\s+(?:Current\s+)?Sources? [Oo]f Truth\s*$", re.MULTILINE),
    re.compile(r"\bthis file is (?:the )?(?:single )?source of truth\b", re.IGNORECASE),
)
_OUTDATED_BUILDER_PATTERNS = (
    "Layer 1A — coordination only",
    "Layer 1A (coordination only)",
    "Safe, read-only coordination commands",
    "No autonomous loops, agent spawning, or budget enforcement yet",
    "Disabled commands (`run`, `loop`, `repl`, `delegate`)",
    "The Builder UI was not implemented",
    "Add a read-only Builder status projection before implementing UI controls",
    "No worker spawning, no PR automation, no daemon, no UI",
    "no heartbeat until Phase 1C",
)
_CLAIM_SCAN_PATHS = (
    Path("AGENTS.md"),
    Path("CLAUDE.md"),
    START_HERE_PATH,
    Path("docs/PROJECT_STATUS.md"),
)
_BUILDER_DESCRIPTION_PATHS = (
    Path("AGENTS.md"),
    Path("CLAUDE.md"),
    START_HERE_PATH,
    Path("docs/ARCHITECTURE.md"),
    Path("docs/BLUEPRINT.md"),
    Path("docs/NORTH_STAR.md"),
    Path("docs/PROJECT_STATUS.md"),
    Path("docs/KITTYBUILDER_QUICKSTART.md"),
    Path("gateway/builder_cli.py"),
)


class ContextReceiptError(RuntimeError):
    """Raised when essential repository evidence cannot be established."""


@dataclass(frozen=True)
class ContinuityCheck:
    level: str  # PASS | WARN | FAIL
    name: str
    detail: str


GitHubLookup = Callable[[int], dict[str, Any]]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _git(
    repo_root: Path,
    args: list[str],
    *,
    required: bool = True,
) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except FileNotFoundError as exc:
        raise ContextReceiptError("git is not installed or not on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise ContextReceiptError(
            f"git {' '.join(args)} timed out after 10 seconds in {repo_root}"
        ) from exc
    if required and result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "no error output"
        raise ContextReceiptError(
            f"git {' '.join(args)} failed in {repo_root} with exit "
            f"{result.returncode}: {detail}"
        )
    return result


def _resolve_repo_root(repo_root: Path) -> Path:
    result = _git(repo_root, ["rev-parse", "--show-toplevel"])
    resolved = Path(result.stdout.strip()).resolve()
    if not resolved.exists():
        raise ContextReceiptError(f"git reported a missing repository root: {resolved}")
    return resolved


def _worktree_paths(repo_root: Path) -> list[Path]:
    result = _git(repo_root, ["worktree", "list", "--porcelain"])
    paths = [
        Path(line.removeprefix("worktree ")).resolve()
        for line in result.stdout.splitlines()
        if line.startswith("worktree ")
    ]
    if not paths:
        raise ContextReceiptError("git worktree list returned no registered worktrees")
    return paths


def _current_branch(repo_root: Path) -> str | None:
    result = _git(repo_root, ["symbolic-ref", "--quiet", "--short", "HEAD"], required=False)
    branch = result.stdout.strip()
    return branch or None


def _parse_timestamp(value: object, *, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty ISO-8601 string")
    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"{field} is not valid ISO-8601: {value!r}") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include a timezone: {value!r}")
    return parsed.astimezone(timezone.utc)


def _load_json_comment(path: Path, marker: str) -> dict[str, Any]:
    if not path.exists():
        raise ValueError(f"required file does not exist: {path}")
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(
        rf"<!--\s*{re.escape(marker)}\s*(\{{.*?\}})\s*-->",
        re.DOTALL,
    )
    match = pattern.search(text)
    if match is None:
        raise ValueError(f"{path} is missing the <!-- {marker} ... --> metadata block")
    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"{path} has invalid {marker} JSON at line {exc.lineno}, column {exc.colno}: "
            f"{exc.msg}"
        ) from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{path} {marker} metadata must be a JSON object")
    return payload


def _load_checkpoint(repo_root: Path, relative_path: Path, marker: str) -> dict[str, Any]:
    payload = _load_json_comment(repo_root / relative_path, marker)
    missing = sorted(_REQUIRED_CHECKPOINT_KEYS - set(payload))
    if missing:
        raise ValueError(f"{relative_path} checkpoint metadata is missing keys: {missing}")
    if payload.get("schema_version") != 1:
        raise ValueError(
            f"{relative_path} checkpoint schema_version must be 1, "
            f"got {payload.get('schema_version')!r}"
        )
    for key in ("completed_items", "blockers", "invalidation_conditions"):
        value = payload.get(key)
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise ValueError(f"{relative_path} {key} must be a list of strings")
    if not payload["invalidation_conditions"]:
        raise ValueError(f"{relative_path} invalidation_conditions must not be empty")
    for key in ("head_sha", "branch", "worktree", "status", "next_action", "active_mission"):
        value = payload.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{relative_path} {key} must be a non-empty string")
    _parse_timestamp(payload.get("updated_at"), field=f"{relative_path}:updated_at")
    allowed_statuses = _ACTIVE_CHECKPOINT_STATUSES | _TERMINAL_CHECKPOINT_STATUSES
    if relative_path == HANDOFF_PATH:
        allowed_statuses |= {"valid", "invalid", "not_required"}
    if payload["status"] not in allowed_statuses:
        raise ValueError(
            f"{relative_path} status {payload['status']!r} is not one of "
            f"{sorted(allowed_statuses)}"
        )
    return payload


def _load_mission(repo_root: Path) -> dict[str, Any]:
    payload = _load_json_comment(repo_root / ACTIVE_MISSION_PATH, "kitty-mission")
    missing = sorted(_REQUIRED_MISSION_KEYS - set(payload))
    if missing:
        raise ValueError(f"{ACTIVE_MISSION_PATH} mission metadata is missing keys: {missing}")
    if payload.get("schema_version") != 1:
        raise ValueError(
            f"{ACTIVE_MISSION_PATH} schema_version must be 1, "
            f"got {payload.get('schema_version')!r}"
        )
    if payload.get("authority") != ACTIVE_MISSION_PATH.as_posix():
        raise ValueError(
            f"{ACTIVE_MISSION_PATH} authority must name itself, got "
            f"{payload.get('authority')!r}"
        )
    base_sha = payload.get("base_sha")
    if not isinstance(base_sha, str) or not _SHA_PATTERN.fullmatch(base_sha):
        raise ValueError(f"{ACTIVE_MISSION_PATH} base_sha must be a full lowercase Git SHA")
    _parse_timestamp(payload.get("approved_at"), field=f"{ACTIVE_MISSION_PATH}:approved_at")
    for key in ("mission_id", "status", "approved_by"):
        if not isinstance(payload.get(key), str) or not str(payload[key]).strip():
            raise ValueError(f"{ACTIVE_MISSION_PATH} {key} must be a non-empty string")
    if payload["status"] not in _MISSION_STATUSES:
        raise ValueError(
            f"{ACTIVE_MISSION_PATH} status {payload['status']!r} is not one of "
            f"{sorted(_MISSION_STATUSES)}"
        )
    return payload


def _load_authorities(repo_root: Path) -> dict[str, str]:
    path = repo_root / AUTHORITY_MAP_PATH
    if not path.exists():
        raise ValueError(f"required authority map does not exist: {path}")
    text = path.read_text(encoding="utf-8")
    authorities: dict[str, str] = {}
    for match in _AUTHORITY_ROW.finditer(text):
        concern = match.group("concern").strip()
        authority = match.group("authority").strip()
        if concern in authorities:
            raise ValueError(f"duplicate authority claim for {concern!r} in {AUTHORITY_MAP_PATH}")
        authorities[concern] = authority
    if not authorities:
        raise ValueError(f"{AUTHORITY_MAP_PATH} contains no parseable authority rows")
    required = {
        "product_purpose",
        "engineering_doctrine",
        "architecture",
        "decisions",
        "live_status",
        "active_mission",
        "session_checkpoint",
        "continuation",
        "builder_state",
        "historical_records",
    }
    missing = sorted(required - set(authorities))
    if missing:
        raise ValueError(f"{AUTHORITY_MAP_PATH} is missing concerns: {missing}")
    return dict(sorted(authorities.items()))


def _load_reading_order(repo_root: Path) -> list[str]:
    path = repo_root / START_HERE_PATH
    if not path.exists():
        raise ValueError(f"required front door does not exist: {path}")
    text = path.read_text(encoding="utf-8")
    block = _READING_ORDER_BLOCK.search(text)
    if block is None:
        raise ValueError(f"{START_HERE_PATH} is missing the marked canonical reading order")
    order = [link.strip() for link in _MARKDOWN_LINK.findall(block.group(1))]
    if not order:
        raise ValueError(f"{START_HERE_PATH} canonical reading order contains no links")
    duplicates = sorted({item for item in order if order.count(item) > 1})
    if duplicates:
        raise ValueError(f"{START_HERE_PATH} reading order contains duplicates: {duplicates}")
    return order


def _github_pr_status(number: int) -> dict[str, Any]:
    gh = shutil.which("gh")
    if gh is None:
        raise RuntimeError("gh is not installed or not on PATH")
    env = dict(os.environ)
    env.pop("GITHUB_TOKEN", None)
    env.pop("GH_TOKEN", None)
    try:
        result = subprocess.run(
            [
                gh,
                "pr",
                "view",
                str(number),
                "--json",
                "number,state,isDraft,headRefName,headRefOid,url",
            ],
            capture_output=True,
            text=True,
            timeout=15,
            env=env,
            cwd=ROOT,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"gh pr view {number} timed out after 15 seconds") from exc
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "no error output"
        raise RuntimeError(f"gh pr view {number} failed with exit {result.returncode}: {detail}")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"gh pr view {number} returned invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"gh pr view {number} returned a non-object payload")
    return payload


def _checkpoint_head_is_fresh(repo_root: Path, recorded_head: str, head: str) -> tuple[bool, str]:
    if recorded_head == head:
        return True, "checkpoint records the current HEAD"
    ancestor = _git(
        repo_root,
        ["merge-base", "--is-ancestor", recorded_head, head],
        required=False,
    )
    if ancestor.returncode != 0:
        return False, f"recorded HEAD {recorded_head} is not an ancestor of current HEAD {head}"
    count_result = _git(repo_root, ["rev-list", "--count", f"{recorded_head}..{head}"])
    changed_result = _git(repo_root, ["diff", "--name-only", f"{recorded_head}..{head}"])
    commit_count = int(count_result.stdout.strip())
    changed_paths = {line for line in changed_result.stdout.splitlines() if line}
    if commit_count == 1 and changed_paths and changed_paths <= _CHECKPOINT_PATHS:
        return (
            True,
            "checkpoint records its parent and the only newer commit changes "
            f"{sorted(changed_paths)}",
        )
    return (
        False,
        f"recorded HEAD {recorded_head} does not match current HEAD {head}; "
        f"{commit_count} newer commit(s) changed {sorted(changed_paths)}",
    )


def _checkpoint_checks(
    repo_root: Path,
    *,
    relative_path: Path,
    marker: str,
    metadata: dict[str, Any] | None,
    metadata_error: str | None,
    head: str,
    branch: str | None,
    now: datetime,
    max_age: timedelta,
    github_lookup: GitHubLookup,
) -> list[ContinuityCheck]:
    prefix = "state" if relative_path == STATE_PATH else "handoff"
    if metadata is None:
        return [ContinuityCheck("FAIL", f"{prefix}:metadata", metadata_error or "unknown error")]

    checks: list[ContinuityCheck] = []
    checks.append(ContinuityCheck("PASS", f"{prefix}:metadata", "schema v1 metadata is valid"))

    recorded_head = str(metadata["head_sha"])
    if not _SHA_PATTERN.fullmatch(recorded_head):
        checks.append(
            ContinuityCheck(
                "FAIL", f"{prefix}:head", f"head_sha is not a full lowercase SHA: {recorded_head!r}"
            )
        )
    else:
        # A recorded head that is missing or no longer an ancestor is WARN, not
        # FAIL: a squash-merge collapses a feature branch into a new commit and
        # orphans the tip the checkpoint recorded, so on main (and in CI, which
        # checks out the merged history) this is the normal post-merge state,
        # not a broken checkpoint. Genuine defects — a malformed SHA above, a
        # stale age below — still FAIL.
        exists = _git(repo_root, ["cat-file", "-e", f"{recorded_head}^{{commit}}"], required=False)
        if exists.returncode != 0:
            checks.append(
                ContinuityCheck("WARN", f"{prefix}:head", f"recorded commit is not in this history: {recorded_head}")
            )
        else:
            fresh, detail = _checkpoint_head_is_fresh(repo_root, recorded_head, head)
            checks.append(ContinuityCheck("PASS" if fresh else "WARN", f"{prefix}:head", detail))

    recorded_branch = str(metadata["branch"])
    if branch is None:
        checks.append(ContinuityCheck("FAIL", f"{prefix}:branch", "current HEAD is detached"))
    elif recorded_branch != branch:
        # Reading a checkpoint from a branch other than the one it was written on
        # is WARN, not FAIL: after any merge to main the checkpoint's feature
        # branch can never match, and CI reads it from the target branch. The
        # branch name is informative, not a gate.
        checks.append(
            ContinuityCheck(
                "WARN",
                f"{prefix}:branch",
                f"recorded branch {recorded_branch!r} does not match current branch {branch!r}",
            )
        )
    else:
        checks.append(ContinuityCheck("PASS", f"{prefix}:branch", branch))

    worktree_value = str(metadata["worktree"])
    recorded_worktree = (
        repo_root if worktree_value == "." else Path(worktree_value).expanduser().resolve()
    )
    if recorded_worktree != repo_root:
        checks.append(
            ContinuityCheck(
                "FAIL",
                f"{prefix}:worktree",
                f"recorded worktree {recorded_worktree} does not match {repo_root}",
            )
        )
    else:
        checks.append(ContinuityCheck("PASS", f"{prefix}:worktree", str(repo_root)))

    updated_at = _parse_timestamp(metadata["updated_at"], field=f"{relative_path}:updated_at")
    age = now.astimezone(timezone.utc) - updated_at
    if age < -timedelta(minutes=5):
        checks.append(
            ContinuityCheck(
                "FAIL", f"{prefix}:age", f"checkpoint timestamp is in the future: {updated_at.isoformat()}"
            )
        )
    elif age > max_age:
        checks.append(
            ContinuityCheck(
                "FAIL",
                f"{prefix}:age",
                f"checkpoint is {age.days} day(s) old; maximum is {max_age.days} day(s)",
            )
        )
    else:
        checks.append(
            ContinuityCheck(
                "PASS", f"{prefix}:age", f"updated {updated_at.isoformat().replace('+00:00', 'Z')}"
            )
        )

    active_mission = str(metadata["active_mission"])
    if active_mission != ACTIVE_MISSION_PATH.as_posix():
        checks.append(
            ContinuityCheck(
                "FAIL",
                f"{prefix}:active_mission",
                f"expected {ACTIVE_MISSION_PATH}, got {active_mission!r}",
            )
        )
    else:
        checks.append(ContinuityCheck("PASS", f"{prefix}:active_mission", active_mission))

    status = str(metadata["status"])
    next_action = str(metadata["next_action"]).strip()
    completed = {item.strip().casefold() for item in metadata["completed_items"]}
    if status in _TERMINAL_CHECKPOINT_STATUSES and next_action.casefold() not in {"none", "n/a"}:
        checks.append(
            ContinuityCheck(
                "FAIL",
                f"{prefix}:active_action",
                f"terminal status {status!r} still declares next action {next_action!r}",
            )
        )
    elif next_action.casefold() in completed:
        checks.append(
            ContinuityCheck(
                "FAIL",
                f"{prefix}:active_action",
                f"next action is already listed as completed: {next_action!r}",
            )
        )
    else:
        checks.append(ContinuityCheck("PASS", f"{prefix}:active_action", next_action))

    pull_request = metadata.get("pull_request")
    if pull_request is None:
        checks.append(ContinuityCheck("PASS", f"{prefix}:pull_request", "no active PR claimed"))
    elif not isinstance(pull_request, dict):
        checks.append(
            ContinuityCheck("FAIL", f"{prefix}:pull_request", "pull_request must be null or an object")
        )
    else:
        number = pull_request.get("number")
        expected_state = pull_request.get("state")
        expected_head = pull_request.get("head_sha")
        if not isinstance(number, int) or number <= 0:
            checks.append(
                ContinuityCheck("FAIL", f"{prefix}:pull_request", "pull_request.number must be positive")
            )
        elif expected_state != "OPEN" or not isinstance(expected_head, str):
            checks.append(
                ContinuityCheck(
                    "FAIL",
                    f"{prefix}:pull_request",
                    "an active pull request must declare state OPEN and a head_sha",
                )
            )
        else:
            try:
                live = github_lookup(number)
            except RuntimeError as exc:
                checks.append(
                    ContinuityCheck(
                        "WARN",
                        f"{prefix}:pull_request",
                        f"PR #{number} could not be verified: {exc}",
                    )
                )
            else:
                live_state = live.get("state")
                live_head = live.get("headRefOid")
                if live_state != expected_state or live_head != expected_head:
                    checks.append(
                        ContinuityCheck(
                            "FAIL",
                            f"{prefix}:pull_request",
                            f"PR #{number} expected {expected_state}@{expected_head}, "
                            f"live state is {live_state}@{live_head}",
                        )
                    )
                else:
                    checks.append(
                        ContinuityCheck(
                            "PASS",
                            f"{prefix}:pull_request",
                            f"PR #{number} is OPEN at {expected_head}",
                        )
                    )
    return checks


def _documentation_checks(
    repo_root: Path,
    *,
    authorities: dict[str, str] | None,
    authorities_error: str | None,
    reading_order: list[str] | None,
    reading_order_error: str | None,
) -> list[ContinuityCheck]:
    checks: list[ContinuityCheck] = []
    if authorities is None:
        checks.append(
            ContinuityCheck("FAIL", "docs:authority_map", authorities_error or "unknown error")
        )
    else:
        broken_authorities = sorted(
            authority
            for authority in authorities.values()
            if (authority.endswith(".md") or authority == "AGENTS.md")
            and not (repo_root / authority).exists()
        )
        if broken_authorities:
            checks.append(
                ContinuityCheck(
                    "FAIL",
                    "docs:authority_map",
                    f"authority paths do not exist: {broken_authorities}",
                )
            )
        else:
            checks.append(
                ContinuityCheck(
                    "PASS", "docs:authority_map", f"{len(authorities)} unique concern owners"
                )
            )

    if reading_order is None:
        checks.append(
            ContinuityCheck("FAIL", "docs:reading_order", reading_order_error or "unknown error")
        )
    else:
        broken_links = sorted(
            path
            for path in reading_order
            if "://" not in path and not (repo_root / path.split("#", 1)[0]).exists()
        )
        if broken_links:
            checks.append(
                ContinuityCheck(
                    "FAIL", "docs:front_door_links", f"broken reading-order links: {broken_links}"
                )
            )
        else:
            checks.append(
                ContinuityCheck(
                    "PASS", "docs:front_door_links", f"{len(reading_order)} reading-order links resolve"
                )
            )

    duplicate_claims: list[str] = []
    for relative_path in _CLAIM_SCAN_PATHS:
        path = repo_root / relative_path
        if not path.exists():
            duplicate_claims.append(f"missing:{relative_path}")
            continue
        text = path.read_text(encoding="utf-8")
        if any(pattern.search(text) for pattern in _DUPLICATE_AUTHORITY_PATTERNS):
            duplicate_claims.append(relative_path.as_posix())
    if duplicate_claims:
        checks.append(
            ContinuityCheck(
                "FAIL",
                "docs:duplicate_authority_claims",
                f"front doors contain competing authority declarations: {duplicate_claims}",
            )
        )
    else:
        checks.append(
            ContinuityCheck(
                "PASS", "docs:duplicate_authority_claims", "authority routing is centralized"
            )
        )

    outdated: list[str] = []
    for relative_path in _BUILDER_DESCRIPTION_PATHS:
        path = repo_root / relative_path
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for phrase in _OUTDATED_BUILDER_PATTERNS:
            if phrase in text:
                outdated.append(f"{relative_path}:{phrase}")
    if outdated:
        checks.append(
            ContinuityCheck(
                "FAIL",
                "docs:builder_descriptions",
                f"outdated Builder descriptions remain: {outdated}",
            )
        )
    else:
        checks.append(
            ContinuityCheck(
                "PASS", "docs:builder_descriptions", "active documents describe current Builder rails"
            )
        )
    return checks


def _safe_load(loader: Callable[[], dict[str, Any]]) -> tuple[dict[str, Any] | None, str | None]:
    try:
        return loader(), None
    except (OSError, ValueError) as exc:
        return None, str(exc)


def _safe_load_strings(
    loader: Callable[[], dict[str, str] | list[str]],
) -> tuple[dict[str, str] | list[str] | None, str | None]:
    try:
        return loader(), None
    except (OSError, ValueError) as exc:
        return None, str(exc)


def inspect_continuity(
    repo_root: Path,
    *,
    expected_canonical: Path | None = None,
    now: datetime | None = None,
    max_age: timedelta = DEFAULT_MAX_CHECKPOINT_AGE,
    github_lookup: GitHubLookup | None = None,
) -> dict[str, Any]:
    """Inspect repository continuity without mutating repository or Builder state."""
    repo_root = _resolve_repo_root(repo_root)
    head = _git(repo_root, ["rev-parse", "HEAD"]).stdout.strip()
    branch = _current_branch(repo_root)
    worktrees = _worktree_paths(repo_root)
    canonical_checkout = worktrees[0]
    if expected_canonical is None:
        env_override = os.environ.get("KITTY_EXPECTED_CANONICAL_CHECKOUT")
        if env_override:
            expected_canonical = Path(env_override)
    expected = (expected_canonical or EXPECTED_CANONICAL_CHECKOUT).expanduser().resolve()
    observed_at = (now or _utc_now()).astimezone(timezone.utc)
    lookup = github_lookup or _github_pr_status

    checks: list[ContinuityCheck] = []
    if canonical_checkout != expected:
        checks.append(
            ContinuityCheck(
                "FAIL",
                "repo:canonical_checkout",
                f"expected {expected}, Git reports canonical checkout {canonical_checkout}",
            )
        )
    else:
        checks.append(ContinuityCheck("PASS", "repo:canonical_checkout", str(canonical_checkout)))
    if repo_root not in worktrees:
        checks.append(
            ContinuityCheck(
                "FAIL", "repo:worktree_registration", f"{repo_root} is not registered with Git"
            )
        )
    else:
        checks.append(ContinuityCheck("PASS", "repo:worktree_registration", str(repo_root)))
    if branch is None:
        checks.append(ContinuityCheck("FAIL", "git:branch", "HEAD is detached"))
    else:
        branch_exists = _git(repo_root, ["show-ref", "--verify", "--quiet", f"refs/heads/{branch}"], required=False)
        checks.append(
            ContinuityCheck(
                "PASS" if branch_exists.returncode == 0 else "FAIL",
                "git:branch",
                branch if branch_exists.returncode == 0 else f"local branch ref is missing: {branch}",
            )
        )

    origin_main = _git(repo_root, ["rev-parse", "--verify", "origin/main"], required=False)
    if origin_main.returncode != 0:
        checks.append(
            ContinuityCheck("FAIL", "git:origin_main", "origin/main does not resolve locally")
        )
    else:
        checks.append(
            ContinuityCheck("PASS", "git:origin_main", origin_main.stdout.strip())
        )
    state, state_error = _safe_load(
        lambda: _load_checkpoint(repo_root, STATE_PATH, "kitty-state")
    )
    handoff, handoff_error = _safe_load(
        lambda: _load_checkpoint(repo_root, HANDOFF_PATH, "kitty-handoff")
    )
    mission, mission_error = _safe_load(lambda: _load_mission(repo_root))
    authority_loaded, authority_error = _safe_load_strings(
        lambda: _load_authorities(repo_root)
    )
    order_loaded, order_error = _safe_load_strings(lambda: _load_reading_order(repo_root))
    authorities = authority_loaded if isinstance(authority_loaded, dict) else None
    reading_order = order_loaded if isinstance(order_loaded, list) else None

    checks.extend(
        _checkpoint_checks(
            repo_root,
            relative_path=STATE_PATH,
            marker="kitty-state",
            metadata=state,
            metadata_error=state_error,
            head=head,
            branch=branch,
            now=observed_at,
            max_age=max_age,
            github_lookup=lookup,
        )
    )
    checks.extend(
        _checkpoint_checks(
            repo_root,
            relative_path=HANDOFF_PATH,
            marker="kitty-handoff",
            metadata=handoff,
            metadata_error=handoff_error,
            head=head,
            branch=branch,
            now=observed_at,
            max_age=max_age,
            github_lookup=lookup,
        )
    )
    if mission is None:
        checks.append(ContinuityCheck("FAIL", "mission:metadata", mission_error or "unknown error"))
    else:
        base_sha = str(mission["base_sha"])
        base_exists = _git(repo_root, ["cat-file", "-e", f"{base_sha}^{{commit}}"], required=False)
        if base_exists.returncode != 0:
            checks.append(
                ContinuityCheck("FAIL", "mission:base_sha", f"mission base does not exist: {base_sha}")
            )
        else:
            base_ancestor = _git(
                repo_root, ["merge-base", "--is-ancestor", base_sha, head], required=False
            )
            checks.append(
                ContinuityCheck(
                    "PASS" if base_ancestor.returncode == 0 else "FAIL",
                    "mission:base_sha",
                    base_sha
                    if base_ancestor.returncode == 0
                    else f"mission base {base_sha} is not an ancestor of HEAD {head}",
                )
            )
        mission_status = mission.get("status")
        state_status = state.get("status") if state else None
        if mission_status in _TERMINAL_MISSION_STATUSES and state_status in _ACTIVE_CHECKPOINT_STATUSES:
            checks.append(
                ContinuityCheck(
                    "FAIL",
                    "mission:active_state",
                    f"mission is {mission_status!r} but session is still {state_status!r}",
                )
            )
        else:
            checks.append(
                ContinuityCheck(
                    "PASS", "mission:active_state", f"mission={mission_status}, session={state_status}"
                )
            )

    if state is not None and handoff is not None:
        agreement_fields = (
            "head_sha",
            "branch",
            "worktree",
            "active_mission",
            "next_action",
            "pull_request",
        )
        disagreements = [field for field in agreement_fields if state.get(field) != handoff.get(field)]
        if disagreements:
            checks.append(
                ContinuityCheck(
                    "FAIL",
                    "checkpoint:agreement",
                    f"STATE and HANDOFF disagree on {disagreements}",
                )
            )
        else:
            checks.append(
                ContinuityCheck(
                    "PASS", "checkpoint:agreement", "STATE and HANDOFF identity/action fields match"
                )
            )

    checks.extend(
        _documentation_checks(
            repo_root,
            authorities=authorities,
            authorities_error=authority_error,
            reading_order=reading_order,
            reading_order_error=order_error,
        )
    )
    sorted_checks = sorted(checks, key=lambda check: (check.name, check.level, check.detail))
    return {
        "checks": sorted_checks,
        "state": state,
        "handoff": handoff,
        "mission": mission,
        "authorities": authorities or {},
        "reading_order": reading_order or [],
        "canonical_checkout": canonical_checkout,
        "worktrees": worktrees,
    }


def run_continuity_checks(
    repo_root: Path,
    *,
    expected_canonical: Path | None = None,
    now: datetime | None = None,
    max_age: timedelta = DEFAULT_MAX_CHECKPOINT_AGE,
    github_lookup: GitHubLookup | None = None,
) -> list[ContinuityCheck]:
    """Return deterministic continuity checks for doctor and CI callers."""
    inspection = inspect_continuity(
        repo_root,
        expected_canonical=expected_canonical,
        now=now,
        max_age=max_age,
        github_lookup=github_lookup,
    )
    return list(inspection["checks"])


def _working_tree(repo_root: Path) -> dict[str, Any]:
    result = _git(repo_root, ["status", "--porcelain=v1", "--untracked-files=all"])
    entries = [
        {"code": line[:2], "path": line[3:]}
        for line in result.stdout.splitlines()
        if len(line) >= 4
    ]
    entries.sort(key=lambda entry: (entry["path"], entry["code"]))
    return {
        "state": "dirty" if entries else "clean",
        "changed_paths": len(entries),
        "entries": entries,
    }


def _recent_commits(repo_root: Path, limit: int) -> list[dict[str, str]]:
    result = _git(
        repo_root,
        ["log", f"-{limit}", "--format=%H%x00%cI%x00%s"],
    )
    commits: list[dict[str, str]] = []
    for line in result.stdout.splitlines():
        fields = line.split("\x00", maxsplit=2)
        if len(fields) != 3:
            raise ContextReceiptError(f"git log returned an invalid record: {line!r}")
        commits.append({"sha": fields[0], "committed_at": fields[1], "summary": fields[2]})
    return commits


def _origin_main_relation(repo_root: Path, head: str) -> dict[str, Any]:
    resolved = _git(repo_root, ["rev-parse", "--verify", "origin/main"], required=False)
    if resolved.returncode != 0:
        return {
            "state": "unknown",
            "sha": None,
            "ahead": None,
            "behind": None,
            "merge_base": None,
            "remote_freshness": "unknown",
            "reason": "origin/main does not resolve locally",
        }
    origin_sha = resolved.stdout.strip()
    counts = _git(repo_root, ["rev-list", "--left-right", "--count", f"origin/main...{head}"])
    fields = counts.stdout.split()
    if len(fields) != 2:
        raise ContextReceiptError(f"git rev-list returned invalid ahead/behind counts: {counts.stdout!r}")
    merge_base = _git(repo_root, ["merge-base", "origin/main", head]).stdout.strip()
    return {
        "state": "available",
        "sha": origin_sha,
        "ahead": int(fields[1]),
        "behind": int(fields[0]),
        "merge_base": merge_base,
        "remote_freshness": "unknown",
        "reason": "no fetch performed; relation uses the local remote-tracking ref",
    }


def _builder_summary(canonical_checkout: Path) -> dict[str, Any]:
    db_path = canonical_checkout / "data" / "kittybuilder" / "builder_queue.db"
    if not db_path.exists():
        return {
            "state": "unavailable",
            "source": "gateway.builder_status.build_control_plane_summary",
            "database": str(db_path),
            "reason": "Builder queue database does not exist; no empty state was inferred",
            "schema_version": None,
            "queue": None,
            "initiatives": None,
        }
    try:
        snapshot = builder_status.build_control_plane_summary(db_path=db_path)
    except (KeyError, OSError, RuntimeError, TypeError, ValueError, sqlite3.Error) as exc:
        return {
            "state": "unknown",
            "source": "gateway.builder_status.build_control_plane_summary",
            "database": str(db_path),
            "reason": f"Builder projection failed: {type(exc).__name__}: {exc}",
            "schema_version": None,
            "queue": None,
            "initiatives": None,
        }
    initiatives = [
        dict(item)
        for item in snapshot.get("initiatives", [])
    ]
    initiatives.sort(key=lambda item: str(item["initiative_id"]))
    return {
        "state": "available",
        "source": "gateway.builder_status.build_control_plane_summary",
        "database": str(db_path),
        "reason": None,
        "schema_version": snapshot.get("schema_version"),
        "queue": snapshot.get("queue"),
        "initiatives": initiatives,
    }


def build_context_receipt(
    repo_root: Path,
    *,
    expected_canonical: Path | None = None,
    now: datetime | None = None,
    max_age: timedelta = DEFAULT_MAX_CHECKPOINT_AGE,
    github_lookup: GitHubLookup | None = None,
    recent_commit_limit: int = DEFAULT_RECENT_COMMITS,
) -> dict[str, Any]:
    """Build the stable JSON-ready context receipt for an agent cold start."""
    repo_root = _resolve_repo_root(repo_root)
    head = _git(repo_root, ["rev-parse", "HEAD"]).stdout.strip()
    branch = _current_branch(repo_root)
    inspection = inspect_continuity(
        repo_root,
        expected_canonical=expected_canonical,
        now=now,
        max_age=max_age,
        github_lookup=github_lookup,
    )
    checks: list[ContinuityCheck] = inspection["checks"]
    builder = _builder_summary(inspection["canonical_checkout"])
    origin_main_relation = _origin_main_relation(repo_root, head)
    unknowns = [
        {
            "field": "git.origin_main.remote_freshness",
            "reason": "context command does not fetch; local origin/main may be stale",
        }
    ]
    if branch is None:
        unknowns.append({"field": "git.branch", "reason": "HEAD is detached"})
    if origin_main_relation["state"] != "available":
        unknowns.append(
            {"field": "git.origin_main", "reason": origin_main_relation["reason"]}
        )
    if builder["state"] != "available":
        unknowns.append({"field": "builder", "reason": builder["reason"]})
    for field, value in (
        ("continuity.state", inspection["state"]),
        ("continuity.handoff", inspection["handoff"]),
        ("continuity.active_mission", inspection["mission"]),
    ):
        if value is None:
            unknowns.append({"field": field, "reason": "structured metadata is invalid or missing"})
    state = inspection["state"] or {}
    failures = [check for check in checks if check.level == "FAIL"]
    warnings = [check for check in checks if check.level == "WARN"]
    for check in warnings:
        unknowns.append(
            {"field": f"continuity.{check.name}", "reason": check.detail}
        )
    unknowns.sort(key=lambda item: (item["field"], str(item["reason"])))
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": not failures,
        "repository": {
            "repo_path": str(repo_root),
            "canonical_checkout": str(inspection["canonical_checkout"]),
            "registered_worktrees": [str(path) for path in inspection["worktrees"]],
        },
        "git": {
            "branch": branch,
            "head": head,
            "origin_main": origin_main_relation,
            "working_tree": _working_tree(repo_root),
            "recent_commits": _recent_commits(repo_root, recent_commit_limit),
        },
        "continuity": {
            "summary": {
                "pass": sum(check.level == "PASS" for check in checks),
                "warn": len(warnings),
                "fail": len(failures),
            },
            "checks": [asdict(check) for check in checks],
            "state": inspection["state"],
            "handoff": inspection["handoff"],
            "active_mission": inspection["mission"],
        },
        "documentation": {
            "authority_map": AUTHORITY_MAP_PATH.as_posix(),
            "authorities": inspection["authorities"],
            "reading_order": inspection["reading_order"],
        },
        "builder": builder,
        "blockers": state.get("blockers") if state else None,
        "next_action": state.get("next_action") if state else None,
        "evidence": {
            "receipt_source": "gateway.context_receipt",
            "git_source": "local repository commands; no fetch performed",
            "checkpoint_source": [STATE_PATH.as_posix(), HANDOFF_PATH.as_posix()],
            "mission_source": ACTIVE_MISSION_PATH.as_posix(),
            "builder_source": builder["source"],
            "head": head,
        },
        "unknowns": unknowns,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="derive a deterministic Kitty context receipt")
    parser.add_argument(
        "--agent",
        action="store_true",
        required=True,
        help="emit deterministic JSON for an agent cold start",
    )
    args = parser.parse_args(argv)
    if not args.agent:
        parser.error("--agent is required")
    try:
        receipt = build_context_receipt(ROOT)
    except ContextReceiptError as exc:
        print(f"context receipt failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
