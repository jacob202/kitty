#!/usr/bin/env python3
"""Fail-closed exact-head PR review gate.

The workflow owns one durable PR comment. Every PR-head change replaces any
older approval-looking comment with a pending marker before reviewing the full
diff. A missing reviewer verdict or any actionable finding fails the workflow;
only an exact no-findings verdict exits successfully.
"""

from __future__ import annotations

import json
import os
import re
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_REVIEW_MODEL = "minimax/minimax-m3"
REVIEW_MODEL = os.environ.get("PR_REVIEW_MODEL", DEFAULT_REVIEW_MODEL)
COMMENT_MARKER = "<!-- kitty-agent-pr-review -->"
NO_FINDINGS = "NO_ACTIONABLE_FINDINGS"
REVIEW_PENDING = "__REVIEW_PENDING__"
REVIEW_OVERRIDE_LABEL = "review/override-approved"
MAX_REVIEW_CHARS = int(os.environ.get("PR_REVIEW_CHUNK_CHARS", "60000"))
MAX_REVIEW_CHUNKS = int(os.environ.get("PR_REVIEW_MAX_CHUNKS", "12"))

SYSTEM_PROMPT = """You are a strict independent code reviewer. Review only the supplied PR diff chunk.

A reportable finding must be supported by the diff and must identify all four:
- name the changed file and identify the changed behavior/hunk
- the exact input, state, sequence, or concurrency condition that reaches the defect
- the specific failure mode: the exact incorrect observable outcome (wrong state, false success, data loss, security boundary break, crash, or user-visible regression)
- the smallest corrective action

Do not report speculative or generic review noise. In particular, do not report a finding
whose reasoning is merely that something *may*, *might*, *could*, or *potentially* fail,
or whose action is only to "ensure", "consider", "verify", "monitor", add comments,
add unspecified tests, or clarify documentation. Missing tests are not themselves a defect.
Configuration is not a defect unless the supplied diff creates a concrete broken configuration.
If you cannot name the exact input/state and exact wrong outcome, omit the finding.

Prioritize correctness, authorization, false-success states, retry/recovery races, stale evidence,
data loss, resource leaks with a concrete trigger, and user-visible failure/recovery behavior.
Do not repeat the PR summary. Before answering, remove any finding that is not directly grounded
in changed code shown in this chunk.

Use concise bullets. If there are no actionable findings, respond with exactly:
NO_ACTIONABLE_FINDINGS
"""


def parse_exact_head_override(body: str, labels: set[str], head_sha: str) -> str | None:
    """Return the override reason only for an explicitly labeled exact full SHA."""
    if REVIEW_OVERRIDE_LABEL not in labels or len(head_sha) != 40:
        return None
    pattern = re.compile(
        r"^Review override:\s*APPROVE\s+([0-9a-fA-F]{40})\s+[—-]\s+(.+)$",
        re.M,
    )
    for match in pattern.finditer(body or ""):
        if match.group(1).lower() == head_sha.lower() and match.group(2).strip():
            return match.group(2).strip()
    return None


def get_exact_head_override(head_sha: str) -> str | None:
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path:
        return None
    try:
        with open(event_path, encoding="utf-8") as event_file:
            event = json.load(event_file)
    except (OSError, json.JSONDecodeError):
        return None
    pr = event.get("pull_request") or {}
    labels = {
        str(label.get("name"))
        for label in (pr.get("labels") or [])
        if isinstance(label, dict) and label.get("name")
    }
    return parse_exact_head_override(str(pr.get("body") or ""), labels, head_sha)


