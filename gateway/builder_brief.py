"""KittyBuilder Phase 1B — worker brief renderer.

Turns a queue task into a complete, self-contained worker prompt: scope,
acceptance criteria, branch, validation, fencing rules, and stop conditions.
Pure presentation — no DB access, no side effects. The CLI feeds it the task
dict, its events, and its PR links.
"""

from __future__ import annotations

import json
from typing import Any

# Recent-event window: enough for takeover context without dumping history.
_EVENT_TAIL = 10


def default_branch_name(task: dict[str, Any]) -> str:
    return f"kittybuilder/{task['id']}"


def render_worker_brief(
    task: dict[str, Any],
    events: list[dict[str, Any]],
    pr_links: list[dict[str, Any]],
    *,
    branch: str | None = None,
) -> str:
    """Render a markdown worker brief for a queue task."""
    branch = branch or default_branch_name(task)
    lines: list[str] = []
    add = lines.append

    add(f"# KittyBuilder task brief — {task['id']}")
    add("")
    add(f"**Title:** {task['title']}")
    add(f"**State:** {task['state']}   **Priority:** {task.get('priority', 0)}")
    owner = task.get("lease_owner")
    if owner and task["state"] not in ("queued", "done", "failed", "cancelled"):
        add(f"**Current owner:** {owner} (check the lease before taking over)")
    add(f"**Branch:** `{branch}` (from clean, up-to-date `main`)")
    add("")

    if task.get("description"):
        add("## Description")
        add("")
        add(str(task["description"]))
        add("")

    add("## Acceptance criteria")
    add("")
    criteria = task.get("acceptance_criteria") or []
    if criteria:
        for i, criterion in enumerate(criteria, 1):
            add(f"{i}. {criterion}")
    else:
        add(
            "None recorded. STOP: ask the operator to add acceptance criteria "
            "(`queue edit --acceptance`) before starting work."
        )
    add("")

    add("## Allowed scope")
    add("")
    allowed = task.get("allowed_paths") or []
    if allowed:
        add("You may modify only these paths:")
        add("")
        for path in allowed:
            add(f"- `{path}`")
        add("")
        add("Everything else is FORBIDDEN scope. If the task genuinely needs")
        add("another path, stop and transition to `blocked` with the reason —")
        add("do not silently broaden scope.")
    else:
        add(
            "No path allowlist recorded — keep the diff to the smallest set of "
            "files the acceptance criteria require, and list every touched "
            "file in your final report."
        )
    add("")
    add("Never touch: secrets/auth/env files, `.claude/`, unrelated code,")
    add("or anything requiring deletion/force-push. Do not add dependencies.")
    add("")

    add("## Validation required before reporting")
    add("")
    add("- `python3.12 -m pytest tests/ -q --tb=short` for touched areas")
    add("  (always include the focused test files for changed modules)")
    add("- Type check touched Python files (mypy) where the repo does")
    add("- UI changes: `make ui-test && make ui-build` + live evidence")
    add("- Every acceptance criterion above verified, with the command/output")
    add("  that proves it")
    add("")

    add("## Fencing rules")
    add("")
    add("Claim before working; keep the `lease_token` and `claim_version`")
    add("from the claim output — every state mutation requires both:")
    add("")
    add(f"    ./kitty builder queue claim {task['id']} --worker <you> --json")
    add(f"    ./kitty builder queue transition {task['id']} running \\")
    add("        --lease-token <token> --claim-version <version>")
    add("")
    add("If any fenced command reports a stale lease, another worker owns the")
    add("task — stop immediately and do not push further changes.")
    add("")

    add("## Stop conditions")
    add("")
    add("- Work complete → attach a final report (`queue attach-report`),")
    add("  transition per the lifecycle, and STOP. Never merge.")
    add("- Blocked → transition to `blocked` with a reason payload and STOP.")
    add("- Scope conflict, failing unrelated tests, or missing context →")
    add("  `blocked` with details. Guessing is worse than stopping.")
    add("- Follow `docs/WORKFLOW.md` for PR reports; push/PR/merge remain")
    add("  operator-gated.")
    add("")

    reports = _last_report(task)
    if reports:
        add("## Previous final report (takeover context)")
        add("")
        add("```json")
        add(json.dumps(reports, indent=2, default=str))
        add("```")
        add("")

    if pr_links:
        add("## Attached PRs")
        add("")
        for link in pr_links:
            parts = [f"- PR #{link['pr_number']}"]
            if link.get("pr_url"):
                parts.append(str(link["pr_url"]))
            if link.get("head_sha"):
                parts.append(f"head `{str(link['head_sha'])[:10]}`")
            if link.get("checks_state"):
                parts.append(f"checks: {link['checks_state']}")
            if link.get("review_state"):
                parts.append(f"review: {link['review_state']}")
            add("  ".join(parts))
        add("")

    if events:
        add(f"## Recent events (last {min(len(events), _EVENT_TAIL)})")
        add("")
        for event in events[-_EVENT_TAIL:]:
            payload = event.get("payload")
            payload_str = f" {json.dumps(payload, default=str)}" if payload else ""
            add(f"- {event.get('created_at', '')}  **{event.get('type', '')}**{payload_str}")
        add("")

    return "\n".join(lines)


def _last_report(task: dict[str, Any]) -> dict[str, Any] | None:
    raw = task.get("final_report_json")
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    return parsed if isinstance(parsed, dict) else None
