#!/usr/bin/env python3
"""Machine-readable coordination for interactive Kitty coding lanes.

GitHub issue #490 is the durable interactive claim surface. KittyBuilder keeps
its own authoritative execution/lease state; this module only projects it.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Sequence

MARKER_RE = re.compile(r"<!--\s*kitty-lane:v1\s*(\{.*?\})\s*-->", re.S)
LANE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{1,63}$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
MAX_LEASE = timedelta(hours=4)
MUTABLE_STATUSES = frozenset({"own", "review", "integrate", "dependency"})
TERMINAL_STATUSES = frozenset({"released", "complete"})
ALL_STATUSES = MUTABLE_STATUSES | TERMINAL_STATUSES
ALL_EVENTS = frozenset({"claim", "refresh", "release", "complete"})


class ProtocolError(ValueError):
    """Raised when a structured lane event violates the v1 protocol."""


@dataclass(frozen=True)
class LaneEvent:
    lane_id: str
    event: str
    owner: str
    execution_owner: str
    lane: str
    base_sha: str
    head_sha: str
    branch: str
    worktree: str
    output: str
    paths: tuple[str, ...]
    status: str
    claim_started_at: datetime
    recorded_at: datetime
    lease_until: datetime | None
    comment_id: int | None = None
    github_created_at: datetime | None = None


@dataclass(frozen=True)
class LaneState:
    event: LaneEvent
    stale: bool
    blocking: bool

    @property
    def lane_id(self) -> str:
        return self.event.lane_id

    @property
    def status(self) -> str:
        return self.event.status

    @property
    def branch(self) -> str:
        return self.event.branch

    @property
    def paths(self) -> tuple[str, ...]:
        return self.event.paths


@dataclass(frozen=True)
class ExternalScope:
    kind: str
    source_id: str
    branch: str | None
    paths: tuple[str, ...]
    unbounded: bool = False


@dataclass(frozen=True)
class Collision:
    source_kind: str
    source_id: str
    overlaps: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class RegistryCollision:
    winner_lane_id: str
    loser_lane_id: str
    overlaps: tuple[tuple[str, str], ...]


def _parse_timestamp(value: object, *, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ProtocolError(f"{field} must be a non-empty ISO-8601 string")
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ProtocolError(f"{field} must be valid ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ProtocolError(f"{field} must include a timezone")
    return parsed.astimezone(timezone.utc)


def normalize_claim_path(raw: object) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise ProtocolError("claim paths must be non-empty strings")
    value = raw.strip().replace("\\", "/")
    if value.startswith("/") or value.startswith("../") or "/../" in value:
        raise ProtocolError("claim paths must be repo-relative and may not traverse parents")
    if value.startswith("./"):
        value = value[2:]
    if any(ch in value for ch in "?[]{}") or ("*" in value and not value.endswith("/**")):
        raise ProtocolError("claim paths support only exact paths or /** subtree claims")
    if value.count("*") not in {0, 2}:
        raise ProtocolError("claim paths support only exact paths or /** subtree claims")
    if value.endswith("/**"):
        prefix = value[:-3].rstrip("/")
        if not prefix or "*" in prefix:
            raise ProtocolError("claim paths support only exact paths or /** subtree claims")
        value = prefix + "/**"
    elif "*" in value:
        raise ProtocolError("claim paths support only exact paths or /** subtree claims")
    if not value:
        raise ProtocolError("claim paths must be repo-relative")
    return value


def _require_text(payload: dict[str, object], field: str, *, max_len: int = 255) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ProtocolError(f"{field} must be a non-empty string")
    value = value.strip()
    if len(value) > max_len:
        raise ProtocolError(f"{field} exceeds {max_len} characters")
    return value


def validate_payload(payload: dict[str, object]) -> dict[str, object]:
    if payload.get("schema_version") != 1:
        raise ProtocolError("schema_version must be 1")
    lane_id = _require_text(payload, "lane_id", max_len=64)
    if not LANE_ID_RE.fullmatch(lane_id):
        raise ProtocolError("lane_id must use lowercase letters, numbers, dot, dash, or underscore")
    event = _require_text(payload, "event", max_len=32)
    status = _require_text(payload, "status", max_len=32)
    if event not in ALL_EVENTS:
        raise ProtocolError(f"unsupported event: {event}")
    if status not in ALL_STATUSES:
        raise ProtocolError(f"unsupported status: {status}")
    if event in {"release", "complete"} and status not in TERMINAL_STATUSES:
        raise ProtocolError("terminal events require released or complete status")
    if event in {"claim", "refresh"} and status not in MUTABLE_STATUSES:
        raise ProtocolError("claim/refresh events require a mutable status")
    execution_owner = _require_text(payload, "execution_owner", max_len=32)
    if execution_owner != "interactive":
        raise ProtocolError("GitHub lane events are only for interactive ownership")
    for field, limit in (("owner", 128), ("lane", 240), ("branch", 255),
                         ("worktree", 255), ("output", 255)):
        _require_text(payload, field, max_len=limit)
    for field in ("base_sha", "head_sha"):
        value = _require_text(payload, field, max_len=40)
        if not SHA_RE.fullmatch(value):
            raise ProtocolError(f"{field} must be a 40-character lowercase git SHA")

    raw_paths = payload.get("paths")
    if not isinstance(raw_paths, list) or not raw_paths:
        raise ProtocolError("paths must be a non-empty array")
    if len(raw_paths) > 64:
        raise ProtocolError("paths may contain at most 64 claims")
    paths = [normalize_claim_path(value) for value in raw_paths]
    if len(paths) != len(set(paths)):
        raise ProtocolError("paths may not contain duplicates")

    claim_started_at = _parse_timestamp(payload.get("claim_started_at"), field="claim_started_at")
    recorded_at = _parse_timestamp(payload.get("recorded_at"), field="recorded_at")
    lease_raw = payload.get("lease_until")
    if status in TERMINAL_STATUSES:
        if lease_raw is not None:
            raise ProtocolError("terminal events must set lease_until to null")
    else:
        lease_until = _parse_timestamp(lease_raw, field="lease_until")
        if lease_until <= recorded_at:
            raise ProtocolError("lease_until must be later than recorded_at")
        if lease_until - recorded_at > MAX_LEASE:
            raise ProtocolError("interactive leases may not exceed four hours")
    if claim_started_at > recorded_at:
        raise ProtocolError("claim_started_at may not be later than recorded_at")
    return {**payload, "paths": paths}


def event_from_payload(
    payload: dict[str, object],
    *,
    comment_id: int | None = None,
    github_created_at: datetime | None = None,
) -> LaneEvent:
    normalized = validate_payload(payload)
    lease_raw = normalized.get("lease_until")
    lease_until = None if lease_raw is None else _parse_timestamp(lease_raw, field="lease_until")
    paths_value = normalized["paths"]
    if not isinstance(paths_value, list):
        raise ProtocolError("validated paths unexpectedly stopped being an array")
    return LaneEvent(
        lane_id=str(normalized["lane_id"]),
        event=str(normalized["event"]),
        owner=str(normalized["owner"]),
        execution_owner=str(normalized["execution_owner"]),
        lane=str(normalized["lane"]),
        base_sha=str(normalized["base_sha"]),
        head_sha=str(normalized["head_sha"]),
        branch=str(normalized["branch"]),
        worktree=str(normalized["worktree"]),
        output=str(normalized["output"]),
        paths=tuple(str(path) for path in paths_value),
        status=str(normalized["status"]),
        claim_started_at=_parse_timestamp(normalized["claim_started_at"], field="claim_started_at"),
        recorded_at=_parse_timestamp(normalized["recorded_at"], field="recorded_at"),
        lease_until=lease_until,
        comment_id=comment_id,
        github_created_at=github_created_at,
    )


def _canonical_payload(event: LaneEvent) -> dict[str, object]:
    def stamp(value: datetime | None) -> str | None:
        if value is None:
            return None
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    return {
        "schema_version": 1,
        "lane_id": event.lane_id,
        "event": event.event,
        "owner": event.owner,
        "execution_owner": event.execution_owner,
        "lane": event.lane,
        "base_sha": event.base_sha,
        "head_sha": event.head_sha,
        "branch": event.branch,
        "worktree": event.worktree,
        "output": event.output,
        "paths": list(event.paths),
        "status": event.status,
        "claim_started_at": stamp(event.claim_started_at),
        "recorded_at": stamp(event.recorded_at),
        "lease_until": stamp(event.lease_until),
    }


def render_event_comment(payload: dict[str, object]) -> str:
    event = event_from_payload(payload)
    canonical = _canonical_payload(event)
    lease = canonical["lease_until"] or "terminal"
    human = [
        f"OWNER: {event.owner}",
        f"LANE: {event.lane}",
        f"BASE: `{event.base_sha}`",
        f"OUTPUT: {event.output}",
        f"STATUS: {event.status}; lease_until={lease}",
        "PATH CLAIMS: " + ", ".join(f"`{path}`" for path in event.paths),
    ]
    encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return "\n".join(human) + f"\n\n<!-- kitty-lane:v1\n{encoded}\n-->"


def parse_lane_comment(
    body: str,
    *,
    comment_id: int | None = None,
    github_created_at: datetime | None = None,
) -> LaneEvent | None:
    match = MARKER_RE.search(body or "")
    if not match:
        return None
    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise ProtocolError(f"invalid JSON in kitty-lane:v1 marker: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise ProtocolError("kitty-lane:v1 payload must be a JSON object")
    return event_from_payload(payload, comment_id=comment_id, github_created_at=github_created_at)


def current_lane_states(
    events: Sequence[LaneEvent], *, now: datetime | None = None
) -> dict[str, LaneState]:
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    latest: dict[str, LaneEvent] = {}
    for event in events:
        previous = latest.get(event.lane_id)
        ordering = (event.recorded_at, event.comment_id or -1)
        if previous is None:
            latest[event.lane_id] = event
            continue
        previous_ordering = (previous.recorded_at, previous.comment_id or -1)
        if ordering > previous_ordering:
            latest[event.lane_id] = event

    states: dict[str, LaneState] = {}
    for lane_id, event in latest.items():
        terminal = event.status in TERMINAL_STATUSES
        stale = not terminal and (event.lease_until is None or event.lease_until <= now)
        blocking = event.status == "own" and not stale and not terminal
        states[lane_id] = LaneState(event=event, stale=stale, blocking=blocking)
    return states


def _split_scope(path: str) -> tuple[str, bool]:
    normalized = normalize_claim_path(path)
    if normalized.endswith("/**"):
        return normalized[:-3].rstrip("/"), True
    return normalized.rstrip("/"), False


def paths_overlap(left: str, right: str) -> bool:
    left_path, left_tree = _split_scope(left)
    right_path, right_tree = _split_scope(right)
    if left_path == right_path:
        return True
    if left_tree and (right_path == left_path or right_path.startswith(left_path + "/")):
        return True
    if right_tree and (left_path == right_path or left_path.startswith(right_path + "/")):
        return True
    return False


def _overlap_pairs(left: Sequence[str], right: Sequence[str]) -> tuple[tuple[str, str], ...]:
    return tuple(
        (a, b)
        for a in left
        for b in right
        if paths_overlap(a, b)
    )


def detect_candidate_collisions(
    *,
    lane_id: str,
    branch: str,
    paths: Sequence[str],
    states: dict[str, LaneState],
    external_scopes: Sequence[ExternalScope],
) -> list[Collision]:
    candidate = tuple(normalize_claim_path(path) for path in paths)
    collisions: list[Collision] = []
    for other_id, state in sorted(states.items()):
        if other_id == lane_id or not state.blocking:
            continue
        overlaps = _overlap_pairs(candidate, state.paths)
        if overlaps:
            collisions.append(Collision("claim", other_id, overlaps))

    for scope in external_scopes:
        if scope.branch and scope.branch == branch:
            continue
        if scope.unbounded:
            overlaps = tuple((path, "<repo-wide>") for path in candidate)
        else:
            overlaps = _overlap_pairs(candidate, scope.paths)
        if overlaps:
            collisions.append(Collision(scope.kind, scope.source_id, overlaps))
    return collisions


def _durable_order(state: LaneState) -> tuple[datetime, int, str]:
    event = state.event
    timestamp = event.github_created_at or event.recorded_at
    return timestamp, event.comment_id or 2**63 - 1, event.lane_id


def registry_collisions(states: dict[str, LaneState]) -> list[RegistryCollision]:
    active = [state for state in states.values() if state.blocking]
    conflicts: list[RegistryCollision] = []
    for index, left in enumerate(active):
        for right in active[index + 1 :]:
            overlaps = _overlap_pairs(left.paths, right.paths)
            if not overlaps:
                continue
            winner, loser = sorted((left, right), key=_durable_order)
            conflicts.append(
                RegistryCollision(winner.lane_id, loser.lane_id, overlaps)
            )
    return sorted(conflicts, key=lambda item: (item.winner_lane_id, item.loser_lane_id))


class EvidenceUnavailableError(RuntimeError):
    """Raised when a mutating claim would rely on unknown coordination state."""


class CollisionError(RuntimeError):
    """Raised when a proposed implementation claim overlaps live work."""


@dataclass(frozen=True)
class EvidenceGap:
    source: str
    reason: str


@dataclass(frozen=True)
class WorktreeRecord:
    path: str
    head: str
    branch: str | None
    detached: bool = False


@dataclass(frozen=True)
class RepoIdentity:
    base_sha: str
    head_sha: str
    branch: str
    worktree: str


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


def extract_events_from_github_comments(
    comments: Sequence[dict[str, object]],
) -> tuple[list[LaneEvent], list[EvidenceGap]]:
    events: list[LaneEvent] = []
    gaps: list[EvidenceGap] = []
    for comment in comments:
        body = comment.get("body")
        if not isinstance(body, str) or "kitty-lane:v1" not in body:
            continue
        comment_id = comment.get("id")
        created_raw = comment.get("created_at")
        try:
            created_at = _parse_timestamp(created_raw, field="github created_at")
            parsed_comment_id: int | None
            if isinstance(comment_id, int):
                parsed_comment_id = comment_id
            elif isinstance(comment_id, str) and comment_id.isdigit():
                parsed_comment_id = int(comment_id)
            elif comment_id is None:
                parsed_comment_id = None
            else:
                raise ProtocolError("GitHub comment id must be numeric")
            event = parse_lane_comment(
                body,
                comment_id=parsed_comment_id,
                github_created_at=created_at,
            )
            if event is not None:
                events.append(event)
        except (ProtocolError, TypeError, ValueError) as exc:
            label = f"#{comment_id}" if comment_id is not None else "<unknown>"
            gaps.append(EvidenceGap(f"github_comment:{label}", str(exc)))
    return events, gaps


def parse_worktree_porcelain(text: str) -> list[WorktreeRecord]:
    records: list[WorktreeRecord] = []
    current: dict[str, object] = {}

    def flush() -> None:
        if not current.get("path"):
            current.clear()
            return
        branch_value = current.get("branch")
        branch = branch_value if isinstance(branch_value, str) else None
        records.append(
            WorktreeRecord(
                path=str(current["path"]),
                head=str(current.get("head", "")),
                branch=branch,
                detached=bool(current.get("detached", False)),
            )
        )
        current.clear()

    for raw in text.splitlines() + [""]:
        line = raw.strip()
        if not line:
            flush()
            continue
        if line.startswith("worktree "):
            current["path"] = line[len("worktree ") :]
        elif line.startswith("HEAD "):
            current["head"] = line[len("HEAD ") :]
        elif line.startswith("branch refs/heads/"):
            current["branch"] = line[len("branch refs/heads/") :]
        elif line == "detached":
            current["detached"] = True
    return records


def builder_scopes_from_db(
    db_path: Path,
) -> tuple[list[ExternalScope], EvidenceGap | None]:
    db_path = Path(db_path)
    if not db_path.is_file():
        return [], EvidenceGap("builder", f"Builder DB missing at {db_path}")
    try:
        uri = f"file:{db_path}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=5.0)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT id, state, allowed_paths_json, lease_owner, lease_expires_at "
                "FROM tasks WHERE state IN ('claimed', 'running') ORDER BY id"
            ).fetchall()
        finally:
            conn.close()
    except sqlite3.Error as exc:
        return [], EvidenceGap("builder", f"read-only Builder projection failed: {exc}")

    scopes: list[ExternalScope] = []
    for row in rows:
        raw = row["allowed_paths_json"]
        if raw is None:
            scopes.append(ExternalScope("builder", str(row["id"]), None, (), True))
            continue
        try:
            allowed = json.loads(raw)
        except (json.JSONDecodeError, TypeError) as exc:
            return [], EvidenceGap("builder", f"invalid allowed_paths_json for {row['id']}: {exc}")
        if not isinstance(allowed, list):
            return [], EvidenceGap(
                "builder", f"invalid allowed_paths_json for {row['id']}: expected array"
            )
        if not allowed:
            scopes.append(ExternalScope("builder", str(row["id"]), None, (), True))
            continue
        projected: list[str] = []
        for item in allowed:
            try:
                normalized = normalize_claim_path(item)
            except ProtocolError as exc:
                return [], EvidenceGap(
                    "builder", f"invalid allowed path for {row['id']}: {exc}"
                )
            if normalized.endswith("/**"):
                return [], EvidenceGap(
                    "builder", f"invalid allowed path for {row['id']}: Builder paths are literal"
                )
            projected.append(normalized.rstrip("/") + "/**")
        scopes.append(
            ExternalScope(
                kind="builder",
                source_id=str(row["id"]),
                branch=None,
                paths=tuple(projected),
            )
        )
    return scopes, None


def _stamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def build_claim_payload(
    *,
    lane_id: str,
    owner: str,
    lane: str,
    output: str,
    paths: Sequence[str],
    identity: RepoIdentity,
    now: datetime | None = None,
    lease_minutes: int = 180,
    status: str = "own",
) -> dict[str, object]:
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if not 1 <= lease_minutes <= 240:
        raise ProtocolError("lease_minutes must be between 1 and 240")
    payload: dict[str, object] = {
        "schema_version": 1,
        "lane_id": lane_id,
        "event": "claim",
        "owner": owner,
        "execution_owner": "interactive",
        "lane": lane,
        "base_sha": identity.base_sha,
        "head_sha": identity.head_sha,
        "branch": identity.branch,
        "worktree": identity.worktree,
        "output": output,
        "paths": list(paths),
        "status": status,
        "claim_started_at": _stamp(now),
        "recorded_at": _stamp(now),
        "lease_until": _stamp(now + timedelta(minutes=lease_minutes)),
    }
    return validate_payload(payload)


def _run_command(
    args: Sequence[str], *, cwd: Path | None = None, timeout: int = 30
) -> CommandResult:
    env = os.environ.copy()
    env.pop("GITHUB_TOKEN", None)
    try:
        completed = subprocess.run(
            list(args),
            cwd=str(cwd) if cwd is not None else None,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return CommandResult(127, "", str(exc))
    return CommandResult(completed.returncode, completed.stdout, completed.stderr)


def publish_claim(
    payload: dict[str, object],
    *,
    states: dict[str, LaneState],
    external_scopes: Sequence[ExternalScope],
    evidence_gaps: Sequence[EvidenceGap],
    repo: str,
    issue: int,
    post: bool,
    runner: Callable[..., CommandResult] = _run_command,
) -> dict[str, object]:
    event = event_from_payload(payload)
    if post and evidence_gaps:
        details = "; ".join(f"{gap.source}: {gap.reason}" for gap in evidence_gaps)
        raise EvidenceUnavailableError(
            "refusing to publish OWN claim with unknown coordination evidence: " + details
        )
    collisions = detect_candidate_collisions(
        lane_id=event.lane_id,
        branch=event.branch,
        paths=event.paths,
        states=states,
        external_scopes=external_scopes,
    )
    if event.status == "own" and collisions:
        names = ", ".join(f"{item.source_kind}:{item.source_id}" for item in collisions)
        raise CollisionError(f"claim collides with live work: {names}")
    body = render_event_comment(payload)
    if not post:
        return {
            "posted": False,
            "body": body,
            "collisions": [item.source_id for item in collisions],
            "evidence_gaps": [gap.source for gap in evidence_gaps],
        }
    comment_id = _post_event_comment(payload, repo=repo, issue=issue, runner=runner)
    if event.status != "own":
        return {"posted": True, "comment_id": comment_id, "body": body}

    refreshed_events, refreshed_gaps = load_github_lane_events(repo, issue, runner=runner)
    if refreshed_gaps:
        details = "; ".join(f"{gap.source}: {gap.reason}" for gap in refreshed_gaps)
        raise EvidenceUnavailableError(
            "claim was posted but durable ownership could not be re-verified: " + details
        )
    refreshed_states = current_lane_states(refreshed_events)
    for conflict in registry_collisions(refreshed_states):
        if conflict.loser_lane_id != event.lane_id:
            continue
        current = refreshed_states.get(event.lane_id)
        if current is not None:
            identity = RepoIdentity(
                current.event.base_sha,
                current.event.head_sha,
                current.event.branch,
                current.event.worktree,
            )
            release = build_followup_payload(
                state=current,
                event="release",
                identity=identity,
                owner=current.event.owner,
            )
            _post_event_comment(release, repo=repo, issue=issue, runner=runner)
        raise CollisionError(
            f"claim lost the durable claim race to {conflict.winner_lane_id}; released self"
        )
    return {
        "posted": True,
        "comment_id": comment_id,
        "body": body,
        "verified": True,
    }


def load_github_lane_events(
    repo: str,
    issue: int,
    *,
    runner: Callable[..., CommandResult] = _run_command,
) -> tuple[list[LaneEvent], list[EvidenceGap]]:
    result = runner(
        [
            "gh",
            "api",
            "--paginate",
            "--slurp",
            f"/repos/{repo}/issues/{issue}/comments?per_page=100",
        ]
    )
    if result.returncode != 0:
        reason = result.stderr.strip() or result.stdout.strip() or "unknown gh failure"
        return [], [EvidenceGap("github", reason)]
    try:
        decoded = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return [], [EvidenceGap("github", f"invalid comments JSON: {exc.msg}")]
    if not isinstance(decoded, list):
        return [], [EvidenceGap("github", "comments response is not an array")]
    if decoded and all(isinstance(page, list) for page in decoded):
        comments = [item for page in decoded for item in page if isinstance(item, dict)]
    else:
        comments = [item for item in decoded if isinstance(item, dict)]
    return extract_events_from_github_comments(comments)


def load_open_pr_scopes(
    repo: str,
    *,
    runner: Callable[..., CommandResult] = _run_command,
) -> tuple[list[ExternalScope], list[EvidenceGap]]:
    result = runner(
        [
            "gh", "pr", "list", "--repo", repo, "--state", "open", "--limit", "100",
            "--json", "number,headRefName,title",
        ]
    )
    if result.returncode != 0:
        reason = result.stderr.strip() or result.stdout.strip() or "unknown gh failure"
        return [], [EvidenceGap("github_prs", reason)]
    try:
        prs = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return [], [EvidenceGap("github_prs", f"invalid PR list JSON: {exc.msg}")]
    if not isinstance(prs, list):
        return [], [EvidenceGap("github_prs", "PR list response is not an array")]
    scopes: list[ExternalScope] = []
    gaps: list[EvidenceGap] = []
    if len(prs) >= 100:
        gaps.append(EvidenceGap("github_prs", "open PR inventory hit the 100-item limit"))
    for pr in prs:
        if not isinstance(pr, dict) or not isinstance(pr.get("number"), int):
            gaps.append(EvidenceGap("github_prs", "malformed PR list entry"))
            continue
        number = int(pr["number"])
        files_result = runner(
            ["gh", "pr", "view", str(number), "--repo", repo, "--json", "files"]
        )
        if files_result.returncode != 0:
            reason = files_result.stderr.strip() or files_result.stdout.strip() or "unknown gh failure"
            gaps.append(EvidenceGap(f"github_pr:#{number}", reason))
            continue
        try:
            detail = json.loads(files_result.stdout)
            files = detail.get("files", []) if isinstance(detail, dict) else []
            paths = tuple(
                normalize_claim_path(item["path"])
                for item in files
                if isinstance(item, dict) and isinstance(item.get("path"), str)
            )
        except (json.JSONDecodeError, ProtocolError, KeyError) as exc:
            gaps.append(EvidenceGap(f"github_pr:#{number}", f"invalid files response: {exc}"))
            continue
        branch = pr.get("headRefName") if isinstance(pr.get("headRefName"), str) else None
        scopes.append(
            ExternalScope(
                kind="pull_request",
                source_id=f"#{number}",
                branch=branch,
                paths=paths,
            )
        )
    return scopes, gaps


def _parse_status_paths(text: str) -> tuple[str, ...]:
    paths: set[str] = set()
    for entry in text.split("\0"):
        if not entry:
            continue
        if len(entry) >= 4 and entry[2] == " ":
            raw = entry[3:]
        else:
            raw = entry
        try:
            paths.add(normalize_claim_path(raw))
        except ProtocolError:
            continue
    return tuple(sorted(paths))


def load_worktree_scopes(
    repo_root: Path,
    *,
    base_ref: str,
    ignore_branches: set[str],
    runner: Callable[..., CommandResult] = _run_command,
) -> tuple[list[ExternalScope], list[EvidenceGap]]:
    listing = runner(["git", "worktree", "list", "--porcelain"], cwd=repo_root)
    if listing.returncode != 0:
        reason = listing.stderr.strip() or listing.stdout.strip() or "git worktree list failed"
        return [], [EvidenceGap("worktrees", reason)]

    scopes: list[ExternalScope] = []
    gaps: list[EvidenceGap] = []
    for record in parse_worktree_porcelain(listing.stdout):
        if record.branch in ignore_branches:
            continue
        status = runner(
            ["git", "status", "--porcelain=v1", "-z"],
            cwd=Path(record.path),
        )
        if status.returncode != 0:
            gaps.append(EvidenceGap(f"worktree:{record.path}", "git status failed"))
            continue
        paths = set(_parse_status_paths(status.stdout))
        if record.branch:
            merged = runner(
                ["git", "merge-base", "--is-ancestor", record.branch, base_ref],
                cwd=repo_root,
            )
            if merged.returncode not in {0, 1}:
                gaps.append(
                    EvidenceGap(f"worktree:{record.path}", "cannot compare branch with base")
                )
                continue
            if merged.returncode == 1:
                diff = runner(
                    ["git", "diff", "--name-only", f"{base_ref}...{record.branch}"],
                    cwd=repo_root,
                )
                if diff.returncode != 0:
                    gaps.append(
                        EvidenceGap(f"worktree:{record.path}", "cannot diff branch against base")
                    )
                    continue
                for raw in diff.stdout.splitlines():
                    if raw.strip():
                        try:
                            paths.add(normalize_claim_path(raw))
                        except ProtocolError as exc:
                            gaps.append(EvidenceGap(f"worktree:{record.path}", str(exc)))
        if not paths:
            continue
        scopes.append(
            ExternalScope("worktree", record.path, record.branch, tuple(sorted(paths)))
        )
    return scopes, gaps


def read_repo_identity(
    repo_root: Path,
    *,
    base_ref: str = "origin/main",
    runner: Callable[..., CommandResult] = _run_command,
) -> tuple[RepoIdentity | None, EvidenceGap | None]:
    commands = {
        "base": ["git", "rev-parse", base_ref],
        "head": ["git", "rev-parse", "HEAD"],
        "branch": ["git", "branch", "--show-current"],
        "root": ["git", "rev-parse", "--show-toplevel"],
    }
    values: dict[str, str] = {}
    for label, args in commands.items():
        result = runner(args, cwd=repo_root)
        if result.returncode != 0:
            reason = result.stderr.strip() or result.stdout.strip() or f"{label} probe failed"
            return None, EvidenceGap("git_identity", reason)
        values[label] = result.stdout.strip()
    if not SHA_RE.fullmatch(values["base"]) or not SHA_RE.fullmatch(values["head"]):
        return None, EvidenceGap("git_identity", "base/head did not resolve to full SHAs")
    if not values["branch"]:
        return None, EvidenceGap("git_identity", "detached HEAD cannot publish an OWN claim")
    return (
        RepoIdentity(
            base_sha=values["base"],
            head_sha=values["head"],
            branch=values["branch"],
            worktree=Path(values["root"]).name,
        ),
        None,
    )


@dataclass(frozen=True)
class Survey:
    identity: RepoIdentity | None
    states: dict[str, LaneState]
    external_scopes: tuple[ExternalScope, ...]
    registry_conflicts: tuple[RegistryCollision, ...]
    evidence_gaps: tuple[EvidenceGap, ...]

    @property
    def healthy(self) -> bool:
        return not self.evidence_gaps and not self.registry_conflicts


def build_followup_payload(
    *,
    state: LaneState,
    event: str,
    identity: RepoIdentity,
    owner: str,
    now: datetime | None = None,
    lease_minutes: int = 180,
) -> dict[str, object]:
    if event not in {"refresh", "release", "complete"}:
        raise ProtocolError("follow-up event must be refresh, release, or complete")
    previous = state.event
    if previous.status in TERMINAL_STATUSES:
        raise ProtocolError("terminal lane cannot be refreshed or released again")
    if owner != previous.owner:
        raise ProtocolError("owner does not match the current lane owner")
    if identity.branch != previous.branch:
        raise ProtocolError("follow-up must stay on the lane's claimed branch")
    if event == "refresh" and state.stale:
        raise ProtocolError("stale lane requires preservation/reclamation, not refresh")
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    payload: dict[str, object] = {
        "schema_version": 1,
        "lane_id": previous.lane_id,
        "event": event,
        "owner": previous.owner,
        "execution_owner": "interactive",
        "lane": previous.lane,
        "base_sha": identity.base_sha,
        "head_sha": identity.head_sha,
        "branch": identity.branch,
        "worktree": identity.worktree,
        "output": previous.output,
        "paths": list(previous.paths),
        "status": previous.status,
        "claim_started_at": _stamp(previous.claim_started_at),
        "recorded_at": _stamp(now),
        "lease_until": None,
    }
    if event == "refresh":
        if not 1 <= lease_minutes <= 240:
            raise ProtocolError("lease_minutes must be between 1 and 240")
        payload["lease_until"] = _stamp(now + timedelta(minutes=lease_minutes))
    elif event == "release":
        payload["status"] = "released"
    else:
        payload["status"] = "complete"
    return validate_payload(payload)


def _lane_dict(state: LaneState) -> dict[str, object]:
    event = state.event
    return {
        "lane_id": event.lane_id,
        "owner": event.owner,
        "lane": event.lane,
        "status": event.status,
        "stale": state.stale,
        "blocking": state.blocking,
        "branch": event.branch,
        "worktree": event.worktree,
        "head_sha": event.head_sha,
        "output": event.output,
        "paths": list(event.paths),
        "lease_until": _canonical_payload(event)["lease_until"],
        "comment_id": event.comment_id,
    }


def render_survey(survey: Survey, *, format: str = "markdown") -> str:
    if format not in {"json", "markdown"}:
        raise ProtocolError("survey format must be json or markdown")
    if format == "json":
        identity = None
        if survey.identity is not None:
            identity = {
                "base_sha": survey.identity.base_sha,
                "head_sha": survey.identity.head_sha,
                "branch": survey.identity.branch,
                "worktree": survey.identity.worktree,
            }
        payload = {
            "healthy": survey.healthy,
            "identity": identity,
            "lanes": [_lane_dict(state) for _, state in sorted(survey.states.items())],
            "external_scopes": [
                {
                    "kind": scope.kind,
                    "source_id": scope.source_id,
                    "branch": scope.branch,
                    "paths": list(scope.paths),
                    "unbounded": scope.unbounded,
                }
                for scope in survey.external_scopes
            ],
            "registry_conflicts": [
                {
                    "winner_lane_id": item.winner_lane_id,
                    "loser_lane_id": item.loser_lane_id,
                    "overlaps": [list(pair) for pair in item.overlaps],
                }
                for item in survey.registry_conflicts
            ],
            "evidence_gaps": [
                {"source": gap.source, "reason": gap.reason}
                for gap in survey.evidence_gaps
            ],
        }
        return json.dumps(payload, indent=2, sort_keys=True)

    lines = ["# Kitty Agent Coordination", ""]
    lines.append(f"Status: **{'HEALTHY' if survey.healthy else 'DEGRADED'}**")
    if survey.identity:
        lines.append(
            f"Current: `{survey.identity.branch}` @ `{survey.identity.head_sha[:12]}` "
            f"(base `{survey.identity.base_sha[:12]}`)"
        )
    lines.extend(["", "## Lanes"])
    if not survey.states:
        lines.append("- none")
    for lane_id, state in sorted(survey.states.items()):
        event = state.event
        flags = []
        if state.blocking:
            flags.append("BLOCKING")
        if state.stale:
            flags.append("STALE")
        suffix = f" [{' / '.join(flags)}]" if flags else ""
        lines.append(
            f"- `{lane_id}` — {event.status}{suffix}; owner={event.owner}; "
            f"branch=`{event.branch}`; paths={', '.join(event.paths)}"
        )
    lines.extend(["", "## External scopes"])
    if not survey.external_scopes:
        lines.append("- none")
    for scope in survey.external_scopes:
        scope_paths = "<repo-wide>" if scope.unbounded else ", ".join(scope.paths)
        branch = f"; branch=`{scope.branch}`" if scope.branch else ""
        lines.append(f"- {scope.kind}:{scope.source_id}{branch}; paths={scope_paths}")
    lines.extend(["", "## Registry collisions"])
    if not survey.registry_conflicts:
        lines.append("- none")
    for item in survey.registry_conflicts:
        overlaps = ", ".join(f"{a} ↔ {b}" for a, b in item.overlaps)
        lines.append(
            f"- **COLLISION** winner=`{item.winner_lane_id}` "
            f"loser=`{item.loser_lane_id}`: {overlaps}"
        )
    lines.extend(["", "## Evidence gaps"])
    if not survey.evidence_gaps:
        lines.append("- none")
    for gap in survey.evidence_gaps:
        lines.append(f"- **UNKNOWN** {gap.source}: {gap.reason}")
    return "\n".join(lines) + "\n"


def default_builder_db(
    repo_root: Path,
    *,
    runner: Callable[..., CommandResult] = _run_command,
) -> tuple[Path | None, EvidenceGap | None]:
    result = runner(
        ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
        cwd=repo_root,
    )
    if result.returncode != 0:
        reason = result.stderr.strip() or result.stdout.strip() or "cannot resolve git common dir"
        return None, EvidenceGap("builder", reason)
    common = Path(result.stdout.strip())
    if not common.is_absolute():
        common = (repo_root / common).resolve()
    canonical_root = common.parent if common.name == ".git" else common
    return canonical_root / "data" / "kittybuilder" / "builder_queue.db", None


def collect_live_survey(
    *,
    repo_root: Path,
    repo: str,
    issue: int = 490,
    base_ref: str = "origin/main",
    builder_db: Path | None = None,
    runner: Callable[..., CommandResult] = _run_command,
    now: datetime | None = None,
) -> Survey:
    gaps: list[EvidenceGap] = []
    identity, identity_gap = read_repo_identity(repo_root, base_ref=base_ref, runner=runner)
    if identity_gap:
        gaps.append(identity_gap)
    remote_main_sha, remote_main_gap = load_remote_main_sha(repo, runner=runner)
    if remote_main_gap:
        gaps.append(remote_main_gap)
    elif identity is not None and remote_main_sha is not None:
        freshness_gap = base_freshness_gap(identity, remote_main_sha)
        if freshness_gap:
            gaps.append(freshness_gap)

    events, event_gaps = load_github_lane_events(repo, issue, runner=runner)
    gaps.extend(event_gaps)
    states = current_lane_states(events, now=now)

    pr_scopes, pr_gaps = load_open_pr_scopes(repo, runner=runner)
    gaps.extend(pr_gaps)
    ignored = {identity.branch} if identity is not None else set()
    worktree_scopes, worktree_gaps = load_worktree_scopes(
        repo_root,
        base_ref=base_ref,
        ignore_branches=ignored,
        runner=runner,
    )
    gaps.extend(worktree_gaps)

    resolved_db = builder_db
    if resolved_db is None:
        resolved_db, builder_path_gap = default_builder_db(repo_root, runner=runner)
        if builder_path_gap:
            gaps.append(builder_path_gap)
    builder_scopes: list[ExternalScope] = []
    if resolved_db is not None:
        builder_scopes, builder_gap = builder_scopes_from_db(resolved_db)
        if builder_gap:
            gaps.append(builder_gap)

    external = tuple(pr_scopes + worktree_scopes + builder_scopes)
    return Survey(
        identity=identity,
        states=states,
        external_scopes=external,
        registry_conflicts=tuple(registry_collisions(states)),
        evidence_gaps=tuple(gaps),
    )


def _post_event_comment(
    payload: dict[str, object],
    *,
    repo: str,
    issue: int,
    runner: Callable[..., CommandResult] = _run_command,
) -> int:
    body = render_event_comment(payload)
    result = runner(
        ["gh", "api", "-X", "POST", f"/repos/{repo}/issues/{issue}/comments", "-f", f"body={body}"]
    )
    if result.returncode != 0:
        reason = result.stderr.strip() or result.stdout.strip() or "unknown gh failure"
        raise EvidenceUnavailableError(f"GitHub comment publish failed: {reason}")
    try:
        response = json.loads(result.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise EvidenceUnavailableError("GitHub comment publish returned invalid JSON") from exc
    comment_id = response.get("id")
    if not isinstance(comment_id, int):
        raise EvidenceUnavailableError("GitHub comment publish returned no numeric id")
    return comment_id


def _default_owner() -> str:
    configured = os.environ.get("KITTY_AGENT_OWNER", "").strip()
    if configured:
        return configured
    user = os.environ.get("USER", "interactive").strip() or "interactive"
    host = socket.gethostname().split(".", 1)[0] or "local"
    return f"{user}@{host}"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Kitty interactive agent coordination registry")
    parser.add_argument("--repo", default="jacob202/kitty")
    parser.add_argument("--issue", type=int, default=490)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--base-ref", default="origin/main")
    parser.add_argument("--builder-db", type=Path)
    sub = parser.add_subparsers(dest="command", required=True)

    survey = sub.add_parser("survey", help="Render the live coordination board")
    survey.add_argument("--format", choices=("json", "markdown"), default="markdown")

    claim = sub.add_parser("claim", help="Claim an interactive implementation lane")
    claim.add_argument("--lane-id", required=True)
    claim.add_argument("--owner", default=_default_owner())
    claim.add_argument("--lane", required=True)
    claim.add_argument("--output", required=True)
    claim.add_argument("--path", dest="paths", action="append", required=True)
    claim.add_argument("--status", choices=sorted(MUTABLE_STATUSES), default="own")
    claim.add_argument("--lease-minutes", type=int, default=180)
    claim.add_argument("--post", action="store_true")

    refresh = sub.add_parser("refresh", help="Refresh an existing lane lease")
    refresh.add_argument("--lane-id", required=True)
    refresh.add_argument("--owner", default=_default_owner())
    refresh.add_argument("--lease-minutes", type=int, default=180)
    refresh.add_argument("--post", action="store_true")

    release = sub.add_parser("release", help="Release or complete an existing lane")
    release.add_argument("--lane-id", required=True)
    release.add_argument("--owner", default=_default_owner())
    release.add_argument("--complete", action="store_true")
    release.add_argument("--post", action="store_true")

    validate = sub.add_parser("validate-comment", help="Validate one kitty-lane:v1 comment")
    validate.add_argument("--file", type=Path, help="Read comment from file; omit for stdin")
    return parser


def _require_identity(survey: Survey) -> RepoIdentity:
    if survey.identity is None:
        raise EvidenceUnavailableError("git identity is unavailable")
    return survey.identity


def _followup_result(
    payload: dict[str, object],
    *,
    repo: str,
    issue: int,
    post: bool,
    evidence_gaps: Sequence[EvidenceGap],
    runner: Callable[..., CommandResult],
    require_complete_evidence: bool,
) -> dict[str, object]:
    if post and require_complete_evidence and evidence_gaps:
        details = "; ".join(f"{gap.source}: {gap.reason}" for gap in evidence_gaps)
        raise EvidenceUnavailableError("refusing follow-up with unknown evidence: " + details)
    body = render_event_comment(payload)
    if not post:
        return {"posted": False, "body": body}
    comment_id = _post_event_comment(payload, repo=repo, issue=issue, runner=runner)
    return {"posted": True, "comment_id": comment_id, "body": body}


def main(
    argv: Sequence[str] | None = None,
    *,
    runner: Callable[..., CommandResult] = _run_command,
    survey_loader: Callable[..., Survey] = collect_live_survey,
) -> int:
    args = _parser().parse_args(list(argv) if argv is not None else None)
    repo_root = args.repo_root.resolve()
    try:
        if args.command == "validate-comment":
            text = args.file.read_text() if args.file is not None else sys.stdin.read()
            event = parse_lane_comment(text)
            if event is None:
                raise ProtocolError("no kitty-lane:v1 marker found")
            print(json.dumps(_canonical_payload(event), indent=2, sort_keys=True))
            return 0

        survey = survey_loader(
            repo_root=repo_root,
            repo=args.repo,
            issue=args.issue,
            base_ref=args.base_ref,
            builder_db=args.builder_db,
            runner=runner,
        )
        if args.command == "survey":
            print(render_survey(survey, format=args.format), end="")
            return 0 if survey.healthy else 1

        identity = _require_identity(survey)
        if args.command == "claim":
            payload = build_claim_payload(
                lane_id=args.lane_id,
                owner=args.owner,
                lane=args.lane,
                output=args.output,
                paths=args.paths,
                identity=identity,
                lease_minutes=args.lease_minutes,
                status=args.status,
            )
            result = publish_claim(
                payload,
                states=survey.states,
                external_scopes=survey.external_scopes,
                evidence_gaps=survey.evidence_gaps,
                repo=args.repo,
                issue=args.issue,
                post=args.post,
                runner=runner,
            )
            print(result["body"])
            return 0
        state = survey.states.get(args.lane_id)
        if state is None:
            print(f"unknown lane: {args.lane_id}", file=sys.stderr)
            return 2

        if args.command == "refresh":
            payload = build_followup_payload(
                state=state,
                event="refresh",
                identity=identity,
                owner=args.owner,
                lease_minutes=args.lease_minutes,
            )
            result = _followup_result(
                payload,
                repo=args.repo,
                issue=args.issue,
                post=args.post,
                evidence_gaps=survey.evidence_gaps,
                runner=runner,
                require_complete_evidence=True,
            )
            print(result["body"])
            return 0

        if args.command == "release":
            terminal_event = "complete" if args.complete else "release"
            payload = build_followup_payload(
                state=state,
                event=terminal_event,
                identity=identity,
                owner=args.owner,
            )
            result = _followup_result(
                payload,
                repo=args.repo,
                issue=args.issue,
                post=args.post,
                evidence_gaps=survey.evidence_gaps,
                runner=runner,
                require_complete_evidence=False,
            )
            print(result["body"])
            return 0
    except (ProtocolError, EvidenceUnavailableError, CollisionError) as exc:
        print(f"coordination: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())


def load_remote_main_sha(
    repo: str,
    *,
    runner: Callable[..., CommandResult] = _run_command,
) -> tuple[str | None, EvidenceGap | None]:
    result = runner(
        ["gh", "api", f"/repos/{repo}/commits/main", "--jq", ".sha"]
    )
    if result.returncode != 0:
        reason = result.stderr.strip() or result.stdout.strip() or "remote main lookup failed"
        return None, EvidenceGap("github_main", reason)
    sha = result.stdout.strip()
    if not SHA_RE.fullmatch(sha):
        return None, EvidenceGap("github_main", "remote main did not resolve to a full SHA")
    return sha, None


def base_freshness_gap(identity: RepoIdentity, remote_main_sha: str) -> EvidenceGap | None:
    if identity.base_sha == remote_main_sha:
        return None
    return EvidenceGap(
        "git_base",
        "local base is stale: "
        f"{identity.base_sha[:12]} != GitHub main {remote_main_sha[:12]}; run git fetch origin",
    )