def get_pr_diff() -> tuple[str, int, str, str, str]:
    """Return (diff, PR number, owner, repo, head SHA) from the event payload."""
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path:
        print("No GITHUB_EVENT_PATH — not running in GitHub Actions?", file=sys.stderr)
        raise SystemExit(1)

    with open(event_path, encoding="utf-8") as event_file:
        event = json.load(event_file)

    pr = event.get("pull_request")
    if not pr:
        print("No pull_request in event — not a PR event.", file=sys.stderr)
        raise SystemExit(1)

    repo = event.get("repository", {})
    owner = repo.get("owner", {}).get("login", "")
    name = repo.get("name", "")
    pr_number = int(pr.get("number", 0))
    head_sha = str(pr.get("head", {}).get("sha", ""))
    api_url = str(pr.get("url") or "")
    if not api_url and owner and name and pr_number:
        api_url = f"https://api.github.com/repos/{owner}/{name}/pulls/{pr_number}"
    if not api_url or not head_sha:
        print("PR payload is missing API URL or head SHA.", file=sys.stderr)
        raise SystemExit(1)

    token = os.environ.get("GITHUB_TOKEN") or ""
    req = Request(api_url)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github.v3.diff")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    try:
        with urlopen(req, timeout=30) as resp:
            diff = resp.read().decode("utf-8")
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        print(f"Could not fetch PR diff: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    return diff, pr_number, owner, name, head_sha


def _review_chunk(chunk: str) -> str | None:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("OPENROUTER_API_KEY not set — current-head review cannot run.", file=sys.stderr)
        return None

    body = json.dumps(
        {
            "model": REVIEW_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Review this PR diff chunk:\n\n```diff\n{chunk}\n```",
                },
            ],
            "temperature": 0.1,
            "max_tokens": 3000,
        }
    ).encode()

    req = Request(OPENROUTER_URL, data=body, method="POST")
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("Content-Type", "application/json")

    try:
        with urlopen(req, timeout=90) as resp:
            result = json.loads(resp.read())
    except HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:300]
        print(f"OpenRouter API error: {exc.status} — {detail}", file=sys.stderr)
        return None
    except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        print(f"Reviewer infrastructure error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return None

    choices = result.get("choices", [])
    if not choices:
        print("No choices in OpenRouter response.", file=sys.stderr)
        return None

    content = choices[0].get("message", {}).get("content")
    return str(content).strip() if content else None


def review_diff(diff: str) -> str | None:
    """Review every byte of the diff in bounded chunks; never silently truncate."""
    chunks = [
        diff[start : start + MAX_REVIEW_CHARS]
        for start in range(0, len(diff), MAX_REVIEW_CHARS)
    ]
    if not chunks:
        return NO_FINDINGS
    if len(chunks) > MAX_REVIEW_CHUNKS:
        print(
            f"PR diff needs {len(chunks)} review chunks; limit is {MAX_REVIEW_CHUNKS}. "
            "Split the PR or explicitly raise the reviewed limit.",
            file=sys.stderr,
        )
        return None

    findings: list[str] = []
    for index, chunk in enumerate(chunks, start=1):
        print(f"Reviewing diff chunk {index}/{len(chunks)} ({len(chunk)} chars).")
        verdict = _review_chunk(chunk)
        if not verdict:
            return None
        if verdict.strip() != NO_FINDINGS:
            findings.append(verdict.strip())

    return NO_FINDINGS if not findings else "\n\n".join(findings)


def render_review_body(review: str, head_sha: str) -> str:
    """Build the one comment body owned by this workflow."""
    if review.strip() == REVIEW_PENDING:
        target = f"`{head_sha[:12]}`" if head_sha else "the current PR head"
        return (
            f"{COMMENT_MARKER}\n## Agent PR Review\n\n"
            f"Review pending for commit {target}. Previous review evidence is stale "
            "until this current-head review completes."
        )
    if review.strip() == NO_FINDINGS:
        review = "No actionable findings in this diff."
    reviewed = f"Reviewed commit `{head_sha[:12]}`." if head_sha else "Reviewed current PR head."
    return f"{COMMENT_MARKER}\n## Agent PR Review\n\n{review}\n\n_{reviewed}_"


def find_existing_review_comment(comments: list[dict[str, Any]]) -> int | None:
    """Return the existing workflow-owned issue comment id, if present."""
    for comment in comments:
        body = comment.get("body")
        comment_id = comment.get("id")
        if isinstance(body, str) and COMMENT_MARKER in body and isinstance(comment_id, int):
            return comment_id
    return None


def github_json(
    url: str,
    token: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
) -> Any:
    data = json.dumps(payload).encode() if payload is not None else None
    req = Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    with urlopen(req, timeout=30) as resp:
        raw = resp.read()
    return json.loads(raw) if raw else None


def upsert_review(review: str, pr_number: int, owner: str, repo: str, head_sha: str) -> None:
    """Create the review comment once, then replace it on later pushes."""
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("No GITHUB_TOKEN — cannot post review.", file=sys.stderr)
        raise SystemExit(1)

    comments_url = (
        f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/comments?per_page=100"
    )
    body = render_review_body(review, head_sha)

    try:
        comments = github_json(comments_url, token)
        existing_id = find_existing_review_comment(comments if isinstance(comments, list) else [])
        if existing_id is None:
            post_url = f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/comments"
            github_json(post_url, token, method="POST", payload={"body": body})
            print("PR review posted.")
        else:
            patch_url = f"https://api.github.com/repos/{owner}/{repo}/issues/comments/{existing_id}"
            github_json(patch_url, token, method="PATCH", payload={"body": body})
            print(f"PR review comment {existing_id} updated.")
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        print(f"GitHub API error updating review: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


def main() -> None:
    diff, pr_number, owner, repo, head_sha = get_pr_diff()

    # Invalidate older approval-looking evidence before any external model call.
    upsert_review(REVIEW_PENDING, pr_number, owner, repo, head_sha)

    override_reason = get_exact_head_override(head_sha)
    if override_reason:
        upsert_review(
            "Exact-head review override approved for "
            f"`{head_sha}`.\n\nReason: {override_reason}",
            pr_number,
            owner,
            repo,
            head_sha,
        )
        return

    review = review_diff(diff)
    if not review:
        print("Current-head agent review did not produce a verdict.", file=sys.stderr)
        raise SystemExit(1)

    upsert_review(review, pr_number, owner, repo, head_sha)
    if review.strip() != NO_FINDINGS:
        print("Actionable review findings block this exact PR head.", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
