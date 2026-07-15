"""KittyBuilder — worker identity and branch lease enforcement.

Verifies that a worker's git state matches the branch lease before any
write.  Called as a preflight at the top of ``run_packet`` or before any
destructive operation on a worktree.

Checks performed (all must pass; any failure returns a finding):

1. A branch lease exists for the packet.
2. The repo root path matches the leased worktree path.
3. The current git branch matches the leased branch.
4. HEAD descends from the lease's ``base_sha`` (no reset or force-push).
5. Every commit between ``base_sha`` and HEAD carries the deterministic
   packet marker ``[<packet_id>]`` — no foreign commits.
6. All changed paths (committed, staged, unstaged, untracked) fall within
   the packet's ``allowed_paths``.

A non-empty finding list means stop immediately via ``EscalationError``.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from gateway import builder_queue as bq

# ---------------------------------------------------------------------------
# Local types (will consolidate with builder_scope.py on merge)
# ---------------------------------------------------------------------------


@dataclass
class ScopeFinding:
    category: str
    field: str
    message: str


class EscalationError(RuntimeError):
    """Raised when identity verification fails — return control to operator."""

    def __init__(
        self,
        findings: list[ScopeFinding],
        *,
        evidence: dict[str, Any] | None = None,
        artifact: dict[str, Any] | None = None,
    ) -> None:
        message = "; ".join(f.message for f in findings) or "identity verification failed"
        super().__init__(message)
        self.findings: list[ScopeFinding] = list(findings)
        self.evidence: dict[str, Any] = evidence or {}
        self.artifact: dict[str, Any] = artifact or {}

# ---------------------------------------------------------------------------
# Git helpers (local to this module — avoids importing builder_runner)
# ---------------------------------------------------------------------------


class IdentityError(RuntimeError):
    """Raised when worker identity verification encounters an unexpected error."""


def _git(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True
    )


def _git_output(args: list[str], *, cwd: Path) -> str:
    result = _git(args, cwd=cwd)
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "no output"
        raise IdentityError(
            f"git {' '.join(args)} failed in {cwd} "
            f"(exit {result.returncode}): {detail}"
        )
    return result.stdout


def _current_branch(repo_root: Path) -> str:
    """Return the short branch name (e.g. ``feat/foo``), or detached HEAD sha."""
    out = _git_output(["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_root)
    return out.strip()


def _head_sha(repo_root: Path) -> str:
    return _git_output(["rev-parse", "HEAD"], cwd=repo_root).strip()


def _is_ancestor(ancestor: str, descendant: str, *, repo_root: Path) -> bool:
    """Return True if *ancestor* is an ancestor of *descendant*."""
    result = _git(
        ["merge-base", "--is-ancestor", ancestor, descendant], cwd=repo_root
    )
    return result.returncode == 0


def _commits_since(
    base_sha: str, repo_root: Path
) -> list[dict[str, str]]:
    """Return commits between *base_sha* and HEAD as ``[{sha, subject}]``."""
    out = _git_output(
        ["log", f"{base_sha}..HEAD", "--format=%H\t%s", "--no-merges"],
        cwd=repo_root,
    )
    commits: list[dict[str, str]] = []
    for line in out.splitlines():
        if not line.strip():
            continue
        sha, _, subject = line.partition("\t")
        commits.append({"sha": sha, "subject": subject})
    return commits


def _changed_paths(repo_root: Path, base_sha: str) -> list[str]:
    """Return all changed paths (committed, staged, unstaged, untracked) since *base_sha*."""
    commands = (
        ["diff", "--name-only", "--no-renames", "-z", f"{base_sha}..HEAD"],
        ["diff", "--name-only", "--no-renames", "-z"],
        ["diff", "--cached", "--name-only", "--no-renames", "-z"],
        ["ls-files", "--others", "--exclude-standard", "-z"],
    )
    changed: set[str] = set()
    for command in commands:
        out = _git_output(command, cwd=repo_root)
        changed.update(item for item in out.split("\0") if item)
    return sorted(changed)


# ---------------------------------------------------------------------------
# Scope helpers
# ---------------------------------------------------------------------------

_PACKET_MARKER_TEMPLATE = "[{packet_id}]"


def _commit_has_marker(subject: str, packet_id: str) -> bool:
    """Return True if the commit subject contains the deterministic packet marker."""
    marker = _PACKET_MARKER_TEMPLATE.format(packet_id=packet_id)
    return marker in subject


def _scope_violations(
    changed_paths: list[str],
    allowed_paths: list[str] | None,
) -> list[str]:
    """Return changed paths outside the packet's explicit file allowlist."""
    if not allowed_paths:
        return []

    normalized: list[str] = []
    for raw_path in allowed_paths:
        candidate = raw_path.strip().rstrip("/") or "."
        if candidate.startswith("/") or candidate.startswith("\\") or ".." in candidate.split("/"):
            continue
        normalized.append(candidate)

    def allowed(path: str) -> bool:
        return any(
            prefix == "." or path == prefix or path.startswith(f"{prefix}/")
            for prefix in normalized
        )

    return [path for path in changed_paths if not allowed(path)]


