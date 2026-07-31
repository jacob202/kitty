#!/usr/bin/env python3
"""Generate a focused coding-session workflow scaffold."""

from __future__ import annotations

import argparse
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _repo_root() -> Path:
    override = os.environ.get("KITTY_VIBE_ROOT")
    if override:
        return Path(override).expanduser().resolve()
    return Path(__file__).resolve().parent.parent


def _minutes(raw: str) -> int:
    value = int(raw)
    if value < 45 or value > 90:
        raise argparse.ArgumentTypeError("minutes must be between 45 and 90")
    return value


def _build_body(
    *,
    outcome: str,
    active_task: str | None,
    minutes: int,
    start_time: datetime,
) -> str:
    end_time = start_time + timedelta(minutes=minutes)
    task_line = active_task or "(choose one active task before coding)"
    return f"""# Vibe Coder Session

## 1) Session loop
- Outcome: {outcome}
- Timebox: {minutes} minutes
- Start (UTC): {start_time.isoformat()}
- End target (UTC): {end_time.isoformat()}

## 2) Strict task funnel
- Active task: {task_line}
- Quick captures for later (backlog):
  - [ ] 
  - [ ] 
- Parking-lot interruptions:
  - [ ] 
  - [ ] 

## 3) Start checklist (before coding)
- [ ] Repo state checked (`git status --short --branch`)
- [ ] Scope stated in one sentence
- [ ] Done criteria listed (tests/checks/docs)
  - [ ] Tests:
  - [ ] Checks:
  - [ ] Docs:

## 4) Tight implementation loop
- [ ] Keep smallest possible diff
- [ ] One concern per commit
- [ ] Run narrowest relevant tests first

## 5) PR quality checklist
- [ ] Clear PR title
- [ ] User impact summary
- [ ] Exact verification commands and results
- [ ] Explicitly note intentionally skipped work

## 6) Anti-chaos guardrails
- [ ] No context switching during this session
- [ ] No unplanned scope creep
- [ ] Interruptions moved to parking lot/backlog

## 7) End-of-session handoff note
- Outcome completed:
- Remaining work:
- Next concrete action:
- Evidence (tests/checks run):
- Blockers/risks:

## Weekly review (15 min)
- What caused friction this week?
- What repeated and should become a rule?
- What can be automated next week?
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("outcome", help="single session outcome")
    parser.add_argument(
        "--active-task",
        help="the one task to keep active during this session",
    )
    parser.add_argument(
        "--minutes",
        type=_minutes,
        default=60,
        help="timebox in minutes (45-90)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="optional explicit output path",
    )
    args = parser.parse_args()

    root = _repo_root()
    log_dir = root / ".agent" / "session_logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc).replace(microsecond=0)
    if args.output:
        output_path = args.output.expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        stamp = now.strftime("%Y%m%dT%H%M%SZ")
        output_path = log_dir / f"{stamp}-vibe-session.md"

    body = _build_body(
        outcome=args.outcome,
        active_task=args.active_task,
        minutes=args.minutes,
        start_time=now,
    )
    output_path.write_text(body, encoding="utf-8")
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
