#!/usr/bin/env python3
"""PR agent review — review a PR diff and maintain one durable review comment.

Requires GITHUB_TOKEN (provided by Actions) and OPENROUTER_API_KEY (repo secret).
Skips silently if OPENROUTER_API_KEY is not set.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
REVIEW_MODEL = os.environ.get("PR_REVIEW_MODEL", "openai/gpt-4o-mini")
COMMENT_MARKER = "<!-- kitty-agent-pr-review -->"
NO_FINDINGS = "NO_ACTIONABLE_FINDINGS"
REVIEW_PENDING = "__REVIEW_PENDING__"

SYSTEM_PROMPT = """You are a strict code reviewer. Review only the supplied PR diff.

Report a finding only when the diff supports a concrete defect. Every finding must:
- name the changed file
- identify the changed behavior or hunk
- explain the specific failure mode
- state the smallest corrective action

Do not write generic advice such as "ensure", "consider", "monitor", "could expose",
or "add more tests" without naming the exact missing case. Do not repeat the PR
summary. Do not speculate about code outside the diff unless the changed line directly
breaks a visible contract.

Use concise bullets. If there are no actionable findings, respond with exactly:
NO_ACTIONABLE_FINDINGS

Never suggest adding comments."""


def get_pr_diff() -> tuple[str, int, str, str, str]:
    """Return (diff, PR number, owner, repo, head SHA) from the event payload."""
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path:
        print("No GITHUB_EVENT_PATH — not running in GitHub Actions?", file=sys.stderr)
        sys.exit(0)

    with open(event_path, encoding="utf-8") as event_file:
        event = json.load(event_file)

    pr = event.get("pull_request")
    if not pr:
        print("No pull_request in event — not a PR event.", file=sys.stderr)
        sys.exit(0)

    repo = event.get("repository", {})
    owner = repo.get("owner", {}).get("login", "")
    name = repo.get("name", "")
    pr_number = int(pr.get("number", 0))
    head_sha = str(pr.get("head", {}).get("sha", ""))
    api_url = str(pr.get("url") or "")
    if not api_url and owner and name and pr_number:
        api_url = f"https://api.github.com/repos/{owner}/{name}/pulls/{pr_number}"
    if not api_url:
        print("No API URL in PR payload.", file=sys.stderr)
        sys.exit(1)

    # GitHub's web .diff URL returns 404 for private repositories even when an
    # Actions token is sent. Ask the authenticated REST PR endpoint for the diff
    # representation instead.
    token = os.environ.get("GITHUB_TOKEN") or ""
    req = Request(api_url)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github.v3.diff")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    with urlopen(req, timeout=30) as resp:
        diff = resp.read().decode("utf-8")

    return diff, pr_number, owner, name, head_sha


def review_diff(diff: str) -> str | None:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("OPENROUTER_API_KEY not set — skipping LLM review.", file=sys.stderr)
        return None

    body = json.dumps(
        {
            "model": REVIEW_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Review this PR diff:\n\n```diff\n{diff[:30000]}\n```",
                },
            ],
            "temperature": 0.1,
            "max_tokens": 2000,
        }
    ).encode()

    req = Request(OPENROUTER_URL, data=body, method="POST")
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("Content-Type", "application/json")

    try:
        with urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read())
    except HTTPError as exc:
        print(
            f"OpenRouter API error: {exc.status} — {exc.read().decode()[:200]}",
            file=sys.stderr,
        )
        return None

    choices = result.get("choices", [])
    if not choices:
        print("No choices in OpenRouter response.", file=sys.stderr)
        return None

    content = choices[0].get("message", {}).get("content")
    return str(content).strip() if content else None


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
    except HTTPError as exc:
        print(
            f"GitHub API error updating review: {exc.status} — {exc.read().decode()[:200]}",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc


def main() -> None:
    diff, pr_number, owner, repo, head_sha = get_pr_diff()
    if not diff.strip():
        print("Empty diff — nothing to review.")
        return

    # Invalidate any older approval-looking comment before the model call.
    # A synchronize event must never leave stale review evidence looking current.
    upsert_review(REVIEW_PENDING, pr_number, owner, repo, head_sha)
    review = review_diff(diff)
    if not review:
        print("Current-head agent review did not produce a verdict.", file=sys.stderr)
        raise SystemExit(1)

    upsert_review(review, pr_number, owner, repo, head_sha)


if __name__ == "__main__":
    main()
