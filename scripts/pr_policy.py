#!/usr/bin/env python3
"""Deterministic merge-policy gate for Kitty pull requests.

This gate turns the PR template's existing trust claims into executable policy:
user-facing work needs completed product acceptance, risky scope needs an
explicit approval label, and unusually large changes need explicit scope
approval. Dependabot is exempt from prose/template requirements but not from
risk approval.
"""

from __future__ import annotations

import json
import os
import re
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

RISK_APPROVED_LABEL = "risk/approved"
LARGE_CHANGE_APPROVED_LABEL = "risk/large-change-approved"
LARGE_CHANGE_LINES = 1500
LARGE_CHANGE_FILES = 25

RISK_PATTERNS = (
    re.compile(r"^\.github/workflows/"),
    re.compile(r"^\.github/dependabot\.yml$"),
    re.compile(r"^gateway/routes/auth", re.I),
    re.compile(r"^gateway/auth", re.I),
    re.compile(r"^gateway/security", re.I),
    re.compile(r"^gateway/.*secret", re.I),
    re.compile(r"^.*\.env(?:\..*)?$"),
    re.compile(r"^requirements.*\.txt$"),
    re.compile(r"^pyproject\.toml$"),
)

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
    pattern = rf"^-\s*\[[xX]\]\s*{re.escape(text)}\s*$"
    return re.search(pattern, section, re.M) is not None


def _not_user_facing_override(body: str) -> tuple[bool, str]:
    override = body.split("### Not user-facing override", 1)[1] if "### Not user-facing override" in body else ""
    checked = re.search(r"^-\s*\[[xX]\]\s*Not user-facing;", override, re.M) is not None
    reason = _field_value(override, "Reason (required when checked)")
    return checked, reason


def _risky_files(changed_files: list[str]) -> list[str]:
    return [path for path in changed_files if any(p.search(path) for p in RISK_PATTERNS)]


def evaluate_policy(pr: dict[str, Any], changed_files: list[str]) -> list[str]:
    body = str(pr.get("body") or "")
    author = str((pr.get("user") or {}).get("login") or "")
    labels = {
        str(label.get("name"))
        for label in (pr.get("labels") or [])
        if isinstance(label, dict) and label.get("name")
    }
    violations: list[str] = []

    if author != "dependabot[bot]":
        summary = _section(body, "Summary")
        test_plan = _section(body, "Test plan")
        if not summary or not re.search(r"^-\s+\S", summary, re.M):
            violations.append("PR body requires `## Summary` with at least one bullet")
        if not test_plan or not re.search(r"^-\s|^-\s*\[[ xX]\]", test_plan, re.M):
            violations.append("PR body requires `## Test plan` with at least one bullet/checklist item")

        not_user_facing, override_reason = _not_user_facing_override(body)
        if not_user_facing:
            if not _has_content(override_reason):
                violations.append("not-user-facing override requires a concrete reason")
        else:
            acceptance = _section(
                body,
                "Product acceptance (required for user-facing changes)",
                until="### Not user-facing override",
            )
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
    if risky and RISK_APPROVED_LABEL not in labels:
        violations.append(f"risky scope requires label `{RISK_APPROVED_LABEL}`")

    changed_lines = int(pr.get("additions") or 0) + int(pr.get("deletions") or 0)
    changed_count = int(pr.get("changed_files") or len(changed_files))
    if (changed_lines > LARGE_CHANGE_LINES or changed_count > LARGE_CHANGE_FILES) and LARGE_CHANGE_APPROVED_LABEL not in labels:
        violations.append(f"large change requires label `{LARGE_CHANGE_APPROVED_LABEL}`")

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
    files: list[str] = []
    page = 1
    while True:
        url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/files?per_page=100&page={page}"
        payload = _github_json(url, token)
        if not isinstance(payload, list):
            raise RuntimeError("GitHub list-files response was not a list")
        files.extend(str(item["filename"]) for item in payload if isinstance(item, dict) and item.get("filename"))
        if len(payload) < 100:
            return files
        page += 1


def main() -> None:
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path:
        print("GITHUB_EVENT_PATH is required", file=sys.stderr)
        raise SystemExit(1)
    try:
        with open(event_path, encoding="utf-8") as event_file:
            event = json.load(event_file)
        pr = event["pull_request"]
        repo = event["repository"]
        owner = str(repo["owner"]["login"])
        name = str(repo["name"])
        number = int(pr["number"])
        files = _changed_files(owner, name, number, os.environ.get("GITHUB_TOKEN", ""))
    except (KeyError, ValueError, TypeError, OSError, HTTPError, URLError, TimeoutError, json.JSONDecodeError, RuntimeError) as exc:
        print(f"PR policy could not inspect current PR state: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    violations = evaluate_policy(pr, files)
    if violations:
        print("PR policy blocked this head:", file=sys.stderr)
        for violation in violations:
            print(f"- {violation}", file=sys.stderr)
        raise SystemExit(1)
    print("PR policy passed.")


if __name__ == "__main__":
    main()