def _get_allowed_paths(
    packet_id: str, *, db_path: Path | None = None
) -> list[str] | None:
    """Fetch the allowed_paths list from initiative_packets for this packet.

    Returns None if the packet is not found (caller should escalate).
    """
    conn = bq.connect(db_path)
    try:
        # Packet IDs are unique across initiatives in the branch-lease
        # context; search all initiative_packets rows.
        row = conn.execute(
            "SELECT allowed_paths_json FROM initiative_packets "
            "WHERE packet_id = ? LIMIT 1",
            (packet_id,),
        ).fetchone()
        if row is None:
            return None
        try:
            return json.loads(row["allowed_paths_json"])
        except (json.JSONDecodeError, TypeError):
            return None
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def verify_worker_identity(
    packet_id: str,
    *,
    repo_root: Path,
    db_path: Path | None = None,
) -> list[ScopeFinding]:
    """Verify the worker's git state matches the branch lease.

    Returns an empty list when all checks pass.  Any finding means the
    worker must not proceed — call ``EscalationError`` immediately.
    """
    findings: list[ScopeFinding] = []

    # --- Check 1: lease exists ---
    lease = bq.verify_branch_lease(packet_id, db_path=db_path)
    if lease is None:
        findings.append(
            ScopeFinding(
                "identity_violation",
                "branch_lease",
                f"no branch lease exists for packet {packet_id!r}; "
                "cannot verify worker identity",
            )
        )
        return findings

    leased_branch: str = lease["branch"]
    leased_worktree: str = lease["worktree_path"]
    base_sha: str = lease["base_sha"]

    # --- Check 2: worktree path matches lease ---
    resolved_repo = str(repo_root.resolve())
    resolved_leased = str(Path(leased_worktree).resolve())
    if resolved_repo != resolved_leased:
        findings.append(
            ScopeFinding(
                "identity_violation",
                "worktree_path",
                f"repo_root {repo_root} does not match leased "
                f"worktree_path {leased_worktree}",
            )
        )

    # --- Check 3: current branch matches lease ---
    try:
        current_branch = _current_branch(repo_root)
    except IdentityError as exc:
        findings.append(
            ScopeFinding(
                "identity_violation",
                "branch",
                f"failed to read current branch: {exc}",
            )
        )
        return findings

    if current_branch != leased_branch:
        findings.append(
            ScopeFinding(
                "identity_violation",
                "branch",
                f"current branch {current_branch!r} does not match "
                f"leased branch {leased_branch!r}",
            )
        )

    # --- Check 4: HEAD descends from base_sha ---
    try:
        current_head = _head_sha(repo_root)
    except IdentityError as exc:
        findings.append(
            ScopeFinding(
                "identity_violation",
                "head",
                f"failed to read HEAD: {exc}",
            )
        )
        return findings

    if not _is_ancestor(base_sha, current_head, repo_root=repo_root):
        findings.append(
            ScopeFinding(
                "identity_violation",
                "head",
                f"HEAD {current_head[:12]} is not a descendant of "
                f"lease base_sha {base_sha[:12]}; possible force-push or reset",
            )
        )

    # --- Check 5: no foreign commits ---
    try:
        commits = _commits_since(base_sha, repo_root)
    except IdentityError as exc:
        findings.append(
            ScopeFinding(
                "identity_violation",
                "commits",
                f"failed to read commit history: {exc}",
            )
        )
        return findings

    foreign = [
        c for c in commits if not _commit_has_marker(c["subject"], packet_id)
    ]
    if foreign:
        examples = ", ".join(
            f"{c['sha'][:12]} ({c['subject'][:60]})" for c in foreign[:3]
        )
        findings.append(
            ScopeFinding(
                "identity_violation",
                "commits",
                f"{len(foreign)} foreign commit(s) on branch lack the "
                f"required [{packet_id}] marker: {examples}",
            )
        )

    # --- Check 6: working tree within packet scope ---
    try:
        changed = _changed_paths(repo_root, base_sha)
    except IdentityError as exc:
        findings.append(
            ScopeFinding(
                "identity_violation",
                "working_tree",
                f"failed to read working tree changes: {exc}",
            )
        )
        return findings

    allowed = _get_allowed_paths(packet_id, db_path=db_path)
    violations = _scope_violations(changed, allowed)
    if violations:
        examples = ", ".join(violations[:5])
        suffix = f" and {len(violations) - 5} more" if len(violations) > 5 else ""
        findings.append(
            ScopeFinding(
                "scope_drift",
                "working_tree",
                f"{len(violations)} file(s) outside packet scope: "
                f"{examples}{suffix}",
            )
        )

    return findings


def verify_and_escalate(
    packet_id: str,
    *,
    repo_root: Path,
    db_path: Path | None = None,
    evidence: dict[str, Any] | None = None,
) -> None:
    """Run ``verify_worker_identity`` and raise ``EscalationError`` on any finding.

    Convenience wrapper for call sites that want a single call that either
    passes or raises.
    """
    findings = verify_worker_identity(
        packet_id, repo_root=repo_root, db_path=db_path
    )
    if findings:
        raise EscalationError(
            findings,
            evidence=evidence or {},
            artifact={
                "type": "identity_escalation",
                "action": "stop_escalate_return_control",
                "packet_id": packet_id,
                "findings": [
                    {"category": f.category, "field": f.field, "message": f.message}
                    for f in findings
                ],
                "guidance": (
                    "Worker identity verification failed. The worker's git "
                    "state does not match the branch lease. Resolve the "
                    "conflict and re-submit."
                ),
            },
        )
