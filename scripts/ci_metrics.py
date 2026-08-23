#!/usr/bin/env python3
"""Delivery-pipeline efficiency evidence, derived from GitHub Actions history.

This exists so "the pipeline got faster" is a measurement rather than a feeling.
It adds no service and no database: it reads the Actions API for a time window
and writes one JSON evidence file plus a short Markdown report.

Fields it cannot derive from Actions history are reported as ``null`` with a
recorded reason. Drafts that never ran, review findings that were actually
actionable, and false-positive rates are not in this data; inventing them would
make the whole report untrustworthy.

    python scripts/ci_metrics.py --window-days 14 --out artifacts/ci-metrics
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

API = "https://api.github.com"
TESTS_WORKFLOW = "tests.yml"
REVIEW_WORKFLOW = "pr-agent-review.yml"

CODE_JOBS = ("pytest", "lint", "typecheck")
FRONTEND_JOBS = ("kitty-chat", "browser-smoke")

# Heuristic only: a PR head whose tip commit merges main is almost always a
# strict-up-to-date refresh, which invalidates the exact-head evidence below it.
BEHIND_REFRESH_PREFIXES = (
    "Merge remote-tracking branch 'origin/main'",
    "Merge branch 'main'",
)

NOT_DERIVABLE = {
    "draft_pushes_avoided": "Actions does not record runs that were never triggered.",
    "actionable_review_findings": "Requires reading review comment bodies, not run metadata.",
    "review_overrides": "Recorded in PR bodies and labels, not in run metadata.",
    "hygiene_findings": "Advisory step output is in logs, not in run metadata.",
    "repeated_false_positives": "Requires cross-night finding identity, which this window has no source for.",
}


def _get(url: str, token: str) -> Any:
    req = Request(url)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def _seconds(start: str | None, end: str | None) -> float | None:
    if not start or not end:
        return None
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    return (datetime.strptime(end, fmt) - datetime.strptime(start, fmt)).total_seconds()


def list_runs(repo: str, workflow: str, since: datetime, token: str, limit: int) -> list[dict]:
    runs: list[dict] = []
    page = 1
    created = quote(f">={since.strftime('%Y-%m-%d')}")
    while len(runs) < limit:
        url = (
            f"{API}/repos/{repo}/actions/workflows/{workflow}/runs"
            f"?per_page=100&page={page}&created={created}"
        )
        payload = _get(url, token)
        batch = payload.get("workflow_runs") if isinstance(payload, dict) else None
        if not batch:
            break
        runs.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return runs[:limit]


def list_jobs(repo: str, run_id: int, token: str) -> list[dict]:
    payload = _get(f"{API}/repos/{repo}/actions/runs/{run_id}/jobs?per_page=100", token)
    return payload.get("jobs", []) if isinstance(payload, dict) else []


def _classify_run(jobs: list[dict]) -> str:
    ran = {job["name"] for job in jobs if job.get("conclusion") not in {"skipped", None}}
    if any(name in ran for name in FRONTEND_JOBS):
        return "frontend"
    if any(name in ran for name in CODE_JOBS):
        return "code"
    return "docs-only"


def summarize_tests(repo: str, runs: list[dict], token: str) -> dict[str, Any]:
    per_run: list[dict[str, Any]] = []
    job_seconds: dict[str, list[float]] = {}
    cancelled = 0
    behind_refreshes = 0

    for run in runs:
        if run.get("status") != "completed":
            continue
        if run.get("conclusion") == "cancelled":
            cancelled += 1
        message = str((run.get("head_commit") or {}).get("message") or "")
        if run.get("event") == "pull_request" and message.startswith(BEHIND_REFRESH_PREFIXES):
            behind_refreshes += 1

        jobs = list_jobs(repo, int(run["id"]), token)
        runner_seconds = 0.0
        for job in jobs:
            duration = _seconds(job.get("started_at"), job.get("completed_at"))
            if duration is None or job.get("conclusion") == "skipped":
                continue
            runner_seconds += duration
            job_seconds.setdefault(str(job.get("name")), []).append(duration)

        per_run.append(
            {
                "run_id": run["id"],
                "event": run.get("event"),
                "conclusion": run.get("conclusion"),
                "head_sha": run.get("head_sha"),
                "classification": _classify_run(jobs),
                "wall_seconds": _seconds(run.get("run_started_at"), run.get("updated_at")),
                "runner_seconds": round(runner_seconds, 1),
            }
        )

    def _bucket(predicate) -> dict[str, Any]:
        rows = [row for row in per_run if predicate(row)]
        runner = [row["runner_seconds"] for row in rows]
        wall = [row["wall_seconds"] for row in rows if row["wall_seconds"] is not None]
        return {
            "runs": len(rows),
            "runner_seconds_total": round(sum(runner), 1),
            "runner_seconds_mean": round(sum(runner) / len(runner), 1) if runner else None,
            "wall_seconds_mean": round(sum(wall) / len(wall), 1) if wall else None,
        }

    return {
        "runs_examined": len(per_run),
        "cancelled_superseded_runs": cancelled,
        "branch_behind_refresh_runs_heuristic": behind_refreshes,
        "classification_counts": dict(Counter(row["classification"] for row in per_run)),
        "by_event": {
            "pull_request": _bucket(lambda row: row["event"] == "pull_request"),
            "push": _bucket(lambda row: row["event"] == "push"),
        },
        "by_classification": {
            name: _bucket(lambda row, name=name: row["classification"] == name)
            for name in ("docs-only", "code", "frontend")
        },
        "job_seconds_mean": {
            name: round(sum(values) / len(values), 1) for name, values in sorted(job_seconds.items())
        },
        "runs": per_run,
    }


def summarize_review(repo: str, runs: list[dict], token: str) -> dict[str, Any]:
    model_invocations = 0
    policy_blocks = 0
    policy_evaluations = 0

    for run in runs:
        if run.get("status") != "completed":
            continue
        for job in list_jobs(repo, int(run["id"]), token):
            name = str(job.get("name"))
            conclusion = job.get("conclusion")
            if name == "agent-review" and conclusion not in {"skipped", None}:
                model_invocations += 1
            if name == "policy-gate" and conclusion not in {"skipped", None}:
                policy_evaluations += 1
                if conclusion == "failure":
                    policy_blocks += 1

    return {
        "runs_examined": len(runs),
        "model_review_invocations": model_invocations,
        "policy_gate_evaluations": policy_evaluations,
        "policy_gate_blocks": policy_blocks,
    }


def render_report(payload: dict[str, Any]) -> str:
    tests = payload["tests"]
    review = payload["review"]
    lines = [
        "# Delivery pipeline metrics",
        "",
        f"- Window: {payload['window_days']} days ending {payload['generated_at']}",
        f"- Tests runs examined: {tests['runs_examined']}",
        f"- Cancelled (superseded) runs: {tests['cancelled_superseded_runs']}",
        f"- Branch-behind refresh runs (heuristic): {tests['branch_behind_refresh_runs_heuristic']}",
        f"- Model review invocations: {review['model_review_invocations']}"
        f" over {review['policy_gate_evaluations']} policy-gate evaluations",
        f"- policy-gate blocks: {review['policy_gate_blocks']}",
        "",
        "## Runner minutes by event",
        "",
        "| event | runs | total runner min | mean runner min | mean wall min |",
        "| --- | --- | --- | --- | --- |",
    ]
    for event, bucket in tests["by_event"].items():
        lines.append(
            f"| {event} | {bucket['runs']} | {round(bucket['runner_seconds_total'] / 60, 1)} | "
            f"{_minutes(bucket['runner_seconds_mean'])} | {_minutes(bucket['wall_seconds_mean'])} |"
        )
    lines += ["", "## Runner minutes by change scope", "",
              "| scope | runs | total runner min | mean runner min |", "| --- | --- | --- | --- |"]
    for name, bucket in tests["by_classification"].items():
        lines.append(
            f"| {name} | {bucket['runs']} | {round(bucket['runner_seconds_total'] / 60, 1)} | "
            f"{_minutes(bucket['runner_seconds_mean'])} |"
        )
    lines += ["", "## Mean seconds per job", "", "| job | mean seconds |", "| --- | --- |"]
    for name, value in tests["job_seconds_mean"].items():
        lines.append(f"| {name} | {value} |")
    lines += ["", "## Not derivable from Actions history", ""]
    lines += [f"- `{key}`: {reason}" for key, reason in payload["not_derivable"].items()]
    return "\n".join(lines) + "\n"


def _minutes(seconds: float | None) -> str:
    return "n/a" if seconds is None else str(round(seconds / 60, 1))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--window-days", type=int, default=14)
    parser.add_argument("--max-runs", type=int, default=60)
    parser.add_argument("--out", type=Path, default=Path("artifacts/ci-metrics"))
    args = parser.parse_args(argv)

    if not args.repo:
        print("--repo or GITHUB_REPOSITORY is required", file=sys.stderr)
        return 1
    token = os.environ.get("GITHUB_TOKEN", "")
    since = datetime.now(timezone.utc) - timedelta(days=args.window_days)

    try:
        tests = summarize_tests(
            args.repo, list_runs(args.repo, TESTS_WORKFLOW, since, token, args.max_runs), token
        )
        review = summarize_review(
            args.repo, list_runs(args.repo, REVIEW_WORKFLOW, since, token, args.max_runs), token
        )
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, KeyError) as exc:
        print(f"Could not read Actions history: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    payload = {
        "repo": args.repo,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "window_days": args.window_days,
        "tests": tests,
        "review": review,
        "not_derivable": NOT_DERIVABLE,
    }

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "ci-metrics.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    report = render_report(payload)
    (args.out / "ci-metrics.md").write_text(report, encoding="utf-8")
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
