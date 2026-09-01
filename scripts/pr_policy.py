#!/usr/bin/env python3
"""Trusted, deterministic merge policy for Kitty pull requests.

Routine changes are governed by deterministic CI. Sensitive changes additionally
require explicit exact-head human approval and trusted independent review.
Product acceptance is required only when native UI source changes.
"""

from __future__ import annotations

import json
import os
import re
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from scripts import pr_review_gate, pr_scope

RISK_APPROVED_LABEL = "risk/approved"
LARGE_CHANGE_LINES = 1500
LARGE_CHANGE_FILES = 25

# Sensitive and native-UI scope come from the one canonical classifier so the
# gate that blocks and the CI that runs can never disagree about what a PR is.
RISK_PATTERNS = pr_scope.RISK_PATTERNS
USER_FACING_PATTERNS = pr_scope.USER_FACING_PATTERNS

ACCEPTANCE_CHECKS = (
    "Every visible primary control either completes its task or is disabled with one clear recovery action.",
    "I tested required services both available and unavailable/misconfigured.",
    "There is no horizontal page overflow, clipped dialog, obscured action, or off-screen primary navigation at the mobile viewport.",
    "Errors explain what failed and what the user can do next; no raw server error is the primary message.",
    "Normal user workflows do not require packet IDs, KTF phases, ports, env vars, YAML, MCP, LiteLLM, terminal commands, or Mac file paths.",
    "A reviewer who did not implement the change completed the task in the running app.",
)

REQUIRED_ACCEPTANCE_FIELDS = (
    "User goal",
    "Running-app steps and visible result",
    "Evidence",
    "Independent task-completion reviewer",
)


def _section(body: str, heading: str, *, until: str | None = None) -> str:
    marker = f"## {heading}"
    if marker not in body:
        return ""
    text = body.split(marker, 1)[1]
    if until and until in text:
        text = text.split(until, 1)[0]
    elif "\n## " in text:
        text = text.split("\n## ", 1)[0]
    return text


def _has_content(value: str) -> bool:
    value = value.strip()
    return bool(value and "<!--" not in value and value.lower() not in {"n/a", "na", "none yet"})


def _field_value(section: str, field: str) -> str:
    match = re.search(rf"^-\s*{re.escape(field)}:\s*(.*)$", section, re.M)
    return match.group(1).strip() if match else ""


def _is_checked(section: str, text: str) -> bool:
    return re.search(rf"^-\s*\[[xX]\]\s*{re.escape(text)}\s*$", section, re.M) is not None


def _exact_head_approval(body: str, field: str, head_sha: str) -> str | None:
    if len(head_sha) != 40 or not re.fullmatch(r"[0-9a-fA-F]{40}", head_sha):
        return None
    pattern = re.compile(
        rf"^{re.escape(field)}:\s*APPROVE\s+([0-9a-fA-F]{{40}})\s+[—-]\s+(.+)$",
        re.M,
    )
    for match in pattern.finditer(body or ""):
        if match.group(1).lower() == head_sha.lower() and _has_content(match.group(2)):
            return match.group(2).strip()
    return None


def _risky_files(changed_files: list[str]) -> list[str]:
    return pr_scope.risky_files(changed_files)


def _is_user_facing(changed_files: list[str]) -> bool:
    return pr_scope.is_user_facing(changed_files)


def policy_warnings(pr: dict[str, Any]) -> list[str]:
    changed_lines = int(pr.get("additions") or 0) + int(pr.get("deletions") or 0)
    changed_count = int(pr.get("changed_files") or 0)
    if changed_lines > LARGE_CHANGE_LINES or changed_count > LARGE_CHANGE_FILES:
        return [
            f"large PR ({changed_lines} changed lines / {changed_count} files): consider splitting if that improves reviewability"
        ]
    return []


