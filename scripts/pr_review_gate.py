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


def agent_review_approved(comment: dict[str, Any], head_sha: str) -> bool:
    """Accept only the workflow-owned no-findings verdict for the exact full SHA."""
    if _login(comment) != AGENT_ACTOR or len(head_sha) != 40:
        return False
    body = str(comment.get("body") or "")
    return (
        pr_review.COMMENT_MARKER in body
        and "Review pending" not in body
        and "No actionable findings in this diff." in body
        and f"Reviewed commit `{head_sha}`." in body
    )


def builder_review_approved(
    comment: dict[str, Any], head_sha: str, trusted_actors: set[str]
) -> bool:
    """Accept a Builder review note only from an explicitly trusted actor."""
    if _login(comment) not in trusted_actors or len(head_sha) != 40:
        return False
    body = str(comment.get("body") or "")
    if BUILDER_REVIEW_MARKER not in body:
        return False
    reviewed = re.search(r"^-\s*Reviewed commit:\s*`([0-9a-fA-F]{40})`\s*$", body, re.M)
    verdict = re.search(r"^-\s*Verdict:\s*`?(approve|approved)`?\s*$", body, re.M | re.I)
    return bool(reviewed and reviewed.group(1).lower() == head_sha.lower() and verdict)


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

    if any(agent_review_approved(comment, head_sha) for comment in comments):
        return True, f"GitHub agent review approved exact head {head_sha}."

    trusted = _trusted_builder_actors(repo_owner)
    if any(builder_review_approved(comment, head_sha, trusted) for comment in comments):
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
        comments_url = (
            f"https://api.github.com/repos/{owner}/{name}/issues/{number}/comments?per_page=100"
        )
        pr = _github_json(pr_url, token)
        comments = _github_json(comments_url, token)
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
