#!/usr/bin/env python3
"""Daily stale-state report. Facts come only from git/gh; never guessed."""
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

REPO = os.environ.get("GITHUB_REPOSITORY", "")
TITLE_PREFIX = "NEEDS JACOB — "
PLANNING_EXTENSIONS = {".json", ".md", ".txt", ".yaml", ".yml"}
NOW = datetime.now(timezone.utc)


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def gh_call(args):
    result = run(["gh"] + args + ["--repo", REPO])
    if result.returncode:
        detail = result.stderr.strip() or "unknown gh error"
        print(f"stale scan failed: gh {' '.join(args[:2])}: {detail}", file=sys.stderr)
        raise SystemExit(1)
    return result


def gh_json(args):
    try:
        return json.loads(gh_call(args).stdout)
    except ValueError:
        print(f"stale scan failed: invalid JSON from gh {' '.join(args[:2])}", file=sys.stderr)
        raise SystemExit(1)


def timestamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def age_days(value):
    return (NOW - timestamp(value)).days


def scanner_started_at():
    result = run(["git", "log", "--diff-filter=A", "--format=%cI", "--", "scripts/scan.py"])
    commits = [line for line in result.stdout.splitlines() if line]
    if result.returncode or not commits:
        print("stale scan failed: cannot derive scanner activation commit", file=sys.stderr)
        raise SystemExit(1)
    return timestamp(commits[-1])


def is_planning_artifact(path):
    parts = path.lower().split("/")
    name = parts[-1]
    suffix = "." + name.rsplit(".", 1)[1] if "." in name else ""
    if suffix not in PLANNING_EXTENSIONS:
        return False
    if any(part in {"plan", "plans", "roadmap", "roadmaps"} for part in parts[:-1]):
        return True
    stem = name.rsplit(".", 1)[0]
    return bool(set(re.split(r"[-_.]+", stem)) & {"plan", "plans", "roadmap", "roadmaps"})


started_at = scanner_started_at()
findings = []
refs = run(["git", "for-each-ref", "--format=%(refname:short)", "refs/remotes/origin"])
branches = [b for b in refs.stdout.splitlines() if b not in ("origin/HEAD", "origin/main")]
unmerged = {}

# Rule 1: post-activation branch ahead of main, idle 7+ days, unmerged.
for branch in branches:
    if run(["git", "merge-base", "--is-ancestor", branch, "origin/main"]).returncode == 0:
        continue
    ahead = run(["git", "rev-list", "--count", f"origin/main..{branch}"])
    last = run(["git", "log", "-1", "--format=%cI", branch])
    try:
        ahead_n = int(ahead.stdout.strip())
        last_at = timestamp(last.stdout.strip())
    except (ValueError, TypeError):
        continue
    if not ahead_n or last_at < started_at:
        continue  # grandfather pre-scanner backlog until it becomes active again
    name = branch.removeprefix("origin/")
    unmerged[name] = last_at
    age = (NOW - last_at).days
    if age >= 7:
        findings.append(f"Branch `{name}` is {age}d idle with unmerged commits — merge it into main or delete it.")

# Rule 2: post-activation open PR, no activity 3+ days.
for pr in gh_json(["pr", "list", "--state", "open", "--json", "number,title,updatedAt"]):
    if timestamp(pr["updatedAt"]) >= started_at and age_days(pr["updatedAt"]) >= 3:
        findings.append(f"PR #{pr['number']} \"{pr['title']}\" has had no activity for {age_days(pr['updatedAt'])}d — review it or close it.")

# Rule 3: main CI inactive for 7+ days after scanner activation.
runs = gh_json(["run", "list", "--branch", "main", "--event", "push", "--json", "createdAt", "--limit", "1"])
if runs:
    last_ci = max(timestamp(runs[0]["createdAt"]), started_at)
    if (NOW - last_ci).days >= 7:
        findings.append(f"CI hasn't run on main in {(NOW - last_ci).days}d — push to main or re-run the workflow.")

# Rule 4: planning artifact touched after activation on an unmerged branch.
for name in sorted(unmerged):
    log = run(["git", "log", f"--since={started_at.isoformat()}", "--name-only", "--format=", f"origin/main..origin/{name}"])
    hits = sorted({path for path in log.stdout.splitlines() if path.strip() and is_planning_artifact(path)})
    if log.returncode == 0 and hits:
        findings.append(f"`{name}` touched {hits[0]} after stale-scan activation and remains unmerged — merge it or fold it into main.")

# Report one issue, or close it when nothing needs attention.
today = NOW.strftime("%Y-%m-%d")
issues = gh_json(["issue", "list", "--state", "open", "--search", "NEEDS JACOB in:title", "--json", "number,title"])
issues = [issue for issue in issues if issue["title"].startswith(TITLE_PREFIX)]
if not findings:
    for issue in issues:
        gh_call(["issue", "close", str(issue["number"])])
    raise SystemExit(0)

body = "\n".join(f"- {finding}" for finding in findings)
if issues:
    gh_call(["issue", "edit", str(issues[0]["number"]), "--title", f"{TITLE_PREFIX}{today}", "--body", body])
else:
    gh_call(["issue", "create", "--title", f"{TITLE_PREFIX}{today}", "--body", body])