def evaluate_policy(
    pr: dict[str, Any],
    changed_files: list[str],
    *,
    independent_review_approved: bool = False,
    event_action: str | None = None,
) -> list[str]:
    del event_action  # live PR state, not event ordering, is authoritative
    body = str(pr.get("body") or "")
    author = str((pr.get("user") or {}).get("login") or "")
    labels = {
        str(label.get("name"))
        for label in (pr.get("labels") or [])
        if isinstance(label, dict) and label.get("name")
    }
    head_sha = str((pr.get("head") or {}).get("sha") or "")
    violations: list[str] = []

    if author != "dependabot[bot]" and _is_user_facing(changed_files):
        acceptance = _section(body, "Product acceptance (required only when `gateway/kitty-chat/src/` or `public/` changes)")
        if not acceptance:
            violations.append("user-facing PR requires completed product acceptance")
        else:
            missing_checks = [text for text in ACCEPTANCE_CHECKS if not _is_checked(acceptance, text)]
            missing_fields = [
                field
                for field in REQUIRED_ACCEPTANCE_FIELDS
                if not _has_content(_field_value(acceptance, field))
            ]
            if missing_checks or missing_fields:
                detail: list[str] = []
                if missing_checks:
                    detail.append(f"{len(missing_checks)} acceptance checkbox(es) unchecked")
                if missing_fields:
                    detail.append("missing fields: " + ", ".join(missing_fields))
                violations.append("user-facing PR has incomplete product acceptance: " + "; ".join(detail))

    risky = _risky_files(changed_files)
    if risky:
        if RISK_APPROVED_LABEL not in labels:
            violations.append(f"risky scope requires label `{RISK_APPROVED_LABEL}`")
        if _exact_head_approval(body, "Risk approval", head_sha) is None:
            violations.append(
                "risky scope requires exact-head risk approval: "
                "`Risk approval: APPROVE <full-head-SHA> — <reason>`"
            )
        if not independent_review_approved:
            violations.append(
                "risky scope requires trusted independent review approval for the exact current head"
            )

    return violations


def _github_json(url: str, token: str) -> Any:
    req = Request(url)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def _changed_files(owner: str, repo: str, pr_number: int, token: str) -> list[str]:
    return pr_scope.pull_request_files(owner, repo, pr_number, token, fetch=_github_json)


def _pr_number_from_event(event: dict[str, Any]) -> int:
    """Resolve the PR this event is about.

    A merge_group event has no ``pull_request`` payload — it carries a
    temporary queue merge commit instead. GitHub encodes the originating PR
    number in ``merge_group.head_ref`` (``refs/heads/gh-readonly-queue/<base>/
    pr-<number>-<sha>``); this is the standard, documented way to recover it.
    Policy is then evaluated against that PR's own head SHA (fetched fresh
    below), not the queue's synthetic commit — "exact-head" approval is about
    the PR author's content, which the queue merge does not change.
    """
    pull_request = event.get("pull_request")
    if isinstance(pull_request, dict):
        return int(pull_request["number"])
    merge_group = event.get("merge_group")
    if isinstance(merge_group, dict):
        head_ref = str(merge_group.get("head_ref") or "")
        match = re.search(r"/pr-(\d+)-", head_ref)
        if not match:
            raise RuntimeError(f"could not recover PR number from merge_group head_ref {head_ref!r}")
        return int(match.group(1))
    raise RuntimeError("event has neither pull_request nor merge_group")


def main() -> None:
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path:
        print("GITHUB_EVENT_PATH is required", file=sys.stderr)
        raise SystemExit(1)
    try:
        with open(event_path, encoding="utf-8") as event_file:
            event = json.load(event_file)
        repo = event["repository"]
        owner = str(repo["owner"]["login"])
        name = str(repo["name"])
        number = _pr_number_from_event(event)
        token = os.environ.get("GITHUB_TOKEN", "")
        pr_url = f"https://api.github.com/repos/{owner}/{name}/pulls/{number}"
        pr = _github_json(pr_url, token)
        if not isinstance(pr, dict):
            raise RuntimeError("GitHub current-PR response was not an object")
        files = _changed_files(owner, name, number, token)

        review_approved = True
        if _risky_files(files):
            comments_url = f"https://api.github.com/repos/{owner}/{name}/issues/{number}/comments?per_page=100"
            comments = _github_json(comments_url, token)
            if not isinstance(comments, list):
                raise RuntimeError("GitHub PR comments response was not a list")
            review_approved, review_reason = pr_review_gate.evaluate_review_gate(
                pr, comments, repo_owner=owner
            )
            print(f"Independent review: {review_reason}")
    except (KeyError, ValueError, TypeError, OSError, HTTPError, URLError, TimeoutError, json.JSONDecodeError, RuntimeError) as exc:
        print(f"PR policy could not inspect current PR state: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    for warning in policy_warnings(pr):
        print(f"::warning title=PR policy advisory::{warning}")

    violations = evaluate_policy(
        pr,
        files,
        independent_review_approved=review_approved,
        event_action=str(event.get("action") or ""),
    )
    if violations:
        print("PR policy blocked this head:", file=sys.stderr)
        for violation in violations:
            print(f"- {violation}", file=sys.stderr)
        raise SystemExit(1)
    print("PR policy passed.")


if __name__ == "__main__":
    main()
