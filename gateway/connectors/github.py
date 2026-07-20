"""GitHub read-only connector (P5b, docs/packets/020).

Polls GitHub for open PRs, their check-run status, new review comments, and
open issues across configured repositories, emitting deduped signal rows.

Scope: personal access token (classic) with `repo:read`. No write scopes.
The connector only issues GET requests and refuses to construct any mutating
call — see `GithubConnector` (there is no write path). Signal payloads carry
repo / PR / issue / check / review summaries only; never diffs or bodies.
Tokens are never logged: warnings name the repo and PR/issue number, not the
credential.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Callable, Optional

logger = logging.getLogger("kitty.connector.github")

GITHUB_API_BASE = "https://api.github.com"
GITHUB_DEFAULT_REPOS = ["jacob202/kitty"]


class GithubConnectorError(RuntimeError):
    """Base for github-connector failures."""


class GithubAuthError(GithubConnectorError):
    """Token missing, invalid, or unauthorized."""


class GithubTransportError(GithubConnectorError):
    """GitHub returned non-200 or unexpected structure."""


@dataclass
class PollResult:
    new: int
    deduped: int
    errors: int = 0

    def to_dict(self) -> dict[str, int]:
        return {"new": self.new, "deduped": self.deduped, "errors": self.errors}


HttpGet = Callable[[str, dict[str, str], dict[str, str]], dict[str, Any]]


def _default_http_get(url: str, params: dict[str, str], headers: dict[str, str]) -> dict[str, Any]:
    import requests

    resp = requests.get(url, params=params, headers=headers, timeout=15)
    if not 200 <= resp.status_code < 300:
        if resp.status_code == 401 or resp.status_code == 403:
            raise GithubAuthError(f"GitHub Auth failed: {resp.status_code} {resp.text[:200]}")
        raise GithubTransportError(f"GitHub GET failed: {resp.status_code} {resp.text[:200]}")
    parsed = resp.json()
    if isinstance(parsed, list):
        return {"items": parsed}
    return parsed


class GithubConnector:
    SOURCE = "github"

    def __init__(
        self,
        token: str,
        repos: list[str],
        *,
        http_get: Optional[HttpGet] = None,
        api_base: str = GITHUB_API_BASE,
    ) -> None:
        self._token = token
        self._repos = repos
        self._http_get = http_get or _default_http_get
        self._api_base = api_base

    def _auth_headers(self) -> dict[str, str]:
        if not self._token:
            raise GithubAuthError("no token bound to connector")
        return {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def poll(self) -> PollResult:
        if not self._token:
            raise GithubAuthError("no token bound to connector")

        from gateway.signal_store import emit

        new_count = 0
        deduped_count = 0
        errors = 0

        for repo in self._repos:
            try:
                prs_resp = self._http_get(f"{self._api_base}/repos/{repo}/pulls", {"state": "open", "per_page": "50"}, self._auth_headers())
                prs = prs_resp.get("items", []) if "items" in prs_resp else prs_resp
            except Exception as exc:
                logger.warning("github: failed to list PRs for %s: %s", repo, exc)
                errors += 1
                continue

            for pr in prs:
                if not isinstance(pr, dict):
                    continue
                pr_number = pr.get("number")
                if not pr_number:
                    continue

                # Emit PR signal
                pr_payload = {
                    "repo": repo,
                    "pr_number": pr_number,
                    "title": pr.get("title", ""),
                    "state": pr.get("state", ""),
                    "draft": pr.get("draft", False),
                    "url": pr.get("html_url", ""),
                    "user": pr.get("user", {}).get("login", ""),
                }
                dedupe_pr = f"github:pr:{repo}:{pr_number}:state:{pr.get('state')}"
                rec = emit(source=self.SOURCE, kind="github.pr", payload=pr_payload, dedupe_key=dedupe_pr)
                if rec:
                    new_count += 1
                else:
                    deduped_count += 1

                # Fetch check runs
                head_sha = pr.get("head", {}).get("sha")
                if head_sha:
                    try:
                        checks_resp = self._http_get(f"{self._api_base}/repos/{repo}/commits/{head_sha}/check-runs", {}, self._auth_headers())
                        check_runs = checks_resp.get("check_runs", [])
                        for check in check_runs:
                            status = check.get("status")
                            conclusion = check.get("conclusion")
                            check_name = check.get("name")

                            check_payload = {
                                "repo": repo,
                                "pr_number": pr_number,
                                "check_name": check_name,
                                "status": status,
                                "conclusion": conclusion,
                                "url": check.get("html_url", ""),
                            }
                            dedupe_check = f"github:check:{repo}:{pr_number}:{check_name}:{status}:{conclusion}"
                            rec = emit(source=self.SOURCE, kind="github.check", payload=check_payload, dedupe_key=dedupe_check)
                            if rec:
                                new_count += 1
                            else:
                                deduped_count += 1
                    except Exception as exc:
                        logger.warning("github: failed to fetch checks for %s PR %s: %s", repo, pr_number, exc)
                        errors += 1

                # Fetch review comments
                try:
                    comments_resp = self._http_get(f"{self._api_base}/repos/{repo}/pulls/{pr_number}/reviews", {"per_page": "50"}, self._auth_headers())
                    comments = comments_resp.get("items", []) if "items" in comments_resp else comments_resp
                    for comment in comments:
                        if not isinstance(comment, dict):
                            continue
                        comment_id = comment.get("id")
                        comment_state = comment.get("state")

                        comment_payload = {
                            "repo": repo,
                            "pr_number": pr_number,
                            "comment_id": comment_id,
                            "state": comment_state,
                            "user": comment.get("user", {}).get("login", ""),
                            "url": comment.get("html_url", ""),
                        }
                        dedupe_comment = f"github:review:{repo}:{pr_number}:{comment_id}:{comment_state}"
                        rec = emit(source=self.SOURCE, kind="github.review", payload=comment_payload, dedupe_key=dedupe_comment)
                        if rec:
                            new_count += 1
                        else:
                            deduped_count += 1
                except Exception as exc:
                    logger.warning("github: failed to fetch reviews for %s PR %s: %s", repo, pr_number, exc)
                    errors += 1

            # Fetch open issues once per repo. GitHub's issues endpoint also
            # returns PRs (with a ``pull_request`` key) — filter those out so
            # they are not double-counted; PRs are emitted above. Bodies are
            # never fetched: issue signals are summary-only, matching the PR path.
            try:
                issues_resp = self._http_get(
                    f"{self._api_base}/repos/{repo}/issues",
                    {"state": "open", "per_page": "50"},
                    self._auth_headers(),
                )
                issues = issues_resp.get("items", []) if "items" in issues_resp else issues_resp
                for issue in issues:
                    if not isinstance(issue, dict):
                        continue
                    if issue.get("pull_request"):
                        continue  # pull requests are emitted as github.pr above
                    issue_number = issue.get("number")
                    if not issue_number:
                        continue
                    issue_payload = {
                        "repo": repo,
                        "issue_number": issue_number,
                        "title": issue.get("title", ""),
                        "state": issue.get("state", ""),
                        "url": issue.get("html_url", ""),
                        "user": issue.get("user", {}).get("login", ""),
                        "labels": [label.get("name", "") for label in issue.get("labels", []) if isinstance(label, dict)],
                        "comments": issue.get("comments", 0),
                    }
                    dedupe_issue = f"github:issue:{repo}:{issue_number}:state:{issue.get('state')}"
                    rec = emit(source=self.SOURCE, kind="github.issue", payload=issue_payload, dedupe_key=dedupe_issue)
                    if rec:
                        new_count += 1
                    else:
                        deduped_count += 1
            except Exception as exc:
                logger.warning("github: failed to fetch issues for %s: %s", repo, exc)
                errors += 1

        return PollResult(new=new_count, deduped=deduped_count, errors=errors)


def is_configured() -> bool:
    """True if GITHUB_TOKEN is set in the environment."""
    return bool(os.environ.get("GITHUB_TOKEN", "").strip())


def poll_now() -> dict[str, Any]:
    """Cron entry point: load token, poll, return a result dict."""
    if not is_configured():
        logger.warning("github.poll skipped: GITHUB_TOKEN not present")
        return {"new": 0, "deduped": 0, "errors": 0, "skipped": "unconfigured"}

    raw_token = os.environ.get("GITHUB_TOKEN")
    if not raw_token or not raw_token.strip():
        # is_configured() returned True but the env may have been cleared
        # between the two reads; treat as an auth miss instead of a KeyError
        # crash. See audit §2.4 / AUDIT_FULL_ENGINEERING_2026-07-20.md.
        logger.warning("github.poll aborted: GITHUB_TOKEN missing at fetch")
        return {
            "new": 0,
            "deduped": 0,
            "errors": 1,
            "skipped": "token-missing-at-fetch",
        }
    token = raw_token.strip()
    repos_env = os.environ.get("GITHUB_WATCH_REPOS", "").strip()
    repos = [r.strip() for r in repos_env.split(",")] if repos_env else GITHUB_DEFAULT_REPOS

    connector = GithubConnector(token, repos)
    try:
        result = connector.poll()
    except GithubConnectorError as exc:
        logger.warning("github.poll failed: %s", exc)
        return {"new": 0, "deduped": 0, "errors": 1, "skipped": str(exc)}
    return result.to_dict()
