#!/usr/bin/env python3
"""Deterministic exact-head review-evidence gate for pull requests."""

from __future__ import annotations

import json
import os
import re
import sys
from typing import Any

from scripts import pr_review

BUILDER_REVIEW_MARKER = "<!-- kitty-builder-independent-review -->"
AGENT_ACTOR = "github-actions[bot]"


def _login(comment: dict[str, Any]) -> str:
    user = comment.get("user")
    return str(user.get("login") or "") if isinstance(user, dict) else ""


def _agent_exact_head_body(comment: dict[str, Any], head_sha: str) -> str | None:
    if _login(comment) != AGENT_ACTOR or len(head_sha) != 40:
        return None
    body = str(comment.get("body") or "")
    if (
        pr_review.COMMENT_MARKER not in body
        or "Review pending" in body
        or f"Reviewed commit `{head_sha}`." not in body
    ):
        return None
    return body


def _agent_body_has_rubric_fields(body: str) -> bool:
    """True when the body carries the rubric's explicit finding fields.

    This is the only signal that may affect the decision. A clean verdict is allowed
    to mention file paths while explaining why an observation was *not* promoted to a
    finding, so a path mention must never veto a sentinel.

    Delegates to pr_review, which owns the definition, so the workflow that produces
    a verdict and the gate that reads it cannot drift apart.
    """
    return pr_review.is_reportable_finding(body)


def agent_review_confirmed_finding(comment: dict[str, Any], head_sha: str) -> bool:
    """A marker-bound exact-head review carrying the rubric's explicit finding fields.

    Used ONLY to choose the failure message; it never decides whether to block. A
    path mention is deliberately NOT sufficient: stalled process narration routinely
    names a file ("I need to inspect scripts/pr_review_gate.py before deciding"), and
    treating that as a finding reproduces the misdiagnosis this change exists to
    remove.
    """
    body = _agent_exact_head_body(comment, head_sha)
    return bool(body and _agent_body_has_rubric_fields(body))


def _agent_body_has_no_findings(body: str) -> bool:
    """Accept a no-findings sentinel unless the same evidence contains a real finding block.

    Review models occasionally explain why an observation was *not* promoted to a
    finding before emitting the required sentinel. That prose is harmless. A
    contradictory response that also contains the rubric's structured finding
    fields remains blocking, so this does not turn the sentinel into an escape hatch.
    """
    if _agent_body_has_rubric_fields(body):
        return False
    if "No actionable findings in this diff." in body:
        return True
    return bool(re.search(rf"(?m)^\s*{re.escape(pr_review.NO_FINDINGS)}\s*$", body))


def agent_review_approved(comment: dict[str, Any], head_sha: str) -> bool:
    """Accept only workflow-owned no-findings evidence for the exact full SHA."""
    body = _agent_exact_head_body(comment, head_sha)
    return bool(body and _agent_body_has_no_findings(body))


def agent_review_blocked(comment: dict[str, Any], head_sha: str) -> bool:
    """Treat any exact-head workflow verdict other than no-findings as blocking."""
    body = _agent_exact_head_body(comment, head_sha)
    return bool(body and not _agent_body_has_no_findings(body))


def agent_review_unusable(comment: dict[str, Any], head_sha: str) -> bool:
    """A marker-bound exact-head review that is neither a verdict nor a finding.

    A stalled or truncated review can post the marker and the `Reviewed commit` line
    without the no-findings sentinel and without any structured finding. That is not
    evidence of a defect, and reporting it as one sends an operator looking for a
    finding that was never produced. It still fails the gate -- an unusable review is
    not an approval -- but it is reported as what it is.
    """
    return agent_review_blocked(comment, head_sha) and not agent_review_confirmed_finding(
        comment, head_sha
    )


def builder_review_verdict(
    comment: dict[str, Any], head_sha: str, trusted_actors: set[str]
) -> str | None:
    """Return a trusted Builder verdict only when it is bound to the exact full SHA."""
    if _login(comment) not in trusted_actors or len(head_sha) != 40:
        return None
    body = str(comment.get("body") or "")
    if BUILDER_REVIEW_MARKER not in body:
        return None
    reviewed = re.search(r"^-\s*Reviewed commit:\s*`([0-9a-fA-F]{40})`\s*$", body, re.M)
    verdict = re.search(
        r"^-\s*Verdict:\s*`?(approve|approved|request_changes|reject)`?\s*$",
        body,
        re.M | re.I,
    )
    if not reviewed or reviewed.group(1).lower() != head_sha.lower() or not verdict:
        return None
    return verdict.group(1).lower()


