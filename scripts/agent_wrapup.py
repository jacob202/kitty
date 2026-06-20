#!/usr/bin/env python3
"""Create a concrete session wrap-up template for the next agent."""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = ROOT / ".agent" / "session_logs"


def _run(args: list[str]) -> str:
    result = subprocess.run(
        args,
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    output = (result.stdout + result.stderr).strip()
    return output or f"(no output, exit {result.returncode})"


def main() -> int:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = LOG_DIR / f"{stamp}-handoff.md"

    branch = _run(["git", "branch", "--show-current"])
    head = _run(["git", "rev-parse", "--short", "HEAD"])
    status = _run(["git", "status", "--short", "--branch"])
    diff_stat = _run(["git", "diff", "--stat"])

    body = f"""# Agent Session Wrap-Up

**Created:** {stamp}
**Branch:** {branch}
**HEAD:** {head}

## Git Status

```text
{status}
```

## Diff Stat

```text
{diff_stat}
```

## What Changed

- 

## Verification Run

- 

## Known Gaps Or Risks

- 

## Next Concrete Action

- 
"""
    path.write_text(body, encoding="utf-8")
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
