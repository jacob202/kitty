#!/usr/bin/env python3
"""Canonical change-scope classifier for Kitty's delivery pipeline.

Every consumer derives scope from this one module: required PR CI job selection,
post-merge validation scope, and the sensitive-scope trust gate in
``scripts/pr_policy.py``. A second independently maintained path list in workflow
YAML or JavaScript would drift away from the policy it claims to describe, and a
classifier that disagrees with the policy gate is a trust hole rather than a
convenience.

Run as a module inside GitHub Actions to publish the scope of the current event:

    python -m scripts.pr_scope

It resolves the changed files for a ``pull_request``/``pull_request_target``
payload or a ``push`` payload and writes ``code``, ``frontend``, ``sensitive``,
and ``docs_only`` to ``$GITHUB_OUTPUT``. It raises instead of guessing when the
changed-file set cannot be resolved; the aggregate merge gate requires this job
to succeed, so an unresolved scope blocks rather than silently narrows CI.
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DOC_PREFIXES = ("docs/",)
DOC_SUFFIXES = (".md", ".mdx")
FRONTEND_PREFIX = "gateway/kitty-chat/"

# Sensitive scope: changes that can alter what the delivery pipeline trusts, what
# it can reach, or what it can spend. These require label + exact-head approval +
# trusted independent review in `scripts/pr_policy.py`.
RISK_PATTERNS = (
    re.compile(r"^\.github/workflows/"),
    re.compile(r"^\.github/dependabot\.yml$"),
    re.compile(r"^scripts/pr_(?:policy|review|review_gate|scope)\.py$"),
    re.compile(r"^gateway/routes/auth", re.I),
    re.compile(r"^gateway/auth", re.I),
    re.compile(r"^gateway/security", re.I),
    re.compile(r"^gateway/.*secret", re.I),
    re.compile(r"^gateway/action_(?:queue|grants)\.py$"),
    re.compile(r"^gateway/routes/actions\.py$"),
    re.compile(r"^gateway/builder_(?:publish|pr_janitor)\.py$"),
    re.compile(r"^scripts/purge_.*\.py$"),
    re.compile(r"^.*\.env(?:\..*)?$"),
    re.compile(r"^requirements.*\.txt$"),
    re.compile(r"^pyproject\.toml$"),
)

USER_FACING_PATTERNS = (re.compile(r"^gateway/kitty-chat/(?:src|public)/"),)

# GitHub's compare endpoint returns at most 300 files. A truncated comparison
# cannot prove a merge was docs-only, so it widens to full scope instead.
COMPARE_FILE_LIMIT = 300

_EMPTY_SHA = "0" * 40


def is_documentation(path: str) -> bool:
    return path.startswith(DOC_PREFIXES) or path.endswith(DOC_SUFFIXES)


def risky_files(paths: list[str]) -> list[str]:
    return [path for path in paths if any(pattern.search(path) for pattern in RISK_PATTERNS)]


def is_user_facing(paths: list[str]) -> bool:
    return any(any(pattern.search(path) for pattern in USER_FACING_PATTERNS) for path in paths)


@dataclass(frozen=True)
class Scope:
    """The classification every delivery-pipeline consumer reads."""

    code: bool
    frontend: bool
    sensitive: bool
    user_facing: bool
    risky_files: tuple[str, ...]

    @property
    def docs_only(self) -> bool:
        return not self.code

    def as_outputs(self) -> dict[str, str]:
        return {
            "code": _flag(self.code),
            "frontend": _flag(self.frontend),
            "sensitive": _flag(self.sensitive),
            "docs_only": _flag(self.docs_only),
        }


def _flag(value: bool) -> str:
    return "true" if value else "false"


def classify(paths: list[str]) -> Scope:
    """Classify a changed-file set. An empty set is docs-only by construction."""
    risky = tuple(risky_files(paths))
    return Scope(
        code=any(not is_documentation(path) for path in paths),
        frontend=any(
            path.startswith(FRONTEND_PREFIX) and not is_documentation(path) for path in paths
        ),
        sensitive=bool(risky),
        user_facing=is_user_facing(paths),
        risky_files=risky,
    )


FULL_SCOPE = Scope(code=True, frontend=True, sensitive=True, user_facing=True, risky_files=())


def _github_json(url: str, token: str) -> Any:
    req = Request(url)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def pull_request_files(
    owner: str,
    repo: str,
    pr_number: int,
    token: str,
    *,
    fetch: Callable[[str, str], Any] | None = None,
) -> list[str]:
    """List every file a pull request changes, following pagination to the end."""
    fetch = fetch or _github_json
    files: list[str] = []
    page = 1
    while True:
        url = (
            f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
            f"/files?per_page=100&page={page}"
        )
        payload = fetch(url, token)
        if not isinstance(payload, list):
            raise RuntimeError("GitHub list-files response was not a list")
        files.extend(
            str(item["filename"])
            for item in payload
            if isinstance(item, dict) and item.get("filename")
        )
        if len(payload) < 100:
            return files
        page += 1


def push_scope(owner: str, repo: str, before: str, after: str, token: str) -> Scope:
    """Classify a push by comparing it with the commit it replaced.

    A first push, a force push, or a comparison GitHub truncates cannot prove
    what changed, so those widen to full scope rather than skipping evidence.
    """
    if not re.fullmatch(r"[0-9a-f]{40}", before or "") or before == _EMPTY_SHA:
        print("Push has no resolvable predecessor commit; validating at full scope.")
        return FULL_SCOPE

    url = f"https://api.github.com/repos/{owner}/{repo}/compare/{before}...{after}"
    payload = _github_json(url, token)
    if not isinstance(payload, dict) or not isinstance(payload.get("files"), list):
        raise RuntimeError("GitHub compare response did not contain a file list")

    files = [
        str(item["filename"])
        for item in payload["files"]
        if isinstance(item, dict) and item.get("filename")
    ]
    if len(files) >= COMPARE_FILE_LIMIT:
        print(
            f"Compare listed {len(files)} files and may be truncated; "
            "validating at full scope."
        )
        return FULL_SCOPE
    return classify(files)


def scope_for_event(event: dict[str, Any], event_name: str, token: str) -> Scope:
    """Resolve the scope of the live GitHub event this job is running for."""
    repo = event.get("repository") or {}
    owner = str((repo.get("owner") or {}).get("login") or "")
    name = str(repo.get("name") or "")
    if not owner or not name:
        raise RuntimeError("event payload is missing repository owner/name")

    pull_request = event.get("pull_request")
    if isinstance(pull_request, dict):
        number = int(pull_request.get("number") or 0)
        if not number:
            raise RuntimeError("pull_request payload is missing a number")
        return classify(pull_request_files(owner, name, number, token))

    merge_group = event.get("merge_group")
    if isinstance(merge_group, dict):
        # The merge queue's temporary commit has no PR number of its own to
        # fetch changed files for; base_sha/head_sha span exactly what this
        # queue entry would add to main, same shape as a push comparison.
        return push_scope(
            owner, name, str(merge_group.get("base_sha") or ""), str(merge_group.get("head_sha") or ""), token
        )

    if event_name == "push" or ("before" in event and "after" in event):
        return push_scope(
            owner, name, str(event.get("before") or ""), str(event.get("after") or ""), token
        )

    # workflow_dispatch, schedule, and anything else that names no diff get the
    # widest scope: they exist to re-validate the whole tree.
    print(f"Event '{event_name}' names no changed-file set; validating at full scope.")
    return FULL_SCOPE


def _write_outputs(scope: Scope) -> None:
    outputs = scope.as_outputs()
    for key, value in outputs.items():
        print(f"{key}={value}")
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        return
    with open(output_path, "a", encoding="utf-8") as handle:
        for key, value in outputs.items():
            handle.write(f"{key}={value}\n")


def main() -> None:
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path:
        print("GITHUB_EVENT_PATH is required", file=sys.stderr)
        raise SystemExit(1)
    try:
        with open(event_path, encoding="utf-8") as event_file:
            event = json.load(event_file)
        scope = scope_for_event(
            event,
            os.environ.get("GITHUB_EVENT_NAME", ""),
            os.environ.get("GITHUB_TOKEN", ""),
        )
    except (
        KeyError,
        ValueError,
        TypeError,
        OSError,
        HTTPError,
        URLError,
        TimeoutError,
        json.JSONDecodeError,
        RuntimeError,
    ) as exc:
        print(
            f"Could not classify change scope: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc

    if scope.risky_files:
        print(f"Sensitive scope: {', '.join(scope.risky_files)}")
    _write_outputs(scope)


if __name__ == "__main__":
    main()