def builder_review_approved(
    comment: dict[str, Any], head_sha: str, trusted_actors: set[str]
) -> bool:
    return builder_review_verdict(comment, head_sha, trusted_actors) in {"approve", "approved"}


def _trusted_builder_actors(repo_owner: str) -> set[str]:
    configured = {
        actor.strip()
        for actor in os.environ.get("PR_REVIEW_TRUSTED_ACTORS", "").split(",")
        if actor.strip()
    }
    return {repo_owner, *configured}


def evaluate_review_gate(
    pr: dict[str, Any], comments: list[dict[str, Any]], *, repo_owner: str
) -> tuple[bool, str]:
    head_sha = str((pr.get("head") or {}).get("sha") or "")
    if len(head_sha) != 40 or not re.fullmatch(r"[0-9a-fA-F]{40}", head_sha):
        return False, "Current PR head is missing a full 40-character SHA."

    labels = {
        str(label.get("name"))
        for label in (pr.get("labels") or [])
        if isinstance(label, dict) and label.get("name")
    }
    override = pr_review.parse_exact_head_override(
        str(pr.get("body") or ""), labels, head_sha
    )
    if override:
        return True, f"Exact-head review override approved for {head_sha}: {override}"

    trusted = _trusted_builder_actors(repo_owner)
    blocking = [comment for comment in comments if agent_review_blocked(comment, head_sha)]
    if blocking:
        # Both outcomes block. The distinction is diagnostic: a stalled review that
        # emitted nothing usable must not be reported as a defect that was found.
        if any(agent_review_confirmed_finding(comment, head_sha) for comment in blocking):
            return False, (
                f"Blocking GitHub agent review finding exists for exact head {head_sha}."
            )
        return False, (
            f"GitHub agent review for exact head {head_sha} is not a parseable verdict "
            "and no finding could be confirmed: the bound comment carries neither the "
            "no-findings sentinel nor the rubric's Failure Mode / Corrective Action "
            "fields, so any claim in it is unverified."
        )
    # Recency: comments arrive oldest-first, so the LAST same-head Builder
    # verdict is the reviewer's current position. A reject-then-approve must
    # not stay blocked forever (and approve-then-reject must stay blocked).
    latest_builder_verdict: str | None = None
    for comment in comments:
        verdict = builder_review_verdict(comment, head_sha, trusted)
        if verdict is not None:
            latest_builder_verdict = verdict
    if latest_builder_verdict in {"request_changes", "reject"}:
        return False, f"Blocking Builder review verdict exists for exact head {head_sha}."

    if any(agent_review_approved(comment, head_sha) for comment in comments):
        return True, f"GitHub agent review approved exact head {head_sha}."

    if latest_builder_verdict in {"approve", "approved"}:
        return True, f"Builder independent review approved exact head {head_sha}."

    return False, f"No trusted exact-head review approval exists for {head_sha}."


def _github_json(url: str, token: str) -> Any:
    return pr_review.github_json(url, token)


def main() -> None:
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    token = os.environ.get("GITHUB_TOKEN") or ""
    if not event_path or not token:
        print("GITHUB_EVENT_PATH and GITHUB_TOKEN are required.", file=sys.stderr)
        raise SystemExit(1)

    try:
        with open(event_path, encoding="utf-8") as event_file:
            event = json.load(event_file)
        event_pr = event["pull_request"]
        repo = event["repository"]
        owner = str(repo["owner"]["login"])
        name = str(repo["name"])
        number = int(event_pr["number"])
        pr_url = f"https://api.github.com/repos/{owner}/{name}/pulls/{number}"
        pr = _github_json(pr_url, token)
        # Paginated: issue comments are oldest-first, so a single page hides the
        # newest head's evidence once a PR passes 100 comments, and the gate would
        # report no trusted approval for a head that actually has one.
        comments = pr_review.issue_comments(owner, name, number, token, fetch=_github_json)
        if not isinstance(pr, dict) or not isinstance(comments, list):
            raise ValueError("GitHub returned invalid PR/review-evidence data")
    except (KeyError, ValueError, TypeError, OSError, json.JSONDecodeError) as exc:
        print(f"Review gate could not inspect live PR state: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    ok, reason = evaluate_review_gate(pr, comments, repo_owner=owner)
    print(reason)
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
