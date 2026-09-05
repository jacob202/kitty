#!/usr/bin/env python3
"""Daily stale-state report. Facts come only from git/gh; never guessed."""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

REPO = os.environ.get("GITHUB_REPOSITORY", "")
TITLE_PREFIX = "NEEDS JACOB — "


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def gh_json(args):
    r = run(["gh"] + args + ["--repo", REPO])
    if r.returncode != 0:
        return None
    try:
        return json.loads(r.stdout)
    except ValueError:
        return None


def days_since(iso):
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return (datetime.now(timezone.utc) - dt).days


findings = []

# Rule 1: branch ahead of main, idle 7+ days, unmerged.
refs = run(["git", "for-each-ref", "--format=%(refname:short)", "refs/remotes/origin"])
branches = [b for b in refs.stdout.splitlines() if b not in ("origin/HEAD", "origin/main")]

unmerged_branches = {}
for b in branches:
    if run(["git", "merge-base", "--is-ancestor", b, "origin/main"]).returncode == 0:
        continue  # already merged into main
    ahead = run(["git", "rev-list", "--count", f"origin/main..{b}"])
    try:
        ahead_n = int(ahead.stdout.strip())
    except ValueError:
        continue
    if ahead_n == 0:
        continue
    last = run(["git", "log", "-1", "--format=%cI", b])
    if last.returncode != 0 or not last.stdout.strip():
        continue
    age = days_since(last.stdout.strip())
    name = b[len("origin/"):]
    unmerged_branches[name] = age
    if age >= 7:
        findings.append(
            f"Branch `{name}` is {age}d idle with unmerged commits — merge it into main or delete it."
        )

# Rule 2: open PR, no activity 3+ days.
prs = gh_json(["pr", "list", "--state", "open", "--json", "number,title,updatedAt"])
if prs is not None:
    for pr in prs:
        age = days_since(pr["updatedAt"])
        if age >= 3:
            findings.append(
                f"PR #{pr['number']} \"{pr['title']}\" has had no activity for {age}d — review it or close it."
            )

# Rule 3: main's last CI run older than 7 days (skip if no CI exists).
runs = gh_json(["run", "list", "--branch", "main", "--event", "push", "--json", "createdAt", "--limit", "1"])
if runs:
    age = days_since(runs[0]["createdAt"])
    if age >= 7:
        findings.append(f"CI hasn't run on main in {age}d — push to main or re-run the workflow.")

# Rule 4: ROADMAP/PLAN file touched in last 30 days on a never-merged branch.
for name, age in sorted(unmerged_branches.items()):
    log = run(["git", "log", "--since=30.days", "--name-only", "--format=", f"origin/main..origin/{name}"])
    if log.returncode != 0:
        continue
    files = sorted({f for f in log.stdout.splitlines() if f.strip()})
    hits = [f for f in files if "roadmap" in f.lower() or "plan" in f.lower()]
    if hits:
        findings.append(
            f"`{name}` touched {hits[0]} in the last 30d and has never merged — merge the branch or fold it into main."
        )

# Report.
today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
existing = gh_json(["issue", "list", "--state", "open", "--search", "NEEDS JACOB in:title", "--json", "number,title"]) or []
existing = [i for i in existing if i["title"].startswith(TITLE_PREFIX)]

if not findings:
    for issue in existing:
        run(["gh", "issue", "close", str(issue["number"]), "--repo", REPO])
    sys.exit(0)

title = f"{TITLE_PREFIX}{today}"
body = "\n".join(f"- {f}" for f in findings)

if existing:
    run(["gh", "issue", "edit", str(existing[0]["number"]), "--repo", REPO, "--title", title, "--body", body])
else:
    run(["gh", "issue", "create", "--repo", REPO, "--title", title, "--body", body])
