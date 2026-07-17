"""Fail-closed worker identity verification for KittyBuilder branch leases.

Post-worker verification binds durable lease ownership to the actual Git
branch, worktree, base ancestry, commit markers, and packet scope before
validation or review can accept an implementation.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from gateway import builder_queue as bq
from gateway.builder_scope import (
    EscalationError,
    ScopeFinding,
    find_changed_path_violations,
    normalize_allowed_paths,
)


class IdentityError(RuntimeError):
    """Raised when identity verification cannot inspect authoritative state."""


def _git(
    args: list[str], *, cwd: Path
) -> subprocess.CompletedProcess[str]:
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
    return _git_output(
        ["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_root
    ).strip()


def _head_sha(repo_root: Path) -> str:
    return _git_output(["rev-parse", "HEAD"], cwd=repo_root).strip()


def _is_ancestor(ancestor: str, descendant: str, *, repo_root: Path) -> bool:
    result = _git(
        ["merge-base", "--is-ancestor", ancestor, descendant], cwd=repo_root
    )
    if result.returncode == 0:
        return True
    if result.returncode == 1:
        return False
    detail = result.stderr.strip() or result.stdout.strip() or "no output"
    raise IdentityError(
        f"git merge-base --is-ancestor failed in {repo_root} "
        f"(exit {result.returncode}): {detail}"
    )


def _commits_since(base_sha: str, repo_root: Path) -> list[dict[str, str]]:
    output = _git_output(
        ["log", f"{base_sha}..HEAD", "--format=%H\t%s"],
        cwd=repo_root,
    )
    commits: list[dict[str, str]] = []
    for line in output.splitlines():
        if not line.strip():
            continue
        sha, separator, subject = line.partition("\t")
        if not separator:
            raise IdentityError(f"malformed git log line for commit {line!r}")
        commits.append({"sha": sha, "subject": subject})
    return commits


def _changed_paths(repo_root: Path, base_sha: str) -> list[str]:
    commands = (
        ["diff", "--name-only", "--no-renames", "-z", f"{base_sha}..HEAD"],
        ["diff", "--name-only", "--no-renames", "-z"],
        ["diff", "--cached", "--name-only", "--no-renames", "-z"],
        ["ls-files", "--others", "--exclude-standard", "-z"],
    )
    changed: set[str] = set()
    for command in commands:
        output = _git_output(command, cwd=repo_root)
        changed.update(path for path in output.split("\0") if path)
    return sorted(changed)


def _get_allowed_paths(
    packet_id: str, *, db_path: Path | None = None
) -> list[str]:
    """Return one unambiguous, valid durable packet allowlist."""
    conn = bq.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT allowed_paths_json FROM initiative_packets "
            "WHERE packet_id = ? LIMIT 2",
            (packet_id,),
        ).fetchall()
    finally:
        conn.close()
    if not rows:
        raise IdentityError(f"packet {packet_id!r} has no allowlist row")
    if len(rows) != 1:
        raise IdentityError(
            f"packet_id {packet_id!r} is not globally unique; lease identity is ambiguous"
        )
    try:
        parsed = json.loads(rows[0]["allowed_paths_json"])
        return normalize_allowed_paths(parsed)
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise IdentityError(
            f"packet {packet_id!r} has invalid allowed_paths_json: {exc}"
        ) from exc


def _finding(field: str, message: str) -> ScopeFinding:
    return ScopeFinding("identity_violation", field, message)


def verify_worker_identity(
    packet_id: str,
    *,
    repo_root: Path,
    db_path: Path | None = None,
    expected_lease_id: int | None = None,
    expected_worker_id: str | None = None,
    expected_branch: str | None = None,
    expected_worktree_path: str | None = None,
    expected_base_sha: str | None = None,
) -> list[ScopeFinding]:
    """Return all detected lease/Git/scope identity violations."""
    findings: list[ScopeFinding] = []
    lease = bq.verify_branch_lease(packet_id, db_path=db_path)
    if lease is None:
        return [
            _finding(
                "branch_lease",
                f"no branch lease exists for packet {packet_id!r}",
            )
        ]

    expected_fields: tuple[tuple[str, Any, Any], ...] = (
        ("lease_id", expected_lease_id, lease["lease_id"]),
        ("worker_id", expected_worker_id, lease["worker_id"]),
        ("branch", expected_branch, lease["branch"]),
        ("base_sha", expected_base_sha, lease["base_sha"]),
    )
    for field, expected, actual in expected_fields:
        if expected is not None and actual != expected:
            findings.append(
                _finding(
                    field,
                    f"leased {field} {actual!r} does not match expected {expected!r}",
                )
            )

    resolved_repo = str(repo_root.expanduser().resolve())
    resolved_lease = str(Path(lease["worktree_path"]).expanduser().resolve())
    if resolved_repo != resolved_lease:
        findings.append(
            _finding(
                "worktree_path",
                f"repo_root {resolved_repo!r} does not match leased "
                f"worktree_path {resolved_lease!r}",
            )
        )
    if expected_worktree_path is not None:
        resolved_expected = str(
            Path(expected_worktree_path).expanduser().resolve()
        )
        if resolved_lease != resolved_expected:
            findings.append(
                _finding(
                    "worktree_path",
                    f"leased worktree {resolved_lease!r} does not match "
                    f"expected {resolved_expected!r}",
                )
            )

    try:
        current_branch = _current_branch(repo_root)
        current_head = _head_sha(repo_root)
    except IdentityError as exc:
        findings.append(_finding("git_state", str(exc)))
        return findings

    if current_branch != lease["branch"]:
        findings.append(
            _finding(
                "branch",
                f"current branch {current_branch!r} does not match "
                f"leased branch {lease['branch']!r}",
            )
        )

    ancestry_valid = False
    try:
        ancestry_valid = _is_ancestor(
            lease["base_sha"], current_head, repo_root=repo_root
        )
    except IdentityError as exc:
        findings.append(_finding("head", str(exc)))
    else:
        if not ancestry_valid:
            findings.append(
                _finding(
                    "head",
                    f"HEAD {current_head[:12]} is not a descendant of "
                    f"lease base_sha {lease['base_sha'][:12]}",
                )
            )

    if ancestry_valid:
        try:
            commits = _commits_since(lease["base_sha"], repo_root)
        except IdentityError as exc:
            findings.append(_finding("commits", str(exc)))
        else:
            marker = f"[{packet_id}]"
            foreign = [commit for commit in commits if marker not in commit["subject"]]
            if foreign:
                examples = ", ".join(
                    f"{commit['sha'][:12]} ({commit['subject'][:60]})"
                    for commit in foreign[:3]
                )
                findings.append(
                    _finding(
                        "commits",
                        f"{len(foreign)} commit(s) lack required marker "
                        f"{marker}: {examples}",
                    )
                )

        try:
            changed = _changed_paths(repo_root, lease["base_sha"])
            allowed = _get_allowed_paths(packet_id, db_path=db_path)
            violations = find_changed_path_violations(changed, allowed)
        except (IdentityError, ValueError) as exc:
            findings.append(_finding("allowed_paths", str(exc)))
        else:
            if violations:
                examples = ", ".join(violations[:5])
                suffix = (
                    f" and {len(violations) - 5} more"
                    if len(violations) > 5
                    else ""
                )
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
    **expected_identity: Any,
) -> None:
    """Raise a structured escalation when identity verification fails."""
    findings = verify_worker_identity(
        packet_id,
        repo_root=repo_root,
        db_path=db_path,
        **expected_identity,
    )
    if not findings:
        return
    raise EscalationError(
        findings,
        evidence=evidence or {},
        artifact={
            "type": "identity_escalation",
            "action": "stop_escalate_return_control",
            "packet_id": packet_id,
            "findings": [
                {
                    "category": finding.category,
                    "field": finding.field,
                    "message": finding.message,
                }
                for finding in findings
            ],
        },
    )
