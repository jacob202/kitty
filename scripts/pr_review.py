#!/usr/bin/env python3
"""PR agent review — sends the PR diff to an LLM and posts a review comment.

Requires GITHUB_TOKEN (provided by Actions) and OPENROUTER_API_KEY (repo secret).
Skips silently if OPENROUTER_API_KEY is not set.
"""

import json, os, sys
from urllib.request import Request, urlopen
from urllib.error import HTTPError

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
REVIEW_MODEL = os.environ.get("PR_REVIEW_MODEL", "openai/gpt-4o-mini")

SYSTEM_PROMPT = """You are a code reviewer. Review the following PR diff. Focus on:
- Bugs, logic errors, off-by-one, wrong operators
- Missing error handling or swallowed exceptions
- Security issues (injection, secrets exposed)
- Broken patterns or reimplementations of existing utilities
- Missing tests for changed logic
- N+1 queries or performance regressions

Be concise. Use bullet points. Skip nitpicks about style or formatting.
If the change looks good, say so briefly.
Never suggest adding comments."""


def get_pr_diff() -> tuple[str, int, str, str]:
    """Return (diff, pr_number, repo_owner, repo_name) from the event payload."""
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path:
        print("No GITHUB_EVENT_PATH — not running in GitHub Actions?", file=sys.stderr)
        sys.exit(0)

    with open(event_path) as f:
        event = json.load(f)

    pr = event.get("pull_request")
    if not pr:
        print("No pull_request in event — not a PR event.", file=sys.stderr)
        sys.exit(0)

    diff_url = pr.get("diff_url")
    if not diff_url:
        print("No diff_url in PR payload.", file=sys.stderr)
        sys.exit(1)

    repo = event.get("repository", {})
    owner = repo.get("owner", {}).get("login", "")
    name = repo.get("name", "")
    pr_number = pr.get("number", 0)

    req = Request(diff_url)
    with urlopen(req) as resp:
        diff = resp.read().decode("utf-8")

    return diff, pr_number, owner, name


def review_diff(diff: str) -> str | None:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("OPENROUTER_API_KEY not set — skipping LLM review.", file=sys.stderr)
        return None

    body = json.dumps({
        "model": REVIEW_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Review this PR diff:\n\n```diff\n{diff[:30000]}\n```"}
        ],
        "temperature": 0.1,
        "max_tokens": 2000,
    }).encode()

    req = Request(OPENROUTER_URL, data=body, method="POST")
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("Content-Type", "application/json")

    try:
        with urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read())
    except HTTPError as e:
        print(f"OpenRouter API error: {e.status} — {e.read().decode()[:200]}", file=sys.stderr)
        return None

    choices = result.get("choices", [])
    if not choices:
        print("No choices in OpenRouter response.", file=sys.stderr)
        return None

    return choices[0].get("message", {}).get("content")


def post_review(review: str, pr_number: int, owner: str, repo: str) -> None:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("No GITHUB_TOKEN — cannot post review.", file=sys.stderr)
        return

    api_url = f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/comments"
    body = json.dumps({"body": f"## Agent PR Review\n\n{review}"}).encode()

    req = Request(api_url, data=body, method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")

    try:
        with urlopen(req, timeout=30) as resp:
            resp.read()
    except HTTPError as e:
        print(f"GitHub API error posting review: {e.status} — {e.read().decode()[:200]}", file=sys.stderr)


def main() -> None:
    diff, pr_number, owner, repo = get_pr_diff()
    if not diff.strip():
        print("Empty diff — nothing to review.")
        return

    review = review_diff(diff)
    if not review:
        return

    post_review(review, pr_number, owner, repo)
    print("PR review posted.")


if __name__ == "__main__":
    main()
