#!/usr/bin/env python3
"""Verify agent coordination control files exist; warn on stale in-progress lanes."""

from __future__ import annotations

import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
COORD = REPO_ROOT / "docs" / "AGENT_COORDINATION.md"
TEMPLATE = REPO_ROOT / "docs" / "AGENT_HANDOFF_TEMPLATE.md"
STALE_AFTER = timedelta(hours=72)


def _active_lanes_section(text: str) -> str:
    if "## Active Lanes" not in text:
        return ""
    rest = text.split("## Active Lanes", 1)[1]
    if "\n## " in rest:
        rest = rest.split("\n## ", 1)[0]
    return rest


def _parse_started(cell: str) -> date | None:
    cell = cell.strip().strip("`")
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", cell)
    if not m:
        return None
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        return date(y, mo, d)
    except ValueError:
        return None


def stale_in_progress_warnings(section: str, today: date) -> list[str]:
    warnings: list[str] = []
    for raw in section.splitlines():
        line = raw.strip()
        if not line.startswith("|") or "---" in line or line.startswith("| Lane"):
            continue
        if "in-progress" not in line.lower():
            continue
        parts = [p.strip() for p in line.split("|")]
        parts = [p for p in parts if p]
        if len(parts) < 4:
            continue
        started = _parse_started(parts[2])
        if started is None:
            continue
        if today - started > STALE_AFTER:
            lane = parts[0]
            agent = parts[1]
            warnings.append(
                f"Stale lane (>{STALE_AFTER.days}d in-progress): {lane} "
                f"owner={agent} started={started} — see stale-lane rule in AGENT_COORDINATION.md"
            )
    return warnings


def main() -> int:
    missing = [p for p in (COORD, TEMPLATE) if not p.is_file()]
    if missing:
        for p in missing:
            print(f"ERROR: missing required file: {p.relative_to(REPO_ROOT)}", file=sys.stderr)
        return 1

    text = COORD.read_text(encoding="utf-8")
    today = datetime.now(timezone.utc).date()
    for w in stale_in_progress_warnings(_active_lanes_section(text), today):
        print(f"WARNING: {w}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
